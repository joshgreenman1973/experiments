"""Turn hand-picked tour stops into tour.json with every number in the captions computed from the data.

For each stop, the "place" is the public ground inside a named polygon (Overture land use, by name) or within a
radius of the given point. Over the place we compute the typical (median) and best landmark counts from the
viewshed arrays; then the best candidate cells are re-traced with an exact point-to-point line of sight (the fast
viewsheds over-count by about 1%), and the stop is pinned to the best cell that survives. Captions are templates:
  {n} exact count at the pinned cell      {max} same as {n}          {median} typical count over the place
  {elev} ground at the pinned cell, ft    {missing} landmarks not seen, when only one or two
  {zero_share} share of the place seeing none     {far_name} {far_mi} farthest landmark seen from the pinned cell
  {esb_mi} miles to the Empire State Building     {sun_mins} minutes before sunset / after sunrise for the sun level

Usage: python make_tour.py GRID_DIR VS_DIR tour_stops.json OUT_tour.json SUN_DIR DATA_DIR
"""
import sys, os, json, numpy as np, numba as nb, geopandas as gpd
from pyproj import Transformer
from rasterio.features import rasterize
import grid

G, VS, STOPS, OUT, SUN_DIR, DATA = sys.argv[1:7]
here = os.path.dirname(os.path.abspath(__file__))
LMS = json.load(open(os.path.join(here, "landmarks.json")))
META = json.load(open(f"{VS}/meta.json"))
CODES = [np.load(f"{VS}/{l['id']}.npy", mmap_mode="r") for l in LMS]
pub = np.load(f"{G}/public.npy", mmap_mode="r")
ground = np.load(f"{G}/ground.npy", mmap_mode="r")
dsm = np.load(f"{G}/dsm.npy")
gnd = np.load(f"{G}/ground.npy")
t = Transformer.from_crs("EPSG:4326", grid.CRS, always_xy=True)
inv = Transformer.from_crs(grid.CRS, "EPSG:4326", always_xy=True)
STATES = {st["key"]: st for st in json.load(open(f"{SUN_DIR}/sun_states.json"))}
SUNLV = {(k, e): np.load(f"{SUN_DIR}/sun_{k}_{ev}.npy", mmap_mode="r") for k in STATES for e, ev in (("rise", "sunrise"), ("set", "sunset"))}
lu = gpd.read_parquet(f"{DATA}/overture/base_land_use.parquet", columns=["names", "class", "geometry"])
lu["name"] = lu.names.apply(lambda n: n["primary"] if n is not None else None)
K = (1 - 0.13) / (2 * 6371000.0)


@nb.njit(cache=True)
def exact(dsm, gnd, r, c, tx, ty, H, res):
    """Exact line of sight from the eye at cell (r, c) to the point (tx, ty, H) in grid units; samples every 0.5 m,
    ignores the observer's own cell and the last 60 m before the target (the landmark's own structure)."""
    r0, c0 = r + 0.5, c + 0.5
    dr, dc = ty - r0, tx - c0
    D = np.hypot(dr, dc) * res
    eye = gnd[r, c] + 1.6
    n = int(D / 0.5)
    for j in range(1, n):
        f = j / n
        s = D * f
        if s > D - 60.0:
            break
        rr, cc = int(np.floor(r0 + dr * f)), int(np.floor(c0 + dc * f))
        if rr == r and cc == c:
            continue
        los = eye + (H - eye) * f - K * s * (D - s)
        if dsm[rr, cc] > los:
            return False
    return True


def exact_set(r, c):
    seen = []
    for l in LMS:
        ok = False
        for p in META[l["id"]]:
            pr, pc = grid.to_rc(p["x"], p["y"])
            if exact(dsm, gnd, r, c, float(pc), float(pr), p["H"][0], grid.RES):
                ok = True
                break
        if ok:
            seen.append(l)
    return seen


