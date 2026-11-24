# Night Flight: methodology

Live page: https://joshgreenman1973.github.io/experiments/nyc-night-flight/

Night Flight pairs four sources, night by night, for New York City's five boroughs: radar estimates of migrating birds overhead (BirdCast), the overnight wind (Open-Meteo) and the birds people reported the next day (eBird and iNaturalist). The page's own "How this works" section says the same in shorter form.

## 1. Birds overhead: BirdCast

**Who:** BirdCast, a project of the Cornell Lab of Ornithology, Colorado State University and the University of Massachusetts Amherst. It reads the National Weather Service's NEXRAD weather radars, removes rain and insects and estimates how many birds are aloft and how many cross each U.S. county each night.

**Where the numbers come from.** BirdCast's Migration Dashboard has no download or public API. Each dashboard page includes its own chart data in the HTML, in a script that sets `window.__NUXT__`. We request one page per borough per night:

```
https://dashboard.birdcast.org/region/<county code>?night=<YYYY-MM-DD>
```

County codes: Bronx `US-NY-005`, Brooklyn (Kings) `US-NY-047`, Manhattan (New York) `US-NY-061`, Queens `US-NY-081`, Staten Island (Richmond) `US-NY-085`.

`build/nuxt_parse.py` reads that script as data. It never runs the JavaScript: it parses the literal values and substitutes the function's arguments for the short names in the body. From each page we keep:

- `migrationHistDataFromApi.season.currentSeasonSeries`: the running total of birds that crossed the county, one value per night of the season (`totalBirds`).
- `migrationHistDataFromApi.season.annualAvgSeries`: BirdCast's historical average running total for the same dates.
- `migrationLiveDataFromApi.nightSeries`: for one night, every 10 minutes, birds in flight (`numAloft`), mean flight direction in degrees (`avgDirection`), mean ground speed in mph (`avgSpeed`) and mean and maximum altitude in feet (`meanHeight`, `maxHeight`).

**Nightly totals.** A night's total is the running total on that date minus the running total the night before (the first night of a season is its running total). This reproduces the "total birds" figure BirdCast shows for the night: for Brooklyn on Oct. 10, 2026, the difference is 120,893 and the dashboard shows 120,892 (rounding). The historical average for a night is the same difference on the average series.

**The historical average is one series for all years.** BirdCast serves the same `annualAvgSeries` whatever season is requested, so every season on the page, fall 2021 included, is compared with the average BirdCast publishes today. It is not the average as it stood in that year. BirdCast does not say on the dashboard which years go into it.

**Seasons covered.** BirdCast's live feed runs March 1 to June 15 (spring) and Aug. 1 to Nov. 15 (fall). Its county pages answer for fall 2021 onward; a request for 2020 returns an empty page. Ten-minute detail is stored from spring 2026 on, to keep the number of page requests reasonable (about 1,070 for the two 2026 seasons). For earlier nights, the page links to BirdCast's own page for that night.

**Not added across boroughs.** A bird crossing Brooklyn and then Manhattan counts in both counties' totals, so the page never sums the five boroughs. Rankings such as "busiest night" are per borough.

