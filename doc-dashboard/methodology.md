# NYC jail performance dashboard: methodology

## Overview

This dashboard tracks conditions in New York City jails operated by the Department of Correction (DOC), with a focus on population, violence, staffing, medical access, and in-custody deaths. Data is updated automatically via NYC Open Data APIs and a daily news scanner.

## Data sources

### Automated (updated daily via scheduled task)

| Metric | Source | Dataset ID | API endpoint | Update lag |
|---|---|---|---|---|
| Jail population (live count) | NYC Open Data: Daily Inmates In Custody | `7479-ugqb` | `data.cityofnewyork.us/resource/7479-ugqb.json` | Real-time (today's snapshot) |
| Population by legal status | Same dataset, grouped by `inmate_status_code` | `7479-ugqb` | Same endpoint | Real-time |
| Assaults on staff | NYC Open Data: Inmate Assault on Staff | `erra-pzy8` | `data.cityofnewyork.us/resource/erra-pzy8.json` | ~1 month |
| Fights (inmate-on-inmate) | NYC Open Data: Inmate Incidents - Inmate Fights | `k548-32d3` | `data.cityofnewyork.us/resource/k548-32d3.json` | ~1 month |
| Stabbings/slashings | NYC Open Data: Inmate Incidents - Slashing and Stabbing | `gakf-suji` | `data.cityofnewyork.us/resource/gakf-suji.json` | ~1 month |
| In-custody deaths | Daily news scan (Gothamist, THE CITY, PIX11, NY Post, NY Daily News, NY Times, ABC7) | N/A | N/A | Same day |

### Manual (updated periodically)

| Metric | Source | Notes |
|---|---|---|
| Historical population (pre-2026 monthly) | NYC Comptroller DOC Dashboard | 1st-of-month snapshots by facility |
| Historical deaths (2000-2018 annual) | NYC DOC Annual Reports; Federal Monitor Second Status Report (Oct 28, 2022) | Page 19 of federal monitor report covers 2015-2021 |
| Individual death records (2019-2025) | NYC Comptroller DOC Dashboard; Vera Institute of Justice; Board of Correction FOIL records | Name, age, date, facility, race, cause |
| Average length of stay | NYC Comptroller DOC Dashboard | Monthly average days in custody |
| Admissions and discharges | NYC Comptroller DOC Dashboard | Monthly flow in/out |
| Staffing (sick rate, medically restricted) | NYC Comptroller DOC Dashboard | No automated source available; quarterly snapshots |
| Medical missed appointments | NYC Open Data (`5n4h-km5r`) | Quarterly, coarse granularity, last updated 2025 |
| Use of force (A/B/C) | NYC Comptroller DOC Dashboard | The Open Data aggregate dataset (`2wuc-x56b`) has been dead since 2021 |

## Calculations

### Violence rates
All violence metrics (assaults, fights, stabbings) are displayed as rates per 1,000 average daily population (ADP) to allow comparison across months with different jail sizes:

```
rate = (incident count / population) * 1,000
```

Population for the rate denominator comes from the population series for the matching month.

### Death mortality rate
Annual mortality rate per 1,000 ADP:

```
rate = (annual deaths / annual ADP) * 1,000
```

### Population count methodology
The live population count from dataset `7479-ugqb` includes all people in DOC custody regardless of legal status:
- **DE** -- Pre-trial detainee (typically ~86% of population)
- **DEP** -- Detainee pending
- **DPV** -- Detainee parole violator
- **CS** -- City sentence (serving a sentence of 1 year or less)
- **CSP** -- City sentence parolee
- **SSR** -- State sentence ready (awaiting transfer to state prison)
- **DNS** -- Detained, not sentenced

This matches how DOC officially reports its population. The vast majority of people in NYC jails have not been convicted and are awaiting trial.

### Incident data completeness
The incident datasets (assaults, fights, stabbings) are incident-level records with date fields. The update script only includes **complete months** -- it excludes the current partial month to avoid showing artificially low counts. Once a month ends, its data typically appears in the API within 2-4 weeks.

### Current year deaths
Deaths in the current year are tracked via a daily automated news scan. They are stored separately in `currentYear.deaths` and dynamically merged into charts and the "Their names" section at render time. At year-end, these must be manually moved to the `historical` and `individuals` arrays.

## Automation

### Update script
`doc-dashboard/update-data.py` fetches from the four Socrata APIs and updates three data files:
- `doc-dashboard/data.json` (main dashboard data)
- `doc-dashboard/deaths-data.json` (death tracker data used by dashboard)
- `rikers-death-tracker/data.json` (standalone death tracker)

The script is invoked daily by the `rikers-death-check` scheduled task, which also scans news for new deaths.

### What the script does NOT update
- Historical monthly population (the live dataset is a snapshot, not a time series -- discharged people are removed)
- Use of force (no reliable automated source)
- Staffing metrics (no time-series dataset on Open Data)
- Medical missed appointments (quarterly, not automated)
- Length of stay (derivable from live data but computationally heavy)

### Population data limitation
Dataset `7479-ugqb` is a **live daily snapshot**: it contains one row per person currently in custody. When someone is discharged, their row is removed from the dataset entirely. This means you can accurately count today's population, but you cannot reconstruct what the population was on any past date. Historical monthly population figures come from the NYC Comptroller DOC Dashboard, which maintains its own time series.

## Files

| File | Purpose |
|---|---|
| `doc-dashboard/data.json` | All dashboard metrics (population, violence, staffing, medical, cards) |
| `doc-dashboard/deaths-data.json` | Death data (historical, monthly, individuals, current year) |
| `doc-dashboard/index.html` | Dashboard visualization (self-contained, inline JS/CSS) |
| `doc-dashboard/update-data.py` | Automated data update script |
| `doc-dashboard/methodology.md` | This file |
| `rikers-death-tracker/data.json` | Death tracker data (kept in sync with deaths-data.json) |
| `rikers-death-tracker/index.html` | Standalone death tracker visualization |

## Limitations

1. **Population backfill**: Cannot automatically fill in past months' population from the live dataset. Depends on Comptroller Dashboard for historical time series.
2. **Use of force**: The LL33 aggregate dataset on Open Data has been abandoned since 2021. UOF data comes from the Comptroller Dashboard and must be updated manually.
3. **Staffing**: No Open Data time series for sick rates or medically restricted staff. Current values are quarterly snapshots from the Comptroller Dashboard.
4. **Death identification**: The daily news scanner depends on media coverage. Deaths that are not reported in the press may be missed until official sources (Board of Correction, Comptroller Dashboard) update.
5. **Incident lag**: Violence data (assaults, fights, stabbings) typically lags 1-2 months behind the current date.
6. **Year-end rollover**: When a new year begins, current-year deaths must be manually migrated to the historical arrays.
