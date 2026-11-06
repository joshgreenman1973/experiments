#!/usr/bin/env python3
"""Rent burden and median contract rent for New York City renters from the Census
Bureau's American Community Survey 1-year estimates. Needs CENSUS_API_KEY in the
environment (on Josh's Mac it is read from the Keychain; the key is never written to
any file). Writes data/acs.json, which both pages read (the price page's median
contract rent via build.py). Run once a year after the fall ACS 1-year release; the
2025 release came out Oct. 29, 2026. 2020 is skipped: Census did not publish standard
1-year data. A year that is not out yet returns 404 and ends the run; any other
failure stops the script without writing."""
import json, os, pathlib, subprocess, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/acs.json"
VARS = {
    "B25071_001E": "median_ratio", "B25071_001M": "median_ratio_moe",
    "B25070_001E": "renters", "B25070_007E": "r30_35", "B25070_008E": "r35_40",
    "B25070_009E": "r40_50", "B25070_010E": "r50_plus", "B25070_011E": "not_computed",
    "B25064_001E": "median_gross_rent", "B25119_003E": "renter_median_income",
    "B25058_001E": "median_contract_rent", "B25058_001M": "median_contract_rent_moe",
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
    for attempt in range(4):  # the API throws occasional 503s; retry before giving up
        try:
            rows = json.load(urllib.request.urlopen(url, timeout=60))
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:  # year not released yet
                return None
            err = f"HTTP {e.code}"  # no URL in the message: it holds the key
        except Exception as e:
            err = e.__class__.__name__
        time.sleep(5 * (attempt + 1))
    else:
        sys.exit(f"ACS {y} fetch failed: {err}")
    v = dict(zip(rows[0], rows[1]))
    r = {VARS[c]: float(v[c]) for c in VARS}
    base = r["renters"] - r["not_computed"]  # households for which a ratio exists
    r["computable"] = base  # B25070_001 minus B25070_011 (no cash rent, or no or negative income)
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
    last = max(out)
    OUT.write_text(json.dumps({
        "source": "Census Bureau, American Community Survey 1-year estimates, New York city: B25071 (median gross rent as a percentage of household income), B25070 (gross rent as a percentage of household income), B25064 (median gross rent), B25058 (median contract rent), B25119",
        "url": f"https://data.census.gov/table/ACSDT1Y{last}.B25070?g=160XX00US3651000",
        "release_url": "https://www.census.gov/newsroom/tip-sheets/2026/tp26-22.html",
        "years": out}, indent=1))


if __name__ == "__main__":
    main()
