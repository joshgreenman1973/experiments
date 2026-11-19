import Foundation
#if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
import ActivityKit
#endif

/// What the widget, the live card and Siri need to know about the parked car, written by the app
/// into the shared app group whenever the car or its schedule changes. The widget can't compute
/// cleaning times itself (it has no sign data), so the app hands it the next several weeks of windows.
struct CarSnapshot: Codable, Equatable {
    struct Win: Codable, Equatable, Hashable {
        var start: Date
        var end: Date
        var suspended: Bool
    }
    var street: String        // "Union Street"
    var side: String          // "south"
    var between: String       // "between 6th Avenue and 7th Avenue"
    var hasRule: Bool         // false: no broom sign on record for this side
    var windows: [Win]        // upcoming, oldest first
    var madeAt: Date

    static let group = "group.com.joshgreenman.sweep"
    private static let key = "carSnapshot"

    static func load() -> CarSnapshot? {
        guard let d = UserDefaults(suiteName: group)?.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(CarSnapshot.self, from: d)
    }
    /// nil clears it (the car moved).
    static func save(_ s: CarSnapshot?) {
        let u = UserDefaults(suiteName: group)
        if let s, let d = try? JSONEncoder().encode(s) { u?.set(d, forKey: key) } else { u?.removeObject(forKey: key) }
    }

    /// The first window that hasn't ended and isn't suspended.
    func next(after now: Date) -> Win? { windows.first { $0.end > now && !$0.suspended } }
    /// A suspended window coming up before the next real one (a holiday): worth saying.
    func skipped(after now: Date) -> Win? {
        guard let n = next(after: now) else { return windows.first { $0.end > now && $0.suspended } }
        return windows.first { $0.end > now && $0.suspended && $0.start < n.start }
    }
}

/// How urgent the next move is; the widget and the app color by it.
enum Urgency: String, Codable, Hashable { case now, today, soon, later, none }

/// The words for "when do I have to move the car", shared by the app's widget, live card and Siri.
enum MoveText {
    static let zone = TimeZone(identifier: "America/New_York")!
    static var cal: Calendar = { var c = Calendar(identifier: .gregorian); c.timeZone = zone; return c }()

    static func clock(_ d: Date) -> String {
        let h = cal.component(.hour, from: d), m = cal.component(.minute, from: d)
        if h == 0 && m == 0 { return "midnight" }
        if h == 12 && m == 0 { return "noon" }
        let hh = h % 12 == 0 ? 12 : h % 12
        return m == 0 ? "\(hh) \(h < 12 ? "am" : "pm")" : String(format: "%d:%02d %@", hh, m, h < 12 ? "am" : "pm")
    }
    static func weekday(_ d: Date, short: Bool = false) -> String {
        let f = DateFormatter(); f.timeZone = zone; f.locale = Locale(identifier: "en_US"); f.dateFormat = short ? "EEE" : "EEEE"
        return f.string(from: d)
    }
    /// "today", "tomorrow", "Thursday"
    static func dayWord(_ d: Date, from now: Date) -> String {
        let n = cal.dateComponents([.day], from: cal.startOfDay(for: now), to: cal.startOfDay(for: d)).day ?? 0
        return n == 0 ? "today" : n == 1 ? "tomorrow" : weekday(d)
    }

    struct Line: Hashable {
        var headline: String      // "Move by 11:30 am Thursday"
        var short: String         // "Thu 11:30 am", for tight spaces
        var detail: String?       // "No parking until 1 pm"
        var urgency: Urgency
        var countdownTo: Date?    // for a live timer
    }

    static func line(_ s: CarSnapshot, now: Date) -> Line {
        guard s.hasRule else {
            return Line(headline: "No cleaning on record", short: "No cleaning", detail: "No broom sign for this side in city records.", urgency: .none)
        }
        guard let w = s.next(after: now) else {
            if s.windows.isEmpty || (s.windows.last?.end ?? now) <= now {
                return Line(headline: "Open Sweep to update", short: "Open Sweep", detail: nil, urgency: .none)
            }
            return Line(headline: "No cleaning soon", short: "None soon", detail: nil, urgency: .later)
        }
        if w.start <= now {
            return Line(headline: "Cleaning now: move the car", short: "Now, till \(clock(w.end))", detail: "No parking until \(clock(w.end)).", urgency: .now, countdownTo: w.end)
        }
        let hours = w.start.timeIntervalSince(now) / 3600
        let u: Urgency = hours < 12 ? .today : hours < 48 ? .soon : .later
        let startsMidnight = cal.component(.hour, from: w.start) == 0 && cal.component(.minute, from: w.start) == 0
        let headline: String
        if startsMidnight, let eve = cal.date(byAdding: .day, value: -1, to: w.start), eve >= cal.startOfDay(for: now) {
            let d = dayWord(eve, from: now)
            headline = "Move by midnight " + (d == "today" ? "tonight" : "\(weekday(eve)) night")
        } else {
            headline = "Move by \(clock(w.start)) \(dayWord(w.start, from: now))"
        }
        var detail = "No parking \(weekday(w.start, short: true)) \(clock(w.start))–\(clock(w.end))."
        if let k = s.skipped(after: now) {
            detail = "\(weekday(k.start)) is suspended for a holiday. " + detail
        }
        return Line(headline: headline, short: "\(weekday(w.start, short: true)) \(clock(w.start))", detail: detail, urgency: u, countdownTo: w.start)
    }

    /// One sentence for Siri.
    static func spoken(_ s: CarSnapshot, now: Date) -> String {
        let l = line(s, now: now)
        return "Your car is on \(s.street), \(s.side) side. \(l.headline). \(l.detail ?? "")"
    }
}

#if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
/// The live card on the lock screen and the CarPlay dashboard, shown in the hours before cleaning.
struct SweepActivity: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var start: Date
        var end: Date
    }
    var street: String
    var side: String
}
#endif
