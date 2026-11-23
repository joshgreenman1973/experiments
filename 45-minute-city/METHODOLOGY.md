# The 45-minute city — methodology

How far can you get from a point in New York City inside a time budget,
on foot, by bike, by subway or by bus?

Every travel time is computed from published schedules and the city's street
geometry. No travel time is hand-tuned. This document records what is measured, what is
assumed and where the map is likely to be wrong.

## What changed from the previous version

The earlier build of this map was a working prototype with three problems. All
three are fixed here, and the fixes are the reason for the rebuild.

| Old | New |
|---|---|
| Bus times were wrong, then multiplied by a hardcoded `2.5` to "reflect real-world speeds". Implied speeds reached 64 mph. | Bus times come from the MTA bus GTFS feeds. Median implied speed is 7.3 mph. No blanket correction; four plainly wrong timetable rows are held to 60 mph (see Validation). |
| Walking assumed a flat `GRID_FACTOR = 1.4` detour over straight-line distance. | Walking and cycling are routed on the city's real street network (331,310 nodes, 427,613 segments, including the New Jersey PATH corridor). |
| No wait times at all. | Waits are computed per stop, route, direction and time of day from scheduled departures. |
| `transitScore()` produced an invented 0–100 index from arbitrary weights. | Removed. The map reports measured quantities only: kilometres of street, stations and stops reached. |

The old 1.4 detour constant was itself testable, so we tested it. Routing 2,396
random origin and destination pairs on the street network gives a median ratio of
**1.28**, spread from 1.10 at the tenth percentile to 1.69 at the ninetieth. No
single constant fits that spread. The current build routes the network and
applies no factor; the measurement is kept only as a reference in
`pipeline/out/detour.json`.

## Sources

| Input | Source |
|---|---|
| Subway schedules | MTA GTFS static, `gtfs_subway.zip` (downloaded November 23, 2026; service of the week of November 25) |
| Bus schedules | MTA GTFS static for the Bronx, Brooklyn, Manhattan, Queens and Staten Island, plus MTA Bus Company (downloaded November 23, 2026; fall 2026 schedules) |
| Staten Island Ferry | NYC DOT GTFS, NYC Open Data `b57i-ri22` (feed version 18, valid 2026-01-01 to 2028-01-17) |
| NYC Ferry | Operator GTFS via Connexionz (feed version 20261112, the fall and winter 2026 schedule) |
| PATH | Port Authority Trans-Hudson GTFS via Trillium (see the staleness note below) |
| New Jersey streets | OpenStreetMap via Overpass, PATH corridor only (Newark, Harrison, Jersey City, Hoboken) |
| Streets | NYC Open Data, Centerline (CSCL), dataset `inkn-q76z`, including `posted_speed` and `trafdir` |
| Taxi calibration | TLC high-volume for-hire (Uber/Lyft) trip records, March 2026 (`fhvhv_tripdata_2026-03.parquet`), cross-checked against yellow-cab records (`yellow_tripdata_2026-03.parquet`) |
| Taxi zones | NYC Open Data dataset `8meu-9t5y` (263 zones) |
| Geocoding | Nominatim (OpenStreetMap), at query time |

All feed URLs are probed before use by `pipeline/probe_feeds.py`.

## Ride times

For each pair of consecutive stops on each route and direction, we take every
scheduled trip whose departure falls inside a time band and compute the median of
`arrival at B - departure from A`. Segments implying more than an hour between
adjacent stops are dropped as layover artifacts.

These are medians of timetable rows.

### Validation

Dividing straight-line distance by the scheduled time gives a lower bound on true
speed, since track and street distance always exceed straight-line distance.

| Mode | p10 | Median | p90 | Max |
|---|---|---|---|---|
| Bus (weekday AM peak) | 5.0 | **7.3** | 12.7 | 44.5 mph |
| Subway (weekday AM peak) | 10.7 | **15.0** | 20.9 | 32.7 mph |

