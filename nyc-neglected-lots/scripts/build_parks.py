"""Parks and playgrounds layer: data/parks.geojson + parks block in data/findings.json.
Three eyes on each park property: neighbors (311 park maintenance complaints inside the
property's boundary), the Parks Department's own inspectors (Parks Inspection Program ratings)
and health inspectors (initial rodent inspections failed for rat activity inside the boundary).
Run after build_data.py (it appends to findings.json)."""
import json, os, re
from collections import defaultdict, Counter
from shapely.geometry import shape, Point, mapping
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "build", "raw")
OUT = os.path.join(HERE, "..", "data")
WINDOW_START = "2024-09-01"
def load(n): return json.load(open(os.path.join(RAW, n)))
def quarter(d): return f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"
BORO = {"M": "Manhattan", "X": "Bronx", "B": "Brooklyn", "Q": "Queens", "R": "Staten Island"}

# ---------------------------------------------------------------- properties
parks = {}
geoms, gid = [], []
for f in load("parks.geojson")["features"]:
    p = f["properties"]
    if p.get("retired") in (True, "true", "True"): continue
    if not f.get("geometry"): continue
    try:
        g = shape(f["geometry"])
        if not g.is_valid: g = g.buffer(0)
    except Exception:
        continue
    k = p.get("omppropid") or p.get("gispropnum")
    if not k: continue
    parks[k] = {"id": k, "name": p.get("signname") or k, "type": p.get("typecategory") or "", "acres": float(p.get("acres") or 0),
                "bo": BORO.get((p.get("borough") or "")[:1], p.get("borough") or ""), "cb": p.get("communityboard") or "", "cc": p.get("councildistrict") or "",
                "ratable": p.get("pip_ratable") in (True, "true", "True"), "geom": g,
                "c311": Counter(), "c311_q": set(), "insp": 0, "u": 0, "u_clean": 0, "u_q": set(), "u_last": None, "zones": set(), "rat": 0, "rat_q": set()}
    geoms.append(g); gid.append(k)
tree = STRtree(geoms)
print("park properties:", len(parks))
byname = defaultdict(list)
for k, P in parks.items(): byname[(P["name"].strip().lower(), P["bo"])].append(k)
BORO311 = {"MANHATTAN": "Manhattan", "BRONX": "Bronx", "BROOKLYN": "Brooklyn", "QUEENS": "Queens", "STATEN ISLAND": "Staten Island"}
NEAR_M = 30   # metres; 311 park complaints are geocoded to the nearest address, usually across the street

def hit(lat, lon):
    p = Point(lon, lat)
    for i in tree.query(p):
        try:
            if geoms[i].contains(p): return gid[i]
        except Exception:
            pass
    return None

# ---------------------------------------------------------------- 311 park maintenance complaints
# placed, in order: inside a property boundary; else by the park name 311 recorded (unique within
# the borough); else the nearest property within NEAR_M metres; else dropped.
c = load("c311_parks.json"); how = Counter()
def nearest_within(lat, lon, m):
    p = Point(lon, lat); i = tree.nearest(p)
    try:
        d = geoms[i].distance(p) * 111000
    except Exception:
        return None
    return gid[i] if d <= m else None
for r in c:
    k = None
    try:
        lat, lon = float(r["latitude"]), float(r["longitude"])
    except (KeyError, TypeError, ValueError):
        lat = lon = None
    if lat is not None: k = hit(lat, lon)
    if k: how["inside"] += 1
    else:
        nm = (r.get("park_facility_name") or "").strip().lower()
        cands = byname.get((nm, BORO311.get((r.get("park_borough") or "").upper(), ""))) if nm and nm != "unspecified" else None
        if cands and len(cands) == 1: k = cands[0]; how["name"] += 1
        elif lat is not None:
            k = nearest_within(lat, lon, NEAR_M)
            if k: how["nearest"] += 1
    if not k: how["dropped"] += 1; continue
    P = parks[k]; P["c311"][r["descriptor"]] += 1; P["c311_q"].add(quarter(r["created_date"][:10]))
n_in = len(c) - how["dropped"]
print("311 park complaints:", len(c), dict(how))

# ---------------------------------------------------------------- PIP ratings; zone ids like B073-ZN28 roll up to B073
pip = load("pip.json"); n_unmatched = 0
for r in pip:
    pid = r["prop_id"]; base = re.split(r"-", pid)[0]
    P = parks.get(pid) or parks.get(base)
    if not P: n_unmatched += 1; continue
    P["insp"] += 1; P["zones"].add(pid)
    if r.get("overall_condition") == "U" or r.get("cleanliness") == "U":
        P["u"] += 1; P["u_q"].add(quarter(r["date"][:10]))
        if r.get("cleanliness") == "U": P["u_clean"] += 1
        P["u_last"] = max(P["u_last"] or "", r["date"][:10])
