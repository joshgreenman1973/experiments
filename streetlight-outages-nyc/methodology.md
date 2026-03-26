# 311 streetlight outage map: methodology and data reference

This document details every data source, filter, calculation and design decision in the streetlight outage map. Nothing is a black box.

---

## 1. Data source

**Dataset:** NYC 311 Service Requests
**Publisher:** NYC Open Data
**Socrata endpoint:** `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
**Documentation:** https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9

The 311 dataset contains every service request filed through NYC's 311 system. Each record includes a complaint type, descriptor, location (address, borough, community board, latitude, longitude), timestamps and status.

**Date range queried:** Jan. 1, 2024 through the current date (the query uses `created_date > '2024-01-01T00:00:00'`).

**Fields retrieved per record:**

| Field | Description | Example |
|---|---|---|
| `descriptor` | Specific complaint subtype | "Street Light Out" |
| `created_date` | When the complaint was filed | "2024-06-15T14:23:00.000" |
| `latitude` | Latitude of the complaint | 40.6782 |
| `longitude` | Longitude of the complaint | -73.9442 |
| `incident_address` | Street address | "123 ATLANTIC AVE" |
| `borough` | Borough name | "BROOKLYN" |
| `community_board` | Community board code | "02 BROOKLYN" |
| `status` | Complaint status | "Open" or "Closed" |

**API query (Socrata SoQL):**
```
$where=complaint_type='Street Light Condition' AND created_date>'2024-01-01T00:00:00' AND latitude IS NOT NULL
$select=descriptor,created_date,latitude,longitude,incident_address,borough,community_board,status
$limit=5000
$offset=[paginated: 0, 5000, 10000, ...]
$order=created_date DESC
```

Records are fetched in batches of 5,000 with 150ms delays between batches. If a batch fails, the app retries up to 3 times with exponential backoff (1s, 2s, 3s). Results are cached in the browser's localStorage for 6 hours to speed up repeat visits.

---

## 2. Filtering: what's included

Only complaints whose `descriptor` field exactly matches one of these eight values are included:

1. Street Light Out
2. Multiple Street Lights Out
3. Street Light Lamp Dim
4. Street Light Lamp Missing
5. Fixture/Luminaire Out Of Position
6. Fixture/Luminaire Damaged
7. Fixture/Luminaire Missing
8. Flood Light Lamp Out

All eight fall under the umbrella complaint type "Street Light Condition." Other complaint types in the same category (e.g., "Street Light Cycling On and Off") are not included because they don't indicate a dark condition.

**What these descriptors mean:** These are complaints about pole-mounted streetlights that illuminate public streets and sidewalks. Traffic signals and pedestrian signals have entirely separate 311 categories ("Traffic Signal Condition") and are not included.

---

## 3. Filtering: what's excluded

After retrieving complaints matching the descriptors above, the app applies a second filter on the `incident_address` field. Any complaint whose address contains one of the following words (case-insensitive, whole-word match) is excluded:

**Parks and green spaces:** park, playground, recreation, meadow(s), greenbelt, botanical, garden, field

**Waterfront and bridges:** bridge, greenway, esplanade, pier, boardwalk, beach, river, promenade

**Highways and expressways:** pkwy, parkway, expwy, expressway, expy, highway, hwy, turnpike, tpke, interchange, overpass, ramp

**Named expressways:** FDR, Deegan, Bruckner, BQE

**Other non-street locations:** cemetery, stadium, island, plaza

**Why exclude these?** The map focuses on streetlights that illuminate ordinary streets and sidewalks where people walk and drive at night. Park lights, highway lights and bridge lights are maintained by different agencies (NYC Parks, DOT highway division) and serve different purposes. Including them would muddy the picture.

**What this means in practice:** A complaint at "123 ATLANTIC AVE" passes the filter. A complaint at "PROSPECT PARK WEST AND PARK CIRCLE" is excluded because it contains "park." A complaint at "FDR DRIVE AND E 62 ST" is excluded because it contains "FDR."

**Known limitation:** This is pattern-based, not perfect. A complaint at "123 PARK AVE" would be incorrectly excluded because the address contains "park." A complaint at a location inside a park but filed with a regular street address would be incorrectly included. For the vast majority of complaints, the filter works correctly.

---

## 4. Location clustering

The 311 data provides latitude and longitude to ~6 decimal places. But multiple complaints about the same dark streetlight often have slightly different coordinates (because GPS is imprecise and people report from different spots nearby). To group these into meaningful locations, the app rounds coordinates to a grid.

**Rounding formula:**
```
roundedLat = (Math.round(lat * 2000) / 2000).toFixed(4)
roundedLng = (Math.round(lng * 2000) / 2000).toFixed(4)
```

This rounds to the nearest 0.0005 degrees, which equals roughly **55 meters (180 feet) north-south** and roughly **42 meters (138 feet) east-west** at NYC's latitude (~40.7 degrees N).

Each unique `roundedLat,roundedLng` pair becomes one "location." All complaints that round to the same grid point are grouped together. The displayed position for each cluster is the **average** of all complaint coordinates in that group (not the rounded center), so dots appear at the true centroid of reports.

**This clustering is used in:**
- The "all spots" view (point layer)
- The chronic dark spots views (10+ and 20+)
- The "worst repeat locations" ranking
- The "repeat locations" stat in the summary box

---

## 5. Views and how they work

### 5a. Hex grid

Uses Uber's H3 hexagonal spatial indexing library at **resolution 8**.

**What resolution 8 means:** Each hexagonal cell covers approximately **0.74 square kilometers (0.29 square miles)**, with an edge length of roughly **460 meters (1,500 feet)**. This is comparable to a few city blocks.

**How it works:** For each complaint, the app calls `h3.latLngToCell(lat, lng, 8)` to assign it to a hex cell. It then counts complaints per cell and draws each cell as a polygon on the map.

**Color scale (fill colors by complaint count in that hex cell):**

| Complaints | Fill color | Opacity |
|---|---|---|
| 1-7 | Dark olive | 0.08 |
| 8-19 | Muted olive | 0.20 |
| 20-39 | Dark amber | 0.35 |
| 40-64 | Amber-orange | 0.50 |
| 65-89 | Red-orange | 0.70 |
| 90-119 | Deep red | 0.85 |
| 120+ | Bright red | 0.95 |

These breakpoints were set manually after examining the distribution of complaints per hex cell. The comment in the code notes the distribution: p10=7, p25=20, p50=42, p75=68, p90=94, max=189.

**Popup contents (click a hex cell):** Total complaints, neighborhood name, borough, number still open, and the top 3 addresses within that cell.

### 5b. All spots (point layer)

Plots every clustered location (see section 4) as a circle marker.

**Point size by complaint count:**

| Complaints | Radius (pixels) |
|---|---|
| 1 | 2.5 |
| 2-3 | 4 |
| 4-9 | 6 |
| 10+ | 8 |

**Point color by complaint count:**

| Complaints | Color |
|---|---|
| 1 | #f0b429 (amber) |
| 2-3 | #db6d28 (orange) |
| 4-9 | #f85149 (red) |
| 10+ | #da3633 (dark red) |

Points with 3+ complaints also get a slightly thicker white stroke (1.5px vs. 0.5px).

**Popup contents:** Address, neighborhood, borough, complaint count, open/closed status, and breakdown by complaint descriptor.

### 5c. Chronic dark spots (10+ and 20+)

These views show only locations where the total complaint count meets the threshold (10 or more, or 20 or more). They use the same location clustering as the point layer (section 4).

**Visual treatment:**
- **Pulsing ring:** Each chronic location has an animated expanding ring that fades out, creating a radar-pulse effect. The pulse speed varies by complaint count: faster pulse = more complaints.
  - Pulse speed formula: `Math.max(0.6, 2.5 - (count - 4) * 0.08)` seconds per cycle
  - Range: 2.5 seconds (slow, ~10 complaints) down to 0.6 seconds (fast, ~28+ complaints)
  - Two rings are staggered at half the period for a continuous effect.
- **Solid circle:** Radius scales with count: `Math.min(3 + count * 0.3, 10)` pixels, capped at 10.
- **Color:** #da3633 (dark red) for 15+ complaints, #f85149 (red) for 8-14, #db6d28 (orange) for fewer.
- **White stroke:** 2px, for visibility against the dark basemap.

**Toggle behavior:** The chronic buttons act as toggles. Clicking "10+ complaints" switches to that view; clicking it again returns to whichever base view (hex grid or all spots) was previously active.

**Popup contents:** Same as the point layer, plus a "chronic dark spot" label and a list of which years have complaints at that location.

---

## 6. Rankings

### 6a. By address

Groups all complaints by `incident_address` (the raw text from the 311 data, not the rounded coordinates). Lists the top 15 addresses by complaint count, showing only those with 2+ complaints. Clicking an address flies the map to its coordinates.

### 6b. By census tract

Groups all complaints by their assigned 2020 census tract (see section 7 below). Lists the top 20 tracts by total complaint count. Each entry shows the tract number, NTA (Neighborhood Tabulation Area) name, and count. Clicking flies to the average coordinate of complaints in that tract.

### 6c. Per square mile (by census tract)

Same as 6b, but instead of raw count, ranks by **complaints per square mile**:

```
density = complaint_count / tract_area_in_square_miles
```

Where `tract_area_in_square_miles = shape_area / 27,878,400` (since the `shape_area` field from NYC Open Data is in square feet, and 1 square mile = 27,878,400 square feet).

**Noise filter:** Tracts with fewer than 3 complaints are excluded from this view to prevent tiny tracts with 1-2 complaints from producing misleadingly high per-square-mile rates.

---

## 7. Census tract assignment

### 7a. Data source

**Dataset:** 2020 Census Tracts
**Publisher:** NYC Open Data
**Socrata endpoint:** `https://data.cityofnewyork.us/resource/63ge-mke6.geojson`
**Documentation:** https://data.cityofnewyork.us/City-Government/2020-Census-Tracts/63ge-mke6

