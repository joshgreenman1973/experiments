"""Build data/lots.json, data/polys.geojson and data/findings.json from build/raw/.
Every number on the page comes from here. See methodology.html for the rules in words."""
import json, os, re, sys, urllib.request, urllib.parse, time
from collections import defaultdict, Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "build", "raw")
OUT = os.path.join(HERE, "..", "data")
os.makedirs(OUT, exist_ok=True)

WINDOW_START = "2024-09-01"
WINDOW_END = "2026-08-31"          # 311 max created_date on build day
QUARTERS = ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3"]
# 2024Q3 is only September; 2026Q3 is July+August. Persistence counts distinct quarters touched, max 9.

def load(name):
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)

def bbl10(v):
    if v is None: return None
    s = str(v).split(".")[0].strip()
    return s if re.fullmatch(r"[1-5]\d{9}", s) else None

BORO_CODE = {"MANHATTAN": "1", "BRONX": "2", "BROOKLYN": "3", "QUEENS": "4", "STATEN ISLAND": "5",
             "MN": "1", "BX": "2", "BK": "3", "QN": "4", "SI": "5", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5"}
BORO_NAME = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}

def mk_bbl(boro, block, lot):
    b = BORO_CODE.get(str(boro).strip().upper())
    try:
        return f"{b}{int(block):05d}{int(lot):04d}" if b else None
    except (TypeError, ValueError):
        return None

def quarter(d):
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"

# ---------------------------------------------------------------- PLUTO vacant land
pluto = load("pluto_vacant.json")
lots = {}
for r in pluto:
    b = bbl10(r.get("bbl"))
    if not b: continue
    ot = (r.get("ownertype") or "").strip()
    lots[b] = {
        "bbl": b, "kind": "V", "borough": BORO_NAME[b[0]], "address": (r.get("address") or "").strip(),
        "owner": (r.get("ownername") or "").strip(), "ownertype": ot or "P",   # blank = private in PLUTO
        "lotarea": int(float(r.get("lotarea") or 0)), "zone": r.get("zonedist1") or "",
        "cd": r.get("cd") or "", "council": r.get("council") or "", "bldgclass": r.get("bldgclass") or "",
        "lat": float(r["latitude"]) if r.get("latitude") else None,
        "lon": float(r["longitude"]) if r.get("longitude") else None,
    }
print("PLUTO vacant land lots:", len(lots))
vacant_bbls = set(lots)

# ---------------------------------------------------------------- signals per BBL
sig = defaultdict(lambda: {
    "c311": Counter(), "c311_q": set(), "c311_first": None, "c311_last": None, "c311_addr": None, "c311_ll": None,
    "lot_res": Counter(),
    "oath": Counter(), "oath_q": set(), "oath_vacantlot": 0, "oath_addr": None,
    "rat": 0, "rat_q": set(), "rat_ll": None,
    "aep": None, "ucp": None, "vacate": None, "stalled": None, "facade": None, "lien": None,
})

c311 = load("c311.json")
n311_nobbl = 0
for r in c311:
    b = bbl10(r.get("bbl"))
    if not b: n311_nobbl += 1; continue
    d = r["created_date"][:10]
    s = sig[b]
    s["c311"][r["complaint_type"]] += 1
    s["c311_q"].add(quarter(d))
    s["c311_first"] = min(s["c311_first"] or d, d); s["c311_last"] = max(s["c311_last"] or d, d)
    if r.get("incident_address"): s["c311_addr"] = r["incident_address"]
    if r.get("latitude") and r.get("longitude"): s["c311_ll"] = (float(r["latitude"]), float(r["longitude"]))
print("311 rows:", len(c311), "without BBL:", n311_nobbl)

def classify_resolution(t):
    t = (t or "").lower()
    if "cleaned the lot" in t or "cleaning crews" in t: return "cleaned"
    if "notified the property owner" in t: return "owner notified"
    if "access warrant" in t or "locked" in t: return "locked, warrant"
    if "isn't a vacant lot" in t or "isn't vacant" in t or "occupied structure" in t: return "not a vacant lot"
    if "couldn't find the condition" in t or "no condition" in t or "didn't find any conditions" in t: return "no condition found"
    if "already exists" in t: return "duplicate"
    if not t: return "open"
    return "other"
