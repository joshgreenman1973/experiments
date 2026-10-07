"""Assemble the static site: inline data into the page template and write the terrain grid.

Usage: python build_site.py GRID_DIR VS_DIR FINDINGS_JSON NTA_GEOJSON SITE_DIR DATA_DIR [SUN_DIR]
(tiles are written into SITE_DIR/tiles by export_tiles.py)
"""
import sys, os, json, gzip, numpy as np, geopandas as gpd
from pyproj import Transformer
import grid

G, VS, FIND, NTA, SITE, DATA = sys.argv[1:7]
SUN = sys.argv[7] if len(sys.argv) > 7 else None
here = os.path.dirname(os.path.abspath(__file__))
LMS = json.load(open(os.path.join(here, "landmarks.json")))
META = json.load(open(f"{VS}/meta.json"))
F = json.load(open(FIND))
to_utm = Transformer.from_crs("EPSG:4326", grid.CRS, always_xy=True)

def world(x, y):  # UTM -> page world metres (x east from grid west edge, y south from north edge)
    return round(x - grid.X0, 1), round(grid.Y1 - y, 1)

stats = {d["id"]: d for d in F["landmarks"]}
lms = []
for lm in LMS:
    pts = []
    for p in META[lm["id"]]:
        wx, wy = world(p["x"], p["y"])
        pts.append({"x": wx, "y": wy, "base": round(p["base"], 1), "H": [round(h, 1) for h in p["H"]]})
    s = stats[lm["id"]]
    lms.append({k: lm[k] for k in ["id", "name", "short", "borough", "year", "kind", "top", "levels", "height_ft", "height_note"]} | {"year_note": lm.get("year_note", "")} |
               {"pts": pts, "pct": s["pct"], "pct_most": s["pct_most"], "by_boro": s["by_boro"], "farthest": s["farthest"]})

# neighbourhood polygons, simplified, in world metres
nta = gpd.read_file(NTA).to_crs(grid.CRS)
nta["geometry"] = nta.geometry.simplify(15)
polys = []
for _, r in nta.iterrows():
    rings = []
    geoms = getattr(r.geometry, "geoms", [r.geometry])
    for g in geoms:
        xs, ys = g.exterior.coords.xy
        rings.append([v for x, y in zip(xs, ys) for v in world(x, y)])
    c = r.geometry.representative_point()
    cx, cy = world(c.x, c.y)
    polys.append({"n": r.NTAName, "b": r.BoroName, "c": [cx, cy], "r": rings,
                  "a": round(r.geometry.area / 1e6, 2)})