New York City buses average roughly 7 to 8 mph citywide, so the bus figure lands
where it should. Four segments on the Q19 at the evening rush imply 112 to 142 mph (571 m in
9 seconds) — timetable errors. The router holds every bus segment to at most
60 mph over the straight-line distance, which changes only those four; no other bus segment in any band implies more than 54 mph.

Late-night buses come out faster than peak buses (10.7 mph against 7.3). That is
congestion showing up in the schedule, and nothing in the build put it there.

Run `pipeline/validate.py` to reproduce this table.

## Express buses

New York's 77 express routes (the SIM, BM, BxM, QM and X families) are
included. They are the fast, one-seat, limited-stop rides that
carry Staten Island and the deep outer boroughs to Manhattan over the highways.
They are treated as buses, which is what they are, and their times and waits
come from the schedule like any other route.

Two points about them:

- **They run mostly at the peak.** The schedule bears this out — express stops
  see about 7,500 scheduled departures an hour in the weekday morning rush,
  2,600 midday and 700 overnight — so a midday or late-night isochrone
  correctly includes far less express service than a rush-hour one. A route that does not run in a band contributes nothing
  to it.
- **They cost more than double.** The express-bus fare is $7.25, against $3.00
  for a local bus or the subway. This map does not model fares, so express and
  local reach look identical on the map even though one costs the price of a
  sandwich more. A Staten Island rush-hour "bus" isochrone leans heavily on
  $7.25 express service, which commuters use daily at more than twice the $3.00
  fare the color implies.

## Waiting

For each stop, route and direction, we count scheduled departures inside a band
and divide the band's duration by that count to get a headway. The wait is half
the headway, which is the average for a rider arriving without consulting a
timetable.

Three details:

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
| B41 | 7.8 min |
| M104 | 12.8 min |

The 6 train reads 6.9 minutes rather than the 2 to 4 minutes riders experience.
At 86 St in the peak direction the schedule has 26
route `6` departures in three hours and a further 26 on route `6X`, the Pelham Bay
express, which runs peak-direction only. Together they are a train every 3.5
minutes. The map counts them separately, so it is conservative here. See
"common lines" below.

The same 6 train goes from 6.9 minutes at peak to 14.7 minutes late at night.

## Taxi

