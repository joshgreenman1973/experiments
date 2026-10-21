#!/usr/bin/env python3
"""Turn the raw pulls in data/raw/ into data/dashboard.json, the only file the page reads.

The comparison rules, applied to every series:
  * Reference month = the latest month BLS has published for the New York CPI.
  * "This year" = December 2025 to the reference month.
  * "Same months last year" = December 2024 to the same month of 2025.
    Both spans cover the same calendar months, so ordinary seasonal swings
    (summer gas, spring apparel) appear in both and cancel in the comparison.
  * "Past 12 months" = reference month vs the same month a year earlier.
  * Nothing is seasonally adjusted, smoothed or re-based except where a
    series note says so.
"""
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
BLS = json.loads((RAW / "bls.json").read_text())["series"]
W = json.loads((ROOT / "data/weights.json").read_text())
ADMIN = json.loads((ROOT / "data/administered.json").read_text())
EXTRA = json.loads((ROOT / "data/other_series.json").read_text()) if (ROOT / "data/other_series.json").exists() else {}

NY = "CUURS12A"


def ym_add(ym, k):
    y, m = map(int, ym.split("-"))
    m += k
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def pct(a, b):
    if a is None or b is None:
        return None
    return round(100 * (a / b - 1), 2)


REF = max(BLS[NY + "SA0"]["obs"])          # latest published NY CPI month
REF_Y = int(REF[:4])
BASE = f"{REF_Y - 1}-12"                    # December before this year
REF_LY = ym_add(REF, -12)
BASE_LY = f"{REF_Y - 2}-12"


def spans(obs, ref=REF):
    """Since-December, same-span-last-year and 12-month changes for a monthly series."""
    y = int(ref[:4])
    b, rly, bly = f"{y - 1}-12", ym_add(ref, -12), f"{y - 2}-12"
    return {
        "ref": ref,
        "ytd": pct(obs.get(ref), obs.get(b)),
        "ytd_ly": pct(obs.get(rly), obs.get(bly)),
        "yoy": pct(obs.get(ref), obs.get(rly)),
    }


def series(sid, start="2024-12"):
    o = BLS[sid]["obs"]
    return [[k, v] for k, v in o.items() if k >= start]


# --- 1. Where this year's inflation came from: exact contributions -------------
GROUPS = [
    ("SAH", "Housing"), ("SAT", "Transportation"), ("SAF", "Food and beverages"),
    ("SAM", "Medical care"), ("SAE", "Education and communication"),
    ("SAR", "Recreation"), ("SAA", "Apparel"), ("SAG", "Other goods and services"),
]
# Housing, split into the parts BLS publishes for New York; the rest is a remainder.
HOUSING_PARTS = [
    ("SEHA", "Rent of primary residence", "Rent"),
    ("SEHC01", "Owners' equivalent rent of primary residence", "Owners' equivalent rent"),
    ("SAH3", "Household furnishings and operations", "Furnishings and household operations"),
]
TRANSPORT_PARTS = [("SETB01", "Gasoline (all types)", "Gasoline")]


def contributions(base, ref, wkey):
    w = W[wkey]["weights"]
    out = []
    for code, name in GROUPS:
        o = BLS[NY + code]["obs"]
        ch = o[ref] / o[base] - 1
        row = {"code": code, "name": name, "weight": w[name],
               "change": round(100 * ch, 2), "contrib": round(w[name] * ch, 3), "parts": []}
        parts = HOUSING_PARTS if code == "SAH" else TRANSPORT_PARTS if code == "SAT" else []
        acc = 0
        for pc_, pname, label in parts:
            po = BLS[NY + pc_]["obs"]
            pch = po[ref] / po[base] - 1
            c = w[pname] * pch
            acc += c
            row["parts"].append({"code": pc_, "name": label, "weight": w[pname],
                                 "change": round(100 * pch, 2), "contrib": round(c, 3)})
        if parts:
            rw = w[name] - sum(w[p[1]] for p in parts)
            row["parts"].append({"code": None, "name": "Everything else in " + name.lower(),
                                 "weight": round(rw, 3), "change": None,
                                 "contrib": round(row["contrib"] - acc, 3), "remainder": True})
        out.append(row)
    a = BLS[NY + "SA0"]["obs"]
    total = round(100 * (a[ref] / a[base] - 1), 2)
    check = round(sum(r["contrib"] for r in out), 2)
    assert abs(check - total) < 0.02, (check, total)
    return {"base": base, "ref": ref, "weights_from": wkey, "total": total, "groups": out}


