#!/usr/bin/env python3
"""Monthly average day-ahead LBMP ($/MWh) for NYISO Zone J (New York City) and,
for comparison, the simple average of the upstate zones A-E and Zone K (Long Island).
Source: NYISO MIS public archive, damlbmp zone CSVs, one zip per month.
Writes data/raw/nyiso_monthly.json.
"""
import io, json, pathlib, sys, zipfile
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data/raw/nyiso"
UP = ["WEST", "GENESE", "CENTRL", "NORTH", "MHK VL"]
out = {}
for z in sorted(SRC.glob("*.zip")):
    parts = []
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            parts.append(pd.read_csv(io.BytesIO(zf.read(n))))
    d = pd.concat(parts)
    col = "LBMP ($/MWHr)"
    by = d.groupby("Name")[col].mean()
    if "N.Y.C." not in by:
        sys.exit(f"Zone J missing in {z.name}")
    key = f"{z.name[:4]}-{z.name[4:6]}"
    out[key] = {"J": round(by["N.Y.C."], 2), "K": round(by.get("LONGIL", float("nan")), 2),
                "upstate": round(by[[u for u in UP if u in by]].mean(), 2),
                "days": int(d["Time Stamp"].str[:10].nunique())}
(ROOT / "data/raw/nyiso_monthly.json").write_text(json.dumps(out, indent=0))
print(len(out), list(out.items())[:2], list(out.items())[-3:])