for r in load("c311_lot_resolutions.json"):
    b = bbl10(r.get("bbl"))
    if b: sig[b]["lot_res"][classify_resolution(r.get("resolution_description"))] += 1

oath = load("oath.json")
n_oath_nobbl = 0
for r in oath:
    b = mk_bbl(r.get("violation_location_borough"), r.get("violation_location_block_no"), r.get("violation_location_lot_no"))
    if not b: n_oath_nobbl += 1; continue
    d = r["violation_date"][:10]
    s = sig[b]
    s["oath"][r["charge_1_code_description"]] += 1
    s["oath_q"].add(quarter(d))
    if "VACANT LOT" in r["charge_1_code_description"]: s["oath_vacantlot"] += 1
    if r.get("violation_location_house") and r.get("violation_location_street_name"):
        s["oath_addr"] = f'{r["violation_location_house"]} {r["violation_location_street_name"]}'.strip()
print("OATH rows:", len(oath), "without block/lot:", n_oath_nobbl)

rod = load("rodent.json")
for r in rod:
    if r.get("inspection_type") != "Initial": continue
    b = bbl10(r.get("bbl"))
    if not b: continue
    s = sig[b]; s["rat"] += 1; s["rat_q"].add(quarter(r["inspection_date"][:10]))
    if r.get("latitude") and r.get("longitude"): s["rat_ll"] = (float(r["latitude"]), float(r["longitude"]))
print("Rodent failed rows:", len(rod), "initial only:", sum(1 for r in rod if r.get("inspection_type") == "Initial"))

for r in load("aep.json"):
    b = bbl10(r.get("bbl"))
    if b: sig[b]["aep"] = {"start": (r.get("aep_start_date") or "")[:10], "units": r.get("total_units"), "round": r.get("aep_round"),
                          "addr": f'{r.get("phn","")} {r.get("street_address","")}'.strip(), "ll": (float(r["latitude"]), float(r["longitude"])) if r.get("latitude") else None}
for r in load("ucp.json"):
    b = bbl10(r.get("bbl"))
    if b: sig[b]["ucp"] = {"start": (r.get("order_issue_date") or "")[:10], "units": r.get("total_units"),
                          "addr": f'{r.get("phn","")} {r.get("street_name","")}'.strip(), "ll": (float(r["latitude"]), float(r["longitude"])) if r.get("latitude") else None}
for r in load("vacate.json"):
    b = bbl10(r.get("bbl"))
    if b: sig[b]["vacate"] = {"date": (r.get("vacate_effective_date") or "")[:10], "reason": r.get("primary_vacate_reason"), "units": r.get("number_of_vacated_units"),
                             "addr": f'{r.get("house_number","")} {r.get("street_name","")}'.strip(), "ll": (float(r["latitude"]), float(r["longitude"])) if r.get("latitude") else None}
st = load("stalled.json")
bin2bbl = {r["bin"]: bbl10(r.get("base_bbl")) for r in st["footprints"]}
n_stalled_unmatched = 0
addr_path = os.path.join(RAW, "stalled_addr.json")
if os.path.exists(addr_path):
    addr2bbl = json.load(open(addr_path))
else:
    addr2bbl = {}
    BN = {"MANHATTAN": "MN", "BRONX": "BX", "BROOKLYN": "BK", "QUEENS": "QN", "STATEN ISLAND": "SI"}
    todo = [r for r in st["sites"] if not bin2bbl.get(r.get("bin"))]
    for r in todo:
        a = f'{(r.get("house_number") or "").strip()} {(r.get("street_name") or "").strip()}'.strip().upper()
        bo = BN.get((r.get("borough_name") or "").strip().upper())
        if not a or not bo: continue
        q = {"$select": "bbl", "$where": f"borough='{bo}' AND address='{a.replace(chr(39), chr(39)*2)}'", "$limit": 2}
        url = "https://data.cityofnewyork.us/resource/64uk-42ks.json?" + urllib.parse.urlencode(q)
        for t in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as rr: rows = json.load(rr); break
            except Exception as e:
                time.sleep(3 * (2 ** t)); rows = []
        if len(rows) == 1: addr2bbl[a + "|" + bo] = bbl10(rows[0]["bbl"])
    json.dump(addr2bbl, open(addr_path, "w"))
    print("  stalled address matches:", len(addr2bbl), "of", len(todo))
