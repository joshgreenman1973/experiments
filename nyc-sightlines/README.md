# Sightlines

An interactive map of which of 16 New York City landmarks a person can see from every street, sidewalk and park in the five boroughs. Hover or tap anywhere to see sightlines drawn to each landmark in view, plus a panorama of what's on the horizon from that spot, with distances, bearings and a Street View link facing the landmark.

## How it works

1. **Surface model** (`pipeline/build_dsm.py`). A 3 m grid in UTM 18N covering the city and the New Jersey shore. It combines the USGS 1/3-arc-second DEM with 1.96 million building footprints and heights from Overture Maps (OpenStreetMap, which carries NYC's measured heights, plus Microsoft's ML heights). It also adds an 18 m canopy for mapped woods of 1 hectare or more. Borough codes come from NYC Planning's shoreline-clipped `nybb`. `pipeline/fix_boro.py` then gives piers that touch only Brooklyn or Queens to those boroughs.
2. **Public ground** (`pipeline/public_ground.py`). Street rights-of-way, from Overture road centrelines buffered to typical NYC half-widths, plus parks, plazas and beaches.
3. **Viewsheds** (`pipeline/viewshed.py`). Radial line-of-sight from each landmark at three heights, with earth curvature and refraction (k = 0.13) and an eye height of 1.6 m. Each cell is judged by the ray nearest its own bearing. Each landmark's own structure is removed first, and bridge points snap to the mapped towers.
4. **Validation** (`pipeline/validate.py`). Exact point-to-point checks on 4,000 random cells per landmark: 99.4–99.7% agreement on whether the top is visible.
5. **Analysis** (`pipeline/analyze.py`). Coverage by landmark, borough and neighbourhood (2010 NTAs dissolved from NYC Planning tracts by `pipeline/nta_from_tracts.py`), best spots and longest sightlines.
6. **Tiles and page** (`pipeline/export_tiles.py`, `pipeline/build_site.py`, `web/template.html`). The output is gzip'd 1024² byte-plane tiles at 3, 6, 12 and 24 m. A WebGL 2 shader decodes the 2-bit-per-landmark visibility on the GPU. The page is self-contained: no map library and no external tiles.

Run order: `build_dsm → fix_boro → public_ground → viewshed → validate → analyze → export_tiles → build_site`. Each script's docstring gives its arguments. Raw inputs come from Overture's public S3 bucket (release 2026-09-23.1), USGS 3DEP on S3, and the `nycehs/NYC_geography` repository.

## Limits

Street trees, bridges and elevated structures aren't obstacles. Treat the map as a winter view. Building data lags new construction, and ML heights can be off by a floor or two.
