"""Summarise the viewsheds: coverage by landmark, borough and neighbourhood, best spots, longest views.

Usage: python analyze.py GRID_DIR VS_DIR NTA_GEOJSON OUT_JSON
All shares are of 'public ground' (streets, sidewalks, parks, plazas) unless noted.
"""
import sys, json, os, numpy as np, geopandas as gpd
from rasterio.features import rasterize
from pyproj import Transformer
import grid

G, VS, NTA, OUT = sys.argv[1:5]
here = os.path.dirname(os.path.abspath(__file__))
LMS = json.load(open(os.path.join(here, "landmarks.json")))
META = json.load(open(f"{VS}/meta.json"))
BORO = {1: "Manhattan", 2: "Bronx", 3: "Brooklyn", 4: "Queens", 5: "Staten Island"}
to_ll = Transformer.from_crs(grid.CRS, "EPSG:4326", always_xy=True)

boro = np.load(f"{G}/boro.npy")
pub = np.load(f"{G}/public.npy").astype(bool)
nta = gpd.read_file(NTA).to_crs(grid.CRS).reset_index(drop=True)
# piers and slivers just outside the shoreline-clipped polygons take the neighbourhood within 300 m
nta_r = rasterize(((g.buffer(300), i + 1) for i, g in enumerate(nta.geometry)), out_shape=pub.shape,
                  transform=grid.transform(), dtype=np.uint16)
rasterize(((g, i + 1) for i, g in enumerate(nta.geometry)), out=nta_r, transform=grid.transform())
SPECIAL = ("park-cemetery-etc", "Airport", "Rikers Island")

