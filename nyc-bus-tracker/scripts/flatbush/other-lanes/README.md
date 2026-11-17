# Bus speeds on NYC bus lane and busway projects, 2023 to October 2026

What this measures: whether weekday bus speeds on the street segments where bus lanes or busways were finished changed after the work, using the MTA's own Bus Route Segment Speeds data (data.ny.gov 58t6-89vi for 2023-24 and kufs-yh3x for 2025 to October 2026). It shows association, not cause. Weather, traffic, congestion pricing, service changes and route redesigns all move speeds too. The control comparison takes out some of that, not all of it.

## Method

Data. One row per route, direction, timepoint-to-timepoint segment, month, weekday and hour, with road distance, average travel time and trip count. Weekdays only (`mta_seg.py`).

Corridors (`build_corridors.py`). Projects 1-11 use the NYC DOT bus lane features (Open Data ycrg-ses3, copy in `../buslanes.csv`) whose open date matches the project. Projects 12-15 are newer than that file, so each corridor is the current MTA GTFS shape of a route that runs there, clipped between the two cross streets (points in `projects.py`). Each feature keeps its travel direction (NB/SB/EB/WB), so a one-way lane only counts buses going that way.

Segments (`build_segments.py`). MTA segments run between timepoints, often a mile or more apart, so they rarely line up with a project. Each segment gets a street path: the route's GTFS shape between the two timepoint stops, picking the slice whose length best matches MTA's road distance (982 of 1,032 segments). If no shape of that route fits, any GTFS shape that fits is used (20), and failing that a straight line (30). Only three straight-line segments enter any result, all in the Pelham Pkwy control and far from any corridor. The path is cut into 10 m pieces. A piece counts as on the corridor if it is within 60 m of a corridor feature that runs parallel to it in the same direction. The overlap share is the on-corridor length divided by the segment length.

- Corridor segments: the project's routes, at least 50% overlap.
- Control segments: the same routes (those that supplied corridor segments), under 10% overlap with every project corridor and with every other DOT bus lane dated 2023 or later.

Speed. Weekday hours 7 through 18 (7 a.m. to 7 p.m.), trip-weighted: sum(road_distance × trips) / sum(travel_time × trips / 60). Peak is hours 7-9 and 16-18 (7-10 a.m. and 4-7 p.m.); PM peak is hours 16-18.

Before and after (`analyze.py`). After months are up to 12 full months starting the month after opening, through October 2026. Each after month is paired with the same calendar month one year earlier. If that month falls in or after the construction month (or the opening month, when the construction start is unknown), the pair goes back two years. If that is before January 2023, the pair is dropped and listed in the flags.

Matching. Within each month pair, a segment counts only if the same stretch has data in both months. "Same stretch" means same route and direction, with start and end stops each within 150 m, which survives MTA renumbering stop IDs. When MTA re-cut timepoints (for example one segment split into two), a chain of up to three consecutive segments on one side can match a single segment on the other with the same ends. Path check: a match is dropped if the trip-weighted road distance differs by more than 3% between the two months.

Difference-in-differences. Corridor change minus control change, both in mph over the same month pairs. `did_month_pairs` repeats the calculation for each month pair on its own and reports how many were positive and the spread. Treat that spread as a floor on the uncertainty, since months within one year are not independent.

Monthly series. Corridor and control speeds for every month from January 2023 to October 2026, using the segments that entered the comparison. `corridorSegmentMiles` shows when segments drop in or out because MTA re-cut timepoints, so the chart's levels can shift for reasons unrelated to the street.

## Results

All figures are weekday, 7 a.m. to 7 p.m., trip-weighted. "Pts" means percentage points of corridor change minus control change.

