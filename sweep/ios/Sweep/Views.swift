import SwiftUI
import MapKit
import UIKit

struct RootView: View {
    @EnvironmentObject var store: Store
    @State private var showAbout = false

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            if let p = store.parked {
                ParkedView(parked: p, showAbout: $showAbout)
            } else {
                ParkView(showAbout: $showAbout)
            }
        }
        .foregroundStyle(Theme.fg)
        .sheet(isPresented: $showAbout) { AboutView().environmentObject(store) }
    }
}

struct TopLine: View {
    @Binding var showAbout: Bool
    var body: some View {
        HStack {
            Text("Sweep").font(Theme.display(17, 800, style: .headline))
            Text("street cleaning, New York City").font(Theme.body(15)).foregroundStyle(Theme.fg2)
            Spacer()
            Button { showAbout = true } label: {
                Image(systemName: "info.circle").font(.system(size: 20)).foregroundStyle(Theme.fg2)
            }
            .accessibilityLabel("About Sweep")
        }
    }
}

// MARK: - Not parked

struct ParkView: View {
    @EnvironmentObject var store: Store
    @StateObject private var locator = Locator()
    @Binding var showAbout: Bool
    @State private var finding = false
    @State private var pick: PickRequest?
    @State private var problem: String?
    @State private var showMap = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            TopLine(showAbout: $showAbout)
            Spacer(minLength: 10)
            Text("Pin the car where you parked it.")
                .font(Theme.display(34, 700, style: .largeTitle))
                .fixedSize(horizontal: false, vertical: true)
            Text("Sweep matches the spot to its block and side of the street in the city’s street-cleaning signs, then reminds you before the sweeper comes. It knows \(store.data.map { $0.faces.count.formatted() } ?? "56,000") block sides across the five boroughs.")
                .font(Theme.body(18))
                .foregroundStyle(Theme.fg2)
                .fixedSize(horizontal: false, vertical: true)
            if let problem {
                Text(problem).font(Theme.body(16, 600)).foregroundStyle(Theme.vermilion)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
            Button {
                Task { await locate() }
            } label: {
                HStack(spacing: 10) {
                    if finding { ProgressView().tint(Theme.bg) }
                    Text(finding ? "Finding your spot…" : "I parked here")
                }
            }
            .buttonStyle(SquareButton())
            .disabled(finding || store.data == nil)
            Button("Pick the spot on a map instead") {
                pick = PickRequest(start: Coord(40.6602, -73.9690), accuracy: nil, fromGPS: false)
            }
            .buttonStyle(SquareButton(fill: nil))
            .disabled(store.data == nil)
            Button("Map of cleaning days") { showMap = true }
                .buttonStyle(SquareButton(fill: nil))
                .disabled(store.data == nil)
        }
        .padding(16)
        .fullScreenCover(item: $pick) { req in PickView(request: req).environmentObject(store) }
        .fullScreenCover(isPresented: $showMap) { BlocksMapView(center: Self.lastKnown()).environmentObject(store) }
        .onAppear(perform: debugHooks)
    }

    private func locate() async {
        problem = nil
        finding = true
        defer { finding = false }
        guard let loc = await locator.fix() else {
            problem = locator.status == .denied || locator.status == .restricted
                ? "Sweep doesn’t have location access. Turn it on in Settings, or pick the spot on a map."
                : "Couldn’t get a location fix. Try again, or pick the spot on a map."
            return
        }
        let c = Coord(loc.coordinate)
        guard (40.47...40.93).contains(c.lat), (-74.27 ... -73.68).contains(c.lon) else {
            problem = "That location is outside New York City, so there are no street-cleaning signs to match."
            return
        }
        pick = PickRequest(start: c, accuracy: loc.horizontalAccuracy, fromGPS: true, preciseOff: locator.preciseOff)
    }

    /// Where to open the cleaning map: the phone's last known spot if Sweep may use it, else Park Slope.
    static func lastKnown() -> Coord {
        let m = CLLocationManager()
        if [.authorizedWhenInUse, .authorizedAlways].contains(m.authorizationStatus), let l = m.location,
           (40.47...40.93).contains(l.coordinate.latitude), (-74.27 ... -73.68).contains(l.coordinate.longitude) {
            return Coord(l.coordinate)
        }
        return Coord(40.6745, -73.9770)
    }

    private func debugHooks() {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        if let i = args.firstIndex(of: "-sweepPick"), i + 1 < args.count {
            let p = args[i + 1].split(separator: ",").compactMap { Double($0) }
            if p.count == 2 { pick = PickRequest(start: Coord(p[0], p[1]), accuracy: 12, fromGPS: true) }
        }
        if args.contains("-sweepMap") { showMap = true }
        if let i = args.firstIndex(of: "-sweepDemoParked"), i + 1 < args.count {
            let p = args[i + 1].split(separator: ",").compactMap { Double($0) }
            if p.count == 2 {
                Task { @MainActor in
                    while store.data == nil { try? await Task.sleep(nanoseconds: 100_000_000) }
                    let c = Coord(p[0], p[1])
                    if let s = store.data?.candidates(near: c).first { store.park(s, at: c) }
                }
            }
        }
        #endif
    }
}

