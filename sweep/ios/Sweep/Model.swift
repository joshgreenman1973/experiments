import Foundation
import CoreLocation

/// One posted street-cleaning rule: which days, and the no-parking window on those days.
struct Rule: Hashable, Codable {
    let days: Int      // bit 0 = Sunday ... bit 6 = Saturday
    let start: Int     // minutes after midnight
    let end: Int       // minutes after midnight; 1440 means midnight at the end of the day
    let night: Bool    // posted with the moon-and-stars symbol

    func applies(weekday: Int) -> Bool { days & (1 << (weekday - 1)) != 0 } // Calendar weekday: 1 = Sunday

    var dayText: String {
        if days == 0b1111110 { return "Mon–Sat" }
        if days == 0b0111110 { return "Mon–Fri" }
        let short = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        let list = (0..<7).filter { days & (1 << $0) != 0 }.map { short[$0] }
        if list.count == 2 { return list.joined(separator: " & ") }
        return list.joined(separator: ", ")
    }
    var timeText: String { "\(Clock.text(start))–\(Clock.text(end))" }
    var text: String { "\(dayText) \(timeText)" }
}

enum Clock {
    /// 690 -> "11:30 am", 720 -> "noon", 0 or 1440 -> "midnight"
    static func text(_ minutes: Int) -> String {
        let m = minutes % 1440
        if m == 0 { return "midnight" }
        if m == 720 { return "noon" }
        var h = m / 60
        let mm = m % 60
        let ap = h >= 12 ? "pm" : "am"
        h = h % 12 == 0 ? 12 : h % 12
        return mm == 0 ? "\(h) \(ap)" : "\(h):\(String(format: "%02d", mm)) \(ap)"
    }
}

struct Coord: Hashable, Codable {
    let lat: Double
    let lon: Double
    var cl: CLLocationCoordinate2D { .init(latitude: lat, longitude: lon) }
    init(_ lat: Double, _ lon: Double) { self.lat = lat; self.lon = lon }
    init(_ c: CLLocationCoordinate2D) { lat = c.latitude; lon = c.longitude }
}

/// One side of one block, as the app offers it when you park.
/// `rules` is empty when city records show no street-cleaning sign on that side.
struct Spot: Identifiable, Hashable, Codable {
    let borough: String
    let street: String
    let from: String
    let to: String
    let side: String        // N, S, E, W
    let rules: [Rule]       // most-posted rule first
    let line: [Coord]       // the sign positions along the curb
    var distance: Double    // meters from the car when it was matched
    var id: String { [borough, street, Names.blockKey(from, to), side].joined(separator: "|") }

    var primary: Rule? { rules.first }
    var sideName: String { ["N": "north", "S": "south", "E": "east", "W": "west"][side] ?? side.lowercased() }
    var streetName: String { Names.pretty(street) }
    var between: String { "between \(Names.pretty(from)) and \(Names.pretty(to))" }
    var title: String { "\(streetName), \(sideName) side" }
}

enum Names {
    static func blockKey(_ a: String, _ b: String) -> String { [a, b].sorted().joined(separator: "~") }

    static let ordinalWords: Set<String> = ["STREET", "AVENUE", "PLACE", "ROAD", "DRIVE", "TERRACE", "COURT", "LANE", "WALK", "BOULEVARD"]

    /// "EAST  182 STREET" -> "East 182nd Street", "ST JOHNS PLACE" -> "St. Johns Place"
    static func pretty(_ raw: String) -> String {
        let words = raw.split(separator: " ").map(String.init)
        var out: [String] = []
        for (i, w) in words.enumerated() {
            if let n = Int(w) {
                let next = i + 1 < words.count ? words[i + 1] : ""
                out.append(ordinalWords.contains(next) ? ordinal(n) : w)
            } else if w == "ST" && i == 0 && words.count > 1 {
                out.append("St.")
            } else if w.count <= 2 && ["N", "S", "E", "W"].contains(w) {
                out.append(w)
            } else {
                out.append(w.prefix(1) + w.dropFirst().lowercased())
            }
        }
        return out.joined(separator: " ")
    }

    static func ordinal(_ n: Int) -> String {
        let t = n % 100
        if (11...13).contains(t) { return "\(n)th" }
        switch n % 10 { case 1: return "\(n)st"; case 2: return "\(n)nd"; case 3: return "\(n)rd"; default: return "\(n)th" }
    }
}

enum Geo {
    /// Meters between two points, flat-earth approximation (fine at block scale).
    static func meters(_ a: Coord, _ b: Coord) -> Double {
        let k = cos(a.lat * .pi / 180)
        let dx = (b.lon - a.lon) * 111_320 * k, dy = (b.lat - a.lat) * 110_574
        return (dx * dx + dy * dy).squareRoot()
    }

    /// Meters from point p to the polyline through `line`.
    static func distance(_ p: Coord, toLine line: [Coord]) -> Double {
        guard let first = line.first else { return .infinity }
        if line.count == 1 { return meters(p, first) }
        let k = cos(p.lat * .pi / 180)
        func xy(_ c: Coord) -> (Double, Double) { ((c.lon - p.lon) * 111_320 * k, (c.lat - p.lat) * 110_574) }
        var best = Double.infinity
        for i in 1..<line.count {
            let (ax, ay) = xy(line[i - 1]), (bx, by) = xy(line[i])
            let vx = bx - ax, vy = by - ay
            let L = vx * vx + vy * vy
            let t = L > 0 ? max(0, min(1, -(ax * vx + ay * vy) / L)) : 0
            let qx = ax + t * vx, qy = ay + t * vy
            best = min(best, (qx * qx + qy * qy).squareRoot())
        }
        return best
    }
}
