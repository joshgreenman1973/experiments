# Methodology: NYC vacant storefronts, six years of the registry

## What this tool is

An interactive map and dashboard built on the **Storefronts Reported Vacant or Not (SRVN)** registry published by the New York City Department of Finance (DOF). It is a companion and counterpoint to the NYC Comptroller's 2026 report ["Who's Minding the Storefronts?"](https://comptroller.nyc.gov/reports/whos-minding-the-storefronts/).

The two use different data and answer different questions:

| | Comptroller report | This tool |
|---|---|---|
| Source | Live XYZ (private vendor) | NYC DOF registry (public) |
| Observation | One field snapshot (April 2026) | Six annual owner filings (2020–2025) |
| Coverage | ~142,000 storefronts surveyed | ~67,000 storefronts that owners registered |
| Strength | A true citywide vacancy *rate* | The *duration* of vacancy at a given address |

The comptroller's snapshot is better for the citywide rate (it observes every visible storefront). The registry is better for **persistence** — because the same owner re-files year after year, you can follow a single storefront through time and see how long it has actually sat empty, rather than estimating it.

## Data source

- **Dataset:** [Storefronts Reported Vacant or Not (92iy-9c3n)](https://data.cityofnewyork.us/dataset/92iy-9c3n), NYC Open Data
- **API endpoint:** `https://data.cityofnewyork.us/resource/92iy-9c3n.json`
- **Rows pulled for this build:** 414,884 registration records
- **Reporting periods:** ending December 2019/June 2020 through 2025

### Background: Local Law 157 of 2019

Local Law 157 directed the Department of Finance to maintain a public registry of ground-floor and second-floor commercial storefronts and their vacancy status. Owners of covered properties report annually whether each storefront is vacant or occupied. The registry is the result.

## How the data is processed

The raw registry has one row per filing. A build script (`build_data.py`) collapses these into one record per **storefront**, then writes a compact `data/storefronts.json` the page loads directly.

1. **Storefront identity.** Rows are grouped by `BBL` (borough-block-lot) + property number + unit. A single building (BBL) can contain several storefronts; the unit number keeps them separate.
2. **Year normalization.** Reporting-period labels like "2019 and 2020" are reduced to the period's **end year** (here, 2020). The years on the map therefore run 2020–2025.
3. **Vacancy per year.** For each storefront and year, it is coded **vacant** if either `vacant_on_12_31` or `vacant_6_30_or_date_sold` is "YES." If any filing in a year reports vacancy, that year is counted vacant.
4. **Consecutive-year streak.** The headline persistence number is the count of consecutive years a storefront was reported vacant, ending at the most recent year it appears. "Vacant 6 years running" means the owner filed in all six periods and reported the space vacant each time.

## The numbers on the page

- **Reported vacant** — storefronts vacant at their most recent filing.
- **Chronic (2+ years running)** — vacant in at least two consecutive filings.
- **Vacant all six years** — reported vacant in every one of the six periods (the longest-empty list).
- **Clustering ("76% more likely")** — among registered storefronts, those within ~75 meters of at least one storefront that was vacant at last filing have a ~19.8% vacancy rate, versus ~11.2% for those with no vacant neighbor in range — about 76% higher. This independently reproduces the comptroller's finding that vacancy clusters spatially. Computed citywide at build time.
- **Reported vacancies by year** — the count of storefronts reported vacant in each calendar period. This rises and falls partly with how many owners filed that year, so read it as a trend in *the registry*, not a precise citywide count.
- **Year slider / Play** — for any year 2020–2025, the map shows storefronts reported vacant in that year, shaded by how many consecutive years they had been vacant up to that point.

## Important caveats

- **Self-reported and not a census.** Everything here is what owners told the city. Coverage is incomplete and compliance varies, so these figures describe **registered** storefronts, not all storefronts. The registry "vacancy rate" (~17% at last filing) is higher than the comptroller's observed 11% partly because owners are more likely to file — or keep filing — when a space is empty. Do not read it as the true citywide rate; use the comptroller's snapshot for that.
- **Filing gaps look like absences.** If an owner stops filing, the storefront simply drops out of later years. A streak counts only years actually filed, so a six-year streak is strong evidence of persistent vacancy, but a *short* streak can reflect a missing filing rather than a re-occupancy.
- **No reason for vacancy.** The data does not say whether a space is actively marketed, mid-renovation, warehoused, or awaiting demolition. Where the owner reported active construction, the popup notes it.
- **Lease-expiration dates** (`expir_dt_of_most_recent_lease`) are present for only a minority of vacant records and are shown only where reported.
- **Geocoding.** Coordinates are derived from the property address and may sit at the building rather than the exact storefront entrance, especially on corner lots and large buildings.

## Reproducing this

Run `python3 build_data.py` to re-pull the registry and regenerate `data/storefronts.json`. The script is self-contained (standard-library `urllib` only) and prints the summary metadata it writes.

## Update frequency

The DOF registry updates on a rolling basis as owners file. Re-running the build script refreshes the underlying file; the page itself loads the pre-built JSON for speed.
