"""Radial line-of-sight viewsheds from each landmark over the 3 m surface model.

For every landmark tower point we cast rays outward at an angular spacing fine enough that
adjacent rays are < 0.7 cells apart at the far edge of the grid, march each ray in half-cell
steps, and keep the running maximum slope of the surface (corrected for earth curvature and
refraction). A cell is visible at level L when a person's eye there (ground + 1.6 m) sits on or
above that horizon as seen from the landmark point at height L. Lines of sight are symmetric,
so this is exactly "can someone standing here see that point on the landmark".

Usage: python viewshed.py GRID_DIR DATA_DIR OUT_DIR [landmark_id ...]
Writes OUT_DIR/<id>.npy (uint8: 0 none, 1 top visible, 2 upper part, 3 most of it).
"""
import sys, json, time, os
import numpy as np, numba as nb, geopandas as gpd
from pyproj import Transformer
from rasterio.features import rasterize
import grid

R_EARTH, K_REFR = 6_371_000.0, 0.13


@nb.njit(parallel=True, fastmath=False, cache=True)
def cast(dsm, ground, r0, c0, H, eye, res, nrays, step, out):
    nr, nc = dsm.shape
    nl = H.shape[0]
    curv_k = (1.0 - K_REFR) / (2.0 * R_EARTH)
    for k in nb.prange(nrays):
        th = 2.0 * np.pi * k / nrays
        dr = -np.cos(th) * step
        dc = np.sin(th) * step
        smax = np.full(nl, -1e30)
        r = r0
        c = c0
        i = 0
        while True:
            i += 1
            r += dr
            c += dc
            ri = int(np.floor(r))
            ci = int(np.floor(c))
            if ri < 0 or ci < 0 or ri >= nr or ci >= nc:
                break
            d = i * step * res
            if d < 2.0:
                continue
            cv = d * d * curv_k
            t = ground[ri, ci] + eye - cv
            z = dsm[ri, ci] - cv
            # Only the ray whose bearing is closest to this cell's centre may mark it, so every
            # cell is judged along (nearly) its own true line of sight rather than any ray that grazes it.
            mine = -1
            for l in range(nl):
                if (t - H[l]) / d >= smax[l]:
                    if mine == -1:
                        a = np.arctan2(ci + 0.5 - c0, -(ri + 0.5 - r0))
                        if a < 0.0:
                            a += 2.0 * np.pi
                        kk = int(np.floor(a / (2.0 * np.pi) * nrays + 0.5)) % nrays
                        mine = 1 if kk == k else 0
                    if mine == 1:
                        out[l, ri, ci] = 1
                s = (z - H[l]) / d
                if s > smax[l]:
                    smax[l] = s
    return 0


@nb.njit(cache=True)
def exact_los(dsm, ground, r0, c0, H, eye, res, rt, ct):
    """Reference check: densely sample the straight line from target cell centre to observer."""
    tr, tc = rt + 0.5, ct + 0.5
    D = np.hypot(tr - r0, tc - c0)
    curv_k = (1.0 - K_REFR) / (2.0 * R_EARTH)
    dt = D * res
    t = ground[rt, ct] + eye - dt * dt * curv_k
    n = int(D / 0.1) + 1
    best = -1e30
    lastr, lastc = -1, -1
    for j in range(1, n):
        f = j / n
        r = r0 + (tr - r0) * f
        c = c0 + (tc - c0) * f
        ri = int(np.floor(r)); ci = int(np.floor(c))
        if ri == rt and ci == ct:
            continue
        if ri == lastr and ci == lastc:
            continue
        lastr, lastc = ri, ci
        d = D * f * res
        if d < 2.0:
            continue
        s = (dsm[ri, ci] - d * d * curv_k - H) / d
        if s > best:
            best = s
    return (t - H) / dt >= best


def load_landmarks(path):
    return json.load(open(path))


_B = {}


