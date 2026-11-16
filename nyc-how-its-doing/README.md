# How New York Is Doing

An annual report on conditions in New York City, built entirely from public data. The first edition is New York in 2025.

Live page: https://joshgreenman1973.github.io/experiments/nyc-how-its-doing/
Methods: `methodology.html` (built with the page)

## What it does

The report tracks 48 measures in 11 areas, listed in `data/registry.json`. Each measure's direction (whether up is better, worse or neither) was set before any data was gathered. For each measure the build:

1. compares the latest year with the average of the five years before it (or, for a series with gaps, the two most recent earlier values within ten years);
2. divides that change by the measure's typical year-to-year change, the median absolute change between consecutive years over the ten years before the latest;
3. calls a change of less than one typical change, or one inside the published margin of error, "no clear change," and otherwise "better" or "worse" (or "higher" or "lower" for measures with no direction);
4. ranks New York against the 25 largest U.S. cities wherever a same-definition comparison exists (`data/peers.json`).

The front page lists results in order of the size of the change, good or bad, so no one chooses which findings lead.

Because the five-year averages for 2025 include the pandemic years, every measure with a 2019 value also shows it.

## Exceptions, all in `build/build.py`

- `BREAKS`: measures whose definition changed; they are scored only from the break year on (state tests in 2023, the Poverty Tracker in 2020, ParkScore in 2020, a lease-accounting rule for city debt in fiscal 2022).
- `NO_TREND`: measures whose publisher warns against year-to-year comparison; shown but never scored (the D.C. tax-burden comparison).
- `PEER_UNITS`: measures where the New York series is a count but the peer comparison is a rate.

## Files

- `fetch/*.py`: one fetcher per data group. Each downloads from the original source, caches the raw file in `data/raw/<group>/` (kept on this computer, not committed: about 350 MB) and writes `data/indicators/<id>.json` in the format in `SCHEMA.md`. A fetcher exits with an error on an empty or failed download, so it never writes an empty file.
- `build/build.py`: reads the indicator files and writes `index.html`, `methodology.html`, `data/edition.json` and one CSV per measure in `data/csv/`.
- `data/changelog.json`: dated corrections and changes, shown on the methods page.

## Rebuilding

```bash
cd nyc-how-its-doing
python3 -I fetch/census.py
python3 -I fetch/economy.py
python3 -I fetch/housing_schools.py
python3 -I fetch/health_safety.py
python3 -I fetch/env_transit_civic.py
python3 -I build/build.py
```

The build also audits its output. Every number printed on the page must have come from an indicator file through the build's number formatter, or the build stops and lists the stray numbers.

## Next year

Bump `edition` in `data/registry.json` and `EDITION_YEAR` in the build, rerun the fetchers, then read every indicator whose source changed its definition before adding it to `BREAKS`. Do not change a measure's direction after seeing the data. Record every change in `data/changelog.json`.

## Known gaps

This edition has no survey of residents' views of the city, so it measures conditions only. Noise and neighborhood-level (community district) results are missing too. These are listed at the bottom of the page.