# --- 2. Category lines (all on the Dec = 100 basis) ---------------------------
LINES = {
    "all": ("SA0", "All items"),
    "core": ("SA0L1E", "All items less food and energy"),
    "rent": ("SEHA", "Rent of primary residence"),
    "oer": ("SEHC01", "Owners' equivalent rent"),
    "groceries": ("SAF11", "Food at home"),
    "restaurants": ("SEFV", "Food away from home"),
    "energy": ("SA0E", "Energy"),
    "gasoline": ("SETB01", "Gasoline"),
    "medical": ("SAM", "Medical care"),
    "tuition_childcare": ("SEEB", "Tuition, other school fees and child care"),
    "apparel": ("SAA", "Apparel"),
    "new_cars": ("SETA01", "New vehicles"),
    "used_cars": ("SETA02", "Used cars and trucks"),
    "furnishings": ("SAH3", "Household furnishings and operations"),
    "recreation": ("SAR", "Recreation"),
}
GROCERY_AISLES = [
    ("SAF111", "Cereals and bakery products"),
    ("SAF112", "Meats, poultry, fish and eggs"),
    ("SEFJ", "Dairy and related products"),
    ("SAF113", "Fruits and vegetables"),
    ("SAF114", "Nonalcoholic beverages"),
    ("SAF115", "Other food at home"),
]
STAPLES = [  # BLS average prices, Northeast region (dollars per unit)
    ("APU0100703112", "Ground beef, 100% beef", "lb"),
    ("APU0100FF1101", "Chicken breast, boneless", "lb"),
    ("APU0100706111", "Whole chicken", "lb"),
    ("APU0100704111", "Bacon, sliced", "lb"),
    ("APU0100712311", "Tomatoes, field grown", "lb"),
    ("APU0100712112", "White potatoes", "lb"),
]


def weight_for(name):
    return W["2025-12"]["weights"].get(name)


def cpi_line(key, code, label):
    sid = NY + code
    o = BLS[sid]["obs"]
    return {"key": key, "id": sid, "label": label, "weight": weight_for(
        {"SA0": "All items", "SA0L1E": "All items less food and energy", "SEHA": "Rent of primary residence",
         "SEHC01": "Owners' equivalent rent of primary residence", "SAF11": "Food at home",
         "SEFV": "Food away from home", "SA0E": "Energy", "SETB01": "Gasoline (all types)",
         "SAM": "Medical care", "SAA": "Apparel", "SAH3": "Household furnishings and operations",
         "SAR": "Recreation"}.get(code, "")),
        **spans(o), "series": series(sid, BASE_LY)}


def main():
    d = {
        "built": datetime.date.today().isoformat(),
        "ref": REF, "base": BASE, "ref_ly": REF_LY, "base_ly": BASE_LY,
        "bls_fetched": json.loads((RAW / "bls.json").read_text())["fetched"],
        "contrib": contributions(BASE, REF, BASE),
        "contrib_ly": contributions(BASE_LY, REF_LY, BASE_LY),
        "lines": [cpi_line(k, c, l) for k, (c, l) in LINES.items()],
        "aisles": [cpi_line(c, c, l) for c, l in GROCERY_AISLES],
        "staples": [{"id": s, "label": l, "unit": u, **spans(BLS[s]["obs"], max(BLS[s]["obs"])),
                     "latest": BLS[s]["obs"][max(BLS[s]["obs"])], "series": series(s, BASE_LY)}
                    for s, l, u in STAPLES if s in BLS],
        "us": {k: spans(BLS[s]["obs"]) for k, s in
               (("all", "CUUR0000SA0"), ("rent", "CUUR0000SEHA"), ("groceries", "CUUR0000SAF11"))},
        "gas_bls": {"id": "APUS12A74714", **spans(BLS["APUS12A74714"]["obs"]),
                    "latest": BLS["APUS12A74714"]["obs"][REF], "series": series("APUS12A74714", BASE_LY)},
        "pay": pay(),
        "administered": administered(),
        "rent_rules": ADMIN["rent_rules"],
        "zori": monthly_block(EXTRA["zori"], lambda v: v),
        "energy": energy(),
        "homes": homes(),
    }
    (ROOT / "data/dashboard.json").write_text(json.dumps(d, indent=1))
    print("built", REF, "all items since Dec:", d["contrib"]["total"], "same span last year:", d["contrib_ly"]["total"])