| # | Project | Opened | Before → after mph | Change | Peak change | Control change | Diff-in-diff | Month pairs (after) | Corridor covered |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Northern Blvd, Broadway to 114th St | 2023-08-08 | 6.198 → 6.212 | +0.014 mph (+0.23%) | -1.15% | -0.209 mph (-2.88%) | +0.223 mph (+3.11 pts); 7/7 pairs positive | 7 (2024-01 to 2024-07) | 62% |
| 2 | E Gun Hill Rd, Bainbridge Ave to Bartow Ave | 2023-10-31 | 6.651 → 6.643 | -0.008 mph (-0.12%) | -0.51% | -0.030 mph (-0.40%) | +0.022 mph (+0.28 pts); 2/4 pairs positive | 4 (2024-01 to 2024-04) | 81% |
| 3 | 3rd Ave, E 59th to E 96th St (northbound) | 2023-12-07 | 4.921 → 5.126 | +0.206 mph (+4.18%) | +3.58% | -0.025 mph (-0.48%) | +0.231 mph (+4.66 pts); 6/6 pairs positive | 6 (2024-01 to 2024-06) | 78% |
| 4 | Livingston St, Boerum Pl to Flatbush Ave | 2024-01-10 | 4.440 → 4.448 | +0.008 mph (+0.18%) | -0.97% | +0.012 mph (+0.21%) | -0.004 mph (-0.03 pts); 3/10 pairs positive | 10 (2024-02 to 2025-01) | 100% |
| 5 | University Ave (north segment) | 2023-12-01 | 6.303 → 6.396 | +0.094 mph (+1.49%) | +1.20% | -0.170 mph (-2.39%) | +0.264 mph (+3.88 pts); 11/11 pairs positive | 11 (2024-01 to 2024-11) | 90% |
| 6 | Pelham Pkwy, Boston Rd to Stillwell Ave (westbound) | 2023-12-27 | 10.703 → 10.306 | -0.397 mph (-3.71%) | -4.17% | +0.069 mph (+0.96%) | -0.466 mph (-4.67 pts); 0/8 pairs positive | 8 (2024-04 to 2024-11) | 76% |
| 7 | 2nd Ave, E 59th St to Houston St (southbound) | 2024-12-05 | 5.819 → 6.019 | +0.200 mph (+3.43%) | +3.95% | +0.113 mph (+1.66%) | +0.087 mph (+1.77 pts); 10/12 pairs positive | 12 (2025-01 to 2025-12) | 100% |
| 8 | 96th St, West End Ave to CPW and Madison Ave to 2nd Ave | 2024-11-27 | 4.136 → 4.357 | +0.221 mph (+5.34%) | +6.19% | +0.109 mph (+1.58%) | +0.112 mph (+3.76 pts); 8/12 pairs positive | 12 (2024-12 to 2025-11) | 92% |
| 9 | 3rd Ave, E 96th to E 128th St (northbound) | 2025-08-04 | 5.366 → 5.537 | +0.172 mph (+3.20%) | +3.42% | +0.030 mph (+0.58%) | +0.142 mph (+2.62 pts); 9/12 pairs positive | 12 (2025-09 to 2026-08) | 99% |
| 10 | Hillside Ave, 139th St to Springfield Blvd | 2025-09-15 | 7.412 → 8.442 | +1.030 mph (+13.90%) | +13.74% | +0.411 mph (+4.73%) | +0.619 mph (+9.17 pts); 12/12 pairs positive | 12 (2025-10 to 2026-09) | 100% |
| 11 | Flatbush Ave phase 1, Livingston St to State St | 2025-10-02 | not measurable | — | — | — | — | 0 | 0% |
| 12 | Madison Ave, E 23rd to E 42nd St (double bus lanes) | 2026-07-07 | 5.469 → 5.831 | +0.361 mph (+6.61%) | +5.38% | -0.053 mph (-0.58%) | +0.414 mph (+7.19 pts); 3/3 pairs positive | 3 (2026-08 to 2026-10) | 100% |
| 13 | Lexington Ave, E 52nd to E 60th St (southbound) | 2026-07-07 | not measurable | — | — | — | — | 0 | 0% |
| 14 | Broadway, 69th St to Roosevelt Ave (eastbound center lane) | June 2026 | not measurable | — | — | — | — | 0 | 0% |
| 15 | Tremont Ave busway (EB Third Ave-Southern Blvd, WB Southern Blvd-Belmont Ave) | 2026-09-19 | not measurable | — | — | — | — | 0 | 0% |

"Corridor covered" is the share of the corridor's length (each direction counted separately) that the matched segments run along.

## Against the city's claims

- 3rd Ave, 59th to 96th St. DOT said "up to 14%" faster in the PM peak. Here the PM peak rose 4.9% (4.911 to 5.152 mph) and the full day 4.2%, January to June 2024 against the same months of 2023. "Up to" usually refers to the best stretch or hour, so the two figures aren't directly comparable.
- Hillside Ave. DOT and MTA said "up to 28%". Here the full day rose 13.9% and the PM peak 17.9%. Most of the gap from 28% fits an "up to" claim, but the Queens bus network redesign happened at the same time (see caveats).
- Lexington Ave, 52nd to 60th St (2026). The 2019 Lexington lanes were reported at 26%. This project can't be measured: the nearest segment, Lexington from 59th to 42nd St, is 46% on the corridor. That segment went from 4.316 to 4.193 mph (-2.84%, August to October 2026 against 2025), but it isn't a reading of the project.
- Madison Ave, 23rd to 42nd St, against Fifth Ave's double lanes (6-12% for local buses). Local buses here (M1, M2, M3, whose segments are only 52% on the corridor) rose 5.55%. All routes together rose 6.61%. This is only three months.

## Caveats by project

