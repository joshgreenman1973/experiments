# Methodology: NYC agency response times

## Data source

This dashboard uses the **NYC 311 Service Requests** dataset from NYC Open Data, accessed via the Socrata Open Data API (SODA).

- **Dataset**: 311 Service Requests from 2010 to Present
- **Dataset identifier**: erm2-nwe9
- **Endpoint**: `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
- **Publisher**: NYC Department of Information Technology and Telecommunications (DoITT)
- **Update frequency**: Daily

Community district boundaries are loaded from the NYC Open Data community districts GeoJSON endpoint (`jp9i-3b7y`).

## Fields used

| Field | Description |
|---|---|
| `created_date` | Timestamp when the service request was opened |
| `closed_date` | Timestamp when the service request was closed |
| `complaint_type` | Category of the complaint (e.g., Noise - Residential, HEAT/HOT WATER) |
| `community_board` | Community district where the complaint originated (format: "01 MANHATTAN") |
| `borough` | Borough name (used for borough filtering) |
| `agency` / `agency_name` | City agency responsible for handling the complaint |
| `status` | Current status of the request (filtered to "Closed") |

## What are community districts?

New York City is divided into 59 community districts, each served by an advisory community board. Community boards are local representative bodies appointed by borough presidents and city council members. Each district covers a defined geographic area within a borough. This dashboard uses community districts as the geographic unit for comparing response times across neighborhoods.

## Calculation methodology

### Resolution time

Resolution time is calculated as:

```
resolution_time = closed_date - created_date
```

Expressed in days (fractional). A complaint opened at 9:00 AM and closed at 9:00 PM the same day would have a resolution time of 0.5 days.

### Median vs. mean

This dashboard uses **median** resolution time rather than mean (average). The median is the middle value when all resolution times are sorted. This choice was made because:

- 311 resolution times have highly skewed distributions, with some complaints taking months to resolve
- A single outlier (e.g., a complaint open for 200 days) can dramatically inflate a mean but has minimal effect on the median
- The median better represents the "typical" experience a resident has when filing a complaint

### Community district aggregation

Complaints are grouped by the `community_board` field in the 311 dataset. District labels are formatted as a two-letter borough abbreviation followed by the district number (e.g., "MN 03" for Manhattan Community District 3).

Districts with fewer than 5 complaints in the selected time period are excluded from charts and tables to avoid misleading results from small sample sizes.

### Map choropleth

The map colors each community district by its median resolution time using this scale:

| Color | Threshold | Interpretation |
|---|---|---|
| Green | Under 24 hours | Fast resolution |
| Yellow | 1-3 days | Moderate resolution |
| Orange | 3-7 days | Slow resolution |
| Red | Over 7 days | Very slow resolution |
| Gray | No data | Fewer than 5 complaints or no closed complaints in the time period |

### Agency breakdown

When a community district is selected on the map, the agency chart recalculates median response times using only complaints from that district. This shows which agencies are faster or slower in a specific neighborhood.

## Sample size and date range

Each data fetch requests up to 50,000 records from the API with these filters applied server-side:

- `complaint_type` matches the selected type (or all types if "All types" is selected)
- `borough` matches the selected borough (if filtered)
- `created_date` falls within the selected time period (default: last 30 days)
- `closed_date` is not null
- `status` equals "Closed"

Records are ordered by `created_date` descending. If more than 50,000 qualifying records exist for a given filter combination, the most recent 50,000 are used.

## Limitations

### Only closed complaints are included

Open and pending complaints are excluded entirely. This means the dashboard does not capture complaints that agencies have not yet resolved. If an agency systematically leaves difficult complaints open rather than closing them, their measured performance may appear artificially better than it actually is.

### "Closed" does not always mean "resolved"

The `closed_date` field reflects when the agency marked the complaint as closed in the system, not necessarily when the underlying issue was physically resolved. Some agencies may close complaints administratively -- for example, after an inspection finds no violation -- without fully addressing the problem the resident reported.

### Some complaint types rarely get formally closed

Certain categories of complaints have low closure rates. For these types, the data shown here represents only the subset that agencies did close, which may not be representative of the full volume of complaints filed.

### Median can mask variation

While the median reduces the impact of outliers, it can also obscure wide variation within a district. Two districts with the same median could have very different distributions -- one might resolve most complaints quickly with a few extreme outliers, while another might have consistently moderate response times.

### Community board field quality

- The `community_board` field is assigned based on the location provided in the complaint. Geocoding errors may assign some complaints to the wrong district.
- Some complaints have blank or "Unspecified" community board values. These are included in citywide statistics but excluded from the district-level breakdown and map.

### Sample size cap

The API returns a maximum of 50,000 records per query. For high-volume complaint types (especially "All types") over long time periods, this cap may exclude older records, biasing the sample toward more recent complaints.

### Reporting rates vary by neighborhood

311 data only captures complaints that are called in, submitted online, or reported via the 311 app. Issues that residents do not report are not reflected. Neighborhoods with lower 311 usage may appear to have fewer or faster-resolved problems than they actually do. Reporting rates vary by neighborhood, demographic group, and complaint type.

## Tools and libraries

- **MapLibre GL JS 3.x** for the interactive choropleth map
- **Chart.js 4.x** with the annotation plugin for horizontal bar charts
- **Socrata Open Data API (SODA)** for data retrieval
- **CARTO Positron** basemap tiles
- All calculations performed client-side in JavaScript
