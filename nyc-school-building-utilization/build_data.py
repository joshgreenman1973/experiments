#!/usr/bin/env python3
"""Build data files for nyc-school-building-utilization ("The empty classroom and the crowded one").

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

    # Build Building ID -> coordinate & address lookup
    bldg_coords = {}
    for _, r in lc.iterrows():
        bc = str(r["Building Code"]).strip().upper()
        dbn = str(r["ATS System Code"]).strip().upper()
        if bc and dbn in schools and schools[dbn].get("lat") and schools[dbn].get("lon"):
            bldg_coords.setdefault(
                bc,
                {
                    "lat": round(float(schools[dbn]["lat"]), 5),
                    "lon": round(float(schools[dbn]["lon"]), 5),
                    "address": str(r["Primary Address"]).strip() or schools[dbn].get("address", ""),
                    "zip": str(r["Zip"]).strip() or schools[dbn].get("zip", ""),
                    "nta": str(r["NTA_Name"]).strip() or schools[dbn].get("neighborhood", ""),
                    "method": "lcgms",
                },
            )

    for _, r in loc1920.iterrows():
        bc = str(r.get("building_code", "")).strip().upper()
        lat, lon = r.get("latitude", "").strip(), r.get("longitude", "").strip()
        if bc and bc not in bldg_coords and lat and lon:
            try:
                bldg_coords[bc] = {
                    "lat": round(float(lat), 5),
                    "lon": round(float(lon), 5),
                    "address": r.get("primary_address_line_1", "").strip(),
                    "zip": r.get("zip", "").strip(),
                    "nta": r.get("nta_name", "").strip(),
                    "method": "loc1920",
                }
            except ValueError:
                pass

    d26 = df[df["Data As Of"] == "09/09/2026"].copy()
    for _, r in d26.iterrows():
        bc = r["Bldg ID"].upper()
        oid = r["Org ID"].upper()
        dbn = cw_org_to_dbn.get(oid)
        if bc and bc not in bldg_coords and dbn and dbn in schools and schools[dbn].get("lat"):
            bldg_coords[bc] = {
                "lat": round(float(schools[dbn]["lat"]), 5),
                "lon": round(float(schools[dbn]["lon"]), 5),
                "address": schools[dbn].get("address", ""),
                "zip": schools[dbn].get("zip", ""),
                "nta": schools[dbn].get("neighborhood", ""),
                "method": "org_crosswalk",
            }

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
            if dbn and dbn.startswith("75"):
                has_d75 = True

            # Class size compliance for this org if in District 1-32 Table C
            cs = cs_schools.get(dbn) if dbn and incl == "" else None
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
                and not oname.startswith("ALC ")
                and "PATHWAYS TO GRADUATION" not in oname.upper()
            ):
                school_orgs_with_cap.append(org_rec)

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

    # 3. Compute nearest underutilized (<60%, active enroll > 0) neighbor for every overcrowded (>100%) building
    # Exclude pairs that share any school organization (e.g. a school's main building and its own annex/minischool)
    # or that resolved to identical coordinates (campus buildings sharing a single address point).
    over100 = [b for b in buildings if b["util"] > 100 and b["lat"] is not None]
    under60_active = [b for b in buildings if b["util"] < 60 and b["enroll"] > 0 and b["lat"] is not None]
    under60_all = [b for b in buildings if b["util"] < 60 and b["lat"] is not None]

    pairs = []
    for o in over100:
        o_orgs = {org["org_id"] for org in o["orgs"] if org["is_school"]}
        best = None
        best_d = 999.0
        best_same_dist = None
        best_same_dist_d = 999.0
        for u in under60_active:
            u_orgs = {org["org_id"] for org in u["orgs"] if org["is_school"]}
            if not o_orgs.isdisjoint(u_orgs):
                continue
            d = haversine_miles(o["lat"], o["lon"], u["lat"], u["lon"])
            if d < 0.01:
                continue
            if d < best_d:
                best_d = d
                best = u
            if u["district"] == o["district"] and d < best_same_dist_d:
                best_same_dist_d = d
                best_same_dist = u
        o["nearest_under60_id"] = best["id"]
        o["nearest_under60_name"] = best["name"]
        o["nearest_under60_util"] = best["util"]
        o["nearest_under60_empty_seats"] = best["empty_seats"]
        o["nearest_under60_miles"] = round(best_d, 2)
        o["nearest_under60_same_dist_miles"] = round(best_same_dist_d, 2) if best_same_dist else None
        pairs.append(
            {
                "crowded_id": o["id"],
                "crowded_name": o["name"],
                "crowded_boro": o["boro"],
                "crowded_district": o["district"],
                "crowded_enroll": o["enroll"],
                "crowded_cap": o["cap"],
                "crowded_util": o["util"],
                "crowded_over_seats": o["enroll"] - o["cap"],
                "crowded_lat": o["lat"],
                "crowded_lon": o["lon"],
                "under_id": best["id"],
                "under_name": best["name"],
                "under_district": best["district"],
                "under_enroll": best["enroll"],
                "under_cap": best["cap"],
                "under_util": best["util"],
                "under_empty_seats": best["empty_seats"],
                "under_lat": best["lat"],
                "under_lon": best["lon"],
                "miles": round(best_d, 2),
                "same_district": o["district"] == best["district"],
                "same_dist_miles": round(best_same_dist_d, 2) if best_same_dist else None,
            }
        )

    pairs.sort(key=lambda x: (x["miles"], -x["crowded_util"]))

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
        "under_60_active": len(under60_active),
        "under_60_zero_enroll": sum(1 for b in buildings if b["util"] < 60 and b["enroll"] == 0),
        "over_100": len(over100),
        "at_or_over_100": sum(1 for b in buildings if b["util"] >= 100),
        "over_100_within_half_mile_of_under60_active": sum(1 for p in pairs if p["miles"] <= 0.5),
        "over_100_within_half_mile_same_district": sum(1 for p in pairs if p["same_dist_miles"] is not None and p["same_dist_miles"] <= 0.5),
        "over_100_within_one_mile_of_under60_active": sum(1 for p in pairs if p["miles"] <= 1.0),
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