def monthly_block(src, val, ref=None):
    """Spans for a non-BLS monthly series, at the CPI reference month when it has it,
    otherwise at its own latest month."""
    m = {k: val(v) for k, v in src["monthly"].items()}
    r = ref or (REF if REF in m else max(m))
    return {"source": src["source"], "url": src["url"], "unit": src.get("unit"),
            **spans(m, r), "latest": m[r], "series": [[k, v] for k, v in m.items() if k >= BASE_LY]}


def energy():
    gas = EXTRA["gas_nyc"]
    # The current month is incomplete until its last weekly reading; use the CPI month.
    g = monthly_block(gas, lambda v: v["v"], REF)
    g["last_week"] = gas["last_week"]
    ce = EXTRA["coned"]
    c = monthly_block(ce, lambda v: v["v"])
    c["preliminary"] = ce["monthly"][c["ref"]]["service"]
    oil = EXTRA["heating_oil_ny"]
    om = {k: v["v"] for k, v in oil["monthly"].items()}
    oref = max(om)
    lw = oil["last_week"]
    ya = lw.get("year_ago")
    o = {"source": oil["source"], "url": oil["url"], "unit": "$/gal", "last_week": lw,
         "yoy_week": pct(lw["v"], ya["v"]) if ya else None,
         "series": [[k, v] for k, v in om.items() if k >= "2024-10"]}
    ne = {k: {"id": s_, **spans(BLS[s_]["obs"]), "series": series(s_, BASE_LY)} for k, s_ in
          (("electricity", "CUUR0100SEHF01"), ("piped_gas", "CUUR0100SEHF02"))}
    return {"gasoline": g, "coned": c, "heating_oil": o, "northeast": ne}


def homes():
    f = EXTRA["fhfa"]
    po = {k: v for k, v in f["purchase_only_nsa"].items() if v}
    ref = max(po)
    y, q = ref.split("-")
    ly = f"{int(y) - 1}-{q}"
    return {"source": f["source"], "url": f["url"], "ref": ref, "yoy": pct(po[ref], po.get(ly)),
            "series": [[k, v] for k, v in po.items() if k >= "2023-Q1"]}


def administered():
    """For each city-set price: the price in effect on Dec. 31 of last year, a year
    before the build date, and on the build date."""
    today = datetime.date.today().isoformat()
    year_ago = f"{int(today[:4]) - 1}{today[4:]}"
    dec = f"{int(today[:4]) - 1}-12-31"

    def at(steps, d):
        v = None
        for s_, x in steps:
            if s_ <= d:
                v = x
        return v

    out = []
    for it in ADMIN["items"]:
        st = it["steps"]
        now, b, ly = at(st, today), at(st, dec), at(st, year_ago)
        row = dict(it, now=now, as_of=today, at_base=b, at_year_ago=ly)
        if not it.get("no_change_calc"):
            row["since_dec"] = pct(now, b)
            row["yoy"] = pct(now, ly)
        out.append(row)
    return {"verified": ADMIN["verified"], "items": out}


def pay():
    """CES New York City average hourly earnings, total private. Monthly values for a
    single city are noisy, so the comparison uses three-month averages."""
    sid = "SMU36935610500000003"
    o = BLS[sid]["obs"]
    ref = max(o)

    def avg3(m):
        vals = [o.get(ym_add(m, -k)) for k in range(3)]
        return None if None in vals else sum(vals) / 3

    return {"id": sid, "ref": ref, "latest": o[ref],
            "yoy_3mo": pct(avg3(ref), avg3(ym_add(ref, -12))),
            "series": series(sid, "2024-01")}


if __name__ == "__main__":
    main()