idx = np.flatnonzero(pub)                       # public cells, flat indices
b_pub = boro.ravel()[idx]
n_pub = nta_r.ravel()[idx]
del boro
count = np.zeros(idx.size, np.uint8)
score = np.zeros(idx.size, np.uint8)
codes = {}
res = {"landmarks": [], "public_km2": round(idx.size * grid.RES ** 2 / 1e6, 1)}
rows, cols = np.divmod(idx, grid.W)
for lm in LMS:
    c = np.load(f"{VS}/{lm['id']}.npy").ravel()[idx]
    codes[lm["id"]] = c
    vis = c > 0
    count += vis
    score += c
    # longest view: the farthest 15 m patch of public ground where most of the patch has the view
    # (single 3 m slits through gaps are too fragile to quote)
    B5 = 5
    kb = (rows // B5) * (grid.W // B5 + 1) + (cols // B5)
    ukb, invb, nb_ = np.unique(kb, return_inverse=True, return_counts=True)
    fr = np.bincount(invb, weights=vis) / nb_
    good = (fr >= 0.6) & (nb_ >= 10)
    far = None
    if good.any():
        br_, bc_ = np.divmod(ukb[good], grid.W // B5 + 1)
        xs, ys = grid.to_xy(br_ * B5 + 2.5, bc_ * B5 + 2.5)
        d = np.full(xs.size, np.inf)
        for p in META[lm["id"]]:
            d = np.minimum(d, np.hypot(xs - p["x"], ys - p["y"]))
        k = int(np.argmax(d))
        lon, lat = to_ll.transform(xs[k], ys[k])
        sel_cells = np.flatnonzero(invb == np.flatnonzero(good)[k])
        ni = int(np.bincount(n_pub[sel_cells]).argmax())
        far = {"km": round(float(d[k]) / 1000, 1), "lat": round(lat, 6), "lon": round(lon, 6),
               "nta": nta.NTAName[ni - 1] if ni else None, "boro": BORO.get(int(b_pub[sel_cells[0]]))}
    res["landmarks"].append({
        "id": lm["id"], "name": lm["name"],
        "pct": round(100 * vis.mean(), 2),
        "pct_most": round(100 * (c == 3).mean(), 2),
        "by_boro": {BORO[b]: round(100 * vis[b_pub == b].mean(), 2) for b in BORO},
        "farthest": far,
    })
    print(lm["id"], res["landmarks"][-1]["pct"], far, flush=True)

res["count_hist"] = np.bincount(count, minlength=len(LMS) + 1).tolist()
res["mean_count"] = round(float(count.mean()), 2)
res["pct_zero"] = round(100 * float((count == 0).mean()), 1)
res["boroughs"] = []
for b, name in BORO.items():
    m = b_pub == b
    res["boroughs"].append({"name": name, "km2": round(m.sum() * 9 / 1e6, 1), "mean": round(float(count[m].mean()), 2),
                            "pct_zero": round(100 * float((count[m] == 0).mean()), 1),
                            "pct_3plus": round(100 * float((count[m] >= 3).mean()), 1),
                            "max": int(count[m].max())})

# neighbourhoods
ntas = []
for i, r in nta.iterrows():
    m = n_pub == i + 1
    if m.sum() < 2000:
        continue
    cm = count[m]
    ntas.append({"name": r.NTAName, "boro": r.BoroName, "special": r.NTAName.startswith(SPECIAL), "mean": round(float(cm.mean()), 2),
                 "pct_zero": round(100 * float((cm == 0).mean()), 1),
                 "pct_esb": round(100 * float((codes["esb"][m] > 0).mean()), 1),
                 "top": sorted(((round(100 * float((codes[l['id']][m] > 0).mean()), 1), l["id"]) for l in LMS), reverse=True)[:3]})
res["ntas"] = sorted(ntas, key=lambda d: -d["mean"])

# best spots: 30 m blocks of public ground with the highest mean count, spread at least 700 m apart
B = 10
br, bc = rows // B, cols // B
key = br * (grid.W // B + 1) + bc
uk, inv, ncell = np.unique(key, return_inverse=True, return_counts=True)
bsum = np.bincount(inv, weights=count)
bmean = bsum / ncell
ok = ncell >= 40
order = np.argsort(-(bmean * ok))
picked = []
for k in order[:20000]:
    if not ok[k]:
        continue
    r0, c0 = divmod(int(uk[k]), grid.W // B + 1)
    x, y = grid.to_xy(r0 * B + B / 2, c0 * B + B / 2)
    if any(np.hypot(x - px, y - py) < 700 for px, py, _ in picked):
        continue
    sel = np.flatnonzero(inv == k)
    j = sel[np.argmax(score[sel])]
    lon, lat = to_ll.transform(*grid.to_xy(rows[j] + 0.5, cols[j] + 0.5))
    ni = int(n_pub[j])
    picked.append((x, y, {"lat": round(lat, 6), "lon": round(lon, 6), "count": int(count[j]), "block_mean": round(float(bmean[k]), 2),
                          "nta": nta.NTAName[ni - 1] if ni else None, "boro": BORO.get(int(b_pub[j])),
                          "visible": [l["id"] for l in LMS if codes[l["id"]][j] > 0]}))
    if len(picked) >= 25:
        break
res["best_spots"] = [p[2] for p in picked]
# best spot per borough
res["best_by_boro"] = {}
for b, name in BORO.items():
    m = np.flatnonzero(b_pub == b)
    j = m[np.lexsort((score[m], count[m]))[-1]]
    lon, lat = to_ll.transform(*grid.to_xy(rows[j] + 0.5, cols[j] + 0.5))
    ni = int(n_pub[j])
    res["best_by_boro"][name] = {"lat": round(lat, 6), "lon": round(lon, 6), "count": int(count[j]),
                                 "nta": nta.NTAName[ni - 1] if ni else None,
                                 "visible": [l["id"] for l in LMS if codes[l["id"]][j] > 0]}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: res[k] for k in ["public_km2", "mean_count", "pct_zero", "count_hist", "boroughs"]}, indent=1))
R = [d for d in res["ntas"] if not d["special"]]
print("top ntas", [(d["name"], d["mean"], d["pct_zero"]) for d in R[:12]])
print("bottom ntas", [(d["name"], d["mean"], d["pct_zero"]) for d in R[-12:]])
for s in res["best_spots"][:15]:
    print(s)
print(res["best_by_boro"])
