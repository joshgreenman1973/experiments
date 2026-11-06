# Methodology: Where you can sit down (`nyc-where-to-sit`)

Version 2, Nov. 6, 2026. Rebuild with `python3 build_data.py` (add `--fetch` to re-download the sources).

## Sources (NYC Open Data, fetched Nov. 6, 2026)

| Dataset | ID | Used |
|---|---|---|
| Department of Transportation seating locations (CityBench benches and leaning bars) | [`esmy-s8q5`](https://data.cityofnewyork.us/Transportation/Seating-Locations/esmy-s8q5) | 5,776 records |
| Privately owned public spaces (Department of City Planning) | [`rvih-nhyn`](https://data.cityofnewyork.us/d/rvih-nhyn) | 217 of 392 with required seating |
| Pedestrian plazas (Department of Transportation) | [`5dck-9m6g`](https://data.cityofnewyork.us/d/5dck-9m6g) | 90 plaza points |
| Bus stop shelters (Department of Transportation) | [`t4f2-8md7`](https://data.cityofnewyork.us/d/t4f2-8md7) | 3,312 |
| Parks properties | [`enfh-gkve`](https://data.cityofnewyork.us/d/enfh-gkve) | 1,433 polygons |
| 2020 Neighborhood Tabulation Areas with 2020 census population, clipped to the shoreline | `raw/nta2020_clipped.geojson` | 197 residential neighborhoods |

**DOT bench types** (`subtype` field): backed 2,160 (Backed 1.0: 1,194; Backed 2.0: 938; World's Fair: 28, assumed backed), backless 2,160 (Backless 2.0: 1,636; Backless 1.0: 524), leaning bar 558, unknown bench 21, blank 877. The installation year is the year in the site ID (`SEAT.YYYY…`). DOT's own seating page describes "over 2,600 benches and leaning bars," well under the 5,776 records in the dataset; the dataset is used as published.

**Parks** count as seating only for types where benches are close to certain: neighborhood parks, playgrounds, jointly operated playgrounds, community parks, flagship parks, triangles and plazas, malls, waterfront facilities, historic house parks and recreational fields and courts. Gardens, nature areas, strips, parkways, undeveloped land, cemeteries, lots and operations sites are left out.

## The three measures

- **Street seat:** a DOT bench (any type except leaning bar), a privately owned public space with required seating, or a DOT plaza.
- **Backed bench:** a DOT bench recorded as backed.
- **Any seat:** a street seat, a bus shelter (most have a bench), or the edge of an eligible park (sampled every 25 meters; anywhere inside the park counts as zero minutes).

## Walking time

The city is divided into 60-meter cells. Each cell gets the straight-line distance to the nearest seat of each kind, multiplied by 1.25 for the street grid and converted at 3 mph (25 minutes per straight-line mile). The page offers 2 mph as an alternative. For reference, the federal traffic-signal manual times crossings at 3.5 feet per second, about 2.4 mph, and the U.K. Department for Transport's Inclusive Mobility guidance recommends seats every 50 meters on pedestrian routes.

"Lived-in land" is any cell in a residential neighborhood (Neighborhood Tabulation Area type 0) outside a park. Shares are shares of that land, not of people.

## Results

| | Median minutes | Beyond 5 minutes | Beyond 10 minutes |
|---|---|---|---|
| Any seat | 2.3 | 18.3% | 4.5% |
| Street seat | 4.1 | 42.0% | 17.6% |
| Backed bench | 6.5 | 61.7% | 30.1% |

Staten Island has the most lived-in land beyond 5 minutes: 47.3 percent for any seat, 75.7 percent for a street seat and 87.5 percent for a backed bench. Manhattan has 0.9 percent beyond 5 minutes for any seat.

**The shift from backed benches.** Of DOT installs from 2012 to 2016 with a recorded type, 68.9 percent were backed (1,116 of 1,620). From 2023 to 2026 it was 24.0 percent (599 of 2,497). Another 877 installs from 2023 to 2026 have no type recorded (191 in 2023, 50 in 2024, 261 in 2025 and 375 in 2026); if every one were backed, the backed share would still be 43.7 percent.

## Changes from version 1

Version 1 left out bus shelters and parks; said 877 recent benches were missing both a type and a date when about 600 more had a type but no date; listed the wrong breakdown of the 877 by year; counted 177 residential neighborhoods instead of 197; offered a "zero backed benches" filter that matched no neighborhood; gave the wrong mix of seats for Midtown–Times Square; described plazas as polygons when they are points; called leaning bars "angled" with no source; and used three different citywide totals.

## Limits

Locations are as published and are not ground-truthed. Straight-line distance times a detour factor is an approximation of a walking route. Privately owned public spaces can close or restrict hours. Bus shelter benches are assumed, not recorded.

## Files

`raw/nta2020_clipped.geojson` is kept in the repository because the build needs it; the other raw downloads are re-created by `--fetch`.
