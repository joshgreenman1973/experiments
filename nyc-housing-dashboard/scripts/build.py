#!/usr/bin/env python3
"""
Who builds New York - turn the raw inputs into the page's data.

Writes data/dashboard.json (all district numbers), data/council.geojson,
data/cd.geojson (simplified shapes) and data/hpd_buildings.csv (download).
Every check that fails stops the build.
"""
import csv
import json
import math
import os
from collections import defaultdict

from shapely.geometry import Point, shape, mapping, Polygon, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data")

FIRST, LAST = 2010, 2026          # Housing Database years; 2026 runs through June 30
HPD_FIRST = 2014                  # HPD production data starts Jan. 1, 2014
TARGET_CITY_5YR = 350_000         # draft Fair Housing Growth Strategy, citywide five-year target
AMI2026 = {1: 118_800, 2: 135_700, 3: 152_700, 4: 169_600}  # HPD 2026, 100% AMI


def load(name):
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fail(msg):
    raise SystemExit("FATAL: " + msg)


# ---------- geography ----------
def districts(fname, key, keep):
    feats = load(fname)["features"]
    out = {}
    for f in feats:
        k = int(f["properties"][key])
        if not keep(k):
            continue
        g = shape(f["geometry"])
        out[k] = g if k not in out else out[k].union(g)
    return out


council = districts("council.geojson", "CounDist", lambda k: 1 <= k <= 51)
# Community districts: drop the 12 joint interest areas (parks, airports), coded 64+ within a borough
cd = districts("cd.geojson", "BoroCD", lambda k: k % 100 <= 18)
if len(council) != 51 or len(cd) != 59:
    fail(f"expected 51 council and 59 community districts, got {len(council)} and {len(cd)}")