struct PickRequest: Identifiable {
    let id = UUID()
    let start: Coord
    let accuracy: Double?
    let fromGPS: Bool
    var preciseOff = false
}

// MARK: - Choosing the block face

struct PickView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss
    let request: PickRequest
    @State private var car: Coord
    @State private var spots: [Spot] = []
    @State private var chosen: String?
    @State private var camera: MapCameraPosition

    init(request: PickRequest) {
        self.request = request
        _car = State(initialValue: request.start)
        _camera = State(initialValue: .camera(MapCamera(centerCoordinate: request.start.cl, distance: request.fromGPS ? 420 : 2400)))
    }

    var selected: Spot? { spots.first { $0.id == chosen } ?? spots.first }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Button("Cancel") { dismiss() }.font(Theme.body(17, 600)).foregroundStyle(Theme.fg2)
                Spacer()
                Text(request.fromGPS ? "Which side is the car on?" : "Tap where you parked").font(Theme.display(17, 700, style: .headline))
                Spacer()
                Text("Cancel").font(Theme.body(17, 600)).hidden()
            }
            .padding(16)

            MapReader { proxy in
                Map(position: $camera) {
                    ForEach(spots) { s in
                        if s.line.count > 1 {
                            MapPolyline(coordinates: s.line.map(\.cl))
                                .stroke(s.id == selected?.id ? Theme.sun : Theme.fg2.opacity(0.55), style: StrokeStyle(lineWidth: s.id == selected?.id ? 7 : 4, lineCap: .round))
                        } else if let p = s.line.first {
                            Annotation("", coordinate: p.cl) {
                                Rectangle().fill(s.id == selected?.id ? Theme.sun : Theme.fg2).frame(width: 10, height: 10)
                            }
                        }
                    }
                    Annotation("Car", coordinate: car.cl, anchor: .center) { CarMark() }.annotationTitles(.hidden)
                    if let a = request.accuracy, request.fromGPS, a > 10 {
                        MapCircle(center: request.start.cl, radius: a).foregroundStyle(Theme.sun.opacity(0.10)).stroke(Theme.sun.opacity(0.5), lineWidth: 1)
                    }
                }
                .mapStyle(.standard(emphasis: .muted, pointsOfInterest: .excludingAll))
                .onTapGesture { pt in
                    if let c = proxy.convert(pt, from: .local) { car = Coord(c); match() }
                }
            }
            .frame(maxHeight: .infinity)

            VStack(alignment: .leading, spacing: 10) {
                Text(guidance).font(Theme.body(15)).foregroundStyle(warning ? Theme.orange : Theme.fg2)
                    .fixedSize(horizontal: false, vertical: true)
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(spots) { s in
                            SpotRow(spot: s, selected: s.id == selected?.id).onTapGesture { chosen = s.id }
                        }
                        if spots.isEmpty {
                            Text(request.fromGPS ? "No street-cleaning signs within 90 meters. Tap the map where the car is." : "Tap the map where the car is.")
                                .font(Theme.body(16)).foregroundStyle(Theme.fg2).frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 12)
                        }
                    }
                }
                .frame(maxHeight: 290)
                Button(selected.map { "Save: \($0.title)" } ?? "Save") {
                    if let s = selected { store.park(s, at: car); dismiss() }
                }
                .buttonStyle(SquareButton())
                .disabled(selected == nil)
            }
            .padding(16)
        }
        .background(Theme.bg.ignoresSafeArea())
        .foregroundStyle(Theme.fg)
        .onAppear { if request.fromGPS { match() } }
        .onChange(of: store.data != nil) { _, ready in if ready && request.fromGPS && spots.isEmpty { match() } }
    }

    var warning: Bool { request.preciseOff || (request.accuracy ?? 0) > 20 }
    var guidance: String {
        if !request.fromGPS && spots.isEmpty { return "Zoom in and tap the spot where the car is parked." }
        if request.preciseOff { return "Precise Location is off for Sweep, so the pin could be a block or more away. Tap the map where the car is, or turn Precise Location on in Settings." }
        if let a = request.accuracy, a > 20 { return "Your location is only good to about \(Int(a)) meters here. Check the street and side below, or tap the map to move the yellow pin." }
        return "The yellow pin is your car. Choose the side of the street it’s on; tap the map to move the pin."
    }

    private func match() {
        guard let d = store.data else { return }
        spots = d.candidates(near: car)
        chosen = spots.first?.id
    }
}