# named parks, for friendlier place names ("Brooklyn Bridge Park" rather than a census neighbourhood)
BORO = {1: "Manhattan", 2: "Bronx", 3: "Brooklyn", 4: "Queens", 5: "Staten Island"}
boro_r = np.load(f"{G}/boro.npy", mmap_mode="r")
lu = gpd.read_parquet(os.path.join(DATA, "overture", "base_land_use.parquet"), columns=["class", "names", "geometry"])
lu = lu[lu["class"].isin(["park", "nature_reserve", "cemetery", "golf_course", "recreation_ground", "beach"]) &
        lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
lu["name"] = lu.names.apply(lambda n: n["primary"] if n is not None else None)
lu = lu[lu.name.notna()].to_crs(grid.CRS)
lu = lu[lu.area >= 3000]
parks = []
for _, r in lu.iterrows():
    c = r.geometry.representative_point()
    rr, cc = grid.to_rc(c.x, c.y)
    if not (0 <= rr < grid.H and 0 <= cc < grid.W):
        continue
    b = int(boro_r[int(rr), int(cc)])
    if b not in BORO:
        continue
    g = r.geometry.simplify(4)
    rings = []
    for part in getattr(g, "geoms", [g]):
        xs, ys = part.exterior.coords.xy
        rings.append([int(round(v)) for x, y in zip(xs, ys) for v in world(x, y)])
    px, py = world(c.x, c.y)
    parks.append({"n": r["name"], "b": BORO[b], "a": round(r.geometry.area / 1e4, 1), "c": [px, py], "r": rings})
parks.sort(key=lambda d: d["a"])   # smallest first, so a pier inside a big park is named for the pier

# terrain at 48 m for elevation angles in the panorama (int16 decimetres, gzip)
ground = np.load(f"{G}/ground.npy", mmap_mode="r")
f = 16
hh, ww = grid.H // f, grid.W // f
dem = np.asarray(ground[: hh * f, : ww * f]).reshape(hh, f, ww, f).mean(axis=(1, 3))
os.makedirs(f"{SITE}/tiles", exist_ok=True)
import base64
open(f"{SITE}/tiles/dem.txt", "w").write(base64.b64encode(gzip.compress(np.clip(dem * 10, -32000, 32000).astype("<i2").tobytes(), 9)).decode())

tile_index = json.load(open(f"{SITE}/tiles/index.json"))
data = {"grid": {"res": grid.RES, "w": grid.W, "h": grid.H, "x0": grid.X0, "y1": grid.Y1,
                 "dem": {"cell": grid.RES * f, "w": ww, "h": hh}},
        "tiles": tile_index, "landmarks": lms, "ntas": polys, "parks": parks,
        "findings": {k: F[k] for k in ["public_km2", "mean_count", "pct_zero", "count_hist", "boroughs", "best_spots", "best_by_boro", "liberty_where"] if k in F} |
                    {"ntas": [{k: d[k] for k in ["name", "boro", "mean", "pct_zero", "pct_esb"]} for d in F["ntas"]]},
        "tour": json.load(open(os.path.join(here, "tour.json"))) if os.path.exists(os.path.join(here, "tour.json")) else []}
def lab(lat, lon, **kw):
    x, y = to_utm.transform(lon, lat); wx, wy = world(x, y); return {"x": wx, "y": wy} | kw
data["labels"] = {
    "boroughs": [lab(40.776, -73.969, name="Manhattan"), lab(40.646, -73.945, name="Brooklyn"),
                 lab(40.708, -73.812, name="Queens"), lab(40.851, -73.868, name="The Bronx"),
                 lab(40.586, -74.148, name="Staten Island")],
    "water": [lab(40.818, -73.966, name="Hudson River", rot=-62, min=0.02), lab(40.742, -73.963, name="East River", rot=-62, min=0.05),
              lab(40.668, -74.048, name="Upper New York Bay", rot=0, min=0.02), lab(40.53, -74.03, name="Lower New York Bay", rot=0, min=0.02),
              lab(40.612, -73.838, name="Jamaica Bay", rot=0, min=0.02), lab(40.835, -73.762, name="Long Island Sound", rot=-28, min=0.02),
              lab(40.545, -73.88, name="Atlantic Ocean", rot=0, min=0.02), lab(40.6435, -74.105, name="Kill Van Kull", rot=-8, min=0.06),
              lab(40.565, -74.236, name="Arthur Kill", rot=-68, min=0.05), lab(40.818, -73.932, name="Harlem River", rot=-68, min=0.08),
              lab(40.768, -73.858, name="Flushing Bay", rot=0, min=0.06), lab(40.80, -73.82, name="East River", rot=0, min=0.05)]}
data["sun"] = json.load(open(f"{SUN}/sun_states.json")) if SUN else []
if SUN and os.path.exists(f"{SUN}/sun_stats.json"):
    data["findings"]["sun"] = json.load(open(f"{SUN}/sun_stats.json"))
for t in data["tour"]:
    x, y = to_utm.transform(t["lon"], t["lat"])
    t["x"], t["y"] = world(x, y)
tpl = open(os.path.join(here, "..", "web", "template.html")).read()
html = tpl.replace("/*__DATA__*/{}", json.dumps(data, separators=(",", ":")))
# artifact.html: the page body alone, for the claude.ai artifact (its host adds the document skeleton).
# index.html: the complete document, served by GitHub Pages and used for local testing.
open(f"{SITE}/artifact.html", "w").write(html)
# The Pages build draws a standard street map underneath. The artifact can't load outside images, so artifact.html
# leaves this out and the page draws its own streets.
# OpenStreetMap's standard tiles: free, no key, attribution required, light use only (tile usage policy). They are
# light-coloured, so the page darkens them; labels are baked in, so there is no separate label layer. (CARTO's dark
# tiles, tried first, now need an API key and come back watermarked without one.)
BASEMAP = {"base": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "labels": None, "maxZoom": 19, "retina": False,
           "dark": True, "attribution": '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'}
DESC = ("Which of 16 New York landmarks, and the rising and setting sun, you can see at street level "
        "from every street, sidewalk and park in the five boroughs.")
title, rest = (html.split("\n", 1) if html.startswith("<title>") else ("", html))
open(f"{SITE}/index.html", "w").write(
    f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n{title}\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    f'<meta name="description" content="{DESC}">\n<meta property="og:title" content="New York Sightlines">\n'
    f'<meta property="og:description" content="{DESC}">\n<script>window.SL_BASEMAP = {json.dumps(BASEMAP)};</script>\n</head>\n<body style="margin:0">\n' + rest + '\n</body>\n</html>\n')
print("index.html", len(html) // 1024, "KB")
