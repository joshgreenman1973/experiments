import Foundation

/// Alternate-side parking suspension days, from NYC DOT's published calendar files
/// (https://www.nyc.gov/html/dot/downloads/misc/<year>-alternate-side.ics).
/// The 2026 file ships with the app; the app re-downloads the current and next year when it opens.
/// These are the scheduled holiday suspensions only. Snow and emergency suspensions are not in them.
struct HolidayCalendar: Codable, Equatable {
    var days: Set<String> = []          // "2026-11-26"
    var years: Set<Int> = []            // years we have a DOT file for
    var checked: Date? = nil            // last successful download

    func isSuspended(_ d: Date) -> Bool { days.contains(NY.dayKey(d)) }
    func covers(_ d: Date) -> Bool { years.contains(NY.calendar.component(.year, from: d)) }

    /// Parse a DOT .ics file into suspension days. Returns nil if it doesn't look like one.
    static func parse(_ text: String) -> Set<String>? {
        guard text.contains("BEGIN:VCALENDAR") else { return nil }
        var out = Set<String>()
        let lines = text.replacingOccurrences(of: "\r\n ", with: "").components(separatedBy: .newlines)
        var inEvent = false, start: String?, end: String?, startTimed = false, endTimed = false
        func ymd(_ v: String) -> String? {
            let digits = v.prefix(8)
            guard digits.count == 8, Int(digits) != nil else { return nil }
            return "\(digits.prefix(4))-\(digits.dropFirst(4).prefix(2))-\(digits.suffix(2))"
        }
        for raw in lines {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line == "BEGIN:VEVENT" { inEvent = true; start = nil; end = nil; continue }
            if line == "END:VEVENT" {
                inEvent = false
                guard let s = start else { continue }
                var e = end ?? s
                // Date-only DTEND is exclusive. A timed DTEND at midnight is too.
                if !endTimed || e.hasSuffix("T000000") { e = String(e.prefix(8)) } else { e = nextDay(String(e.prefix(8))) }
                _ = startTimed
                var cur = String(s.prefix(8))
                var guardCount = 0
                repeat {
                    if let k = ymd(cur) { out.insert(k) }
                    cur = nextDay(cur)
                    guardCount += 1
                } while cur < e && guardCount < 31
                continue
            }
            guard inEvent, let colon = line.firstIndex(of: ":") else { continue }
            let key = line[..<colon], value = String(line[line.index(after: colon)...])
            if key.hasPrefix("DTSTART") { start = value; startTimed = value.contains("T") }
            if key.hasPrefix("DTEND") { end = value; endTimed = value.contains("T") }
        }
        return out.isEmpty ? nil : out
    }

    private static func nextDay(_ ymd8: String) -> String {
        var c = DateComponents()
        c.year = Int(ymd8.prefix(4)); c.month = Int(ymd8.dropFirst(4).prefix(2)); c.day = Int(ymd8.suffix(2))
        guard let d = NY.calendar.date(from: c), let n = NY.calendar.date(byAdding: .day, value: 1, to: d) else { return "99999999" }
        let k = NY.calendar.dateComponents([.year, .month, .day], from: n)
        return String(format: "%04d%02d%02d", k.year!, k.month!, k.day!)
    }

    mutating func add(year: Int, days new: Set<String>) {
        days = days.filter { !$0.hasPrefix("\(year)-") }.union(new.filter { $0.hasPrefix("\(year)-") })
        years.insert(year)
    }

    static func url(_ year: Int) -> URL { URL(string: "https://www.nyc.gov/html/dot/downloads/misc/\(year)-alternate-side.ics")! }
}
