import CoreLocation

/// Gets one good location fix: keeps listening for up to `timeout` seconds and returns the most
/// accurate reading, or stops early once a reading is within `goodEnough` meters.
@MainActor
final class Locator: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var status: CLAuthorizationStatus
    @Published var preciseOff = false
    private let manager = CLLocationManager()
    private var best: CLLocation?
    private var goodEnough: Double = 8
    private var generation = 0
    private var waiter: CheckedContinuation<CLLocation?, Never>?
    private var authWaiter: CheckedContinuation<Void, Never>?

    override init() {
        status = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.activityType = .otherNavigation
    }

    func fix(timeout: TimeInterval = 8, goodEnough: Double = 8) async -> CLLocation? {
        if manager.authorizationStatus == .notDetermined {
            await withCheckedContinuation { c in authWaiter = c; manager.requestWhenInUseAuthorization() }
        }
        guard [.authorizedWhenInUse, .authorizedAlways].contains(manager.authorizationStatus) else { return nil }
        preciseOff = manager.accuracyAuthorization == .reducedAccuracy
        best = nil
        self.goodEnough = goodEnough
        manager.startUpdatingLocation()
        generation += 1
        let mine = generation
        let result: CLLocation? = await withCheckedContinuation { c in
            waiter = c
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(timeout * 1e9))
                if self.generation == mine { self.finish() }
            }
        }
        return result
    }

    private func finish() {
        manager.stopUpdatingLocation()
        waiter?.resume(returning: best)
        waiter = nil
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        Task { @MainActor in
            for l in locs where l.horizontalAccuracy >= 0 && abs(l.timestamp.timeIntervalSinceNow) < 15 {
                if best == nil || l.horizontalAccuracy < best!.horizontalAccuracy { best = l }
            }
            if let b = best, b.horizontalAccuracy <= goodEnough, waiter != nil { finish() }
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {}

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        Task { @MainActor in
            status = m.authorizationStatus
            if m.authorizationStatus != .notDetermined { authWaiter?.resume(); authWaiter = nil }
        }
    }
}