1. Northern Blvd. Construction start unknown, so before months are January to July 2023 and after months are January to July 2024 only. The control is just two other Q66 segments (5.4 mi). The PM peak fell 3.7% while the full day was flat. The express routes (QM2, QM20, QM32) have no segment with half its length on the corridor. Q66 timepoints were re-cut in April 2024 and June 2025, so the monthly series covers less of the corridor after mid-2025.
2. Gun Hill Rd. Construction began May 17, 2023, so only January to April 2023 can serve as before months: four pairs. No measurable change.
3. 3rd Ave, 59th to 96th St. Only the 67th-to-97th St segment of the M101, M102 and M103 qualifies, so 59th to 67th St is not covered. Six month pairs (January to June). The construction months July to December 2023 have no clean before month.
4. Livingston St. Opening is taken as the January 10, 2024 completion announcement, and before months stop at October 2023. The B41's segments through here (48% and 41% on the corridor) fall just short of the 50% cut, so the result rests on the B45 and B67 only. No measurable change.
5. University Ave. Only the Bx3 runs here. The control is small (4 segments, 4.3 mi). The corridor gained and the control lost, so the diff-in-diff (+0.26 mph) is larger than the raw change (+0.09 mph).
6. Pelham Pkwy. Only one segment qualifies: the Bx12 local westbound, Eastchester Rd to White Plains Rd. The Bx12 SBS segments are too long. Its road distance changed in April 2023, so January to March pairs fail the path check. Buses on this segment got slower in all eight month pairs, against a flat control.
7. 2nd Ave. Congestion pricing began January 5, 2025. Every after month is post-pricing and every before month pre-pricing, and the corridor is inside the zone while much of the control (the M15 north of 60th St) is not. So the +0.09 mph diff-in-diff could be lanes, pricing or both. Before months for June to December come from 2023. The M15 SBS segment (4.9 mi, 52% on the corridor) carries much of the weight. M15 local +1.5%, M15 SBS +4.4%.
8. 96th St. The control is small (9 segments, 5.5 mi). The month-pair results range from -0.38 to +0.66 mph, and 8 of 12 are positive.
9. 3rd Ave, 96th to 128th St. Construction start unknown. One before month (August 2024) comes from two years back.
10. Hillside Ave. Strongest result and the most confounded. The Queens bus network redesign re-cut these routes and their stops in summer 2025: new timepoint patterns appear in the MTA data from June 2025. All after months are post-redesign; most before months are pre-redesign. Fewer stops alone can raise speeds. The same-route control rose 4.7%, which takes out the network-wide part but not any stop changes concentrated on Hillside. 618 corridor segment-months had no counterpart across the redesign and were left out, and 56 of 96 corridor segments were used. Every route in the mix rose: Q43 +19.8%, Q77 +14.5%, Q17 +12.7%, Q36 +10.7%, Q76 +7.8%, Q1 +5.6%. Local routes only: +13.75%.
11. Flatbush Ave phase 1. Not measurable. The project is about 250 m of Flatbush Ave in each direction and the nearest segments (B45 and B67, Livingston/Smith to Atlantic/Flatbush) are about 30% on it. A diagnostic run on those segments (`diagnosticLowOverlap`, not a corridor figure) shows +6.61%, November 2025 to October 2026 against a year earlier. They also run on Livingston St and other streets.
12. Madison Ave. Only three months (August to October 2026). The segments mostly on Madison between 23rd and 42nd St (X27, X28, X37, X38, SIM4C, SIM33C, BXM18; 81-100% on the corridor) rose 9-20%. The segments only about half on it (M1-M3, BXM6-BXM10) rose 4-7%. That pattern is consistent with a corridor effect, but three months is thin. Express buses make up 90% of control miles, mostly highway; a local-only control gives a similar diff-in-diff (+0.40 mph). The brief calls these lanes southbound, but Madison is one-way northbound, so the corridor is direction-free.
13. Lexington Ave. Not measurable (see above).
14. Broadway, Queens. Not measurable. The eastbound lane is about 440 m. The Q70 SBS segment that uses it runs 4.5 mi from LaGuardia to Woodside, of which 8% is on the corridor. The install date ("June 2026") is approximate.
15. Tremont Ave busway. Not measurable. The busway is about half a mile, and the Bx36 segments through it are 2.5-2.6 mi long (26% and 19% on the corridor). Diagnostic only: the eastbound segment went from 5.029 to 5.156 mph (+2.53%), October 2026 against October 2025.

## General limits

- Timepoint segments blur any effect: a corridor segment can be up to half off the project, and the off-project part dilutes the change.
- The control is the same routes off the corridor. It absorbs citywide and route-level shifts, not changes specific to the treated street (signal retiming, construction, enforcement, stop changes).
- Most comparisons span one year, so a single unusual month (weather, a detour) can move a pair. The per-pair spread is in `results.json`.
- Segment paths come from the current (November 2026) GTFS. Where a 2023 routing differed, the match to road distance usually caught it, but overlap shares for old patterns are approximate.

## Files

- `run.sh`: order of steps
- `mta_seg.py`: downloads route CSVs into `mta/` (routes already in `../mta` are reused)
- `projects.py`: project dates, routes, corridor definitions and context notes
- `geo.py`, `gtfs_lib.py`: geometry and GTFS helpers
- `build_corridors.py`: writes `corridors.json` and `corridors.geojson`
- `build_segments.py`: writes `segments.csv` and `segments.geojson` (every segment's path, overlap share with each corridor, months present)
- `analyze.py`: writes `results.json`
- `make_table.py`: writes `table.md`

Inputs outside this folder: `../buslanes.csv`, `../gtfs/{b,m,bx}` (MTA GTFS), and `../mta/*.csv` for B41, B45, B67, B103, M1-M4, M101-M103, BX12, BX12+ and BX36. The Queens, MTA Bus and Staten Island GTFS feeds are in `gtfs/`.
