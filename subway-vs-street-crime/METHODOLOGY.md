# How the subway-vs-street calculation works

This document walks through every step of the calculation behind “Is the subway safer than the street?”: what goes in, where each number comes from, which numbers are measured and which are assumed, and the arithmetic that connects them. It uses full-year 2025 data and was published in November 2026.

## A word of caution first

Every result here is an estimate. The crime counts include only crimes reported to police. The time people spend in the subway is estimated from fare data and an assumed trip length. The time they spend on the street is estimated from a travel survey plus several judgment calls, and it is the least certain number in the whole calculation; reasonable changes to it make the gap between street and subway noticeably larger or smaller.

The rates are citywide averages over a full year, and no one actually faces the average. Street risk in particular varies greatly by neighborhood: by the measure in Step 9, violent crime per resident in Mott Haven is about 12 times what it is in Bayside. Beyond neighborhood, a person’s risk depends on which station or block, the hour of the day, how long they linger, who they are with, their age and circumstances, and many other things this calculation cannot see. The results are a way to compare two kinds of places in general. They are not a prediction of what will happen to any one person, and the personal calculator should be read the same way.

## The question and where it comes from

Most people judge the subway’s safety by counting crimes, but a count alone can’t tell you how risky a place is. A place where few crimes happen can still be dangerous if almost nobody spends time there. The fairer comparison is crimes per hour that people spend in each place.

