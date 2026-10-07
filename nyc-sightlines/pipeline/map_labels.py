"""Street and neighbourhood names for the map, so a close-up reads like a street map.

Usage: python map_labels.py GRID_DIR DATA_DIR OUT_TXT
Writes gzip'd JSON as base64 text (the artifact host serves text): {"streets": {...}, "hoods": [...]}, all in world
coordinates (metres east of the grid's west edge, south of its north edge).
Streets: named Overture road segments in the five boroughs, merged by name into continuous runs; each run gets label
anchors spaced along it, with the street's direction there and the length of street the label may use ("room").
Neighbourhoods: Overture neighbourhood points inside the city (plazas, triangles and the like left out).
"""
import sys, re, json, gzip, base64, numpy as np, geopandas as gpd
from shapely.ops import linemerge
from shapely.geometry import MultiLineString
import grid

G, DATA, OUT = sys.argv[1:4]
boro = np.load(f"{G}/boro.npy", mmap_mode="r")
RANK = {"motorway": 0, "trunk": 0, "primary": 1, "secondary": 2, "tertiary": 3, "residential": 4, "unclassified": 4,
        "living_street": 4, "pedestrian": 5}
SPACING = {0: 900, 1: 350, 2: 320, 3: 300, 4: 250, 5: 200}
WORDS = {"Street": "St", "Avenue": "Ave", "Boulevard": "Blvd", "Road": "Rd", "Place": "Pl", "Parkway": "Pkwy",
         "Drive": "Dr", "Lane": "Ln", "Expressway": "Expwy", "Highway": "Hwy", "Terrace": "Ter", "Court": "Ct",
         "Turnpike": "Tpke", "Square": "Sq"}
DIRS = {"West": "W", "East": "E", "North": "N", "South": "S"}


def short(name):
    w = name.split()
    if len(w) > 2 and w[0] in DIRS and w[1][0].isdigit():      # West 42nd Street -> W 42nd St (but West End Ave stays)
        w[0] = DIRS[w[0]]
    if len(w) > 1 and w[-1] in WORDS:
        w[-1] = WORDS[w[-1]]
    return " ".join(w)


def in_city(x, y):
    r, c = grid.to_rc(x, y)
    r, c = int(r), int(c)
    return 0 <= r < grid.H and 0 <= c < grid.W and 1 <= boro[r, c] <= 5


s = gpd.read_parquet(f"{DATA}/overture/transportation_segment.parquet", columns=["subtype", "class", "names", "geometry"])
s = s[(s.subtype == "road") & s["class"].isin(RANK)]
s["name"] = s.names.apply(lambda n: n["primary"] if n is not None else None)
s = s[s.name.notna()].to_crs(grid.CRS)
mid = s.geometry.interpolate(0.5, normalized=True)
s = s[[in_city(p.x, p.y) for p in mid]]
s["rank"] = s["class"].map(RANK)
names, X, Y, A, N, C, R = [], [], [], [], [], [], []
idx = {}
for (nm, rank), grp in s.groupby(["name", "rank"]):
    merged = linemerge(MultiLineString([g for geom in grp.geometry for g in (geom.geoms if geom.geom_type == "MultiLineString" else [geom])]))
    runs = merged.geoms if merged.geom_type == "MultiLineString" else [merged]
    label = short(nm)
    for run in runs:
        L = run.length
        if L < 40:
            continue
        n = max(1, int(L // SPACING[rank]))
        room = L / n
        for i in range(n):
            d = (i + 0.5) * room
            h = min(30.0, room / 2)
            p0, p1, p = run.interpolate(max(0, d - h)), run.interpolate(min(L, d + h)), run.interpolate(d)
            # world y points south, so screen angle = atan2(-(dNorth), dEast); keep text upright
            ang = np.degrees(np.arctan2(-(p1.y - p0.y), p1.x - p0.x))
            if ang > 90: ang -= 180
            if ang <= -90: ang += 180
            if label not in idx:
                idx[label] = len(names); names.append(label)
            X.append(round(p.x - grid.X0)); Y.append(round(grid.Y1 - p.y)); A.append(round(ang))
            N.append(idx[label]); C.append(rank); R.append(round(room))

dv = gpd.read_parquet(f"{DATA}/overture/divisions_division.parquet", columns=["names", "subtype", "geometry"])
dv["name"] = dv.names.apply(lambda n: n["primary"] if n is not None else None)
dv = dv[dv.subtype.isin(["macrohood", "neighborhood", "microhood"]) & dv.name.notna()].to_crs(grid.CRS)
skip = re.compile(r"Square|Triangle|Plaza|Circle|Mall|Park$|Homes|Houses|Station$|^PATH|Historic District|Community Board|Waterfront District|Navy Yard")
hoods = []
for nm, st, g in zip(dv.name, dv.subtype, dv.geometry):
    if skip.search(nm) or nm in ("Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island") or not in_city(g.x, g.y):
        continue
    hoods.append([nm, round(g.x - grid.X0), round(grid.Y1 - g.y), {"macrohood": 0, "neighborhood": 1, "microhood": 1}[st]])
seen = set(); hoods = [h for h in hoods if not (h[0] in seen or seen.add(h[0]))]
out = {"streets": {"names": names, "x": X, "y": Y, "a": A, "n": N, "c": C, "r": R}, "hoods": hoods}
raw = json.dumps(out, separators=(",", ":")).encode()
open(OUT, "w").write(base64.b64encode(gzip.compress(raw, 9)).decode())
print(f"{len(names)} street names, {len(X)} anchors, {len(hoods)} neighbourhoods; {len(raw) / 1e6:.1f} MB raw")
