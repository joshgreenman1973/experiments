#!/usr/bin/env python3
"""Build data files for nyc-school-building-utilization ("The empty classroom and the crowded one").

Version 2 (Nov. 6, 2026): building coordinates now come from each building's own address
(DCP Facilities Database geocodes of LCGMS addresses, then the 2019-20 School Locations file,
then NYC GeoSearch), never from a school's main site; each building gets the grade bands its
schools serve (LCGMS "Grades Final"); each school's class-size counts are assigned to one
building only; near pairs are reported by grade match; District 75 and District 79 programs
are left out of the under-one-roof comparison.

Sources (all on disk in nyc-schools-atlas/data/sources/):
  1. NYC School Construction Authority / NYC Public Schools "Enrollment, Capacity & Utilization Report"
     (the Blue Book), Target Calculation, via NYC Open Data dataset gkd7-3vk7:
     nyc_sca_enrollment_capacity_utilization_gkd7-3vk7_all_vintages_thru_2025-26.csv
  2. DOE LCGMS school directory (2026-10-07), 2019-20 School Locations (wg9x-4ke6),
     and nyc-schools-atlas schools.json / capacity.json / class_size.json for coordinates,
     Org-to-DBN crosswalk, and state class-size cap compliance (Education Law 211-d, Table C, Oct. 31, 2025).
"""
import io
import json
import math
import os
import re
from collections import Counter, defaultdict

import pandas as pd

ATLAS_ROOT = "/Users/joshgreenman/Experiments/nyc-schools-atlas"
BB_CSV = os.path.join(ATLAS_ROOT, "data/sources/nyc_sca_enrollment_capacity_utilization_gkd7-3vk7_all_vintages_thru_2025-26.csv")
LCGMS_XLS = os.path.join(ATLAS_ROOT, "data/sources/nyc_doe_lcgms_school_data_2026-10-07.xls")
LOC1920_CSV = os.path.join(ATLAS_ROOT, "data/sources/nyc_doe_school_locations_2019-20_wg9x-4ke6.csv")
SCHOOLS_JSON = os.path.join(ATLAS_ROOT, "data/schools.json")
CAP_JSON = os.path.join(ATLAS_ROOT, "data/metrics/capacity.json")
CS_JSON = os.path.join(ATLAS_ROOT, "data/metrics/class_size.json")
FACDB_JSON = os.path.join(ATLAS_ROOT, "data/sources/facdb_doe_lcgms_2026-07.json")
GEOSEARCH_JSON = os.path.join(ATLAS_ROOT, "data/sources/geosearch_cache_lcgms_2026-10.json")

GRADE_BANDS = {"ES": {"PK", "0K", "01", "02", "03", "04", "05"}, "MS": {"06", "07", "08"}, "HS": {"09", "10", "11", "12"}}


def bands_of(grades_final):
    toks = set(re.findall(r"PK|0K|SE|\d\d", str(grades_final or "")))
    return {k for k, v in GRADE_BANDS.items() if toks & v}


def norm_addr(a):
    return re.sub(r"\s+", " ", str(a).upper().strip())

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "data")
os.makedirs(OUT_DIR, exist_ok=True)

VINTAGES = [
    ("04/27/2015", "2013-14", 2014),
    ("09/12/2017", "2015-16", 2016),
    ("01/08/2018", "2016-17", 2017),
    ("01/31/2019", "2017-18", 2018),
    ("12/18/2019", "2018-19", 2019),
    ("01/04/2023", "2021-22", 2022),
    ("09/09/2026", "2025-26", 2026),
]

ORG_RE = re.compile(r"^[MXKQR]\d{3}$")
BORO_BY_LETTER = {
    "M": "Manhattan",
    "X": "Bronx",
    "K": "Brooklyn",
    "Q": "Queens",
    "R": "Staten Island",
}