BN2 = {"MANHATTAN": "MN", "BRONX": "BX", "BROOKLYN": "BK", "QUEENS": "QN", "STATEN ISLAND": "SI"}
for r in st["sites"]:
    b = bin2bbl.get(r.get("bin"))
    if not b:
        a = f'{(r.get("house_number") or "").strip()} {(r.get("street_name") or "").strip()}'.strip().upper()
        b = addr2bbl.get(a + "|" + BN2.get((r.get("borough_name") or "").strip().upper(), ""))
    if not b: n_stalled_unmatched += 1; continue
    sig[b]["stalled"] = {"since": (r.get("date_complaint_received") or "")[:10], "addr": f'{r.get("house_number","")} {r.get("street_name","")}'.strip()}
print("Stalled sites:", len(st["sites"]), "run", st["run"], "unmatched BIN:", n_stalled_unmatched)

fac = load("facades.json")
latest = {}
for r in fac:
    k = r.get("bin")
    if not k: continue
    d = (r.get("filing_date") or r.get("submitted_on") or "")
    if k not in latest or d > latest[k][0]: latest[k] = (d, r)
n_unsafe = 0
for k, (d, r) in latest.items():
    if r.get("filing_status") != "UNSAFE": continue
    b = mk_bbl(r.get("borough"), r.get("block"), r.get("lot"))
    if not b: continue
    n_unsafe += 1
    sig[b]["facade"] = {"filed": d[:10], "addr": f'{r.get("house_no","")} {r.get("street_name","")}'.strip()}
print("Facade cycle 9 latest-filing UNSAFE buildings:", n_unsafe)

for r in load("taxlien.json"):
    b = mk_bbl(r.get("borough"), r.get("block"), r.get("lot"))
    if b: sig[b]["lien"] = {"class": r.get("building_class"), "water_only": r.get("water_debt_only") == "Y",
                           "addr": f'{r.get("house_number","")} {r.get("street_name","")}'.strip()}

# ---------------------------------------------------------------- LotSmart history -> today's vacant lots
# LotSmart rows carry a borough id, tax block, house number + street, and a coordinate that is
# shared by many rows (3,404 distinct points for 56,505 rows), so it is a block-face geocode, not
# a lot. PLUTO's vacant lots mostly have no house number. Join rule, in order:
#   1. same borough + block, and the vacant lot's street name is the row's street name;
#      if that leaves one lot, match. If several, take the nearest to the row's coordinate.
#   2. otherwise no match (the lot was built on, or the row's block has no vacant lot on that street).
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from pyproj import Transformer
LS_BORO = {"6": "1", "7": "3", "8": "4", "9": "2", "10": "5"}   # derived by matching block+address; see methodology
def norm(a): return re.sub(r"\s+", " ", (a or "").strip().upper())
def street_of(a):
    a = norm(a)
    return re.sub(r"^[\d\-]+[A-Z]?\s+", "", a)
by_block = defaultdict(list)
for b, L in lots.items():
    by_block[(b[0], int(b[1:6]))].append((b, street_of(L["address"]), L["lat"], L["lon"]))
tr = Transformer.from_crs("EPSG:2263", "EPSG:4326", always_xy=True)
ls_rows = load("lotsmart.json")
# one row per lot record: the file repeats a record once per activity logged against it;
# keep the longest inspector note seen for the record
byid = {}
for r in ls_rows:
    k = r.get("lotid")
    if not k: continue
    if k not in byid: byid[k] = dict(r)
    elif len(r.get("inspectorfindings") or "") > len(byid[k].get("inspectorfindings") or ""):
        byid[k]["inspectorfindings"] = r.get("inspectorfindings")
