"""Request NYC census-tract population totals 1910-1960 plus tract boundary
shapefiles from IPUMS NHGIS, wait for the extract, download it to data/nhgis/.

Key: NHGIS_API_KEY env var or ~/.nhgis_api_key (same as nyc-child-density).
Tables (all are counts of persons by tract):
  1910_tPop_NYC  NT5    Sex by Race/Nativity   -> sum all cells = total persons
  1920_tPop_NYC  NT1    Population, 1910 and 1920 (1920 column used)
  1930_tPop_NYC  NT3    Sex by Race            -> sum = total persons
  1940_tPH_NYC   NT1    Total Population       (geog level 'tractnyc')
  1950_tPH_Major NT1    Total Population
  1960_tPH       NTSUP2 Total Persons
"""
import os, sys, time, json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "nhgis"
OUT.mkdir(parents=True, exist_ok=True)
API = "https://api.ipums.org/extracts"
P = {"collection": "nhgis", "version": "2"}

def key():
    k = os.environ.get("NHGIS_API_KEY")
    return k.strip() if k else (Path.home() / ".nhgis_api_key").read_text().strip()

H = {"Authorization": key(), "Content-Type": "application/json"}

body = {
    "datasets": {
        "1910_tPop_NYC": {"dataTables": ["NT5"], "geogLevels": ["tract"]},
        "1920_tPop_NYC": {"dataTables": ["NT1"], "geogLevels": ["tract"]},
        "1930_tPop_NYC": {"dataTables": ["NT3"], "geogLevels": ["tract"]},
        "1940_tPH_NYC": {"dataTables": ["NT1"], "geogLevels": ["tractnyc"]},
        "1950_tPH_Major": {"dataTables": ["NT1"], "geogLevels": ["tract"]},
        "1960_tPH": {"dataTables": ["NTSUP2"], "geogLevels": ["tract"]},
    },
    "shapefiles": [f"us_tract_{y}_tl2008" for y in (1910, 1920, 1930, 1940, 1950, 1960)],
    "dataFormat": "csv_header",
    "breakdownAndDataTypeLayout": "single_file",
    "description": "NYC tract population 1910-1960 (where-new-york-lives)",
}

def main():
    num = sys.argv[1] if len(sys.argv) > 1 else None
    if not num:
        r = requests.post(API, params=P, headers=H, json=body, timeout=60)
        if r.status_code >= 400:
            print(r.status_code, r.text[:2000]); sys.exit(1)
        num = r.json()["number"]
        print("submitted extract", num)
    while True:
        r = requests.get(f"{API}/{num}", params=P, headers=H, timeout=60)
        r.raise_for_status(); j = r.json()
        print("status:", j["status"], flush=True)
        if j["status"] == "completed": break
        if j["status"] == "failed": print(json.dumps(j)[:2000]); sys.exit(1)
        time.sleep(20)
    for kind, link in j["downloadLinks"].items():
        if not isinstance(link, dict) or "url" not in link: continue
        fn = OUT / link["url"].split("/")[-1]
        with requests.get(link["url"], headers=H, stream=True, timeout=600) as d:
            d.raise_for_status()
            with open(fn, "wb") as f:
                for chunk in d.iter_content(1 << 20): f.write(chunk)
        print("downloaded", kind, fn.name, fn.stat().st_size)

if __name__ == "__main__":
    main()
