#!/usr/bin/env python3
"""Extract BLS relative importance (December) for the New York-Newark-Jersey City
CPI-U from the BLS workbooks in data/raw/ri<YEAR>.xlsx -> data/weights.json.
Relative importance at December of year Y is the share of each item in the
index going into year Y+1, which makes Dec-to-month contributions additive."""
import json, pathlib, sys, urllib.request, openpyxl
ROOT = pathlib.Path(__file__).resolve().parent.parent
bls = json.loads((ROOT / "data/raw/bls.json").read_text())["series"]
ref_year = int(max(bls["CUURS12ASA0"]["obs"])[:4])
out = {}
# December weights for the two years the page compares (BLS posts them each February).
for y in (ref_year - 2, ref_year - 1):
    f = ROOT / f"data/raw/ri{y}.xlsx"
    if not f.exists():
        req = urllib.request.Request(f"https://www.bls.gov/cpi/tables/relative-importance/{y}.xlsx",
                                     headers={"User-Agent": "Mozilla/5.0 (research; josh.greenman@gmail.com)"})
        try:
            f.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        except Exception as e:
            sys.exit(f"December {y} relative importance not available yet from BLS ({e}); hold the January rebuild until it is")
    wb = openpyxl.load_workbook(f, read_only=True)
    found = False
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 6:
            continue
        hdr = rows[3]
        for j, h in enumerate(hdr):
            if h and "New York" in str(h) and rows[4][j] == "CPI-U":
                w = {}
                for r in rows[5:]:
                    if r[1] and isinstance(r[j], (int, float)):
                        w.setdefault(str(r[1]).strip(), float(r[j]))
                out[f"{y}-12"] = {"table": ws.title, "weights": w}
                found = True
                break
        if found:
            break
    assert found, f"New York column not found in ri{y}.xlsx"
(ROOT / "data/weights.json").write_text(json.dumps(out, indent=1))
for k, v in out.items():
    print(k, v["table"], {n: v["weights"].get(n) for n in ["Housing", "Rent of primary residence", "Energy", "Gasoline (all types)", "Food at home"]})
