"""One-off repair for grids built before build_dsm excluded neighbouring counties from the shoreline fill:
cells outside NYC Planning's borough polygons that fall inside Nassau, Westchester or New Jersey counties go back
to 'other land' (9). Usage: python fix_outside.py GRID_DIR DATA_DIR"""
import sys, numpy as np, geopandas as gpd
from rasterio.features import rasterize
import grid
G, SRC = sys.argv[1:3]
shape = (grid.H, grid.W); T = grid.transform()
boro = np.load(f"{G}/boro.npy")
nybb = gpd.read_file(f"{SRC}/nycgeo/NYC_geography/nybb_20a/nybb.shp").to_crs(grid.CRS)
city = rasterize(((g, 1) for g in nybb.geometry), out_shape=shape, transform=T, dtype=np.uint8).astype(bool)
da = gpd.read_parquet(f"{SRC}/overture/divisions_division_area.parquet")
da["name"] = da.names.apply(lambda n: n["primary"])
nyc_counties = {"New York County", "Bronx County", "Kings County", "Queens County", "Richmond County"}
others = da[(da.subtype == "county") & (da.is_land == True) & ~da.name.isin(nyc_counties)].to_crs(grid.CRS)
outside = rasterize(((g, 1) for g in others.geometry), out_shape=shape, transform=T, dtype=np.uint8).astype(bool)
m = (boro >= 1) & (boro <= 5) & ~city & outside
print("cells returned to other land:", int(m.sum()), "km2", m.sum() * 9 / 1e6, "by borough", np.bincount(boro[m], minlength=6)[1:].tolist())
boro[m] = 9
np.save(f"{G}/boro.npy", boro)
