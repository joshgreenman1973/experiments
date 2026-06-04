#!/usr/bin/env python3
"""
Download the full NYC Storefront Registry (SRVN, dataset 92iy-9c3n) and
pre-process it into a compact JSON file the front-end can load instantly.

The registry's superpower is TIME: the same storefront is re-registered year
after year, so we can track how long a given space has sat dark. The comptroller
report (Live XYZ) has one observed snapshot; this has six years of history per
location. We exploit that to compute "chronic" / persistent vacancy that the
report can only infer.
"""
import json, urllib.request, urllib.parse, sys, time
from collections import defaultdict

BASE = "https://data.cityofnewyork.us/resource/92iy-9c3n.json"
FIELDS = [
    "borough_block_lot", "bbl", "unit", "property_number", "property_street",
    "property_street_address_or", "borough", "zip_code", "postcode",
    "latitude", "longitude", "reporting_year",
    "vacant_on_12_31", "vacant_6_30_or_date_sold", "construction_reported",
    "primary_business_activity", "council_district", "community_board",
    "nta", "nbhd", "census_tract", "expir_dt_of_most_recent_lease",
]

# Map "2019 and 2020" style reporting_year strings to a single integer year.
def year_int(ry):
    if not ry:
        return 0
    ry = ry.strip()
    # take the LAST 4-digit year mentioned (the period's end)
    digits = [int(t) for t in ry.replace("and", " ").split() if t.isdigit() and len(t) == 4]
    return max(digits) if digits else 0

def fetch_all():
    out, offset, page = [], 0, 50000
    while True:
        params = {
            "$select": ",".join(FIELDS),
            "$limit": page,
            "$offset": offset,
            "$order": ":id",
        }
        url = BASE + "?" + urllib.parse.urlencode(params)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    chunk = json.loads(r.read().decode())
                break
            except Exception as e:
                print(f"  retry {attempt} after error: {e}", file=sys.stderr)
                time.sleep(3)
        else:
            raise RuntimeError("failed after retries")
        if not chunk:
            break
        out.extend(chunk)
        print(f"  fetched {len(out)} rows...", file=sys.stderr)
        if len(chunk) < page:
            break
        offset += page
    return out

def is_vacant(rec):
    v1 = (rec.get("vacant_on_12_31") or "").strip().upper()
    v2 = (rec.get("vacant_6_30_or_date_sold") or "").strip().upper()
    return v1 == "YES" or v2 == "YES"

def storefront_key(rec):
    bbl = rec.get("bbl") or rec.get("borough_block_lot") or ""
    unit = (rec.get("unit") or "").strip().upper()
    num = (rec.get("property_number") or "").strip().upper()
    return f"{bbl}|{num}|{unit}"

def main():
    rows = fetch_all()
    print(f"total rows: {len(rows)}", file=sys.stderr)

    # Group registrations by storefront identity, keep one record per year
    stores = {}
    for rec in rows:
        key = storefront_key(rec)
        y = year_int(rec.get("reporting_year"))
        if y == 0:
            continue
        s = stores.get(key)
        if s is None:
            s = stores[key] = {"key": key, "years": {}, "rec": rec}
        # vacancy status for this year (YES wins if any filing says vacant)
        prev = s["years"].get(y)
        vac = is_vacant(rec)
        s["years"][y] = (prev or vac) if prev is not None else vac
        # keep the most recent record for display attributes
        if y >= year_int(s["rec"].get("reporting_year")):
            s["rec"] = rec

    all_years = sorted({y for s in stores.values() for y in s["years"]})
    latest_year = max(all_years)

    out_points = []
    for s in stores.values():
        rec = s["rec"]
        lat = rec.get("latitude"); lon = rec.get("longitude")
        if not lat or not lon:
            continue
        try:
            lat = round(float(lat), 6); lon = round(float(lon), 6)
        except ValueError:
            continue
        years_sorted = sorted(s["years"])
        vac_years = [y for y in years_sorted if s["years"][y]]
        # consecutive-vacant streak ending at the most recent year this store was seen
        last_seen = years_sorted[-1]
        streak = 0
        y = last_seen
        # count consecutive observed years (must be vacant and present) walking back
        present = set(years_sorted)
        while y in present and s["years"].get(y):
            streak += 1
            y -= 1
        latest_status = s["years"][last_seen]
        out_points.append({
            "k": s["key"],
            "lat": lat, "lng": lon,
            "a": rec.get("property_street_address_or") or "",
            "b": (rec.get("borough") or "").upper(),
            "z": rec.get("zip_code") or rec.get("postcode") or "",
            "cd": rec.get("community_board") or "",
            "cc": rec.get("council_district") or "",
            "nb": rec.get("nbhd") or "",
            "nta": rec.get("nta") or "",
            "act": rec.get("primary_business_activity") or "",
            "lease": (rec.get("expir_dt_of_most_recent_lease") or "")[:10],
            "constr": (rec.get("construction_reported") or "").strip().upper() == "YES",
            "vy": vac_years,            # list of years this store was reported vacant
            "ly": last_seen,            # last year observed
            "lv": 1 if latest_status else 0,  # vacant at last observation?
            "streak": streak,           # consecutive years vacant ending at last_seen
            "nvac": len(vac_years),     # total years ever vacant
        })

    meta = {
        "years": all_years,
        "latest_year": latest_year,
        "n_storefronts": len(out_points),
        "generated_from_rows": len(rows),
    }
    with open("data/storefronts.json", "w") as f:
        json.dump({"meta": meta, "points": out_points}, f, separators=(",", ":"))
    print(f"wrote data/storefronts.json: {len(out_points)} storefronts", file=sys.stderr)
    print(json.dumps(meta, indent=2), file=sys.stderr)

if __name__ == "__main__":
    main()
