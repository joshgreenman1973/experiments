import SwiftUI
import UserNotifications
import CloudKit

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
                    await CarShare.shared.pullAndApply()
                    store.reschedule()
                    await store.checkNotificationStatus()
                    await store.refreshHolidays()
                }
                .onChange(of: phase) { _, now in
                    guard now == .active else { return }
                    store.reschedule()   // the next windows roll forward as days pass
                    Task {
                        await CarShare.shared.pullAndApply()
                        await store.checkNotificationStatus(); await store.refreshHolidays()
                    }
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
        if CarShare.available { app.registerForRemoteNotifications() }   // silent pushes when the shared car changes
        return true
    }

    /// The other phone changed the car: fetch it so reminders and the calendar follow.
    func application(_ app: UIApplication, didReceiveRemoteNotification info: [AnyHashable: Any]) async -> UIBackgroundFetchResult {
        await CarShare.shared.pullAndApply()
        return .newData
    }

    func application(_ app: UIApplication, configurationForConnecting s: UISceneSession, options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let c = UISceneConfiguration(name: nil, sessionRole: s.role)
        c.delegateClass = SceneDelegate.self
        return c
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

/// Receives the invitation when someone taps a shared-car link.
final class SceneDelegate: NSObject, UIWindowSceneDelegate {
    func scene(_ scene: UIScene, willConnectTo s: UISceneSession, options: UIScene.ConnectionOptions) {
        if let m = options.cloudKitShareMetadata { Task { @MainActor in await CarShare.shared.accept(m) } }
    }
    func windowScene(_ ws: UIWindowScene, userDidAcceptCloudKitShareWith m: CKShare.Metadata) {
        Task { @MainActor in await CarShare.shared.accept(m) }
    }
}
