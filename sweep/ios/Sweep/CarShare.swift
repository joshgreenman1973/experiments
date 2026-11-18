import CloudKit
import Foundation
import SwiftUI
import UIKit

/// Shares the parked car between two (or more) people through iCloud.
///
/// The car lives in one record ("car") in a custom zone ("Car"). The person who starts sharing owns the
/// zone in their private database and shares the whole zone; whoever accepts reads and writes the same
/// record through their shared database. Every change is stamped with a time, and the newest wins.
/// A silent push (a zone/database subscription) tells the other phone to fetch, so its reminders and
/// calendar move too even when the app isn't open.
@MainActor
final class CarShare: ObservableObject {
    static let shared = CarShare()
    static let containerID = "iCloud.com.joshgreenman.sweep"
    static let zoneName = "Car"
    static let recordType = "ParkedCar"

    enum Role: String { case none, owner, participant }

    @Published private(set) var role: Role
    @Published private(set) var others: [String] = []      // names of the other people on the share
    @Published var problem: String?

    private let defaults = UserDefaults.standard
    /// The Mac preview copy is built without signing, so it has no iCloud entitlement: leave iCloud alone there.
    static var available: Bool {
        #if targetEnvironment(macCatalyst)
        return false
        #else
        return true
        #endif
    }
    private lazy var container = CKContainer(identifier: Self.containerID)

    private init() {
        role = Role(rawValue: UserDefaults.standard.string(forKey: "share.role") ?? "") ?? .none
    }

    private var zoneID: CKRecordZone.ID {
        if role == .participant, let owner = defaults.string(forKey: "share.owner") {
            return CKRecordZone.ID(zoneName: Self.zoneName, ownerName: owner)
        }
        return CKRecordZone.ID(zoneName: Self.zoneName, ownerName: CKCurrentUserDefaultName)
    }
    private var db: CKDatabase { role == .participant ? container.sharedCloudDatabase : container.privateCloudDatabase }
    private var recordID: CKRecord.ID { CKRecord.ID(recordName: "car", zoneID: zoneID) }

    private func setRole(_ r: Role, owner: String? = nil) {
        role = r
        defaults.set(r.rawValue, forKey: "share.role")
        if let owner { defaults.set(owner, forKey: "share.owner") }
    }

    // MARK: starting a share (the owner)

    /// Makes the zone, writes the current car into it and returns the zone-wide share to send.
    func prepareShare(current: ParkedCar?, stamp: Date) async throws -> CKShare {
        let zone = CKRecordZone(zoneName: Self.zoneName)
        _ = try await container.privateCloudDatabase.modifyRecordZones(saving: [zone], deleting: [])
        if role != .owner { setRole(.owner) }
        try await push(current, stamp: stamp)
        try await subscribe()
        let shareID = CKRecord.ID(recordName: CKRecordNameZoneWideShare, zoneID: zone.zoneID)
        if let existing = try? await container.privateCloudDatabase.record(for: shareID) as? CKShare {
            return existing
        }
        let share = CKShare(recordZoneID: zone.zoneID)
        share[CKShare.SystemFieldKey.title] = "Our car in Sweep"
        share.publicPermission = .none
        let result = try await container.privateCloudDatabase.modifyRecords(saving: [share], deleting: [])
        if case .success(let rec) = result.saveResults[shareID], let s = rec as? CKShare { return s }
        return share
    }

    func refreshParticipants() async {
        guard Self.available, role != .none else { others = []; return }
        let shareID = CKRecord.ID(recordName: CKRecordNameZoneWideShare, zoneID: zoneID)
        guard let share = try? await db.record(for: shareID) as? CKShare else { return }
        others = share.participants
            .filter { $0 != share.currentUserParticipant && $0.acceptanceStatus == .accepted }
            .compactMap { p in p.userIdentity.nameComponents.map { PersonNameComponentsFormatter.localizedString(from: $0, style: .default) } ?? p.userIdentity.lookupInfo?.emailAddress }
    }

    // MARK: joining (the person invited)

    func accept(_ metadata: CKShare.Metadata) async {
        do {
            _ = try await container.accept(metadata)
            setRole(.participant, owner: metadata.share.recordID.zoneID.ownerName)
            try? await subscribe()
            await pullAndApply()
            await refreshParticipants()
        } catch {
            problem = "Couldn't join the shared car: \(error.localizedDescription)"
        }
    }

    /// Stop sharing (owner) or leave the share (participant). The car stays on this phone.
    func stop() async {
        guard role != .none else { return }
        do {
            // owner: deleting the zone ends the share for everyone; participant: deleting it from the
            // shared database just leaves
            _ = try await db.modifyRecordZones(saving: [], deleting: [zoneID])
        } catch { }
        setRole(.none)
        others = []
    }

    // MARK: the car record

