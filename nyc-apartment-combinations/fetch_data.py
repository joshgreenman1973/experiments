#!/usr/bin/env python3
"""
Fetch NYC DOB apartment-combination filings from NYC Open Data (ic3t-wcy2)
and save as a compact GeoJSON + summary JSON.

Criteria:
  - job_description contains "COMBIN" AND one of: APART / UNIT / DWELLING
  - Has gis_latitude
  - Anywhere in NYC, all dates in dataset (2000-present)
"""

import json
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

BASE = "https://data.cityofnewyork.us/resource/ic3t-wcy2.json"
WHERE = (
    "upper(job_description) like '%COMBIN%' "
    "AND (upper(job_description) like '%APART%' "
    "OR upper(job_description) like '%UNIT%' "
    "OR upper(job_description) like '%DWELLING%') "
    "AND gis_latitude IS NOT NULL"
)
SELECT = ",".join([
    "job__", "job_type", "job_status", "job_status_descrp",
    "job_description", "borough", "house__", "street_name",
    "pre__filing_date", "existing_dwelling_units", "proposed_dwelling_units",
    "initial_cost", "gis_latitude", "gis_longitude",
    "gis_nta_name", "community___board", "owner_s_business_name",
])

PAGE = 5000
OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)


def fetch_page(offset):
    qs = urllib.parse.urlencode({
        "$select": SELECT,
        "$where": WHERE,
        "$order": "pre__filing_date DESC",
        "$limit": PAGE,
        "$offset": offset,
    })
    url = f"{BASE}?{qs}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def parse_year(s):
    if not s:
        return None
    # format: MM/DD/YYYY or ISO
    try:
        if "/" in s:
            parts = s.split("/")
            return int(parts[2][:4])
        return int(s[:4])
    except Exception:
        return None


def parse_cost(s):
    if not s:
        return 0
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return 0


def main():
    all_rows = []
    offset = 0
    while True:
        print(f"Fetching offset {offset}...", file=sys.stderr)
        rows = fetch_page(offset)
        all_rows.extend(rows)
        if len(rows) < PAGE:
            break
        offset += PAGE
    print(f"Total rows: {len(all_rows)}", file=sys.stderr)

    features = []
    annual = Counter()
    annual_by_boro = defaultdict(Counter)
    boro_total = Counter()
    nta = Counter()
    total_cost = 0
    cost_count = 0

    for r in all_rows:
        try:
            lat = float(r.get("gis_latitude", 0))
            lon = float(r.get("gis_longitude", 0))
        except Exception:
            continue
        if not (40.4 < lat < 41.0 and -74.3 < lon < -73.6):
            continue
        year = parse_year(r.get("pre__filing_date"))
        if not year:
            continue
        cost = parse_cost(r.get("initial_cost"))
        if cost > 0:
            total_cost += cost
            cost_count += 1
        boro = (r.get("borough") or "").title()
        addr = f'{(r.get("house__") or "").strip()} {(r.get("street_name") or "").strip()}'.strip()
        desc = (r.get("job_description") or "").strip()
        status = (r.get("job_status_descrp") or r.get("job_status") or "").strip()

        # Trim description for payload
        if len(desc) > 240:
            desc = desc[:237] + "..."

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {
                "j": r.get("job__"),
                "t": r.get("job_type"),
                "s": status,
                "y": year,
                "b": boro,
                "a": addr,
                "n": r.get("gis_nta_name"),
                "d": desc,
                "c": int(cost) if cost > 0 else None,
                "eu": r.get("existing_dwelling_units"),
                "pu": r.get("proposed_dwelling_units"),
            },
        })
        annual[year] += 1
        annual_by_boro[year][boro] += 1
        boro_total[boro] += 1
        if r.get("gis_nta_name"):
            nta[(boro, r["gis_nta_name"])] += 1

    geo = {"type": "FeatureCollection", "features": features}
    with open(OUT_DIR / "combinations.geojson", "w") as f:
        json.dump(geo, f, separators=(",", ":"))

    years_sorted = sorted(annual.keys())
    summary = {
        "total": len(features),
        "year_range": [years_sorted[0], years_sorted[-1]] if years_sorted else [None, None],
        "annual": [{"year": y, "count": annual[y]} for y in years_sorted],
        "annual_by_borough": [
            {
                "year": y,
                "Manhattan": annual_by_boro[y].get("Manhattan", 0),
                "Brooklyn": annual_by_boro[y].get("Brooklyn", 0),
                "Queens": annual_by_boro[y].get("Queens", 0),
                "Bronx": annual_by_boro[y].get("Bronx", 0),
                "Staten Island": annual_by_boro[y].get("Staten Island", 0),
            }
            for y in years_sorted
        ],
        "borough_totals": dict(boro_total),
        "top_ntas": [
            {"borough": b, "nta": n, "count": c}
            for (b, n), c in nta.most_common(25)
        ],
        "mean_cost": int(total_cost / cost_count) if cost_count else None,
        "cost_count": cost_count,
        "fetched_at": None,
    }
    import datetime
    summary["fetched_at"] = datetime.date.today().isoformat()

    with open(OUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved {len(features)} features.", file=sys.stderr)
    print(f"Year range: {summary['year_range']}", file=sys.stderr)
    print(f"Borough totals: {summary['borough_totals']}", file=sys.stderr)


if __name__ == "__main__":
    main()
