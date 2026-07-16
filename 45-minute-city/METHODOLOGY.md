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
| Walking assumed a flat `GRID_FACTOR = 1.4` detour over straight-line distance. | Walking and cycling are routed on the city's real street network (199,859 nodes, 267,515 segments). |
| No wait times at all. | Waits are computed per stop, route, direction and time of day from scheduled departures. |
| `transitScore()` produced an invented 0–100 index from arbitrary weights. | Removed. The map reports measured quantities only: kilometres of street, stations and stops reached. |

The old 1.4 detour constant was itself testable, so we tested it. Routing 2,395
random origin and destination pairs on the real network gives a median ratio of
**1.31**, spread from 1.13 at the tenth percentile to 1.73 at the ninetieth. A
single constant was never adequate. The current build routes the network and
applies no factor; the measurement is kept only as a reference in
`pipeline/out/detour.json`.

## Sources

| Input | Source |
|---|---|
| Subway schedules | MTA GTFS static, `gtfs_subway.zip` |
| Bus schedules | MTA GTFS static for the Bronx, Brooklyn, Manhattan, Queens and Staten Island, plus MTA Bus Company |
| Streets | NYC Open Data, Centerline (CSCL), dataset `inkn-q76z`, including `posted_speed` and `trafdir` |
| Taxi calibration | TLC yellow-cab trip records, March 2026 (`yellow_tripdata_2026-03.parquet`) |
| Taxi zones | NYC Open Data dataset `8meu-9t5y` (263 zones) |
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
| Subway (weekday AM peak) | 10.8 | **15.1** | 20.8 | 32.7 mph |

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

The same 6 train goes from 6.9 minutes at peak to 14.7 minutes late at night.

## Taxi