    /// Writes this phone's car (nil = moved) with the time it changed.
    func push(_ car: ParkedCar?, stamp: Date) async throws {
        guard Self.available, role != .none else { return }
        let rec: CKRecord
        if let existing = try? await db.record(for: recordID) {
            if let theirs = existing["changedAt"] as? Date, theirs > stamp { return }   // someone else changed it later
            rec = existing
        } else {
            rec = CKRecord(recordType: Self.recordType, recordID: recordID)
        }
        rec["payload"] = car.flatMap { try? JSONEncoder().encode($0) } ?? Data()
        rec["changedAt"] = stamp
        _ = try await db.modifyRecords(saving: [rec], deleting: [], savePolicy: .changedKeys)
    }

    /// Fetches the shared car and hands it to the store if it's newer than what this phone has.
    func pullAndApply() async {
        guard Self.available, role != .none else { return }
        do {
            let rec = try await db.record(for: recordID)
            guard let stamp = rec["changedAt"] as? Date else { return }
            let data = rec["payload"] as? Data ?? Data()
            let car = data.isEmpty ? nil : try? JSONDecoder().decode(ParkedCar.self, from: data)
            Store.shared.applyShared(car, stamp: stamp)
        } catch let e as CKError where e.code == .zoneNotFound || e.code == .userDeletedZone {
            setRole(.none)            // the owner stopped sharing
            others = []
        } catch let e as CKError where e.code == .unknownItem {
            // nothing written yet
        } catch {
            // offline or iCloud signed out: try again next time
        }
    }

    // MARK: silent pushes

    private func subscribe() async throws {
        let id = role == .participant ? "sweep.shared" : "sweep.private"
        if defaults.bool(forKey: "share.subscribed.\(id)") { return }
        let sub = CKDatabaseSubscription(subscriptionID: id)
        let info = CKSubscription.NotificationInfo()
        info.shouldSendContentAvailable = true
        sub.notificationInfo = info
        _ = try await db.modifySubscriptions(saving: [sub], deleting: [])
        defaults.set(true, forKey: "share.subscribed.\(id)")
    }
}

/// The system sheet for inviting people to the shared car and managing who's on it.
struct ShareSheet: UIViewControllerRepresentable {
    let share: CKShare
    func makeUIViewController(context: Context) -> UICloudSharingController {
        let c = UICloudSharingController(share: share, container: CKContainer(identifier: CarShare.containerID))
        c.availablePermissions = [.allowReadWrite, .allowPrivate]
        c.delegate = context.coordinator
        return c
    }
    func updateUIViewController(_ c: UICloudSharingController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator() }
    final class Coordinator: NSObject, UICloudSharingControllerDelegate {
        func itemTitle(for csc: UICloudSharingController) -> String? { "Our car in Sweep" }
        func cloudSharingController(_ csc: UICloudSharingController, failedToSaveShareWithError error: Error) {}
        func cloudSharingControllerDidStopSharing(_ csc: UICloudSharingController) {
            Task { @MainActor in await CarShare.shared.stop() }
        }
    }
}

/// "Shared with <name>" or a button to start sharing; shown on the main screens.
struct ShareRow: View {
    @EnvironmentObject var store: Store
    @ObservedObject var share = CarShare.shared
    @State private var sheetShare: CKShare?
    @State private var working = false

    var body: some View {
        if CarShare.available {
            VStack(alignment: .leading, spacing: 6) {
                switch share.role {
                case .none:
                    Button {
                        Task { await start() }
                    } label: {
                        HStack(spacing: 10) {
                            if working { ProgressView().tint(Theme.fg) }
                            Text(working ? "Setting up…" : "Share the car with someone")
                        }
                    }
                    .buttonStyle(SquareButton(fill: nil))
                    .disabled(working)
                case .owner, .participant:
                    HStack(alignment: .firstTextBaseline) {
                        Text(statusText).font(Theme.body(16, 600)).foregroundStyle(Theme.mint)
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer()
                        if share.role == .owner {
                            Button("Manage") { Task { await start() } }.font(Theme.body(16, 700)).foregroundStyle(Theme.sun)
                        }
                    }
                }
                if let p = share.problem {
                    Text(p).font(Theme.body(15, 600)).foregroundStyle(Theme.vermilion).fixedSize(horizontal: false, vertical: true)
                }
            }
            .sheet(item: $sheetShare) { s in ShareSheet(share: s).ignoresSafeArea() }
            .task { await share.refreshParticipants() }
        }
    }

    var statusText: String {
        let names = share.others
        if share.role == .participant {
            return names.isEmpty ? "Shared car: changes here show up on the other phone." : "Shared with \(names.joined(separator: " and ")). Changes show up on both phones."
        }
        return names.isEmpty ? "Sharing is set up. Waiting for the other person to accept the invitation." : "Shared with \(names.joined(separator: " and ")). Changes show up on both phones."
    }

    func start() async {
        working = true
        defer { working = false }
        share.problem = nil
        do {
            sheetShare = try await share.prepareShare(current: store.parked, stamp: store.changedAt == .distantPast ? Date() : store.changedAt)
        } catch {
            share.problem = "Couldn't set up sharing: \(error.localizedDescription). Check that iCloud is on in Settings."
        }
    }
}

extension CKShare: @retroactive Identifiable {
    public var id: CKRecord.ID { recordID }
}
