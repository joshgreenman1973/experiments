# Street pace: methodology

Built Nov. 15, 2026.

## Sources

| What | Where | Notes |
|---|---|---|
| E-ZPass reader speeds | NYC Open Data, "EZ Pass Readers" one file per year: 2021 [s7y8-dkgd](https://data.cityofnewyork.us/d/s7y8-dkgd), 2022 [2dzd-mqxq](https://data.cityofnewyork.us/d/2dzd-mqxq), 2023 [pi8f-savx](https://data.cityofnewyork.us/d/pi8f-savx), 2024 [7ank-n7rd](https://data.cityofnewyork.us/d/7ank-n7rd), 2025 [5dxh-vk2s](https://data.cityofnewyork.us/d/5dxh-vk2s), 2026 [6a2s-2t65](https://data.cityofnewyork.us/d/6a2s-2t65) | Department of Transportation. All six created Sept. 24, 2026; the 2021 file was published Sept. 28 and the rest Oct. 3. The 2021 file starts April 8, 2021. The 2026 file updates daily. |
| Congestion zone | MTA Central Business District Geofence, data.ny.gov [srxy-5nxn](https://data.ny.gov/d/srxy-5nxn) | Seven polygons (Manhattan plus small waterfront pieces), all used. Manhattan south of and including 60th Street, minus the FDR Drive, the West Side Highway and the Battery Park Underpass. |

Each source row is one link (a pair of readers, usually one direction over a few blocks) and carries `sid`, `link_name`, `borough`, an encoded `polyline`, `link_length_ft`, `aggregation_period_sec`, `n_samples`, `median_calculation_timestamp`, `median_tt_sec` and `median_speed_fps`. Rows arrive about once a minute per link; each is the median over the previous 15 minutes. The same 351 links, with the same names and shapes, appear in every year's file.

## Steps

1. **`build/fetch_days.py`** queries each day separately (Socrata times out on longer windows) and keeps:
   - `aggregation_period_sec = 900` (the field takes only 0 and 900; rows with 0 have no reading. They were 20% of rows on Oct. 11, 2022, 30% on Oct. 8, 2024, and 44% to 47% on sampled days in October 2026),
   - `0 < median_speed_fps < 100`,
   - `n_samples >= 3`,
   and returns, per link and hour, the average of `median_speed_fps`, the average of `median_tt_sec` and the row count. One file per UTC day in `~/.vital-city/street-pace/raw/`.
2. **Time zone, and a switch.** Through May 16, 2025, timestamps are UTC: the fastest hour of the night falls at 8 UTC in summer and 9 UTC in winter, which is 4 a.m. in New York either way. The source has **no rows at all from May 16 to June 30, 2025** (last row 2025-05-16 14:29 UTC; first row back 2025-06-30 14:00 local; daily counts are zero from May 17 to June 29) (checked with a daily count against the 2025 file). When the feed resumed June 30, 2025, the fastest hour sits at 4 in every month, summer and winter, so the stamps are New York local time from then on. `build/analyze.py` converts pre-outage UTC day-hours to local time with `zoneinfo` and uses later rows as published. Treating the later rows as UTC would have shifted 2025 and 2026 daytime averages by four or five hours.
3. **Day types.** Weekdays are Monday to Friday minus federal holidays (observed dates), the day after Thanksgiving and Christmas Eve. Weekends are Saturday and Sunday. Holidays are left out of both.
4. **Speeds.** mph = feet per second × 3,600 / 5,280. Every link-hour-day cell counts once.
5. **Map profiles.** For each link, year (Feb. 1 to Oct. 31 of 2022 through 2026, minus May 16 to June 30 in every year to match the 2025 outage), day type and local hour: the mean of the daily cells, shown only when 20 or more days stand behind it.
6. **Zone.** A link is in the zone when the midpoint of its decoded polyline falls inside the geofence. A link whose midpoint is outside but 5% or more of whose length (measured in state-plane feet) is inside is an **edge** link and is left out of both sides of every comparison: the two Williamsburg Bridge links (38% inside; the westbound one ends at a toll entry) and five southbound avenue links from 72nd to 57th Street (21% to 25% inside).
6a. **Suspect links.** Some links show long steps that look like reader faults, not traffic (Woodhaven Blvd northbound falls from about 12 mph to about 1 from December 2024 on; Belt Pkwy eastbound, 68th St to Bay 8th, drops from about 40 to about 10 mph for a year and returns). A link is set aside when either:
   - its monthly weekday 7 a.m.–7 p.m. speed is at a third or less, or three times or more, of its own median month for six or more consecutive months with data, or
   - 10% or more of its full-window readings on sampled days (the 8th and 22nd of every month, Feb. 2022 to Nov. 2026; `build/fetch_overcap.py`) are at or above the 100 fps cap. For those links the cap cuts off real fast readings and leaves only the slow tail. Six links: both Henry Hudson Parkway links (82% and 84%), Belt Pkwy between Cross Bay Blvd and Pennsylvania Ave both ways (66% and 69%), and Jackie Robinson Pkwy both ways (15% and 56%).
   The rule sets aside 29 links (listed in `summary.json` under `suspect`, with the reason). It is a judgment call; the sensitivity table below shows results under other rules.
7. **Year comparison.** A link's weekday daytime speed is the mean of its 12 hourly values from 7 a.m. to 7 p.m., computed from unrounded hourly means. Comparisons use only links that have all 12 values in 2024, 2025 and 2026 and are neither edge nor suspect links, so each year averages the same streets (the days behind each year can still differ within a link). Group figures are simple means across links. Because a few links can still pull a mean, the page also reports the **median link's percent change**.
7a. **Seasons.** The same comparison run separately for Feb. 1 to May 15 and July 1 to Oct. 31, each requiring all 12 daytime hours in that season in all three years.
8. **Monthly chart.** Mean weekday 7 a.m. to 7 p.m. speed per link per month, requiring at least eight weekdays with data. Lines average a fixed set of links that have a value in at least 90% of months, excluding edge and suspect links.

## Results

See `data/summary.json`. The figures on the page are read from that file when it loads.

Weekday mph, 7 a.m. to 7 p.m., Feb. 1 to Oct. 31 minus May 16 to June 30, data through 2026-11-14. Segments = links with all 12 daytime hourly values in 2024, 2025 and 2026, excluding edge and suspect links; the 2022 and 2023 columns average whichever of those links have values in that year.

| Group | Segments | 2022 | 2023 | 2024 | 2025 | 2026 | 2025 vs 2024 (mean) | 2025 vs 2024 (median link) | 2026 vs 2024 (mean) | 2026 vs 2024 (median link) | Faster in 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Inside the zone | 128 | 9.15 | 8.44 | 8.01 | 8.30 | 7.61 | +3.6% | +4.1% | -5.0% | -3.6% | 73 |
| Manhattan outside the zone (Upper East and West Sides, 72nd to 96th) | 11 | 9.82 | 9.46 | 9.62 | 9.37 | 9.42 | -2.6% | -3.1% | -2.0% | -2.3% | 3 |
| Queens, Brooklyn, Staten Island | 122 | 18.39 | 17.88 | 17.43 | 16.49 | 16.21 | -5.4% | -2.1% | -7.0% | -5.6% | 40 |
| All non-edge segments | 261 | 13.50 | 12.91 | 12.48 | 12.18 | 11.71 | -2.4% | -0.7% | -6.2% | -4.6% | 116 |

By season (mean of the same links within each season):

| Group | Feb. 1–May 15: links, 2025 vs 2024, 2026 vs 2024 | July 1–Oct. 31: links, 2025 vs 2024, 2026 vs 2024 |
|---|---|---|
| Inside the zone | 107, +9.1%, -4.5% | 98, +1.6%, -4.4% |
| Manhattan outside | 10, +2.8%, -2.9% | 11, -7.4%, -0.8% |
| Queens, Brooklyn, Staten Island | 115, -4.9%, -6.8% | 91, -4.1%, -6.2% |

The Manhattan-outside group has only 11 links; treat it as a rough contrast. Before edge and suspect links were set aside, this group was 18 links and showed +7.2%, all of it from the two Williamsburg Bridge links (westbound 9.35 to 14.90 mph). The page's first version reported that figure and has been corrected.

**Sensitivity to the suspect-link rule** (change from 2024 to 2025; every rule also applies the cap test):

| Rule | Links set aside | Zone median link | Zone Feb.–May 15 | Zone July–Oct. | Queens/Brooklyn/SI median link | Manhattan outside median link |
|---|---|---|---|---|---|---|
| Cap test only | 6 | +3.5% | +9.9% | +0.2% | -2.3% | -3.1% |
| ≤1/4 or ≥4×, 6 months | 19 | +3.8% | +9.2% | +0.7% | -2.1% | -3.1% |
| **≤1/3 or ≥3×, 6 months (used)** | **29** | **+4.1%** | **+9.1%** | **+1.6%** | **-2.1%** | **-3.1%** |
| ≤0.4 or ≥2.5×, 6 months | 39 | +4.9% | +9.4% | +1.5% | -2.2% | -2.4% |
| ≤0.4 or ≥2.5×, 3 months | 78 | +3.8% | +5.2% | +2.3% | -2.1% | -3.1% |

Under every rule the zone's typical link got faster in 2025, the gain was concentrated in spring, and the typical link elsewhere got slower.

## Limitations

- Only vehicles carrying E-ZPass tags are timed, and only between reader pairs. Speeds on the measured links do not describe every street.
- 152 of the 351 links are inside the zone, all between 14th and 57th streets. No zone link is below 14th Street, so the zone figures say nothing about Lower Manhattan. Four measured links reach below 14th, all outside the zone: two Battery Park Underpass links and the two Williamsburg Bridge links.
- A link on 57th Street or 60th Street sits on or near the zone edge; the midpoint test decides.
- Many things changed at once in 2025: tolls, bus and bike lanes, signal timing, construction, deliveries and the economy. Comparing zone links with links elsewhere helps but does not isolate the toll's effect.
- A median over 15 minutes with as few as three vehicles can swing. Averaging over hours and months smooths it, but single link-hours in quiet periods can be noisy.
- In the zone line of the monthly chart, January runs about 0.5 to 1.6 mph above December in every year, so month-to-month changes around the start of tolls are partly seasonal; the jump into January 2025 is the largest. The other two lines move 0.7 mph or less either way. The page compares the same months year over year instead.
- Speeds here are averages of 15-minute median speeds. Dividing link length by mean travel time instead gives lower levels (about 5.3 mph for the zone in 2024 rather than 7.8, in the fact-check rebuild) but the same direction of change.
- The number of links reporting fell from about 320 a day in early 2024 to about 250 by late 2025. Comparisons hold the set of links fixed.
