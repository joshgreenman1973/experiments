# Subway vs. street: methodology

How the model behind “Is the subway safer than the street?” works, every number it uses, where each one comes from and which ones are assumptions. Revised November 3, 2026, with full-year 2025 data.

## What the model measures

The model asks how often violent crime happens per hour that people spend in a place. It divides crimes in the subway by the total hours people spend in the subway, does the same for streets and other public outdoor spaces, and compares the two rates.

> rate = crimes ÷ person-hours of exposure
>
> ratio = street rate ÷ subway rate

A person-hour is one person spending one hour in a place. Rates are stated per million person-hours.

The approach comes from Aaron Chalfin, Alex Chohlas-Wood and Morgan C. Williams Jr., “[Underground: Safer Than the Surface?](https://www.vitalcitynyc.org/underground-safer-than-the-surface/)” (Vital City, October 2, 2024). That article computed the subway rate for 2023 and asked how much street time would make the two rates equal. This model goes one step further and estimates street time directly.

## Headline results (2025)

| | Subway | Street and public spaces | Street ÷ subway |
|---|---|---|---|
| Violent index crimes | 1,007 | 16,003 | |
| Person-hours | 952 million | 1.82 billion | |
| Violent crimes per million person-hours | 1.06 | 8.79 | **8.3×** |
| Plus misdemeanor assault, per million hours | 2.86 | 18.65 | **6.5×** |
| All seven index crimes, per million hours | 2.28 | 25.37 | **11.2×** |

Run on 2023 inputs, the same code gives 8.0× for violent crime, against 7.9× in the earlier version of the page.

## 1. Counting the crimes

**Dataset.** NYPD Complaint Data Historic ([NYC Open Data, qgea-i56i](https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i)), pulled November 3, 2026. It covers complaints reported through December 31, 2025. Each complaint is dated by its report date (RPT_DT), the convention NYPD uses for its own year totals. The 2023 violent total in this dataset (46,588) matches the sum of NYPD’s published 2023 counts for murder, rape, robbery and felony assault.

**Crime categories.**

- Violent index crimes: murder and non-negligent manslaughter, rape, robbery, felony assault.
- Violent plus misdemeanor assault: adds “Assault 3 and related offenses,” the lower-level assault charge.
- All index crimes: the four violent crimes plus burglary, grand larceny and grand larceny of a motor vehicle.

**Where a crime counts as “subway.”** Complaints under the jurisdiction of the NYPD Transit Bureau (JURIS_DESC = “N.Y. TRANSIT POLICE”). This reproduces the Vital City article’s 2023 subway count of 1,120 exactly. Using the premise code “Transit – NYC Subway” instead gives 1,086, so the article evidently counted by jurisdiction.

**Where a crime counts as “street.”** Every other complaint whose premise is one of: street; park or playground; public or private parking lot or garage; highway or parkway; open lot; bus stop; bridge; marina or pier. This gives 16,099 violent crimes for 2023, within 0.1% of the article’s 16,079. The article does not publish its premise list; this is the closest documented rule found, and the new numbers use it consistently.

**Counts.**

| | 2023 subway | 2023 street | 2025 subway | 2025 street |
|---|---|---|---|---|
| Violent index | 1,120 | 16,099 | 1,007 | 16,003 |
| Misdemeanor assault | 1,790 | 16,301 | 1,720 | 17,949 |
| Violent + misdemeanor assault | 2,910 | 32,400 | 2,727 | 33,952 |
| All seven index crimes | 2,285 | 46,487 | 2,166 | 46,180 |

Citywide, at all locations, 2025: 47,291 violent index crimes, 60,898 misdemeanor assaults and 121,756 index crimes.

**Caveats on the counts.**

- About half of murders have no premise recorded (163 of 309 in 2025), so they never enter the street count. That slightly understates street risk.
- New York broadened its legal definition of rape in September 2024. Rape complaints rose from 1,452 in 2023 to 2,049 in 2025 citywide. The change applies to subway and street alike, but it affects comparisons across years.
- The index category includes car theft (grand larceny of a motor vehicle: 11,976 of the 46,180 street index crimes in 2025). Car theft is not a risk to a person walking down the street, so the “all index” ratio overstates the danger a pedestrian faces. It is kept because it is NYPD’s standard grouping.
- These are crimes, not victims. A robbery of two people is one complaint, and one person can be victimized twice.
- Only reported crimes count. If subway crime is reported more often (more cameras, more police, more witnesses), the true gap is larger than measured.

## 2. Subway exposure

| Input | Value | Source | Status |
|---|---|---|---|
| Paid subway entries, 2025 | 1,282,466,281 | [MTA Daily Ridership and Traffic](https://data.ny.gov/Transportation/MTA-Daily-Ridership-and-Traffic-Beginning-2020/sayj-mze2) (data.ny.gov), mode = Subway, summed over 2025 | Measured |
| Fare evasion, 2025 | 10.20% | Mean of the four 2025 quarterly rates (9.8%, 9.9%, 11.0%, 10.1%) in [MTA NYCT Subway Fare Evasion](https://data.ny.gov/Transportation/MTA-NYCT-Subway-Fare-Evasion-Beginning-2018/6kj3-ijvb) | Survey estimate |
| Time in the system per trip | 40 minutes | Vital City: 30 on the train, 10 on platforms and stairs | Assumption, checked below |

> trips = 1,282,466,281 ÷ (1 − 0.1020) = 1,428,136,170
>
> person-hours = 1,428,136,170 × 40 ÷ 60 = 952,090,780 ≈ **952 million**

**Check against the original.** For 2023: 1,150,217,108 paid entries ÷ (1 − 0.12675) × 40 ÷ 60 = 878 million, matching the article’s “about 880 million” and its “over 1.3 billion” rides. That confirms the article added fare evaders to MTA’s paid count, and that this update repeats its method.

**Check on the 40 minutes.** NYC DOT’s 2024 Citywide Mobility Survey records each leg of a trip. Summing the subway legs of each trip gives a weighted average of about 42 minutes in the subway per trip. So 40 minutes is a fair round number. If the true figure were 33 minutes, subway hours would fall to about 785 million and the violent-crime ratio would fall from 8.3× to about 6.9×.

## 3. Street exposure

This is the weakest link. No dataset measures how long New Yorkers spend on the street, so the model builds three estimates and averages them. Each input below is marked as measured or assumed.

**Effective daily population: 9,785,000.** 8,585,000 residents (Census Vintage 2025 estimate for July 1, 2025, as reported by the [NYC Department of City Planning](https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/population/population-estimates/new-york-city-population-estimates-and-trends-march-2026.pdf), March 2026) plus 1,000,000 commuters and 200,000 tourists. The commuter and tourist figures are the Vital City article’s and were not refreshed. The earlier version of this page used 8.3 million residents (9.5 million in all).

### Method 1: walking-trip decomposition

> street hours = population × trips per person per day × share of trips made on foot × minutes per walking trip ÷ 60 × 365

| Input | Value | Source | Status |
|---|---|---|---|
| Trips per adult per day | 3.666 | 2024 Citywide Mobility Survey microdata | Measured |
| Share of trips made entirely on foot | 36.65% | Same | Measured |
| Mean walk-only trip | 22.25 minutes | Same | Measured |

> 9,785,000 × 3.666 × 0.3665 = 13,147,662 walking trips a day
>
> 13,147,662 × 22.25 ÷ 60 = 4,874,667 person-hours a day
>
> × 365 = **1,779,253,500** (1.78 billion)

The survey figures come from the trip table ([wgnh-qwsg](https://data.cityofnewyork.us/d/wgnh-qwsg)) and day table ([naav-ygga](https://data.cityofnewyork.us/d/naav-ygga)) with the survey’s citywide weights. Trips per day is total weighted trips divided by total weighted adult-days, which the survey’s user guide gives as the correct way to compute a trip rate; it averages over all seven days of the week. Transit trips are counted once even though the survey stores them as several legs.

The earlier version used 2.5 trips per weekday and 2.3 per weekend day (a weighted 2.44), a 41% walking share credited to MIT’s 2026 Nature Cities study and 20 minutes a trip. The 2.5 trips could not be traced to a published survey figure. The 41% appears in the MIT paper as background drawn from travel surveys, not as a result of the model. The survey microdata replace all three.

Limits of this method:

- It counts only trips made entirely on foot. It leaves out walking to and from transit, which the same survey measures at another 9.0 minutes a day per adult. Some of that walking happens inside stations, which the subway’s 40 minutes already covers.
- The survey covers adult residents in May and June. The model applies their walking rates to children, commuters and tourists, and to the whole year. Spring weather probably inflates walking compared with a yearly average, which makes the street look safer than it is.
- The median walk-only trip is 9 minutes and the mean is 22. Long recreational walks pull the mean up, but the mean is the right figure for a total.

### Method 2: time-use approach

> street hours = (residents × 45 min × 365 + commuters × 30 min × 250 workdays + tourists × 120 min × 365) ÷ 60 × 0.70

| Input | Value | Status |
|---|---|---|
| Resident outdoor pedestrian time | 45 minutes a day | Assumption |
| Commuter outdoor pedestrian time | 30 minutes a workday | Assumption |
| Tourist outdoor pedestrian time | 120 minutes a day | Assumption |
| Share of outdoor time that is street-comparable | 70% | Assumption |

> residents: 8,585,000 × 45 ÷ 60 × 365 = 2,350,143,750
>
> commuters: 1,000,000 × 30 ÷ 60 × 250 = 125,000,000
>
> tourists: 200,000 × 120 ÷ 60 × 365 = 146,000,000
>
> total 2,621,143,750 × 0.70 = **1,834,800,625** (1.83 billion)

The earlier version grounded the 45 minutes in a claim that Americans walk about 20 minutes a day according to the American Time Use Survey and that New Yorkers walk 1.5 to 2.5 times as much. Neither figure could be traced to a source. The 2024 Mobility Survey now gives a direct check: adults spend 29.9 minutes a day on walk-only trips and 9.0 minutes walking to and from transit, 38.9 minutes in all. A 45-minute figure that also covers outdoor time that is not a trip is consistent with that, so it is unchanged.

The 30% discount removes time in parks, plazas and private outdoor space, which counts as outdoors but is not comparable to streets for crime exposure. It is a judgment call.

### Method 3: residual-time accounting

> street hours = population × (24 − sleep − work or school − home awake − transit) × 0.60 × 365 × (0.30 to 0.45)

| Input | Value | Status |
|---|---|---|
| Sleep | 8.0 hours | Assumption |
| Work or school, indoors | 8.5 hours | Assumption |
| Home, awake | 4.5 hours | Assumption |
| Transit | 0.7 hours | Assumption |
| Share of leftover time that is outdoors | 60% | Assumption |
| Share of that which is truly on the street | 30% to 45% | Assumption |

> leftover time: 24 − 8.0 − 8.5 − 4.5 − 0.7 = 2.3 hours
>
> 2.3 × 0.60 = 1.38 hours a day
>
> 9,785,000 × 1.38 × 365 = 4,928,704,500
>
> × 0.30 = **1,478,611,350**; × 0.45 = **2,217,917,025**; midpoint 1,848,264,188

This method is a sanity check. Every input is a guess, and the time budget treats every day as a workday for everyone, which understates free time for children, retirees and everyone on weekends.

### Central estimate

> (1,779,253,500 + 1,834,800,625 + 1,848,264,188) ÷ 3 = 1,820,772,771 ≈ **1.82 billion person-hours**

The earlier version described its 1.6 billion as “weighted toward Methods 1 and 2.” Its own three figures average to 1.58 billion, so a simple average is what it effectively used. This version says so. The model rounds the central estimate to the nearest 10 million (1,820 million). The three methods span 1.48 billion to 2.22 billion.

**Per person, the central estimate works out to about 31 minutes a day on the street** (1.82 billion ÷ 9,785,000 ÷ 365).

## 4. Rates and ratios

| | Subway | Street | Ratio |
|---|---|---|---|
| Violent index | 1,007 ÷ 952 = 1.0578 | 16,003 ÷ 1,820 = 8.7929 | 8.31× |
| Violent + misdemeanor assault | 2,727 ÷ 952 = 2.8645 | 33,952 ÷ 1,820 = 18.6549 | 6.51× |
| All index | 2,166 ÷ 952 = 2.2752 | 46,180 ÷ 1,820 = 25.3736 | 11.15× |

Rates are per million person-hours. 60 ÷ 8.31 = 7.2, so about 7 minutes on the street carries the violent-crime risk of an hour on the subway.

Subway share of public-space violent crime, 2025: 1,007 ÷ (1,007 + 16,003) = 5.9%, about 1 in 17.

## 5. Sensitivity to street time

Holding the subway rate at 1.0578:

| Street person-hours | Street rate | Ratio |
|---|---|---|
| 1.0 billion | 16.00 | 15.1× |
| 1.2 billion | 13.34 | 12.6× |
| 1.5 billion | 10.67 | 10.1× |
| **1.82 billion (central)** | **8.79** | **8.3×** |
| 2.2 billion | 7.27 | 6.9× |
| 3.0 billion | 5.33 | 5.0× |

Across the range the three methods produce (1.48 billion to 2.22 billion), the ratio runs from 10.2× to 6.8×.

**Break-even.** The rates would be equal at 16,003 ÷ 1.0578 = 15.1 billion street person-hours a year, or 29.7 hours a week for each of the 9.785 million people in the city on a given day. (The Vital City article’s 2023 figure was “over 12.5 billion” and “over 25 hours a week.”)

## 6. The personal calculator

> annual risk = 1 − (1 − r)^h

where r is crimes per person-hour and h is the user’s hours a year (weekly hours × 52). Each hour is treated as an independent trial with the same small chance of being victimized; at these rates the result is almost exactly r × h.

Default example, violent index crimes, citywide:

- Subway, 5 hours a week: r = 1,007 ÷ 952,000,000 = 1.0578 × 10⁻⁶; h = 260; risk = 1 − 0.999725 = 0.0275%, or 1 in 3,637.
- Street, 10 hours a week: r = 16,003 ÷ 1,820,000,000 = 8.7929 × 10⁻⁶; h = 520; risk = 1 − 0.995438 = 0.456%, or 1 in 219.
- Street in Mott Haven (multiplier 3.204): r = 2.8172 × 10⁻⁵; risk = 1.454%, or 1 in 69. The calculator rounds the multiplier to 3.20 and shows 1.452%.

The calculator’s “street risk ÷ subway risk” card compares total annual risk, so it depends on the hours entered as well as the per-hour rates.

## 7. Neighborhood multipliers

The calculator can scale street risk by neighborhood. The multiplier is a precinct’s violent index crimes per resident divided by the citywide rate.

> citywide rate, 2025: 47,291 ÷ 8,804,081 = 5.37 per 1,000 residents
>
> Mott Haven (40th Precinct): 1,737 ÷ 100,929 = 17.21 per 1,000 → 17.21 ÷ 5.37 = **3.20×**
>
> Bayside (111th Precinct): 179 ÷ 122,211 = 1.46 per 1,000 → 1.46 ÷ 5.37 = **0.27×**

Crimes are 2025 complaints by precinct (ADDR_PCT_CD). Populations are 2020 Census counts by precinct from John Keefe’s [census-by-precincts](https://github.com/jkeefe/census-by-precincts) (they sum to 8,804,081). Neighborhoods that span several precincts add the crimes and the residents before dividing. The “All Index” setting repeats the calculation with all seven index crimes.

Limits:

- The multiplier counts all violent crime in a precinct, indoors and out, but is applied only to street time. Domestic violence raises a precinct’s multiplier without raising the risk to someone walking through it.
- Residents are the denominator, so precincts with many workers and visitors look more dangerous than they are. Midtown (14th and 18th Precincts) comes out at 3.04× and is left out of the calculator for that reason.
- Recomputing 2024 with the same code reproduces the earlier version’s multipliers to within 0.02 everywhere except Hunts Point, where the data give 3.28 rather than the 2.67 the page showed.

## 8. What the model cannot tell you

- **The street-time estimate is the crux.** The central estimate implies about 31 minutes a day on the street per person. The 2024 Mobility Survey measures 39 minutes a day of walking as travel for adults (walk-only trips plus walking to and from transit), before counting any time spent outdoors that is not a trip. If street time were set from that measurement (about 2.3 billion hours), the violent-crime ratio would be about 6.5×. The Vital City article also sketched a typical working New Yorker’s week at around 18 hours outside, which would bring the ratio much closer to even. The direction of the finding is robust; its size depends on this one estimate.
- **Crime type.** In 2025, robbery was 40% of violent crime on the subway and 47% on the street; felony assault was a larger share underground.
- **Place and time.** Both rates vary enormously by station, neighborhood and hour. These are system-wide averages.
- **Concentration.** In 2025, half of violent subway crimes were reported at 56 station names. NYPD’s station names merge some stations that share a name, such as those at 14th Street, so the true number of stations is somewhat higher. The model does not measure per-hour rates at individual stations.
- **Perception.** An enclosed train can feel more dangerous than it is. Fear and risk are related but distinct.

## 9. Corrections in this revision

Beyond moving from 2023 to 2025 data, the review found and fixed these errors in the earlier version:

1. **All-index street count.** The text used about 59,000 street index crimes (a 14× ratio); the calculator used 48,000 (11.6×). The 59,000 came from guessed outdoor shares by crime type that implied 28,500 violent crimes outdoors, contradicting the page’s own count of 16,079. Counting by premise gives 46,487 for 2023 and 46,180 for 2025. The bottom-line range changes from “6 to 14 times” to “6 to 11 times.”
2. **Misdemeanor assault.** The page gave 44,151 misdemeanor assaults citywide in 2023 and said 60% happened in residences. The complaint data show 58,322, with 45% in residences. The street count also used a narrower premise rule than the violent count, and the subway count used premise rather than jurisdiction. All three now use the same rules.
3. **Subway hours.** The walkthrough multiplied 1.3 billion trips by 40 minutes, got 866.7 million and “rounded” to 880 million. The 880 million actually comes from 1.317 billion trips (paid entries plus fare evaders). The explanation is corrected.
4. **Method 3 arithmetic.** The summary said 1.2 to 1.8 hours a day, 4.2 to 6.2 billion hours and 1.5 to 2.2 billion after discounting. Those do not follow from one another. The walkthrough’s figures (1.38 hours, 4.79 billion, 1.44 to 2.15 billion) were right, and the low end should have read 1.4, not 1.5.
5. **Break-even population.** The page said the break-even required “every person in the metro area” to spend 25+ hours a week outside. The article’s calculation uses the roughly 9.5 million people in the city on a given day; the metro area has about 20 million.
6. **Sensitivity rounding.** Ratios were computed from a subway rate rounded to 1.27, so the generous case showed 5.8× when the unrounded figure is 5.7×. All ratios are now computed unrounded.
7. **“Tripling the conservative estimate.”** The 3.0 billion case was 2.5 times the 1.2 billion “conservative” case. Reworded.
8. **Neighborhood labels.** “South Bronx / Melrose” covered the 44th and 46th Precincts, which are Highbridge, Concourse, Fordham and University Heights; Melrose is in the 40th and 42nd. Relabeled “Highbridge / Fordham.” “Williamsburg” included the 94th Precinct (Greenpoint) and is now “Williamsburg / Greenpoint.”
9. **Crime mix.** The page said the subway has “proportionally more robberies.” It has proportionally fewer: 48% vs. 51% in 2023 and 40% vs. 47% in 2025.
10. **Station concentration.** The page said half of violent subway crimes occur at 30 of 472 stations and that even those stations have per-hour rates far below the streets around them. The 2025 data put half at 56 station names, and no station-level exposure data exist to support the second claim. Corrected and removed.
11. **Time of day.** The page said rush hours are “when violence is lowest.” That was not checked against data, so the hypothesis is now worded without it.
12. **Calculator note.** In “All Index” mode the neighborhood note showed the violent-crime multiplier while the math used the index multiplier. The note now shows the multiplier actually applied.

## 10. Reproducing the numbers

Scripts are in `scripts/`; data files land in `data/`. Run from the project folder:

1. `python3 -I scripts/pull_crime_counts.py`: NYPD complaints by year, offense, premise and jurisdiction for 2023 to 2025.
2. `python3 -I scripts/cms_walking.py data`: walking inputs from the 2024 Mobility Survey.
3. Precinct counts (`data/precinct_violent_2024.json`, `precinct_violent_2025.json`, `precinct_index_2025.json`) come from grouped queries on the same NYPD dataset by ADDR_PCT_CD; `data/nyc_precinct_2020pop.csv` is from census-by-precincts. Then `python3 -I scripts/multipliers.py`.
4. `python3 -I scripts/build_numbers.py`: computes every figure on the page for 2023 and 2025, prints them and writes `data/model.json`.
5. `python3 scripts/render_methodology.py`: turns this file into `methodology.html`.

MTA ridership, fare evasion and the population estimate are entered by hand at the top of `build_numbers.py`, each with its source.

## Sources

- Chalfin, Chohlas-Wood and Williams, “[Underground: Safer Than the Surface?](https://www.vitalcitynyc.org/underground-safer-than-the-surface/),” Vital City, October 2, 2024.
- NYPD, [Complaint Data Historic](https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i), NYC Open Data, accessed November 3, 2026.
- MTA, [Daily Ridership and Traffic: Beginning 2020](https://data.ny.gov/Transportation/MTA-Daily-Ridership-and-Traffic-Beginning-2020/sayj-mze2), data.ny.gov, accessed November 3, 2026.
- MTA, [NYCT Subway Fare Evasion: Beginning 2018](https://data.ny.gov/Transportation/MTA-NYCT-Subway-Fare-Evasion-Beginning-2018/6kj3-ijvb), data.ny.gov, accessed November 3, 2026.
- NYC Department of Transportation, Citywide Mobility Survey 2024: [trips](https://data.cityofnewyork.us/d/wgnh-qwsg), [days](https://data.cityofnewyork.us/d/naav-ygga) and the 2024 user guide attached to those datasets.
- NYC Department of City Planning, “[New York City Population Estimates and Trends](https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/population/population-estimates/new-york-city-population-estimates-and-trends-march-2026.pdf),” March 2026.
- John Keefe, [census-by-precincts](https://github.com/jkeefe/census-by-precincts), 2020 Census population by NYPD precinct.
- Sevtsuk and colleagues, “Spatial Distribution of Foot-traffic in New York City and Applications for Urban Planning,” Nature Cities, 2026 ([MIT News summary](https://news.mit.edu/2026/new-model-maps-foot-traffic-new-york-city-0206)). Cited for context only; no figure from it is used.
