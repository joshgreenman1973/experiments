"""Score random New York City households with PolicyEngine US, under current law
and several reforms, and write the cases for check_engine.mjs to compare with
engine.js.  Usage: python check_engine.py OUT.json [N] [scenario,scenario,...]"""
import json, sys, random
import numpy as np
from policyengine_us import Simulation
from policyengine_core.reforms import Reform

Y = 2026
N = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
random.seed(7)
FOREVER = "2026-01-01.2100-12-31"
INF = float("inf")

REFORMS = {
    "baseline": None,
    "mamdani": {"gov.local.ny.mamdani_income_tax.in_effect": True},
    "mamdani_3pct_500k": {"gov.local.ny.mamdani_income_tax.in_effect": True,
                          "gov.local.ny.mamdani_income_tax.rate[1].rate": 0.03,
                          "gov.local.ny.mamdani_income_tax.rate[1].threshold": 500_000},
    "escc_bigger": {"gov.states.ny.tax.income.credits.ctc.post_2024.amount[0].amount": 1500,
                    "gov.states.ny.tax.income.credits.ctc.post_2024.amount[1].amount": 1000,
                    "gov.states.ny.tax.income.credits.ctc.post_2024.phase_out.threshold.JOINT": 150_000,
                    "gov.states.ny.tax.income.credits.ctc.post_2024.phase_out.threshold.HEAD_OF_HOUSEHOLD": 100_000,
                    "gov.states.ny.tax.income.credits.ctc.post_2024.phase_out.threshold.SINGLE": 100_000},
    "ny_eitc_45": {"gov.states.ny.tax.income.credits.eitc.match": 0.45},
    "nyc_eitc_30": {f"gov.local.ny.nyc.tax.income.credits.eitc.percent[{i}].amount": 0.30 for i in range(5)},
    "no_elimination": {"gov.local.ny.nyc.tax.income.credits.income_tax_elimination.in_effect": False},
    # The Empire State Child Credit's 2028 reversion to the pre-2025 formula.
    "escc_lapse": {"gov.states.ny.tax.income.credits.ctc.post_2024.in_effect": False},
    # S9077 amounts (2029 and 2030 steps), with eligibility through age 17.
    "s9077_2029": {"gov.states.ny.tax.income.credits.ctc.post_2024.amount[0].amount": 1500,
                   "gov.states.ny.tax.income.credits.ctc.post_2024.amount[1].amount": 1250,
                   "gov.states.ny.tax.income.credits.ctc.post_2024.amount[2].threshold": 18},
    "s9077_2030": {"gov.states.ny.tax.income.credits.ctc.post_2024.amount[0].amount": 1500,
                   "gov.states.ny.tax.income.credits.ctc.post_2024.amount[1].amount": 1500,
                   "gov.states.ny.tax.income.credits.ctc.post_2024.amount[2].threshold": 18},
    # PolicyEngine's own reforms for New York bills.
    "wftc_2026": {"gov.contrib.states.ny.wftc.in_effect": True},
    "wftc_full": {"gov.contrib.states.ny.wftc.in_effect": True, "gov.contrib.states.ny.wftc.amount.max": 1600,
                  "gov.contrib.states.ny.wftc.amount.min": 100, "gov.contrib.states.ny.wftc.child_age_threshold": 17,
                  "gov.contrib.states.ny.wftc.eitc.match": 0, "gov.contrib.states.ny.wftc.exemptions.in_effect": True,
                  "gov.contrib.states.ny.wftc.reduction.single[1].threshold": 25_000,
                  "gov.contrib.states.ny.wftc.reduction.married[1].threshold": 50_000},
    "s9110_2026": {"gov.contrib.states.ny.s9110.in_effect": True},
    "s9110_2035": {"gov.contrib.states.ny.s9110.in_effect": True,
                   **{f"gov.contrib.states.ny.s9110.rates.{st}[1].threshold": t for st, t in [("single", 50_000), ("joint", 100_000), ("head_of_household", 75_000)]},
                   **{f"gov.contrib.states.ny.s9110.rates.{st}[3].rate": 0.0882 for st in ["single", "joint", "head_of_household"]},
                   **{f"gov.contrib.states.ny.s9110.rates.{st}[{i}].threshold": INF for st in ["single", "joint", "head_of_household"] for i in (4, 5)}},
    "a04038": {"gov.contrib.states.ny.a04038.in_effect": True},
    "a04038_s9077": {"gov.contrib.states.ny.a04038.in_effect": True,
                     "gov.states.ny.tax.income.credits.ctc.post_2024.amount[0].amount": 1500,
                     "gov.states.ny.tax.income.credits.ctc.post_2024.amount[1].amount": 1250,
                     "gov.states.ny.tax.income.credits.ctc.post_2024.amount[2].threshold": 18},
    "s04487": {"gov.contrib.states.ny.s04487.in_effect": True},
    "stc_phase_out": {"gov.contrib.local.nyc.stc.phase_out.in_effect": True},
    "stc_phase_out_2pct": {"gov.contrib.local.nyc.stc.phase_out.in_effect": True,
                           "gov.contrib.local.nyc.stc.phase_out.rate.joint_and_surviving_spouse[1].rate": 0.02,
                           "gov.contrib.local.nyc.stc.phase_out.rate.other[1].rate": 0.02},
}

