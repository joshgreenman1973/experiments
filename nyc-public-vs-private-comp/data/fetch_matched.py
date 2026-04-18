#!/usr/bin/env python3
"""Fetch NYC payroll medians for common occupation titles (public sector).
Combine with hardcoded BLS OEWS NY-NJ-PA MSA May 2024 medians (all employers)
for side-by-side comparison.
"""
import json, urllib.parse, urllib.request
from pathlib import Path

# Curated title keywords -> occupation canonical name
TITLES = [
    ("Registered nurse",          "NURSE",            "29-1141"),
    ("Police officer",            "POLICE OFFICER",   "33-3051"),
    ("Firefighter",               "FIREFIGHTER",      "33-2011"),
    ("Teacher",                   "TEACHER",          "25-2021"),
    ("Accountant",                "ACCOUNTANT",       "13-2011"),
    ("Civil engineer",            "ENGINEER",         "17-2051"),
    ("Attorney / lawyer",         "ATTORNEY",         "23-1011"),
    ("Electrician",               "ELECTRICIAN",      "47-2111"),
    ("Social worker",             "SOCIAL WORKER",    "21-1021"),
    ("Bus driver",                "BUS OPERATOR",     "53-3052"),
    ("Plumber",                   "PLUMBER",          "47-2152"),
    ("Office assistant",          "OFFICE ASSISTANT", "43-6014"),
]

# BLS OEWS, New York-Newark-Jersey City NY-NJ MSA, May 2024 median annual wages (area 3562200).
# These are all-ownership MSA medians — skew toward private for most roles because
# private employment dominates most occupations in the region (except police/fire/teacher).
OEWS_NY_MSA_MAY_2024 = {
    "29-1141": {"median": 109940, "mean": 112060, "label": "Registered nurses"},
    "33-3051": {"median": 108860, "mean": 110220, "label": "Police & sheriff patrol"},
    "33-2011": {"median": 99390,  "mean": 106440, "label": "Firefighters"},
    "25-2021": {"median": 92590,  "mean": 93990,  "label": "Elementary teachers, except special ed"},
    "13-2011": {"median": 108620, "mean": 127270, "label": "Accountants & auditors"},
    "17-2051": {"median": 100980, "mean": 112520, "label": "Civil engineers"},
    "23-1011": {"median": 197760, "mean": 231060, "label": "Lawyers"},
    "47-2111": {"median": 93100,  "mean": 94840,  "label": "Electricians"},
    "21-1021": {"median": 70090,  "mean": 75710,  "label": "Child, family, school social workers"},
    "53-3052": {"median": 65960,  "mean": 64390,  "label": "Bus drivers, transit & intercity"},
    "47-2152": {"median": 83510,  "mean": 88450,  "label": "Plumbers, pipefitters"},
    "43-6014": {"median": 51050,  "mean": 54020,  "label": "Secretaries & admin assistants"},
}

BASE = "https://data.cityofnewyork.us/resource/k397-673e.json"

def query(params):
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)

def nyc_median_mean(keyword, year=2025):
    rows = query({
        "$select": "count(*) as n, median(regular_gross_paid) as med, avg(regular_gross_paid) as mean, median(regular_gross_paid + total_ot_paid + total_other_pay) as med_tot, avg(regular_gross_paid + total_ot_paid + total_other_pay) as mean_tot",
        "$where": f"fiscal_year={year} AND pay_basis='per Annum' AND regular_gross_paid > 20000 AND upper(title_description) like '%{keyword}%'",
        "$limit": "1",
    })
    r = rows[0] if rows else {}
    return {
        "n": int(r.get("n", 0) or 0),
        "median_reg": float(r.get("med") or 0),
        "mean_reg": float(r.get("mean") or 0),
        "median_total": float(r.get("med_tot") or 0),
        "mean_total": float(r.get("mean_tot") or 0),
    }

def main():
    out = []
    for name, kw, soc in TITLES:
        pub = nyc_median_mean(kw)
        msa = OEWS_NY_MSA_MAY_2024.get(soc, {})
        out.append({
            "name": name,
            "keyword": kw,
            "soc": soc,
            "nyc_public": pub,
            "nyc_msa_all": msa,
        })
        print(f"{name}: pub_n={pub['n']}, pub_med=${pub['median_reg']:.0f} / MSA_med=${msa.get('median', 0):.0f}")
    Path(__file__).parent.joinpath("matched.json").write_text(json.dumps(out, indent=2))
    print("wrote matched.json")

if __name__ == "__main__":
    main()