struct CarMark: View {
    var body: some View {
        ZStack {
            Rectangle().fill(Theme.sun).frame(width: 22, height: 22)
            Rectangle().stroke(Theme.bg, lineWidth: 3).frame(width: 22, height: 22)
            Image(systemName: "car.fill").font(.system(size: 11, weight: .bold)).foregroundStyle(Theme.bg)
        }
        .accessibilityLabel("Your car")
    }
}

struct SpotRow: View {
    let spot: Spot
    let selected: Bool
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Rectangle().fill(selected ? Theme.sun : Color.clear).frame(width: 5)
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(spot.title).font(Theme.display(19, 700, style: .headline))
                    Spacer()
                    Text("\(Int(spot.distance.rounded())) m").font(Theme.body(14)).foregroundStyle(Theme.fg2).monospacedDigit()
                }
                Text(spot.between).font(Theme.body(15)).foregroundStyle(Theme.fg2)
                Text(spot.primary.map { "No parking \($0.text)" } ?? "No street-cleaning sign on record for this side")
                    .font(Theme.body(16, 600)).foregroundStyle(spot.primary == nil ? Theme.fg2 : Theme.fg)
            }
            .padding(.vertical, 10)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(selected ? Theme.bg2 : Color.clear)
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.line).frame(height: 1) }
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// MARK: - Parked

