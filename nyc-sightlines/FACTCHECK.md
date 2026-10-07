# Fact-check

Every claim on the page, and in the chat that produced it, was checked blind by independent agents. They were given the claims and the data, but not the pipeline code, and asked to find errors:

1. **Data checker.** Recomputed every number on the page from the raw arrays with its own code, including its own exact line-of-sight tracer.
2. **External checker.** Checked facts about the world (heights, dates, zoning, history, prior work) against primary and authoritative sources on the web.
3. **Sun checker.** Recomputed solar positions with its own algorithm and brute-forced the horizon at sampled squares. Its results are in the last section.

The fixes below were then applied, and the numbers were regenerated from scratch.

## What was wrong, and what changed

### Facts about the world (external checker)

| Claim | Finding | Resolution |
|---|---|---|
| "Seven buildings" among the Manhattan landmarks | ❌ Miscount: six towers plus the statue | Corrected |
| Landmark heights | 🔶 Mixed tip and roof heights; some wrong | Heights now use CTBUH architectural height for buildings (ESB 1,250 ft, with the 1,454-ft antenna tip noted), tower height above water for bridges, and the arch crown for Hell Gate. The table shows what each number means |
| Hell Gate Bridge opened 1916 | ⚠️ Opened 1917 | Corrected. Parachute Jump (built 1939, moved to Coney Island 1941) and Brooklyn Tower (topped out 2021, finished 2022) carry notes |
| "1.96 million buildings" as the city's | 🔶 1.96 million includes nearby NJ, Westchester and Nassau; the city has about 1.1 million | Clarified |
| Building heights "machine-learned where missing" | 🔶 Overstated the ML share: in the city, 99% of heights come from OpenStreetMap (from city data), fewer than 1% are Microsoft ML, and about 1% have no height | Rewritten with the actual shares |
| "None of the 16 is in the Bronx" | ⚠️ The Hell Gate Bridge's approach viaduct reaches Port Morris | Clarified: the arch, the point traced, spans Queens to Wards Island |
| June 21 sunrise time | ❌ Refraction was applied twice | Times now use the standard definition; June 21 sunrise 5:25, sunset 8:30 |
| (Chat) the Promenade has "the only" protected view | 🔶 SV-1 is the only Scenic View District, but waterfront zoning also protects visual corridors (ZR 62-512, 128-43) | Corrected in chat |

### Numbers computed from the data (data checker)

All headline numbers were reproduced. These were not:

| Claim | Finding | Resolution |
|---|---|---|
| Tour counts ("14 landmarks" at Jamaica Bay, "13" at Alice Austen) | 🔶 Each was the single best cell; Jamaica Bay's pin was out on Little Egg Marsh, not the trail; Alice Austen's spot saw 12 under the exact check | Captions are now generated from data: "up to N (exact line of sight at the pinned spot), M from a typical spot," over the named place. Jamaica Bay uses the West Pond loop |
| "100% see none" (two neighbourhoods) | ⚠️ 99.5% | Shares that aren't exactly 100 no longer display as 100 |
| Statue of Liberty "seen nearly all from the waterfront" | ❌ About half (54%) of its viewing spots are within 200 m of the water; the biggest shares are Floyd Bennett Field and Green-Wood Cemetery | Rewritten from the data |
| Brooklyn average "1.9" vs. "2.0" | ⚠️ Rounding from rounded data | Averages are now kept to three decimals before display |
| Times Square "sees none of the 16" | 🔶 A strip at the north end, by the TKTS steps, sees the Empire State Building | Caption says so; 95% of the plazas see none |
| Sunset Park summit height and count | ⚠️ Off by a few feet and landmarks | Computed from data |
| Longest sightlines (Verrazzano "from Pelham Bay", One Court Square "from New Springville") | 🔶 The spots were on Hart Island and the closed Fresh Kills mounds | See "public ground" below. Every longest sightline now passes the exact check, with a specific place name |
| Williamsburgh Savings Bank traced point "345 ft" | ⚠️ 344 ft | Foot conversion now uses 3.28084 |
| Validation "agreed 99.3–99.6%" | 🔶 Agreement on a 50/50 stratified sample, not a random one | Reworded with the rates in each half and the net effect (percentages may run up to about 1.5% of their value high) |
| Public ground | 🔶 2.57 km² leaked into neighbouring counties | Fixed |
| One World Trade Center base elevation | ⚠️ The DEM put it in the excavation (−1.9 m) | Set to 3.2 m (street level) and recomputed |

### Found while applying the fixes

- **"Public ground" included private and closed land.**
  - The Empire State Building's "farthest view" was a service road inside a fenced oil terminal.
  - Service roads and paths inside fenced industrial sites, rail yards, airports and power plants are now excluded, as are Rikers Island, Hart Island and Freshkills Park (except separately mapped parks within it). That removed 12.1 km², or 3.5%.
  - All numbers were recomputed. Notable changes: the Empire State Building's share went from 16.6% to 15.9% and the statue's from 1.3% to 1.1%. Staten Island, not the Bronx, now has the lowest borough average (0.47 against 0.55), so a tour caption that called the Bronx lowest was rewritten.
- **The longest sightlines are marginal.** Each passes the exact check, but by only 0.4–1.8 m of clearance, which is within the model's error. The page now says so.
- **Brooklyn Heights Promenade in June.** The caption said the sun sets behind "Lower Manhattan's west side". Tracing it shows the blockers are Financial District towers (95–125 Wall St., 55 Water St., 125 Broad St., One New York Plaza). Corrected.
- **Clock times for paired dates.** Each sun map serves two dates mirrored around a solstice (e.g. Feb. 19 and Oct. 23), but the page showed one date's clock times for both. They differ by up to 32 minutes, partly because of daylight saving time. Each date now has its own times.
- **Place labels.** Neighbourhood-area names were too coarse ("Pelham Bay" for a spot on City Island). Labels now use the named park or the specific neighbourhood.

## Sun checker

Pending: the results will be added here.
