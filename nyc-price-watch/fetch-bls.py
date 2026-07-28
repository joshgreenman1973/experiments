#!/usr/bin/env python3
"""Fetch NY-area CES earnings and CPI-U categories from the BLS API v2.

Writes bls-data.json. Re-run to refresh; the API is the only source used.
"""
import os, json, urllib.request, sys, datetime

KEY = os.environ.get("BLS_API_KEY", "")
AREA = "S12A"            # New York-Newark-Jersey City, NY-NJ-PA (CPI-U area)
START, END = 2024, 2026

# Table 1 expenditure categories, in release order. (item_code, label)
TABLE1 = [
    ("SA0",     "All items"),
    ("SAF",     "Food and beverages"),
    ("SAF1",    "Food"),
    ("SAF11",   "Food at home"),
    ("SAF111",  "Cereals and bakery products"),
    ("SAF112",  "Meats, poultry, fish, and eggs"),
    ("SAF113",  "Dairy and related products"),
    ("SAF114",  "Fruits and vegetables"),
    ("SAF115",  "Nonalcoholic beverages and beverage materials"),
    ("SAF116",  "Other food at home"),
    ("SEFV",    "Food away from home"),
    ("SAF2",    "Alcoholic beverages"),
    ("SAH",     "Housing"),
    ("SAH1",    "Shelter"),
    ("SEHA",    "Rent of primary residence"),
    ("SEHC",    "Owners' equivalent rent of residences"),
    ("SEHC01",  "Owners' equivalent rent of primary residence"),
    ("SAH3",    "Household furnishings and operations"),
    ("SAA",     "Apparel"),
    ("SAT",     "Transportation"),
    ("SAT1",    "Private transportation"),
    ("SETA",    "New and used motor vehicles"),
    ("SETA01",  "New vehicles"),
    ("SETA02",  "Used cars and trucks"),
    ("SETB",    "Motor fuel"),
    ("SETB01",  "Gasoline, all types"),
    ("SS47014", "Gasoline, unleaded regular"),
    ("SS47015", "Gasoline, unleaded midgrade"),
    ("SS47016", "Gasoline, unleaded premium"),
    ("SAM",     "Medical care"),
    ("SAR",     "Recreation"),
    ("SAE",     "Education and communication"),
    ("SEEB",    "Tuition, other school fees, and childcare"),
    ("SAG",     "Other goods and services"),
]
# Special aggregate, NOT part of Table 1. Fetched only to keep the existing
# energy card current; flagged separately so it never mixes with Table 1.
EXTRA = [("SA0E", "Energy (special aggregate, Table 2)")]

CES = [
    ("SMU36356200500000003", "Average hourly earnings, total private"),
    ("SMU36356200500000011", "Average weekly earnings, total private"),
]

def cpi_id(item): return f"CUUR{AREA}{item}"

def post(ids):
    payload = {"seriesid": ids, "startyear": str(START), "endyear": str(END),
               "catalog": True}
    if KEY:
        payload["registrationkey"] = KEY
    req = urllib.request.Request(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        json.dumps(payload).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))

def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def main():
    wanted = [(cpi_id(c), lbl, "cpi", c) for c, lbl in TABLE1] \
           + [(cpi_id(c), lbl, "extra", c) for c, lbl in EXTRA] \
           + [(sid, lbl, "ces", sid) for sid, lbl in CES]
    by_id = {w[0]: w for w in wanted}

    raw = {}
    meta = {}
    for batch in chunks([w[0] for w in wanted], 20):
        d = post(batch)
        if d.get("status") != "REQUEST_SUCCEEDED":
            print("API status:", d.get("status"), d.get("message"), file=sys.stderr)
        for m in (d.get("message") or []):
            if "does not exist" in m.lower():
                print("  !", m, file=sys.stderr)
        for s in d["Results"]["series"]:
            raw[s["seriesID"]] = s.get("data", [])
            meta[s["seriesID"]] = s.get("catalog") or {}

    out = {"_fetched": datetime.date.today().isoformat(),
           "_api": "BLS API v2 (unregistered)" if not KEY else "BLS API v2 (registered)",
           "_area_cpi": AREA, "series": {}, "missing": []}

    for sid, label, kind, code in wanted:
        obs = raw.get(sid, [])
        # Drop annual averages (M13) and any non-monthly period.
        obs = [o for o in obs if o.get("period", "").startswith("M") and o["period"] != "M13"]
        if not obs:
            out["missing"].append({"id": sid, "label": label})
            continue
        pts = {}
        prelim = {}
        for o in obs:
            k = f'{o["year"]}-{o["period"]}'
            try:
                pts[k] = float(o["value"])
            except ValueError:
                continue
            fn = o.get("footnotes") or []
            codes = [f.get("code") for f in fn if f and f.get("code")]
            if codes:
                prelim[k] = codes
        out["series"][sid] = {
            "label": label, "kind": kind, "item_code": code,
            "catalog": {k: meta.get(sid, {}).get(k) for k in
                        ("series_title", "area", "item", "seasonality", "survey_name")},
            "obs": pts, "footnotes": prelim,
        }
    json.dump(out, open("bls-data.json", "w"), indent=1, sort_keys=False)
    print(f"fetched {len(out['series'])} series, {len(out['missing'])} missing -> bls-data.json")
    for m in out["missing"]:
        print("  MISSING:", m["id"], m["label"])

if __name__ == "__main__":
    main()