struct ParkedView: View {
    @EnvironmentObject var store: Store
    let parked: ParkedCar
    @Binding var showAbout: Bool
    @State private var showSettings = false
    @State private var confirmMoved = false
    @State private var showMap = false

    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { ctx in
            content(now: ctx.date)
        }
        .sheet(isPresented: $showSettings) { SettingsView().environmentObject(store) }
        .fullScreenCover(isPresented: $showMap) { BlocksMapView(center: parked.car).environmentObject(store) }
        .confirmationDialog("Clear the parked car?", isPresented: $confirmMoved, titleVisibility: .visible) {
            Button("I moved the car", role: .destructive) { store.moved() }
        } message: { Text("This cancels its reminders.") }
    }

    func content(now: Date) -> some View {
        let spot = parked.spot
        let windows = store.windows(now: now)
        let next = windows.first { !$0.suspended }
        let skipped = windows.prefix { $0.suspended }
        let status = Status(spot: spot, next: next, now: now)

        return ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                TopLine(showAbout: $showAbout)
                VStack(alignment: .leading, spacing: 8) {
                    Text(status.headline)
                        .font(Theme.display(36, 750, style: .largeTitle))
                        .foregroundStyle(status.color)
                        .fixedSize(horizontal: false, vertical: true)
                    if let sub = status.sub {
                        Text(sub).font(Theme.body(18, 600)).foregroundStyle(Theme.fg)
                    }
                }
                ForEach(Array(skipped), id: \.self) { w in
                    Text("\(NY.format(w.start, "EEEE, MMM d"))’s cleaning is suspended for a holiday, per the city’s calendar.")
                        .font(Theme.body(17)).foregroundStyle(Theme.mint).fixedSize(horizontal: false, vertical: true)
                }
                Text("\(spot.title), \(spot.between). Parked \(NY.dayTime(parked.parkedAt)).")
                    .font(Theme.body(17)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)

                CarMap(parked: parked).frame(height: 210)

                if spot.rules.count > 1 {
                    Text("Another sign on this block reads \(spot.rules.dropFirst().map(\.text).joined(separator: "; ")). Sweep goes by the most common sign, \(spot.rules[0].text). Check what’s posted.")
                        .font(Theme.body(16)).foregroundStyle(Theme.orange).fixedSize(horizontal: false, vertical: true)
                }

                if spot.primary != nil {
                    Block("Coming up") {
                        ForEach(windows.prefix(5), id: \.self) { w in
                            HStack {
                                Text(NY.format(w.start, "EEE, MMM d")).font(Theme.body(17, 600)).frame(width: 120, alignment: .leading)
                                if w.suspended {
                                    Text("Suspended, holiday").font(Theme.body(17)).foregroundStyle(Theme.mint)
                                } else {
                                    Text(spot.primary!.timeText).font(Theme.body(17)).monospacedDigit()
                                }
                                Spacer()
                            }
                            .padding(.vertical, 6)
                            .overlay(alignment: .bottom) { Rectangle().fill(Theme.line).frame(height: 1) }
                        }
                        if let w = windows.first(where: { !store.holidays.covers($0.start) }) {
                            Text("The city hasn’t posted its \(String(NY.calendar.component(.year, from: w.start))) holiday calendar yet, so those dates assume the rules are in effect. Sweep checks for it each time it opens.")
                                .font(Theme.body(15)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)
                        }
                    }

                    Block("Reminders") {
                        if store.notificationsAllowed == false {
                            Text("Notifications are off for Sweep, so no reminders will arrive.")
                                .font(Theme.body(17, 600)).foregroundStyle(Theme.vermilion)
                            Button("Open Settings") {
                                if let u = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(u) }
                            }.buttonStyle(SquareButton(fill: nil))
                        } else {
                            Text(reminderText()).font(Theme.body(17)).fixedSize(horizontal: false, vertical: true)
                        }
                        Button("Change reminder times") { showSettings = true }.buttonStyle(SquareButton(fill: nil))
                    }
                }

                Button("Map of cleaning days") { showMap = true }.buttonStyle(SquareButton(fill: nil))
                Button("Walk to my car") { walk() }.buttonStyle(SquareButton(fill: nil))
                Button("I moved the car") { confirmMoved = true }.buttonStyle(SquareButton())

                Text("Snow and other emergency suspensions aren’t in the city’s calendar file, so Sweep can’t know about them. The posted sign is the rule.")
                    .font(Theme.body(14)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)
            }
            .padding(16)
        }
    }

    func reminderText() -> String {
        let a = store.scheduled.filter { $0.kind != .suspended }.prefix(2)
        if a.isEmpty { return "No reminders are set. Turn one on below." }
        let times = a.map { "\(NY.format($0.fire, "EEE, MMM d")) at \(Clock.text(NY.calendar.component(.hour, from: $0.fire) * 60 + NY.calendar.component(.minute, from: $0.fire)))" }
        return "Next: " + times.joined(separator: " and ") + "."
    }

    func walk() {
        let item = MKMapItem(placemark: MKPlacemark(coordinate: parked.car.cl))
        item.name = "My car"
        item.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeWalking])
    }
}

struct Status {
    let headline: String
    let sub: String?
    let color: Color