**The citywide view (the page's default).** For New York City as a whole, the page uses the largest of the five borough estimates each night, and words it as "at least": every bird that crossed the busiest borough crossed the city, so that count is a floor, while the true citywide number is somewhere between it and the (double-counted) sum. The citywide historical average line is the largest of the five borough averages for that date. Rankings in this view are by that nightly floor.

**Limits.** These are radar-based estimates, not counts, and they do not say which species flew. BirdCast notes that radar coverage and ground clutter vary by place. Nights with radar outages appear as missing.

## 2. Wind: Open-Meteo

Hourly wind speed and direction at 10 meters and hourly precipitation at Central Park (latitude 40.78, longitude -73.97), from Open-Meteo's historical weather API (`archive-api.open-meteo.com/v1/archive`, reanalysis data, CC BY 4.0). Units: mph, degrees the wind blows from, millimeters.

A night is the hours from 7 p.m. on its date to 6 a.m. the next morning (12 hours). The night's wind is the vector mean: each hour becomes east and north components, u = −speed × sin(direction) and v = −speed × cos(direction); the mean direction is atan2(−mean u, −mean v), and the mean speed is the plain average of hourly speeds. Nights with fewer than 10 hours are dropped.

**"Blowing the way migrants fly."** In fall, a night counts when cos(direction) > 0.3, meaning the mean wind comes from the north (roughly west-northwest through east-northeast). In spring, when cos(direction) < −0.3, from the south. The comparison on the page is the plain average of nightly BirdCast totals for those nights against all other nights, over complete seasons only, for the borough selected. It is a description, not a model: it does not separate wind from the calendar, rain, temperature or the winds aloft that birds actually ride.

## 3. Birds on the ground: eBird

eBird (Cornell Lab of Ornithology) is a database of birders' checklists. Through the eBird API 2.0, with an API key (`EBIRD_API_KEY`), one request per borough (county code) and day:

```
https://api.ebird.org/v2/data/obs/<county>/historic/<y>/<m>/<d>?rank=mrec&detail=simple&cat=species
```

This lists the species reported that day, one record per species (`cat=species` leaves out hybrids, spuhs and slashes). Checklist counts are not used: they need a second, slow request per borough and day, which the rate limit below can't afford.

- **Citywide:** species are not added across boroughs. The citywide list is the union of the five borough lists.
- **Pairing:** night D is paired with reports dated D+1, as with iNaturalist.
- **First of the season** is computed in the page for whatever is selected: a species' first eBird report of the season in the city or in that borough. Not shown in a season's first 14 days.
- **Stored:** per day, per species, which boroughs reported it. eBird's terms require attribution and restrict redistributing data in its original format, so no raw records are kept. Species names come from the eBird records; photos come from iNaturalist by exact scientific-name match (`fetch_inat.py link-ebird`), only when CC-licensed.
- **Rate limit and backfill:** eBird allows 500 requests an hour per key (bursts of 25 in 5 seconds). Each daily run spends at most 450 requests: first the last 14 days of the current season (during the season and for 45 days after, since checklists are often submitted late), then missing days of older seasons, newest first, about 85 days per run. eBird is kept only for spring 2024 on (the last three years), about 3,200 requests in all, which the daily runs fill in over a few days. When eBird reports the hour's quota is gone, the run saves what it has and stops; it fails only if the recent days weren't refreshed. `fetch_ebird.py backfill --patient` does the same locally but waits out the quota.
- **Which source the chart uses:** a season's ground panel uses eBird only once every day of that season is in (`allDays` in `data/src/ebird/<season>.json`). Until then, and for seasons before 2024, it uses iNaturalist; the night details still list whatever eBird days exist.
- **Limits:** reports follow birder effort (weekends, good weather, May). They measure what birders found, not how many birds were present.

The season chart's ground panel is drawn on its own scale in a separate shaded panel. It is a different measure from the radar counts above it, and the two scales should not be compared directly.

## 4. Birds on the ground: iNaturalist

Observations from the iNaturalist API v2:

```
https://api.inaturalist.org/v2/observations?taxon_id=3&place_id=674&verifiable=true&d1=<start>&d2=<end>&order_by=id&id_above=<n>
```

- `taxon_id=3` is birds (class Aves). `place_id=674` is iNaturalist's New York City boundary.
- `verifiable=true` keeps research-grade and needs-ID observations, which excludes captive or cultivated organisms and records missing a date, location or photo/sound.
- Observations are grouped by `observed_on`, the date the observer recorded.
- Species names, photos and licenses come from `https://api.inaturalist.org/v1/taxa/<ids>`. Subspecies, varieties and forms are folded into their species (for example, feral Rock Pigeon into Rock Pigeon). Observations not identified to species count in the sightings total but not the species count. If a subspecies' parent is not a species, the fetch stops with an error rather than guess.

**Pairing.** Night D (the evening of D into the morning of D+1) is paired with observations dated D+1.

**First of the season.** A species is "first of the season" on the first day it appears in the season's iNaturalist records for the city. The page doesn't flag any in a season's first 14 days, when nearly every species is new to the list.

**Photos.** The page shows iNaturalist's default photo for each species only when its license is Creative Commons (any CC BY variant) or CC0, with the photographer's attribution listed under "Photo credits." These photos are not necessarily taken in New York City.

**Limits.** iNaturalist records what people photograph and upload, so counts rise on weekends, in good weather and at popular parks, and fall on rainy weekdays. Uploads and identifications lag, so the daily job re-fetches the last 30 days, and keeps doing so for 45 days after a season ends. Treat a day's list as a sample of what was around, not a census.

## Files

| File | What it holds |
| --- | --- |
| `build/common.py` | season calendar, borough codes, HTTP with retries (raises on failure) |
| `build/nuxt_parse.py` | reads a dashboard page's embedded data without running it |
| `build/fetch_birdcast.py` | `totals`, `curves` and `nightly` commands |
| `build/fetch_ebird.py` | species reported to eBird by borough and day, within eBird's hourly limit |
| `build/fetch_inat.py` | sightings by day and species, taxa and photos; photos for eBird species |
| `build/fetch_weather.py` | hourly wind and rain by night |
| `build/build.py` | writes `data/index.json`, `data/season/<season>.json`, `data/curves/<season>.json` |
| `data/src/` | the raw pulls the build reads, committed so the daily job can add to them |

## Updates and failure handling

`.github/workflows/nyc-night-flight.yml` (in the repository root) runs every morning. Each source runs as its own step; the page data is rebuilt and committed from whatever succeeded, and the job then fails if any source failed, so a failure shows up red in GitHub Actions instead of passing silently. Fetch helpers raise after their retries instead of returning empty results. The BirdCast step fails in season when the newest night with data is three or more days older than expected. Each source's "last checked" time on the page comes from that source's own files, which are only rewritten after a successful fetch.

## Use of the data

BirdCast, eBird, iNaturalist and Open-Meteo are credited on the page and every figure links to its source. BirdCast publishes no terms for reuse of its dashboard numbers; the page shows them with credit and links back for each figure.
