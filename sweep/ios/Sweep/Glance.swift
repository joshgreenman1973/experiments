import Foundation
import WidgetKit
#if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
import ActivityKit
#endif

/// Keeps everything outside the app in step with the parked car: the shared snapshot the widget
/// reads (home screen, lock screen, CarPlay), and the live card in the hours before cleaning.
@MainActor
enum Glance {
    static func update(_ parked: ParkedCar?, windows: [Window]) {
        let snap = parked.map { p in
            CarSnapshot(street: p.spot.streetName, side: p.spot.sideName, between: p.spot.between,
                        hasRule: p.spot.primary != nil,
                        windows: windows.map { .init(start: $0.start, end: $0.end, suspended: $0.suspended) },
                        madeAt: Date())
        }
        if snap != CarSnapshot.load() || snap == nil {
            CarSnapshot.save(snap)
            WidgetCenter.shared.reloadAllTimelines()
        }
        updateLiveCard(snap)
    }

    /// A live card can run for at most eight hours, and an app can only start one while it's open
    /// (or from a Siri request). So: when the next cleaning starts within eight hours, show it.
    static let liveLead: TimeInterval = 8 * 3600

    static func updateLiveCard(_ snap: CarSnapshot?) {
        #if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        let now = Date()
        let next = snap?.next(after: now)
        let want = next.flatMap { $0.start.timeIntervalSince(now) <= liveLead ? $0 : nil }
        let running = Activity<SweepActivity>.activities
        Task {
            for a in running {
                if let w = want, a.attributes.street == snap?.street, a.attributes.side == snap?.side {
                    if a.content.state.start != w.start || a.content.state.end != w.end {
                        await a.update(ActivityContent(state: .init(start: w.start, end: w.end), staleDate: w.end))
                    }
                } else {
                    await a.end(nil, dismissalPolicy: .immediate)
                }
            }
            guard let w = want, let s = snap,
                  !Activity<SweepActivity>.activities.contains(where: { $0.attributes.street == s.street && $0.attributes.side == s.side })
            else { return }
            _ = try? Activity.request(attributes: SweepActivity(street: s.street, side: s.side),
                                      content: ActivityContent(state: .init(start: w.start, end: w.end), staleDate: w.end))
        }
        #endif
    }
}
