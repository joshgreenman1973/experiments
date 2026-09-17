# Report card

Every indicator in New York City's Mayor's Management Report, fiscal 2016 through fiscal 2025,
searchable and charted — plus a dozen different ways of asking which ones are outliers.

The Mayor's Management Report is required by the City Charter. It is the city's own account of how
its agencies performed, published each September as a stack of agency chapters in PDF and,
separately, as a 768,409-row table on the open data portal. This reads the whole table at once.

- **Scoreboard** — how many indicators moved the way the city says it wants them to, citywide and
  agency by agency, against a baseline year you choose.
- **Agencies** — each agency's indicators in the report's own hierarchy of service and goal, with
  what it spent and how many people it employed over the same years.
- **All indicators** — search across names, the city's own description of each indicator, agency,
  service and goal.
- **Outliers** — rank by one-year change, sustained trend, a line fitted through every year,
  distance from an indicator's own normal, best or worst reading on record, volatility, streaks,
  the biggest one-year step it ever took, or the handful of published figures that cannot be right.
- **Retired** — what the city has stopped counting, including five whole initiative chapters.

Every indicator links out to its raw rows on the open data portal and to the agency's published
chapter, so any figure here can be checked against the source in two clicks.

## Building the data

No dependencies beyond Python 3.

```
python3 build/fetch.py        # ~4 min, writes build/raw/ (~700 MB, gitignored)
PYTHONPATH=build python3 build/transform.py
```

`fetch.py` pages three tables off the NYC Open Data portal and fails loudly if a page comes back
short. `transform.py` writes `data/indicators.json` plus the per-agency files the page loads on
demand. `stats.py` holds the outlier measures, each one commented with why it exists and what it
cannot tell you. Nothing is cached between runs and nothing is hand-edited: rerun it after the city
posts a new year and the new year appears.

## What it will not tell you

The full list is on the [method page](methodology.html). The short version: the fiscal 2026 report
is published but the open dataset behind it still stops in March 2026, so full-year figures here end
at fiscal 2025. The data starts at fiscal 2016. There are no target figures in the open dataset, so
nothing here says whether an agency hit its own target — only which way the number went.

## Sources

- [Mayor's Management Report — Agency Performance Indicators](https://data.cityofnewyork.us/City-Government/Mayor-s-Management-Report-Agency-Performance-Indica/rbed-zzin) (`rbed-zzin`)
- [MMR Agency Resources](https://data.cityofnewyork.us/resource/4qmi-txnk) (`4qmi-txnk`) and [Preliminary MMR Agency Resources](https://data.cityofnewyork.us/resource/nvzu-6t9y) (`nvzu-6t9y`)
- [Mayor's Office of Operations](https://www.nyc.gov/site/operations/reports/mmr.page) — the published chapters
- [The city's own Dynamic MMR](https://dmmr.nyc.gov/) — not scraped; its robots file asks not to be crawled
