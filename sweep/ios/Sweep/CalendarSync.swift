import EventKit
import Foundation

/// Puts the parked car's upcoming cleaning windows on the phone's default calendar, and takes them
/// off again when the car moves. Sweep only touches events it created (their ids are kept here).
/// The events carry no alarms: Sweep's own notifications do the reminding.
@MainActor
final class CalendarSync {
    static let shared = CalendarSync()
    private let store = EKEventStore()
    private let defaults = UserDefaults.standard
    private let idsKey = "calendar.eventIds", sigKey = "calendar.signature"

    enum Access { case allowed, denied, notAsked }

    var access: Access {
        switch EKEventStore.authorizationStatus(for: .event) {
        case .fullAccess, .authorized: return .allowed
        case .notDetermined: return .notAsked
        default: return .denied
        }
    }

    /// Make the calendar match `windows` for `spot` (nil spot or empty windows clears Sweep's events).
    /// Asks for calendar access only when `ask` is true, so opening the app never pops a prompt.
    func sync(spot: Spot?, windows: [Window], ask: Bool) async {
        if access == .notAsked {
            guard ask, spot != nil, !windows.isEmpty else { return }
            let ok = (try? await store.requestFullAccessToEvents()) ?? false
            if !ok { return }
        }
        guard access == .allowed else { return }

        let want = windows.filter { !$0.suspended }
        let sig = spot.map { s in ([s.title] + want.map { "\(Int($0.start.timeIntervalSince1970))-\(Int($0.end.timeIntervalSince1970))" }).joined(separator: "|") } ?? ""
        if sig == defaults.string(forKey: sigKey) { return }   // already up to date

        removeOurs()
        guard let s = spot, !want.isEmpty, let cal = store.defaultCalendarForNewEvents else {
            defaults.set(sig, forKey: sigKey)
            return
        }
        var ids: [String] = []
        for w in want {
            let e = EKEvent(eventStore: store)
            e.calendar = cal
            e.title = "Street cleaning: move the car"
            e.location = "\(s.streetName), \(s.sideName) side"
            e.notes = "No parking \(Clock.text(minutes(w.start)))–\(Clock.text(minutes(w.end))) on \(s.streetName), \(s.sideName) side, \(s.between). Added by Sweep, which removes it when you mark the car moved."
            e.timeZone = NY.zone
            e.startDate = w.start
            e.endDate = w.end
            e.availability = .free
            do {
                try store.save(e, span: .thisEvent, commit: false)
                if let id = e.eventIdentifier { ids.append(id) }
            } catch { continue }
        }
        try? store.commit()
        defaults.set(ids, forKey: idsKey)
        defaults.set(sig, forKey: sigKey)
    }

    private func removeOurs() {
        let ids = defaults.stringArray(forKey: idsKey) ?? []
        for id in ids {
            if let e = store.event(withIdentifier: id) { try? store.remove(e, span: .thisEvent, commit: false) }
        }
        try? store.commit()
        defaults.removeObject(forKey: idsKey)
    }

    private func minutes(_ d: Date) -> Int {
        NY.calendar.component(.hour, from: d) * 60 + NY.calendar.component(.minute, from: d)
    }
}