def own_structure(lm, DATA, to_utm, shape):
    """Return (snapped UTM points, boolean mask of the landmark's own structure)."""
    if not _B:
        bld = gpd.read_parquet(f"{DATA}/overture/building.parquet", columns=["id", "geometry", "height"]).to_crs(grid.CRS)
        parts = gpd.read_parquet(f"{DATA}/overture/building_part.parquet", columns=["building_id", "geometry", "height"]).to_crs(grid.CRS)
        allp = gpd.GeoDataFrame({"h": list(bld.height) + list(parts.height),
                                 "geometry": list(bld.geometry) + list(parts.geometry)}, crs=grid.CRS)
        _B.update(bld=bld, parts=parts, allp=allp)
    bld, parts, allp = _B["bld"], _B["parts"], _B["allp"]
    selfg = list(bld[bld.id.isin(lm["self"])].geometry) + list(parts[parts.building_id.isin(lm["self"])].geometry)
    selfh = list(bld[bld.id.isin(lm["self"])].height) + list(parts[parts.building_id.isin(lm["self"])].height)
    snapped = []
    for lat, lon in lm["points"]:
        x, y = to_utm.transform(lon, lat)
        if selfg and lm["self"]:
            cand = [(h if h == h else 0, g) for h, g in zip(selfh, selfg)]
        else:  # bridges and the like: any tall structure mapped within 80 m of the estimate
            near = allp.iloc[list(allp.sindex.query(gpd.points_from_xy([x], [y])[0].buffer(80)))]
            near = near[near.h.fillna(0) > 0.5 * lm["levels"][0]]
            cand = list(zip(near.h, near.geometry))
            selfg += list(near.geometry)
        if cand:
            top = max(cand, key=lambda t: t[0])[1]
            x, y = top.centroid.x, top.centroid.y
        snapped.append((x, y))
    mask = None
    if selfg:
        mask = rasterize(((g, 1) for g in gpd.GeoSeries(selfg, crs=grid.CRS).buffer(1.5)), out_shape=shape,
                         transform=grid.transform(), dtype=np.uint8).astype(bool)
    return snapped, mask


def main():
    G, DATA, OUT = sys.argv[1:4]
    only = set(sys.argv[4:])
    os.makedirs(OUT, exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))
    lms = load_landmarks(os.path.join(here, "landmarks.json"))
    dsm = np.load(f"{G}/dsm.npy")
    ground = np.load(f"{G}/ground.npy")
    to_utm = Transformer.from_crs("EPSG:4326", grid.CRS, always_xy=True)
    meta = {}
    for lm in lms:
        if only and lm["id"] not in only:
            continue
        t0 = time.time()
        # Remove the landmark's own structure so it does not hide itself, and snap each
        # observer point onto the tallest piece of that structure.
        snapped, mask = own_structure(lm, DATA, to_utm, dsm.shape)
        saved = None
        if mask is not None:
            saved = (mask, dsm[mask].copy())
            dsm[mask] = ground[mask]
        code = np.zeros(dsm.shape, np.uint8)
        pts = []
        for (lat, lon), (x, y) in zip(lm["points"], snapped):
            lon, lat = to_utm.transform(x, y, direction="INVERSE")
            r0, c0 = grid.to_rc(x, y)
            r0, c0 = float(r0), float(c0)
            base = float(ground[int(r0), int(c0)]) if lm["base"] == "dem" else float(lm["base"])
            H = np.array([base + h for h in lm["levels"]], np.float64)
            # farthest grid corner in cells -> number of rays
            dmax = max(np.hypot(r0 - a, c0 - b) for a in (0, grid.H) for b in (0, grid.W))
            nrays = int(np.ceil(2 * np.pi * dmax / 0.7))
            out = np.zeros((len(H), grid.H, grid.W), np.uint8)
            cast(dsm, ground, r0, c0, H, grid.EYE, grid.RES, nrays, 0.5, out)
            pc = np.zeros(dsm.shape, np.uint8)
            for l in range(len(H)):
                pc[out[l] == 1] = l + 1   # later (lower) levels overwrite: code = lowest visible level
            np.maximum(code, pc, out=code)  # bridges: either tower counts
            del pc
            pts.append({"lat": lat, "lon": lon, "x": x, "y": y, "base": base, "H": H.tolist(), "nrays": nrays})
            del out
        if saved is not None:
            dsm[saved[0]] = saved[1]
        np.save(f"{OUT}/{lm['id']}.npy", code)
        meta[lm["id"]] = pts
        print(f"{lm['id']:12s} {time.time()-t0:6.1f}s  visible cells: {np.bincount(code.ravel(), minlength=4).tolist()}", flush=True)
    old = json.load(open(f"{OUT}/meta.json")) if os.path.exists(f"{OUT}/meta.json") else {}
    old.update(meta)
    json.dump(old, open(f"{OUT}/meta.json", "w"), indent=1)


if __name__ == "__main__":
    main()
