#!/usr/bin/env python3
"""
NYC Citywide Payroll Data (Socrata dataset k397-673e).
Aggregate by fiscal_year: count, mean gross pay, and percentiles via bucket
histogram. Also aggregate by agency for the most recent year.
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://data.cityofnewyork.us/resource/k397-673e.json"

def q(params):
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def totals_by_year():
    rows = q({
        "$select": "fiscal_year, count(*) as n, "
                   "avg(regular_gross_paid) as mean_reg, "
                   "avg(total_ot_paid) as mean_ot, "
                   "avg(total_other_pay) as mean_other, "
                   "sum(regular_gross_paid) as sum_reg, "
                   "sum(total_ot_paid) as sum_ot, "
                   "sum(total_other_pay) as sum_other, "
                   "median(regular_gross_paid) as median_reg",
        "$group": "fiscal_year",
        "$where": "regular_gross_paid > 0",
        "$order": "fiscal_year",
        "$limit": "200",
    })
    return rows

def by_agency_latest(year):
    rows = q({
        "$select": "agency_name, count(*) as n, "
                   "avg(regular_gross_paid) as mean_reg, "
                   "avg(total_ot_paid) as mean_ot, "
                   "avg(total_other_pay) as mean_other, "
                   "median(regular_gross_paid) as median_reg",
        "$where": f"fiscal_year={year} AND regular_gross_paid > 0 AND pay_basis='per Annum'",
        "$group": "agency_name",
        "$order": "n DESC",
        "$limit": "500",
    })
    return rows

def salary_histogram(year):
    """Count workers in $10k bins for given year."""
    buckets = []
    edges = list(range(0, 260001, 10000))  # 0,10k,..260k
    for i, lo in enumerate(edges[:-1]):
        hi = edges[i+1]
        try:
            rows = q({
                "$select": "count(*) as n",
                "$where": f"fiscal_year={year} AND pay_basis='per Annum' AND "
                          f"regular_gross_paid >= {lo} AND regular_gross_paid < {hi}",
                "$limit": "1",
            })
            buckets.append({"lo": lo, "hi": hi, "n": int(rows[0]["n"])})
        except Exception as e:
            print(f"bucket fail {lo}-{hi}: {e}")
    try:
        rows = q({
            "$select": "count(*) as n",
            "$where": f"fiscal_year={year} AND pay_basis='per Annum' AND regular_gross_paid >= 260000",
            "$limit": "1",
        })
        buckets.append({"lo": 260000, "hi": None, "n": int(rows[0]["n"])})
    except Exception as e:
        print(f"top bucket fail: {e}")
    return buckets

def main():
    out_dir = Path(__file__).parent
    print("fetching totals by year...")
    yearly = totals_by_year()
    (out_dir / "payroll_yearly.json").write_text(json.dumps(yearly, indent=2))
    latest_year = max(int(r["fiscal_year"]) for r in yearly)
    print(f"latest fiscal_year = {latest_year}")
    print("fetching by agency (latest)...")
    ag = by_agency_latest(latest_year)
    (out_dir / "payroll_by_agency.json").write_text(json.dumps({"year": latest_year, "agencies": ag}, indent=2))
    print("fetching salary histogram (latest)...")
    hist = salary_histogram(latest_year)
    (out_dir / "payroll_histogram.json").write_text(json.dumps({"year": latest_year, "bins": hist}, indent=2))
    print("done")

if __name__ == "__main__":
    main()
