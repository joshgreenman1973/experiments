#!/usr/bin/env python3
"""Flatten EIA-861M monthly utility files (2010-2026) into one table of residential
revenue, sales and customers per utility per month: data/raw/eia861m_res.csv.

Two layouts: 2010-2013 (UTILITY_ID, UTILNAME, STATE_CODE, YEAR, MONTH, RES_REV...)
and 2014 on (Year, Month, Utility Number, Utility Name, State, Ownership, Status,
then RESIDENTIAL revenue / sales / customers). Only the "States" sheet is used.
"""
import pathlib, sys
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data/raw/eia861m"

frames = []
for f in sorted(SRC.iterdir()):
    x = pd.read_excel(f, sheet_name=0, header=None)
    top = [str(v).strip().upper() for v in x.iloc[0]]
    if top[0].startswith("UTILITY") and top[0] != "UTILITY CHARACTERISTICS" and top[0] != "UTILITY CHARATERISTICS":
        # one header row: UTILITY_ID / UTILITYID, UTILNAME, STATE_CODE, YEAR, MONTH, residential revenue...
        r = top.index(next(t for t in top if t.startswith("RES") and "REV" in t))
        d = x.iloc[1:, [0, 1, 2, 3, 4, r, r + 1, r + 2]].copy()
    else:
        hdr = [str(v).strip() for v in x.iloc[2]]
        assert hdr[2] == "Utility Number", f
        r = top.index("RESIDENTIAL")
        d = x.iloc[3:, [2, 3, 4, 0, 1, r, r + 1, r + 2]].copy()
    d.columns = ["uid", "name", "state", "year", "month", "rev_k", "mwh", "cust"]
    d = d[pd.to_numeric(d.year, errors="coerce").notna()]
    for c in ["uid", "year", "month", "rev_k", "mwh", "cust"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    frames.append(d)
    print(f.name, len(d), int(d.year.min()), int(d.year.max()))

all_ = pd.concat(frames)
all_ = all_[all_.uid > 0]
if (all_.uid == 4226).sum() < 190:
    sys.exit("Con Edison (4226) months missing; layout changed?")
all_.to_csv(ROOT / "data/raw/eia861m_res.csv", index=False)
print("rows", len(all_))