ls = list(byid.values())
print("LotSmart rows", len(ls_rows), "distinct lot records", len(ls))
hist = defaultdict(lambda: {"n": 0, "amb": 0, "years": set(), "private": 0, "city": 0, "findings": Counter()})
n_tot = n_hit = n_one = n_near = n_noblock = n_nostreet = 0
FIND_WORDS = ["weeds", "litter", "debris", "bulk", "tires", "open", "fenced", "locked", "vacant structure", "abandoned"]
for r in ls:
    n_tot += 1
    bo = LS_BORO.get(str(r.get("boroid")))
    try:
        blk = int(r.get("block") or 0)
    except ValueError:
        blk = 0
    if not bo or not blk or (bo, blk) not in by_block: n_noblock += 1; continue
    st_name = street_of(r.get("streetaddress") or "")
    cands = [c for c in by_block[(bo, blk)] if st_name and c[1] == st_name]
    if not cands: n_nostreet += 1; continue
    if len(cands) == 1:
        b = cands[0][0]; n_one += 1
    else:
        try:
            x, y = float(r.get("coordinatex") or 0), float(r.get("coordinatey") or 0)
        except (TypeError, ValueError):
            x = y = 0
        if not (900000 < x < 1100000 and 100000 < y < 300000): continue
        lon, lat = tr.transform(x, y)
        cands2 = [c for c in cands if c[2] is not None and c[3] is not None]
        if not cands2: continue
        b = min(cands2, key=lambda c: (c[2] - lat) ** 2 + (c[3] - lon) ** 2)[0]; n_near += 1
    h = hist[b]; h["n"] += 1; n_hit += 1
    if len(cands) > 1: h["amb"] += 1
    m = re.match(r"(\d{4})", (r.get("lotentrydate") or r.get("inspectiondate") or ""))
    if m: h["years"].add(int(m.group(1)))
    if r.get("privateind") == "681": h["private"] += 1
    else: h["city"] += 1
    t = (r.get("inspectorfindings") or "").lower()
    for w in FIND_WORDS:
        if w in t: h["findings"][w] += 1
print(f"LotSmart lot records {n_tot}: matched {n_hit} (single lot on street {n_one}, nearest of several {n_near}); "
      f"block has no vacant lot today {n_noblock}; block has vacant lots but none on that street {n_nostreet}; distinct lots {len(hist)}")
polys = load("pluto_polys.geojson")["features"]

# ---------------------------------------------------------------- score
def inwin(d): return bool(d) and d[:10] >= WINDOW_START
def score_of(s):
    """Agencies with a record INSIDE the window. A status listing (AEP, vacate order, stalled
    site, unsafe facade, lien) counts only if it was issued inside the window; older listings
    that are still in force are shown in the lot file but never scored."""
    src = []
    if sum(s["c311"].values()): src.append("311")
    if sum(s["oath"].values()): src.append("DSNY")
    if s["rat"]: src.append("DOHMH")
    if (s["aep"] and inwin(s["aep"]["start"])) or (s["ucp"] and inwin(s["ucp"]["start"])) or (s["vacate"] and inwin(s["vacate"]["date"])): src.append("HPD")
    if (s["stalled"] and inwin(s["stalled"]["since"])) or (s["facade"] and inwin(s["facade"]["filed"])): src.append("DOB")
    if s["lien"]: src.append("DOF")   # the 2025 sale (May 2025) is inside the window
    return src
def stale_of(s):
    """Status listings still in force but issued before the window: shown, not counted."""
    out = []
    if s["aep"] and not inwin(s["aep"]["start"]): out.append("aep")
    if s["ucp"] and not inwin(s["ucp"]["start"]): out.append("ucp")
    if s["vacate"] and not inwin(s["vacate"]["date"]): out.append("vacate")
    if s["stalled"] and not inwin(s["stalled"]["since"]): out.append("stalled")
    if s["facade"] and not inwin(s["facade"]["filed"]): out.append("facade")
    return out

# universe: every vacant lot + every HPD/DOB-listed building + any other lot flagged by 3+ agencies
extra = set()
dist = Counter()
for b, s in sig.items():
    src = score_of(s)
    dist[len(src)] += 1
    if b in vacant_bbls: continue
    hard = bool(s["aep"] or s["ucp"] or s["vacate"] or s["stalled"])
    # a building joins the map only on a hard distress listing, or when four agencies agree,
    # or when three agree and one of them is a lien or an unsafe-facade filing
    if hard or len(src) >= 4 or (len(src) == 3 and (s["lien"] or s["facade"])):
        extra.add(b)
print("BBLs with any signal:", len(sig), "score distribution (all BBLs):", dict(sorted(dist.items())))
print("Extra (non-vacant) universe lots:", len(extra))

