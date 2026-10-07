"""List NHGIS decennial datasets 1910-1960 and their tract-level population tables.
Uses the IPUMS API key stored the same way as nyc-child-density (~/.nhgis_api_key)."""
import os, sys, json
from pathlib import Path
import requests

def key():
    k = os.environ.get("NHGIS_API_KEY")
    if k: return k.strip()
    return (Path.home() / ".nhgis_api_key").read_text().strip()

H = {"Authorization": key()}
BASE = "https://api.ipums.org/metadata"
what = sys.argv[1] if len(sys.argv) > 1 else "datasets"
if what == "datasets":
    out = []
    page = 1
    while True:
        r = requests.get(f"{BASE}/datasets", params={"collection": "nhgis", "version": "2", "pageNumber": page, "pageSize": 500}, headers=H, timeout=60)
        r.raise_for_status()
        j = r.json()
        out += j["data"]
        if not j.get("links", {}).get("nextPage"): break
        page += 1
    for d in out:
        if d["name"][:4] in {"1910","1920","1930","1940","1950","1960"}:
            print(d["name"], "|", d.get("description", "")[:90])
elif what == "dataset":
    r = requests.get(f"{BASE}/datasets/{sys.argv[2]}", params={"collection": "nhgis", "version": "2"}, headers=H, timeout=60)
    r.raise_for_status(); j = r.json()
    print("geogs:", [g["name"] for g in j.get("geogLevels", [])])
    for t in j.get("dataTables", []):
        print(t["name"], "|", t.get("description", "")[:80], "|", t.get("universe", "")[:40])
elif what == "shapefiles":
    out = []; page = 1
    while True:
        r = requests.get(f"{BASE}/shapefiles", params={"collection": "nhgis", "version": "2", "pageNumber": page, "pageSize": 2500}, headers=H, timeout=60)
        r.raise_for_status(); j = r.json(); out += j["data"]
        if not j.get("links", {}).get("nextPage"): break
        page += 1
    for s in out:
        if "nyc" in s["name"].lower() or "tract_19" in s["name"]:
            print(s["name"], "|", s.get("year"), "|", s.get("basis"))
