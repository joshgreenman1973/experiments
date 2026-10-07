"""Build the 3 m digital surface model (terrain + buildings) and land-class grids.

Inputs (directory passed as argv[1]):
  overture/building.parquet, overture/building_part.parquet, overture/base_land_use.parquet,
  overture/divisions_division_area.parquet, dem/USGS_13_*.tif, nycgeo/NYC_geography/nybb_20a/nybb.shp
Outputs (argv[2]): ground.npy, dsm.npy, cls.npy, boro.npy (memory-mappable)
"""
import sys, time, glob
import numpy as np, geopandas as gpd, pandas as pd, rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
import grid

SRC, OUT = sys.argv[1], sys.argv[2]
T = grid.transform()
shape = (grid.H, grid.W)
t0 = time.time()
def log(*a): print(f"[{time.time()-t0:6.0f}s]", *a, flush=True)

# 1. Terrain ---------------------------------------------------------------
ground = np.full(shape, np.nan, np.float32)
for f in sorted(glob.glob(f"{SRC}/dem/USGS_13_*.tif")):
    with rasterio.open(f) as ds:
        tmp = np.full(shape, np.nan, np.float32)
        reproject(rasterio.band(ds, 1), tmp, dst_transform=T, dst_crs=grid.CRS,
                  resampling=Resampling.bilinear, dst_nodata=np.nan)
        ok = np.isnan(ground) & ~np.isnan(tmp)
        ground[ok] = tmp[ok]
ground = np.nan_to_num(ground, nan=0.0)
log("terrain", float(np.nanmin(ground)), float(np.nanmax(ground)))

# 2. Land / borough mask --------------------------------------------------------
# Coastline-derived land (OpenStreetMap via Overture) plus piers, then the city's own
# shoreline-clipped borough boundaries on top. Codes: 1-5 boroughs (DCP BoroCode), 9 other land.
boro = np.zeros(shape, np.uint8)
land = gpd.read_parquet(f"{SRC}/overture/base_land.parquet", columns=["subtype", "class", "geometry"])
land = land[(land.subtype == "land") & land.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
rasterize(((g, 9) for g in land.geometry), out=boro, transform=T)
inf = gpd.read_parquet(f"{SRC}/overture/base_infrastructure.parquet", columns=["class", "geometry"])
piers = inf[(inf["class"] == "pier") & inf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
rasterize(((g, 9) for g in piers.geometry), out=boro, transform=T)
nybb = gpd.read_file(f"{SRC}/nycgeo/NYC_geography/nybb_20a/nybb.shp").to_crs(grid.CRS)
city = rasterize(((g, int(c)) for g, c in zip(nybb.geometry, nybb.BoroCode)), out_shape=shape, transform=T, dtype=np.uint8)
# Piers and slivers within 250 m of the city's shoreline join the nearest borough.
from scipy.ndimage import distance_transform_edt
dist, (ir, ic) = distance_transform_edt(city == 0, return_indices=True)
m = (boro == 9) & (city == 0) & (dist * grid.RES <= 250)
boro[m] = city[ir[m], ic[m]]
del dist, ir, ic, m
boro[city > 0] = city[city > 0]
del city
log("boroughs", np.bincount(boro.ravel(), minlength=10))

# 3. Green space --------------------------------------------------------------
lu = gpd.read_parquet(f"{SRC}/overture/base_land_use.parquet", columns=["subtype", "class", "geometry"])
keep = (lu["class"].isin(["park", "nature_reserve", "cemetery", "golf_course", "recreation_ground", "dog_park", "grave_yard"]))
lu = lu[keep & lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
green = rasterize(((g, 1) for g in lu.geometry), out_shape=shape, transform=T, dtype=np.uint8)
log("green cells", int(green.sum()))

# 4. Buildings -------------------------------------------------------------------
def ground_at(geoms):
    c = geoms.representative_point()
    r, cc = grid.to_rc(c.x.values, c.y.values)
    r = np.clip(r.astype(int), 0, grid.H - 1); cc = np.clip(cc.astype(int), 0, grid.W - 1)
    return ground[r, cc]

b = gpd.read_parquet(f"{SRC}/overture/building.parquet",
                     columns=["id", "geometry", "height", "num_floors", "has_parts", "is_underground"])
b = b[b.is_underground != True]
b = b[b.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
h = b.height.copy()
h = h.fillna(b.num_floors * 3.3 + 1.0).fillna(8.0).clip(lower=3.0)
b["h"] = h.astype(float)
b["base"] = ground_at(b.geometry)
log("buildings", len(b))

p = gpd.read_parquet(f"{SRC}/overture/building_part.parquet", columns=["building_id", "geometry", "height", "num_floors"])
p = p[p.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
p["h"] = p.height.fillna(p.num_floors * 3.3 + 1.0)
p = p[p.h.notna() & (p.h > 0)]
base_by_id = dict(zip(b.id, b.base))
p["base"] = p.building_id.map(base_by_id)
miss = p.base.isna()
p.loc[miss, "base"] = ground_at(p.geometry[miss])
# Outlines that have parts sit at the height of their lowest part (the podium); parts add the towers.
min_part = p.groupby("building_id").h.min()
wp = b.id.isin(min_part.index)
b.loc[wp, "h"] = np.minimum(b.loc[wp, "h"], b.loc[wp, "id"].map(min_part))
log("parts", len(p), "outlines with parts", int(wp.sum()))

shapes = pd.concat([
    pd.DataFrame({"geometry": b.geometry.values, "top": (b.base + b.h).values}),
    pd.DataFrame({"geometry": p.geometry.values, "top": (p.base + p.h).values}),
]).sort_values("top")
btop = rasterize(zip(shapes.geometry, shapes.top.astype(np.float32)), out_shape=shape, transform=T,
                 fill=-9999.0, dtype=np.float32)
log("rasterized buildings")

isb = btop > ground + 1.0
dsm = np.where(isb, btop, ground).astype(np.float32)
# Woods block views even with the leaves off: mapped forest of a hectare or more becomes an 18 m
# canopy. Smaller patches are mostly young plantings in landscaped parks and are left out.
land = gpd.read_parquet(f"{SRC}/overture/base_land.parquet", columns=["subtype", "class", "geometry"])
woods = land[(land.subtype == "forest") & land.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
woods = woods[woods.area >= 10_000]
canopy = rasterize(((g, 1) for g in woods.geometry), out_shape=shape, transform=T, dtype=np.uint8).astype(bool) & ~isb
dsm[canopy] = ground[canopy] + 18.0
log("woodland cells", int(canopy.sum()))
np.save(f"{OUT}/woods.npy", canopy.astype(np.uint8))
del canopy, land, woods
cls = np.zeros(shape, np.uint8)            # 0 water
cls[boro > 0] = 1                          # open land
cls[(boro > 0) & (green == 1)] = 3         # parks, cemeteries, etc.
cls[isb] = 2                               # building (anywhere, incl. piers)
log("classes", np.bincount(cls.ravel(), minlength=4))

np.save(f"{OUT}/ground.npy", ground)
np.save(f"{OUT}/dsm.npy", dsm)
np.save(f"{OUT}/cls.npy", cls)
np.save(f"{OUT}/boro.npy", boro)
log("saved", grid.H, grid.W)
