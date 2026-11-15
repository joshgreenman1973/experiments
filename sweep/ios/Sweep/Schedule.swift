import Foundation

enum NY {
    static let zone = TimeZone(identifier: "America/New_York")!
    static var calendar: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = zone
        c.locale = Locale(identifier: "en_US_POSIX")
        return c
    }()
    static func dayKey(_ d: Date) -> String {
        let c = calendar.dateComponents([.year, .month, .day], from: d)
        return String(format: "%04d-%02d-%02d", c.year!, c.month!, c.day!)
    }
    static func format(_ d: Date, _ pattern: String) -> String {
        let f = DateFormatter()
        f.timeZone = zone
        f.locale = Locale(identifier: "en_US")
        f.dateFormat = pattern
        return f.string(from: d)
    }
    /// "Thu 11:30 am"
    static func dayTime(_ d: Date) -> String {
        let m = calendar.component(.hour, from: d) * 60 + calendar.component(.minute, from: d)
        return "\(format(d, "EEE")) \(Clock.text(m))"
    }
}

/// One street-cleaning window on a particular date.
struct Window: Hashable {
    let start: Date
    let end: Date
    let suspended: Bool
}

enum Schedule {
    /// Cleaning windows for `rule` that end after `after`, over the next `days` days.
    static func windows(_ rule: Rule, after: Date, days: Int = 28, suspended: (Date) -> Bool) -> [Window] {
        let cal = NY.calendar
        let today = cal.startOfDay(for: after)
        var out: [Window] = []
        for k in 0...days {
            guard let day = cal.date(byAdding: .day, value: k, to: today) else { continue }
            guard rule.applies(weekday: cal.component(.weekday, from: day)) else { continue }
            let s = at(day, rule.start), e = at(day, rule.end)
            if e > after { out.append(Window(start: s, end: e, suspended: suspended(day))) }
        }
        return out
    }

    /// The wall-clock time `minutes` after midnight on `day`, in New York (handles DST days).
    static func at(_ day: Date, _ minutes: Int) -> Date {
        let cal = NY.calendar
        if minutes >= 1440 { return cal.date(byAdding: .day, value: 1, to: day)! }
        var c = cal.dateComponents([.year, .month, .day], from: day)
        c.hour = minutes / 60; c.minute = minutes % 60
        return cal.date(from: c)!
    }

    struct Alert: Hashable {
        let fire: Date
        let window: Window
        let kind: Kind
        enum Kind: String { case evening, before, suspended }
    }

    /// The notifications to schedule for a parked car.
    static func alerts(for windows: [Window], now: Date, settings: ReminderSettings, max: Int = 40) -> [Alert] {
        var out: [Alert] = []
        let cal = NY.calendar
        for w in windows {
            let dayBefore = cal.date(byAdding: .day, value: -1, to: cal.startOfDay(for: w.start))!
            let evening = at(dayBefore, settings.eveningMinutes)
            if w.suspended {
                if settings.eveningOn && settings.tellSuspended && evening > now && evening < w.start {
                    out.append(Alert(fire: evening, window: w, kind: .suspended))
                }
                continue
            }
            if settings.eveningOn && evening > now && evening < w.start {
                out.append(Alert(fire: evening, window: w, kind: .evening))
            }
            let before = w.start.addingTimeInterval(TimeInterval(-settings.beforeMinutes * 60))
            if settings.beforeOn && before > now && !(settings.eveningOn && abs(before.timeIntervalSince(evening)) < 30 * 60) {
                out.append(Alert(fire: before, window: w, kind: .before))
            }
        }
        return Array(out.sorted { $0.fire < $1.fire }.prefix(max))
    }
}

struct ReminderSettings: Codable, Equatable {
    var eveningOn = true
    var eveningMinutes = 20 * 60      // 8 pm the day before
    var beforeOn = true
    var beforeMinutes = 60            // an hour before cleaning starts
    var tellSuspended = true          // say so the evening before a suspended day
}
