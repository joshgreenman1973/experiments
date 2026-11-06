#!/usr/bin/env python3
"""Build data/pay.json for the pay-and-rent-burden page from data already pulled:
BLS CES and CPI (data/raw/bls.json), OEWS (data/oews.json), ACS (data/acs.json),
city-set minimum wage (data/administered.json) and report figures
(data/burden_static.json). Same rule as the price page: pay and prices are shown
side by side, never subtracted.

The spans are not always identical, and the page says so:
  * Monthly: three-month-average earnings growth beside single-month CPI
    inflation (the published twelve-month change for the last month of the three).
  * Yearly: OEWS wages beside the CPI for May of each year. OEWS changed its
    New York area with the May 2024 estimates (25 counties to 22), so changes are
    computed only within a stretch of years that share one area, never across
    the break. The CPI area stays at 25 counties throughout."""
import datetime, json, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLS = json.loads((ROOT / "data/raw/bls.json").read_text())["series"]
OEWS = json.loads((ROOT / "data/oews.json").read_text())
ACS = json.loads((ROOT / "data/acs.json").read_text())
STATIC = json.loads((ROOT / "data/burden_static.json").read_text())
ADMIN = json.loads((ROOT / "data/administered.json").read_text())
CPI = BLS["CUURS12ASA0"]["obs"]
AHE = BLS["SMU36935610500000003"]["obs"]


def ym_add(ym, k):
    y, m = map(int, ym.split("-"))
    m += k
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def pct(a, b):
    return None if a is None or b is None else round(100 * (a / b - 1), 4)


def avg3(o, m):
    v = [o.get(ym_add(m, -k)) for k in range(3)]
    return None if None in v else sum(v) / 3


def monthly():
    """Twelve-month change, each month: NYC average hourly earnings, three-month
    average against the same three months a year earlier (to damp sampling noise),
    and New York-area CPI, single month against the same month a year earlier.
    The two windows differ; the page labels them."""
    rows = []
    m = "2025-01"
    end = max(max(AHE), max(CPI))
    while m <= end:
        rows.append({"m": m, "pay": pct(avg3(AHE, m), avg3(AHE, ym_add(m, -12))),
                     "prices": pct(CPI.get(m), CPI.get(ym_add(m, -12)))})
        m = ym_add(m, 1)
    return rows


def yearly_wages():
    """OEWS May wages beside May CPI. Rows are grouped into stretches of years with
    the same OEWS area; every change is computed from the first year of its own
    stretch, so no figure spans the 2024 change of area."""
    out = []
    for y, r in OEWS["years"].items():
        out.append(dict(r, cpi_may=CPI.get(f"{y}-05")))
    segs = []
    for r in out:
        if not segs or segs[-1]["area_title"] != r["area_title"]:
            segs.append({"area_title": r["area_title"], "counties": r["counties"], "area_note": r["area_note"],
                         "from": r["year"], "rows": []})
        segs[-1]["rows"].append(r)
    for i, sg in enumerate(segs):
        f = sg["rows"][0]
        for r in sg["rows"]:
            r["segment"] = i
            r["median_since_seg"] = pct(r["median_hourly"], f["median_hourly"])
            r["mean_since_seg"] = pct(r["mean_hourly"], f["mean_hourly"])
            r["cpi_since_seg"] = pct(r["cpi_may"], f["cpi_may"])
        l = sg["rows"][-1]
        sg.update({"to": l["year"], "median_change": l["median_since_seg"], "mean_change": l["mean_since_seg"],
                   "cpi_change": l["cpi_since_seg"]})
        del sg["rows"]
    # Year-over-year changes, only where both years share an area.
    out[0].update(comparable_with_prior=None, median_yoy=None, mean_yoy=None, cpi_yoy=None)
    for prev, r in zip(out, out[1:]):
        same = prev["area_title"] == r["area_title"]
        r["comparable_with_prior"] = same
        r["median_yoy"] = pct(r["median_hourly"], prev["median_hourly"]) if same else None
        r["mean_yoy"] = pct(r["mean_hourly"], prev["mean_hourly"]) if same else None
        r["cpi_yoy"] = pct(r["cpi_may"], prev["cpi_may"])
    last, prev = out[-1], out[-2]
    breaks = [r["year"] for r in out[1:] if not r["comparable_with_prior"]]
    return {"source": OEWS["source"], "url": OEWS["url"], "area_change_url": OEWS.get("area_change_url"),
            "cpi_area": "New York-Newark-Jersey City, NY-NJ-PA", "cpi_counties": 25,
            "years": out, "segments": segs, "breaks": breaks,
            "latest": {"year": last["year"], "comparable": last["comparable_with_prior"],
                       "median_yoy": last["median_yoy"], "mean_yoy": last["mean_yoy"],
                       "cpi_yoy": pct(last["cpi_may"], prev["cpi_may"]), "counties": last["counties"]}}


def acs_change():
    """Latest two ACS years' median rent-to-income ratio, with the Census Bureau's
    standard significance test (90 percent margins, SE = MOE / 1.645)."""
    ys = sorted(ACS["years"])
    a, b = ACS["years"][ys[-2]], ACS["years"][ys[-1]]
    d = round(b["median_ratio"] - a["median_ratio"], 1)
    se = math.hypot(a["median_ratio_moe"] / 1.645, b["median_ratio_moe"] / 1.645)
    z = abs(d) / se if se else None
    return {"from": ys[-2], "to": ys[-1], "change_points": d, "z": round(z, 2) if z is not None else None,
            "significant_90": bool(z is not None and z > 1.645)}


def main():
    mw = next(i for i in ADMIN["items"] if i["id"] == "min_wage")
    ref = max(AHE)
    d = {
        "built": datetime.date.today().isoformat(),
        "monthly": {"ahe_ref": ref, "ahe_latest": AHE[ref], "cpi_ref": max(CPI), "rows": monthly(),
                    "ahe_id": "SMU36935610500000003", "cpi_id": "CUURS12ASA0"},
        "min_wage": {"steps": mw["steps"], "url": mw["url"], "source": mw["source"]},
        "wages": yearly_wages(),
        "acs": ACS,
        "acs_change": acs_change(),
        "hvs": STATIC["hvs"],
        "shelf": STATIC["shelf"],
        "comptroller": STATIC["comptroller"],
    }
    (ROOT / "data/pay.json").write_text(json.dumps(d, indent=1))
    segs = "; ".join(f"{s['from']}-{s['to']} ({s['counties']} counties) median {s['median_change']} vs prices {s['cpi_change']}"
                     for s in d["wages"]["segments"])
    print("built pay:", ref, "|", segs, "| ACS", max(ACS["years"]), d["acs_change"])


if __name__ == "__main__":
    main()
