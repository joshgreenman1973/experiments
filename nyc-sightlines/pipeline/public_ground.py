"""Rasterize 'public ground': streets and sidewalks (buffered road centrelines), parks, plazas, beaches.

Usage: python public_ground.py GRID_DIR DATA_DIR  -> GRID_DIR/public.npy (uint8 0/1)
Roads are buffered to typical New York right-of-way half-widths (building line to building line),
so the mask covers sidewalks as well as the roadway. Highways are left out: nobody stands on them.
Inside fenced land (industry, rail yards, airports, power plants, construction sites, military land) only
mapped public streets, parks and plazas count; the service roads and paths there are private. Places closed to
the public, or open only by appointment or on tours, are left out entirely: Rikers Island, Hart Island and
Freshkills Park (except fields within it that are mapped as parks of their own, such as Owl Hollow).
"""
import sys, numpy as np, geopandas as gpd, pandas as pd
from rasterio.features import rasterize
import grid

G, DATA = sys.argv[1:3]
shape = (grid.H, grid.W); T = grid.transform()
ras = lambda geoms: rasterize(((g, 1) for g in geoms), out_shape=shape, transform=T, dtype=np.uint8).astype(bool)
HALF = {"primary": 15, "secondary": 15, "tertiary": 12, "residential": 9, "unclassified": 9,
        "living_street": 7, "pedestrian": 5, "footway": 2, "path": 2, "cycleway": 2, "steps": 2, "service": 4}
MINOR = {"footway", "path", "cycleway", "steps", "service"}
s = gpd.read_parquet(f"{DATA}/overture/transportation_segment.parquet", columns=["subtype", "class", "subclass", "geometry"])
s = s[(s.subtype == "road") & s["class"].isin(HALF) & ~s.subclass.isin(["driveway", "parking_aisle"])].to_crs(grid.CRS)
buf = s.geometry.buffer(s["class"].map(HALF).values, cap_style="flat")
minor = s["class"].isin(MINOR).values
lu = gpd.read_parquet(f"{DATA}/overture/base_land_use.parquet", columns=["names", "class", "geometry"])
lu = lu[lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
lu["name"] = lu.names.apply(lambda n: n["primary"] if n is not None else None)
plaza = lu[lu["class"].isin(["pedestrian", "plaza"])]
park = lu[lu["class"].isin(["park", "dog_park", "recreation_ground"])]
land = gpd.read_parquet(f"{DATA}/overture/base_land.parquet", columns=["names", "class", "geometry"])
land = land[land.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
land["name"] = land.names.apply(lambda n: n["primary"] if n is not None else None)
beach = land[land["class"] == "beach"]
inf = gpd.read_parquet(f"{DATA}/overture/base_infrastructure.parquet", columns=["subtype", "class", "geometry"])
inf = inf[inf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)

main = ras(pd.concat([buf[~minor], plaza.geometry, beach.geometry]))
paths = ras(buf[minor])
fenced = ras(pd.concat([
    lu[lu["class"].isin(["industrial", "works", "military", "base", "training_area", "obstacle_course", "landfill",
                         "railway", "construction", "brownfield", "quarry"])].geometry,
    inf[(inf.subtype == "airport") | inf["class"].isin(["plant", "substation"])].geometry]))
closed = ras(pd.concat([land[land.name.isin(["Rikers Island", "Hart Island"])].geometry,
                        lu[lu.name == "Freshkills Park"].geometry]))
parks = ras(park.geometry)

cls = np.load(f"{G}/cls.npy"); boro = np.load(f"{G}/boro.npy")
nyc_open = ((cls == 1) | (cls == 3)) & (boro >= 1) & (boro <= 5)
pub = nyc_open & (main | (paths & ~fenced) | ((cls == 3) & ~fenced) | parks)
pub &= ~closed | parks
old = np.load(f"{G}/public.npy").astype(bool) if len(sys.argv) > 3 else None
np.save(f"{G}/public.npy", pub.astype(np.uint8))
print("public km2", pub.sum() * 9 / 1e6, "of open", int(nyc_open.sum()) * 9 / 1e6)
print("dropped: fenced paths", (nyc_open & paths & fenced & ~main & ~parks).sum() * 9 / 1e6,
      "closed", (nyc_open & closed & ~parks).sum() * 9 / 1e6)
