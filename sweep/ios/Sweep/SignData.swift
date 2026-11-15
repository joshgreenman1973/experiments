import Foundation

/// The citywide block-face table built by tools/build_data.py from NYC DOT's sign records.
final class SignData {
    struct Face {
        let borough: Int, street: Int, from: Int, to: Int   // indexes into `names`
        let side: String
        let rules: [Int]                                    // indexes into `rules`
        let pointStart: Int, pointCount: Int
    }

    let pulled: String
    let names: [String]
    let rules: [Rule]
    let faces: [Face]
    private let lat: [Int32], lon: [Int32], pointFace: [Int32]
    private var byBlock: [String: [Int]] = [:]

    init(json: Data, points: Data) throws {
        guard let root = try JSONSerialization.jsonObject(with: json) as? [String: Any],
              let names = root["names"] as? [String],
              let rawRules = root["rules"] as? [[Int]],
              let rawFaces = root["faces"] as? [[Any]] else { throw CocoaError(.fileReadCorruptFile) }
        self.pulled = root["pulled"] as? String ?? ""
        self.names = names
        self.rules = rawRules.map { Rule(days: $0[0], start: $0[1], end: $0[2], night: $0[3] == 1) }
        var faces: [Face] = []
        faces.reserveCapacity(rawFaces.count)
        for f in rawFaces {
            guard let b = f[0] as? Int, let s = f[1] as? Int, let fr = f[2] as? Int, let to = f[3] as? Int,
                  let side = f[4] as? String, let r = f[5] as? [Int], let ps = f[6] as? Int, let pc = f[7] as? Int
            else { throw CocoaError(.fileReadCorruptFile) }
            faces.append(Face(borough: b, street: s, from: fr, to: to, side: side, rules: r, pointStart: ps, pointCount: pc))
        }
        self.faces = faces
        let n = points.count / 8
        var la = [Int32](repeating: 0, count: n), lo = [Int32](repeating: 0, count: n)
        points.withUnsafeBytes { raw in
            for i in 0..<n {
                la[i] = Int32(littleEndian: raw.loadUnaligned(fromByteOffset: i * 8, as: Int32.self))
                lo[i] = Int32(littleEndian: raw.loadUnaligned(fromByteOffset: i * 8 + 4, as: Int32.self))
            }
        }
        var pf = [Int32](repeating: -1, count: n)
        for (i, f) in faces.enumerated() { for p in f.pointStart..<(f.pointStart + f.pointCount) where p < n { pf[p] = Int32(i) } }
        lat = la; lon = lo; pointFace = pf
        for (i, f) in faces.enumerated() { byBlock[blockKey(f), default: []].append(i) }
    }

    static func bundled() throws -> SignData {
        func url(_ name: String, _ ext: String) -> URL? {
            Bundle.main.url(forResource: name, withExtension: ext) ?? Bundle.main.url(forResource: name, withExtension: ext, subdirectory: "Data")
        }
        guard let j = url("faces", "json"), let p = url("points", "bin") else { throw CocoaError(.fileNoSuchFile) }
        return try SignData(json: Data(contentsOf: j), points: Data(contentsOf: p))
    }

    private func blockKey(_ f: Face) -> String {
        [names[f.borough], names[f.street], Names.blockKey(names[f.from], names[f.to])].joined(separator: "|")
    }

    func line(_ f: Face) -> [Coord] {
        (f.pointStart..<(f.pointStart + f.pointCount)).map { Coord(Double(lat[$0]) / 1e6, Double(lon[$0]) / 1e6) }
    }

    func spot(_ i: Int, from p: Coord) -> Spot {
        let f = faces[i], l = line(f)
        return Spot(borough: names[f.borough], street: names[f.street], from: names[f.from], to: names[f.to], side: f.side,
                    rules: f.rules.map { rules[$0] }, line: l, distance: Geo.distance(p, toLine: l))
    }

    /// Faces with at least one sign inside the box, or nil if there are more than `limit`
    /// (the map asks the user to zoom in rather than draw thousands of lines).
    func faces(lat: ClosedRange<Double>, lon: ClosedRange<Double>, limit: Int) -> [Int]? {
        let la0 = Int32(lat.lowerBound * 1e6), la1 = Int32(lat.upperBound * 1e6)
        let lo0 = Int32(lon.lowerBound * 1e6), lo1 = Int32(lon.upperBound * 1e6)
        var seen = Set<Int32>()
        for i in 0..<self.lat.count where self.lat[i] >= la0 && self.lat[i] <= la1 && self.lon[i] >= lo0 && self.lon[i] <= lo1 {
            let f = pointFace[i]
            if f >= 0 { seen.insert(f); if seen.count > limit { return nil } }
        }
        return seen.map(Int.init)
    }

    /// The same block's other side, if city records have a broom sign on it.
    func oppositeSide(of i: Int) -> Int? {
        let f = faces[i]
        guard let other = Self.opposite[f.side] else { return nil }
        return byBlock[blockKey(f)]?.first { faces[$0].side == other }
    }

    static let opposite = ["N": "S", "S": "N", "E": "W", "W": "E"]

    /// The block faces nearest to `p`, each followed by the other side of the same block.
    /// When city records have no broom sign on the other side, that side is offered with no rules.
    func candidates(near p: Coord, radius: Double = 90, limit: Int = 4) -> [Spot] {
        let dLat = Int32(radius / 110_574 * 1e6), dLon = Int32(radius / (111_320 * cos(p.lat * .pi / 180)) * 1e6)
        let la = Int32((p.lat * 1e6).rounded()), lo = Int32((p.lon * 1e6).rounded())
        var near = Set<Int>()
        for i in 0..<lat.count where abs(lat[i] &- la) <= dLat && abs(lon[i] &- lo) <= dLon {
            if pointFace[i] >= 0 { near.insert(Int(pointFace[i])) }
        }
        let ranked = near.map { spot($0, from: p) }.filter { $0.distance <= radius }.sorted { $0.distance < $1.distance }
        var out: [Spot] = [], seenBlocks = Set<String>()
        for s in ranked {
            let block = [s.borough, s.street, Names.blockKey(s.from, s.to)].joined(separator: "|")
            if seenBlocks.contains(block) { continue }
            seenBlocks.insert(block)
            let sides = (byBlock[block] ?? []).map { spot($0, from: p) }
            out.append(s)
            let other = Self.opposite[s.side] ?? ""
            if let o = sides.first(where: { $0.side == other }) {
                out.append(o)
            } else {
                out.append(Spot(borough: s.borough, street: s.street, from: s.from, to: s.to, side: other,
                                rules: [], line: [], distance: s.distance))
            }
            if seenBlocks.count >= limit { break }
        }
        return out
    }
}