The raw GeoJSON was downloaded in three paginated batches (1,000 records each, 2,325 tracts total), then simplified and saved as a static file (`census-tracts.json`) hosted in the repository.

**Simplification steps applied to the raw data:**
1. Coordinate precision reduced from ~15 decimal places to 4 decimal places (~11 meter accuracy).
2. Point reduction: every third point in each polygon ring is kept (minimum 4 points per ring), with the ring always properly closed.
3. Only four property fields are retained per tract: `ctlabel` (tract number), `boroname` (borough), `ntaname` (Neighborhood Tabulation Area name), and `shape_area` (area in square feet).

**Result:** 1.5 MB static file vs. ~9 MB raw, loads in under a second from GitHub Pages CDN.

### 7b. Spatial assignment algorithm

Each complaint is assigned to a census tract using a two-step process:

**Step 1: Bounding box filter.** For each of the 2,325 census tracts, a bounding box (min/max latitude and longitude) is pre-computed when the tract data loads. For each complaint, only tracts whose bounding box contains the complaint's coordinates are tested further. This typically reduces the candidate set from 2,325 to 5-15 tracts per complaint.

**Step 2: Ray-casting point-in-polygon test.** For each candidate tract, the algorithm casts a horizontal ray from the complaint's coordinates and counts how many times it crosses the tract's polygon boundary. If the count is odd, the point is inside the polygon.

