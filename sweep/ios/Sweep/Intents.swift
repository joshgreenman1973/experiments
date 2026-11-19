import AppIntents
import CoreLocation
import Foundation

/// "I parked with Sweep": finds the nearest block side with a broom sign and parks the car there,
/// hands-free (Siri on the phone or in CarPlay). The side can be corrected in the app afterward.
struct ParkHereIntent: AppIntent {
    static let title: LocalizedStringResource = "I parked"
    static let description = IntentDescription("Marks the car parked on the nearest block side and sets the street-cleaning reminders.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let store = Store.shared
        let loc = await Locator().fix(timeout: 10, goodEnough: 10)
        guard let loc else {
            return .result(dialog: "Sweep couldn’t get your location. Open Sweep and tap I parked here.")
        }
        let data: SignData
        if let d = store.data { data = d } else {
            guard let d = try? SignData.bundled() else { return .result(dialog: "Sweep couldn’t read its sign data. Open the app and try again.") }
            data = d; store.data = d
        }
        let here = Coord(loc.coordinate.latitude, loc.coordinate.longitude)
        guard let spot = data.candidates(near: here, radius: 60).first(where: { $0.primary != nil }) else {
            return .result(dialog: "There’s no street-cleaning sign on record near you. Open Sweep to check.")
        }
        store.park(spot, at: here)
        let line = CarSnapshot.load().map { MoveText.line($0, now: Date()) }
        let move = line.map { "\($0.headline)." } ?? ""
        return .result(dialog: "Parked on \(spot.streetName), \(spot.sideName) side. \(move) If you’re across the street, open Sweep to switch sides.")
    }
}

/// "When do I move the car, Sweep?"
struct WhenToMoveIntent: AppIntent {
    static let title: LocalizedStringResource = "When do I move the car?"
    static let description = IntentDescription("Says when street cleaning next comes to where the car is parked.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        let store = Store.shared
        guard store.parked != nil else { return .result(dialog: "Sweep doesn’t have the car parked anywhere. Say: I parked with Sweep.") }
        store.reschedule()
        guard let s = CarSnapshot.load() else { return .result(dialog: "Open Sweep to update the car.") }
        return .result(dialog: "\(MoveText.spoken(s, now: Date()))")
    }
}

/// "I moved the car with Sweep": clears the car and its reminders.
struct MovedCarIntent: AppIntent {
    static let title: LocalizedStringResource = "I moved the car"
    static let description = IntentDescription("Clears the parked car and its street-cleaning reminders.")
    static let openAppWhenRun = false

    @MainActor
    func perform() async throws -> some IntentResult & ProvidesDialog {
        guard Store.shared.parked != nil else { return .result(dialog: "There’s no car parked in Sweep.") }
        Store.shared.moved()
        return .result(dialog: "Got it. The reminders are off until you park again.")
    }
}

struct SweepShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: ParkHereIntent(), phrases: [
            "I parked with \(.applicationName)",
            "I parked in \(.applicationName)",
            "Park with \(.applicationName)",
            "\(.applicationName) I parked",
        ], shortTitle: "I parked", systemImageName: "car.fill")
        AppShortcut(intent: WhenToMoveIntent(), phrases: [
            "When do I move the car with \(.applicationName)",
            "When do I have to move the car in \(.applicationName)",
            "Ask \(.applicationName) when to move the car",
            "\(.applicationName) when do I move",
        ], shortTitle: "When to move", systemImageName: "clock")
        AppShortcut(intent: MovedCarIntent(), phrases: [
            "I moved the car with \(.applicationName)",
            "I moved the car in \(.applicationName)",
            "\(.applicationName) I moved the car",
        ], shortTitle: "I moved the car", systemImageName: "car.side.arrowtriangle.up.fill")
    }
}
