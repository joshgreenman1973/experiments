#!/usr/bin/env python3
"""Build data/pay.json for the pay-and-rent-burden page from data already pulled:
BLS CES and CPI (data/raw/bls.json), OEWS (data/oews.json), ACS (data/acs.json),
city-set minimum wage (data/administered.json) and report figures
(data/burden_static.json). Same rule as the price page: pay and prices are shown
side by side over identical spans, never subtracted."""
import datetime, json, pathlib

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
    """Twelve-month change, each month: NYC average hourly earnings (three-month
    average, to damp sampling noise) and New York-area CPI (single month)."""
    rows = []
    m = "2025-01"
    end = max(max(AHE), max(CPI))
    while m <= end:
        rows.append({"m": m, "pay": pct(avg3(AHE, m), avg3(AHE, ym_add(m, -12))),
                     "prices": pct(CPI.get(m), CPI.get(ym_add(m, -12)))})
        m = ym_add(m, 1)
    return rows


def yearly_wages():
    out = []
    for y, r in OEWS["years"].items():
        out.append(dict(r, cpi_may=CPI.get(f"{y}-05")))
    first = out[0]
    for r in out:
        r["median_since_first"] = pct(r["median_hourly"], first["median_hourly"])
        r["mean_since_first"] = pct(r["mean_hourly"], first["mean_hourly"])
        r["cpi_since_first"] = pct(r["cpi_may"], first["cpi_may"])
    last, prev = out[-1], out[-2]
    return {"source": OEWS["source"], "url": OEWS["url"], "years": out,
            "latest": {"year": last["year"], "median_yoy": pct(last["median_hourly"], prev["median_hourly"]),
                       "mean_yoy": pct(last["mean_hourly"], prev["mean_hourly"]),
                       "cpi_yoy": pct(last["cpi_may"], prev["cpi_may"])}}


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
        "hvs": STATIC["hvs"],
        "shelf": STATIC["shelf"],
    }
    (ROOT / "data/pay.json").write_text(json.dumps(d, indent=1))
    w = d["wages"]["years"][-1]
    print("built pay:", ref, "| median since", d["wages"]["years"][0]["year"], w["median_since_first"],
          "vs prices", w["cpi_since_first"], "| ACS", max(ACS["years"]))


if __name__ == "__main__":
    main()
