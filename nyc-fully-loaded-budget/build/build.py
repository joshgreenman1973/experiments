#!/usr/bin/env python3
"""Build data.json for "The fully loaded budget".

Takes New York City's adopted expense budget, which parks pensions, fringe
benefits and judgments in three central agencies, and pushes that money back
onto the agencies whose employees and operations incur it.

Everything here reconciles to the budget's own printed totals. Any mismatch
above one dollar fails the build rather than warning.

    python3 build/build.py [fiscal_year]     # default 2027
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

FY = sys.argv[1] if len(sys.argv) > 1 else "2027"
CLAIMS_FROM = "2021"          # first claims year used for the judgments split
# Census Bureau vintage 2025 estimate for New York City, the same denominator
# used in the New York City ledger. Held flat for budget years the Bureau has
# not yet reached.
POPULATION = 8584629

# Central agencies that hold pooled money rather than run anything.
POOL_AGENCIES = {"095": "pension", "098": "miscellaneous", "099": "debt service"}

# Pension object codes, straight from the budget's own line names. Each named
# fund maps to the agency whose workforce belongs to it; the contingent
# reserve fund is the city's NYCERS payment and covers everyone else.
PENSION_TO_AGENCY = {
    "TEACH RET SYS CONTINGNT RES SY": "040",
    "TEACH RET SYS PENS FND RES #2": "040",
    "BOARD OF EDUCATION RETIRE. SYS": "040",
    "POLICE ACTUARIAL PENSION FUND": "056",
    "FIRE ACTUARIAL PENSION FUND": "057",
}
PENSION_POOLED = {"CONTINGENT RESERVE FUND", "ADDITIONAL PENSION ACCRUAL"}

# Payroll object codes. Uniformed and pedagogical staff belong to their own
# pension funds, so their pay is taken out of the base that shares NYCERS.
PAY_CLASSES = ("01", "02", "03", "04")
OWN_FUND_PAY = {
    "056": ["FULL TIME UNIFORMED PERSONNEL"],
    "057": ["FULL TIME UNIFORMED PERSONNEL"],
    "040": ["*"],                                  # all of it: TRS and BERS
}

RETIREE_BUDGET_CODE = "3006"                       # Retiree Health Benefits Trust
FRINGE_BY_PAYROLL = {"SOCIAL SECURITY CONTRIBUTIONS"}
JUDGMENTS_CODE = "JUDGEMENTS AND CLAIMS"

# Claims-report agency strings to budget agency codes. Anything unmatched is
# left in the unallocated pile rather than spread around.
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
}


def get(url, **params):
    """Socrata, with retries. A 403 here is throttling, not a permission wall."""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=120) as r:
                return json.loads(r.read())
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            code = getattr(e, "code", None)
            if code in (403, 429, 500, 502, 503) or code is None:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise SystemExit("Socrata did not answer after six tries; nothing written.")


def die(msg):
    raise SystemExit("BUILD FAILED: " + msg)


def num(x):
    return float(x or 0)


# ---------------------------------------------------------------- fetch ----

pubs = get(BUDGET, **{"$select": "publication_date", "$where": f"fiscal_year='{FY}'",
                      "$group": "publication_date", "$order": "publication_date DESC",
                      "$limit": "20"})
if not pubs:
    die(f"no rows for fiscal year {FY}")
PUB = pubs[0]["publication_date"]
W = f"fiscal_year='{FY}' AND publication_date='{PUB}'"
print(f"fiscal {FY}, snapshot {PUB} ({len(pubs)} published this year)")

agency_total = get(BUDGET, **{
    "$select": "agency_number,agency_name,sum(adopted_budget_amount) as amt",
    "$where": W, "$group": "agency_number,agency_name", "$limit": "1000"})
AG = {r["agency_number"]: r["agency_name"].title() for r in agency_total}
TOTAL = {r["agency_number"]: num(r["amt"]) for r in agency_total}

citywide = num(get(BUDGET, **{"$select": "sum(adopted_budget_amount) as amt", "$where": W})[0]["amt"])
if abs(sum(TOTAL.values()) - citywide) > 1:
    die(f"agency totals {sum(TOTAL.values()):,.0f} do not sum to citywide {citywide:,.0f}")

pay_rows = get(BUDGET, **{
    "$select": "agency_number,object_code_name,sum(adopted_budget_amount) as amt,"
               "sum(adopted_budget_position) as pos",
    "$where": W + " AND object_class_number in('%s')" % "','".join(PAY_CLASSES),
    "$group": "agency_number,object_code_name", "$limit": "5000"})
PAY = {}
for r in pay_rows:
    PAY.setdefault(r["agency_number"], {})[r.get("object_code_name") or "?"] = (num(r["amt"]), num(r.get("pos")))

own_fringe_rows = get(BUDGET, **{
    "$select": "agency_number,object_code_name,sum(adopted_budget_amount) as amt",
    "$where": W + " AND object_class_number='06'", "$group": "agency_number,object_code_name",
    "$limit": "2000"})
OWNFR = {}
for r in own_fringe_rows:
    OWNFR.setdefault(r["agency_number"], {})[r.get("object_code_name") or "?"] = num(r["amt"])

misc_rows = get(BUDGET, **{
    "$select": "unit_appropriation_name,budget_code_number,budget_code_name,object_code_name,"
               "sum(adopted_budget_amount) as amt",
    "$where": W + " AND agency_number='098'",
    "$group": "unit_appropriation_name,budget_code_number,budget_code_name,object_code_name",
    "$limit": "2000"})
pension_rows = get(BUDGET, **{
    "$select": "object_code_name,sum(adopted_budget_amount) as amt",
    "$where": W + " AND agency_number='095'", "$group": "object_code_name", "$limit": "200"})

claims_rows = get(CLAIMS, **{
    "$select": "agency,sum(disposition_amount) as amt",
    "$where": f"claim_action='SETTLED' AND disposition_amount>0 AND fiscal_year_fy_>='{CLAIMS_FROM}'",
    "$group": "agency", "$limit": "200"})
claims_last = get(CLAIMS, **{"$select": "max(fiscal_year_fy_) as y",
                             "$where": "claim_action='SETTLED'"})[0]["y"]

# --------------------------------------------------------------- shape -----

payroll = {c: sum(v[0] for v in d.values()) for c, d in PAY.items()}
positions = {c: sum(v[1] for v in d.values()) for c, d in PAY.items()}
own_fringe = {c: sum(d.values()) for c, d in OWNFR.items()}

# ---- pension pool -----------------------------------------------------
pension_pot = TOTAL["095"]
if abs(sum(num(r["amt"]) for r in pension_rows) - pension_pot) > 1:
    die("pension object codes do not sum to the pension agency total")

pension_named, pension_pooled, pension_other = {}, 0.0, {}
for r in pension_rows:
    name, amt = r.get("object_code_name") or "?", num(r["amt"])
    if name in PENSION_TO_AGENCY:
        pension_named.setdefault(PENSION_TO_AGENCY[name], []).append((name, amt))
    elif name in PENSION_POOLED:
        pension_pooled += amt
    else:
        pension_other[name] = pension_other.get(name, 0.0) + amt

# Base for the NYCERS share: payroll not already covered by a named fund.
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
    die("no payroll left to share the NYCERS contribution over")

alloc_pension, pension_note = {}, {}
for code, lines in pension_named.items():
    alloc_pension[code] = sum(a for _, a in lines)
    pension_note[code] = "; ".join(n.title() for n, _ in lines)
for code, base in nycers_base.items():
    share = pension_pooled * base / nb
    alloc_pension[code] = alloc_pension.get(code, 0.0) + share

# ---- fringe pool ------------------------------------------------------
misc_total = TOTAL["098"]
if abs(sum(num(r["amt"]) for r in misc_rows) - misc_total) > 1:
    die("miscellaneous detail does not sum to the miscellaneous agency total")

fringe_head, fringe_pay, retiree_pot, judgments_pot = 0.0, 0.0, 0.0, 0.0
fringe_lines, other_misc = {}, {}
for r in misc_rows:
    ua = r.get("unit_appropriation_name") or ""
    obj = r.get("object_code_name") or "?"
    bc = r.get("budget_code_number") or ""
    amt = num(r["amt"])
    if ua == "FRINGE BENEFITS":
        if bc == RETIREE_BUDGET_CODE:
            retiree_pot += amt
            fringe_lines["Retiree health benefits trust"] = fringe_lines.get("Retiree health benefits trust", 0) + amt
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

# An agency that already buys its own health insurance is not in the pool.
self_health, self_fica = set(), set()
for code, lines in OWNFR.items():
    p = positions.get(code, 0.0)
    h = lines.get("HEALTH INSURANCE PLAN CITY EMP", 0.0)
    if p and h / p > 5000:
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
    die("no headcount or payroll base for the fringe pool")

alloc_fringe = {}
for c, v in head_base.items():
    alloc_fringe[c] = alloc_fringe.get(c, 0.0) + fringe_head * v / th
for c, v in pay_base.items():
    alloc_fringe[c] = alloc_fringe.get(c, 0.0) + fringe_pay * v / tp

# Validation: the pooled rate per head against agencies that buy their own.
# Compare like with like — payroll taxes are shared on payroll, not headcount,
# so they come out of both sides before the rates are compared.
pool_rate = fringe_head / th
self_rates = {}
for c in self_health:
    if not positions.get(c):
        continue
    head_only = sum(v for k, v in OWNFR[c].items() if k not in FRINGE_BY_PAYROLL)
    self_rates[c] = head_only / positions[c]

# ---- judgments pool ---------------------------------------------------
claims_total = sum(num(r["amt"]) for r in claims_rows)
claims_by_code, claims_unmatched = {}, 0.0
for r in claims_rows:
    code = CLAIMS_TO_AGENCY.get(r.get("agency") or "")
    if code and code in TOTAL:
        claims_by_code[code] = claims_by_code.get(code, 0.0) + num(r["amt"])
    else:
        claims_unmatched += num(r["amt"])
matched = sum(claims_by_code.values())
if matched / claims_total < 0.85:
    die(f"only {matched/claims_total:.0%} of settlement dollars map to an agency")
alloc_judg = {c: judgments_pot * v / claims_total for c, v in claims_by_code.items()}
judg_unalloc = judgments_pot * claims_unmatched / claims_total

# --------------------------------------------------------------- assemble --

agencies = []
for code, name in AG.items():
    if code in POOL_AGENCIES:
        continue
    pub = TOTAL[code]
    if pub <= 0:
        continue
    add = {
        "pension": round(alloc_pension.get(code, 0.0)),
        "fringe": round(alloc_fringe.get(code, 0.0)),
        "judgments": round(alloc_judg.get(code, 0.0)),
    }
    loaded = pub + sum(add.values())
    agencies.append({
        "code": code,
        "name": SHORT.get(code, name),
        "full": name,
        "published": round(pub),
        "loaded": round(loaded),
        "add": add,
        "pension_note": pension_note.get(code, ""),
        "own_fringe": round(own_fringe.get(code, 0.0)),
        "payroll": round(payroll.get(code, 0.0)),
        "positions": round(positions.get(code, 0.0)),
        "self_health": code in self_health,
    })
agencies.sort(key=lambda a: -a["loaded"])

# The central charges that no agency can be billed for, grouped so the list
# reads as reasons rather than as budget-code names.
UNALLOC_GROUPS = [
    ("debt", "Debt service", [],
     "Principal and interest on money already borrowed and spent, most of it on "
     "schools, bridges, water mains and vehicles bought in earlier years. It is a "
     "bill from past capital budgets, not from any agency's current operations."),
    ("retiree", "Health care for retired city workers", [],
     "Coverage for people who have stopped working for the city. It was earned in "
     "the agencies of past decades, and the uniformed services generate far more of "
     "it per employee than anyone else, but the budget does not say whose it is."),
    ("reserve", "Reserves and contingency", ["SPECIAL RESERVES", "CAPITAL STABILIZATION RESERVE"],
     "Money set aside against a bad year and against costs the city can see coming "
     "but has not yet assigned."),
    ("labor", "Collective bargaining reserve", ["PERSONAL SERVICES"],
     "Raises negotiated or expected but not yet written into any agency's payroll "
     "line. When contracts are settled this money moves into the agencies."),
    ("transit", "Transit subsidies", ["TA REDUCED FARE/ELDERLY", "PAYMENTS TO MTA BUS COMPANY",
                                      "MTA PAYROLL TAX", "TA OPERATING ASSISTANCE 18B",
                                      "MTA FOR STATION MAINTENANCE", "PAY TO METRO TRANSPORT AUTHOR"],
     "Payments to the Metropolitan Transportation Authority, which runs the subway "
     "and buses. The city pays; it does not operate."),
    ("school_aid", "State building aid for schools", ["STATE BUILDING AID"],
     "A pass-through tied to school construction debt."),
]

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
                    "note": "Tax equivalency payments, obligatory county expenses, pensions for "
                            "cultural institutions outside the city payroll, and claims filed "
                            "against no single agency."})
unallocated = grouped

# ------------------------------------------------------------------ checks --

checks = {}
alloc_sum = sum(a["add"]["pension"] + a["add"]["fringe"] + a["add"]["judgments"] for a in agencies)
pool_sum = round(sum(alloc_pension.values())) + round(sum(alloc_fringe.values())) + round(sum(alloc_judg.values()))
loaded_sum = sum(a["loaded"] for a in agencies)
unalloc_sum = sum(u["amount"] for u in unallocated)

if abs(sum(alloc_pension.values()) + sum(pension_other.values()) - pension_pot) > 1:
    die("pension allocation does not add back to the pension pot")
if abs(sum(alloc_fringe.values()) + retiree_pot - (fringe_head + fringe_pay + retiree_pot)) > 1:
    die("fringe allocation does not add back to the fringe pool")
if abs(sum(alloc_judg.values()) + judg_unalloc - judgments_pot) > 1:
    die("judgments allocation does not add back to the judgments line")

drift = abs(loaded_sum + unalloc_sum - citywide)
if drift > len(agencies) + len(unallocated) + 5:
    die(f"loaded {loaded_sum:,.0f} plus unallocated {unalloc_sum:,.0f} misses the "
        f"citywide total {citywide:,.0f} by {drift:,.0f}")

for c, rate in self_rates.items():
    ratio = rate / pool_rate
    if not 0.65 < ratio < 1.55:
        die(f"agency {c} buys its own benefits at ${rate:,.0f} a head against a pooled "
            f"${pool_rate:,.0f} — the headcount model does not hold")

checks = {
    "citywide": round(citywide),
    "agency_lines": round(sum(a["published"] for a in agencies)),
    "reallocated": round(alloc_sum),
    "unallocated": round(unalloc_sum),
    "rounding_drift": round(drift),
    "pooled_fringe_per_position": round(pool_rate),
    "self_funded_per_position": {AG[c]: round(r) for c, r in sorted(self_rates.items())},
    "settlement_dollars_matched": round(matched / claims_total, 4),
}

data = {
    "meta": {
        "fiscal_year": int(FY),
        "publication_date": PUB,
        "basis": f"Adopted expense budget for fiscal {FY}, published {PUB[:4]}-{PUB[4:6]}-{PUB[6:]}",
        "claims_years": f"fiscal {CLAIMS_FROM} to {claims_last}",
        "total": round(citywide),
        "positions": round(sum(positions.values())),
        "population": POPULATION,
        "population_note": "Census Bureau vintage 2025 estimate, held flat for the budget year",
        "sources": [
            "NYC Open Data mwzb-yiwb, Office of Management and Budget expense budget",
            "NYC Open Data ex6k-ym48, Comptroller's claims report",
        ],
    },
    "pools": {
        "pension": {
            "total": round(pension_pot),
            "sourced": round(sum(sum(a for _, a in v) for v in pension_named.values())),
            "shared": round(pension_pooled),
            "unallocated": round(sum(pension_other.values())),
            "lines": {k.title(): round(v) for k, v in
                      sorted(((r.get("object_code_name") or "?", num(r["amt"])) for r in pension_rows),
                             key=lambda kv: -kv[1]) if v > 1e6},
        },
        "fringe": {
            "total": round(fringe_head + fringe_pay + retiree_pot),
            "by_head": round(fringe_head),
            "by_payroll": round(fringe_pay),
            "retiree": round(retiree_pot),
            "lines": {k: round(v) for k, v in sorted(fringe_lines.items(), key=lambda kv: -kv[1])},
            "per_position": round(pool_rate),
            "positions_in_base": round(th),
        },
        "judgments": {
            "total": round(judgments_pot),
            "allocated": round(judgments_pot - judg_unalloc),
            "shares": {SHORT.get(c, AG.get(c, c)): round(v / claims_total, 4)
                       for c, v in sorted(claims_by_code.items(), key=lambda kv: -kv[1])},
        },
    },
    "agencies": agencies,
    "unallocated": sorted(unallocated, key=lambda u: -u["amount"]),
    "checks": checks,
}

with open(OUT, "w") as f:
    json.dump(data, f, separators=(",", ":"), sort_keys=False)

print(f"citywide           ${citywide/1e9:9.3f}B")
print(f"agency lines       ${sum(a['published'] for a in agencies)/1e9:9.3f}B")
print(f"reallocated        ${alloc_sum/1e9:9.3f}B  (pension, fringe, judgments)")
print(f"unallocated        ${unalloc_sum/1e9:9.3f}B")
print(f"pooled fringe      ${pool_rate:9,.0f} per position, over {th:,.0f} positions")
for c, r in self_rates.items():
    print(f"  cross-check      ${r:9,.0f} per position at {AG[c]} (buys its own)")
print(f"drift              ${drift:,.0f}")
print(f"\nwrote {OUT}")
for a in agencies[:12]:
    print(f"  {a['name'][:34]:34} {a['published']/1e9:7.2f} -> {a['loaded']/1e9:7.2f}  "
          f"x{a['loaded']/a['published']:.2f}")
