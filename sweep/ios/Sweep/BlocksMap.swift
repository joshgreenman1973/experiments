import SwiftUI
import MapKit

/// A map of every block side in view, colored by when it gets swept.
/// Each line runs along the curb it applies to, through that side's posted signs.
struct BlocksMapView: View {
    enum Mode: String, CaseIterable { case week = "By day", day = "One day", now = "If I park now" }

    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss
    @State private var camera: MapCameraPosition
    @State private var mode: Mode = .week
    @State private var day: Int                      // Calendar weekday, 2 = Monday ... 7 = Saturday
    @State private var shown: [Drawn] = []
    @State private var tooMany = false
    @State private var region: MKCoordinateRegion?
    @State private var selected: Int?
    @State private var tapPoint: Coord?

    static let maxFaces = 1600
    static let offDay = Theme.fg2.opacity(0.5)

    struct Drawn: Identifiable {
        let id: Int                 // face index
        let spot: Spot
        let hoursUntil: Double?     // until the next cleaning that isn't suspended
    }

    init(center: Coord) {
        _camera = State(initialValue: .camera(MapCamera(centerCoordinate: center.cl, distance: 1300)))
        let wd = NY.calendar.component(.weekday, from: Date())
        _day = State(initialValue: wd == 1 ? 2 : wd)
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            MapReader { proxy in
                Map(position: $camera, interactionModes: [.pan, .zoom]) {
                    ForEach(shown) { d in lines(d) }
                    if let s = selectedDrawn {
                        if s.spot.line.count > 1 {
                            MapPolyline(coordinates: s.spot.line.map(\.cl)).stroke(Theme.fg, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                        } else if let p = s.spot.line.first {
                            MapCircle(center: p.cl, radius: 7).foregroundStyle(Theme.fg)
                        }
                    }
                    if let p = store.parked {
                        Annotation("Car", coordinate: p.car.cl, anchor: .center) { CarMark() }.annotationTitles(.hidden)
                    }
                    UserAnnotation()
                }
                .mapStyle(.standard(emphasis: .muted, pointsOfInterest: .excludingAll))
                .mapControls { MapUserLocationButton(); MapCompass() }
                .onMapCameraChange(frequency: .onEnd) { ctx in region = ctx.region; refresh(); debugTap() }
                .onTapGesture { pt in
                    guard let c = proxy.convert(pt, from: .local) else { return }
                    select(near: Coord(c))
                }
                .overlay(alignment: .top) {
                    if tooMany {
                        Text("Zoom in to see the blocks.")
                            .font(Theme.body(16, 700)).foregroundStyle(Theme.bg)
                            .padding(.horizontal, 12).padding(.vertical, 8).background(Theme.sun).padding(.top, 10)
                    }
                }
            }
            footer
        }
        .background(Theme.bg.ignoresSafeArea())
        .foregroundStyle(Theme.fg)
        .onChange(of: mode) { _, _ in refresh() }
        .onChange(of: store.data != nil) { _, _ in refresh() }
    }

    // MARK: header and footer

