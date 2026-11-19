import Foundation
import SwiftUI
import UserNotifications

struct ParkedCar: Codable, Equatable {
    var car: Coord
    var spot: Spot
    var parkedAt: Date
}

@MainActor
final class Store: ObservableObject {
    static let shared = Store()

    @Published var data: SignData?
    @Published var loadError: String?
    @Published var parked: ParkedCar? { didSet { save(); reschedule() } }
    @Published var settings = ReminderSettings() { didSet { save(); reschedule() } }
    @Published var holidays = HolidayCalendar() { didSet { save() } }
    @Published var notificationsAllowed: Bool? = nil
    @Published var scheduled: [Schedule.Alert] = []
    /// Put each cleaning window on the phone's calendar. Kept apart from ReminderSettings so older saved settings still load.
    @Published var calendarOn: Bool = UserDefaults.standard.object(forKey: "calendarOn") as? Bool ?? true {
        didSet { defaults.set(calendarOn, forKey: "calendarOn"); syncCalendar(ask: calendarOn) }
    }
    @Published var calendarAccess: CalendarSync.Access = CalendarSync.shared.access
    /// When the parked car last changed on any phone sharing it (newest change wins).
    private(set) var changedAt: Date = UserDefaults.standard.object(forKey: "changedAt") as? Date ?? .distantPast {
        didSet { defaults.set(changedAt, forKey: "changedAt") }
    }

    /// A change that arrived from the other phone: apply it here without sending it back.
    func applyShared(_ car: ParkedCar?, stamp: Date) {
        guard stamp > changedAt else { return }
        changedAt = stamp
        if car != parked { parked = car }
    }

    private func shareChange() {
        let now = Date()
        changedAt = now
        let car = parked
        Task { try? await CarShare.shared.push(car, stamp: now) }
    }

    private let defaults = UserDefaults.standard
    private var loading = false

    init() {
        let dec = JSONDecoder()
        if let d = defaults.data(forKey: "parked"), let p = try? dec.decode(ParkedCar.self, from: d) { parked = p }
        if let d = defaults.data(forKey: "settings"), let s = try? dec.decode(ReminderSettings.self, from: d) { settings = s }
        if let d = defaults.data(forKey: "holidays"), let h = try? dec.decode(HolidayCalendar.self, from: d) { holidays = h }
        if holidays.years.isEmpty, let u = Bundle.main.url(forResource: "asp-2026", withExtension: "ics"),
           let t = try? String(contentsOf: u, encoding: .utf8), let days = HolidayCalendar.parse(t) {
            holidays.add(year: 2026, days: days)
        }
    }

    private func save() {
        let enc = JSONEncoder()
        if let p = parked { defaults.set(try? enc.encode(p), forKey: "parked") } else { defaults.removeObject(forKey: "parked") }
        defaults.set(try? enc.encode(settings), forKey: "settings")
        defaults.set(try? enc.encode(holidays), forKey: "holidays")
    }

    func loadData() {
        guard data == nil, !loading else { return }
        loading = true
        Task.detached(priority: .userInitiated) {
            do {
                let d = try SignData.bundled()
                await MainActor.run { self.data = d; self.loading = false }
            } catch {
                await MainActor.run { self.loadError = "Couldn't read the sign data: \(error.localizedDescription)"; self.loading = false }
            }
        }
    }

    // MARK: cleaning times for the parked car

    func windows(now: Date = Date()) -> [Window] {
        guard let rule = parked?.spot.primary else { return [] }
        let h = holidays
        return Schedule.windows(rule, after: now, suspended: h.isSuspended)
    }

    // MARK: holiday calendar

