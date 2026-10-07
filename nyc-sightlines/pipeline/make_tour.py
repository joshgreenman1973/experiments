"""Turn hand-picked tour stops into tour.json, snapping each to the best public cell within ~25 m
and filling {n} (landmarks visible) and {names} in the captions from the data.
Usage: python make_tour.py GRID_DIR VS_DIR tour_stops.json OUT_tour.json"""
import sys, os, json, numpy as np
from pyproj import Transformer
import grid

G, VS, STOPS, OUT = sys.argv[1:5]
here = os.path.dirname(os.path.abspath(__file__))
LMS = json.load(open(os.path.join(here, "landmarks.json")))
codes = {l["id"]: np.load(f"{VS}/{l['id']}.npy", mmap_mode="r") for l in LMS}
pub = np.load(f"{G}/public.npy", mmap_mode="r")
ground = np.load(f"{G}/ground.npy", mmap_mode="r")
META = json.load(open(f"{VS}/meta.json"))
t = Transformer.from_crs("EPSG:4326", grid.CRS, always_xy=True)
inv = Transformer.from_crs(grid.CRS, "EPSG:4326", always_xy=True)
out = []
for s in json.load(open(STOPS)):
    x, y = t.transform(s["lon"], s["lat"]); r, c = grid.to_rc(x, y); r, c = int(r), int(c)
    R = s.get("radius", 8)
    best = None
    for dr in range(-R, R + 1):
        for dc in range(-R, R + 1):
            rr, cc = r + dr, c + dc
            if not pub[rr, cc]:
                continue
            v = [l for l in LMS if codes[l["id"]][rr, cc] > 0]
            if s.get("want") and s["want"] not in [l["id"] for l in v]:
                continue
            key = (len(v) if not s.get("fewest") else -len(v), -(abs(dr) + abs(dc)))
            if best is None or key > best[0]:
                best = (key, rr, cc, v)
    if best is None:
        print("!! no cell for", s["title"]); continue
    _, rr, cc, v = best
    lon, lat = inv.transform(*grid.to_xy(rr + 0.5, cc + 0.5))
    names = [l["short"] for l in v]
    d = {k: s[k] for k in ("title", "tag", "lm", "zoom", "start") if k in s}
    cx, cy = grid.to_xy(rr + 0.5, cc + 0.5)
    dist = {l["id"]: min(np.hypot(p["x"] - cx, p["y"] - cy) for p in META[l["id"]]) for l in LMS}
    far = max(v, key=lambda l: dist[l["id"]]) if v else None
    if "expect" in s:
        assert len(v) == s["expect"], (s["title"], len(v))
    d["text"] = s["text"].format(n=len(v), names=", ".join(names[:-1]) + (" and " + names[-1] if len(names) > 1 else "".join(names)),
                                 far_name=far["name"] if far else "", far_mi=f"{dist[far['id']] / 1609.344:.0f}" if far else "",
                                 elev=f"{ground[rr, cc] * 3.281:.0f}",
                                 esb_mi=f"{dist['esb'] / 1609.344:.1f}")
    d["lat"], d["lon"] = round(lat, 6), round(lon, 6)
    out.append(d)
    print(f"{len(v):2d}  {s['title']:40s} {d['text'][:110]}")
json.dump(out, open(OUT, "w"), indent=1)