The ray-casting algorithm (from the code):
```
for each polygon in the MultiPolygon:
  for each ring in the polygon:
    inside = false
    for each edge (i, j) in the ring:
      xi = ring[i][latitude], yi = ring[i][longitude]
      xj = ring[j][latitude], yj = ring[j][longitude]
      if the ray crosses this edge:
        inside = !inside
    if inside: return true
```

**What gets stored on each complaint after assignment:**
- `_tract`: Tract label (e.g., "234")
- `_tractBoro`: Borough name from the tract data
- `_tractNta`: NTA name (e.g., "Brownsville")
- `_tractArea`: Area in square feet

**Complaints that don't match any tract:** Some complaints fall in water, on jurisdiction boundaries or in areas not covered by census tracts. These are silently excluded from tract-based rankings but still appear in all other views.

---

## 8. Neighborhood names

Two different neighborhood name systems are used:

### 8a. Community board neighborhoods (hex grid, points, chronic spots)

Derived from the `community_board` field in the 311 data (e.g., "02 BROOKLYN"). A built-in lookup table maps all 59 community boards to common neighborhood names. For example:
- "03 BROOKLYN" = Bedford-Stuyvesant
- "05 BROOKLYN" = East New York/Cypress Hills
- "10 MANHATTAN" = Central Harlem

When multiple community boards appear in a hex cell or cluster, the one with the most complaints is used.

### 8b. NTA names (census tract rankings)