    var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Street cleaning").font(Theme.display(22, 750, style: .title2))
                Spacer()
                Button("Done") { dismiss() }.font(Theme.body(17, 700)).foregroundStyle(Theme.sun)
            }
            Picker("View", selection: $mode) {
                ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            if mode == .day {
                Picker("Day", selection: $day) {
                    ForEach(2...7, id: \.self) { wd in Text(Self.short[wd - 1]).tag(wd) }
                }
                .pickerStyle(.segmented)
            }
        }
        .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 10)
    }

    @ViewBuilder var footer: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let s = selectedDrawn {
                detail(s)
            } else {
                legend
                Text("Each line sits on the side of the street it applies to. Tap one to see both sides.")
                    .font(Theme.body(14)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.bg)
    }

    static let short = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    var legend: some View {
        let items: [(Color, String)]
        switch mode {
        case .week:
            items = (2...7).map { (Self.dayColor($0), Self.short[$0 - 1]) } + [(Theme.orange, "3+ days a week")]
        case .day:
            items = [(Theme.vermilion, "Cleaned \(Self.short[day - 1])"), (Self.offDay, "Not that day")]
        case .now:
            items = [(Theme.vermilion, "Under a day"), (Theme.orange, "1 to 3 days"), (Theme.mint, "3 days or more")]
        }
        return VStack(alignment: .leading, spacing: 6) {
            FlowRow(items.map { item in
                HStack(spacing: 6) {
                    Rectangle().fill(item.0).frame(width: 18, height: 5)
                    Text(item.1).font(Theme.body(14, 600))
                }
            })
            if mode == .week { Text("Two colors, dashed: cleaned on two days.").font(Theme.body(14)).foregroundStyle(Theme.fg2) }
            if mode == .now { Text("Time until the next cleaning, skipping the city’s holiday suspensions.").font(Theme.body(14)).foregroundStyle(Theme.fg2) }
        }
    }

    func detail(_ d: Drawn) -> some View {
        let other = store.data?.oppositeSide(of: d.id).map { store.data!.spot($0, from: d.spot.line.first ?? Coord(0, 0)) }
        return VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(d.spot.streetName).font(Theme.display(21, 750, style: .headline))
                    Text(d.spot.between).font(Theme.body(15)).foregroundStyle(Theme.fg2)
                }
                Spacer()
                Button { selected = nil } label: { Image(systemName: "xmark").foregroundStyle(Theme.fg2) }
                    .accessibilityLabel("Close")
            }
            sideLine(d.spot, next: d.hoursUntil ?? Self.hoursUntil(d.spot, store: store))
            if let o = other {
                sideLine(o, next: Self.hoursUntil(o, store: store))
            } else if let opp = SignData.opposite[d.spot.side] {
                Text("\(["N": "North", "S": "South", "E": "East", "W": "West"][opp] ?? opp) side: no street-cleaning sign on record")
                    .font(Theme.body(15)).foregroundStyle(Theme.fg2)
            }
            if d.spot.rules.count > 1 {
                Text("Signs on this side disagree; another reads \(d.spot.rules.dropFirst().map(\.text).joined(separator: "; ")).")
                    .font(Theme.body(14)).foregroundStyle(Theme.orange).fixedSize(horizontal: false, vertical: true)
            }
            Button("I parked on the \(d.spot.sideName) side") {
                var s = d.spot
                let car = nearestPoint(on: s.line, to: tapPoint ?? s.line.first!)
                s.distance = 0
                store.park(s, at: car)
                dismiss()
            }
            .buttonStyle(SquareButton())
        }
    }

    func sideLine(_ s: Spot, next: Double?) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Rectangle().fill(color(for: s, hours: next)).frame(width: 14, height: 5).alignmentGuide(.firstTextBaseline) { $0[.bottom] }
            VStack(alignment: .leading, spacing: 1) {
                Text("\(s.sideName.capitalized) side: \(s.primary?.text ?? "no sign")").font(Theme.body(16, 700))
                if let h = next {
                    Text(h <= 0 ? "Cleaning now" : "Next cleaning in \(Status.span(h))").font(Theme.body(14)).foregroundStyle(Theme.fg2)
                }
            }
        }
    }

    // MARK: drawing

    @MapContentBuilder
    func lines(_ d: Drawn) -> some MapContent {
        let s = d.spot
        let main = color(for: s, hours: d.hoursUntil)
        let dimmed = mode == .day && !(s.primary?.applies(weekday: day) ?? false)
        let width: CGFloat = dimmed ? 2.5 : 4.5
        if s.line.count > 1 {
            MapPolyline(coordinates: s.line.map(\.cl)).stroke(main, style: StrokeStyle(lineWidth: width, lineCap: .butt))
            if mode == .week, let second = secondColor(s) {
                MapPolyline(coordinates: s.line.map(\.cl)).stroke(second, style: StrokeStyle(lineWidth: width, lineCap: .butt, dash: [7, 7]))
            }
        } else if let p = s.line.first {
            MapCircle(center: p.cl, radius: dimmed ? 3 : 5).foregroundStyle(main)
        }
    }

    static func dayColor(_ weekday: Int) -> Color {
        switch weekday {
        case 2: return Theme.cobalt
        case 3: return Theme.vermilion
        case 4: return Theme.mint
        case 5: return Color(hex: 0xb79bff)   // lilac
        case 6: return Color(hex: 0xff6fae)   // rose
        case 7: return Color(hex: 0x3cc8d8)   // cyan
        default: return Theme.fg2
        }
    }

    func days(_ s: Spot) -> [Int] {
        guard let r = s.primary else { return [] }
        return (1...7).filter { r.applies(weekday: $0) }
    }

    func color(for s: Spot, hours: Double?) -> Color {
        switch mode {
        case .week:
            let d = days(s)
            if d.count >= 3 { return Theme.orange }
            return d.first.map(Self.dayColor) ?? Theme.fg2
        case .day:
            return (s.primary?.applies(weekday: day) ?? false) ? Theme.vermilion : Self.offDay
        case .now:
            guard let h = hours else { return Theme.mint }
            return h < 24 ? Theme.vermilion : h < 72 ? Theme.orange : Theme.mint
        }
    }

    func secondColor(_ s: Spot) -> Color? {
        let d = days(s)
        return d.count == 2 ? Self.dayColor(d[1]) : nil
    }

    static func hoursUntil(_ s: Spot, store: Store, now: Date = Date()) -> Double? {
        guard let r = s.primary else { return nil }
        let h = store.holidays
        guard let w = Schedule.windows(r, after: now, days: 21, suspended: h.isSuspended).first(where: { !$0.suspended }) else { return nil }
        return max(0, w.start.timeIntervalSince(now) / 3600)
    }

    var selectedDrawn: Drawn? { selected.flatMap { id in shown.first { $0.id == id } } }

    // MARK: data

    func refresh() {
        guard let data = store.data, let r = region else { return }
        let lat = (r.center.latitude - r.span.latitudeDelta / 2)...(r.center.latitude + r.span.latitudeDelta / 2)
        let lon = (r.center.longitude - r.span.longitudeDelta / 2)...(r.center.longitude + r.span.longitudeDelta / 2)
        guard let ids = data.faces(lat: lat, lon: lon, limit: Self.maxFaces) else {
            tooMany = true
            shown = []
            return
        }
        tooMany = false
        let center = Coord(r.center)
        let now = Date()
        shown = ids.map { i in
            let s = data.spot(i, from: center)
            return Drawn(id: i, spot: s, hoursUntil: mode == .now ? Self.hoursUntil(s, store: store, now: now) : nil)
        }
        if let sel = selected, !ids.contains(sel) { selected = nil }
    }

    /// Debug only: `-sweepMapTap lat,lon` selects the block nearest that point once, for testing without a touch screen.
    func debugTap() {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard !Self.debugTapped, let i = args.firstIndex(of: "-sweepMapTap"), i + 1 < args.count else { return }
        let p = args[i + 1].split(separator: ",").compactMap { Double($0) }
        guard p.count == 2, !shown.isEmpty else { return }
        Self.debugTapped = true
        select(near: Coord(p[0], p[1]))
        #endif
    }
    static var debugTapped = false

    func select(near p: Coord) {
        tapPoint = p
        let best = shown.map { ($0.id, Geo.distance(p, toLine: $0.spot.line)) }.min { $0.1 < $1.1 }
        if let b = best, b.1 <= 25 {
            selected = b.0
            if let i = shown.firstIndex(where: { $0.id == b.0 }), shown[i].hoursUntil == nil {
                shown[i] = Drawn(id: b.0, spot: shown[i].spot, hoursUntil: Self.hoursUntil(shown[i].spot, store: store))
            }
        } else {
            selected = nil
        }
    }

    func nearestPoint(on line: [Coord], to p: Coord) -> Coord {
        guard line.count > 1 else { return line.first ?? p }
        var best = line[0], bestD = Double.infinity
        let k = cos(p.lat * .pi / 180)
        for i in 1..<line.count {
            let a = line[i - 1], b = line[i]
            let ax = (a.lon - p.lon) * k, ay = a.lat - p.lat, bx = (b.lon - p.lon) * k, by = b.lat - p.lat
            let vx = bx - ax, vy = by - ay, L = vx * vx + vy * vy
            let t = L > 0 ? max(0, min(1, -(ax * vx + ay * vy) / L)) : 0
            let q = Coord(a.lat + t * (b.lat - a.lat), a.lon + t * (b.lon - a.lon))
            let d = Geo.meters(p, q)
            if d < bestD { bestD = d; best = q }
        }
        return best
    }
}

/// Lays items out left to right, wrapping onto new lines.
struct FlowRow: View {
    let items: [AnyView]
    init<V: View>(_ items: [V]) { self.items = items.map { AnyView($0) } }
    var body: some View {
        FlowLayout(spacing: 14, lineSpacing: 6) { ForEach(items.indices, id: \.self) { items[$0] } }
    }
}

struct FlowLayout: Layout {
    var spacing: CGFloat
    var lineSpacing: CGFloat
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 360
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > width { x = 0; y += line + lineSpacing; line = 0 }
            x += s.width + spacing; line = max(line, s.height)
        }
        return CGSize(width: width, height: y + line)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX { x = bounds.minX; y += line + lineSpacing; line = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing; line = max(line, s.height)
        }
    }
}
