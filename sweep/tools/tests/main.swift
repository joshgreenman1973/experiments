// Logic checks that run on the Mac: swift-compile the app's model files with this file.
// ./tools/test_logic.sh
import Foundation
var fails = 0
func check(_ ok: Bool, _ msg: String) { print(ok ? "ok   " : "FAIL ", msg); if !ok { fails += 1 } }
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let t0 = Date()
let data = try SignData(json: Data(contentsOf: root.appendingPathComponent("faces.json")), points: Data(contentsOf: root.appendingPathComponent("points.bin")))
print(String(format: "loaded %d faces in %.2fs", data.faces.count, Date().timeIntervalSince(t0)))

// Union Street, south side, between 6th and 7th Avenue (Thu 11:30-1 per the original page)
let fi = data.faces.firstIndex { data.names[$0.street] == "UNION STREET" && data.names[$0.borough] == "BROOKLYN" && Set([data.names[$0.from], data.names[$0.to]]) == ["6 AVENUE", "7 AVENUE"] && $0.side == "S" }!
let line = data.line(data.faces[fi])
let mid = line[line.count / 2]
// a car 3 m north of the south-side signs, i.e. parked at the south curb
let car = Coord(mid.lat + 3 / 110_574, mid.lon)
let t1 = Date()
let c = data.candidates(near: car)
print(String(format: "search %.1f ms", Date().timeIntervalSince(t1) * 1000))
for s in c { print("   ", s.title, s.between, s.rules.map(\.text), String(format: "%.0f m", s.distance)) }
check(c.first?.street == "UNION STREET" && c.first?.side == "S", "nearest is Union St south side")
check(c.first?.primary?.text == "Thu 11:30 am–1 pm", "rule reads Thu 11:30 am–1 pm (got \(c.first?.primary?.text ?? "-"))")
check(c.count > 1 && c[1].side == "N" && c[1].primary?.text == "Mon 11:30 am–1 pm", "second is the north side, Mon")
check(Names.pretty("EAST  182 STREET") == "East 182nd Street", "pretty East 182nd Street")
check(Names.pretty("ST JOHNS PLACE") == "St. Johns Place", "pretty St. Johns Place")
check(Names.pretty("6 AVENUE") == "6th Avenue", "pretty 6th Avenue")

// Holidays
let ics = try String(contentsOf: root.appendingPathComponent("asp-2026.ics"), encoding: .utf8)
let days = HolidayCalendar.parse(ics) ?? []
print("   \(days.count) suspension days in 2026:", days.sorted().joined(separator: " "))
for d in ["2026-11-26", "2026-11-01", "2026-12-25", "2026-04-08", "2026-04-09", "2026-01-01"] { check(days.contains(d), "suspended \(d)") }
for d in ["2026-11-27", "2026-11-02", "2026-04-11", "2026-12-26"] { check(!days.contains(d), "not suspended \(d)") }
var hc = HolidayCalendar(); hc.add(year: 2026, days: days)

// Schedule from Fri Nov 13 2026, 3 pm New York
var comp = DateComponents(); comp.year = 2026; comp.month = 11; comp.day = 13; comp.hour = 15
let now = NY.calendar.date(from: comp)!
let w = Schedule.windows(c[0].primary!, after: now, suspended: hc.isSuspended)
for x in w.prefix(4) { print("   ", NY.format(x.start, "EEE MMM d h:mm a"), "–", NY.format(x.end, "h:mm a"), x.suspended ? "SUSPENDED" : "") }
check(NY.format(w[0].start, "yyyy-MM-dd HH:mm") == "2026-11-19 11:30", "next window Thu Nov 19 11:30")
check(w[1].suspended && NY.dayKey(w[1].start) == "2026-11-26", "Thanksgiving window suspended")
let a = Schedule.alerts(for: w, now: now, settings: ReminderSettings())
for x in a.prefix(5) { print("   alert", x.kind.rawValue, NY.format(x.fire, "EEE MMM d h:mm a")) }
check(a.count >= 3 && NY.format(a[0].fire, "MMM d HH:mm") == "Nov 18 20:00" && a[0].kind == .evening, "evening-before alert Wed 8 pm")
check(NY.format(a[1].fire, "MMM d HH:mm") == "Nov 19 10:30" && a[1].kind == .before, "hour-before alert Thu 10:30")
check(a[2].kind == .suspended && NY.format(a[2].fire, "MMM d HH:mm") == "Nov 25 20:00", "suspended note Wed Nov 25 8 pm")
// night rule: Mon & Thu midnight-3am fires Sun 8 pm and Sun 11 pm
let night = Rule(days: 0b0010010, start: 0, end: 180, night: true)
let wn = Schedule.windows(night, after: now, suspended: { _ in false })
let an = Schedule.alerts(for: wn, now: now, settings: ReminderSettings())
check(NY.format(wn[0].start, "EEE MMM d HH:mm") == "Mon Nov 16 00:00", "night window starts Mon 00:00")
check(NY.format(an[0].fire, "EEE HH:mm") == "Sun 20:00" && NY.format(an[1].fire, "EEE HH:mm") == "Sun 23:00", "night alerts Sun 8 pm and 11 pm")
// DST: Sunday Mar 8 2026 has no 2:30 am; Mon 8 Mar 2027... just check a Nov 2 window across fall back
check(Clock.text(1440) == "midnight" && Clock.text(720) == "noon" && Clock.text(510) == "8:30 am", "clock text")
print(fails == 0 ? "ALL PASSED" : "\(fails) FAILED")
exit(fails == 0 ? 0 : 1)
