#!/usr/bin/env python3
"""BLS ECEC: private vs state/local gov. Historical total comp/wages/benefits + latest breakdown."""
import json, urllib.request
from pathlib import Path

ITEMS = {
    "010": "total_comp", "020": "wages", "030": "benefits",
    "040": "paid_leave", "050": "supp_pay", "130": "insurance",
    "150": "health_insurance", "180": "retirement", "080": "legally_required",
}
OWN = {"2": "Private", "3": "StateLocal"}

def api(sids, start, end):
    body = json.dumps({"seriesid": sids, "startyear": str(start), "endyear": str(end)}).encode()
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=body, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def pick_annual(data_list, yr):
    rows = [d for d in data_list if int(d["year"]) == yr]
    if not rows:
        return None
    for p in ("Q01", "Q04", "Q02", "Q03"):
        for r in rows:
            if r["period"] == p:
                try: return float(r["value"])
                except: pass
    return None

def main():
    sids = [f"CMU{o}{it}000000000D" for o in OWN for it in ITEMS]
    annual = {}
    for (start, end) in [(2006, 2015), (2016, 2025)]:
        resp = api(sids, start, end)
        for s in resp["Results"]["series"]:
            sid = s["seriesID"]
            own = OWN[sid[3]]
            item = ITEMS[sid[4:7]]
            for yr in range(start, end + 1):
                v = pick_annual(s["data"], yr)
                if v is None: continue
                annual.setdefault(yr, {}).setdefault(own, {})[item] = v
    Path(__file__).parent.joinpath("ecec_annual.json").write_text(json.dumps(annual, indent=2, sort_keys=True))
    print(f"wrote ecec_annual.json, years: {sorted(annual.keys())}")
    # latest Q4 2025
    resp = api(sids, 2025, 2025)
    latest = {}
    for s in resp["Results"]["series"]:
        sid = s["seriesID"]
        own = OWN[sid[3]]; item = ITEMS[sid[4:7]]
        q4 = next((d for d in s["data"] if d["period"] == "Q04"), None)
        if q4: latest.setdefault(own, {})[item] = float(q4["value"])
    Path(__file__).parent.joinpath("ecec_latest.json").write_text(json.dumps(latest, indent=2))
    print("wrote ecec_latest.json")

if __name__ == "__main__":
    main()
