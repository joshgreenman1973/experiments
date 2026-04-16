# Methodology — NYC apartment combinations map

## What this map shows

Every filing on record with the NYC Department of Buildings (DOB) where an owner applied for a permit to combine two or more apartments into one. Each dot is a single job filing — typically an Alteration Type 2 (A2) application — tied to the building where the work was proposed.

Timeframe: January 1, 2000 through December 31, 2020.

Total filings mapped: 21,665 (of 21,672 matching records in the underlying dataset — seven had no geographic coordinates and were dropped).

## Data source

**NYC DOB Job Application Filings** on NYC Open Data.

- Dataset ID: `ic3t-wcy2`
- URL: https://data.cityofnewyork.us/d/ic3t-wcy2
- API endpoint used: https://data.cityofnewyork.us/resource/ic3t-wcy2.json
- Data fetched: 2026-04-15

This dataset covers jobs submitted through DOB Borough Offices, eFiling, and the HUB — the legacy DOB filing systems. It does NOT include jobs submitted through DOB NOW, which replaced most alteration filings starting in 2021.

## How apartment combinations were identified

DOB does not tag filings with a "combination" code. The `job_description` is a free-text field filled in by the applicant. A combination job is identified by the description text.

### The filter

A record was classified as an apartment combination if its `job_description`, uppercased, contained:

- the substring `COMBIN` (catches "combine," "combining," "combination," "combines," etc.), AND
- at least one of: `APART`, `UNIT`, or `DWELLING`

In SoQL:

```
upper(job_description) like '%COMBIN%'
AND (upper(job_description) like '%APART%'
  OR upper(job_description) like '%UNIT%'
  OR upper(job_description) like '%DWELLING%')
AND gis_latitude IS NOT NULL
```

This caught ~21,672 records. A broader filter of just `COMBIN` alone returned ~33,000 records — but those included things like combining stores, combining offices, combining mechanical rooms. Requiring an apartment/unit/dwelling keyword alongside eliminated most of that noise.

### What the filter misses

- **Combinations described without the word "combine."** If someone wrote "merge apartments 4A and 4B" or "remove demising wall between units 12C and 12D," this filter will not catch them. The DOB's own reporting has flagged this inconsistency for years.
- **Combinations filed through DOB NOW after 2021.** The DOB NOW dataset (`w9ak-ipjd`) has no job description field, so there's no reliable way to identify combinations in it. The `existing_dwelling_units > proposed_dwelling_units` proxy is unreliable — it picks up demolitions and conversions.
- **Unpermitted combinations.** Some combinations happen without any filing. Those are, by definition, not in this dataset.

### What the filter catches that isn't strictly a combination

Spot-checking the 21,672 records confirms the vast majority describe genuine apartment combinations. Some are edge cases — e.g., a job description that mentions "combination sprinkler system" for an apartment building, or legalizations of previously combined units. I left those in because they were a small share and filtering them out would require subjective judgment on each record.

## Why the dataset drops off after 2020

Annual counts before and after the cutoff:

| Year | Filings |
|------|---------|
| 2018 | 889 |
| 2019 | 856 |
| 2020 | 922 |
| 2021 | 53 |
| 2022 | 2 |
| 2023 | 0 |
| 2024 | 3 |
| 2025 | 4 |

In 2021, DOB migrated most alteration filings from the legacy systems to DOB NOW. The 50-plus 2021 records in the legacy system are the tail end of grandfathered jobs. Post-2020 combinations still happen — they're just not separately identifiable in the public data.

For this reason, **the map is hard-capped at 2000–2020** and the controls do not let users extend the year range beyond 2020. Including 2021+ would give a misleading picture of a "collapse" in combinations that is really a data-system artifact.

## Fields used

From the source dataset:

- `job__` — DOB job number (unique filing ID)
- `job_type` — A1, A2, A3 (alteration types), or other
- `job_status_descrp` — human-readable status, e.g., "SIGNED-OFF," "PERMIT ISSUED - ENTIRE JOB/WORK"
- `job_description` — free-text description used to identify combinations
- `borough`, `house__`, `street_name` — address
- `gis_latitude`, `gis_longitude` — geographic coordinates (DOB-provided)
- `gis_nta_name` — Neighborhood Tabulation Area
- `pre__filing_date` — when the application was submitted (used as the "filing year")
- `existing_dwelling_units`, `proposed_dwelling_units` — unit counts before and after. **Unreliable**: many filers list building-wide counts rather than the specific change, so this is shown in pop-ups but not used for filtering.
- `initial_cost` — estimated cost of work at filing

## Summary statistics shown

- **Total:** simple count of mapped records.
- **Average filed cost:** arithmetic mean of `initial_cost` across all records where cost > 0 (21,546 of 21,665). Filed cost is the applicant's own estimate at time of filing and is widely understood to be lowballed to reduce permit fees. Treat it as rough order of magnitude, not true project cost.
- **Share in Manhattan:** `Manhattan filings / total filings`. Manhattan accounts for 85% (18,385 of 21,665).
- **Top neighborhoods:** counted by `gis_nta_name` within the current filter.

## Known limitations, in one place

1. Free-text search misses combinations that don't use the word "combine."
2. Post-2020 combinations are not identifiable in the public DOB NOW data.
3. Filed cost is an applicant estimate and routinely understated.
4. Unit-count fields (`existing_dwelling_units`, `proposed_dwelling_units`) are inconsistently reported — not used for filtering.
5. Filings are not combinations completed. A filing means a permit was applied for. Status may be "signed off" (work done), "permit issued" (in progress), "withdrawn," or similar. The "Signed off only" filter narrows to filings explicitly marked as signed off.
6. Geographic coordinates come from DOB, not re-geocoded. Seven records (~0.03%) had no coordinates and are excluded.

## Reproducibility

The fetch script (`fetch_data.py` in this directory) pulls fresh data from the Socrata API and writes `data/combinations.geojson` plus `data/summary.json`. Run:

```bash
python3 fetch_data.py
```

No dependencies beyond Python 3's standard library.
