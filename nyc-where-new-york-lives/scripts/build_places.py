"""Add map labels and a neighborhood lookup grid to assets/meta.json.

  - places: a short list of neighborhoods to label, projected to grid pixels
  - nta.bin.gz: uint16 index of the 2020 Neighborhood Tabulation Area under
    each grid cell (0 = none), so a click can be named; names go in meta.json
Run after build_grids.py.
"""
import json, gzip
from pathlib import Path
import numpy as np
import geopandas as gpd
from pyproj import Transformer
from rasterio import features
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
meta = json.load(open(OUT / "meta.json"))
W, H, CELL = meta["W"], meta["H"], meta["cell_m"]
x0, y1 = meta["origin"]
tr = Transformer.from_crs(4326, meta["crs"], always_xy=True)

# label anchor, lat, lon, which side of the dot the text sits on
PLACES = [
    ("Lower East Side", 40.7150, -73.9843, "l"),
    ("Harlem", 40.8116, -73.9465, "l"),
    ("Upper East Side", 40.7736, -73.9566, "r"),
    ("Washington Heights", 40.8417, -73.9394, "l"),
    ("Midtown", 40.7549, -73.9840, "l"),
    ("Grand Concourse", 40.8340, -73.9180, "r"),
    ("Co-op City", 40.8740, -73.8295, "r"),
    ("Williamsburg", 40.7081, -73.9571, "r"),
    ("Brownsville", 40.6631, -73.9098, "r"),
    ("Flatbush", 40.6415, -73.9594, "l"),
    ("Coney Island", 40.5755, -73.9707, "r"),
    ("Flushing", 40.7580, -73.8303, "r"),
    ("Jamaica", 40.7027, -73.7890, "r"),
    ("St. George", 40.6437, -74.0776, "r"),
    ("Rockaway", 40.5860, -73.8160, "r"),
]
places = []
for name, lat, lon, side in PLACES:
    x, y = tr.transform(lon, lat)
    places.append({"name": name, "col": round((x - x0) / CELL, 2), "row": round((y1 - y) / CELL, 2), "side": side})

nta = gpd.read_file(ROOT.parent / "nyc-child-density" / "data" / "nyc_nta_2020.geojson").to_crs(meta["crs"])
nta = nta.reset_index(drop=True)
T = from_origin(x0, y1, CELL, CELL)
idx = features.rasterize(((g, i + 1) for i, g in enumerate(nta.geometry)), out_shape=(H, W),
                         transform=T, fill=0, dtype="uint16")
(OUT / "nta.bin.gz").write_bytes(gzip.compress(idx.astype("<u2").tobytes(), 9, mtime=0))

meta["places"] = places
meta["ntas"] = [{"name": r.ntaname, "boro": r.boroname, "type": str(r.ntatype)} for r in nta.itertuples()]
json.dump(meta, open(OUT / "meta.json", "w"), separators=(",", ":"))
print(len(places), "places,", len(nta), "NTAs")
