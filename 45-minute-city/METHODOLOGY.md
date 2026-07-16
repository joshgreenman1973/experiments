# The 45-minute city — methodology

How far can you actually get from a point in New York City inside a time budget,
on foot, by bike, by subway or by bus?

Every travel time is computed from published schedules and the city's real street
geometry. Nothing is hand-tuned. This document records what is measured, what is
assumed and where the map is likely to be wrong.

## What changed from the previous version

The earlier build of this map was a working prototype with three problems. All
three are fixed here, and the fixes are the reason for the rebuild.

| Old | New |
|---|---|
| Bus times were wrong, then multiplied by a hardcoded `2.5` to "reflect real-world speeds". Implied speeds reached 64 mph. | Bus times come from the MTA bus GTFS feeds. Median implied speed is 7.4 mph. No correction applied, and none needed. |
| Walking assumed a flat `GRID_FACTOR = 1.4` detour over straight-line distance. | Walking and cycling are routed on the city's real street network (198,792 nodes, 266,213 segments). |
| No wait times at all. | Waits are computed per stop, route, direction and time of day from scheduled departures. |
| `transitScore()` produced an invented 0–100 index from arbitrary weights. | Removed. The map reports measured quantities only: kilometres of street, stations and stops reached. |

The old 1.4 detour constant was itself testable, so we tested it. Routing 2,392
random origin and destination pairs on the real network gives a median ratio of
**1.30**, spread from 1.10 at the tenth percentile to 1.78 at the ninetieth. A
single constant was never adequate. The current build routes the network and
applies no factor; the measurement is kept only as a reference in
`pipeline/out/detour.json`.

## Sources

| Input | Source |
|---|---|
| Subway schedules | MTA GTFS static, `gtfs_subway.zip` |
| Bus schedules | MTA GTFS static for the Bronx, Brooklyn, Manhattan, Queens and Staten Island, plus MTA Bus Company |
| Streets | NYC Open Data, Centerline (CSCL), dataset `inkn-q76z` |
| Geocoding | Nominatim (OpenStreetMap), at query time |

All feed URLs are probed before use by `pipeline/probe_feeds.py`. None are guessed.

## Ride times

For each pair of consecutive stops on each route and direction, we take every
scheduled trip whose departure falls inside a time band and compute the median of
`arrival at B - departure from A`. Segments implying more than an hour between
adjacent stops are dropped as layover artifacts.

These are medians of real timetable rows.

### Validation

Dividing straight-line distance by the scheduled time gives a lower bound on true
speed, since track and street distance always exceed straight-line distance.

| Mode | p10 | Median | p90 | Max |
|---|---|---|---|---|
| Bus (weekday AM peak) | 5.0 | **7.4** | 12.7 | 44.5 mph |
| Subway (weekday AM peak) | 11.4 | **15.3** | 21.0 | 32.7 mph |

New York City buses average roughly 7 to 8 mph citywide, so the bus figure lands
where it should. No segment implies a bus faster than 45 mph.

Late-night buses come out faster than peak buses (10.2 mph against 7.4). That is
congestion showing up in the schedule, and it is a good sign: it was not put there
deliberately.

Run `pipeline/validate.py` to reproduce this table.

## Waiting

For each stop, route and direction, we count scheduled departures inside a band
and divide the band's duration by that count to get a headway. The wait is half
the headway, which is the average for a rider arriving without consulting a
timetable.

Three details matter:

1. **Direction is counted separately.** A rider going uptown gains nothing from
   downtown trains. Collapsing the subway's N and S platforms onto one station and
   counting both would halve every wait.
2. **You pay the wait once, at boarding.** The router models one node per
   `(stop, route, direction)`; riding onward is free. A graph that charged a wait
   per edge would bill a rider thirty waits down Lexington Avenue.
3. **The wait is capped**, by default at 20 minutes and adjustable in the
   interface. An hourly bus then contributes a 20-minute wait rather than 30,
   which is roughly how people treat infrequent service — they consult the
   schedule instead of turning up blind.

### Validation

Weekday AM peak headways, per direction:

| Route | Median headway |
|---|---|
| 6 | 6.9 min |
| L | 3.6 min |
| 7 | 5.2 min |
| A | 6.7 min |
| G | 7.5 min |
| B41 | 8.6 min |
| M104 | 12.8 min |