def rand_household():
    married = random.random() < 0.5
    k = [random.choice([0, 0, 0, 0, 1]), random.choice([0, 0, 0, 1, 2]), random.choice([0, 0, 1, 1, 2, 3]), random.choice([0, 0, 0, 0, 1])]
    r = random.random()
    if r < 0.45: wages = random.uniform(0, 120_000)
    elif r < 0.75: wages = random.uniform(120_000, 600_000)
    elif r < 0.95: wages = 10 ** random.uniform(5.7, 7.0)
    else: wages = 10 ** random.uniform(7.0, 7.7)
    return {"married": married, "wages": round(wages), "kidsUnder1": k[0], "kids1to3": k[1], "kids4to16": k[2], "kids17": k[3]}

def situation(hs):
    S = {"people": {}, "tax_units": {}, "families": {}, "spm_units": {}, "marital_units": {}, "households": {}}
    for i, h in enumerate(hs):
        members = []
        adults = 2 if h["married"] else 1
        for a in range(adults):
            pid = f"h{i}a{a}"; members.append(pid)
            S["people"][pid] = {"age": {Y: 38}, "employment_income": {Y: h["wages"] / adults}}
        # Children under 1 are 0; 1 to 3 are 2 (PolicyEngine's newborn credit
        # also counts 1-year-olds, which the page does not; see engine.js).
        ages = [0] * h["kidsUnder1"] + [2] * h["kids1to3"] + [10] * h["kids4to16"] + [17] * h["kids17"]
        for c, age in enumerate(ages):
            pid = f"h{i}c{c}"; members.append(pid)
            S["people"][pid] = {"age": {Y: age}}
        S["tax_units"][f"t{i}"] = {"members": members}
        S["families"][f"f{i}"] = {"members": members}
        S["spm_units"][f"s{i}"] = {"members": members}
        S["households"][f"h{i}"] = {"members": members, "state_code": {Y: "NY"}, "county_str": {Y: "KINGS_COUNTY_NY"}}
        if h["married"]:
            S["marital_units"][f"m{i}"] = {"members": [f"h{i}a0", f"h{i}a1"]}
        else:
            S["marital_units"][f"m{i}"] = {"members": [f"h{i}a0"]}
    return S

VARS = ["eitc", "ny_taxable_income", "ny_main_income_tax", "ny_supplemental_tax", "ny_household_credit", "ny_eitc", "ny_ctc",
        "ny_income_tax", "nyc_income_tax_before_credits", "nyc_household_credit", "nyc_eitc", "nyc_school_tax_credit",
        "nyc_income_tax_elimination_credit", "nyc_income_tax"]

hs = [rand_household() for _ in range(N)]
# Add edge cases at bracket and phase-out boundaries.
for w in [0, 1, 25_000, 50_000, 75_000, 75_999, 107_650, 150_000, 150_500, 157_650, 161_550, 215_400, 1_077_550, 1_008_000, 1_016_050, 2_155_350, 5_000_000, 25_000_000, 25_000_004, 30_000_000]:
    for married in (False, True):
        hs.append({"married": married, "wages": w, "kidsUnder1": 0, "kids1to3": 1, "kids4to16": 1, "kids17": 0})
        hs.append({"married": married, "wages": w, "kidsUnder1": 1, "kids1to3": 0, "kids4to16": 0, "kids17": 1})
        hs.append({"married": married, "wages": w, "kidsUnder1": 0, "kids1to3": 0, "kids4to16": 0, "kids17": 0})

# JSON has no infinity; check_engine.mjs reads "inf" as the engine does.
out = {"households": hs, "reforms": {k: ({p: ("inf" if v == INF else v) for p, v in r.items()} if r else r) for k, r in REFORMS.items()}, "results": {}}
# Optional third argument: a comma-separated list of scenarios to run (so runs
# can be split across processes and merged).
ONLY = sys.argv[3].split(",") if len(sys.argv) > 3 else list(REFORMS)
out["reforms"] = {k: v for k, v in out["reforms"].items() if k in ONLY}
for name, ref in REFORMS.items():
    if name not in ONLY: continue
    reform = Reform.from_dict({k: {FOREVER: v} for k, v in ref.items()}, country_id="us") if ref else None
    res = {v: [] for v in VARS}
    for b in range(0, len(hs), 400):
        # start_instant: PolicyEngine decides which structural reforms (the
        # contrib bill reforms) to build from parameter values on this date.
        sim = Simulation(situation=situation(hs[b:b+400]), reform=reform, start_instant=f"{Y}-01-01")
        for v in VARS:
            res[v] += [round(float(x), 2) for x in sim.calculate(v, Y)]
    out["results"][name] = res
    print(name, "done", file=sys.stderr)
json.dump(out, open(sys.argv[1], "w"))
