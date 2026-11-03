"""Pull NYPD complaint counts by year, offense, premise and jurisdiction.

Source: NYPD Complaint Data Historic (NYC Open Data, qgea-i56i), dated by
report date (RPT_DT), which matches NYPD's own CompStat year totals.
Writes data/complaints_by_premise.json; build_numbers.py does the math.
"""
import json, time, urllib.parse, urllib.request, pathlib

BASE = "https://data.cityofnewyork.us/resource/qgea-i56i.json"
OFFENSES = [
    "MURDER & NON-NEGL. MANSLAUGHTER", "RAPE", "ROBBERY", "FELONY ASSAULT",
    "BURGLARY", "GRAND LARCENY", "GRAND LARCENY OF MOTOR VEHICLE",
    "ASSAULT 3 & RELATED OFFENSES",
]
YEARS = [2023, 2024, 2025]
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "complaints_by_premise.json"


def get(params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Socrata answers anonymous throttling with 403 as well as 429
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(5 * (attempt + 1)); continue
            raise
    raise RuntimeError("gave up: " + url)


rows = []
for y in YEARS:
    offs = ",".join("'" + o.replace("'", "''") + "'" for o in OFFENSES)
    data = get({
        "$select": "ofns_desc,law_cat_cd,prem_typ_desc,juris_desc,count(*) as n",
        "$where": f"rpt_dt between '{y}-01-01T00:00:00' and '{y}-12-31T23:59:59' and ofns_desc in ({offs})",
        "$group": "ofns_desc,law_cat_cd,prem_typ_desc,juris_desc",
        "$limit": 50000,
    })
    if not data:
        raise SystemExit(f"FAIL: no rows for {y}")
    for r in data:
        rows.append({"year": y, "ofns": r.get("ofns_desc"), "law": r.get("law_cat_cd"),
                     "prem": r.get("prem_typ_desc"), "juris": r.get("juris_desc"),
                     "n": int(r["n"])})
    print(y, sum(r["n"] for r in rows if r["year"] == y))

OUT.write_text(json.dumps({"source": "NYC Open Data qgea-i56i, grouped by RPT_DT year",
                           "pulled": time.strftime("%Y-%m-%d"), "rows": rows}, indent=1))
print("wrote", OUT)