# PLUTO attributes for the extra lots (cached)
extra_path = os.path.join(RAW, "pluto_extra.json")
if os.path.exists(extra_path):
    pextra = json.load(open(extra_path))
else:
    pextra = []
    ex = sorted(extra)
    for i in range(0, len(ex), 400):
        chunk = ex[i:i + 400]
        q = {"$select": "bbl,borough,address,ownername,ownertype,lotarea,zonedist1,cd,council,latitude,longitude,bldgclass,landuse,unitsres,numfloors,yearbuilt",
             "$where": "bbl in (" + ",".join(chunk) + ")", "$limit": 1000}
        url = "https://data.cityofnewyork.us/resource/64uk-42ks.json?" + urllib.parse.urlencode(q)
        for t in range(6):
            try:
                with urllib.request.urlopen(url, timeout=120) as r: pextra += json.load(r); break
            except Exception as e:
                print("  pluto extra retry", t, str(e)[:80]); time.sleep(5 * (2 ** t))
        print("  pluto extra", len(pextra), flush=True)
    json.dump(pextra, open(extra_path, "w"))
pex = {}
for r in pextra:
    b = bbl10(r.get("bbl"))
    if b: pex[b] = r
LANDUSE = {"01": "1-2 family", "02": "multifamily walk-up", "03": "multifamily elevator", "04": "mixed residential/commercial",
           "05": "commercial/office", "06": "industrial", "07": "transportation/utility", "08": "public facility/institution",
           "09": "open space/recreation", "10": "parking", "11": "vacant land"}
for b in extra:
    r = pex.get(b, {})
    s = sig[b]
    ll = s["c311_ll"] or s["rat_ll"] or (s["aep"] or {}).get("ll") or (s["ucp"] or {}).get("ll") or (s["vacate"] or {}).get("ll")
    lat = float(r["latitude"]) if r.get("latitude") else (ll[0] if ll else None)
    lon = float(r["longitude"]) if r.get("longitude") else (ll[1] if ll else None)
    addr = (r.get("address") or "").strip() or s["c311_addr"] or s["oath_addr"] or (s["aep"] or s["ucp"] or s["vacate"] or s["stalled"] or {}).get("addr") or ""
    ot = (r.get("ownertype") or "").strip()
    lots[b] = {"bbl": b, "kind": "B", "borough": BORO_NAME[b[0]], "address": addr, "owner": (r.get("ownername") or "").strip(),
               "ownertype": ot or "P", "lotarea": int(float(r.get("lotarea") or 0)), "zone": r.get("zonedist1") or "",
               "cd": r.get("cd") or "", "council": r.get("council") or "", "bldgclass": r.get("bldgclass") or "",
               "landuse": LANDUSE.get(r.get("landuse") or "", ""), "units": r.get("unitsres"), "lat": lat, "lon": lon}

# ---------------------------------------------------------------- assemble records
recs = []
no_coord = 0
for b, L in lots.items():
    s = sig.get(b)
    src = score_of(s) if s else []
    q = (s["c311_q"] | s["oath_q"] | s["rat_q"]) if s else set()
    h = hist.get(b)
    if L["lat"] is None: no_coord += 1; continue
    rec = {
        "bbl": b, "k": L["kind"], "bo": L["borough"], "a": L["address"], "own": L["owner"], "ot": L["ownertype"],
        "area": L["lotarea"], "z": L["zone"], "cd": L["cd"], "cc": L["council"], "bc": L["bldgclass"],
        "lat": round(L["lat"], 6), "lon": round(L["lon"], 6),
        "sc": len(src), "src": src, "pq": len(q),
    }
    if s and stale_of(s): rec["stale"] = stale_of(s)
    if L["kind"] == "B": rec["lu"] = L.get("landuse", ""); rec["u"] = L.get("units")
    if s:
        if sum(s["c311"].values()):
            rec["c311"] = dict(s["c311"]); rec["c311_first"] = s["c311_first"]; rec["c311_last"] = s["c311_last"]
            if s["lot_res"]: rec["lotres"] = dict(s["lot_res"])
        if sum(s["oath"].values()):
            rec["oath"] = sum(s["oath"].values()); rec["oath_top"] = s["oath"].most_common(3); rec["oath_vl"] = s["oath_vacantlot"]
        if s["rat"]: rec["rat"] = s["rat"]
        for k in ("aep", "ucp", "vacate", "stalled", "facade", "lien"):
            if s[k]:
                v = dict(s[k]); v.pop("ll", None); rec[k] = v
    if h:
        rec["hist"] = {"n": h["n"], "amb": h["amb"], "y0": min(h["years"]) if h["years"] else None, "y1": max(h["years"]) if h["years"] else None,
                       "priv": h["private"], "city": h["city"], "f": h["findings"].most_common(4)}
    recs.append(rec)