The census tract data includes NTA (Neighborhood Tabulation Area) names directly from the Census Bureau / NYC Department of City Planning. These are more granular than community board names and are used in the "census tract" and "per sq mi" rankings.

---

## 9. Summary statistics

The four stat cards at the top of the panel:

1. **Total complaints:** Simple count of all complaints that pass both filters (descriptor match + address exclusion).
2. **Repeat locations:** Count of clustered locations (section 4) that have 2 or more complaints.
3. **Still open:** Count of complaints where `status === 'Open'` in the 311 data.
4. **Worst spot:** The single `incident_address` with the highest complaint count, shown with its neighborhood name.

All four update when you change the borough filter.

---

## 10. Borough filter

The dropdown filters all views by the `borough` field in the 311 data. Options: All boroughs, Bronx, Brooklyn, Manhattan, Queens, Staten Island. When a borough is selected, the hex grid, point layer, chronic layers and all rankings are rebuilt using only complaints from that borough.

---

## 11. Caching

**Browser cache (localStorage):**
- Key: `311-streetlight-data`
- Contains: The full raw API response (before filtering), a version string (`2024-v3`) and a timestamp.
- Expires: After 6 hours.
- On a cached visit: The app loads instantly from cache, displays the map, then silently re-fetches from the API in the background and rebuilds all layers when the fresh data arrives.
- Cache version is incremented when the data structure changes, which forces a fresh fetch.

**Census tract file:** Loaded from `census-tracts.json` in the same directory. No expiration since census tract boundaries don't change.

---

## 12. Technical stack

| Component | Library/service | Version | Purpose |
|---|---|---|---|
| Map | Leaflet.js | 1.9.4 | Map rendering, markers, popups |
| Basemap tiles | CARTO dark_all | - | Dark-themed street map tiles |
| Hex grid | H3-js | 4.1.0 | Hexagonal spatial indexing |
| Fonts | Google Fonts (Inter) | - | UI typography |
| Hosting | GitHub Pages | - | Static file hosting |
| Data API | NYC Open Data (Socrata) | - | Live 311 complaint data |

The entire application is a single HTML file with no build step, no server-side code, no dependencies beyond the three CDN-hosted libraries (Leaflet, H3, Inter font).

---

## 13. Data files in this repository

| File | What it is | How it was generated |
|---|---|---|
| `index.html` | The complete application | Hand-coded |
| `census-tracts.json` | Pre-simplified 2020 census tract boundaries (2,325 tracts, 1.5 MB) | Downloaded from NYC Open Data endpoint `63ge-mke6.geojson` in 3 paginated batches, then coordinates simplified to 4 decimal places with point reduction, non-essential properties stripped |
| `about.md` | Short project summary | Hand-written |
| `methodology.md` | This document | Hand-written |

All 311 complaint data is fetched live from the NYC Open Data API at page load. No complaint data is stored in the repository.

---

## 14. Known limitations and caveats

1. **Address-based filtering is imperfect.** The word-matching exclusion filter can produce false positives (e.g., "Park Ave" is excluded because it contains "park") and false negatives (a park complaint filed with a nearby street address would be included).

2. **Location clustering is approximate.** The ~50-meter grid may group complaints about different streetlights that happen to be near each other, or may separate complaints about the same light that straddle a grid boundary.

3. **"Still open" reflects 311 status, not reality.** A complaint marked "open" in 311 may have already been fixed but not yet closed in the system. Conversely, a "closed" complaint may have been closed without the light actually being repaired.

4. **Census tract assignment can miss edge cases.** Complaints on tract boundaries or in water/unmapped areas won't be assigned to any tract. These still appear in hex grid and point views but are absent from census tract rankings.

5. **Data freshness depends on caching.** On a repeat visit within 6 hours, you see cached data (though the app silently refreshes in the background). For the absolute latest data, clear your browser cache or open in an incognito window.

6. **Census tract geometry is simplified.** Coordinates are rounded to 4 decimal places (~11m) and polygon rings are point-reduced. This means tract boundaries are approximate to within about 10-15 meters, which can misassign a small number of complaints near tract edges.

7. **No population normalization.** The "per square mile" ranking normalizes by area but not by population. A dense residential tract and an industrial tract of the same area are treated equally. Population-weighted analysis would require linking to American Community Survey data, which is not currently included.
