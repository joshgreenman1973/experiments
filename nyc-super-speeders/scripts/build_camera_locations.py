#!/usr/bin/env python3
"""
Build nyc-super-speeders/intersections.json — geocoded speed-camera locations.

Strategy:
 1. Query pvqr-7yc4 for the top-N (street_name, intersecting_street, violation_county)
    triples by count where violation_code = 36 (school-zone speed camera).
 2. Normalize the weirdly-truncated columns (street_name is clipped at 20 chars and
    the remainder spills into intersecting_street).
 3. Geocode each normalized "A AND B, BORO" label via NYC Planning Labs Geosearch.
 4. Emit lat/lon plus the raw (street_name, intersecting_street) so the frontend
    can join live counts client-side.
"""

import json
import time
import urllib.parse
import urllib.request
import sys
from pathlib import Path

TOP_N = 500
PER_FY_N = 400
# Fiscal-year datasets (same list as the frontend FY_DATASETS). The union of
# each FY's top PER_FY_N intersections gives us a geo cache that covers both
# the FY2026 and the all-years map view.
FY_DATASETS = {
    2026: "pvqr-7yc4", 2025: "m5vz-tzqv", 2024: "8zf9-spf8",
    2023: "869v-vr48", 2022: "7mxj-7a6y", 2021: "kvfd-bves",
    2020: "p7t3-5i9s", 2019: "faiq-9dfq", 2018: "a5td-mswe",
    2017: "2bnn-yakx", 2016: "kiv2-tbus", 2015: "c284-tqph",
    2014: "jt7v-77mi",
}
SODA = "https://data.cityofnewyork.us/resource/pvqr-7yc4.json"
GEOSEARCH = "https://geosearch.planninglabs.nyc/v2/search"
CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/address"
OUT = Path(__file__).resolve().parent.parent / "intersections.json"

BORO = {
    "QN": "Queens", "BK": "Brooklyn", "MN": "Manhattan",
    "BX": "Bronx",  "ST": "Staten Island",
}

def fetch_top_for(fy, dsid):
    params = {
        "$select": "street_name,intersecting_street,violation_county,count(*) as c",
        "$where": "violation_code=36",
        "$group": "street_name,intersecting_street,violation_county",
        "$order": "c DESC",
        "$limit": str(PER_FY_N),
    }
    url = f"https://data.cityofnewyork.us/resource/{dsid}.json?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  FY{fy} ({dsid}) failed: {e}", file=sys.stderr)
        return []

def fetch_top():
    """Union of top-PER_FY_N intersections across every fiscal-year dataset,
    summed to a grand total per (street, cross, county). Top TOP_N returned."""
    agg = {}
    fy26_totals = {}
    for fy, dsid in FY_DATASETS.items():
        rows = fetch_top_for(fy, dsid)
        print(f"  FY{fy}: {len(rows)} rows", file=sys.stderr)
        for row in rows:
            k = (row.get("street_name",""), row.get("intersecting_street",""), row.get("violation_county",""))
            c = int(row.get("c", 0))
            agg[k] = agg.get(k, 0) + c
            if fy == 2026:
                fy26_totals[k] = c
    merged = []
    for (sn, xs, vc), total in agg.items():
        merged.append({
            "street_name": sn, "intersecting_street": xs, "violation_county": vc,
            "c": total, "fy26": fy26_totals.get((sn, xs, vc), 0),
        })
    merged.sort(key=lambda r: r["c"], reverse=True)
    return merged[:TOP_N]

def normalize(street_name, intersecting_street):
    """
    Combine the two truncated fields and split on '@' to recover real street + cross.
    Strip direction prefix (WB/EB/NB/SB) from the primary street.
    """
    combined = (street_name or "") + (intersecting_street or "")
    # Socrata stores both fields uppercased; collapse repeated whitespace
    combined = " ".join(combined.split())
    if "@" not in combined:
        # No cross-street delimiter — treat whole thing as street
        parts = [combined, ""]
    else:
        parts = combined.split("@", 1)
    street = parts[0].strip()
    cross = parts[1].strip()
    # Strip leading direction marker
    for pfx in ("WB ", "EB ", "NB ", "SB "):
        if street.startswith(pfx):
            street = street[3:]
            break
    return street, cross

def _sane(lat, lon):
    return lat and lon and 40.45 <= lat <= 40.95 and -74.30 <= lon <= -73.65

def geocode_census(street, cross, boro_name):
    if not (street and cross):
        return None
    intersection = f"{street} & {cross}"
    params = urllib.parse.urlencode({
        "street": intersection,
        "city": boro_name or "New York",
        "state": "NY",
        "benchmark": "2020",
        "format": "json",
    })
    try:
        with urllib.request.urlopen(f"{CENSUS}?{params}", timeout=15) as r:
            data = json.loads(r.read())
    except Exception:
        return None
    matches = data.get("result", {}).get("addressMatches") or []
    if not matches:
        return None
    c = matches[0].get("coordinates", {})
    lat, lon = c.get("y"), c.get("x")
    if not _sane(lat, lon):
        return None
    return {"lat": lat, "lon": lon, "source": "census"}

def geocode_geosearch(label):
    params = urllib.parse.urlencode({"text": label, "size": 1})
    try:
        with urllib.request.urlopen(f"{GEOSEARCH}?{params}", timeout=15) as r:
            data = json.loads(r.read())
    except Exception:
        return None
    feats = data.get("features") or []
    if not feats:
        return None
    coords = feats[0].get("geometry", {}).get("coordinates")
    if not coords or len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    if not _sane(lat, lon):
        return None
    return {"lat": lat, "lon": lon, "source": "nyc-geosearch"}

def geocode(street, cross, boro_name, label):
    return geocode_census(street, cross, boro_name) or geocode_geosearch(label)

def main():
    rows = fetch_top()
    print(f"Fetched {len(rows)} intersection candidates", file=sys.stderr)
    out = []
    hits = 0
    for i, row in enumerate(rows):
        sn = row.get("street_name", "")
        xs = row.get("intersecting_street", "")
        boro_code = row.get("violation_county", "")
        boro_name = BORO.get(boro_code, "")
        count = int(row.get("c", 0))
        street, cross = normalize(sn, xs)
        if cross:
            label = f"{street} and {cross}"
        else:
            label = street
        if boro_name:
            label = f"{label}, {boro_name}"
        geo = geocode(street, cross, boro_name, label)
        entry = {
            "street_name": sn,
            "intersecting_street": xs,
            "boro": boro_code,
            "tickets_at_build_all_years": count,
            "tickets_at_build_fy26": int(row.get("fy26", 0)),
            "label": label,
            "lat": geo["lat"] if geo else None,
            "lon": geo["lon"] if geo else None,
        }
        out.append(entry)
        if geo:
            hits += 1
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(rows)} processed, {hits} hits", file=sys.stderr)
        time.sleep(0.08)

    OUT.write_text(json.dumps(
        {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "source_dataset": "pvqr-7yc4",
         "geocoder": "NYC Planning Labs Geosearch v2",
         "intersections": out},
        indent=2))
    print(f"Wrote {OUT} — {hits}/{len(out)} geocoded ({100*hits/len(out):.1f}%)", file=sys.stderr)

if __name__ == "__main__":
    main()
