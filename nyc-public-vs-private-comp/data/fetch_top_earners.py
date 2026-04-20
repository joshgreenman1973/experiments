#!/usr/bin/env python3
"""Fetch top earner(s) per NYC agency for FY2025 from the Citywide Payroll dataset.
Total comp = regular_gross_paid + total_ot_paid + total_other_pay.
"""
import json, urllib.parse, urllib.request
from pathlib import Path

BASE = "https://data.cityofnewyork.us/resource/k397-673e.json"
YEAR = 2025

def query(params):
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)

def agencies_top_earners():
    # First get list of agencies with >= 500 annual-basis workers (same filter as tab 07)
    ag = query({
        "$select": "agency_name, count(*) as n",
        "$where": f"fiscal_year={YEAR} AND pay_basis='per Annum' AND regular_gross_paid > 20000",
        "$group": "agency_name",
        "$having": "count(*) >= 500",
        "$order": "n desc",
        "$limit": "60",
    })
    results = []
    for a in ag:
        name = a["agency_name"]
        # Top earner at this agency (by total comp)
        rows = query({
            "$select": "first_name, last_name, title_description, agency_name, regular_gross_paid, total_ot_paid, total_other_pay",
            "$where": f"fiscal_year={YEAR} AND agency_name='{name.replace(chr(39), chr(39)*2)}'",
            "$order": "regular_gross_paid + total_ot_paid + total_other_pay desc",
            "$limit": "1",
        })
        if not rows:
            continue
        r = rows[0]
        reg = float(r.get("regular_gross_paid") or 0)
        ot = float(r.get("total_ot_paid") or 0)
        oth = float(r.get("total_other_pay") or 0)
        total = reg + ot + oth
        results.append({
            "agency": name,
            "first": (r.get("first_name") or "").strip().title(),
            "last": (r.get("last_name") or "").strip().title(),
            "title": (r.get("title_description") or "").strip(),
            "reg": round(reg),
            "ot": round(ot),
            "other": round(oth),
            "total": round(total),
            "n_agency": int(a["n"]),
        })
        print(f"  {name[:40]:40} {results[-1]['first']} {results[-1]['last']:20} ${total:,.0f}")
    return results

def citywide_top_earners():
    rows = query({
        "$select": "first_name, last_name, title_description, agency_name, regular_gross_paid, total_ot_paid, total_other_pay",
        "$where": f"fiscal_year={YEAR} AND regular_gross_paid > 20000",
        "$order": "regular_gross_paid + total_ot_paid + total_other_pay desc",
        "$limit": "25",
    })
    out = []
    for r in rows:
        reg = float(r.get("regular_gross_paid") or 0)
        ot = float(r.get("total_ot_paid") or 0)
        oth = float(r.get("total_other_pay") or 0)
        out.append({
            "agency": r.get("agency_name"),
            "first": (r.get("first_name") or "").strip().title(),
            "last": (r.get("last_name") or "").strip().title(),
            "title": (r.get("title_description") or "").strip(),
            "reg": round(reg),
            "ot": round(ot),
            "other": round(oth),
            "total": round(reg + ot + oth),
        })
    return out

def main():
    print("== Top earner per agency ==")
    ag = agencies_top_earners()
    print("\n== Top 25 citywide ==")
    city = citywide_top_earners()
    for r in city[:10]:
        print(f"  {r['first']} {r['last']} · {r['title'][:40]} · {r['agency'][:30]} · ${r['total']:,}")
    out = {"year": YEAR, "by_agency": ag, "citywide_top25": city}
    Path(__file__).parent.joinpath("top_earners.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote top_earners.json ({len(ag)} agencies, {len(city)} citywide)")

if __name__ == "__main__":
    main()
