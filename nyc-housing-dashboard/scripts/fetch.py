#!/usr/bin/env python3
"""
Who builds New York - fetch every input.

  1. DCP Housing Database, project level (br6q-ssj3): every DOB job since 2010
     that adds or removes homes, with net change in permanent (Class A) units
  2. DCP Housing Database summaries by 2024 Council district (szq8-b4uy) and
     community district (dbdt-5s7j): DCP's own yearly net completions
  3. HPD Affordable Housing Production by Building (hg8x-zxpr)
  4. District boundaries (DCP, clipped to shoreline)
  5. 2020 census blocks with population (TIGERweb), to split tracts by district
  6. ACS 2020-2024 five-year tract tables (needs CENSUS_API_KEY)
  7. Current Council members (NYC Council Legistar, via the open API)

Fails loudly. A short fetch would understate what got built.
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
os.makedirs(RAW, exist_ok=True)

SOC = "https://data.cityofnewyork.us/resource"
ARC = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services"
TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/12"
UA = {"User-Agent": "who-builds-new-york/1.0 (housing policy research)"}
COUNTIES = ["005", "047", "061", "081", "085"]


def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(4 * (i + 1))  # Socrata throttles with 403s; retry those too
    raise SystemExit(f"FATAL: {url} failed after {tries} tries: {last}")


def save(name, obj):
    with open(os.path.join(RAW, name), "w") as f:
        json.dump(obj, f)
    print(f"  wrote {name}")


def socrata_all(dataset, select, where=None, page=50000, expect_min=1):
    out, offset = [], 0
    while True:
        q = {"$select": select, "$limit": page, "$offset": offset, "$order": ":id"}
        if where:
            q["$where"] = where
        chunk = get(f"{SOC}/{dataset}.json?" + urllib.parse.urlencode(q))
        out.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    if len(out) < expect_min:
        raise SystemExit(f"FATAL: {dataset} returned {len(out)} rows, expected {expect_min}+")
    return out


def arcgis_geojson(url, where="1=1", fields="*", expect_min=1, page=2000, geometry=True):
    out, offset = [], 0
    while True:
        p = {"where": where, "outFields": fields, "outSR": "4326", "f": "geojson" if geometry else "json",
             "returnGeometry": "true" if geometry else "false",
             "resultOffset": offset, "resultRecordCount": page}
        d = get(url + "/query?" + urllib.parse.urlencode(p))
        chunk = d.get("features", [])
        out.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    if len(out) < expect_min:
        raise SystemExit(f"FATAL: {url} returned {len(out)} features, expected {expect_min}+")
    return out


def main():
    print("Housing Database, project level")
    hdb_fields = ("job_number,job_type,job_status,compltyear,permityear,datepermit,datecomplt,"
                  "classainit,classaprop,classanet,units_co,boro,bbl,addressnum,addressst,"
                  "ntaname20,bct2020,commntydst,councildst,latitude,longitude,hpdaffrdbl,ownership,version")
    save("hdb_projects.json", socrata_all("br6q-ssj3", hdb_fields, "residflag='Residential'", expect_min=100000))

    print("Housing Database summaries")
    comp = ",".join(f"comp{y}" for y in range(2010, 2027))
    save("hdb_council.json", socrata_all("szq8-b4uy", f"councildst,cenunits20,comp2010ap,{comp},filed,approved,permitted", expect_min=51))
    save("hdb_cd.json", socrata_all("dbdt-5s7j", f"commntydst,cenunits20,comp2010ap,{comp},filed,approved,permitted", expect_min=59))

    print("HPD Affordable Housing Production by Building")
    save("hpd_buildings.json", socrata_all("hg8x-zxpr", "*", expect_min=9000))

    print("Boundaries")
    save("council.geojson", {"type": "FeatureCollection", "features": arcgis_geojson(
        f"{ARC}/NYC_City_Council_Districts/FeatureServer/0", fields="CounDist", expect_min=51)})
    save("cd.geojson", {"type": "FeatureCollection", "features": arcgis_geojson(
        f"{ARC}/NYC_Community_Districts/FeatureServer/0", fields="BoroCD", expect_min=59)})

    print("2020 census blocks")
    blocks = []
    for c in COUNTIES:
        f = arcgis_geojson(TIGER, where=f"STATE='36' AND COUNTY='{c}'",
                           fields="GEOID,POP100,HU100,INTPTLAT,INTPTLON", geometry=False, expect_min=500)
        blocks += [x["attributes"] for x in f]
    if sum(b["POP100"] for b in blocks) < 8_000_000:
        raise SystemExit("FATAL: block population sums under 8 million; NYC 2020 was 8.80 million")
    save("blocks2020.json", blocks)

    print("ACS 2020-2024 tract tables")
    key = os.environ.get("CENSUS_API_KEY") or subprocess.run(
        ["security", "find-generic-password", "-s", "CENSUS_API_KEY", "-w"],
        capture_output=True, text=True).stdout.strip()
    if not key:
        raise SystemExit("FATAL: no CENSUS_API_KEY in env or Keychain")
    groups = ["B01003", "B11001", "B19001", "B19013", "B25003", "B25063", "B25061", "B25070", "B25004"]
    acs = {}
    for g in groups:
        rows = []
        for c in COUNTIES:
            url = (f"https://api.census.gov/data/2024/acs/acs5?get=group({g})"
                   f"&for=tract:*&in=state:36%20county:{c}&key={key}")
            d = get(url)
            rows += [dict(zip(d[0], r)) for r in d[1:]]
        if len(rows) < 2000:
            raise SystemExit(f"FATAL: ACS {g} returned {len(rows)} tracts")
        acs[g] = rows
        print(f"  {g}: {len(rows)} tracts")
    save("acs2024_tracts.json", acs)


if __name__ == "__main__":
    main()