    init(spot: Spot, next: Window?, now: Date) {
        guard let rule = spot.primary else {
            headline = "No street cleaning on record for this side."
            sub = "City records show no broom sign on \(spot.streetName)’s \(spot.sideName) side here. Check the posted signs."
            color = Theme.mint
            return
        }
        guard let w = next else {
            headline = "No cleaning in the next four weeks."
            sub = rule.text
            color = Theme.mint
            return
        }
        if w.start <= now {
            let endMin = NY.calendar.component(.hour, from: w.end) * 60 + NY.calendar.component(.minute, from: w.end)
            headline = "Street cleaning now, until \(Clock.text(endMin)). Move the car."
            sub = nil
            color = Theme.vermilion
            return
        }
        let startMin = NY.calendar.component(.hour, from: w.start) * 60 + NY.calendar.component(.minute, from: w.start)
        let cal = NY.calendar
        let dayDiff = cal.dateComponents([.day], from: cal.startOfDay(for: now), to: cal.startOfDay(for: w.start)).day ?? 0
        let dayWord = dayDiff == 0 ? "today" : dayDiff == 1 ? "tomorrow" : NY.format(w.start, "EEEE")
        let timeWord = startMin == 0 ? "midnight" : Clock.text(startMin)
        if startMin == 0 && dayDiff >= 1 {
            // A midnight start means the night before the posted day
            let night = dayDiff == 1 ? "tonight" : "\(NY.format(cal.date(byAdding: .day, value: -1, to: w.start)!, "EEEE")) night"
            headline = "Move by midnight \(night)."
        } else {
            headline = "Move by \(timeWord) \(dayWord)."
        }
        let hours = w.start.timeIntervalSince(now) / 3600
        sub = "In " + Status.span(hours) + ". No parking \(NY.format(w.start, "EEE")) \(rule.timeText)."
        color = hours < 24 ? Theme.vermilion : hours < 72 ? Theme.orange : Theme.mint
    }

    static func span(_ h: Double) -> String {
        if h < 1 { return "\(max(1, Int((h * 60).rounded()))) minutes" }
        if h < 24 { let n = Int(h.rounded()); return n == 1 ? "1 hour" : "\(n) hours" }
        let d = Int(h / 24), r = Int(h.truncatingRemainder(dividingBy: 24).rounded())
        return (d == 1 ? "1 day" : "\(d) days") + (r > 0 ? ", \(r) hour\(r == 1 ? "" : "s")" : "")
    }
}

struct Block<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    init(_ title: String, @ViewBuilder content: () -> Content) { self.title = title; self.content = content() }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(Theme.display(22, 700, style: .title2))
            content
        }
    }
}

struct CarMap: View {
    let parked: ParkedCar
    var body: some View {
        Map(initialPosition: .camera(MapCamera(centerCoordinate: parked.car.cl, distance: 380)), interactionModes: [.zoom, .pan]) {
            if parked.spot.line.count > 1 {
                MapPolyline(coordinates: parked.spot.line.map(\.cl)).stroke(Theme.sun, style: StrokeStyle(lineWidth: 7, lineCap: .round))
            }
            Annotation("Car", coordinate: parked.car.cl, anchor: .center) { CarMark() }.annotationTitles(.hidden)
        }
        .mapStyle(.standard(emphasis: .muted, pointsOfInterest: .excludingAll))
        .overlay(Rectangle().stroke(Theme.line, lineWidth: 1))
    }
}

// MARK: - Settings

