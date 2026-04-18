#!/usr/bin/env python3
"""Fetch NYS statewide QCEW means (FIPS 36000), and NYC-resident medians via ACS."""
import csv, io, json, urllib.request, zipfile
from pathlib import Path

NYS_FIPS = "36000"
OWN_NAMES = {"1": "Federal", "2": "State", "3": "Local", "5": "Private"}
YEARS = list(range(2000, 2025))

def fetch_zip(year):
    url = f"https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_by_area.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def parse_year(zbytes):
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    agg = {o: {"emp": 0, "total_wages": 0, "wkly_num": 0, "wkly_den": 0} for o in OWN_NAMES}
    for name in z.namelist():
        if NYS_FIPS not in name:
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
            "avg_weekly_wage": round(a["wkly_num"]/a["wkly_den"], 2) if a["wkly_den"] else 0,
            "avg_annual_wage": round(a["total_wages"]/a["emp"], 2),
        }
    return out

def main():
    results = {}
    for year in YEARS:
        try:
            results[str(year)] = parse_year(fetch_zip(year))
            print(year, list(results[str(year)].keys()))
        except Exception as e:
            print("FAIL", year, e)
    Path(__file__).parent.joinpath("qcew_nys.json").write_text(json.dumps(results, indent=2))
    print("wrote qcew_nys.json")

if __name__ == "__main__":
    main()