def write_shapes(geoms, fname, tol=0.00025):
    feats = []
    for k, g in sorted(geoms.items()):
        s = g.simplify(tol, preserve_topology=True)
        # d3 draws spherical polygons: exterior rings must run clockwise
        if isinstance(s, Polygon):
            s = orient(s, sign=-1.0)
        else:
            s = MultiPolygon([orient(q, sign=-1.0) for q in s.geoms])
        gj = mapping(s)
        def rnd(c):
            return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
        gj = {"type": gj["type"], "coordinates": rnd(gj["coordinates"])}
        feats.append({"type": "Feature", "properties": {"id": k}, "geometry": gj})
    with open(os.path.join(OUT, fname), "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))


write_shapes(council, "council.geojson")
write_shapes(cd, "cd.geojson")


def locator(geoms):
    keys = list(geoms)
    tree = STRtree([geoms[k] for k in keys])
    def find(lon, lat):
        p = Point(lon, lat)
        for i in tree.query(p):
            if geoms[keys[i]].covers(p):
                return keys[i]
        return None
    return find


in_council, in_cd = locator(council), locator(cd)

# ---------- 2020 population and tract-to-district weights ----------
blocks = load("blocks2020.json")
pop = {"council": defaultdict(float), "cd": defaultdict(float)}
w = {"council": defaultdict(lambda: defaultdict(float)), "cd": defaultdict(lambda: defaultdict(float))}
tract_pop = defaultdict(float)
unplaced_pop = 0
for b in blocks:
    p = num(b["POP100"])
    if p <= 0:
        continue
    lon, lat = num(b["INTPTLON"]), num(b["INTPTLAT"])
    tract = b["GEOID"][:11]
    tract_pop[tract] += p
    c, d = in_council(lon, lat), in_cd(lon, lat)
    if c is None:
        unplaced_pop += p
    else:
        pop["council"][c] += p
        w["council"][tract][c] += p
    if d is not None:
        pop["cd"][d] += p
        w["cd"][tract][d] += p
total_pop = sum(tract_pop.values())
print(f"2020 population {total_pop:,.0f}; in council districts {sum(pop['council'].values()):,.0f}; "
      f"in community districts {sum(pop['cd'].values()):,.0f}")
if abs(total_pop - 8_804_190) > 1000:
    fail(f"2020 block population {total_pop:,.0f} does not match the census count of 8,804,190")
if unplaced_pop > 2000:
    fail(f"{unplaced_pop:,.0f} residents fell outside every council district")

# ---------- ACS 2020-2024, allocated tract -> district by 2020 population ----------
acs = load("acs2024_tracts.json")


def acs_alloc(level, group, cols):
    """Sum ACS tract estimates into districts using population weights."""
    out = defaultdict(lambda: [0.0] * len(cols))
    for r in acs[group]:
        tract = r["state"] + r["county"] + r["tract"]
        tp = tract_pop.get(tract, 0)
        if tp <= 0:
            continue
        vals = [max(num(r.get(c)), 0) for c in cols]
        for dist, p in w[level][tract].items():
            share = p / tp
            for i, v in enumerate(vals):
                out[dist][i] += v * share
    return out


INC_EDGES = [0, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 60000, 75000,
             100000, 125000, 150000, 200000, None]
INC_COLS = [f"B19001_{i:03d}E" for i in range(2, 18)]
# B25063: gross rent for renter-occupied units paying cash rent (cols 003-026)
GR_EDGES = [0, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900,
            1000, 1250, 1500, 2000, 2500, 3000, 3500, None]
GR_COLS = [f"B25063_{i:03d}E" for i in range(3, 27)]
# B25061: rent asked for vacant-for-rent units (cols 002-025), same brackets as B25063
RA_EDGES = GR_EDGES
RA_COLS = [f"B25061_{i:03d}E" for i in range(2, 26)]


def check_cols(group, cols):
    have = acs[group][0].keys()
    missing = [c for c in cols if c not in have]
    if missing:
        fail(f"ACS {group} is missing {missing[:3]}; bracket layout changed")


def median_from_brackets(counts, edges):
    total = sum(counts)
    if total <= 0:
        return None
    half, run = total / 2, 0
    for i, c in enumerate(counts):
        if run + c >= half:
            lo, hi = edges[i], edges[i + 1]
            if hi is None:
                return lo  # median in the open top bracket: report its floor
            return lo + (half - run) / c * (hi - lo) if c else lo
        run += c
    return None


def share_below(counts, edges, cutoff):
    total = sum(counts)
    if total <= 0:
        return None
    under = 0
    for i, c in enumerate(counts):
        lo, hi = edges[i], edges[i + 1]
        if hi is not None and hi <= cutoff:
            under += c
        elif lo < cutoff and (hi is None or hi > cutoff):
            if hi is None:
                break
            under += c * (cutoff - lo) / (hi - lo)
    return under / total


for g, cols in [("B19001", INC_COLS), ("B25063", GR_COLS), ("B25061", RA_COLS)]:
    check_cols(g, cols)

# Rents a two-person household could pay at 30 percent of income
RENT60 = AMI2026[2] * 0.60 * 0.30 / 12
RENT100 = AMI2026[2] * 1.00 * 0.30 / 12

acsd = {}
for level in ("council", "cd"):
    inc = acs_alloc(level, "B19001", INC_COLS)
    hh = acs_alloc(level, "B11001", ["B11001_001E"])
    ten = acs_alloc(level, "B25003", ["B25003_001E", "B25003_002E", "B25003_003E"])
    gr = acs_alloc(level, "B25063", GR_COLS)
    ra = acs_alloc(level, "B25061", RA_COLS)
    burden = acs_alloc(level, "B25070", [f"B25070_{i:03d}E" for i in range(1, 12)])
    vac = acs_alloc(level, "B25004", ["B25004_002E"])
    out = {}
    for k in (council if level == "council" else cd):
        b = burden[k]
        computed = b[0] - b[10]  # all renters minus "not computed"
        out[k] = {
            "medinc": round(median_from_brackets(inc[k], INC_EDGES) or 0),
            "households": round(hh[k][0]),
            "renter_share": round(ten[k][2] / ten[k][0], 3) if ten[k][0] else None,
            "gross_rent_median": round(median_from_brackets(gr[k], GR_EDGES) or 0),
            "occ_aff60": round(share_below(gr[k], GR_EDGES, RENT60), 3),
            "occ_aff100": round(share_below(gr[k], GR_EDGES, RENT100), 3),
            "vac_for_rent": round(vac[k][0]),
            "asked_median": round(median_from_brackets(ra[k], RA_EDGES) or 0),
            "asked_aff60": (round(share_below(ra[k], RA_EDGES, RENT60), 3) if sum(ra[k]) >= 150 else None),
            "burdened": round((b[6] + b[7] + b[8] + b[9]) / computed, 3) if computed else None,
            "severe": round(b[9] / computed, 3) if computed else None,
        }
    acsd[level] = out

# Citywide check: median from all tracts' brackets vs the published city figure
city_inc = [0.0] * len(INC_COLS)
for r in acs["B19001"]:
    for i, c in enumerate(INC_COLS):
        city_inc[i] += max(num(r.get(c)), 0)
city_med = median_from_brackets(city_inc, INC_EDGES)
print(f"citywide median household income from brackets: ${city_med:,.0f}")

# ---------- Housing Database ----------
P = load("hdb_projects.json")
if len({p.get("version") for p in P}) != 1:
    fail("mixed Housing Database versions")
HDB_VERSION = P[0]["version"]


def zero_series():
    return [0] * (LAST - FIRST + 1)


def blank():
    return {"comp_net": zero_series(), "comp_gain": zero_series(), "comp_loss": zero_series(),
            "permit_net": zero_series(), "pipeline": 0, "nb_units": zero_series(),
            "afford_hdb": zero_series(), "big": []}


agg = {"council": defaultdict(blank), "cd": defaultdict(blank), "city": defaultdict(blank)}
missing_geo = {"council": 0, "cd": 0}
unmatched_cd = 0
for p in P:
    st = p.get("job_status", "")
    net = num(p.get("classanet"))
    ckey = int(num(p.get("councildst"))) if p.get("councildst") else None
    dkey = int(num(p.get("commntydst"))) if p.get("commntydst") else None
    if dkey is not None and dkey not in cd:
        unmatched_cd += 1  # joint interest areas (parks, airports)
        dkey = None
    targets = [("city", 0)]
    if ckey in council:
        targets.append(("council", ckey))
    else:
        missing_geo["council"] += 1
    if dkey is not None:
        targets.append(("cd", dkey))
    else:
        missing_geo["cd"] += 1
    cy = int(num(p.get("compltyear"))) if p.get("compltyear") else None
    py = int(num(p.get("permityear"))) if p.get("permityear") else None
    for lvl, k in targets:
        a = agg[lvl][k]
        if st.startswith("5") and cy and FIRST <= cy <= LAST:
            i = cy - FIRST
            a["comp_net"][i] += net
            if net > 0:
                a["comp_gain"][i] += net
            else:
                a["comp_loss"][i] -= net
            if p.get("job_type") == "New Building":
                a["nb_units"][i] += num(p.get("classaprop"))
            a["afford_hdb"][i] += num(p.get("hpdaffrdbl"))
            if lvl != "city" and net >= 50:
                a["big"].append({"addr": f"{p.get('addressnum','')} {p.get('addressst','')}".strip().title(),
                                 "net": int(net), "year": cy, "type": p.get("job_type"),
                                 "aff": int(num(p.get("hpdaffrdbl")))})
        if st[:1] in "345" and py and FIRST <= py <= LAST:
            a["permit_net"][py - FIRST] += net
        if st[:1] == "3":
            a["pipeline"] += net

print(f"jobs with no council district: {missing_geo['council']}; no community district: {missing_geo['cd']} "
      f"({unmatched_cd} in parks or airports)")

# Check against DCP's own summary tables
for lvl, fname, key in [("council", "hdb_council.json", "councildst"), ("cd", "hdb_cd.json", "commntydst")]:
    off = load(fname)
    worst = 0
    for s in off:
        k = int(num(s[key]))
        if k not in agg[lvl]:
            continue
        mine = sum(agg[lvl][k]["comp_net"])
        theirs = sum(num(s.get(f"comp{y}")) for y in range(FIRST, LAST + 1))
        worst = max(worst, abs(mine - theirs))
    print(f"{lvl}: worst district gap vs DCP summary, 2010-2026 net completions: {worst:,.0f}")
    if worst > 2500:
        fail(f"{lvl} completions drift from DCP's own summary by {worst:,.0f}")

# ---------- HPD Affordable Housing Production ----------
H = load("hpd_buildings.json")
TIERS = ["extremely_low_income_units", "very_low_income_units", "low_income_units",
         "moderate_income_units", "middle_income_units", "other_income_units"]
hpd_rows = []
for h in H:
    sd = (h.get("project_start_date") or "")[:10]
    if not sd:
        continue
    cdcode = h.get("community_board", "")  # e.g. "MN-03"
    boro = {"MN": 1, "BX": 2, "BK": 3, "QN": 4, "SI": 5}.get(cdcode[:2])
    cdk = boro * 100 + int(cdcode[3:]) if boro and cdcode[3:].isdigit() else None
    cck = int(num(h.get("council_district"))) if h.get("council_district") else None
    hpd_rows.append({
        "project": h.get("project_name", ""), "pid": h.get("project_id"),
        "addr": f"{h.get('house_number','') or ''} {h.get('street_name','') or ''}".strip().title() or "Address withheld",
        "boro": h.get("borough", ""), "cd": cdk if cdk in cd else None,
        "cc": cck if cck in council else None,
        "start": sd, "done": (h.get("building_completion_date") or h.get("project_completion_date") or "")[:10],
        "type": h.get("reporting_construction_type"),
        "tiers": [int(num(h.get(t))) for t in TIERS],
        "counted": int(num(h.get("all_counted_units"))), "total": int(num(h.get("total_units"))),
        "rent": int(num(h.get("counted_rental_units"))), "own": int(num(h.get("counted_homeownership_units"))),
    })
tier_sum_gap = sum(abs(sum(r["tiers"]) - r["counted"]) for r in hpd_rows)
print(f"HPD buildings: {len(hpd_rows):,}; counted units {sum(r['counted'] for r in hpd_rows):,}; "
      f"tier-vs-counted mismatch {tier_sum_gap}")
if tier_sum_gap > 0.01 * sum(r["counted"] for r in hpd_rows):
    fail("HPD income tiers do not add up to counted units")
no_cc = sum(1 for r in hpd_rows if r["cc"] is None)
no_cd = sum(1 for r in hpd_rows if r["cd"] is None)
print(f"HPD buildings with no council district: {no_cc}; no community district: {no_cd}")

with open(os.path.join(OUT, "hpd_buildings.csv"), "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["project_id", "project_name", "address", "borough", "community_district", "council_district",
                 "start_date", "completion_date", "type", "extremely_low", "very_low", "low", "moderate",
                 "middle", "other", "counted_units", "total_units"])
    for r in sorted(hpd_rows, key=lambda r: r["start"]):
        wr.writerow([r["pid"], r["project"], r["addr"], r["boro"], r["cd"] or "", r["cc"] or "", r["start"],
                     r["done"], r["type"], *r["tiers"], r["counted"], r["total"]])

