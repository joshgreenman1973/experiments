#!/usr/bin/env python3
"""Checks run after every rebuild. Exit non-zero (and publish nothing) on any failure."""
import json, pathlib, sys, datetime, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "data/dashboard.json").read_text())
bad = []

# 1. The contribution identity must hold for both years.
gap = d.get("ly_gap")  # last year's month is one BLS never published
if d["contrib_ly"] is None and not gap:
    bad.append("contrib_ly missing although last year's month is not a known gap")
for k in ("contrib", "contrib_ly"):
    c = d[k]
    if c is None:
        continue
    s = sum(g["contrib"] for g in c["groups"])
    if abs(s - c["total"]) > 0.02:
        bad.append(f"{k}: contributions sum {s:.3f} != total {c['total']}")
    if abs(sum(g["weight"] for g in c["groups"]) - 100) > 0.05:
        bad.append(f"{k}: weights do not sum to 100")

# 2. No missing headline numbers.
for l in d["lines"] + d["aisles"]:
    for f in ("ytd",) if gap else ("ytd", "ytd_ly"):
        if l[f] is None:
            bad.append(f"{l['label']}: {f} missing")

# 3. Freshness: BLS month no more than 3 months behind today.
ref = datetime.date(int(d["ref"][:4]), int(d["ref"][5:]), 1)
if (datetime.date.today() - ref).days > 100:
    bad.append(f"BLS reference month {d['ref']} is stale")
for name, blk in (("gasoline", d["energy"]["gasoline"]), ("coned", d["energy"]["coned"]), ("zori", d["zori"])):
    r = datetime.date(int(blk["ref"][:4]), int(blk["ref"][5:]), 1)
    if (datetime.date.today() - r).days > 160:
        bad.append(f"{name} reference month {blk['ref']} is stale")

# 4. Implausible moves usually mean a parsing error, not a price change.
for l in d["lines"]:
    if l["yoy"] is not None and abs(l["yoy"]) > 80:
        bad.append(f"{l['label']}: 12-month change {l['yoy']}% looks wrong")

# 5. The page's scripts must parse.
for f in ("app.js", "sections.js"):
    r = subprocess.run(["node", "--check", str(ROOT / f)], capture_output=True, text=True)
    if r.returncode:
        bad.append(f"{f} syntax: {r.stderr.strip()[:200]}")

# 6. No NaN/undefined anywhere in the data.
if re.search(r"NaN|undefined|Infinity", (ROOT / "data/dashboard.json").read_text()):
    bad.append("NaN/undefined in dashboard.json")

if bad:
    print("VERIFY FAILED"); [print(" -", b) for b in bad]; sys.exit(1)
ly = d["contrib_ly"]["total"] if d["contrib_ly"] else "n/a (BLS gap)"
print(f"verify ok: BLS {d['ref']}, all items since Dec {d['contrib']['total']}% vs {ly}% same months last year")
