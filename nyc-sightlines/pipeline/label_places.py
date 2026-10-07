"""Give each farthest-view spot in a findings file a short, specific place label.

Usage: python label_places.py FINDINGS_JSON DATA_DIR   (rewrites the file, adding "label" to each "farthest")
The label is the named park, cemetery or nature area the spot is in, if any; otherwise the part of the
neighbourhood (NTA) name nearest the spot, judged by Overture's neighbourhood points (an NTA like
"Pelham Bay-Country Club-City Island" covers several places, and "Pelham Bay" alone would be wrong for City Island).
"""
import sys, json, re, geopandas as gpd
from shapely.geometry import Point
import grid

F, DATA = sys.argv[1:3]
res = json.load(open(F))
lu = gpd.read_parquet(f"{DATA}/overture/base_land_use.parquet", columns=["names", "class", "geometry"])
lu["name"] = lu.names.apply(lambda n: n["primary"] if n is not None else None)
lu = lu[lu.name.notna() & ~lu.name.str.lower().isin(["cemetery", "park", "playground", "garden", "golf course", "graveyard"]) & lu["class"].isin(["park", "cemetery", "grave_yard", "nature_reserve", "golf_course", "recreation_ground", "beach_resort"])
        & lu.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].to_crs(grid.CRS)
dv = gpd.read_parquet(f"{DATA}/overture/divisions_division.parquet", columns=["names", "subtype", "geometry"])
dv["name"] = dv.names.apply(lambda n: n["primary"] if n is not None else None)
dv = dv[dv.subtype.isin(["neighborhood", "macrohood", "microhood"])].to_crs(grid.CRS)
norm = lambda s: re.sub(r"[^a-z]", "", s.lower())


def label(f):
    x, y = gpd.GeoSeries([Point(f["lon"], f["lat"])], crs=4326).to_crs(grid.CRS).iloc[0].coords[0]
    p = Point(x, y)
    inside = lu[lu.contains(p)]
    if not inside.empty:
        return inside.assign(a=inside.area).sort_values("a").name.iloc[0]
    if (f.get("nta") or "").startswith("park-cemetery-etc") or not f.get("nta"):
        d = lu.distance(p)
        return lu.name[d.idxmin()] if d.min() < 300 else f.get("boro")
    parts = [s for s in f["nta"].split("-") if s]
    near = dv.assign(d=dv.distance(p)).sort_values("d")
    for nm in near.name.head(8):
        for part in parts:
            if norm(part) == norm(nm):
                return part
    return parts[0]


for lm in res["landmarks"]:
    if lm.get("farthest"):
        lm["farthest"]["label"] = label(lm["farthest"])
        print(f'{lm["id"]:11s} {lm["farthest"]["km"] / 1.609344:5.1f} mi  {lm["farthest"]["label"]}  ({lm["farthest"]["nta"]})')
json.dump(res, open(F, "w"), indent=1)
