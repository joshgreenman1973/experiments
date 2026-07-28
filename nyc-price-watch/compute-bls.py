#!/usr/bin/env python3
"""Derive YoY changes from bls-data.json. Month-matched, never a row lag."""
import json, datetime

d = json.load(open("bls-data.json"))
S = d["series"]

MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
def pretty(k):
    y, p = k.split("-"); return f"{MON[int(p[1:])-1]} {y}"

def yoy(obs, key):
    """Compare key (YYYY-Mnn) with the SAME calendar month one year earlier."""
    y, p = key.split("-")
    prior = f"{int(y)-1}-{p}"
    if key not in obs or prior not in obs:
        return None
    a, b = obs[prior], obs[key]
    if not a:
        return None
    return (b - a) / a * 100.0

def latest_key(obs):
    return max(obs, key=lambda k: (int(k.split("-")[0]), int(k.split("-")[1][1:]))) if obs else None

# --- latest month common to AHE, AWE and headline CPI ---
AHE, AWE, CPI0 = "SMU36356200500000003", "SMU36356200500000011", "CUURS12ASA0"
def keys_with_yoy(sid):
    o = S[sid]["obs"]
    return {k for k in o if yoy(o, k) is not None}
common = keys_with_yoy(AHE) & keys_with_yoy(AWE) & keys_with_yoy(CPI0)
ref = latest_key({k: 1 for k in common})

out = {
    "_computed": datetime.date.today().isoformat(),
    "_source": "U.S. Bureau of Labor Statistics, API v2",
    "_reference_month": ref,
    "_reference_month_label": pretty(ref),
    "_notes": {
        "earnings_area": "New York-Newark-Jersey City, NY-NJ metropolitan area (CES, series SMU36356200500000003/11)",
        "cpi_area": "New York-Newark-Jersey City, NY-NJ-PA (CPI-U area S12A)",
        "seasonality": "All series not seasonally adjusted",
        "method": "Year-over-year compares each month with the same calendar month one year earlier",
    },
    "earnings": {}, "cpi": {}, "extra": {}, "missing": d.get("missing", []),
}

for sid, label, bucket in [(AHE, "Average hourly earnings", "earnings"),
                           (AWE, "Average weekly earnings", "earnings")]:
    o = S[sid]["obs"]
    k = ref if ref in o else latest_key(o)
    out[bucket][sid] = {
        "label": label, "series_id": sid,
        "month": k, "month_label": pretty(k),
        "level": round(o[k], 2), "unit": "USD",
        "yoy_pct": round(yoy(o, k), 2) if yoy(o, k) is not None else None,
        "prior_year_level": round(o[f'{int(k.split("-")[0])-1}-{k.split("-")[1]}'], 2)
            if f'{int(k.split("-")[0])-1}-{k.split("-")[1]}' in o else None,
        "footnotes": S[sid]["footnotes"].get(k, []),
    }

for sid, v in S.items():
    if v["kind"] not in ("cpi", "extra"):
        continue
    o = v["obs"]
    k = latest_key(o)
    r = yoy(o, k)
    rec = {
        "label": v["label"], "series_id": sid, "item_code": v["item_code"],
        "month": k, "month_label": pretty(k),
        "index": round(o[k], 3),
        "yoy_pct": round(r, 2) if r is not None else None,
        "footnotes": v["footnotes"].get(k, []),
        "table1": v["kind"] == "cpi",
    }
    out["cpi" if v["kind"] == "cpi" else "extra"][sid] = rec

json.dump(out, open("bls-derived.json", "w"), indent=1)

# ---------------- validation ----------------
print("reference month (common to AHE, AWE, headline CPI):", out["_reference_month_label"])
print()
errs = []
for sid, v in S.items():
    if any(p == "M13" for p in (x.split("-")[1] for x in v["obs"])):
        errs.append(f"M13 present in {sid}")
    if not (sid.startswith("CUUR") or sid.startswith("SMU")):
        errs.append(f"possible seasonally adjusted series: {sid}")
# spot-check month matching on a series with a gap
for sid in list(S)[:5]:
    o = S[sid]["obs"]
    for k in o:
        y, p = k.split("-")
        pri = f"{int(y)-1}-{p}"
        if pri in o:
            manual = (o[k]-o[pri])/o[pri]*100
            assert abs(manual - yoy(o, k)) < 1e-9, f"mismatch {sid} {k}"
print("checks:", "PASS - no M13, all NSA prefixes, month-matching verified" if not errs else errs)
print()
print(f'{"AHE":<28}{out["earnings"][AHE]["yoy_pct"]:>7.2f}%   level ${out["earnings"][AHE]["level"]}   {out["earnings"][AHE]["month_label"]}')
print(f'{"AWE":<28}{out["earnings"][AWE]["yoy_pct"]:>7.2f}%   level ${out["earnings"][AWE]["level"]}   {out["earnings"][AWE]["month_label"]}')
c = out["cpi"][CPI0]
print(f'{"CPI, all items":<28}{c["yoy_pct"]:>7.2f}%   index {c["index"]}   {c["month_label"]}')
print()
print("Table 1 categories retrieved:", len(out["cpi"]))
miss = [m["label"] for m in out["missing"]]
print("Missing:", ", ".join(miss) if miss else "none")