print("Records:", len(recs), "dropped for no coordinates:", no_coord)

# ---------------------------------------------------------------- polygons for the lots worth drawing
draw = {r["bbl"] for r in recs if r["sc"] >= 1 or r.get("hist") or r["k"] == "B"}
have = {}
for f in polys:
    b = bbl10(f["properties"].get("BBL"))
    if b in draw and f.get("geometry"): have[b] = f["geometry"]
need = sorted(draw - set(have))
poly_extra_path = os.path.join(RAW, "polys_extra.json")
if os.path.exists(poly_extra_path):
    pe = json.load(open(poly_extra_path))
else:
    pe = {}
    ARC = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query"
    for i in range(0, len(need), 300):
        chunk = need[i:i + 300]
        body = urllib.parse.urlencode({"where": "BBL IN (" + ",".join(chunk) + ")", "outFields": "BBL", "f": "geojson", "outSR": "4326", "geometryPrecision": 5}).encode()
        for t in range(6):
            try:
                with urllib.request.urlopen(urllib.request.Request(ARC, data=body), timeout=120) as r:
                    g = json.load(r)
                for f in g.get("features", []):
                    b = bbl10(f["properties"].get("BBL"))
                    if b and f.get("geometry"): pe[b] = f["geometry"]
                break
            except Exception as e:
                print("  poly extra retry", t, str(e)[:80]); time.sleep(5 * (2 ** t))
        print("  polys extra", len(pe), "/", len(need), flush=True)
    json.dump(pe, open(poly_extra_path, "w"))
have.update(pe)
byb = {r["bbl"]: r for r in recs}
feats = [{"type": "Feature", "properties": {"bbl": b, "sc": byb[b]["sc"], "k": byb[b]["k"], "h": 1 if byb[b].get("hist") else 0},
          "geometry": g} for b, g in have.items() if b in byb]
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(OUT, "polys.geojson"), "w"), separators=(",", ":"))
print("Polygons written:", len(feats), "of", len(draw), "wanted")

# ---------------------------------------------------------------- findings
V = [r for r in recs if r["k"] == "V"]
B = [r for r in recs if r["k"] == "B"]
def otname(o): return {"P": "private", "C": "city", "X": "other public", "O": "other public", "M": "mixed"}.get(o, "private")
f1 = [r for r in V if r.get("hist")]
f1_signal = [r for r in f1 if r["sc"] >= 1]
f1_res = [r for r in f1 if r.get("c311")]
f1_top = sorted(f1, key=lambda r: (-r["hist"]["n"], -r["sc"]))[:40]
own = Counter(otname(r["ot"]) for r in V)
own_chronic = Counter(otname(r["ot"]) for r in V if r["sc"] >= 2)
own_hist = Counter(otname(r["ot"]) for r in f1)
own_any = Counter(otname(r["ot"]) for r in V if r["sc"] >= 1)
cd_rows = defaultdict(lambda: {"lots": 0, "res": 0, "insp": 0, "both": 0, "any": 0, "hist": 0, "chronic": 0})
for r in V:
    c = cd_rows[r["cd"] or "?"]; c["lots"] += 1
    rs, ins = bool(r.get("c311")), bool(r.get("oath") or r.get("rat"))
    if rs: c["res"] += 1
    if ins: c["insp"] += 1
    if rs and ins: c["both"] += 1
    if r["sc"] >= 1: c["any"] += 1
    if r["sc"] >= 2: c["chronic"] += 1
    if r.get("hist"): c["hist"] += 1
sc_dist_V = Counter(r["sc"] for r in V)
top_lots = sorted(recs, key=lambda r: (-r["sc"], -r["pq"], -(r.get("hist") or {"n": 0})["n"]))[:60]
lotres = Counter()
for r in V:
    for k, v in (r.get("lotres") or {}).items(): lotres[k] += v
