# Sightlines

An interactive map of which of 16 New York City landmarks a person can see from every street, sidewalk and park in the five boroughs, at street level (eyes 1.6 m above the ground). Hover or tap anywhere to see sightlines drawn to each landmark in view, plus a panorama of the horizon from that spot, with distances, bearings and a Street View link facing the landmark. Sunrise and Sunset tabs show where you can watch the sun come up or go down, by month, including Manhattanhenge.

Live: https://joshgreenman1973.github.io/experiments/nyc-sightlines/

How the 16 landmarks were chosen, and what that choice does to the numbers, is spelled out on the page ("Why these 16?"). The fact-check is documented in [FACTCHECK.md](FACTCHECK.md).

## How it works

1. **Surface model** (`pipeline/build_dsm.py`). A 3 m grid in UTM 18N covering the city and the nearby shore. It combines the USGS 1/3-arc-second DEM with 1.96 million building footprints and heights from Overture Maps. Of the 1.1 million buildings in the city, 99% have OpenStreetMap heights, which come from NYC's own data. The rest of the 1.96 million are in New Jersey, Westchester and Nassau, and more of their heights are Microsoft's machine-learned estimates.
   - Woods of 1 hectare or more get an 18 m canopy.
   - The Brooklyn Heights Promenade and the High Line are raised to deck height.
   - Borough codes come from NYC Planning's shoreline-clipped `nybb`. `fix_boro.py` gives piers that touch only Brooklyn or Queens to those boroughs, and `fix_outside.py` returns land in neighbouring counties to "outside".
2. **Public ground** (`pipeline/public_ground.py`). Street rights-of-way (Overture road centrelines buffered to typical NYC half-widths), parks, plazas and beaches.
   - Service roads and paths inside fenced industrial sites, rail yards, airports and power plants are excluded.
   - So are places closed to the public or open only by appointment or tour: Rikers Island, Hart Island and Freshkills Park, except separately mapped parks within it.
3. **Viewsheds** (`pipeline/viewshed.py`). Radial line-of-sight from each landmark at three heights, with earth curvature, refraction (k = 0.13) and an eye height of 1.6 m. Each cell is judged by the ray nearest its own bearing. Each landmark's own structure is removed first, and bridge points snap to the mapped towers.
4. **Validation** (`pipeline/validate.py`). Exact point-to-point checks on 4,000 cells per landmark, half from cells the fast method calls visible and half from the rest. Of the first half, 0.9–1.4% fail the exact check; of the second, at most 0.2% pass it.
5. **Analysis** (`pipeline/analyze.py`, `pipeline/label_places.py`).
   - Coverage by landmark, borough and neighbourhood. The neighbourhoods are 2010 NTAs, dissolved from NYC Planning tracts by `pipeline/nta_from_tracts.py`.
   - Best spots, longest sightlines (with a specific place name for each), and where the Statue of Liberty can be seen from.
6. **Sunrise and sunset** (`pipeline/sun.py`, `pipeline/sun_times.py`, `pipeline/sun_stats.py`).
   - For 8 maps (each of the solstices, five pairs of dates mirrored around them, and Manhattanhenge), the sun's path near the horizon is sampled at 13 apparent altitudes from 0.3° to 6°.
   - Each cell's horizon toward the sun is computed with an upper-hull sweep, and each cell keeps the lowest altitude at which it sees the sun.
   - `sun_times.py` adds clock times for the second date each map serves.
7. **Tour** (`pipeline/make_tour.py`, `pipeline/tour_stops.json`). Every number in the tour captions is computed from the data. The best spot at each stop is re-traced with an exact line of sight.
8. **Names** (`pipeline/map_labels.py`). Street names (merged by name into runs, with label anchors along them) and neighbourhood names from Overture, drawn when you zoom in. Zoomed in, the map switches to a street-map style: grey streets, dark buildings, green parks, blue water.
9. **Tiles and page** (`pipeline/export_tiles.py`, `pipeline/tiles_to_text.py`, `pipeline/build_site.py`, `web/template.html`).
   - Gzip'd 1024² byte-plane tiles at 3, 6, 12 and 24 m, stored as base64 text. Sun tiles are separate.
   - A WebGL 2 shader decodes the 2-bit-per-landmark visibility on the GPU.
   - The page is self-contained: no map library and no external tiles.
   - `build_site.py` writes `index.html`, the complete page that GitHub Pages serves, and `artifact.html`, the same page without the document wrapper, for the claude.ai artifact.

Run order: `build_dsm → fix_boro → fix_outside → public_ground → viewshed → validate → analyze → label_places → sun → sun_times → sun_stats → make_tour → map_labels → export_tiles → tiles_to_text → build_site`. Each script's docstring gives its arguments. Raw inputs come from Overture's public S3 bucket (release 2026-09-23.1), USGS 3DEP on S3, and the `nycehs/NYC_geography` repository.

## Limits

Everything is at street level: from a window, roof, bridge walkway or elevated train you would see far more.

Treat the map as a winter view. Street trees, bridges and elevated structures aren't modeled as obstacles. Building data lags new construction, and machine-learned heights can be off by a floor or two.

The longest sightlines clear the ground in between by a metre or two, which is within the model's margin of error.
