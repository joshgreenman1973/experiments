# Methodology: Public street seating across New York City (`nyc-where-to-sit`)

## Data sources

1. **New York City Department of Transportation (DOT) Seating Locations (`esmy-s8q5`)**
   - URL: <https://data.cityofnewyork.us/Transportation/Seating-Locations/esmy-s8q5>
   - Fetched Nov. 6, 2026: **5,776** unique `siteid` records, all with valid coordinates.
   - Subtype breakdown:
     - `BACKED`: 2,160 (`BACKED 1.0`: 1,194; `BACKED 2.0`: 938; `WORLDS FAIR`: 28)
     - `BACKLESS`: 2,160 (`BACKLESS 2.0`: 1,636; `BACKLESS 1.0`: 524)
     - `LEANING BAR`: 558 (angled bus-stop leaning rails without a horizontal seat)
     - `UNKNOWN BENCH`: 21
     - Blank `asset_subtype` / `installation_date` (`SEAT.2023.*` through `SEAT.2026.*`): 877 (`SEAT.2023`: 1; `SEAT.2024`: 472; `SEAT.2025`: 355; `SEAT.2026`: 49)

2. **New York City Department of City Planning (DCP) Privately Owned Public Spaces (`rvih-nhyn`)**
   - URL: <https://data.cityofnewyork.us/Housing-Development/Privately-Owned-Public-Spaces-POPS-/rvih-nhyn>
   - Fetched Nov. 6, 2026: **392** records with coordinates.
   - **217** explicitly list `Seating` or `Tables` in `amenities_required` (and 168 of those 217 list `24 Hours` in `hour_of_access_required`).
   - 366 of the 392 POPS (93.4%) and 208 of the 217 POPS with required seating (95.9%) are in Manhattan.

3. **DOT Pedestrian Plazas (`5dck-9m6g`)**
   - URL: <https://data.cityofnewyork.us/Transportation/Pedestrian-Plazas/5dck-9m6g>
   - Fetched Nov. 6, 2026: **90** polygon records represented by their geometric centroids.

4. **Shoreline-clipped 2020 Neighborhood Tabulation Areas (`nyc_nta_2020.geojson`) and 2020 Census population (`populations.json`)**
   - 262 shoreline-clipped NTA polygons (197 residential NTAs with `ntatype == "0"`, of which 177 have 2020 population ≥ 5,000).

## Walk-distance and neighborhood metrics

- **Public seat sites:** Defined as DOT street benches (excluding the 558 `LEANING BAR` records) plus the 217 POPS with required seating and the 90 DOT pedestrian plazas (**5,525** total sites; **6,083** when leaning bars are included).
- **Grid walk sampling:** Inside each shoreline-clipped 2020 NTA polygon, a regular grid of points (~0.0028 degrees, or ~250 meters apart) is sampled. At each sample point, straight-line haversine distance to the nearest public seat site (and to the nearest backed DOT bench) is multiplied by a **1.25×** Manhattan-grid street routing factor and converted to walking time at **3.0 mph** (20 minutes per mile).
- **What is excluded:** The New York City Department of Parks and Recreation does not publish a citywide park-bench point inventory on NYC Open Data; interior park benches are therefore not included in these street-level counts.

## Rebuilding the data

Run `python3 build_data.py` to regenerate `data/seating.json`, `data/nta_seating.geojson` and the three CSV files in `data/`.
