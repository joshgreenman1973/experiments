#!/usr/bin/env python3
"""Compute NYC-resident private-sector median annual wages by occupation
from ACS 2023 1-year PUMS microdata. Full-time full-year workers only
(WKHP >= 35, WKWN >= 50) to match NYC annual-salary comparison.
"""
import csv, json, os
from pathlib import Path

HERE = Path(__file__).parent
CSV_PATH = HERE / "psam_p36.csv"

# 2020-vintage NYC PUMA codes (as integers)
NYC_PUMAS = set(range(3701, 3711))   # Bronx
NYC_PUMAS |= set(range(3801, 3811))  # Manhattan
NYC_PUMAS |= set(range(3901, 3904))  # Staten Island
NYC_PUMAS |= set(range(4001, 4019))  # Brooklyn
NYC_PUMAS |= set(range(4101, 4115))  # Queens

# Target SOC codes -> display name. SOCP in PUMS is a 6-char code like "291141"
# (with trailing X for generic codes we ignore). We group any SOCP starting
# with the target prefix into one bucket to catch the sub-codes BLS publishes.
# Use 4-char SOC-prefix matching to catch sub-codes and generic placeholders
# (e.g. "2310" matches 231011 attorneys, 2310XX generics, etc.)
TARGETS = [
    ("29-1141", "2911", "Registered nurse"),        # RN family
    ("25-2021", "2520", "Elementary / middle school teachers"),
    ("13-2011", "1320", "Accountants & auditors"),  # 1320xx accountants group
    ("17-2051", "1720", "Civil / related engineers"),
    ("23-1011", "2310", "Lawyers / judicial workers"),
    ("47-2111", "4721", "Electricians"),
    ("21-1021", "2110", "Social workers / counselors"),
    ("53-3052", "5330", "Bus / transit drivers"),
    ("47-2152", "4721", "Plumbers / pipefitters"),  # overlaps 4721 with electricians; excluded below
    ("43-6014", "4360", "Secretaries & admin assistants"),
]
# SOCP narrow matches when the 4-char prefix is ambiguous:
NARROW = {
    "47-2111": lambda s: s.startswith("47211"),   # electricians
    "47-2152": lambda s: s.startswith("47215"),   # plumbers
    "53-3052": lambda s: s.startswith("533"),      # transit drivers incl. 5330xx
    "43-6014": lambda s: s.startswith("4360"),    # secretaries/admin
}

# class-of-worker codes: 1=private for-profit, 2=private non-profit
PRIVATE_COW = {"1", "2"}

def weighted_median(vals_weights):
    vals_weights.sort(key=lambda x: x[0])
    total = sum(w for _, w in vals_weights)
    if total == 0:
        return None
    half = total / 2
    cum = 0
    for v, w in vals_weights:
        cum += w
        if cum >= half:
            return v
    return vals_weights[-1][0]

def weighted_mean(vals_weights):
    total_w = sum(w for _, w in vals_weights)
    if total_w == 0:
        return None
    return sum(v * w for v, w in vals_weights) / total_w

def main():
    # Collect (wage, weight) tuples bucket by SOC prefix
    buckets = {t[0]: [] for t in TARGETS}
    kept = 0
    scanned = 0
    with open(CSV_PATH, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            scanned += 1
            try:
                puma = int(row["PUMA"])
            except (ValueError, KeyError):
                continue
            if puma not in NYC_PUMAS:
                continue
            if row["COW"] not in PRIVATE_COW:
                continue
            # Employed: ESR 1 (civilian, at work), 2 (with job, not at work), 4/5 (armed forces)
            if row["ESR"] not in {"1", "2", "4", "5"}:
                continue
            # Full-time full-year
            try:
                wkhp = int(row["WKHP"] or 0)
                wkwn = int(row["WKWN"] or 0)
            except ValueError:
                continue
            if wkhp < 35 or wkwn < 50:
                continue
            try:
                wagp = float(row["WAGP"] or 0)
                pw = float(row["PWGTP"] or 0)
            except ValueError:
                continue
            if wagp <= 0 or pw <= 0:
                continue
            soc = row["SOCP"] or ""
            if not soc:
                continue
            # Match against each target. Use NARROW override where provided.
            for soc_code, prefix, _name in TARGETS:
                narrow = NARROW.get(soc_code)
                ok = narrow(soc) if narrow else soc.startswith(prefix)
                if ok:
                    buckets[soc_code].append((wagp, pw))
                    kept += 1
                    break
    print(f"scanned={scanned} kept={kept}")

    out = []
    for soc, prefix, name in TARGETS:
        vw = buckets[soc]
        n_records = len(vw)
        pop = sum(w for _, w in vw)
        med = weighted_median(list(vw)) if vw else None
        mean = weighted_mean(vw) if vw else None
        out.append({
            "soc": soc,
            "prefix": prefix,
            "name": name,
            "n_records": n_records,       # unweighted PUMS records
            "weighted_n": round(pop / 5) if pop else 0,  # 5-year → approx annual count
            "median": round(med) if med else None,
            "mean": round(mean) if mean else None,
        })
        print(f"  {soc} {name}: n={n_records} wN={round(pop/5) if pop else 0} med={med and round(med)} mean={mean and round(mean)}")

    (HERE / "pums_nyc_private.json").write_text(json.dumps(out, indent=2))
    print("wrote pums_nyc_private.json")

if __name__ == "__main__":
    main()