struct SettingsView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss
    let leads = [15, 30, 45, 60, 90, 120]

    var eveningTime: Binding<Date> {
        Binding(get: { Schedule.at(NY.calendar.startOfDay(for: Date()), store.settings.eveningMinutes) },
                set: { d in store.settings.eveningMinutes = NY.calendar.component(.hour, from: d) * 60 + NY.calendar.component(.minute, from: d) })
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("Sweep sends up to two reminders before each cleaning, and a note the evening before when the city has suspended it for a holiday.")
                        .font(Theme.body(17)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)
                    VStack(alignment: .leading, spacing: 10) {
                        Toggle(isOn: $store.settings.eveningOn) { Text("The evening before").font(Theme.display(20, 700)) }
                            .tint(Theme.sun)
                        if store.settings.eveningOn {
                            DatePicker("At", selection: eveningTime, displayedComponents: .hourAndMinute)
                                .font(Theme.body(17))
                                .environment(\.timeZone, NY.zone)
                        }
                    }
                    Rectangle().fill(Theme.line).frame(height: 1)
                    VStack(alignment: .leading, spacing: 10) {
                        Toggle(isOn: $store.settings.beforeOn) { Text("Before cleaning starts").font(Theme.display(20, 700)) }
                            .tint(Theme.sun)
                        if store.settings.beforeOn {
                            Picker("How long before", selection: $store.settings.beforeMinutes) {
                                ForEach(leads, id: \.self) { m in Text(m < 60 ? "\(m) min" : m % 60 == 0 ? "\(m / 60) hr" : "1½ hr").tag(m) }
                            }
                            .pickerStyle(.segmented)
                        }
                    }
                    Rectangle().fill(Theme.line).frame(height: 1)
                    Toggle(isOn: $store.settings.tellSuspended) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Holiday suspensions").font(Theme.display(20, 700))
                            Text("Tell me the evening before when I don’t need to move.").font(Theme.body(15)).foregroundStyle(Theme.fg2)
                        }
                    }
                    .tint(Theme.sun)
                    .disabled(!store.settings.eveningOn)
                    Text("For a sign that starts at midnight, “the evening before” is the evening before that midnight.")
                        .font(Theme.body(15)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)
                }
                .padding(16)
            }
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("Reminders")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.foregroundStyle(Theme.sun) } }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - About

struct AboutView: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    para("Where the hours come from", "Every current street-cleaning sign (the ones with the broom) in NYC DOT’s Parking Regulation Locations and Signs data, \(store.data.map { $0.pulled.isEmpty ? "" : "pulled \(pretty($0.pulled))" } ?? ""). Sweep groups the signs by block and side of the street and uses the hours most of them show. It has \(store.data?.faces.count.formatted() ?? "about 56,000") block sides. About 2,100 more are in the city’s records without a location, so Sweep can’t match them.")
                    para("How it finds your side", "It takes your phone’s location and finds the nearest street-cleaning signs. Phones are often off by 5 to 10 meters, about the width of a street, so Sweep shows both sides of the nearest blocks and lets you pick. If a side has no broom sign in the records, it says so.")
                    para("Holidays", holidayText())
                    para("What it can’t know", "Snow and emergency suspensions, which the city announces through 311 and @NYCASP. Signs put up or changed after the data was pulled. Temporary no-parking signs for film shoots or construction. The posted sign is the rule.")
                    Link("City’s suspension calendar", destination: URL(string: "https://www.nyc.gov/html/dot/html/motorist/alternate-side-parking.shtml")!)
                        .font(Theme.body(17, 600)).foregroundStyle(Theme.sun)
                    Link("311 alternate side parking status", destination: URL(string: "https://portal.311.nyc.gov/article/?kanumber=KA-01011")!)
                        .font(Theme.body(17, 600)).foregroundStyle(Theme.sun)
                }
                .padding(16)
            }
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("About Sweep")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.foregroundStyle(Theme.sun) } }
        }
        .preferredColorScheme(.dark)
    }

    func para(_ h: String, _ t: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(h).font(Theme.display(20, 700))
            Text(t).font(Theme.body(17)).foregroundStyle(Theme.fg2).fixedSize(horizontal: false, vertical: true)
        }
    }

    func holidayText() -> String {
        let years = store.holidays.years.sorted().map(String.init).joined(separator: " and ")
        let checked = store.holidays.checked.map { " Last downloaded \(NY.format($0, "MMM d, h:mm a"))." } ?? " The copy built into the app is in use until the download succeeds."
        return "Sweep reads DOT’s published suspension calendar (\(years)) and skips reminders on those days. It downloads a fresh copy, including next year’s once the city posts it, each time it opens.\(checked)"
    }

    func pretty(_ ymd: String) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.timeZone = NY.zone
        guard let d = f.date(from: ymd) else { return ymd }
        return NY.format(d, "MMMM d, yyyy")
    }
}