Cars route on a DIRECTED graph built from the same centerline file: one-way
streets are honored via `trafdir` (166,919 nodes, 312,188 directed edges), and
highways, bridges, tunnels and ramps are included. Each segment costs its length
at the posted speed limit (missing or zero limits default to the city's 25 mph).

Posted limits are a ceiling, not a description of traffic. To measure how far
below them the city actually moves, every band's factor comes from real trips:

    alpha = observed trip duration / posted-speed routed duration

computed per trip over a month of TLC yellow-cab records (March 2026), routing
each trip's pickup zone centroid to its dropoff zone centroid on the car graph.
Roughly 64,000 to 77,000 usable trips per band after filters (3 min–2 h duration,
0.8–35 mi, 1–65 mph implied, pickup and dropoff in different zones).

The factor is measured PER BOROUGH, because a single citywide number
flattered Manhattan (where most of the trips are) and slandered the edges of
the city. Each borough's factor comes from intra-borough, non-shared Uber/Lyft
trips in the TLC high-volume FHV file — 11.9 million usable trips in March
2026 — and is applied to each street segment by its borough. Cross-borough
segments of a trip simply pick up each borough's factor as the route passes
through.

| Band | Citywide | Manhattan | Brooklyn | Queens | Bronx | Staten Island |
|---|---|---|---|---|---|---|
| Weekday AM peak | 2.32 | 2.53 | 2.34 | 2.12 | 2.29 | 1.46 |
| Weekday midday | 2.39 | 2.85 | 2.42 | 2.11 | 2.23 | 1.48 |
| Weekday PM peak | 2.51 | 2.80 | 2.49 | 2.23 | 2.33 | 1.55 |
| Weekday evening | 2.04 | 2.30 | 2.09 | 1.83 | 1.90 | 1.34 |
| Weekday late night | 1.71 | 1.91 | 1.82 | 1.59 | 1.71 | 1.29 |
| Saturday midday | 2.56 | 2.84 | 2.54 | 2.28 | 2.45 | 1.55 |
| Sunday midday | 2.34 | 2.63 | 2.39 | 2.12 | 2.14 | 1.47 |

A 25 mph Manhattan street at weekday midday is effectively an 8.8 mph street —
the crosstown speed every New Yorker knows — while the same street in Queens
moves at 11.8 and Staten Island at 16.9. An earlier build applied one citywide
factor from yellow-cab trips (midday 2.75); the two sources agree closely
where they overlap, which is a good sign since they are different vehicle
fleets measured different ways.

### The pickup wait

The taxi clock starts at the REQUEST, matching transit, which pays its
platform wait. The median request-to-pickup gap over every non-shared FHV trip
in the month is about 4 minutes (3.8 to 4.6 by band) — measured, not assumed.
Without this, the taxi map was structurally flattered against the train.

### Validation

Midday from Grand Central, against common experience: Columbus Circle, Wall Street, Barclays Center and LaGuardia all land inside
real cab ranges for weekday midday.

### Known biases, and their direction

- **Highway compression.** One factor per borough still slows a flowing
  expressway as much as a jammed local street, so highway-heavy trips — the
  airports especially — read somewhat slower than reality.
- **Zone centroids.** Trips are routed centroid to centroid rather than
  door to door; the median over tens of thousands of trips absorbs this noise.

Any single ride also varies enormously — intra-Manhattan midday spans roughly
2.2 to 3.6 between the 25th and 75th percentile trip.

Not modeled: tolls and turn penalties. (The pickup wait now is.)

## Train vs cab

Total reach is the wrong lens for "which is faster" — a car sweeps every
street while the subway wins point-to-point along its corridors, and both
facts are true at once. The "Train vs cab" view answers the real question:
from your origin, every street is colored by which door-to-door trip arrives
first, waits included on both sides. Blue where the train is faster, orange
where the cab is, faded orange where the train cannot arrive within the budget
at all, gray where they land within two minutes of each other.

From Washington Square at the morning rush, the train's wins trace the express
spines — the West Side and Lexington lines into upper Manhattan and the Bronx —
while the cab takes the near field and the space between lines. At 3am the
train's winning territory nearly vanishes. Technically: taxi times live on the
drivable graph and transit times on the walk graph, so each car node is linked
to its nearest walk node at build time (`pipeline/build_carlink.py`).

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
from any street node, and 18 — bus stops on routes that dip into Nassau County —
have no city street within reach at all. Buses ride through those 18 normally;
you just cannot board or alight there, which mirrors reality for a map that ends
at the city line.

## Bridges

CSCL types car-only expressway decks (the Verrazzano, Throgs Neck, the elevated
Brooklyn-Queens Expressway) as "bridge" alongside walkable crossings, and posted
speed does not separate them — the Verrazzano deck is posted at 35. What does
separate them, verified in the data: every major crossing with pedestrian access
has dedicated path segments ("BROOKLYN BRIDGE PEDESTRIAN PATH", "GEORGE
WASHINGTON BRDG PED PATH"), so same-named roadway decks are excluded from the
walk and bike graphs, while small local drawbridges (Gowanus, Newtown Creek,
City Island), whose sidewalks live on the roadway segment, stay.

A consequence handled deliberately: severing the Verrazzano makes Staten
Island's street network a separate component — which is true; the island has no
pedestrian link — so the graph keeps every component of 500+ nodes rather than
only the largest, which would have deleted the borough. (An earlier draft of
this build allowed walking to Staten Island over the Verrazzano; an adversarial
review caught it.)

## Accessibility mode

The "I require accessible transit" toggle answers the same question for a rider
who cannot use stairs.

- **Subway**: boarding and alighting are limited to the MTA's listed accessible
  stations — 162 fully accessible and 9 accessible in one direction, of 496.
  Trains still ride through everything else. The 9 partial stations are treated
  as accessible in both directions, a small optimism noted here because GTFS
  direction ids do not map cleanly onto the MTA's north/south flags.
- **Bus**: unchanged. The entire fleet has ramps or lifts.
- **Walking**: routed on the street network minus step streets — the
  stairs-free network.
- **Taxi/Uber**: becomes a wheelchair-accessible vehicle (WAV), and the clock
  starts at the request. The wait is measured, not assumed: the TLC high-volume
  FHV file records request and pickup timestamps and a WAV flag for every
  Uber/Lyft trip in the city. Median request-to-pickup over March 2026, per
  band, runs 7.1 to 7.9 minutes (1,072 to 21,538 WAV requests per band),
  against 3.8 to 4.6 minutes for standard vehicles.
- **Access-A-Ride** is absent, deliberately: it must be booked by 5pm the day
  before, so it cannot appear in a map of where you can go from here, now. Its
  absence from a turn-up-and-go picture is itself a finding.

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
- **Route branches.** A rider who boards a trunk stop pays that stop's combined
  wait and can then chain to either branch of the route (the A to Lefferts or
  the Rockaways) without a further wait, though a specific branch runs less
  often than the trunk. Branch termini therefore read somewhat closer than
  reality — one of the few optimistic errors in this model, bounded by the
  branch's own headway.
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
| Taxi times | Moderate. Calibrated to real trips, but one factor per band; conservative on highways and in the outer boroughs. |
| Walking and cycling speeds | Assumptions, exposed as sliders. |
| Correspondence to a real trip | Moderate. Schedules are optimistic; delay is not modelled. |

## Rebuilding

```
python3 pipeline/probe_feeds.py     # verify every source URL resolves
python3 pipeline/build_transit.py   # MTA GTFS -> ride times + headways per band
python3 pipeline/build_streets.py   # CSCL -> routable walk/bike graph
python3 pipeline/build_link.py      # snap stops to streets; measure detour factor
python3 pipeline/build_car.py       # CSCL -> directed drivable graph with posted speeds
python3 pipeline/calibrate_taxi.py  # yellow-cab citywide factors (cross-check)
python3 pipeline/calibrate_boroughs.py # FHV -> per-borough factors + car_zones.bin
python3 pipeline/build_carlink.py   # car node -> nearest walk node (race view)
python3 pipeline/pack.py            # pack to binary for the browser
cp pipeline/out/{core.json,bands.bin,bands.json,street_nodes.bin,street_edges.bin,car_nodes.bin,car_edges.bin,car_calibration.json} data/
python3 pipeline/validate.py        # speed + headway checks quoted above
```

Total payload is 12.4 MB across nine files, covering all seven time bands.

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
