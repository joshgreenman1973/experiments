#!/usr/bin/env python3
"""Build data.json for "The fully loaded budget".

New York City's expense budget parks pensions, health insurance and legal
payouts in three central agencies rather than against the agencies whose
employees and operations incur them. This pushes that money back where it was
run up, for every adopted budget the city publishes as open data.

Everything reconciles to the budget's own printed totals. Any mismatch beyond
the rounding on individual lines fails the build rather than warning.

    python3 build/build.py              # every year the dataset carries
    python3 build/build.py 2024 2027    # a range
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BUDGET = "https://data.cityofnewyork.us/resource/mwzb-yiwb.json"
CLAIMS = "https://data.cityofnewyork.us/resource/ex6k-ym48.json"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")

CLAIMS_FROM = "2021"          # first claims year used for the judgments split
# Census Bureau vintage 2025 estimate for New York City, the same denominator
# used in The New York City ledger. Held flat for budget years the Bureau has
# not yet reached, so year-over-year comparisons here are of dollars, not of
# dollars per head.
POPULATION = 8584629

# Central agencies that hold pooled money rather than run anything.
POOL_AGENCIES = {"095", "098", "099"}

# Pension object codes, straight from the budget's own line names. Each named
# fund maps to the agency whose workforce belongs to it; the contingent
# reserve fund is the city's NYCERS payment and covers everyone else. These
# strings are unchanged across every year in the dataset.
PENSION_TO_AGENCY = {
    "TEACH RET SYS CONTINGNT RES SY": "040",
    "TEACH RET SYS PENS FND RES #2": "040",
    "BOARD OF EDUCATION RETIRE. SYS": "040",
    "POLICE ACTUARIAL PENSION FUND": "056",
    "FIRE ACTUARIAL PENSION FUND": "057",
}
PENSION_POOLED = {"CONTINGENT RESERVE FUND", "ADDITIONAL PENSION ACCRUAL"}

PAY_CLASSES = ("01", "02", "03", "04")
# Uniformed and pedagogical pay belongs to a named fund, so it comes out of the
# base that shares the employees' retirement system payment.
OWN_FUND_PAY = {
    "056": ["FULL TIME UNIFORMED PERSONNEL"],
    "057": ["FULL TIME UNIFORMED PERSONNEL"],
    "040": ["*"],
}

RETIREE_BUDGET_CODE = "3006"                       # Retiree Health Benefits Trust
FRINGE_BY_PAYROLL = {"SOCIAL SECURITY CONTRIBUTIONS"}
JUDGMENTS_CODE = "JUDGEMENTS AND CLAIMS"

CLAIMS_TO_AGENCY = {
    "Police Department": "056",
    "Department of Transportation": "841",
    "Department of Sanitation": "827",
    "Department of Education": "040",
    "NYC Health + Hospitals": "819",
    "Department of Correction": "072",
    "Fire Department": "057",
    "Department of Parks & Recration": "846",
    "Department of Environmental Protection": "826",
    "Department of Buildings": "810",
    "NYC Human Resources Administration": "069",
    "Department of Homeless Services": "071",
    "Administration for Children's Services": "068",
    "Department of Health and Mental Hygiene": "816",
}

SHORT = {
    "040": "Education", "056": "Police", "057": "Fire", "069": "Social Services",
    "071": "Homeless Services", "068": "Children's Services", "072": "Correction",
    "816": "Health and Mental Hygiene", "827": "Sanitation", "826": "Environmental Protection",
    "841": "Transportation", "846": "Parks and Recreation", "856": "Citywide Administrative Services",
    "806": "Housing Preservation and Development", "042": "City University",
    "819": "Health and Hospitals", "858": "Information Technology", "836": "Finance",
    "260": "Youth and Community Development", "125": "Aging", "025": "Law",
    "810": "Buildings", "128": "Criminal Justice", "030": "City Planning",
    "126": "Cultural Affairs", "801": "Small Business Services", "781": "Probation",
    "102": "City Council", "015": "Comptroller", "002": "Mayoralty", "072": "Correction",
}

# Central charges that belong to no agency, grouped so the list reads as
# reasons rather than as budget-code names.
UNALLOC_GROUPS = [
    ("debt", "Debt service", [],
     "Principal and interest on money already borrowed and spent, most of it on schools, "
     "bridges, water mains and vehicles bought in earlier years. It is a bill from past "
     "capital budgets, not from any agency's current operations."),
    ("retiree", "Health care for retired city workers", [],
     "Coverage for people who have stopped working for the city. It was earned in the "
     "agencies of past decades, and the uniformed services generate far more of it per "
     "employee than anyone else, but the budget does not say whose it is."),
    ("reserve", "Reserves and contingency", ["SPECIAL RESERVES", "CAPITAL STABILIZATION RESERVE",
                                             "GENERAL RESERVE"],
     "Money set aside against a bad year and against costs the city can see coming but "
     "has not yet assigned."),
    ("labor", "Collective bargaining reserve", ["PERSONAL SERVICES"],
     "Raises negotiated or expected but not yet written into any agency's payroll line. "
     "When contracts are settled this money moves into the agencies."),
    ("transit", "Transit subsidies", ["TA REDUCED FARE/ELDERLY", "PAYMENTS TO MTA BUS COMPANY",
                                      "MTA PAYROLL TAX", "TA OPERATING ASSISTANCE 18B",
                                      "MTA FOR STATION MAINTENANCE", "PAY TO METRO TRANSPORT AUTHOR"],
     "Payments to the Metropolitan Transportation Authority, which runs the subway and "
     "buses. The city pays; it does not operate."),
    ("school_aid", "State building aid for schools", ["STATE BUILDING AID"],
     "A pass-through tied to school construction debt."),
]


def get(url, **params):
    """Socrata, with retries. A 403 here is throttling, not a permission wall."""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params),
                                        timeout=240) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except OSError:
            # Read timeouts and dropped connections on the wider aggregations.
            time.sleep(3 * (attempt + 1))
            continue
    raise SystemExit("Socrata did not answer after six tries; nothing written.")


def die(msg):
    raise SystemExit("BUILD FAILED: " + msg)


def num(x):
    return float(x or 0)


def ag3(x):
    """Agency numbers lose their leading zero before fiscal 2027 — '40' in one
    year is '040' in the next. Left unpadded, a filter on '095' silently
    matches nothing and a year quietly builds with no pension pool at all."""
    return str(x or "").strip().zfill(3)


def oc2(x):
    """Same for object class numbers: '1' and '01' are the same class."""
    return str(x or "").strip().zfill(2)


# ---------------------------------------------------------- claims split ----

def claims_shares():
    rows = get(CLAIMS, **{
        "$select": "agency,sum(disposition_amount) as amt",
        "$where": f"claim_action='SETTLED' AND disposition_amount>0 "
                  f"AND fiscal_year_fy_>='{CLAIMS_FROM}'",
        "$group": "agency", "$limit": "300"})
    last = get(CLAIMS, **{"$select": "max(fiscal_year_fy_) as y",
                          "$where": "claim_action='SETTLED'"})[0]["y"]
    total = sum(num(r["amt"]) for r in rows)
    if total <= 0:
        die("the claims report returned no settled dollars")
    by_code, unmatched = {}, 0.0
    for r in rows:
        code = CLAIMS_TO_AGENCY.get(r.get("agency") or "")
        if code:
            by_code[code] = by_code.get(code, 0.0) + num(r["amt"])
        else:
            unmatched += num(r["amt"])
    matched = sum(by_code.values())
    if matched / total < 0.85:
        die(f"only {matched/total:.0%} of settlement dollars map to an agency")
    return ({c: v / total for c, v in by_code.items()}, unmatched / total,
            f"fiscal {CLAIMS_FROM} to {last}", matched / total)


# ------------------------------------------------------------- one year ----

def build_year(fy, shares, unmatched_share):
    pubs = get(BUDGET, **{"$select": "publication_date", "$where": f"fiscal_year='{fy}'",
                          "$group": "publication_date", "$order": "publication_date DESC",
                          "$limit": "20"})
    if not pubs:
        die(f"no rows for fiscal year {fy}")
    # OMB republishes a year two or three times as it moves preliminary to
    # executive to adopted, keeping every snapshot. Grouping on fiscal_year
    # alone sums them and overstates the year two or three times over.
    pub = pubs[0]["publication_date"]
    W = f"fiscal_year='{fy}' AND publication_date='{pub}'"

    rows = get(BUDGET, **{"$select": "agency_number,agency_name,sum(adopted_budget_amount) as amt",
                          "$where": W, "$group": "agency_number,agency_name", "$limit": "1000"})
    AG, TOTAL = {}, {}
    for r in rows:
        c = ag3(r["agency_number"])
        AG[c] = r["agency_name"].title()
        TOTAL[c] = TOTAL.get(c, 0.0) + num(r["amt"])
    for c in POOL_AGENCIES:
        if c not in TOTAL:
            die(f"fiscal {fy} has no agency {c}; the agency-number padding is wrong")

    citywide = num(get(BUDGET, **{"$select": "sum(adopted_budget_amount) as amt",
                                  "$where": W})[0]["amt"])
    if abs(sum(TOTAL.values()) - citywide) > 1:
        die(f"fiscal {fy}: agency totals do not sum to the citywide total")

    PAY = {}
    for r in get(BUDGET, **{
            "$select": "agency_number,object_class_number,object_code_name,"
                       "sum(adopted_budget_amount) as amt,sum(adopted_budget_position) as pos",
            "$where": W, "$group": "agency_number,object_class_number,object_code_name",
            "$limit": "50000"}):
        if oc2(r.get("object_class_number")) not in PAY_CLASSES:
            continue
        c = ag3(r["agency_number"])
        k = r.get("object_code_name") or "?"
        a, p = PAY.setdefault(c, {}).get(k, (0.0, 0.0))
        PAY[c][k] = (a + num(r["amt"]), p + num(r.get("pos")))

    OWNFR = {}
    for r in get(BUDGET, **{
            "$select": "agency_number,object_class_number,object_code_name,"
                       "sum(adopted_budget_amount) as amt",
            "$where": W, "$group": "agency_number,object_class_number,object_code_name",
            "$limit": "50000"}):
        if oc2(r.get("object_class_number")) != "06":
            continue
        c = ag3(r["agency_number"])
        k = r.get("object_code_name") or "?"
        OWNFR.setdefault(c, {})[k] = OWNFR.get(c, {}).get(k, 0.0) + num(r["amt"])

    misc_rows = get(BUDGET, **{
        "$select": "unit_appropriation_name,budget_code_number,budget_code_name,"
                   "object_code_name,sum(adopted_budget_amount) as amt",
        "$where": W + " AND agency_number in('098','98')",
        "$group": "unit_appropriation_name,budget_code_number,budget_code_name,object_code_name",
        "$limit": "5000"})
    pension_rows = get(BUDGET, **{
        "$select": "object_code_name,sum(adopted_budget_amount) as amt",
        "$where": W + " AND agency_number in('095','95')",
        "$group": "object_code_name", "$limit": "300"})

    payroll = {c: sum(v[0] for v in d.values()) for c, d in PAY.items()}
    positions = {c: sum(v[1] for v in d.values()) for c, d in PAY.items()}
    own_fringe = {c: sum(d.values()) for c, d in OWNFR.items()}

    # ---- pensions ----
    pension_pot = TOTAL["095"]
    if abs(sum(num(r["amt"]) for r in pension_rows) - pension_pot) > 1:
        die(f"fiscal {fy}: pension object codes do not sum to the pension agency total")

    pension_named, pension_pooled, pension_other = {}, 0.0, {}
    for r in pension_rows:
        name, amt = r.get("object_code_name") or "?", num(r["amt"])
        if name in PENSION_TO_AGENCY:
            pension_named.setdefault(PENSION_TO_AGENCY[name], []).append((name, amt))
        elif name in PENSION_POOLED:
            pension_pooled += amt
        else:
            pension_other[name] = pension_other.get(name, 0.0) + amt
    if not pension_named or pension_pooled <= 0:
        die(f"fiscal {fy}: the pension line names changed; nothing matched")

    nycers_base = {}
    for code in TOTAL:
        if code in POOL_AGENCIES:
            continue
        excl = OWN_FUND_PAY.get(code, [])
        if "*" in excl:
            continue
        base = payroll.get(code, 0.0) - sum(PAY.get(code, {}).get(k, (0, 0))[0] for k in excl)
        if base > 0:
            nycers_base[code] = base
    nb = sum(nycers_base.values())
    if nb <= 0:
        die(f"fiscal {fy}: no payroll left to share the employees' system payment over")

    alloc_pension, pension_note = {}, {}
    for code, lines in pension_named.items():
        alloc_pension[code] = sum(a for _, a in lines)
        pension_note[code] = "; ".join(n.title() for n, _ in lines)
    for code, base in nycers_base.items():
        alloc_pension[code] = alloc_pension.get(code, 0.0) + pension_pooled * base / nb

    # ---- benefits ----
    if abs(sum(num(r["amt"]) for r in misc_rows) - TOTAL["098"]) > 1:
        die(f"fiscal {fy}: miscellaneous detail does not sum to its agency total")

    fringe_head, fringe_pay, retiree_pot, judgments_pot = 0.0, 0.0, 0.0, 0.0
    fringe_lines, other_misc = {}, {}
    for r in misc_rows:
        ua = r.get("unit_appropriation_name") or ""
        obj = r.get("object_code_name") or "?"
        bc = str(r.get("budget_code_number") or "")
        amt = num(r["amt"])
        if ua == "FRINGE BENEFITS":
            if bc == RETIREE_BUDGET_CODE:
                retiree_pot += amt
                fringe_lines["Retiree health benefits trust"] = \
                    fringe_lines.get("Retiree health benefits trust", 0.0) + amt
                continue
            fringe_lines[obj.title()] = fringe_lines.get(obj.title(), 0.0) + amt
            if obj in FRINGE_BY_PAYROLL:
                fringe_pay += amt
            else:
                fringe_head += amt
        elif obj == JUDGMENTS_CODE:
            judgments_pot += amt
        else:
            key = (r.get("budget_code_name") or obj).title()
            other_misc[key] = other_misc.get(key, 0.0) + amt
    if fringe_head <= 0:
        die(f"fiscal {fy}: no fringe benefits found in the miscellaneous agency")

    # An agency already buying its own coverage is not in the pool.
    self_health, self_fica = set(), set()
    for code, lines in OWNFR.items():
        p = positions.get(code, 0.0)
        if p and lines.get("HEALTH INSURANCE PLAN CITY EMP", 0.0) / p > 5000:
            self_health.add(code)
        s = lines.get("SOCIAL SECURITY CONTRIBUTIONS", 0.0)
        if payroll.get(code) and s / payroll[code] > 0.03:
            self_fica.add(code)

    head_base = {c: positions.get(c, 0.0) for c in TOTAL
                 if c not in POOL_AGENCIES and c not in self_health and positions.get(c, 0) > 0}
    pay_base = {c: payroll.get(c, 0.0) for c in TOTAL
                if c not in POOL_AGENCIES and c not in self_fica and payroll.get(c, 0) > 0}
    th, tp = sum(head_base.values()), sum(pay_base.values())
    if th <= 0 or tp <= 0:
        die(f"fiscal {fy}: no headcount or payroll base for the benefits pool")

    alloc_fringe = {}
    for c, v in head_base.items():
        alloc_fringe[c] = alloc_fringe.get(c, 0.0) + fringe_head * v / th
    for c, v in pay_base.items():
        alloc_fringe[c] = alloc_fringe.get(c, 0.0) + fringe_pay * v / tp

    # Compare like with like: payroll taxes are shared on payroll, not on
    # headcount, so they come out of both sides before the rates are compared.
    pool_rate = fringe_head / th
    self_rates = {}
    for c in self_health:
        if positions.get(c):
            head_only = sum(v for k, v in OWNFR[c].items() if k not in FRINGE_BY_PAYROLL)
            self_rates[c] = head_only / positions[c]
    for c, rate in self_rates.items():
        ratio = rate / pool_rate
        if not 0.55 < ratio < 1.75:
            die(f"fiscal {fy}: {AG[c]} buys its own benefits at ${rate:,.0f} a head against a "
                f"pooled ${pool_rate:,.0f} — the headcount model does not hold")

    # ---- judgments ----
    alloc_judg = {c: judgments_pot * s for c, s in shares.items() if c in TOTAL}
    judg_unalloc = judgments_pot - sum(alloc_judg.values())

    # ---- assemble ----
    agencies = []
    for code, name in AG.items():
        if code in POOL_AGENCIES or TOTAL[code] <= 0:
            continue
        named = sum(a for _, a in pension_named.get(code, []))
        add = {"pension": round(alloc_pension.get(code, 0.0)),
               "fringe": round(alloc_fringe.get(code, 0.0)),
               "judgments": round(alloc_judg.get(code, 0.0))}
        agencies.append({
            "code": code, "name": SHORT.get(code, name), "full": name,
            "published": round(TOTAL[code]), "loaded": round(TOTAL[code] + sum(add.values())),
            "add": add, "pension_note": pension_note.get(code, ""),
            # Split the pension figure so the page can say which part is the
            # budget's own line and which part is a share of the pooled payment.
            "pension_named": round(named),
            "pension_shared": round(alloc_pension.get(code, 0.0) - named),
            "own_fringe": round(own_fringe.get(code, 0.0)),
            "payroll": round(payroll.get(code, 0.0)),
            "positions": round(positions.get(code, 0.0)),
            "self_health": code in self_health,
        })
    agencies.sort(key=lambda a: -a["loaded"])

    grouped, used = [], set()
    for key, label, codes, note in UNALLOC_GROUPS:
        if key == "debt":
            amt = TOTAL["099"]
        elif key == "retiree":
            amt = retiree_pot
        else:
            amt = 0.0
            for k in codes:
                for lbl, v in other_misc.items():
                    if lbl.upper() == k:
                        amt += v
                        used.add(lbl)
        if amt > 0:
            grouped.append({"key": key, "label": label, "amount": round(amt), "note": note})
    rest = sum(v for lbl, v in other_misc.items() if lbl not in used)
    rest += sum(pension_other.values()) + judg_unalloc
    if rest > 0:
        grouped.append({"key": "other", "label": "Other central charges", "amount": round(rest),
                        "note": "Tax equivalency payments, obligatory county expenses, pensions "
                                "for bodies outside the city payroll, and claims filed against "
                                "no single agency."})
    grouped.sort(key=lambda u: -u["amount"])

    # ---- checks ----
    if abs(sum(alloc_pension.values()) + sum(pension_other.values()) - pension_pot) > 1:
        die(f"fiscal {fy}: pension allocation does not add back to the pension pot")
    if abs(sum(alloc_fringe.values()) - (fringe_head + fringe_pay)) > 1:
        die(f"fiscal {fy}: benefits allocation does not add back to the benefits pool")
    if abs(sum(alloc_judg.values()) + judg_unalloc - judgments_pot) > 1:
        die(f"fiscal {fy}: judgments allocation does not add back to the judgments line")

    loaded_sum = sum(a["loaded"] for a in agencies)
    unalloc_sum = sum(u["amount"] for u in grouped)
    drift = abs(loaded_sum + unalloc_sum - citywide)
    if drift > len(agencies) + len(grouped) + 5:
        die(f"fiscal {fy}: loaded plus unassigned misses the citywide total by ${drift:,.0f}")

    return {
        "fy": int(fy), "publication_date": pub, "snapshots": len(pubs),
        "total": round(citywide), "positions": round(sum(positions.values())),
        "agencies": agencies, "unallocated": grouped,
        "pools": {
            "pension": {
                "total": round(pension_pot),
                "sourced": round(sum(sum(a for _, a in v) for v in pension_named.values())),
                "shared": round(pension_pooled),
                "unallocated": round(sum(pension_other.values())),
                "lines": {(r.get("object_code_name") or "?").title(): round(num(r["amt"]))
                          for r in pension_rows if num(r["amt"]) > 1e6},
            },
            "fringe": {
                "total": round(fringe_head + fringe_pay + retiree_pot),
                "by_head": round(fringe_head), "by_payroll": round(fringe_pay),
                "retiree": round(retiree_pot),
                "lines": {k: round(v) for k, v in
                          sorted(fringe_lines.items(), key=lambda kv: -kv[1])},
                "per_position": round(pool_rate), "positions_in_base": round(th),
                "self_funded": {AG[c]: round(r) for c, r in sorted(self_rates.items())},
            },
            "judgments": {"total": round(judgments_pot),
                          "allocated": round(judgments_pot - judg_unalloc)},
        },
        "checks": {
            "agency_lines": round(sum(a["published"] for a in agencies)),
            "reallocated": round(sum(sum(a["add"].values()) for a in agencies)),
            "unallocated": round(unalloc_sum),
            "rounding_drift": round(drift),
        },
    }


# ------------------------------------------------------------------ main ----

years = [r["fiscal_year"] for r in get(BUDGET, **{
    "$select": "fiscal_year", "$group": "fiscal_year", "$order": "fiscal_year", "$limit": "60"})]
years = sorted(set(years))
if len(sys.argv) == 3:
    lo, hi = sys.argv[1], sys.argv[2]
    years = [y for y in years if lo <= y <= hi]
elif len(sys.argv) == 2:
    years = [y for y in years if y == sys.argv[1]]
if not years:
    die("no fiscal years selected")

shares, unmatched, claims_years, matched_share = claims_shares()
print(f"claims split from {claims_years}: {matched_share:.1%} of dollars map to an agency")
print(f"building {len(years)} years: {years[0]} to {years[-1]}\n")

built = {}
for y in years:
    r = build_year(y, shares, unmatched)
    built[y] = r
    police = [a for a in r["agencies"] if a["code"] == "056"][0]
    fire = [a for a in r["agencies"] if a["code"] == "057"][0]
    print(f"  FY{y}  snapshot {r['publication_date']}  ${r['total']/1e9:7.2f}B  "
          f"reassigned ${r['checks']['reallocated']/1e9:6.2f}B  "
          f"unassigned ${r['checks']['unallocated']/1e9:6.2f}B  "
          f"police x{police['loaded']/police['published']:.2f}  "
          f"fire x{fire['loaded']/fire['published']:.2f}  "
          f"drift ${r['checks']['rounding_drift']}")

current = years[-1]

# The multiple over time, for agencies present in every year built.
codes = set.intersection(*[{a["code"] for a in built[y]["agencies"]} for y in years])
trend = []
for code in codes:
    series = []
    for y in years:
        a = [x for x in built[y]["agencies"] if x["code"] == code][0]
        series.append(round(a["loaded"] / a["published"], 4) if a["published"] > 0 else None)
    cur = [x for x in built[current]["agencies"] if x["code"] == code][0]
    if cur["published"] < 1e8:
        continue
    trend.append({"code": code, "name": cur["name"], "m": series,
                  "published": cur["published"], "loaded": cur["loaded"]})
trend.sort(key=lambda t: -(t["m"][-1] or 0))

data = {
    "meta": {
        "years": [int(y) for y in years],
        "current": int(current),
        "basis": "Adopted expense budget, newest published snapshot of each fiscal year",
        "claims_years": claims_years,
        "settlement_dollars_matched": round(matched_share, 4),
        "claims_shares": {SHORT.get(c, c): round(v, 4)
                          for c, v in sorted(shares.items(), key=lambda kv: -kv[1])},
        "population": POPULATION,
        "population_note": "Census Bureau vintage 2025 estimate, held flat across the series",
        "sources": [
            "NYC Open Data mwzb-yiwb, Office of Management and Budget expense budget",
            "NYC Open Data ex6k-ym48, comptroller's claims report",
        ],
    },
    "years": {y: built[y] for y in years},
    "trend": trend,
}

with open(OUT, "w") as f:
    json.dump(data, f, separators=(",", ":"))

size = os.path.getsize(OUT)
print(f"\nwrote {OUT}  ({size/1024:.0f} KB)")
cur = built[current]
print(f"\nfiscal {current}, the current adopted budget")
for a in cur["agencies"][:10]:
    print(f"  {a['name'][:34]:34} {a['published']/1e9:7.2f} -> {a['loaded']/1e9:7.2f}  "
          f"x{a['loaded']/a['published']:.2f}")
print("\nbiggest change in the multiple over the series")
movers = sorted(trend, key=lambda t: -((t["m"][-1] or 0) - (t["m"][0] or 0)))
for t in movers[:5] + movers[-3:]:
    print(f"  {t['name'][:34]:34} {t['m'][0]:.2f} -> {t['m'][-1]:.2f}")
