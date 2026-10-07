"""Turn twelve censuses of New York City tract populations (1910-2020) into
smoothed population-density grids for the animated map.

Inputs
  data/nhgis/nhgis0004_csv/*.csv            NHGIS tract tables 1910-1960
  data/nhgis/nhgis0004_shape/*.zip          NHGIS tract boundaries 1910-1960
  ../nyc-child-density/data/nhgis_unpacked  NHGIS nominal tract time series 1970-2020
  ../nyc-child-density/data/nhgis_shapes    NHGIS tract boundaries 1970-2000
  ../nyc-child-density/data/tracts_20{10,20}_36.zip  Census cartographic tracts
  data/boro_gthc-hcne.geojson               NYC Planning borough boundaries, clipped to shoreline

Method
  1. Each tract's population is spread evenly over the land inside it, on a
     grid of 1/20-mile cells (land = today's shoreline-clipped boroughs).
  2. The grid is smoothed with a Gaussian kernel, normalised by the land
     fraction so people are not smeared into the water.
  3. Densities are stored as people per square mile.

Outputs
  assets/grids.bin.gz   uint16 sqrt-scaled densities, one plane per census
  assets/land.png       land mask at 3x the grid resolution
  assets/meta.json      grid geometry, per-census figures, labels
"""
import json, gzip, glob, sys
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
from shapely.geometry import box
from shapely.ops import unary_union
from rasterio import features
from rasterio.transform import from_origin
from scipy import ndimage
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CD = ROOT.parent / "nyc-child-density" / "data"
OUT = ROOT / "assets"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:32618"                 # UTM 18N, metres
MILE = 1609.344
CELL = MILE / 20                   # 1/20 mile, so 20x20 cells = 1 square mile
SQMI_PER_CELL = (CELL / MILE) ** 2
SIGMA = float(sys.argv[1]) if len(sys.argv) > 1 else 2.5   # smoothing, in cells
YEARS = [1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
NYC_COUNTIES = {"New York", "Kings", "Queens", "Bronx", "Richmond"}
OFFICIAL = {1910: 4766883, 1920: 5620048, 1930: 6930446, 1940: 7454995, 1950: 7891957,
            1960: 7781984, 1970: 7894862, 1980: 7071639, 1990: 7322564, 2000: 8008278,
            2010: 8175133, 2020: 8804190}

# ---------------------------------------------------------------- land + grid
boros = gpd.read_file(ROOT / "data" / "boro_gthc-hcne.geojson").to_crs(CRS)
boros["geometry"] = boros.buffer(0)
land = unary_union(boros.geometry)
x0, y0, x1, y1 = land.bounds
PAD = 0.6 * MILE
x0 = np.floor((x0 - PAD) / CELL) * CELL
y1 = np.ceil((y1 + PAD) / CELL) * CELL
W = int(np.ceil((x1 + PAD - x0) / CELL))
H = int(np.ceil((y1 - (y0 - PAD)) / CELL))
T = from_origin(x0, y1, CELL, CELL)
print(f"grid {W} x {H} cells of {CELL:.2f} m, sigma {SIGMA} cells ({SIGMA*CELL:.0f} m)")

landmask = features.rasterize([(land, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8").astype(bool)

def to_px(x, y):
    """UTM metres -> fractional grid pixel (col, row)."""
    return (x - x0) / CELL, (y1 - y) / CELL

# -------------------------------------------------------------- tract loaders
def read_shp(path):
    crs = pyogrio.read_info(str(path))["crs"]
    bb = gpd.GeoSeries([box(*land.bounds)], crs=CRS).to_crs(crs).total_bounds
    return gpd.read_file(path, bbox=tuple(bb))

_shapes = {}
def shapes(year):
    """Tract boundaries for a census year as GISJOIN + geometry in CRS."""
    if year in _shapes:
        return _shapes[year]
    if year <= 1960:
        g = read_shp(glob.glob(str(ROOT / f"data/nhgis/nhgis0004_shape/t{year}/*.shp"))[0])
    elif year <= 2000:
        g = read_shp(CD / f"nhgis_shapes/nhgis0002_shape/nhgis0002_shapefile_tl2000_us_tract_{year}/US_tract_{year}.shp")
    else:
        g = gpd.read_file(f"zip://{CD / f'tracts_{year}_36.zip'}")
        geoid = g["GEOID"] if "GEOID" in g.columns else g["GEO_ID"].str[-11:]
        g["GISJOIN"] = "G" + geoid.str[:2] + "0" + geoid.str[2:5] + "0" + geoid.str[5:]
    g = g[["GISJOIN", "geometry"]].to_crs(CRS)
    _shapes[year] = g
    return g

# Which boundary files to try, in order, for each census. NYC kept its 1930
# tracts in 1940, and NHGIS's 1940 boundary file has only health areas for
# the city, so 1940 counts are drawn on 1930 tracts. Any tract code missing
# from its own year's file is looked up in the neighbouring decades.
GEOM_ORDER = {1940: [1930, 1950, 1920]}
def geom_years(year):
    if year in GEOM_ORDER:
        return GEOM_ORDER[year]
    out = [year]
    for d in (10, 20):
        for yy in (year - d, year + d):
            if yy in YEARS and yy != 1940:
                out.append(yy)
    return out

def counts_historic(year):
    spec = {1910: ("ds40_1910_tract", "A65"), 1920: ("ds48_1920_tract", "BBQ002"),
            1930: ("ds66_1930_tract", "BOC"), 1940: ("ds81_1940_tractnyc", "BZO001"),
            1950: ("ds82_1950_tract", "BZ8001"), 1960: ("ds92_1960_tract", "CA4001")}[year]
    f = glob.glob(str(ROOT / "data/nhgis/nhgis0004_csv" / f"*{spec[0]}.csv"))[0]
    df = pd.read_csv(f, encoding="latin-1", low_memory=False, skiprows=[1])
    df = df[(df.STATE == "New York") & df.COUNTY.isin(NYC_COUNTIES)].copy()
    col = spec[1]
    cols = [c for c in df.columns if c.startswith(col)] if len(col) == 3 else [col]
    df["pop"] = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    return df[["GISJOIN", "pop"]]

_ts = None
def counts_modern(year):
    global _ts
    if _ts is None:
        cols = [f"GJOIN{y}" for y in (1970, 1980, 1990, 2000, 2010, 2020)] + ["STATEFP", "COUNTYFP"] + \
               [f"D08A{a}{y}" for a in "AB" for y in (1970, 1980, 1990, 2000, 2010, 2020)]
        _ts = pd.read_csv(CD / "nhgis_unpacked/nhgis0001_csv/nhgis0001_ts_nominal_tract.csv",
                          usecols=cols, dtype=str, encoding="latin-1")
        _ts = _ts[(_ts.STATEFP == "36") & _ts.COUNTYFP.isin(["005", "047", "061", "081", "085"])]
    df = _ts[_ts[f"GJOIN{year}"].notna()].copy()
    df["pop"] = sum(pd.to_numeric(df[f"D08A{a}{year}"], errors="coerce").fillna(0) for a in "AB")
    df["GISJOIN"] = df[f"GJOIN{year}"]
    return df.groupby("GISJOIN", as_index=False)["pop"].sum()

def tracts(year):
    df = counts_historic(year) if year < 1970 else counts_modern(year)
    df = df[df["pop"] > 0].copy()
    df["geometry"] = None
    df["geom_year"] = 0
    for gy in geom_years(year):
        todo = df["geometry"].isna()
        if not todo.any():
            break
        lut = shapes(gy).drop_duplicates("GISJOIN").set_index("GISJOIN").geometry
        hit = todo & df.GISJOIN.isin(lut.index)
        df.loc[hit, "geometry"] = df.loc[hit, "GISJOIN"].map(lut)
        df.loc[hit, "geom_year"] = gy
    return df

# ------------------------------------------------------------------- build
dist_idx = ndimage.distance_transform_edt(~landmask, return_distances=False, return_indices=True)
land_f = landmask.astype(np.float64)
den = ndimage.gaussian_filter(land_f, SIGMA, mode="constant")

grids, meta_years = [], []
for year in YEARS:
    g = tracts(year)
    missing = g.geometry.isna()
    lost = g.loc[missing, "pop"].sum()
    lost_codes = g.loc[missing, "GISJOIN"].tolist()
    borrowed = g.loc[~missing & (g.geom_year != year), "pop"].sum()
    g = gpd.GeoDataFrame(g[~missing].reset_index(drop=True), geometry="geometry", crs=CRS)
    ids = features.rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)),
                             out_shape=(H, W), transform=T, fill=0, dtype="int32")
    ids[~landmask] = 0
    counts = np.bincount(ids.ravel(), minlength=len(g) + 1)
    pop = g["pop"].to_numpy(dtype=np.float64)
    per = np.zeros(len(g) + 1)
    per[1:] = np.where(counts[1:] > 0, pop / np.maximum(counts[1:], 1), 0)
    grid = per[ids]
    # tracts too small (or too watery) to own a land cell: drop at nearest land cell
    orphan = np.where(counts[1:] == 0)[0]
    for i in orphan:
        p = g.geometry.iloc[i].representative_point()
        c, r = to_px(p.x, p.y)
        r, c = int(np.clip(r, 0, H - 1)), int(np.clip(c, 0, W - 1))
        rr, cc = dist_idx[0][r, c], dist_idx[1][r, c]
        grid[rr, cc] += pop[i]
    total = grid.sum()

    # borough shares by the cell each person was placed in
    boro_tot = {}
    for _, b in boros.iterrows():
        m = features.rasterize([(b.geometry, 1)], out_shape=(H, W), transform=T, fill=0, dtype="uint8").astype(bool)
        boro_tot[b.boroname] = float(grid[m].sum())

    # densest square mile: 20x20-cell moving window over unsmoothed cells
    win = ndimage.uniform_filter(grid, size=20, mode="constant") * 400
    r, c = np.unravel_index(np.argmax(win), win.shape)
    cx, cy = x0 + (c + 0.5) * CELL, y1 - (r + 0.5) * CELL
    lonlat = gpd.GeoSeries(gpd.points_from_xy([cx], [cy]), crs=CRS).to_crs(4326).iloc[0]

    # population-weighted mean centre
    rows, cols = np.indices(grid.shape)
    mc, mr = (grid * cols).sum() / total + 0.5, (grid * rows).sum() / total + 0.5

    smooth = ndimage.gaussian_filter(grid, SIGMA, mode="constant") / np.maximum(den, 1e-9)
    smooth[den < 0.02] = 0
    smooth[~landmask] = 0
    dens = smooth / SQMI_PER_CELL               # people per square mile
    grids.append(dens.astype(np.float32))

    meta_years.append({
        "year": year, "tracts": int(len(g)), "population": int(round(total)),
        "official": OFFICIAL[year], "unplaced": int(lost), "unplacedTracts": lost_codes,
        "borrowedGeometryPop": int(borrowed), "orphans": int(len(orphan)),
        "boroughs": {k: int(round(v)) for k, v in boro_tot.items()},
        "densestSqMi": {"people": int(round(win[r, c])), "col": float(c + 0.5), "row": float(r + 0.5),
                        "lon": round(lonlat.x, 5), "lat": round(lonlat.y, 5)},
        "center": {"col": float(mc), "row": float(mr)},
        "peakSmoothed": float(dens.max()),
    })
    print(year, len(g), "tracts", int(total), "vs", OFFICIAL[year], f"{total/OFFICIAL[year]-1:+.3%}",
          "orphans", len(orphan), "unjoined pop", int(lost), lost_codes[:6], "borrowed", int(borrowed), "densest sq mi", int(win[r, c]),
          f"@ {lonlat.y:.4f},{lonlat.x:.4f}", "peak smoothed", int(dens.max()))

# ----------------------------------------------------------------- encode
DMAX = float(max(g.max() for g in grids))
planes = []
for d in grids:
    q = np.round(np.sqrt(d / DMAX) * 65535).astype(np.uint16)
    delta = np.diff(q.astype(np.int32), axis=1, prepend=0).astype(np.int16).view(np.uint16)
    planes.append(np.concatenate([(delta >> 8).astype(np.uint8).ravel(), (delta & 255).astype(np.uint8).ravel()]))
blob = gzip.compress(np.concatenate(planes).tobytes(), compresslevel=9, mtime=0)
(OUT / "grids.bin.gz").write_bytes(blob)
print(f"grids.bin.gz {len(blob)/1e6:.2f} MB, DMAX {DMAX:.0f}")

# land mask at 3x, antialiased from a 12x rasterisation
S = 3
hi = features.rasterize([(land, 255)], out_shape=(H * S * 4, W * S * 4),
                        transform=from_origin(x0, y1, CELL / S / 4, CELL / S / 4), fill=0, dtype="uint8")
lo = hi.reshape(H * S, 4, W * S, 4).mean(axis=(1, 3)).round().astype(np.uint8)
Image.fromarray(lo, "L").save(OUT / "land.png", optimize=True)

# coastline outline in grid pixel coordinates, for an SVG overlay
def ring_px(ring, tol):
    ring = ring.simplify(tol) if hasattr(ring, "simplify") else ring
    return [[round((x - x0) / CELL, 2), round((y1 - y) / CELL, 2)] for x, y in ring.coords]

boro_paths = {}
for _, b in boros.iterrows():
    geom = b.geometry.simplify(CELL * 0.25)
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    boro_paths[b.boroname] = [ring_px(p.exterior, 0) for p in polys if p.area > (CELL * 2) ** 2]

json.dump({
    "W": W, "H": H, "cell_m": CELL, "sigma_cells": SIGMA, "crs": CRS,
    "origin": [x0, y1], "dmax": DMAX, "landScale": S,
    "years": meta_years, "boroughOutlines": boro_paths,
}, open(OUT / "meta.json", "w"), separators=(",", ":"))
np.save(ROOT / "data" / "grids.npy", np.stack(grids))
np.save(ROOT / "data" / "landmask.npy", landmask)
print("wrote", OUT)