    func refreshHolidays() async {
        let year = NY.calendar.component(.year, from: Date())
        var cal = holidays
        var changed = false
        for y in [year, year + 1] {
            var req = URLRequest(url: HolidayCalendar.url(y), timeoutInterval: 20)
            req.setValue("Sweep/1.0 (iPhone)", forHTTPHeaderField: "User-Agent")
            guard let (body, resp) = try? await URLSession.shared.data(for: req),
                  (resp as? HTTPURLResponse)?.statusCode == 200,
                  let text = String(data: body, encoding: .utf8), let days = HolidayCalendar.parse(text),
                  days.filter({ $0.hasPrefix("\(y)-") }).count >= 5 else { continue }
            cal.add(year: y, days: days)
            changed = true
        }
        if changed {
            cal.checked = Date()
            holidays = cal
            reschedule()
        }
    }

    // MARK: notifications

    static let category = "sweep.move"
    static let movedAction = "sweep.moved"

    func requestNotifications() async {
        let c = UNUserNotificationCenter.current()
        let ok = (try? await c.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        notificationsAllowed = ok
        reschedule()
    }

    func checkNotificationStatus() async {
        let s = await UNUserNotificationCenter.current().notificationSettings()
        switch s.authorizationStatus {
        case .authorized, .provisional, .ephemeral: notificationsAllowed = true
        case .denied: notificationsAllowed = false
        default: notificationsAllowed = nil
        }
    }

    func syncCalendar(ask: Bool) {
        let spot = calendarOn ? parked?.spot : nil
        let w = (calendarOn && spot?.primary != nil) ? windows() : []
        Task {
            await CalendarSync.shared.sync(spot: spot, windows: w, ask: ask)
            calendarAccess = CalendarSync.shared.access
        }
    }

    func reschedule() {
        syncCalendar(ask: false)
        Glance.update(parked, windows: parked?.spot.primary != nil ? windows() : [])
        let c = UNUserNotificationCenter.current()
        c.removeAllPendingNotificationRequests()
        guard let p = parked, p.spot.primary != nil else { scheduled = []; return }
        let alerts = Schedule.alerts(for: windows(), now: Date(), settings: settings)
        scheduled = alerts
        for a in alerts {
            let content = UNMutableNotificationContent()
            let start = NY.calendar.component(.hour, from: a.window.start) * 60 + NY.calendar.component(.minute, from: a.window.start)
            let end = NY.calendar.component(.hour, from: a.window.end) * 60 + NY.calendar.component(.minute, from: a.window.end)
            let dayName = NY.format(a.window.start, "EEEE")
            let where_ = "\(p.spot.streetName), \(p.spot.sideName) side"
            switch a.kind {
            case .evening:
                let when = start == 0 ? "tonight at midnight" : "tomorrow at \(Clock.text(start))"
                content.title = "Move your car: street cleaning \(when)"
                content.body = "\(where_). No parking \(dayName) \(Clock.text(start))–\(Clock.text(end))."
            case .before:
                content.title = "Street cleaning at \(Clock.text(start))"
                content.body = "Your car is on \(where_). No parking until \(Clock.text(end))."
            case .suspended:
                content.title = "No need to move tomorrow"
                content.body = "Alternate side parking is suspended \(dayName), per the city's holiday calendar. Your car on \(p.spot.streetName) can stay."
            }
            content.sound = .default
            content.categoryIdentifier = Self.category
            if #available(iOS 15.0, *) { content.interruptionLevel = .active }
            let comps = NY.calendar.dateComponents(in: NY.zone, from: a.fire)
            var dc = DateComponents()
            dc.timeZone = NY.zone
            dc.year = comps.year; dc.month = comps.month; dc.day = comps.day; dc.hour = comps.hour; dc.minute = comps.minute
            let trigger = UNCalendarNotificationTrigger(dateMatching: dc, repeats: false)
            let id = "sweep.\(a.kind.rawValue).\(Int(a.fire.timeIntervalSince1970))"
            c.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
        }
    }

    func park(_ spot: Spot, at car: Coord) {
        parked = ParkedCar(car: car, spot: spot, parkedAt: Date())
        shareChange()
        Task {
            await requestNotifications()
            syncCalendar(ask: true)   // after the notification prompt, so the two don't collide
        }
    }

    func moved() { parked = nil; shareChange() }
}
