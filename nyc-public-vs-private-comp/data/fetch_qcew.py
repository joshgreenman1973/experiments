#!/usr/bin/env python3
"""
Fetch BLS QCEW annual by-area zip for each year; extract NYC's 5 counties,
aggregate to NYC totals for Private + each level of gov, at NAICS '10'.
"""
import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

NYC_COUNTIES = {"36005", "36047", "36061", "36081", "36085"}
OWN_NAMES = {"1": "Federal", "2": "State", "3": "Local", "5": "Private"}
YEARS = list(range(2000, 2025))

def fetch_zip(year):
    url = f"https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_by_area.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def parse_year(year, zbytes):
    # one CSV per area, inside the zip. find NYC county CSVs.
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    agg = {o: {"emp": 0, "total_wages": 0, "wkly_num": 0, "wkly_den": 0} for o in OWN_NAMES}
    for name in z.namelist():
        # Look for our county FIPS codes in filename
        hit = next((c for c in NYC_COUNTIES if c in name), None)
        if not hit:
            continue
        with z.open(name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                if row.get("industry_code") != "10":
                    continue
                own = row.get("own_code")
                if own not in OWN_NAMES:
                    continue
                try:
                    emp = int(row.get("annual_avg_emplvl") or 0)
                    wages = int(row.get("total_annual_wages") or 0)
                    wkly = int(row.get("annual_avg_wkly_wage") or 0)
                except ValueError:
                    continue
                agg[own]["emp"] += emp
                agg[own]["total_wages"] += wages
                agg[own]["wkly_num"] += wkly * emp
                agg[own]["wkly_den"] += emp
    out = {}
    for o, name in OWN_NAMES.items():
        a = agg[o]
        if a["emp"] == 0:
            continue
        out[name] = {
            "employment": a["emp"],
            "total_wages": a["total_wages"],
            "avg_weekly_wage": round(a["wkly_num"] / a["wkly_den"], 2) if a["wkly_den"] else 0,
            "avg_annual_wage": round(a["total_wages"] / a["emp"], 2),
        }
    return out

def main():
    results = {}
    for year in YEARS:
        try:
            zbytes = fetch_zip(year)
            results[str(year)] = parse_year(year, zbytes)
            print(f"{year}: {list(results[str(year)].keys())}")
        except Exception as e:
            print(f"FAIL {year}: {e}")
    out = Path(__file__).parent / "qcew_nyc.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