findings = {
    "built": date.today().isoformat(), "window": [WINDOW_START, WINDOW_END], "quarters": len(QUARTERS),
    "counts": {
        "vacant_lots": len(V), "vacant_private": own["private"], "vacant_city": own["city"], "vacant_other_public": own["other public"] + own["mixed"],
        "vacant_any_signal": sum(1 for r in V if r["sc"] >= 1), "vacant_2plus": sum(1 for r in V if r["sc"] >= 2), "vacant_3plus": sum(1 for r in V if r["sc"] >= 3),
        "buildings": len(B), "buildings_hpd": sum(1 for r in B if r.get("aep") or r.get("ucp") or r.get("vacate")),
        "buildings_stalled": sum(1 for r in B if r.get("stalled")), "buildings_3plus": sum(1 for r in B if r["sc"] >= 3),
        "hist_lots": len(f1), "hist_with_signal": len(f1_signal), "hist_with_residents": len(f1_res),
        "hist_requests": sum(r["hist"]["n"] for r in f1), "hist_ambiguous": sum(1 for r in f1 if r["hist"]["amb"] > r["hist"]["n"] / 2),
        "raw": {"c311": len(c311), "c311_nobbl": n311_nobbl, "oath": len(oath), "oath_nobbl": n_oath_nobbl, "rodent_initial": sum(1 for r in rod if r.get("inspection_type") == "Initial"),
                "aep": sum(1 for s in sig.values() if s["aep"]), "ucp": sum(1 for s in sig.values() if s["ucp"]), "vacate": sum(1 for s in sig.values() if s["vacate"]),
                "aep_inwin": sum(1 for s in sig.values() if s["aep"] and inwin(s["aep"]["start"])), "ucp_inwin": sum(1 for s in sig.values() if s["ucp"] and inwin(s["ucp"]["start"])),
                "vacate_inwin": sum(1 for s in sig.values() if s["vacate"] and inwin(s["vacate"]["date"])), "stalled_inwin": sum(1 for s in sig.values() if s["stalled"] and inwin(s["stalled"]["since"])),
                "facade_inwin": sum(1 for s in sig.values() if s["facade"] and inwin(s["facade"]["filed"])),
                "stalled": len(st["sites"]), "stalled_run": st["run"][:10], "stalled_unmatched": n_stalled_unmatched, "facade_unsafe": n_unsafe,
                "lien": sum(1 for s in sig.values() if s["lien"]), "lotsmart_requests": n_tot, "lotsmart_on_vacant": n_hit, "lotsmart_noblock": n_noblock, "lotsmart_nostreet": n_nostreet,
                "all_bbls_with_signal": len(sig), "score_dist_all": dict(sorted(dist.items()))},
    },
    "score_dist_vacant": dict(sorted(sc_dist_V.items())),
    "ownership": {"all": dict(own), "any_signal": dict(own_any), "chronic": dict(own_chronic), "hist": dict(own_hist)},
    "lot_condition_resolutions": dict(lotres),
    "cd": dict(cd_rows),
    "hist_top_note": "records = distinct sanitation lot records 2010-2021 tied to this lot",
    "hist_top": [{"bbl": r["bbl"], "a": r["a"], "bo": r["bo"], "ot": otname(r["ot"]), "n": r["hist"]["n"], "y0": r["hist"]["y0"], "y1": r["hist"]["y1"], "sc": r["sc"], "src": r["src"], "area": r["area"]} for r in f1_top],
    "top": [{"bbl": r["bbl"], "a": r["a"], "bo": r["bo"], "k": r["k"], "ot": otname(r["ot"]), "sc": r["sc"], "src": r["src"], "pq": r["pq"], "hist": (r.get("hist") or {}).get("n", 0)} for r in top_lots],
}
json.dump(findings, open(os.path.join(OUT, "findings.json"), "w"), indent=1)
json.dump({"meta": {"built": findings["built"], "window": findings["window"]}, "lots": recs}, open(os.path.join(OUT, "lots.json"), "w"), separators=(",", ":"))
print("findings:", json.dumps(findings["counts"], indent=1))
print("vacant score dist:", findings["score_dist_vacant"])
print("ownership:", findings["ownership"])
print("lot condition resolutions:", findings["lot_condition_resolutions"])