print("PIP inspections:", len(pip), "unmatched to a property:", n_unmatched)

# ---------------------------------------------------------------- rat inspections inside parks
rod = load("rodent.json"); n_rat = 0
for r in rod:
    if r.get("inspection_type") != "Initial": continue
    try:
        k = hit(float(r["latitude"]), float(r["longitude"]))
    except (KeyError, TypeError, ValueError):
        continue
    if not k: continue
    n_rat += 1; parks[k]["rat"] += 1; parks[k]["rat_q"].add(quarter(r["inspection_date"][:10]))
print("failed initial rat inspections inside a park:", n_rat)

# ---------------------------------------------------------------- score
# neighbors: 3 or more maintenance complaints in the window (one call about a big park is not a signal)
# Parks inspectors: unacceptable on 2 or more inspections in the window
# health: 1 or more failed initial inspections inside the boundary
feats = []; sc_dist = Counter(); recs = []
for k, P in parks.items():
    src = []
    n311 = sum(P["c311"].values())
    if n311 >= 3: src.append("311")
    if P["u"] >= 2: src.append("Parks")
    if P["rat"] >= 1: src.append("DOHMH")
    q = P["c311_q"] | P["u_q"] | P["rat_q"]
    sc_dist[len(src)] += 1
    rec = {"id": k, "k": "P", "a": P["name"], "t": P["type"], "acres": round(P["acres"], 2), "bo": P["bo"], "cb": P["cb"], "cc": P["cc"],
           "sc": len(src), "src": src, "pq": len(q), "n311": n311, "c311": dict(P["c311"]) if n311 else None,
           "insp": P["insp"], "u": P["u"], "u_clean": P["u_clean"], "u_last": P["u_last"], "zones": len(P["zones"]), "rat": P["rat"]}
    cen = P["geom"].representative_point()
    rec["lat"] = round(cen.y, 6); rec["lon"] = round(cen.x, 6)
    recs.append(rec)
    if len(src) >= 1 or P["u"] >= 1 or n311 >= 1:
        g = P["geom"].simplify(0.00004, preserve_topology=True)
        feats.append({"type": "Feature", "properties": {"id": k, "sc": len(src), "k": "P"}, "geometry": mapping(g)})
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(OUT, "parks.geojson"), "w"), separators=(",", ":"))
json.dump({"parks": recs}, open(os.path.join(OUT, "parks.json"), "w"), separators=(",", ":"))
print("park records:", len(recs), "drawn:", len(feats), "score dist:", dict(sorted(sc_dist.items())))

# findings
insp = [r for r in recs if r["insp"] >= 3]
worst = sorted(insp, key=lambda r: (-(r["u"] / r["insp"]), -r["u"]))[:40]
F = json.load(open(os.path.join(OUT, "findings.json")))
F["parks"] = {
    "properties": len(recs), "inspected": sum(1 for r in recs if r["insp"]), "inspections": len(pip), "pip_unmatched": n_unmatched,
    "c311": len(c), "c311_inside": n_in, "c311_how": dict(how), "rat_inside": n_rat,
    "any_signal": sum(1 for r in recs if r["sc"] >= 1), "two_plus": sum(1 for r in recs if r["sc"] >= 2), "three": sum(1 for r in recs if r["sc"] >= 3),
    "u_two_plus": sum(1 for r in recs if r["u"] >= 2), "u_three_plus": sum(1 for r in recs if r["u"] >= 3),
    "by_type_flagged": dict(Counter(r["t"] for r in recs if r["sc"] >= 2).most_common()),
    "by_type_all": dict(Counter(r["t"] for r in recs).most_common()),
    "worst": [{"id": r["id"], "a": r["a"], "t": r["t"], "bo": r["bo"], "insp": r["insp"], "u": r["u"], "sc": r["sc"], "src": r["src"], "n311": r["n311"]} for r in worst],
    "pip_max_date": max(r["date"][:10] for r in pip),
}
json.dump(F, open(os.path.join(OUT, "findings.json"), "w"), indent=1)
print("parks findings:", {k: v for k, v in F["parks"].items() if k not in ("worst", "by_type_flagged", "by_type_all")})