# ---------- targets ----------
targets = {}
with open(os.path.join(ROOT, "research", "fhgs_targets_draft_2026-08-19.csv")) as f:
    for r in csv.DictReader(f):
        targets[int(r["borocd"])] = {"name": r["name"], "laa": r["laa"] == "True", "cohort": r["cohort"],
                                     "homes2025": int(r["homes2025"]), "goal": int(r["goal5yr"]),
                                     "goal_aff": int(r["affordable"]), "goal_deep": int(r["deeply"]),
                                     "goal_homeless": int(r["homeless"])}
if set(targets) != set(cd):
    fail("target table does not cover exactly the 59 community districts")

members = json.load(open(os.path.join(ROOT, "research", "council_members_2026-10-22.json")))["members"]

BORO = {1: "Manhattan", 2: "Bronx", 3: "Brooklyn", 4: "Queens", 5: "Staten Island"}


def pack(lvl, k):
    a = agg[lvl][k]
    a["big"].sort(key=lambda b: -b["net"])
    d = {"comp": [round(x) for x in a["comp_net"]], "gain": [round(x) for x in a["comp_gain"]],
         "loss": [round(x) for x in a["comp_loss"]], "permit": [round(x) for x in a["permit_net"]],
         "pipeline": round(a["pipeline"]), "afford_hdb": [round(x) for x in a["afford_hdb"]],
         "big": a["big"][:5]}
    if lvl != "city":
        d["pop20"] = round(pop[lvl][k])
        d.update(acsd[lvl][k])
    return d