def place_cells(s):
    if s.get("place") or s.get("near_water"):
        x, y = t.transform(s["lon"], s["lat"])
        from shapely.geometry import Point
        here_pt = Point(x, y)
        geoms = []
        names = s["place"] if isinstance(s.get("place"), list) else ([s["place"]] if s.get("place") else [])
        for nm in names:      # names repeat across the region: take the polygon nearest the stop
            g = lu[(lu.name == nm) & lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
            if s.get("class"):
                g = g[g["class"] == s["class"]]
            g = g.to_crs(grid.CRS)
            if g.empty:
                raise SystemExit(f"no polygon named {nm}")
            geoms.append(g.geometry.iloc[int(np.argmin(g.geometry.distance(here_pt).values))])
        if s.get("near_water"):
            wv = gpd.read_parquet(f"{DATA}/overture/base_water.parquet", columns=["names", "geometry"])
            wv["name"] = wv.names.apply(lambda n: n["primary"] if n is not None else None)
            wv = wv[(wv.name == s["near_water"]) & wv.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
            wgeom = wv.geometry.iloc[int(np.argmin(wv.geometry.distance(here_pt).values))]
            geoms.append(wgeom.buffer(s.get("buffer_m", 120)).difference(wgeom))
        m = rasterize(((x, 1) for x in geoms), out_shape=(grid.H, grid.W), transform=grid.transform(), dtype=np.uint8)
        r, c = np.nonzero(m)
    else:
        x, y = t.transform(s["lon"], s["lat"]); r0, c0 = grid.to_rc(x, y); r0, c0 = int(r0), int(c0)
        R = int(s.get("radius_m", 150) / grid.RES)
        rr, cc = np.mgrid[r0 - R:r0 + R + 1, c0 - R:c0 + R + 1]
        keep = np.hypot(rr - r0, cc - c0) <= R
        r, c = rr[keep], cc[keep]
    ok = pub[r, c] == 1
    return r[ok], c[ok]


def mi(m):
    return m / 1609.344


out = []
for s in json.load(open(STOPS)):
    r, c = place_cells(s)
    counts = np.zeros(len(r), np.int32)
    for C in CODES:
        counts += C[r, c] > 0
    x0, y0 = t.transform(s["lon"], s["lat"]); pr0, pc0 = grid.to_rc(x0, y0)
    dist0 = np.hypot(r - pr0, c - pc0)
    d = {k: s[k] for k in ("title", "tag", "lm", "zoom", "start", "sun") if k in s}
    vals = {"median": int(np.median(counts)), "zero_share": f"{100 * (counts == 0).mean():.0f}%"}
    if s.get("sun"):
        lv = SUNLV[(s["sun"]["k"], s["sun"]["e"])][r, c]
        okc = np.flatnonzero(lv >= s["sun"].get("min", 3))
        if okc.size == 0:
            raise SystemExit(f"no cell meets the sun level for {s['title']}")
        j = okc[np.argmin(dist0[okc])]
        st = STATES[s["sun"]["k"]]; ev = st["sunrise" if s["sun"]["e"] == "rise" else "sunset"]
        f = lambda tt: int(tt[:2]) * 60 + int(tt[3:5])
        lvj = int(lv[j])
        vals["sun_mins"] = str(abs(f(ev["official"]) - f(ev["levels"][lvj - 1]["time"])))
        vals["sun_share"] = f"{100 * (lv >= s['sun'].get('min', 3)).mean():.0f}%"
        seen = []
    else:
        # candidates: the highest array counts, nearest first; keep the best exact count
        order = np.lexsort((dist0, -counts))
        if s.get("want"):
            wi = [l["id"] for l in LMS].index(s["want"])
            order = order[CODES[wi][r[order], c[order]] > 0]
        best = None
        for j in order[: s.get("candidates", 40)]:
            seen_j = exact_set(int(r[j]), int(c[j]))
            if s.get("want") and s["want"] not in [l["id"] for l in seen_j]:
                continue
            key = (len(seen_j), -dist0[j])
            if best is None or key > best[0]:
                best = (key, j, seen_j)
        _, j, seen = best
        if s.get("fewest"):   # e.g. Times Square: pin the most typical spot, the centre of the place
            j = int(np.argmin(dist0)); seen = exact_set(int(r[j]), int(c[j]))
    rr, cc = int(r[j]), int(c[j])
    lon, lat = inv.transform(*grid.to_xy(rr + 0.5, cc + 0.5))
    cx, cy = grid.to_xy(rr + 0.5, cc + 0.5)
    dist = {l["id"]: min(np.hypot(p["x"] - cx, p["y"] - cy) for p in META[l["id"]]) for l in LMS}
    far = max(seen, key=lambda l: dist[l["id"]]) if seen else None
    missing = [l["name"] for l in LMS if l not in seen]
    vals.update(n=len(seen), max=len(seen), elev=f"{ground[rr, cc] * 3.28084:.0f}",
                far_name=far["name"] if far else "", far_mi=f"{mi(dist[far['id']]):.0f}" if far else "",
                esb_mi=f"{mi(dist['esb']):.1f}", missing=" and ".join(missing) if len(missing) <= 2 else "")
    for k, v in s.get("expect", {}).items():
        assert str(vals[k]) == str(v), (s["title"], k, vals[k], v)
    d["text"] = s["text"].format(**vals)
    d["lat"], d["lon"] = round(lat, 6), round(lon, 6)
    d["check"] = {"place_cells": int(len(r)), "array_max": int(counts.max()), "median": vals["median"], "exact_at_pin": len(seen),
                  "array_at_pin": int(counts[j]), "seen": [l["id"] for l in seen]}
    out.append(d)
    print(f"{len(seen):2d} (array max {counts.max():2d}, median {vals['median']:2d}, n={len(r)})  {s['title']:38s} {d['text'][:120]}", flush=True)
json.dump(out, open(OUT, "w"), indent=1)