That idea comes from “[Underground: Safer Than the Surface?](https://www.vitalcitynyc.org/underground-safer-than-the-surface/),” by Aaron Chalfin, Alex Chohlas-Wood and Morgan C. Williams Jr. (Vital City, October 2, 2024). Using 2023 data, the article:

1. Counted violent index crimes (murders, rapes, robberies and felony assaults) in the subway (1,120) and on city streets and other public places such as parks and parking lots (16,079).
2. Estimated how much time people spent in the subway: “over 1.3 billion” rides, counting an estimate of fare evaders, at 30 minutes on a train plus 10 minutes on platforms, in tunnels and on stairs. That came to about 880 million person-hours.
3. Divided the two to get a subway rate of almost 1.3 violent crimes per million person-hours.
4. Asked how much time people would have to spend on the street for the street rate to be that low. The answer was “over 12.5 billion hours,” or more than 25 hours a week for each of the roughly 9.5 million people in the city on a given day (about 8.3 million residents plus over 1 million commuters and tourists).
5. Compared that with a sketch of a typical New Yorker’s week outside: about an hour a day commuting on weekdays, five hours of errands and eight hours of weekend leisure, roughly 18 hours in all. The article concluded the subway was likely safer per hour, while noting that its estimates rest on “some educated guesses about how people spend their time.”

The article stopped at step 5: it showed how much street time it would take to erase the subway’s advantage, but did not estimate how much street time there actually is. This analysis follows the same steps with 2025 data and adds that missing piece, an estimate of total street time, so the two rates can be compared directly.

## The basic formula

A **person-hour** is one person spending one hour in a place. If a million people each spend an hour in the subway, that is a million person-hours.

> rate = crimes ÷ person-hours
>
> ratio = street rate ÷ subway rate

Rates are stated per million person-hours. A ratio of 8 means that, on average, an hour on the street carries eight times the chance of violent victimization of an hour in the subway.

It doesn’t matter whether the subway’s hours come from many people riding a little or a few people riding a lot. For every hour anyone spends down there, the rate says how many crimes occur on average. Someone who rides more accumulates more exposure, but the average rate per hour is the same.

## Step 1: Count the crimes

**The data.** Every count comes from NYPD Complaint Data Historic ([NYC Open Data, qgea-i56i](https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i)), a record of every criminal complaint NYPD takes, accessed November 3, 2026. Each complaint is assigned to a year by the date it was reported, the convention NYPD uses for its own annual totals.

**Which crimes.** The main measure is the one the Vital City article used, violent index crimes:

- murder and non-negligent manslaughter
- rape
- robbery
- felony assault

The calculator offers two other groupings:

- **Violent plus misdemeanor assault** adds “assault 3 and related offenses,” the lower-level assault charge that covers most fights resulting in minor injury.
- **All index crimes** adds the three property crimes in NYPD’s index: burglary, grand larceny and grand larceny of a motor vehicle.

**What counts as the subway.** A complaint counts as a subway crime if NYPD’s Transit Bureau, which polices the subway, handled it (the dataset’s jurisdiction field reads “N.Y. Transit Police”). That covers trains, platforms and stations. Applied to 2023, this rule gives 1,120 violent crimes, exactly the article’s number.

**What counts as the street.** A complaint counts as a street crime if any other part of NYPD handled it and the premise is one of these public outdoor places: street; park or playground; public or private parking lot or garage; highway or parkway; open lot; bus stop; bridge; marina or pier. Applied to 2023, this rule gives 16,099 violent crimes, within 0.1% of the article’s 16,079. (The article doesn’t list which premise codes it used. This list is the closest documented rule.)

**The 2025 counts.**

| Crime | Subway | Street and public spaces |
|---|---|---|
| Murder | 4 | 0 (see below) |
| Rape | 9 | 181 |
| Robbery | 401 | 7,542 |
| Felony assault | 593 | 8,280 |
| **Violent index crimes** | **1,007** | **16,003** |
| Misdemeanor assault | 1,720 | 17,949 |
| **Violent plus misdemeanor assault** | **2,727** | **33,952** |
| Burglary | 14 | 1,271 |
| Grand larceny | 1,145 | 16,930 |
| Grand larceny of a motor vehicle | 0 | 11,976 |
| **All index crimes** | **2,166** | **46,180** |

Of the 16,003 street violent crimes, 14,508 happened on a street, 1,037 in a park or playground and the remaining 458 in the other public places listed above.

The subway’s share of violent crime in public places: 1,007 ÷ (1,007 + 16,003) = 5.9%, or about 1 in 17.

**Things to know about these counts.**

- **Murders on the street.** About half of murders in this dataset have no premise recorded (163 of 309 in 2025), so none reach the street count. That slightly understates street risk.
- **Rape.** New York broadened its legal definition of rape in September 2024, so 2025 counts are higher than in earlier years under the old definition. The change affects subway and street alike.
- **Car theft.** The “all index” grouping includes car theft, which is not a danger to a person walking down the street. That grouping therefore overstates pedestrian risk; it is offered because it is NYPD’s standard set.
- **Crimes, not victims.** A robbery of two people is one complaint, and one person can be a victim twice.
- **Reported crimes only.** Many crimes are never reported. If subway crime is reported more often than street crime (more cameras, police and witnesses), the true gap is larger than measured; if less often, smaller.

## Step 2: Estimate time spent in the subway

The article’s method, with 2025 inputs:

| Input | Value | Source | Measured or assumed |
|---|---|---|---|
| Paid subway entries, 2025 | 1,282,466,281 | [MTA Daily Ridership and Traffic](https://data.ny.gov/Transportation/MTA-Daily-Ridership-and-Traffic-Beginning-2020/sayj-mze2), mode “Subway,” summed over the year | Measured |
| Share of riders who don’t pay | 10.20% | Average of MTA’s four 2025 quarterly estimates (9.8%, 9.9%, 11.0% and 10.1%) in [MTA NYCT Subway Fare Evasion](https://data.ny.gov/Transportation/MTA-NYCT-Subway-Fare-Evasion-Beginning-2018/6kj3-ijvb) | Survey estimate |
| Time in the system per trip | 40 minutes | The article: 30 minutes on the train, 10 on platforms, in tunnels and on stairs | Assumed |

MTA’s ridership counts paid entries. People who jump the turnstile are in the subway too, so the paid count is scaled up. If 10.2% of riders don’t pay, paid riders are the other 89.8%:

> all trips = 1,282,466,281 ÷ (1 − 0.1020) = 1,282,466,281 ÷ 0.8980 = 1,428,136,170
>
> person-hours = 1,428,136,170 × 40 ÷ 60 = 952,090,780 ≈ **952 million**

The same steps reproduce the article’s 2023 figure. MTA counted 1,150,217,108 paid entries in 2023, and fare evasion averaged 12.675% across that year’s four quarters (11.1%, 12.3%, 14.0% and 13.3%). That gives 1,150,217,108 ÷ 0.87325 = 1,317,168,174 trips (the article’s “over 1.3 billion”) and 1,317,168,174 × 40 ÷ 60 = 878 million person-hours (the article’s “about 880 million”).

**Checking the 40 minutes.** NYC Department of Transportation’s 2024 Citywide Mobility Survey asks New Yorkers to log every trip, broken into legs. Adding up the subway legs of each subway trip gives a weighted average of about 42 minutes in the subway per trip, close to the article’s 40. If the true figure were 33 minutes, subway hours would fall to about 785 million and the final violent-crime ratio would fall from 8.3 to about 6.9.

## Step 3: Calculate the subway rate

> subway rate = 1,007 ÷ 952 million person-hours = **1.06 violent crimes per million person-hours**

(More precisely 1,007 ÷ 952 = 1.0578. The article’s 2023 figure was 1,120 ÷ 880 = 1.27, its “almost 1.3.”)

## Step 4: Find the break-even amount of street time

This is the article’s central move. How many hours would people have to spend on the street for the street rate to be as low as the subway’s?

> break-even street hours = street crimes ÷ subway rate = 16,003 ÷ 1.0578 per million = 15.13 billion person-hours

Spread over everyone in the city on a given day (Step 5 explains the 9,785,000):

> 15,130,000,000 ÷ 52 weeks ÷ 9,785,000 people = **29.7 hours a week each**

The article’s 2023 version of this number was “over 25 hours per week.” If people spend less time than this on the street, the street is the riskier place per hour. The rest of the analysis estimates how much less.

## Step 5: Estimate time spent on the street

No dataset measures how long New Yorkers spend on the street, so this step builds three independent estimates and averages them. Each input is marked as measured or assumed.

**Who is in the city on a given day: 9,785,000 people.**

| Group | Number | Source |
|---|---|---|
| Residents | 8,585,000 | Census Bureau estimate for July 1, 2025 (Vintage 2025), as reported by the [NYC Department of City Planning](https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/population/population-estimates/new-york-city-population-estimates-and-trends-march-2026.pdf), March 2026 |
| Commuters from outside the city | 1,000,000 | The article’s “over 1 million” commuters and tourists; assumed |
| Tourists | 200,000 | Assumed |

### Method 1: Count the walking trips

Multiply the number of people by how many trips they make, the share of those trips made on foot and how long a walking trip lasts.

| Input | Value | Measured or assumed |
|---|---|---|
| Trips per adult per day, averaged over all seven days of the week | 3.666 | Measured, 2024 Citywide Mobility Survey |
| Share of trips made entirely on foot | 36.65% | Measured, same survey |
| Average length of a walk-only trip | 22.25 minutes | Measured, same survey |

> walking trips per day = 9,785,000 × 3.666 × 0.3665 = 13,147,662
>
> hours per day = 13,147,662 × 22.25 ÷ 60 = 4,874,667
>
> hours per year = 4,874,667 × 365 = **1,779,253,500** (1.78 billion)

The survey inputs come from the survey’s trip records ([wgnh-qwsg](https://data.cityofnewyork.us/d/wgnh-qwsg)) and day records ([naav-ygga](https://data.cityofnewyork.us/d/naav-ygga)), using the weights the survey provides to make its sample represent the city’s adults. Trips per day is the weighted number of trips divided by the weighted number of days, the method the survey’s user guide prescribes. A subway trip is counted once, even though the survey records the walk to the station, the ride and the walk from the station as separate legs.

This method misses some street time, so treat it as a floor:

- It counts only trips made entirely on foot. Walking to and from the subway or bus adds another 9.0 minutes a day per adult in the same survey, though some of that walking happens inside stations, which the subway’s 40 minutes already covers.
- It leaves out time outside that isn’t a trip: standing on a corner, waiting at a bus stop, sitting at an outdoor table.

It also has biases in the other direction:

- The survey covers adult residents in May and June. The calculation applies their habits to children, commuters and tourists, and to the whole year. Spring weather probably means more walking than the yearly average, which inflates street time and makes the street look safer than it is.
- The typical (median) walk-only trip is 9 minutes; long recreational walks pull the average up to 22. The average is the right figure for a total, but it is sensitive to those long walks.

### Method 2: Estimate time outdoors

Assign each group a daily amount of time spent outdoors on foot, then remove the share that isn’t comparable to a street.

| Input | Value | Measured or assumed |
|---|---|---|
| Residents’ outdoor pedestrian time | 45 minutes a day, every day | Assumed |
| Commuters’ outdoor pedestrian time | 30 minutes a day, 250 workdays | Assumed |
| Tourists’ outdoor pedestrian time | 120 minutes a day, every day | Assumed |
| Share of outdoor time spent somewhere street-like | 70% | Assumed |

> residents: 8,585,000 × 45 ÷ 60 × 365 = 2,350,143,750
>
> commuters: 1,000,000 × 30 ÷ 60 × 250 = 125,000,000
>
> tourists: 200,000 × 120 ÷ 60 × 365 = 146,000,000
>
> total outdoor time: 2,621,143,750
>
> street-comparable: 2,621,143,750 × 0.70 = **1,834,800,625** (1.83 billion)

The 45 minutes is checked against the Mobility Survey, which shows adults spending 29.9 minutes a day on walk-only trips and 9.0 minutes walking to and from transit, 38.9 minutes in all. Time spent outdoors that isn’t a trip comes on top of that, so 45 minutes is a reasonable figure.

The 30% reduction removes time in parks, plazas and private outdoor spaces such as yards and outdoor dining areas. That time is outdoors, but not exposed to street crime in the same way. (Central Park alone gets about 42 million visits a year.) The 30% is a judgment call.

### Method 3: Account for the whole day

Start with 24 hours, subtract time that is clearly not on the street, and estimate how much of what’s left is.

| Input | Value | Measured or assumed |
|---|---|---|
| Sleep | 8.0 hours | Assumed |
| Work or school, indoors | 8.5 hours | Assumed |
| Home, awake | 4.5 hours | Assumed |
| Transit | 0.7 hours | Assumed |
| Share of the remaining time spent outdoors | 60% | Assumed |
| Share of that outdoor time truly on the street | 30% to 45% | Assumed |

> time left over = 24 − 8.0 − 8.5 − 4.5 − 0.7 = 2.3 hours a day
>
> outdoors = 2.3 × 0.60 = 1.38 hours a day
>
> citywide = 9,785,000 × 1.38 × 365 = 4,928,704,500
>
> on the street, low end = 4,928,704,500 × 0.30 = **1,478,611,350**
>
> on the street, high end = 4,928,704,500 × 0.45 = **2,217,917,025**
>
> midpoint = 1,848,264,188

Every input here is a guess, so this method serves mainly as a check on the other two. Its time budget also treats every day as a workday for everyone, which understates free time for children, retirees and everyone on weekends.

### The central estimate

Average the three methods, taking Method 3 at its midpoint:

> (1,779,253,500 + 1,834,800,625 + 1,848,264,188) ÷ 3 = 1,820,772,771 ≈ **1.82 billion person-hours**

The calculation rounds this to 1,820 million. The three methods span 1.48 billion to 2.22 billion.

Per person, that works out to 1,820,772,771 ÷ 9,785,000 ÷ 365 = 0.51 hours, or **about 31 minutes a day on the street.** Total street time is about 1.9 times total subway time (1,820 ÷ 952).

## Step 6: Calculate the street rate and compare

> street rate = 16,003 ÷ 1,820 million person-hours = **8.79 violent crimes per million person-hours**
>
> ratio = 8.7929 ÷ 1.0578 = **8.31**

On average, an hour on the street carries about **8.3 times** the risk of violent victimization of an hour in the subway. Put another way, 60 ÷ 8.31 = 7.2: **about 7 minutes on the street carries the same average risk as an hour in the subway.**

The same arithmetic for the other crime groupings:

| Grouping | Subway rate | Street rate | Ratio |
|---|---|---|---|
| Violent index crimes | 1,007 ÷ 952 = 1.06 | 16,003 ÷ 1,820 = 8.79 | 8.3 |
| Violent plus misdemeanor assault | 2,727 ÷ 952 = 2.86 | 33,952 ÷ 1,820 = 18.65 | 6.5 |
| All index crimes | 2,166 ÷ 952 = 2.28 | 46,180 ÷ 1,820 = 25.37 | 11.2 |

Rates are per million person-hours. Misdemeanor assault narrows the gap because the subway has a larger share of low-level fights. The property crimes in the index widen it, largely because of car theft.

## Step 7: Test how much the street-time estimate matters

Street time is the least certain number in the calculation, so here is the violent-crime ratio across a wide range of values, holding the subway rate at 1.0578:

| Street person-hours | Street rate | Ratio |
|---|---|---|
| 1.0 billion | 16,003 ÷ 1,000 = 16.00 | 15.1 |
| 1.2 billion | 16,003 ÷ 1,200 = 13.34 | 12.6 |
| 1.5 billion | 16,003 ÷ 1,500 = 10.67 | 10.1 |
| **1.82 billion (central)** | **16,003 ÷ 1,820 = 8.79** | **8.3** |
| 2.2 billion | 16,003 ÷ 2,200 = 7.27 | 6.9 |
| 3.0 billion | 16,003 ÷ 3,000 = 5.33 | 5.0 |

Across the range the three methods produce (1.48 billion to 2.22 billion), the ratio runs from 10.2 to 6.8. Even at 3 billion hours, two-thirds more than the central estimate, the street comes out five times riskier per hour. The two rates meet only at the break-even of about 15.1 billion hours from Step 4.

## Step 8: The personal risk calculator

The calculator turns the average rates into a rough yearly chance of being a victim, given how many hours a week someone spends in each place. It assumes that person faces the citywide average risk every hour, which no real person does; treat its output as an illustration of scale, not a forecast.

> chance of being a victim in a year = 1 − (1 − r)^h

- **r** is the average chance per hour: crimes ÷ person-hours.
- **h** is that person’s hours a year: hours a week × 52.

The formula treats each hour as an independent draw with a small chance of victimization; the result is the chance that at least one hour in the year goes wrong. At these small rates it is almost exactly r × h.

**Example: 5 hours a week in the subway.**

> r = 1,007 ÷ 952,000,000 = 0.0000010578
>
> h = 5 × 52 = 260
>
> chance = 1 − (1 − 0.0000010578)^260 = 1 − 0.999725 = 0.0275%, about **1 in 3,637**

**Example: 10 hours a week on the street, citywide.**

> r = 16,003 ÷ 1,820,000,000 = 0.0000087929
>
> h = 10 × 52 = 520
>
> chance = 1 − (1 − 0.0000087929)^520 = 1 − 0.995438 = 0.456%, about **1 in 219**

The third card in the calculator divides the street chance by the subway chance (here, 0.456 ÷ 0.0275 = 16.6). That figure compares total yearly risk in each place, so it depends on the hours entered as well as the per-hour rates.

## Step 9: Adjust for neighborhood

Street risk varies enormously across the city, so the calculator can scale the street rate up or down by neighborhood. The subway rate is not adjusted, because the subway is one connected system: a rider from Mott Haven passes through Midtown on the same train as a rider from the Upper East Side.

The multiplier is a neighborhood’s violent crime per resident divided by the citywide rate.

> citywide: 47,291 violent crimes ÷ 8,804,081 residents = 5.37 per 1,000
>
> Mott Haven (40th Precinct): 1,737 ÷ 100,929 = 17.21 per 1,000; 17.21 ÷ 5.37 = **3.20**
>
> Bayside (111th Precinct): 179 ÷ 122,211 = 1.46 per 1,000; 1.46 ÷ 5.37 = **0.27**

So Mott Haven’s rate is 3.2 times the city’s and Bayside’s about a quarter, a gap of about 12 to 1 (3.204 ÷ 0.273 = 11.8). In the calculator, 10 hours a week on the street in Mott Haven becomes:

> r = 0.0000087929 × 3.204 = 0.000028172
>
> chance = 1 − (1 − 0.000028172)^520 = 1.454%, about 1 in 69

(The calculator rounds the multiplier to 3.20 and shows 1.452%.)

Crimes are 2025 complaints, all locations, by the precinct where they occurred. Residents are 2020 Census counts by precinct from John Keefe’s [census-by-precincts](https://github.com/jkeefe/census-by-precincts), which sum to 8,804,081 citywide. Neighborhoods covering several precincts add their crimes and residents before dividing. With “All Index” selected, the calculator uses the same calculation with all seven index crimes.

Limits of the multiplier:

- It counts all violent crime in a precinct, indoors and out, but is applied only to street time. Domestic violence, for instance, raises a precinct’s multiplier without raising the risk to someone walking through it.
- It divides by residents only, so areas full of workers and visitors look more dangerous than they are. Midtown (14th and 18th Precincts) comes out at 3.04 and is left out of the calculator for that reason.
- A precinct is still a large area. Risk varies block by block and hour by hour within it.

## What the calculation cannot tell you

- **The size of the gap rests on one estimate.** Street time is the least certain input. The central estimate means about 31 minutes a day per person. The Mobility Survey measures 39 minutes a day of walking as travel for adults, before counting any time outside that isn’t a trip; at that level (about 2.3 billion hours) the ratio would be about 6.5. The article’s sketch of a typical working New Yorker, about 18 hours a week outside, would bring the ratio much closer to even, though that sketch describes one kind of New Yorker rather than the average across children, retirees and everyone else. Across the estimates here the street comes out riskier per hour; how much riskier depends on this number.
- **Your risk is not the average.** These are citywide averages. Individual risk varies in many ways: by neighborhood and block, by station and line, by time of day and day of week, by how long someone lingers rather than passes through, by age and circumstances, and by whether someone is caught up in disputes with people they know. The calculation captures none of that beyond the rough neighborhood adjustment.
- **Correlation, not cause.** As the article says, the comparison does not show that being in the subway causes lower risk. The people, times of day and activities in each place differ.
- **Crime type.** The subway’s violent crime is more heavily felony assault: in 2025, robbery was 40% of violent crime in the subway and 47% on the street.
- **Concentration.** In 2025, half of violent subway crimes were reported at 56 station names, out of 472 stations. NYPD’s station names merge some stations that share a name, such as those at 14th Street. The calculation does not measure per-hour rates at individual stations.
- **Perception.** An enclosed underground train can feel more dangerous than it is. Fear of crime and the risk of crime are related but different.

## Reproducing the numbers

The scripts are in `scripts/` and write to `data/`. From the project folder:

1. `python3 -I scripts/pull_crime_counts.py` pulls NYPD complaint counts by year, offense, premise and jurisdiction for 2023 through 2025.
2. `python3 -I scripts/cms_walking.py data` computes the walking inputs from the 2024 Mobility Survey.
3. Precinct counts (`data/precinct_violent_2025.json`, `data/precinct_index_2025.json`) come from the same NYPD dataset grouped by precinct; `data/nyc_precinct_2020pop.csv` comes from census-by-precincts. Then `python3 -I scripts/multipliers.py` computes the multipliers.
4. `python3 -I scripts/build_numbers.py` computes every figure in this document and on the page, prints them and saves `data/model.json`.
5. `python3 scripts/render_methodology.py` turns this file into `methodology.html`.

MTA ridership, fare evasion and the population figures are entered by hand at the top of `build_numbers.py`, each with its source.

## Sources

- Aaron Chalfin, Alex Chohlas-Wood and Morgan C. Williams Jr., “[Underground: Safer Than the Surface?](https://www.vitalcitynyc.org/underground-safer-than-the-surface/),” Vital City, October 2, 2024.
- NYPD, [Complaint Data Historic](https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i), NYC Open Data, accessed November 3, 2026.
- MTA, [Daily Ridership and Traffic: Beginning 2020](https://data.ny.gov/Transportation/MTA-Daily-Ridership-and-Traffic-Beginning-2020/sayj-mze2), data.ny.gov, accessed November 3, 2026.
- MTA, [NYCT Subway Fare Evasion: Beginning 2018](https://data.ny.gov/Transportation/MTA-NYCT-Subway-Fare-Evasion-Beginning-2018/6kj3-ijvb), data.ny.gov, accessed November 3, 2026.
- NYC Department of Transportation, Citywide Mobility Survey 2024: [trip records](https://data.cityofnewyork.us/d/wgnh-qwsg), [day records](https://data.cityofnewyork.us/d/naav-ygga) and the survey user guide attached to them.
- NYC Department of City Planning, “[New York City Population Estimates and Trends](https://s-media.nyc.gov/agencies/dcp/assets/files/pdf/data-tools/population/population-estimates/new-york-city-population-estimates-and-trends-march-2026.pdf),” March 2026.
- John Keefe, [census-by-precincts](https://github.com/jkeefe/census-by-precincts): 2020 Census population by NYPD precinct.