The 6 train reads 6.9 minutes rather than the 2 to 4 minutes riders experience,
and the reason is instructive. At 86 St in the peak direction the schedule has 26
route `6` departures in three hours and a further 27 on route `6X`, the Pelham Bay
express, which runs peak-direction only. Together they are a train every 3.4
minutes. The map counts them separately, so it is conservative here. See
"common lines" below.

The same 6 train goes from 6.9 minutes at peak to 28.9 minutes late at night.

## Walking and cycling

Both are routed on the CSCL street network, filtered by road type:

- **Walk**: streets, bridges, boardwalks, paths, step streets, alleys.
- **Bike**: the same, minus step streets, which are stairs.
- **Both exclude**: highways, ramps, driveways, ferry routes, non-physical
  segments and U-turns.

The graph keeps only the largest connected component, which is 95.8% of nodes;
the remainder is stray geometry that would leave some origins unroutable.

Default speeds are 3.1 mph walking and 8.9 mph cycling. Both are exposed as
sliders, because a person's speed is not the map's assumption to make.

Transit stops are snapped to the nearest street node: median distance 20.6 m, 45.2 m
at the ninety-fifth percentile. Seventy-four stops of 14,833 sit more than 200 m
from any street node.

## Station counts

The map counts 496 subway stations where the commonly cited figure is 472. Both
are correct. The MTA's feed treats separately-built stations that share a name as
distinct: there are four parent stations called "Times Sq-42 St" and four called
"125 St". The 472 figure counts connected complexes once.

## What this does not model

- **Delays.** These are schedules, not what ran. Real trips are worse. This is the
  single largest gap between the map and the city, and it runs one way.
- **Common lines.** Each route's wait is computed on its own. In reality a rider
  boards whichever train arrives first, so where several routes serve the same
  trip — the 6 and the 6X, or the 4, 5 and 6 down Lexington Avenue — the true wait
  is shorter than shown. The map is conservative here.
- **Crowding, fare gates, elevators, stairs and platform changes.** No penalty for
  entering a station or transferring between platforms, which makes complex
  transfers slightly optimistic.
- **Bike lanes, hills and bike parking.** Cycling uses street geometry at a flat
  speed. It does not know that a bridge approach is a climb.
- **Planned service changes.** Weekend and overnight diversions are not in the
  static feed.
- **Bikes plus transit.** Bike mode is bike only; transit modes walk to the stop.
- **Ferries, PATH, Metro-North, Long Island Rail Road, New Jersey Transit.** Not
  included. New Jersey has no street data here either, which is why the map stops
  at the Hudson.

## Confidence

| Quantity | Confidence |
|---|---|
| Ride times | High. Medians of published schedules. |
| Headways and waits | High as scheduled. Standard practice, deliberately conservative. |
| Street routing | High. The city's own centerline file. |
| Walking and cycling speeds | Assumptions, exposed as sliders. |
| Correspondence to a real trip | Moderate. Schedules are optimistic; delay is not modelled. |

## Rebuilding

```
python3 pipeline/probe_feeds.py     # verify every source URL resolves
python3 pipeline/build_transit.py   # MTA GTFS -> ride times + headways per band
python3 pipeline/build_streets.py   # CSCL -> routable walk/bike graph
python3 pipeline/build_link.py      # snap stops to streets; measure detour factor
python3 pipeline/pack.py            # pack to binary for the browser
cp pipeline/out/{core.json,bands.bin,bands.json,street_nodes.bin,street_edges.bin} data/
python3 pipeline/validate.py        # speed + headway checks quoted above
```

Total payload is 7.6 MB across five files, covering all seven time bands.

## Time bands

| Band | Window |
|---|---|
| `weekday_am_peak` | 7–10am |
| `weekday_midday` | 10am–4pm |
| `weekday_pm_peak` | 4–7pm |
| `weekday_evening` | 7–11pm |
| `weekday_late` | 11pm–5am |
| `saturday_midday` | 10am–6pm |
| `sunday_midday` | 10am–6pm |

Service dates are chosen inside each feed's validity window: a representative
Wednesday, Saturday and Sunday, with `calendar_dates.txt` exceptions honoured.

## A note on the AI caution label

This map was built with heavy use of an AI coding assistant. The inputs are
authoritative and the outputs are validated against known quantities, but the code
joining them was largely machine-written. Treat it as a research sketch, not a trip
planner.