out = {
    "meta": {"hdb_version": HDB_VERSION, "first": FIRST, "last": LAST, "hpd_first": HPD_FIRST,
             "target_city_5yr": TARGET_CITY_5YR, "pop20": round(total_pop),
             "rent60": round(RENT60), "rent100": round(RENT100), "ami2": AMI2026[2],
             "city_medinc_brackets": round(city_med), "built": "2026-10-22"},
    "city": pack("city", 0),
    "council": {}, "cd": {},
    "hpd": [[r["cc"], r["cd"], int(r["start"][:4]), 0 if r["type"] == "New Construction" else 1, *r["tiers"]]
            for r in hpd_rows],
    "hpd_list": [[r["project"], r["addr"], r["boro"][:2], r["cc"], r["cd"], r["start"], r["done"],
                  "N" if r["type"] == "New Construction" else "P", r["counted"], *r["tiers"]] for r in hpd_rows],
}
for k in sorted(council):
    d = pack("council", k)
    m = members.get(str(k), {})
    d["member"] = m.get("member")
    d["boro"] = m.get("borough")
    out["council"][k] = d
for k in sorted(cd):
    d = pack("cd", k)
    d.update(targets[k])
    d["boro"] = BORO[k // 100]
    out["cd"][k] = d

with open(os.path.join(OUT, "dashboard.json"), "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("wrote data/dashboard.json", os.path.getsize(os.path.join(OUT, "dashboard.json")) // 1024, "KB")
