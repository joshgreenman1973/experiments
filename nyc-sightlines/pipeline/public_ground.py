"""Rasterize 'public ground': streets and sidewalks (buffered road centrelines), parks, plazas, beaches.

Usage: python public_ground.py GRID_DIR DATA_DIR  -> GRID_DIR/public.npy (uint8 0/1)
Roads are buffered to typical New York right-of-way half-widths (building line to building line),
so the mask covers sidewalks as well as the roadway. Highways are left out: nobody stands on them.
"""
import sys, numpy as np, geopandas as gpd, pandas as pd
from rasterio.features import rasterize
import grid

G, DATA = sys.argv[1:3]
HALF = {"primary": 15, "secondary": 15, "tertiary": 12, "residential": 9, "unclassified": 9,
        "living_street": 7, "pedestrian": 5, "footway": 2, "path": 2, "cycleway": 2, "steps": 2, "service": 4}
s = gpd.read_parquet(f"{DATA}/overture/transportation_segment.parquet", columns=["subtype", "class", "subclass", "geometry"])
s = s[(s.subtype == "road") & s["class"].isin(HALF) & ~s.subclass.isin(["driveway", "parking_aisle"])].to_crs(grid.CRS)
geoms = s.geometry.buffer(s["class"].map(HALF).values, cap_style="flat")
lu = gpd.read_parquet(f"{DATA}/overture/base_land_use.parquet", columns=["class", "geometry"])
lu = lu[lu["class"].isin(["pedestrian", "plaza"]) & lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
land = gpd.read_parquet(f"{DATA}/overture/base_land.parquet", columns=["class", "geometry"])
beach = land[(land["class"] == "beach") & land.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
mask = rasterize(((g, 1) for g in pd.concat([geoms, lu.geometry, beach.geometry])), out_shape=(grid.H, grid.W),
                 transform=grid.transform(), dtype=np.uint8)
cls = np.load(f"{G}/cls.npy"); boro = np.load(f"{G}/boro.npy")
nyc_open = ((cls == 1) | (cls == 3)) & (boro >= 1) & (boro <= 5)
pub = (nyc_open & ((mask == 1) | (cls == 3))).astype(np.uint8)
np.save(f"{G}/public.npy", pub)
print("public cells", int(pub.sum()), "km2", pub.sum() * 9 / 1e6, "of open", int(nyc_open.sum()) * 9 / 1e6)
