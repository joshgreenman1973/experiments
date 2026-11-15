import SwiftUI
import UserNotifications

@main
struct SweepApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var store = Store.shared
    @Environment(\.scenePhase) private var phase

    init() { Theme.registerFonts() }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .preferredColorScheme(.dark)
                .onAppear { store.loadData() }
                .task {
                    store.reschedule()
                    await store.checkNotificationStatus()
                    await store.refreshHolidays()
                }
                .onChange(of: phase) { _, now in
                    guard now == .active else { return }
                    store.reschedule()   // the next windows roll forward as days pass
                    Task { await store.checkNotificationStatus(); await store.refreshHolidays() }
                }
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ app: UIApplication, didFinishLaunchingWithOptions opts: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        let c = UNUserNotificationCenter.current()
        c.delegate = self
        let moved = UNNotificationAction(identifier: Store.movedAction, title: "I moved the car", options: [])
        c.setNotificationCategories([UNNotificationCategory(identifier: Store.category, actions: [moved], intentIdentifiers: [])])
        return true
    }

    func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    func userNotificationCenter(_ c: UNUserNotificationCenter, didReceive r: UNNotificationResponse) async {
        if r.actionIdentifier == Store.movedAction {
            await MainActor.run { Store.shared.moved() }
        }
    }
}