Cars route on a DIRECTED graph built from the same centerline file: one-way
streets are honored via `trafdir` (166,919 nodes, 308,594 directed edges), and
highways, bridges, tunnels and ramps are included. Each segment costs its length
at the posted speed limit (missing or zero limits default to the city's 25 mph).

Posted limits are a ceiling. To measure how far below them traffic moves,
every band's factor comes from real trips:

    alpha = observed trip duration / posted-speed routed duration

computed per trip over a month of Taxi and Limousine Commission (TLC) yellow-cab records (March 2026), routing
each trip's pickup zone centroid to its dropoff zone centroid on the car graph.
Roughly 64,000 to 77,000 usable trips per band after filters (3 min–2 h duration,
0.8–35 mi, 1–65 mph implied, pickup and dropoff in different zones).

The factor is measured PER BOROUGH, because a single citywide number
made Manhattan (where most of the trips are) look faster and the edges of
the city look slower than they are. Each borough's factor comes from intra-borough, non-shared Uber/Lyft
trips in the TLC high-volume for-hire vehicle (FHV) file — 11.9 million usable trips in March
2026 — and is applied to each street segment by its borough. Cross-borough
segments of a trip pick up each borough's factor as the route passes
through.

| Band | Citywide | Manhattan | Brooklyn | Queens | Bronx | Staten Island |
|---|---|---|---|---|---|---|
| Weekday AM peak | 2.41 | 2.60 | 2.44 | 2.19 | 2.36 | 1.47 |
| Weekday midday | 2.49 | 2.98 | 2.48 | 2.18 | 2.33 | 1.49 |
| Weekday PM peak | 2.60 | 2.87 | 2.53 | 2.30 | 2.44 | 1.58 |
| Weekday evening | 2.08 | 2.37 | 2.11 | 1.85 | 1.92 | 1.35 |
| Weekday late night | 1.78 | 2.00 | 1.87 | 1.61 | 1.73 | 1.29 |
| Saturday midday | 2.34 | 2.63 | 2.39 | 2.12 | 2.14 | 1.47 |
| Sunday midday | 2.16 | 2.41 | 2.32 | 1.95 | 1.95 | 1.44 |

A 25 mph Manhattan street at weekday midday is effectively an 8.4 mph street —
the crosstown speed every New Yorker knows — while the same street in Queens
moves at 11.5 and Staten Island at 16.8. An earlier build applied one citywide
factor from yellow-cab trips (midday 2.75). Yellow cabs work mostly in
Manhattan, and their factor comes out within about 10% of the Manhattan Uber/Lyft
factor in every band, a little faster — a useful cross-check, since they are
different fleets.

**A correction (November 2026).** The first release of this table assigned
trips to the wrong day of the week: a date formula was off by one, so the
"weekday" bands included Sundays, "Saturday" was really Friday and "Sunday" was
really Saturday. The table above is the corrected one. The fix made weekday
traffic slightly slower (Manhattan midday 2.85 became 2.98), and it brought the
weekend factors into line with the yellow-cab cross-check, which had computed
the day of the week correctly all along (Saturday citywide 2.34 against 2.35,
Sunday 2.16 against 2.15). The wait-for-pickup figures below had the same error
and were corrected the same way.

### Light, typical and heavy traffic

The map exposes three traffic levels, and all three are measured. For each borough and time band, the calibration keeps the 25th
percentile trip, the median and the 75th:

- **Light** — the 25th-percentile trip. A quarter of real trips run at least
  this well.
- **Typical** — the median trip.
- **Heavy** — the 75th-percentile trip. A quarter run at least this badly.

At weekday midday in Manhattan those are alphas of 2.37, 2.98 and 3.69: a
25 mph street running at 10.5, 8.4 or 6.8 mph. That spread is
what a New Yorker means by "depends on traffic."

Its effect on the map is large. From Washington Square at the morning rush,
a cab's 45-minute reach runs 6,407 km in light traffic, 3,444 typical and
1,999 heavy — a 3.2x swing. The train's reach does not move at all, because the
train runs on its schedule regardless of traffic. Territory each side wins:

| Traffic | Train wins | Cab is faster | Only a cab reaches | Tie |
|---|---|---|---|---|
| Light | 65 km | 2,216 | 3,930 | 232 |
| Typical | 532 km | 1,479 | 1,150 | 501 |
| Heavy | **1,340 km** | 574 | 273 | 599 |

Territory is counted on drivable streets inside the city, and a street counts
for a mode only when both its ends are reached in time — the same rule as the
per-mode totals, so the cab's three columns never exceed its own reach.

In heavy traffic the train wins more than twice the territory the cab does.
In light traffic it wins almost nothing. Which is faster
depends on a variable the rider cannot see when they decide, and that
uncertainty is the case for taking the train.

The traffic level scales driving speed only. The pickup wait stays at its
measured median, because the data does not establish how strongly wait and
congestion move together, and inventing that correlation would undo the point
of measuring.

### The pickup wait

The taxi clock starts at the REQUEST, matching transit, which pays its
platform wait. The median request-to-pickup gap over every non-shared FHV trip
in the month is about 4 minutes (3.8 to 4.7 by band).
Without it, the taxi map gave the cab an unfair head start against the train.

### Validation

Midday from Grand Central, against common experience: Columbus Circle, Wall Street, Barclays Center and LaGuardia all land inside
real cab ranges for weekday midday.

### Known biases, and their direction

- **Highway compression.** One factor per borough still slows a flowing
  expressway as much as a jammed local street, so highway-heavy trips — the
  airports especially — read somewhat slower than reality.
- **Zone centroids.** Trips are routed centroid to centroid rather than
  door to door; the median over hundreds of thousands of trips absorbs this noise.

### Where a cab starts

A cab starts from the nearest ordinary street — posted at 35 mph or less, and
part of the main network a car can both leave and return to — within 400 m of
the click. An earlier build snapped to the nearest car node of any kind, which
put about 3% of clicks on a dead end (a cab that reaches nothing) and about 6% on
an expressway (Brooklyn Heights onto the Brooklyn-Queens Expressway). With no
such street within 400 m — New Jersey, the middle of a large park — the map says
the cab is not modelled there instead of showing it going nowhere.

Any single ride varies enormously — intra-Manhattan midday spans 2.25 to 3.58
between the 25th and 75th percentile trip. That spread is exposed as the
Light/Typical/Heavy control rather than hidden inside a median.

Not modeled: tolls and turn penalties. (The pickup wait now is.)

## Train vs cab

Total reach does not answer "which is faster": a car sweeps every
street while the subway wins point-to-point along its corridors. The "Train
vs cab" view answers that question:
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
sliders, so you can set your own.

Transit stops are snapped to the nearest street node: median distance 20.6 m, 45.2 m
at the ninety-fifth percentile. Seventy-three stops of 14,994 sit more than 200 m
from any street node, and 20 of those — bus stops on routes that run past the
city line into Nassau County, Yonkers and Bayonne — have no street within reach
at all. Buses ride through those 20 normally;
you just cannot board or alight there, which mirrors reality for a map that ends
at the city line.

## Bridges

CSCL types car-only expressway decks (the Verrazzano, Throgs Neck, the elevated
Brooklyn-Queens Expressway) as "bridge" alongside walkable crossings, and posted
speed does not separate them — the Verrazzano deck is posted at 35. What does
separate them: every major crossing with pedestrian access
has dedicated path segments ("BROOKLYN BRIDGE PEDESTRIAN PATH", "GEORGE
WASHINGTON BRDG PED PATH"), so same-named roadway decks are excluded from the
walk and bike graphs, while small local drawbridges (Gowanus, Newtown Creek,
City Island), whose sidewalks live on the roadway segment, stay.

One consequence: severing the Verrazzano makes Staten
Island's street network a separate component — which is true; the island has no
pedestrian link — so the graph keeps every component of 500+ nodes rather than
only the largest, which would have deleted the borough. (An earlier draft of
this build allowed walking to Staten Island over the Verrazzano; an adversarial
review caught it.)

## Ferries

Three operators, three feeds, and none of them is the Metropolitan Transportation Authority (MTA) — which is why an
earlier build of this map had no boats at all.

**NYC Ferry** contributes five boat routes across 25 landings: Astoria, East
River, South Brooklyn (which also calls at Governors Island), Rockaway-Soundview
and St. George. Two summer-only boats, the Governors Island shuttle and the
Rockaway Rocket express, are not in the fall schedule used here, so a summer
weekend map would show a little more ferry reach than this one. The feed also
carries two `route_type=3` routes — the free Rockaway East and Rockaway West
shuttle *buses* — so route kind is read from each route's GTFS `route_type`
rather than assumed from the feed. Labelling by feed would have called 25 bus
stops on the Rockaway peninsula "ferry landings".

Validation against the timetables: the East River route runs Wall St to Dumbo in
8 minutes and Dumbo to South Williamsburg in 10, on 12-to-26-minute headways at
the morning peak; Astoria runs every 36 to 45 and South Brooklyn every 45 to 60.
The outer routes' headways are long: from Red Hook, the ferry reaches Wall
Street in 36 minutes, 20 of them (the capped wait) spent waiting for a boat that
comes every 45.

**The Staten Island Railway** was already present — it arrives inside the MTA
subway feed as route `SIR`, all 21 stations from Tottenville to St George, and
is counted as rail alongside the subway.

## The Staten Island Ferry

The ferry is included, and it matters more than any other single line in the
system. It is published by the New York City Department of Transportation rather
than the MTA, which is why it lives in a separate feed and why it is easy to
miss: an earlier build of this map excluded it.

From the St George terminal on a weekday morning with a 60-minute budget:

| | Manhattan street reached | Manhattan subway stations reached |
|---|---|---|
| Without the ferry | ~0 | **none** |
| With the ferry | substantial | South Ferry, Bowling Green, Wall St, Chambers St, 14 St-Union Sq, Times Sq |

Staten Island has 27 SIM express bus routes to Manhattan over the Verrazzano,
so the borough was not literally unconnected — but on the schedules, none of
them delivers a rider from St George to a Manhattan subway station inside an
hour. Without the ferry the map effectively cut a borough of half a million
people off from the rest of the city. Readers would have taken that modelling
gap as a claim about Staten Island.

### Validation

The feed gives a 25-minute crossing, which is the real crossing. Headways per
direction come out at 16 to 18 minutes in the rush bands, 27 to 30 minutes
midday and evening, and 30 minutes overnight and at weekends. The published
timetable runs boats every 15 minutes at the height of the rush; the band
average includes its shoulders. A trip from St George works out as: walk to the terminal, wait 9
minutes (half of the 18-minute headway), cross for 25, reach Whitehall at 34
minutes, South Ferry station at 39, Times Square at 56.

Both terminals are fully accessible, so the ferry stays available in
accessibility mode. The ferry is also free, which this map does not model
because it does not model fares at all.

Note that the walk graph still treats Staten Island as a separate component —
correctly, since you cannot walk the Verrazzano. The ferry connects the
boroughs in the transit graph, not the pedestrian one.

## PATH, and why not the commuter railroads

PATH is included. The Long Island Rail Road (LIRR), Metro-North and New Jersey
Transit are not. What separates them is whether this map's wait model describes
the service accurately.

### The reason, measured

This map assumes you turn up without consulting a timetable and wait, on
average, half the headway. That is a fair description of how people use
frequent service and a false one for infrequent service: nobody strolls to a
station hoping to catch a train that comes once an hour. They read the
schedule and arrive three minutes before.

So the question for any railroad is whether it runs often enough that riders
turn up and go.

| | Median headway, weekday AM peak | Where the 20-minute wait cap binds |
|---|---|---|
| **PATH** | **3.0 min** (combined across its routes) | **0 of 11 stations** |
| LIRR | 60 min | 60% of stops |

PATH is a subway that happens to cross a river. Trains every three minutes at
Grove Street, every three at 33rd Street; the frequency model describes it
exactly as well as it describes the L. The LIRR is a different kind of thing:
the median stop gets three trains in a three-hour peak. Modelling it with
half-headway waits would produce a 20-minute wait (the cap) where the real
answer is close to zero for anyone who owns a watch — and no cap value fixes
it, because the right number depends on a departure time that a frequency
model has already thrown away.

Adding the commuter railroads properly means moving the router from
frequency-based to schedule-based search over timetables. That is worth
doing, and it would also repair the common-lines conservatism and the
branch-chaining optimism documented above, but it means rewriting the core
rather than adding a feed.

Three smaller reasons point the same way:

- **Streets.** PATH's seven New Jersey stations needed a walkable network, or
  you could ride the train but not leave the platform. The PATH corridor is
  small enough to take from OpenStreetMap (38,216 ways across Newark,
  Harrison, Jersey City and Hoboken). The LIRR and Metro-North catchments are
  the whole metropolitan area, which is a different data source, roughly five
  times the graph, and an architecture that no longer fits in a browser.
- **Fares.** Inside the city the local subway and bus fare is a flat $3.00, so
  ignoring fares is mostly defensible. PATH is close to it at $3.25. A commuter
  rail isochrone that says "Ronkonkoma in 45 minutes" is true and misleading at
  $21.50 one way at the peak.
  (Express buses, included here, are the one in-network exception at $7.25 —
  see below.)
- **Park and ride.** The real suburban trip is drive, park, then train. This
  router does not chain a car to a train, and the commuter railroads are
  mostly used that way.

### What PATH adds

Seven routes, 13 stations, and the west bank of the Hudson: Newark, Harrison,
Journal Square, Grove Street, Exchange Place, Newport and Hoboken join the map.
From Hoboken at the morning rush, the World Trade Center is 15 minutes away,
Times Square 26, Newark 35.

Walking still cannot cross the Hudson — from Hoboken the walk network reaches
about 16,000 nodes in New Jersey and exactly zero in Manhattan, which is
correct. PATH connects the two banks in the transit graph, not the pedestrian
one, exactly as the Staten Island Ferry connects St George to Whitehall.

PATH does not run the same service at all hours, and the map reflects it, because
headways are computed per line, per station, per time band from scheduled
departures. A line with no departures in a band is not boardable in that band.
The combined PATH headway at 33rd Street runs 3 minutes at the weekday peak, 6
midday, and 30 overnight; the set of lines that run changes too — four at the
weekday peak, and three on weekends in this (2025) feed. All of it comes
from counting the schedule band by band.

**The taxi mode deliberately stays inside New York City.** Its speeds
come from 11.9 million measured TLC trips, and the TLC regulates New York City
vehicles only. There is no equivalent free record of what traffic does
on the New Jersey Turnpike. Rather than route cars over New Jersey at posted
speeds — which would imply free-flowing highways precisely on the inbound
commute, the one trip where congestion decides everything — the car graph ends
at the city line. The New Jersey streets here are for walking to a PATH station.

### Staleness

The only published PATH static feed comes through Trillium, was last modified
in June 2025, and carries a validity window ending 2026-06-01 — which has
passed. We use it because it is the only GTFS PATH publishes, but its service dates
are 2025 ones and it is the least current input in this map. It predates
PATH's 2026 service increases: more weekday trains from March 15, and, since
May 17, all four lines on weekends from 10am to 9pm (the feed has three). Weekend
PATH reach here is therefore understated.

## Accessibility mode

The "I require accessible transit" toggle answers the same question for a rider
who cannot use stairs.

- **Subway and rail**: boarding and alighting are limited to listed accessible
  stations — 166 fully accessible and 8 accessible in one direction, of 496
  subway and Staten Island Railway stations, per the MTA's station file as of
  November 2026. Trains still ride through everything else. The 9 partial
  stations are treated as accessible in both directions, a small optimism noted
  here because GTFS direction ids do not map cleanly onto the MTA's north/south
  flags.
- **PATH**: nine of its thirteen stations are elevator-accessible — Newark,
  Harrison, Journal Square, Grove Street, Exchange Place, Newport, Hoboken, 33rd
  Street and World Trade Center, taken verbatim from
  [PANYNJ](https://www.panynj.gov/path/en/accessibility.html). The four Sixth
  Avenue stations in Manhattan (Christopher, 9th, 14th, 23rd) are not. PATH is a
  Port Authority system, absent from the MTA station file, so an earlier build
  silently marked every PATH station inaccessible and cut New Jersey off for
  accessible-transit riders. Jersey City, Newark and Hoboken are now reachable
  in accessibility mode.
- **Bus**: unchanged. The entire fleet has ramps or lifts.
- **Walking**: routed on the street network minus step streets — the
  stairs-free network.
- **Taxi/Uber**: becomes a wheelchair-accessible vehicle (WAV), and the clock
  starts at the request. The wait is measured: the TLC high-volume
  FHV file records request and pickup timestamps and a WAV flag for every
  Uber/Lyft trip in the city. Median request-to-pickup over March 2026, per
  band, runs 7.1 to 7.9 minutes (1,072 to 21,538 WAV requests per band),
  against 3.8 to 4.7 minutes for standard vehicles.
- **Access-A-Ride** is absent, deliberately: it must be booked by 5pm the day
  before, so it cannot appear in a map of where you can go from here, now. Its
  absence from a turn-up-and-go picture is itself a finding.

### Elevators that work only on paper

The accessible-station list is which stations *have* an elevator or ramp, not
which are working right now. A station whose single elevator is out of service
is, that day, not accessible — you can reach the mezzanine and no further. This
map cannot see that: it treats every listed station as accessible all the time,
so the accessible reach it shows is a best case, every elevator working at once.

The MTA publishes real-time [elevator and escalator
status](https://www.mta.info/elevator-escalator-status), and outages are common.
A live version of this map would subtract
out-of-service stations from the accessible set on each visit; this one does
not, and a rider planning a real trip should check that page.

## Station counts

The map counts 496 stations where the commonly cited figure is 472. Both are
correct. The 496 are the MTA station file's rows: 475 subway stations plus the
21 stations of the Staten Island Railway. The MTA's 472 counts subway stations
only, and the remaining handful of difference comes from stations the file
splits in two. Counting connected complexes once gives a smaller number again,
424.

## What this does not model

- **Delays.** These are scheduled times, and real trips run slower. This is the
  largest gap between the map and the city, and it runs one way.
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
- **Metro-North, Long Island Rail Road, New Jersey Transit.** Not included —
  see "PATH, and why not the commuter railroads" above for the reason, which is
  that this map's wait model would misdescribe them. PATH, both ferry systems
  and the Staten Island Railway are included.
- **Driving outside New York City.** The car graph ends at the city line
  because the traffic calibration does.

## Confidence

| Quantity | Confidence |
|---|---|
| Ride times | High. Medians of published schedules. |
| Headways and waits | High as scheduled. Standard practice, deliberately conservative. |
| Street routing | High. The city's own centerline file. |
| Taxi times | Moderate. Calibrated to real trips, one factor per borough and band; conservative on highways. |
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
python3 pipeline/build_access.py      # accessible stations + measured pickup waits
cp pipeline/out/{core.json,bands.bin,bands.json,street_nodes.bin,street_edges.bin,car_nodes.bin,car_edges.bin,car_calibration.json,car_calibration2.json,car_zones.bin,car_link.bin,access.json} data/
python3 pipeline/validate.py        # speed + headway checks quoted above
```

Copy all twelve files together. `car_zones.bin` and `car_link.bin` are indexed
by car-network node, so a new car network shipped with old copies of either
would attach traffic factors and race times to the wrong streets without any
error.

Total payload is 16.0 MB across twelve files, covering all seven time bands.

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

Service dates are chosen inside each feed's validity window (PATH's has expired;
see above): a representative
Wednesday, Saturday and Sunday, with `calendar_dates.txt` exceptions honoured.
"Representative" is measured: for each day kind the build counts scheduled trips
on that weekday across the next eight weeks and takes the first date with the
most common count, so a holiday or a holiday week is never chosen. This build
uses November 25, 28 and 29, 2026 for most feeds (December 2 for Brooklyn
weekday buses and December 5 for NYC Ferry's Saturday, where Thanksgiving week
differs). An earlier rule skipped any date with a calendar exception, but the
MTA bus feeds add a few trips on nearly every weekday, so it skipped every
ordinary Wednesday and would have landed on December 30, which runs about 12%
fewer buses.

## A note on the AI caution label

This map was built with heavy use of an AI coding assistant. The inputs are
authoritative and the outputs are validated against known quantities, but the code
joining them was largely machine-written. Treat it as a research sketch, not a trip
planner.
