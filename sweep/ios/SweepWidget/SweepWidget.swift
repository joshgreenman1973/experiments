import SwiftUI
import WidgetKit
#if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
import ActivityKit
#endif

private enum C {
    static let bg = Color(red: 0x11 / 255, green: 0x13 / 255, blue: 0x11 / 255)
    static let fg = Color(red: 0xf2 / 255, green: 0xf3 / 255, blue: 0xef / 255)
    static let fg2 = Color(red: 0xa2 / 255, green: 0xa8 / 255, blue: 0xa1 / 255)
    static let sun = Color(red: 1, green: 0xd2 / 255, blue: 0x3f / 255)
    static let vermilion = Color(red: 1, green: 0x6a / 255, blue: 0x45 / 255)
    static let orange = Color(red: 1, green: 0x9f / 255, blue: 0x2e / 255)
    static let mint = Color(red: 0x3f / 255, green: 0xd6 / 255, blue: 0x8f / 255)
    static func of(_ u: Urgency) -> Color {
        switch u { case .now, .today: vermilion; case .soon: orange; case .later: mint; case .none: fg2 }
    }
}

struct Entry: TimelineEntry {
    let date: Date
    let car: CarSnapshot?
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> Entry { Entry(date: Date(), car: Self.sample) }
    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) {
        completion(Entry(date: Date(), car: context.isPreview ? (CarSnapshot.load() ?? Self.sample) : CarSnapshot.load()))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        let car = CarSnapshot.load(), now = Date()
        // Redraw when a window starts or ends, at each midnight (today/tomorrow wording) and a few
        // hours before each start (the color steps up).
        var times: Set<Date> = [now]
        for w in car?.windows ?? [] where w.end > now {
            times.insert(w.start); times.insert(w.end)
            for h in [12.0, 48.0] { times.insert(w.start.addingTimeInterval(-h * 3600)) }
        }
        var day = MoveText.cal.startOfDay(for: now)
        for _ in 0..<10 { day = MoveText.cal.date(byAdding: .day, value: 1, to: day)!; times.insert(day) }
        let entries = times.filter { $0 >= now }.sorted().prefix(60).map { Entry(date: $0, car: car) }
        completion(Timeline(entries: Array(entries), policy: .atEnd))
    }
    static let sample = CarSnapshot(street: "Union Street", side: "south", between: "between 6th Avenue and 7th Avenue", hasRule: true,
                                    windows: [.init(start: Date().addingTimeInterval(30 * 3600), end: Date().addingTimeInterval(31.5 * 3600), suspended: false)],
                                    madeAt: Date())
}

struct MoveByView: View {
    let entry: Entry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        if let car = entry.car {
            let l = MoveText.line(car, now: entry.date)
            switch family {
            case .accessoryInline:
                Text(l.urgency == .none ? l.short : "Move car \(l.short)")
            case .accessoryRectangular:
                VStack(alignment: .leading, spacing: 1) {
                    Text(l.headline).font(.headline).lineLimit(2).minimumScaleFactor(0.8)
                    Text("\(car.street), \(car.side) side").font(.caption).lineLimit(1)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            default:
                VStack(alignment: .leading, spacing: 6) {
                    Text("SWEEP").font(.system(size: 11, weight: .heavy)).kerning(1.2).foregroundStyle(C.sun)
                    Text(l.headline).font(.system(size: 19, weight: .heavy)).foregroundStyle(C.of(l.urgency))
                        .lineLimit(3).minimumScaleFactor(0.75)
                    Spacer(minLength: 0)
                    if let t = l.countdownTo, l.urgency == .now || l.urgency == .today {
                        Text(t, style: .relative).font(.system(size: 13, weight: .bold)).foregroundStyle(C.fg).monospacedDigit()
                    }
                    Text("\(car.street), \(car.side) side").font(.system(size: 12, weight: .semibold)).foregroundStyle(C.fg2).lineLimit(2)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
        } else {
            switch family {
            case .accessoryInline: Text("Sweep: no car parked")
            case .accessoryRectangular:
                VStack(alignment: .leading) { Text("Sweep").font(.headline); Text("No car parked").font(.caption) }
            default:
                VStack(alignment: .leading, spacing: 6) {
                    Text("SWEEP").font(.system(size: 11, weight: .heavy)).kerning(1.2).foregroundStyle(C.sun)
                    Text("No car parked").font(.system(size: 19, weight: .heavy)).foregroundStyle(C.fg)
                    Spacer(minLength: 0)
                    Text("Say “I parked with Sweep”").font(.system(size: 12, weight: .semibold)).foregroundStyle(C.fg2)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
        }
    }
}

struct MoveByWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "MoveBy", provider: Provider()) { e in
            MoveByView(entry: e).containerBackground(C.bg, for: .widget)
        }
        .configurationDisplayName("Move by")
        .description("When you next have to move the car for street cleaning. Also shows in CarPlay.")
        .supportedFamilies([.systemSmall, .accessoryRectangular, .accessoryInline])
    }
}

#if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
struct LiveCard: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: SweepActivity.self) { ctx in
            LiveCardView(a: ctx.attributes, s: ctx.state)
                .padding(16)
                .activityBackgroundTint(C.bg)
                .activitySystemActionForegroundColor(C.fg)
        } dynamicIsland: { ctx in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(ctx.state.start > Date() ? "Move by \(MoveText.clock(ctx.state.start))" : "Cleaning now")
                        .font(.headline).foregroundStyle(C.vermilion)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(ctx.state.start > Date() ? ctx.state.start : ctx.state.end, style: .timer)
                        .font(.headline).monospacedDigit().frame(maxWidth: 80)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text("\(ctx.attributes.street), \(ctx.attributes.side) side").font(.caption).foregroundStyle(C.fg2)
                }
            } compactLeading: {
                Image(systemName: "car.fill").foregroundStyle(C.sun)
            } compactTrailing: {
                Text(ctx.state.start > Date() ? ctx.state.start : ctx.state.end, style: .timer)
                    .monospacedDigit().frame(maxWidth: 52).foregroundStyle(C.vermilion)
            } minimal: {
                Image(systemName: "car.fill").foregroundStyle(C.vermilion)
            }
        }
        .supplementalActivityFamilies([.small, .medium])   // .small is what CarPlay and the Watch show
    }
}

struct LiveCardView: View {
    let a: SweepActivity
    let s: SweepActivity.ContentState
    @Environment(\.activityFamily) private var family

    var body: some View {
        let upcoming = s.start > Date()
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(upcoming ? "Move by \(MoveText.clock(s.start))" : "Cleaning now: move the car")
                    .font(.system(size: family == .small ? 15 : 20, weight: .heavy)).foregroundStyle(C.vermilion)
                    .lineLimit(1).minimumScaleFactor(0.7)
                Spacer(minLength: 4)
                Text(upcoming ? s.start : s.end, style: .timer)
                    .font(.system(size: family == .small ? 15 : 20, weight: .bold)).monospacedDigit().foregroundStyle(C.fg)
                    .multilineTextAlignment(.trailing).frame(maxWidth: 90, alignment: .trailing)
            }
            Text("\(a.street), \(a.side) side" + (upcoming ? "" : ". No parking until \(MoveText.clock(s.end))."))
                .font(.system(size: family == .small ? 12 : 14, weight: .semibold)).foregroundStyle(C.fg2).lineLimit(2)
        }
    }
}
#endif

@main
struct SweepWidgets: WidgetBundle {
    var body: some Widget {
        MoveByWidget()
        #if canImport(ActivityKit) && !targetEnvironment(macCatalyst)
        LiveCard()
        #endif
    }
}
