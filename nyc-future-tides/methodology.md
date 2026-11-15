# The tide line: methodology

Built Nov. 15, 2026.

## Sources

| What | Where | Notes |
|---|---|---|
| Future high tide layers, 2030s–2150s | NYC Open Data [xbxf-ev5m](https://data.cityofnewyork.us/d/xbxf-ev5m), file `nyc_future_high_tide_sea_level_rise.gdb.zip` | Mayor's Office of Climate and Environmental Justice (MOCEJ). Posted Sept. 21, 2026; marked public Nov. 13, 2026. Five layers. |
| Future floodplain layers, 2030s–2150s | NYC Open Data [29fz-v4rp](https://data.cityofnewyork.us/d/29fz-v4rp), file `nyc_future_floodplain_sea_level_rise.gdb.zip` | Same office and dates. Ten layers: 1% and 0.2% annual chance storms for five decades. |
| Methodology documents | Attachments on the two datasets above | Quoted below. |
| Tax lots and housing units | PLUTO, NYC Open Data [64uk-42ks](https://data.cityofnewyork.us/d/64uk-42ks), version 26v2 | Fields used: `bbl`, `borough`, `unitsres`, `xcoord`, `ycoord`. |
| Neighborhoods | 2020 Neighborhood Tabulation Areas, [9nt8-h7nd](https://data.cityofnewyork.us/d/9nt8-h7nd) | City Planning, clipped to the shoreline. |
| City line | Borough Boundaries (water areas included), [wh2p-dxnf](https://data.cityofnewyork.us/d/wh2p-dxnf) | Used to clip the flood layers, which extend into New Jersey in places. |

## What the layers assume

From the city's methodology documents:

- Sea-level rise is the 90th-percentile projection of the fourth New York City Panel on Climate Change (NPCC4, April 2024): **13 inches for the 2030s, 23 for the 2050s, 45 for the 2080s, 65 for the 2100s and 177 for the 2150s.** These are high-end values; the panel's central estimates are lower.
- **High tide** is mean higher high water (MHHW) for the 1992 tidal epoch from NOAA's VDatum 4.5.1, raised to 2014 using the observed local rate of rise, then raised again by the projected rise. MHHW is the average height of the higher of each day's two high tides.
- **Storm floodplains** start from base flood elevations in FEMA's 2015 preliminary flood insurance rate map (PFIRM), plus the projected rise. The 1% layer includes wave effects; the 0.2% layer uses stillwater elevation only.
- Ground elevation is FEMA Region 2's 10-foot digital elevation model from the NY/NJ Coastal Restudy.
- The method is a static "bathtub": water fills any land connected to the shoreline that sits below the water level. Low inland pockets with no connection to the shore are left dry.
- The city lists what the model leaves out: erosion, land subsidence, groundwater, rainfall and drainage, future construction and defenses. Piers and wharves missing from the elevation model can appear flooded. The city says the layers are for information only and lack the precision for site-level planning.

## Steps

1. Download both geodatabases, PLUTO (`$select=bbl,address,borough,unitsres,unitstotal,bldgclass,landuse,xcoord,ycoord,yearbuilt,version`, paged 50,000 rows at a time), the NTA GeoJSON and the borough boundaries. Raw files live outside the repo in `~/.vital-city/flood-dl/`.
2. `build/build_lots.py`
   - Each layer is one multipolygon in EPSG:6539 (high tide in 2263). Reproject to EPSG:2263, repair with `make_valid`, clip to the five boroughs.
   - Area in square miles = polygon area in square feet / 27,878,400.
   - Make a point for every PLUTO lot from `xcoord`/`ycoord` (857,347 of 858,284 lots have them) and test which layers contain it.
   - For each lot and each line (high tide, 100-year, 500-year), record the first decade whose layer contains it.
   - Homes = sum of `unitsres` over lots inside a layer.
   - Spatially join lots to 2020 NTAs for the neighborhood list.
   - Check that layers nest. A handful of lots fall inside an earlier decade but not the next one (2 for high tide, 12 for the 100-year, 10 for the 500-year), from tiny differences in polygon edges. They are left as the source has them.
   - Writes `data/summary.json` and `data/lots/{1-5}.json`. Each lot file maps BBL to a three-digit code: high-tide decade, 100-year decade, 500-year decade, each as 1–5 for the 2030s–2150s and 0 for never.
3. `build/build_tiles.py` simplifies each clipped layer to 6 feet, reprojects to WGS84 and runs tippecanoe (zooms 9–14) into `data/flood.pmtiles`. Simplification affects only the map, not the counts.

## Headline numbers (from `data/summary.json`)

| Decade | Rise | High tide: sq mi / homes | 100-year: sq mi / homes | 500-year: sq mi / homes |
|---|---|---|---|---|
| 2030s | 13 in. | 5.3 / 844 | 54.9 / 278,220 | 72.7 / 448,740 |
| 2050s | 23 in. | 6.9 / 1,218 | 61.4 / 320,253 | 78.0 / 503,002 |
| 2080s | 45 in. | 12.2 / 13,151 | 73.7 / 445,904 | 86.6 / 589,820 |
| 2100s | 65 in. | 21.4 / 62,987 | 82.4 / 537,313 | 93.5 / 683,506 |
| 2150s | 177 in. | 85.0 / 602,457 | 117.8 / 1,020,119 | 126.1 / 1,156,328 |

PLUTO 26v2 counts 3,735,269 residential units citywide, so the 2150s high-tide figure is 16.1%.

## Limitations

- **Lot centers, not buildings.** A lot counts in full if its center point is inside a line and not at all if only its edge is. Large waterfront lots can count early because their centers sit on a bulkhead or pier; one Williamsburg lot with 333 units counts from the 2030s high-tide layer on that basis.
- **Homes are units, not people.** PLUTO `unitsres` counts residential units of any kind, occupied or not.
- **Today's buildings.** The counts put today's housing under future water. They do not model what gets built, raised, protected or abandoned.
- **No present-day baseline.** The city did not publish a current-sea-level layer in this set, so the page compares future decades to one another.
- **Address lookup.** NYC GeoSearch returns the address point and its BBL. The page reports the earliest decade from either the lot file or the map polygons at that point. Condominium units may carry a BBL that differs from the PLUTO lot.