def to_int(v):
    v = (v or "").strip().replace(",", "")
    if v == "":
        return None
    return int(float(v))


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main():
    df = pd.read_csv(BB_CSV, dtype=str, keep_default_na=False)
    for c in df.columns:
        df[c] = df[c].str.strip()

    # Load crosswalks and school metadata
    raw_lcgms = open(LCGMS_XLS, "rb").read().decode("utf-16")
    lc = pd.read_html(
        io.StringIO(raw_lcgms),
        header=0,
        converters={"ATS System Code": str, "Location Code": str, "Building Code": str},
    )[0].fillna("")
    loc1920 = pd.read_csv(LOC1920_CSV, dtype=str, keep_default_na=False)
    schools = {s["dbn"]: s for s in json.load(open(SCHOOLS_JSON))}
    cap_meta = json.load(open(CAP_JSON))
    cs_schools = json.load(open(CS_JSON))["schools"]
    cw_org_to_dbn = {v["org_id"]: dbn for dbn, v in cap_meta["crosswalk"].items()}

    # Building ID -> coordinates, from the building's own address. Order of preference:
    #   1. DCP Facilities Database geocode of the LCGMS primary address for a location in that building
    #   2. 2019-20 School Locations (wg9x-4ke6) row whose primary building code is that building
    #   3. NYC GeoSearch geocode of the LCGMS address (cached)
    # v1 fell back to a school's main-site coordinates for annexes, which put about 20 buildings
    # more than 0.1 mile from where they are. That fallback is gone; such buildings stay unmapped.
    fac = json.load(open(FACDB_JSON))
    facll = {}
    for f in fac:
        try:
            facll[(norm_addr(f["address"]), str(f["zipcode"])[:5])] = (float(f["latitude"]), float(f["longitude"]))
        except (KeyError, ValueError, TypeError):
            pass
    geos = json.load(open(GEOSEARCH_JSON))
    BORO_NAME = {"M": "Manhattan", "X": "Bronx", "K": "Brooklyn", "Q": "Queens", "R": "Staten Island"}
    grades_by_loc = {}
    loc_cat = {}
    bldg_info = {}
    for _, r in lc.iterrows():
        loc = str(r["Location Code"]).strip().upper()
        grades_by_loc[loc] = str(r["Grades Final"])
        loc_cat[loc] = str(r["Location Category Description"])
        bc = str(r["Building Code"]).strip().upper()
        if not bc or str(r["Primary Address"]).strip() in ("", "NOT AVAILABLE"):
            continue
        info = bldg_info.setdefault(bc, {"address": str(r["Primary Address"]).strip(), "zip": str(r["Zip"]).strip()[:5],
                                         "nta": str(r["NTA_Name"]).strip(), "lat": None, "lon": None, "method": None})
        k = (norm_addr(r["Primary Address"]), str(r["Zip"]).strip()[:5])
        if info["lat"] is None and k in facll:
            info["lat"], info["lon"] = facll[k]
            info["method"] = "facdb_address"
    for _, r in loc1920.iterrows():
        bc = str(r.get("Primary_building_code", r.get("building_code", ""))).strip().upper()
        lat, lon = str(r.get("LATITUDE", r.get("latitude", ""))).strip(), str(r.get("LONGITUDE", r.get("longitude", ""))).strip()
        if not bc or lat in ("", "NULL"):
            continue
        info = bldg_info.setdefault(bc, {"address": str(r.get("primary_address_line_1", "")).strip(), "zip": "",
                                         "nta": str(r.get("NTA_Name", r.get("nta_name", ""))).strip(), "lat": None, "lon": None, "method": None})
        if info["lat"] is None:
            try:
                info["lat"], info["lon"] = float(lat), float(lon)
                info["method"] = "school_locations_2019_20"
            except ValueError:
                pass
    for bc, info in bldg_info.items():
        if info["lat"] is None and info["address"]:
            key = f"{info['address']}, {BORO_NAME.get(bc[0], '')} {info['zip']}"
            g = geos.get(key)
            if g and g.get("lat"):
                info["lat"], info["lon"], info["method"] = g["lat"], g["lon"], "geosearch"
    bldg_coords = {bc: {"lat": round(i["lat"], 5), "lon": round(i["lon"], 5), "address": i["address"], "zip": i["zip"],
                        "nta": i["nta"], "method": i["method"]} for bc, i in bldg_info.items() if i["lat"] is not None}
    d26 = df[df["Data As Of"] == "09/09/2026"].copy()
    # Last resort, for map display only: the coordinates of a school housed in the building. For an
    # annex this can be the school's main site, so these buildings are drawn but left out of every
    # distance comparison.
    for _, r in d26.iterrows():
        bc = r["Bldg ID"].upper()
        dbn = cw_org_to_dbn.get(r["Org ID"].upper())
        if bc and bc not in bldg_coords and dbn and dbn in schools and schools[dbn].get("lat"):
            bldg_coords[bc] = {"lat": round(float(schools[dbn]["lat"]), 5), "lon": round(float(schools[dbn]["lon"]), 5),
                               "address": "", "zip": schools[dbn].get("zip", ""), "nta": schools[dbn].get("neighborhood", ""),
                               "method": "school_main_site"}

    # 1. Historical series across all 7 Blue Book editions in gkd7-3vk7
    history = []
    for dao, sy, spring in VINTAGES:
        sub = df[df["Data As Of"] == dao]
        if len(sub) < 2500:
            raise SystemExit(f"Unexpectedly few rows ({len(sub)}) for {dao}")
        b = sub.drop_duplicates("Bldg ID").copy()
        b["e"] = b["Bldg Enroll"].apply(to_int)
        b["c"] = b["Target Bldg Cap"].apply(to_int)
        b["u"] = b["Target Bldg Util"].apply(to_int)
        b_valid = b[b["c"].notnull() & (b["c"] > 0)].copy()
        b_active = b_valid[b_valid["e"].notnull() & (b_valid["e"] > 0)].copy()

        tot_e = int(b_valid["e"].fillna(0).sum())
        tot_c = int(b_valid["c"].sum())
        history.append(
            {
                "data_as_of": dao,
                "school_year": sy,
                "spring": spring,
                "buildings_total_rows": len(b),
                "buildings": len(b_valid),
                "buildings_active": len(b_active),
                "enrollment": tot_e,
                "capacity": tot_c,
                "overall_util_pct": round(100 * tot_e / tot_c, 1),
                "under_50": int((b_valid["u"] < 50).sum()),
                "under_60": int((b_valid["u"] < 60).sum()),
                "under_60_active": int((b_active["u"] < 60).sum()),
                "under_70": int((b_valid["u"] < 70).sum()),
                "between_60_100": int(((b_valid["u"] >= 60) & (b_valid["u"] <= 100)).sum()),
                "over_100": int((b_valid["u"] > 100).sum()),
                "at_or_over_100": int((b_valid["u"] >= 100).sum()),
                "over_110": int((b_valid["u"] > 110).sum()),
                "over_120": int((b_valid["u"] > 120).sum()),
                "empty_seats_net": tot_c - tot_e,
            }
        )

    # 2. Build 2025-26 building-level records with housed organizations and class-size cap data
    b26_groups = defaultdict(list)
    for _, r in d26.iterrows():
        if r["Bldg ID"]:
            b26_groups[r["Bldg ID"]].append(r)

    # Each school's class-size counts belong to one building: the one holding most of its students.
    primary_bldg = {}
    best_e = {}
    for _, r in d26.iterrows():
        oid = r["Org ID"].upper()
        dbn = cw_org_to_dbn.get(oid)
        oe = to_int(r["Org Enroll"]) or 0
        if dbn and r["Incl. Class"] == "" and oe > best_e.get(dbn, -1):
            best_e[dbn] = oe
            primary_bldg[dbn] = r["Bldg ID"]
    loc_grades_1920 = {str(r["location_code"]).strip().upper(): str(r["Grades_final_text"]) for _, r in loc1920.iterrows()}

    buildings = []
    colocated_splits = []
    total_bldg_rows = len(b26_groups)
    dropped_zero_cap = 0

    for bid, rows in sorted(b26_groups.items()):
        r0 = rows[0]
        be = to_int(r0["Bldg Enroll"])
        bc = to_int(r0["Target Bldg Cap"])
        bu = to_int(r0["Target Bldg Util"])
        if not bc or bc <= 0:
            dropped_zero_cap += 1
            continue

        boro = BORO_BY_LETTER.get(bid[0], "")
        dist = int(r0["Geo Dist"]) if r0["Geo Dist"].isdigit() else 0
        coord = bldg_coords.get(bid)

        # Parse organizations housed in this building
        orgs = []
        school_orgs_with_cap = []
        has_charter = False
        has_d75 = False
        bldg_nonexempt_classes = 0
        bldg_compliant_classes = 0
        bldg_over_cap_classes = 0
        bldg_exempt_classes = 0
        bldg_space_exempt = False

        for r in rows:
            oid = r["Org ID"]
            oname = r["Organization Name"]
            incl = r["Incl. Class"]
            oe = to_int(r["Org Enroll"])
            oc = to_int(r["Org Target Cap"])
            ou = to_int(r["Org Target Util"])
            is_school_org = bool(ORG_RE.match(oid))
            dbn = cw_org_to_dbn.get(oid) if is_school_org else None
            s_meta = schools.get(dbn, {}) if dbn else {}
            sector = s_meta.get("sector", "")
            if "CHARTER" in oname.upper() or sector == "charter" or (dbn and dbn.startswith("84")):
                is_charter = True
                if incl == "":
                    has_charter = True
            else:
                is_charter = False
            is_d75 = bool(dbn and dbn.startswith("75")) or incl != ""
            is_d79 = bool(dbn and dbn.startswith("79")) or oname.startswith("ALC ") or "PATHWAYS TO GRADUATION" in oname.upper()
            if dbn and dbn.startswith("75"):
                has_d75 = True
            grades = grades_by_loc.get(oid.upper()) or loc_grades_1920.get(oid.upper()) or ""

            # Class size compliance for this org if in District 1-32 Table C
            cs = cs_schools.get(dbn) if dbn and incl == "" and primary_bldg.get(dbn) == bid else None
            if cs and cs.get("cap_n_nonexempt_classes") is not None:
                ne = cs["cap_n_nonexempt_classes"] or 0
                ov = cs["cap_n_over"] or 0
                ex = cs["cap_n_exempt_classes"] or 0
                bldg_nonexempt_classes += ne
                bldg_compliant_classes += (ne - ov)
                bldg_over_cap_classes += ov
                bldg_exempt_classes += ex
                if cs.get("cap_exemption") and "Space" in cs["cap_exemption"]:
                    bldg_space_exempt = True

            org_rec = {
                "org_id": oid,
                "dbn": dbn,
                "name": oname,
                "incl": incl,
                "enroll": oe,
                "cap": oc,
                "util": ou,
                "is_school": is_school_org,
                "is_charter": is_charter,
                "d75": is_d75,
                "d79": is_d79,
                "bands": sorted(bands_of(grades)),
                "avg_class_size": cs.get("avg_class_size_overall") if cs else None,
                "cap_pct": round(100 * cs["cap_pct_at_or_below"], 1) if cs and cs.get("cap_pct_at_or_below") is not None else None,
                "cap_exempt_n": cs.get("cap_n_exempt_classes") if cs else None,
                "cap_exemption": cs.get("cap_exemption") if cs else None,
            }
            orgs.append(org_rec)
            if (
                is_school_org
                and incl == ""
                and oc
                and oc >= 50
                and oe
                and oe >= 50
                and ou is not None
                and not is_d75
                and not is_d79
            ):
                school_orgs_with_cap.append(org_rec)

        bands = set()
        for o in orgs:
            if o["is_school"] and not o["d75"] and not o["d79"] and (o["enroll"] or 0) >= max(1, 0.10 * (be or 0)):
                bands |= set(o["bands"])
        level = "+".join(x for x in ("ES", "MS", "HS") if x in bands) or "unknown"
        crowded_side = [o for o in school_orgs_with_cap if o["util"] > 100]
        under_side = [o for o in school_orgs_with_cap if o["util"] < 60]
        if crowded_side and under_side:
            cc, uc = any(o["is_charter"] for o in crowded_side), any(o["is_charter"] for o in under_side)
            cd, ud = any(not o["is_charter"] for o in crowded_side), any(not o["is_charter"] for o in under_side)
            if cc and not cd and ud and not uc:
                split_kind = "charter_crowded"
            elif cd and not cc and ud and not uc:
                split_kind = "district_only"
            else:
                split_kind = "mixed"
        else:
            split_kind = None
        max_org_u = max((o["util"] for o in school_orgs_with_cap), default=None)
        min_org_u = min((o["util"] for o in school_orgs_with_cap), default=None)
        org_spread = (max_org_u - min_org_u) if (len(school_orgs_with_cap) >= 2 and max_org_u is not None and min_org_u is not None) else 0
        split_100_60 = len(school_orgs_with_cap) >= 2 and max_org_u > 100 and min_org_u < 60
        split_100_75 = len(school_orgs_with_cap) >= 2 and max_org_u > 100 and min_org_u < 75

        b_rec = {
            "id": bid,
            "name": r0["Bldg Name"],
            "boro": boro,
            "district": dist,
            "enroll": be or 0,
            "cap": bc,
            "util": bu if bu is not None else round(100 * (be or 0) / bc),
            "empty_seats": bc - (be or 0),
            "lat": coord["lat"] if coord else None,
            "lon": coord["lon"] if coord else None,
            "address": coord["address"] if coord else "",
            "zip": coord["zip"] if coord else "",
            "nta": coord["nta"] if coord else "",
            "n_orgs": len(school_orgs_with_cap),
            "has_charter": has_charter,
            "has_d75": has_d75,
            "max_org_util": max_org_u,
            "min_org_util": min_org_u,
            "org_spread": org_spread,
            "split_100_60": split_100_60,
            "split_100_75": split_100_75,
            "split_kind": split_kind if split_100_60 else None,
            "level": level,
            "geo_method": coord["method"] if coord else None,
            "cap_nonexempt_classes": bldg_nonexempt_classes if bldg_nonexempt_classes > 0 else None,
            "cap_compliant_pct": round(100 * bldg_compliant_classes / bldg_nonexempt_classes, 1) if bldg_nonexempt_classes > 0 else None,
            "cap_over_classes": bldg_over_cap_classes if bldg_nonexempt_classes > 0 else None,
            "cap_exempt_classes": bldg_exempt_classes if (bldg_nonexempt_classes > 0 or bldg_exempt_classes > 0) else None,
            "space_exempt": bldg_space_exempt,
            "orgs": orgs,
        }
        buildings.append(b_rec)
        if split_100_60:
            colocated_splits.append(b_rec)

    # 3. For every overcrowded (>100%) building, the nearest active (<60%, enrollment > 0) building,
    # three ways: any level; serving at least one of the same grade bands (ES = PK-5, MS = 6-8,
    # HS = 9-12); and serving exactly the same bands. Pairs that share a school organization (a
    # school's own annex) or sit on the same campus point (< 0.01 mile) are skipped.
    placed = lambda b: b["lat"] is not None and b["geo_method"] != "school_main_site"
    over100 = [b for b in buildings if b["util"] > 100 and placed(b)]
    under60_active = [b for b in buildings if b["util"] < 60 and b["enroll"] > 0 and placed(b)]

    def orgset(b):
        return {o["org_id"] for o in b["orgs"] if o["is_school"]}

    def bandset(b):
        return set(b["level"].split("+")) if b["level"] != "unknown" else set()

    pairs = []
    for o in over100:
        best = {"any": (999.0, None), "band": (999.0, None), "same": (999.0, None), "same_dist": (999.0, None)}
        for u in under60_active:
            if orgset(o) & orgset(u):
                continue
            d = haversine_miles(o["lat"], o["lon"], u["lat"], u["lon"])
            if d < 0.01:
                continue
            if d < best["any"][0]:
                best["any"] = (d, u)
            if bandset(o) & bandset(u) and d < best["band"][0]:
                best["band"] = (d, u)
            if o["level"] != "unknown" and o["level"] == u["level"] and d < best["same"][0]:
                best["same"] = (d, u)
            if u["district"] == o["district"] and d < best["same_dist"][0]:
                best["same_dist"] = (d, u)
        for key in ("any", "band", "same"):
            d, u = best[key]
            if u is None:
                continue
            o[f"near_{key}"] = {"id": u["id"], "name": u["name"], "util": u["util"], "empty": u["empty_seats"],
                                "level": u["level"], "miles": round(d, 3)}
        d, u = best["band"] if best["band"][1] else best["any"]
        u_any = best["any"][1]
        pairs.append({
            "crowded_id": o["id"], "crowded_name": o["name"], "crowded_boro": o["boro"], "crowded_district": o["district"],
            "crowded_level": o["level"], "crowded_enroll": o["enroll"], "crowded_cap": o["cap"], "crowded_util": o["util"],
            "crowded_lat": o["lat"], "crowded_lon": o["lon"],
            "any_id": u_any["id"], "any_miles": round(best["any"][0], 3), "any_level": u_any["level"],
            "under_id": u["id"] if u else None, "under_name": u["name"] if u else None,
            "under_district": u["district"] if u else None, "under_level": u["level"] if u else None,
            "under_enroll": u["enroll"] if u else None, "under_cap": u["cap"] if u else None,
            "under_util": u["util"] if u else None, "under_empty_seats": u["empty_seats"] if u else None,
            "under_lat": u["lat"] if u else None, "under_lon": u["lon"] if u else None,
            "miles": round(d, 3) if u else None,
            "grade_match": "same" if (best["same"][1] is not None and best["same"][1] is u) else ("overlap" if best["band"][1] else "none"),
            "same_level_miles": round(best["same"][0], 3) if best["same"][1] else None,
            "same_district": bool(u and u["district"] == o["district"]),
            "same_dist_miles": round(best["same_dist"][0], 3) if best["same_dist"][1] else None,
        })

    pairs.sort(key=lambda x: (x["miles"] if x["miles"] is not None else 99, -x["crowded_util"]))

    # 4. District summary (Districts 1-32)
    by_dist = []
    for dist in range(1, 33):
        db = [b for b in buildings if b["district"] == dist]
        de = sum(b["enroll"] for b in db)
        dc = sum(b["cap"] for b in db)
        u60 = sum(1 for b in db if b["util"] < 60)
        u60_act = sum(1 for b in db if b["util"] < 60 and b["enroll"] > 0)
        o100 = sum(1 for b in db if b["util"] > 100)
        ne_cls = sum(b["cap_nonexempt_classes"] or 0 for b in db)
        ov_cls = sum(b["cap_over_classes"] or 0 for b in db)
        ex_cls = sum(b["cap_exempt_classes"] or 0 for b in db)
        by_dist.append(
            {
                "district": dist,
                "boro": db[0]["boro"] if db else "",
                "buildings": len(db),
                "enrollment": de,
                "capacity": dc,
                "util_pct": round(100 * de / dc, 1) if dc else 0,
                "empty_seats_net": dc - de,
                "under_60": u60,
                "under_60_active": u60_act,
                "over_100": o100,
                "both_extremes": u60 > 0 and o100 > 0,
                "cap_compliant_pct": round(100 * (ne_cls - ov_cls) / ne_cls, 1) if ne_cls else None,
                "cap_exempt_classes": ex_cls,
            }
        )

    # 5. Class size compliance by building utilization band
    bands = [
        ("Under 60% full", lambda u: u < 60),
        ("60% to 79% full", lambda u: 60 <= u < 80),
        ("80% to 99% full", lambda u: 80 <= u < 100),
        ("100% or more", lambda u: u >= 100),
        ("Over 100% full", lambda u: u > 100),
    ]
    class_size_by_band = []
    for label, fn in bands:
        sub = [b for b in buildings if fn(b["util"])]
        sub_cs = [b for b in sub if b["cap_nonexempt_classes"]]
        ne = sum(b["cap_nonexempt_classes"] for b in sub_cs)
        ov = sum(b["cap_over_classes"] for b in sub_cs)
        ex = sum(b["cap_exempt_classes"] or 0 for b in sub)
        sp_ex = sum(1 for b in sub if b["space_exempt"])
        class_size_by_band.append(
            {
                "band": label,
                "buildings": len(sub),
                "buildings_with_class_data": len(sub_cs),
                "enrollment": sum(b["enroll"] for b in sub),
                "capacity": sum(b["cap"] for b in sub),
                "nonexempt_classes": ne,
                "classes_within_cap": ne - ov,
                "classes_over_cap": ov,
                "pct_within_cap": round(100 * (ne - ov) / ne, 1) if ne else None,
                "exempt_classes": ex,
                "buildings_with_space_exemption": sp_ex,
            }
        )

    summary = {
        "fetched": "2026-10-07",
        "data_as_of": "09/09/2026",
        "school_year": "2025-26",
        "register_date": "2025-10-31",
        "total_csv_rows": len(df),
        "rows_2025_26": len(d26),
        "distinct_bldg_ids_2025_26": total_bldg_rows,
        "dropped_zero_capacity_bldg_ids": dropped_zero_cap,
        "buildings_kept": len(buildings),
        "buildings_geocoded": sum(1 for b in buildings if b["lat"] is not None),
        "buildings_active": sum(1 for b in buildings if b["enroll"] > 0),
        "total_enrollment": sum(b["enroll"] for b in buildings),
        "total_capacity": sum(b["cap"] for b in buildings),
        "overall_utilization_pct": round(100 * sum(b["enroll"] for b in buildings) / sum(b["cap"] for b in buildings), 1),
        "net_empty_seats": sum(b["cap"] - b["enroll"] for b in buildings),
        "under_60_all": sum(1 for b in buildings if b["util"] < 60),
        "under_60_active": sum(1 for b in buildings if b["util"] < 60 and b["enroll"] > 0),
        "under_60_active_placed": len(under60_active),
        "over_100_placed": len(over100),
        "under_60_zero_enroll": sum(1 for b in buildings if b["util"] < 60 and b["enroll"] == 0),
        "over_100": sum(1 for b in buildings if b["util"] > 100),
        "at_or_over_100": sum(1 for b in buildings if b["util"] >= 100),
        "over_100_within_half_mile_any_level": sum(1 for p in pairs if p["any_miles"] < 0.5),
        "over_100_within_half_mile_shared_band": sum(1 for p in pairs if p["miles"] is not None and p["miles"] < 0.5),
        "over_100_within_half_mile_same_level": sum(1 for p in pairs if p["same_level_miles"] is not None and p["same_level_miles"] < 0.5),
        "over_100_within_one_mile_any_level": sum(1 for p in pairs if p["any_miles"] < 1.0),
        "over_100_within_one_mile_shared_band": sum(1 for p in pairs if p["miles"] is not None and p["miles"] < 1.0),
        "geocode_methods": dict(Counter(b["geo_method"] for b in buildings)),
        "split_kinds": dict(Counter(b["split_kind"] for b in colocated_splits)),
        "levels": dict(Counter(b["level"] for b in buildings)),
        "colocated_buildings": sum(1 for b in buildings if b["n_orgs"] >= 2),
        "colocated_split_100_60": len(colocated_splits),
        "colocated_split_100_75": sum(1 for b in buildings if b["split_100_75"]),
        "districts_with_both_under60_and_over100": sum(1 for d in by_dist if d["both_extremes"]),
    }

    payload = {
        "summary": summary,
        "history": history,
        "class_size_by_band": class_size_by_band,
        "districts": by_dist,
        "closest_pairs": pairs,
        "colocated_splits": sorted(colocated_splits, key=lambda b: -b["org_spread"]),
        "buildings": buildings,
    }

    with open(os.path.join(OUT_DIR, "utilization.json"), "w") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)

    # Also write flat CSVs for download and transparency
    pd.DataFrame(history).to_csv(os.path.join(OUT_DIR, "history_by_edition.csv"), index=False)
    pd.DataFrame(by_dist).to_csv(os.path.join(OUT_DIR, "districts_2025_26.csv"), index=False)
    pd.DataFrame(pairs).to_csv(os.path.join(OUT_DIR, "overcrowded_nearest_under60_2025_26.csv"), index=False)
    b_flat = [{k: v for k, v in b.items() if k != "orgs"} for b in buildings]
    pd.DataFrame(b_flat).to_csv(os.path.join(OUT_DIR, "buildings_2025_26.csv"), index=False)

    print("Summary:", json.dumps(summary, indent=2))
    print("History:", json.dumps(history, indent=2))
    print("Class size by band:", json.dumps(class_size_by_band, indent=2))
    print("Top 5 closest pairs (>100% to <60% active):")
    for p in pairs[:5]:
        print(" ", p["crowded_id"], p["crowded_name"], f"({p['crowded_util']}%) ->", p["under_id"], p["under_name"], f"({p['under_util']}%)", f"{p['miles']} mi")


if __name__ == "__main__":
    main()
