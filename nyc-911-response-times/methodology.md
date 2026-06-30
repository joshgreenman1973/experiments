# Methodology: NYC 911 response times

This dashboard measures **911 response time** — the interval between when an NYPD call-for-service job is entered into the dispatch system (`add_ts`) and when the first responding unit arrives on scene (`arrivd_ts`). It is the same general metric NYPD uses internally to report response time.

## Data source

- **Dataset**: NYPD Calls for Service (Year to Date)
- **Dataset identifier**: `n2zq-pubd`
- **Endpoint**: `https://data.cityofnewyork.us/resource/n2zq-pubd.json`
- **Publisher**: NYC Police Department
- **Update frequency**: Daily

Precinct boundaries come from the NYC Police Precincts dataset (`y76i-bdw7`).

## Fields used

| Field | Description |
|---|---|
| `add_ts` | Timestamp when the job was added to the dispatch queue |
| `arrivd_ts` | Timestamp when the first unit arrived on scene |
| `nypd_pct_cd` | NYPD precinct number (1-123) |
| `typ_desc` | Call-type description (e.g., "DISPUTE: INSIDE") |
| `boro_nm` | Borough name |
| `cip_jobs` | "CIP" = Critical Incident Program (priority emergency), "Non CIP" = everything else |

## What is a precinct?

NYC is divided into 77 NYPD patrol precincts (numbered 1-123 with gaps). Each precinct is the operational unit responsible for first response to calls within its boundary. Precincts do not align with community districts, school districts, or zip codes.

## Calculation methodology

### Response time

```
response_time_minutes = (arrivd_ts - add_ts) / 60_000
```

A call entered at 9:00:00 PM and met by a unit at 9:08:30 PM has a response time of 8.5 minutes.

### What "response time" means here

This is the time from when the dispatch system received the job to when the first NYPD unit arrived on scene. It is not:

- The total length of time you waited on the line with the 911 operator before that — call-taking time happens before `add_ts`.
- Time from when the incident occurred — the public's 911 call comes after the incident.
- Time to resolution — `closng_ts` (closing time) is typically much later than arrival.

The dataset's `closng_ts` field exists but reflects administrative case closing, not a meaningful "resolved" event, so this dashboard does not use it.

### Median vs. mean

This dashboard uses the **median**. NYPD response times have a long right tail — most jobs close fast, a small share take an hour or more — so the median better represents the typical experience than the mean would.

### Outlier handling

Records where the computed response time is negative (clearly a data error) or greater than 12 hours (almost always a closeout artifact, not a real wait) are dropped before any aggregation. NYPD's own response-time metric similarly caps far below half a day.

### Precinct aggregation

Calls are grouped by `nypd_pct_cd`. Precincts with fewer than 5 calls in the selected window are excluded from charts and the map.

### Map choropleth

The map colors each precinct relative to the current citywide median response time (`M`) for the selected filters. Using relative rather than fixed thresholds keeps the map readable whether the selection is a fast category (e.g. critical-priority alarms) or a slow one (e.g. quality-of-life complaints).

| Color | Threshold | Interpretation |
|---|---|---|
| Green | Under 0.67 × M | Much faster than citywide median |
| Yellow | 0.67 × M to 1.33 × M | Near citywide median |
| Orange | 1.33 × M to 2 × M | Slower than citywide median |
| Red | Over 2 × M | Much slower than citywide median |
| Gray | No data | Fewer than 5 calls in the time period |

### Call-type breakdown

The call-type chart shows response times for the **top 15 call types by volume** in the current selection, sorted by median response time. Selecting by volume (rather than by slowest) ensures very common categories are visible alongside slower outlier categories.

When a precinct is selected on the map, the call-type chart recalculates using only calls from that precinct.

## Sample size and date range

Each fetch paginates the Socrata API in 50,000-record chunks. Because 911 volume is roughly 5 million calls/year — much higher than 311 — the client uses a hard upper bound of **300,000 records per fetch** to keep load times manageable. The records returned are always the most recent matching the filter (ordered by `add_ts DESC`), so when the cap binds, more granular filters (a single call type, a single borough, a shorter date window) will show the same numbers based on the full universe.

Server-side filters:

- `typ_desc` matches the selected call type, or `cip_jobs='CIP'` when "All critical jobs" is selected
- `boro_nm` matches the selected borough (if filtered)
- `add_ts` falls within the selected time window (default: last 30 days)
- `add_ts` is not null
- `arrivd_ts` is not null

## Limitations

### Only calls with a recorded arrival are included

Calls that were cancelled before arrival, handled over the phone, or never closed out with an arrival timestamp are excluded entirely. If certain call types are disproportionately resolved without on-scene arrival, those will be undercounted here.

### "Arrived" reflects what dispatch records, not what you experienced

`arrivd_ts` is when the responding unit told dispatch they were on scene. In practice that's usually accurate within a minute or two of physical arrival, but it can be delayed if units are mid-task and update their status late.

### Call types are how NYPD categorizes the call, not the underlying event

A call labeled "INVESTIGATE/POSSIBLE CRIME: SERIOUS/OTHER" may turn out to be anything from a real emergency to an unfounded report. The dataset reflects how the call was coded at intake.

### Priority is not granular

The dataset only distinguishes "CIP" (Critical Incident Program — the highest priority) from "Non CIP" — it does not expose NYPD's full internal priority levels (1-10). Two non-CIP calls in the same category may have meaningfully different priority codes internally.

### Median can mask variation

The median hides spread. Two precincts with the same median may have very different distributions — one might respond consistently while another swings widely.

### Volume cap on broad queries

To keep page loads fast, queries with no call-type filter pull only the most recent 300,000 records. For "All call types, last 30 days, citywide," that's typically more than enough to be representative, but the very oldest part of the window may be slightly under-sampled. Filtering by call type or borough generally fetches the full universe.

### Reporting bias

This dataset captures calls that 911 dispatched as NYPD jobs. Not every situation generates such a call. Neighborhoods with different rates of 911 use will appear with different call volumes — and the underlying mix of call types will differ — for reasons that go beyond what's happening on the ground.

## Tools and libraries

- **MapLibre GL JS 3.x** for the precinct choropleth
- **Chart.js 4.x** with the annotation plugin for horizontal bar charts
- **Socrata Open Data API (SODA)** for data retrieval
- **CARTO Positron** basemap tiles
- All calculations performed client-side in JavaScript
