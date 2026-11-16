# The tide line: methodology

Built Nov. 15, 2026.

## Sources

| What | Where | Notes |
|---|---|---|
| Future high tide layers, 2030s–2150 | NYC Open Data [xbxf-ev5m](https://data.cityofnewyork.us/d/xbxf-ev5m), file `nyc_future_high_tide_sea_level_rise.gdb.zip` | Mayor's Office of Climate and Environmental Justice (MOCEJ). Posted Sept. 21, 2026; marked public Nov. 13, 2026. Five layers. |
| Future floodplain layers, 2030s–2150 | NYC Open Data [29fz-v4rp](https://data.cityofnewyork.us/d/29fz-v4rp), file `nyc_future_floodplain_sea_level_rise.gdb.zip` | Same office and dates. Ten layers: 1% and 0.2% annual chance storms for five decades. |
| Methodology documents | Attachments on the two datasets above | Quoted below. |
| Tax lots and housing units | PLUTO, NYC Open Data [64uk-42ks](https://data.cityofnewyork.us/d/64uk-42ks), version 26v2 | Fields used: `bbl`, `borough`, `unitsres`, `xcoord`, `ycoord`. |
| Neighborhoods | 2020 Neighborhood Tabulation Areas, [9nt8-h7nd](https://data.cityofnewyork.us/d/9nt8-h7nd) | City Planning, clipped to the shoreline. |
| City line | Borough Boundaries (water areas included), [wh2p-dxnf](https://data.cityofnewyork.us/d/wh2p-dxnf) | Used to clip the flood layers, which extend into New Jersey in places. |

## What the layers assume

From the city's methodology documents:

- Sea-level rise is the 90th-percentile projection of the fourth New York City Panel on Climate Change (NPCC4, April 2024): **13 inches for the 2030s, 23 for the 2050s, 45 for the 2080s, 65 for 2100 and 177 for 2150.** The city's files label the last two "2100s" and "2150s"; the panel's table gives them as single years, and the page follows the panel. The 90th percentile is the panel's high estimate: NPCC4 pools three IPCC scenarios with equal weight and reads percentiles off that pool, so it is not a stated probability.
- **High tide** is mean higher high water (MHHW) for the 1992 tidal epoch from NOAA's VDatum 4.5.1, raised to 2014 using the observed local rate of rise, then raised again by the projected rise. MHHW is the average height of the higher of each day's two high tides.
- **Storm floodplains** start from base flood elevations in FEMA's 2015 preliminary flood insurance rate map (PFIRM), plus the projected rise. The 1% layer includes wave effects; the 0.2% layer uses stillwater elevation only.
- Ground elevation is FEMA Region 2's 10-foot digital elevation model from the NY/NJ Coastal Restudy.
- The method is a static "bathtub": water fills any land connected to the shoreline that sits below the water level. Low inland pockets with no connection to the shore are left dry.
- The city lists what the model leaves out: erosion, land subsidence, groundwater, rainfall and drainage, future construction or changes in land use; the shoreline used includes existing coastal structures. Piers and wharves missing from the elevation model can appear flooded. The city says the layers are for information only and lack the precision for site-level planning.

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
| 2100 | 65 in. | 21.4 / 62,987 | 82.4 / 537,313 | 93.5 / 683,506 |
| 2150 | 177 in. | 85.0 / 602,454 | 117.8 / 1,020,119 | 126.1 / 1,156,328 |

PLUTO 26v2 counts 3,735,269 residential units citywide, so the 2150 high-tide figure is 16.1%.

## Pick a projection (NOAA layers)

The city's layers exist only for the panel's 90th-percentile projection. To show other projections, the "Pick a projection" tab uses a second set of maps.

| What | Where | Notes |
|---|---|---|
| Sea-level rise inundation, 0 to 10 feet | NOAA Office for Coastal Management, Sea Level Rise Viewer data, [NY_Metro_slr_data_dist.zip](https://coast.noaa.gov/htdata/Inundation/SLR/SLRdata/NY/NY_Metro_slr_data_dist.zip) (17.5 MB, file dated March 12, 2019; metadata dates the analysis 2017) | Layers `NY_M_slr_0ft` to `NY_M_slr_10ft`: areas connected to the ocean that sit below mean higher high water plus N feet. Layers `NY_M_low_*`: low spots below that level with no connection. NOAA calls the data "a screening-level tool." |
| Projections | NYC Panel on Climate Change (2024), NYC Open Data [38ps-fnsg](https://data.cityofnewyork.us/d/38ps-fnsg) | Sea-level rise for the 2030s, 2050s, 2080s, 2100 and 2150 at the 10th, 25th, 75th and 90th percentiles. The table has no 50th percentile, so the page has none. The 90th-percentile row matches the city's layers (13, 23, 45, 65, 177 inches). |
| Land | Borough Boundaries, shoreline clipped, NYC Open Data [gthc-hcne](https://data.cityofnewyork.us/d/gthc-hcne) | NOAA's polygons include open water; clipping to land leaves 302 square miles of city land to test against. |
| Battery tide gauge | NOAA Tides and Currents, station 8518750 | Monthly mean higher high water, 1983–2014 (CO-OPS data API, product `monthly_mean`, datum STND). Long-term trend 1.16 inches per decade (±0.02), 1856–2025. |
| Panel baseline | NPCC4, Braneon et al. 2024, *Annals of the New York Academy of Sciences*, doi 10.1111/nyas.15116, App. C.3 | "The baseline period is 1995−2014 for sea level rise." |

Projection table (inches of rise):

| Percentile | 2030s | 2050s | 2080s | 2100 | 2150 |
|---|---|---|---|---|---|
| 10th | 6 | 12 | 21 | 25 | 38 |
| 25th | 7 | 14 | 25 | 30 | 47 |
| 75th | 11 | 19 | 39 | 50 | 89 |
| 90th | 13 | 23 | 45 | 65 | 177 |

Steps (`build/build_noaa.py`):

1. For each foot from 0 to 10, take NOAA's connected layer, reproject to EPSG:2263, repair with `make_valid` and clip to the shoreline-clipped boroughs.
2. Count homes the same way as the city layers: PLUTO 26v2 lot centers inside the polygon, summing `unitsres`. NOAA keeps unconnected low spots over an acre as a separate "low-lying" layer because culverts, ditches and drains it does not model could connect them. Homes in that layer, minus any already in the connected layer, are reported separately and not added in. At low levels they outnumber the counted homes (1,748 against 538 at 0 feet; 5,854 against 2,464 at 3 feet).
3. Simplify to 6 feet for the web map and build `data/noaa.pmtiles` (zooms 9–14). Write `data/noaa.json` and, for the address lookup, `data/noaa_lots/{1-5}.json` (BBL to the first foot at which the lot center is under water).

Matching a projection to a NOAA layer:

- NOAA's 0 feet is mean higher high water for the 1983–2001 tidal epoch. The panel measures rise from 1995–2014 (NPCC4 App. C.3). At the Battery, monthly mean higher high water averaged 2.29 inches higher in 1995–2014 than in 1983–2001 (mean sea level: 2.05 inches). The page adds 2.3 inches to each projection before matching it to a NOAA layer. (The long-term trend of 1.16 inches per decade over the 12.5 years between midpoints would give 1.45 inches.) Every offset from 1.5 to 2.9 inches matches every cell of the table to the same foot; with no offset, 65 inches would map to 5 feet instead of 6 and 89 inches to 7 instead of 8.
- NOAA's maps come in whole feet, so each projection is shown at its nearest foot: feet = round((inches + 2.3) / 12). That moves a projection by up to about 6 inches, and the home count can change a lot between adjacent feet (35,686 at 5 feet, 80,259 at 6). When a reader picks a cell, the page shows the counts for the feet on both sides, and for 90th-percentile cells the city's own count for the same projection. A cell is shaded when its nearest foot is at or above the slider's.
- 177 inches (the 90th percentile for 2150) is beyond NOAA's 10-foot maps; the page says so.

Why the two sets of maps differ:

- Different elevation data and tidal surfaces. The city used FEMA Region 2's 10-foot elevation model and raised its 1992 high-tide surface to 2014. NOAA used its own elevation model and tidal surface from 2017.
- At the same rise, the two will not match exactly. Compare the city's 2050s layer (23 inches) with NOAA's 2-foot layer in `data/summary.json` and `data/noaa.json`.
- NOAA's maps are bathtub models too, with the same limits listed above.
- The 0-foot layer shows how much the lot-center rule interacts with where each source draws the shoreline. NOAA's map of today's high tide covers the centers of 574 lots. Of those, 290 first appear in the city's 2030s high-tide layer, 41 in later periods (10 in the 2050s, 10 in the 2080s, 11 in 2100, 10 in 2150) and 243 in none of the city's high-tide layers. Those 243 centers sit just outside the city's outline (median about 22 feet away in the fact-check measurement) and all are inside the city's 100-year floodplain. So the difference is mostly where the edge is drawn, not a different answer about elevation.
- At the same rise the counts differ. For the 90th-percentile 2100 projection (65 inches), the city's map counts 62,987 homes and 21.4 square miles; NOAA's 6-foot layer, the nearest, counts 80,259 and 29.0, and its 5-foot layer 35,686 and 22.0.
- Areas are not like-for-like across the tabs: the city layers were clipped to borough boundaries that include water (so piers and some water area count), the NOAA layers to the shoreline-clipped boundaries. Clipped to land only, the city's high-tide areas would be about 5.0, 6.5, 11.8, 20.9 and 84.5 square miles instead of 5.3, 6.9, 12.2, 21.4 and 85.0.

## Limitations

- **Lot centers, not buildings.** A lot counts in full if its center point is inside a line and not at all if only its edge is. Large waterfront lots can count early because their centers sit near the water. Two lots, 184 Kent Avenue in Williamsburg (333 units, center 53 feet from the shore) and 70 New Lane on Staten Island (277 units, 7 feet), are 610 of the 844 high-tide homes in the 2030s (72%) and 610 of 1,218 in the 2050s (50%).
- **Homes are units, not people.** PLUTO `unitsres` counts residential units of any kind, occupied or not.
- **Today's buildings.** The counts put today's housing under future water. They do not model what gets built, raised, protected or abandoned.
- **No present-day baseline.** The city did not publish a current-sea-level layer in this set, so the page compares future decades to one another.
- **Address lookup.** NYC GeoSearch returns the address point and its BBL. In both tabs the page reports the earliest level from either the lot file (lot center) or the map polygons at the address point. The two can differ by decades: 184 Kent Avenue counts from the 2030s by its lot center, while its address point is outside the city's high-tide line through the 2080s. Condominium units may carry a BBL that differs from the PLUTO lot.
