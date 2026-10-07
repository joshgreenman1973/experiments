"""Pack the viewsheds into gzip'd 1024x1024 tiles at four zoom levels for the web viewer.

Usage: python export_tiles.py GRID_DIR VS_DIR OUT_DIR [SUN_DIR]

Each tile file holds byte planes, plane-major:
  plane 0  base: bits 0-2 class (0 water, 1 city open ground, 2 city park, 3 city building,
           4 other land, 5 other building); bit 3 public street/park; bits 3-7 for buildings hold a
           height bucket instead (sqrt scale).
  Sun tiles (s{z}_{tx}_{ty}, levels 0-2 only): 4 planes, 8 dates, sunrise in bits 0-1 and sunset in bits 2-3 of each
  nibble (date k in plane k//2, nibble k%2). Level 2 (6 m) keeps the best of its four 3 m cells.
  planes 1-4 (only when the tile touches the city): 16 landmarks x 2 bits. Landmark i lives in
           plane 1 + i//4, bits 2*(i%4). At 3 m (level 3) the value is how much of the landmark
           is visible (0 none, 1 top, 2 upper part, 3 most). Coarser levels hold the mean of that
           value over the block's open ground, rounded so thin corridors still register.
"""
import sys, os, json, gzip, numpy as np
import grid

G, VS, OUT = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
LMS = json.load(open(os.path.join(here, "landmarks.json")))
T = 1024
os.makedirs(OUT, exist_ok=True)

cls = np.load(f"{G}/cls.npy"); boro = np.load(f"{G}/boro.npy"); pub = np.load(f"{G}/public.npy")
dsm = np.load(f"{G}/dsm.npy", mmap_mode="r"); ground = np.load(f"{G}/ground.npy", mmap_mode="r")
city = (boro >= 1) & (boro <= 5)
N = 16384  # padded size, a multiple of every tile footprint
def pad(a, fill=0):
    out = np.full((N, N), fill, a.dtype); out[: a.shape[0], : a.shape[1]] = a; return out

# --- level-3 class / base ----------------------------------------------------
klass = np.zeros(cls.shape, np.uint8)
klass[(cls == 1) & city] = 1
klass[(cls == 3) & city] = 2
klass[(cls == 2) & city] = 3
klass[((cls == 1) | (cls == 3)) & ~city & (boro == 9)] = 4
klass[(cls == 2) & ~city] = 5
bh = np.zeros(cls.shape, np.uint8)
for r0 in range(0, grid.H, 2000):
    h = np.asarray(dsm[r0:r0 + 2000]) - np.asarray(ground[r0:r0 + 2000])
    bh[r0:r0 + 2000] = np.clip(np.sqrt(np.clip(h, 0, None)) * 1.4, 0, 31).astype(np.uint8)
isb = (klass == 3) | (klass == 5)
open_city = ((klass == 1) | (klass == 2))
base3 = klass.copy()
base3[open_city & (pub == 1)] |= 8
base3[isb] |= (bh[isb] << 3)
del bh
klass = pad(klass); base3 = pad(base3); open_city = pad(open_city)

