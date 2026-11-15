# Street pace: methodology

Built Nov. 15, 2026.

## Sources

| What | Where | Notes |
|---|---|---|
| E-ZPass reader speeds | NYC Open Data, "EZ Pass Readers" one file per year: 2021 [s7y8-dkgd](https://data.cityofnewyork.us/d/s7y8-dkgd), 2022 [2dzd-mqxq](https://data.cityofnewyork.us/d/2dzd-mqxq), 2023 [pi8f-savx](https://data.cityofnewyork.us/d/pi8f-savx), 2024 [7ank-n7rd](https://data.cityofnewyork.us/d/7ank-n7rd), 2025 [5dxh-vk2s](https://data.cityofnewyork.us/d/5dxh-vk2s), 2026 [6a2s-2t65](https://data.cityofnewyork.us/d/6a2s-2t65) | Department of Transportation. All six posted Sept. 24, 2026. The 2021 file starts April 8, 2021. The 2026 file updates daily. |
| Congestion zone | MTA Central Business District Geofence, data.ny.gov [srxy-5nxn](https://data.ny.gov/d/srxy-5nxn) | Manhattan south of and including 60th Street, minus the FDR Drive, the West Side Highway and the Battery Park Underpass. |

Each source row is one link (a pair of readers, usually one direction over a few blocks) and carries `sid`, `link_name`, `borough`, an encoded `polyline`, `link_length_ft`, `aggregation_period_sec`, `n_samples`, `median_calculation_timestamp`, `median_tt_sec` and `median_speed_fps`. Rows arrive about once a minute per link; each is the median over the previous 15 minutes. The same 351 links, with the same names and shapes, appear in every year's file.

## Steps

1. **`build/fetch_days.py`** queries each day separately (Socrata times out on longer windows) and keeps:
   - `aggregation_period_sec = 900` (rows with 0 have no reading; in October 2026 they were 45% of all rows),
   - `0 < median_speed_fps < 100`,
   - `n_samples >= 3`,
   and returns, per link and hour, the average of `median_speed_fps`, the average of `median_tt_sec` and the row count. One file per UTC day in `~/.vital-city/street-pace/raw/`.
2. **Time zone, and a switch.** Through May 16, 2025, timestamps are UTC: the fastest hour of the night falls at 8 UTC in summer and 9 UTC in winter, which is 4 a.m. in New York either way. The source has **no rows at all from May 16 to June 30, 2025** (checked with a daily count against the 2025 file). When the feed resumed June 30, 2025, the fastest hour sits at 4 in every month, summer and winter, so the stamps are New York local time from then on. `build/analyze.py` converts pre-outage UTC day-hours to local time with `zoneinfo` and uses later rows as published. Treating the later rows as UTC would have shifted 2025 and 2026 daytime averages by four or five hours.
3. **Day types.** Weekdays are Monday to Friday minus federal holidays (observed dates), the day after Thanksgiving and Christmas Eve. Weekends are Saturday and Sunday. Holidays are left out of both.
4. **Speeds.** mph = feet per second × 3,600 / 5,280. Every link-hour-day cell counts once.
5. **Map profiles.** For each link, year (Feb. 1 to Oct. 31 of 2022 through 2026, minus May 16 to June 30 in every year to match the 2025 outage), day type and local hour: the mean of the daily cells, shown only when 20 or more days stand behind it.
6. **Zone.** A link is in the zone when the midpoint of its decoded polyline falls inside the geofence.
7. **Year comparison.** A link's weekday daytime speed is the mean of its 12 hourly values from 7 a.m. to 7 p.m. Comparisons use only links that have all 12 values in 2024, 2025 and 2026, so each year averages the same streets. Group figures are simple means across links.
8. **Monthly chart.** Mean weekday 7 a.m. to 7 p.m. speed per link per month, requiring at least eight weekdays with data. Lines average a fixed set of links that have a value in at least 90% of months.

## Results

See `data/summary.json`. The figures on the page are read from that file when it loads.

Weekday mph, 7 a.m. to 7 p.m., Feb. 1 to Oct. 31 minus May 16 to June 30, data through 2026-11-14. Segments = links with all 12 daytime hourly values in 2024, 2025 and 2026; the 2022 and 2023 columns average whichever of those links have values in that year.

| Group | Segments | 2022 | 2023 | 2024 | 2025 | 2026 | 2025 vs 2024 | 2026 vs 2024 | Faster in 2025 |
|---|---|---|---|---|---|---|---|---|---|
| Inside the zone (Midtown) | 136 | 9.02 | 8.27 | 7.83 | 8.05 | 7.46 | +2.8% | -4.7% | 74 |
| Manhattan outside the zone | 18 | 10.86 | 10.29 | 10.29 | 11.03 | 10.96 | +7.2% | +6.5% | 9 |
| Queens, Brooklyn, Staten Island | 134 | 18.6 | 17.94 | 17.32 | 16.11 | 16.03 | -7.0% | -7.5% | 43 |
| All measured segments | 288 | 13.59 | 12.91 | 12.4 | 11.99 | 11.67 | -3.3% | -5.9% | 126 |

## Limitations

- Only vehicles carrying E-ZPass tags are timed, and only between reader pairs. Speeds on the measured links do not describe every street.
- The 351 links lean heavily to Midtown Manhattan (152 inside the zone, all between 14th and 57th streets). Nothing below 14th Street is measured, so the zone figures are Midtown figures.
- A link on 57th Street or 60th Street sits on or near the zone edge; the midpoint test decides.
- Many things changed at once in 2025: tolls, bus and bike lanes, signal timing, construction, deliveries and the economy. Comparing zone links with links elsewhere helps but does not isolate the toll's effect.
- A median over 15 minutes with as few as three vehicles can swing. Averaging over hours and months smooths it, but single link-hours in quiet periods can be noisy.
- The monthly chart's January values run about 1 mph above December's in every year, so month-to-month changes around the start of tolls are mostly seasonal. The page compares the same months year over year instead.
- The number of links reporting fell from about 320 a day in early 2024 to about 250 by late 2025. Comparisons hold the set of links fixed.
