# NYC Super Speeders — Methodology

Live companion to the [NYC Traffic Collisions deep dive](https://joshgreenman1973.github.io/experiments/nyc-collisions/). Every chart, counter, and map below is a live read from [NYC Open Data](https://data.cityofnewyork.us) via the Socrata Open Data API. No backend, no caching layer.

## Data sources

| # | Dataset | 4x4 ID | Role |
|---|---|---|---|
| 1 | Parking Violations Issued – Fiscal Year 2026 | [`pvqr-7yc4`](https://data.cityofnewyork.us/d/pvqr-7yc4) | **Primary.** Speed-camera rows isolated via `violation_code = 36` (equivalent to description `PHTO SCHOOL ZN SPEED VIOLATION`). Scope is NYC Fiscal Year 2026 (July 1, 2025 – June 30, 2026), the freshest live-updating dataset. Every metric on this page — top plates, DVAP cohort, escalation curves, hour/day patterns, map — starts here. |
| 2 | Motor Vehicle Collisions – Crashes | [`h9gi-nx95`](https://data.cityofnewyork.us/d/h9gi-nx95) | Cross-reference. Used in "Same Places, Same People" to compare camera-ticket density against pedestrian + cyclist killed/injured totals by borough (filtered to on-or-after July 1, 2025 to match the ticket window). |

## Definitions

- **Super speeder** — in this project, any plate with ≥15 school-zone speed-camera tickets during NYC Fiscal Year 2026 (the dataset's window). The DVAP statutory threshold is ≥15 in a rolling 12-month window; because pvqr-7yc4 is fiscal-year-scoped, FY2026 is a 12-month proxy that becomes an exact match as the fiscal year closes on June 30, 2026.
- **DVAP status** (on the plate lookup dossier) — Red: ≥15 FY2026 tickets (legally eligible for booting). Amber: 10–14 (approaching). Green: <10.
- **Window** — NYC Fiscal Year 2026, July 1, 2025 – June 30, 2026. Hero counters reflect live cumulative totals within that window.
- **Camera ticket** — a speed-camera citation issued by NYC DOT in a designated school zone. Does not include red-light camera citations (not in this v1) or NYPD officer-issued speed tickets.
- **Fine estimate** — `$50 × ticket count`. $50 is the statutory NYC school-zone speed-camera fine. This estimate does not account for late fees, judge dismissals, or unpaid balances.

## Filters and queries

Every panel's query is visible in the page source (`index.html`, search for `sodaGet(`). Key patterns:

```
# Wall of shame
$select=plate_id, registration_state, COUNT(*) as c
$where=violation_code=36
$group=plate_id, registration_state
$order=c DESC
$limit=50
```

```
# DVAP simulator — derived client-side from cached top-20k plate grouping
# (server-side $having on 3M rows is slow enough to time out the browser fetch)
$select=plate_id, COUNT(*) as c
$where=violation_code=36
$group=plate_id
$order=c DESC
$limit=20000
# then filter in JS: rows.filter(r => +r.c >= threshold)
```

## Calculations

- **Top-1% concentration** (Why Speed Kills panel): fetch the top 20,000 plates by FY2026 ticket count, sum the top 1% of the list, divide by the total ticket volume of those 20k plates. The denominator is "plates in the top 20k," not citywide, so the true citywide concentration is somewhat lower than reported — this is an acceptable over-estimate because the long tail of 1-ticket plates is dominated by one-time offenders who aren't the focus of the chart.
- **Insurance externality estimate** ($328 / NYC household / year): derived from NYC's average full-coverage auto premium ($~4,100/yr per Bankrate 2025) × an 8% allocation attributable to excess-speed-related claims. The 8% is a conservative estimate informed by NHTSA attribution of ~29% of traffic fatalities to speeding and the smaller proportional contribution of speeding to injury-only claims. This number is **an estimate**, not a statutory figure — it's intended as an order-of-magnitude illustration of the shared-cost externality.
- **Pedestrian fatality curve** (20/30/40/50 mph → ~10/40/80/95%): synthesis of AAA Foundation for Traffic Safety; Rosén & Sander, *Accident Analysis & Prevention* (2009); and the NHTSA/NACTO literature on impact-speed lethality. Not a NYC-specific measurement.
- **NYC registered vehicles ≈ 2,000,000**: used as DVAP-simulator denominator. Source: NYS DMV registration counts.

## Precinct centroids

The School Zone map plots camera-ticket totals at approximate NYPD precinct centroids (77 points, embedded in `index.html`). These are centroid approximations, not the exact camera locations. The source dataset does not carry lat/lng, only precinct + street-pair text. Future work: geocode the top 500 `(street_name, intersecting_street)` pairs into a static `intersections.json` for marker-level precision.

## Known limitations

1. **Camera coverage is school-zone-only.** A plate with zero speed-camera tickets is not necessarily a safe driver — it may simply not have passed a camera at a speed worth capturing. Speed cameras cover a subset of NYC roadways, so this is a floor on observed speeding, not a ceiling.
2. **Plate-level, not driver-level.** The data identifies the vehicle's registered owner's plate, not the person driving at the time of the ticket. A family-shared vehicle, a rental, or a fleet car may have multiple drivers contributing to a single plate's record.
3. **Full plates are displayed.** License plates are public record and have been published previously by Transportation Alternatives, Streetsblog, and NYC DOF's public violation-lookup tool. This project follows that precedent. If your plate appears and you believe it shouldn't, the data flows directly from the DOF record — disputes should be directed to NYC DOF.
4. **Fine totals don't reflect payment status.** The $50 × count is statutory gross, not outstanding balance. A dedicated paid/unpaid overlay querying per-ticket payment status is a v2 feature.
5. **Aug 1, 2022 inflection.** Speed cameras were legally limited to school hours until this date, after which they run 24/7. The FY2026 dataset is entirely post-inflection, so this matters only for context, not for in-scope comparisons.
6. **Null `issue_date` in pvqr-7yc4.** Roughly 58% of rows in pvqr-7yc4 (about 1.77M of 3M speed-camera rows as of this writing) have a null `issue_date`. Counts and groupings (Wall of Shame, DVAP cohort, concentration math) use the full 3M row population, but anything time-indexed (escalation curves, monthly trend, day-of-week, hour histogram, "data through" timestamp) applies a `WHERE issue_date IS NOT NULL` filter and therefore runs on the dated subset.
7. **Borough-level cross-reference.** The "Same Places, Same People" scatter is at borough granularity (5 points) because the crashes dataset carries borough but the camera-violations dataset's lat/lng is absent. A precinct-level version would require a client-side spatial join of crash lat/lng to precinct polygons.
8. **Auto-refresh cadence.** The page re-queries the hero counters and Wall of Shame every 5 minutes. Heavier panels (escalation curves, temporal patterns) are loaded once per page visit to avoid unnecessary API calls.

## References

- Transportation Alternatives + Families for Safe Streets, *Super Speeders* (Feb 2026): https://transalt.org/press-releases/like-shooting-a-gun-into-a-crowd-just-10-drivers-threaten-25-million-new-yorkers-according-to-new-data-from-transportation-alternatives-and-families-for-safe-streets
- Streetsblog NYC, *To Protect and Swerve: NYPD Cop Has 527 Speeding Tickets Yet Remains on the Force* (Apr 23, 2026): https://nyc.streetsblog.org/2026/04/23/to-protect-and-swerve-nypd-cop-has-527-speeding-tickets-yet-remains-on-the-force
- NYC Local Law 5 of 2020 — Dangerous Vehicle Abatement Program.
- NHTSA — Speeding and Traffic Fatalities fact sheets.
- AAA Foundation for Traffic Safety — *Impact Speed and a Pedestrian's Risk of Severe Injury or Death*.
- Rosén E., Sander U. (2009). *Pedestrian fatality risk as a function of car impact speed*. Accident Analysis & Prevention.
- Bankrate, *Average cost of car insurance in New York* (2025 update).