# --- level-3 visibility planes ---------------------------------------------------
vis3 = np.zeros((4, N, N), np.uint8)
for i, lm in enumerate(LMS):
    c = np.load(f"{VS}/{lm['id']}.npy")
    c = np.where(open_city[: grid.H, : grid.W], c, 0).astype(np.uint8)
    vis3[i // 4, : grid.H, : grid.W] |= (c << (2 * (i % 4)))
    print("packed", lm["id"], flush=True)
# --- level-3 sun planes: 8 dates x (sunrise 2 bits | sunset 2 bits); date k lives in plane k//2, nibble k%2
SUN_DIR = sys.argv[4] if len(sys.argv) > 4 else None
sun3 = np.zeros((4, N, N), np.uint8)
if SUN_DIR:
    states = json.load(open(f"{SUN_DIR}/sun_states.json"))
    for k, st in enumerate(states):
        for e, ev in enumerate(("sunrise", "sunset")):
            lv = np.load(f"{SUN_DIR}/sun_{st['key']}_{ev}.npy")
            lv = np.where(open_city[: grid.H, : grid.W], lv, 0).astype(np.uint8)
            sun3[k // 2, : grid.H, : grid.W] |= (lv << (4 * (k % 2) + 2 * e))
        print("packed sun", st["key"], flush=True)
del cls, boro, pub

def coarse_tile(z, tx, ty):
    """Aggregate the 3 m data under one coarse tile (f x f cells per texel)."""
    f = 2 ** (3 - z)
    rs, cs = slice(ty * T * f, (ty + 1) * T * f), slice(tx * T * f, (tx + 1) * T * f)
    k = klass[rs, cs].reshape(T, f, T, f)
    best = np.zeros((T, T), np.uint16); kz = np.zeros((T, T), np.uint8)
    for v in (0, 4, 1, 2, 5, 3):           # later classes win ties: buildings stay visible when zoomed out
        cnt = (k == v).sum(axis=(1, 3), dtype=np.uint16)
        m = cnt >= best; kz[m] = v; best[m] = cnt[m]
    b3 = base3[rs, cs].reshape(T, f, T, f)
    isb = (k == 3) | (k == 5)
    hb = np.where(isb, b3 >> 3, 0).max(axis=(1, 3)).astype(np.uint8)
    oc_full = open_city[rs, cs].reshape(T, f, T, f)
    oc = oc_full.sum(axis=(1, 3), dtype=np.uint32)
    pubz = (((b3 & 8) > 0) & oc_full).sum(axis=(1, 3), dtype=np.uint32)
    base = kz.copy()
    bz = (kz == 3) | (kz == 5)
    base[bz] |= (hb[bz] << 3)
    base[((kz == 1) | (kz == 2)) & (pubz * 2 >= oc)] |= 8
    vis = np.zeros((4, T, T), np.uint8)
    ocz = np.maximum(oc, 1)
    for i in range(len(LMS)):
        v = ((vis3[i // 4, rs, cs] >> (2 * (i % 4))) & 3).reshape(T, f, T, f).sum(axis=(1, 3), dtype=np.uint32) / ocz
        q = np.clip(np.floor(v + 0.75), 0, 3).astype(np.uint8)   # mean value, rounded up from 0.25
        q[oc == 0] = 0
        vis[i // 4] |= (q << (2 * (i % 4)))
    sun = np.zeros((4, T, T), np.uint8)
    for k in range(8):
        for e in range(2):
            sh = 4 * (k % 2) + 2 * e
            lv = ((sun3[k // 2, rs, cs] >> sh) & 3).reshape(T, f, T, f)
            if f == 2:      # finest sun level: a 6 m block catches the sun if any of its 3 m cells does
                q = lv.max(axis=(1, 3)).astype(np.uint8)
            else:
                v = lv.sum(axis=(1, 3), dtype=np.uint32) / ocz
                q = np.clip(np.floor(v + 0.75), 0, 3).astype(np.uint8)
            q[oc == 0] = 0
            sun[k // 2] |= (q << sh)
    return base, vis, sun

index = {"tile": T, "levels": []}
for z in range(3, -1, -1):
    f = 2 ** (3 - z)
    nt = N // f // T
    tiles = []
    sun_tiles = []
    total = 0
    for ty in range(nt):
        for tx in range(nt):
            sn = None
            if f == 1:
                sl = (slice(ty * T, (ty + 1) * T), slice(tx * T, (tx + 1) * T))
                b, v = base3[sl], vis3[(slice(None),) + sl]
            else:
                rs, cs = slice(ty * T * f, (ty + 1) * T * f), slice(tx * T * f, (tx + 1) * T * f)
                if not klass[rs, cs].any():
                    continue
                b, v, sn = coarse_tile(z, tx, ty)
            if sn is not None and sn.any():   # sun layers ship separately, 6 m and coarser, fetched only in sun mode
                data = gzip.compress(sn.tobytes(), 9)
                open(f"{OUT}/s{z}_{tx}_{ty}.bin", "wb").write(data)
                sun_tiles.append([tx, ty, len(data)])
            if not b.any():
                continue
            has_vis = bool(v.any()) or bool((((b & 7) == 1) | ((b & 7) == 2) | ((b & 7) == 3)).any())
            buf = b.tobytes() + (v.tobytes() if has_vis else b"")
            name = f"z{z}_{tx}_{ty}.bin"
            data = gzip.compress(buf, 9)
            open(f"{OUT}/{name}", "wb").write(data)
            total += len(data)
            tiles.append([tx, ty, 1 if has_vis else 0, len(data)])
    index["levels"].append({"z": z, "cell": grid.RES * f, "n": nt, "tiles": tiles, "sun": sun_tiles})
    print(f"level {z}: {len(tiles)} tiles, {total/1e6:.1f} MB", flush=True)
index["levels"].sort(key=lambda d: d["z"])
index["grid"] = {"x0": grid.X0, "y1": grid.Y1, "res": grid.RES, "w": grid.W, "h": grid.H, "crs": grid.CRS}
json.dump(index, open(f"{OUT}/index.json", "w"))
