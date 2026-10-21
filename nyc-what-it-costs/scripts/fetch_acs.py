#!/usr/bin/env python3
"""Rent burden for New York City renters from the Census Bureau's American Community
Survey 1-year estimates. Needs CENSUS_API_KEY in the environment (on Josh's Mac it is
read from the Keychain). Writes data/acs.json. Run once a year after the September/
October ACS release. 2020 is skipped: Census did not publish standard 1-year data."""
import json, os, pathlib, subprocess, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/acs.json"
VARS = {
    "B25071_001E": "median_ratio", "B25071_001M": "median_ratio_moe",
    "B25070_001E": "renters", "B25070_007E": "r30_35", "B25070_008E": "r35_40",
    "B25070_009E": "r40_50", "B25070_010E": "r50_plus", "B25070_011E": "not_computed",
    "B25064_001E": "median_gross_rent", "B25119_003E": "renter_median_income",
}


def key():
    k = os.environ.get("CENSUS_API_KEY", "")
    if not k:
        try:
            k = subprocess.run(["security", "find-generic-password", "-s", "CENSUS_API_KEY", "-w"],
                               capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            pass
    if not k:
        sys.exit("CENSUS_API_KEY not set; the ACS update must run where the key is available")
    return k


def year(y, k):
    url = (f"https://api.census.gov/data/{y}/acs/acs1?get={','.join(VARS)}"
           f"&for=place:51000&in=state:36&key={k}")
    try:
        rows = json.load(urllib.request.urlopen(url, timeout=60))
    except Exception as e:
        return None
    v = dict(zip(rows[0], rows[1]))
    r = {VARS[c]: float(v[c]) for c in VARS}
    base = r["renters"] - r["not_computed"]  # households for which a ratio exists
    r["share_30_plus"] = round(100 * (r["r30_35"] + r["r35_40"] + r["r40_50"] + r["r50_plus"]) / base, 2)
    r["share_50_plus"] = round(100 * r["r50_plus"] / base, 2)
    return r


def main():
    k = key()
    out = {}
    for y in range(2010, 2031):
        if y == 2020:
            continue
        r = year(y, k)
        if r is None:
            if y <= 2024:
                sys.exit(f"ACS {y} fetch failed")
            break
        out[str(y)] = r
        print(y, r["median_ratio"], r["share_30_plus"], r["share_50_plus"])
    OUT.write_text(json.dumps({
        "source": "Census Bureau, American Community Survey 1-year estimates, New York city: B25071 (median gross rent as a percentage of household income), B25070 (gross rent as a percentage of household income), B25064, B25119",
        "url": "https://data.census.gov/table/ACSDT1Y2024.B25070?g=160XX00US3651000",
        "years": out}, indent=1))


if __name__ == "__main__":
    main()
