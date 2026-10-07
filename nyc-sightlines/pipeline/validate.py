"""Compare the radial viewshed against exact per-target line-of-sight checks on random cells."""
import sys, json, os, numpy as np, geopandas as gpd
from rasterio.features import rasterize
import grid
from viewshed import exact_los

G, DATA, VS = sys.argv[1:4]
ids = sys.argv[4:]
N = 4000
here = os.path.dirname(os.path.abspath(__file__))
lms = {l["id"]: l for l in json.load(open(os.path.join(here, "landmarks.json")))}
meta = json.load(open(f"{VS}/meta.json"))
dsm = np.load(f"{G}/dsm.npy"); ground = np.load(f"{G}/ground.npy")
cls = np.load(f"{G}/cls.npy", mmap_mode="r"); boro = np.load(f"{G}/boro.npy", mmap_mode="r")
rng = np.random.default_rng(1)
from pyproj import Transformer
from viewshed import own_structure
to_utm = Transformer.from_crs("EPSG:4326", grid.CRS, always_xy=True)
for lid in ids:
    lm = lms[lid]
    code = np.load(f"{VS}/{lid}.npy", mmap_mode="r")
    _, mask = own_structure(lm, DATA, to_utm, dsm.shape)
    saved = None
    if mask is not None:
        saved = (mask, dsm[mask].copy()); dsm[mask] = ground[mask]
    # stratified sample: half from cells the radial method calls visible, half from the rest
    picks = []
    while len(picks) < N:
        r = rng.integers(0, grid.H, 200000); c = rng.integers(0, grid.W, 200000)
        ok = ((cls[r, c] == 1) | (cls[r, c] == 3)) & (boro[r, c] >= 1) & (boro[r, c] <= 5)
        r, c = r[ok], c[ok]
        v = code[r, c] > 0
        picks += list(zip(r[v][:N // 2 - sum(1 for p in picks if p[2])], c[v][:N // 2], [True] * N))[:max(0, N // 2 - sum(1 for p in picks if p[2]))]
        picks += list(zip(r[~v], c[~v], [False] * N))[:max(0, N // 2 - sum(1 for p in picks if not p[2]))]
    agree = np.zeros(3); tot = 0; fp = np.zeros(3); fn = np.zeros(3)
    for r, c, _ in picks[:N]:
        exact_code = 0
        radial = int(code[r, c])
        for pt in meta[lid]:
            r0, c0 = grid.to_rc(pt["x"], pt["y"])
            for l, Hl in enumerate(pt["H"]):
                if exact_los(dsm, ground, float(r0), float(c0), Hl, grid.EYE, grid.RES, int(r), int(c)):
                    exact_code = max(exact_code, l + 1)
        for l in range(3):
            a = radial >= l + 1; b = exact_code >= l + 1
            agree[l] += a == b; fp[l] += a and not b; fn[l] += b and not a
        tot += 1
    if saved is not None:
        dsm[saved[0]] = saved[1]
    print(f"{lid:12s} n={tot}  agreement by level {np.round(agree/tot*100,1)}  radial-only {fp.astype(int)}  exact-only {fn.astype(int)}", flush=True)
