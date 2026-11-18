"""Score random New York City households with PolicyEngine US, under current law
and several reforms, and write the cases for check_engine.mjs to compare with
engine.js.  Usage: python check_engine.py OUT.json [N]"""
import json, sys, random
import numpy as np
from policyengine_us import Simulation
from policyengine_core.reforms import Reform

Y = 2026
N = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
random.seed(7)
FOREVER = "2026-01-01.2100-12-31"

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
}

def rand_household():
    married = random.random() < 0.5
    k = [random.choice([0, 0, 0, 1, 2]), random.choice([0, 0, 1, 1, 2, 3]), random.choice([0, 0, 0, 0, 1])]
    r = random.random()
    if r < 0.45: wages = random.uniform(0, 120_000)
    elif r < 0.75: wages = random.uniform(120_000, 600_000)
    elif r < 0.95: wages = 10 ** random.uniform(5.7, 7.0)
    else: wages = 10 ** random.uniform(7.0, 7.7)
    return {"married": married, "wages": round(wages), "kidsUnder4": k[0], "kids4to16": k[1], "kids17to18": k[2]}

def situation(hs):
    S = {"people": {}, "tax_units": {}, "families": {}, "spm_units": {}, "marital_units": {}, "households": {}}
    for i, h in enumerate(hs):
        members = []
        adults = 2 if h["married"] else 1
        for a in range(adults):
            pid = f"h{i}a{a}"; members.append(pid)
            S["people"][pid] = {"age": {Y: 38}, "employment_income": {Y: h["wages"] / adults}}
        ages = [2] * h["kidsUnder4"] + [10] * h["kids4to16"] + [17] * h["kids17to18"]
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
for w in [0, 1, 107_650, 157_650, 161_550, 215_400, 1_077_550, 1_008_000, 1_016_050, 2_155_350, 5_000_000, 25_000_000, 25_000_004, 30_000_000]:
    for married in (False, True):
        hs.append({"married": married, "wages": w, "kidsUnder4": 1, "kids4to16": 1, "kids17to18": 0})
        hs.append({"married": married, "wages": w, "kidsUnder4": 0, "kids4to16": 0, "kids17to18": 0})

out = {"households": hs, "reforms": {k: v for k, v in REFORMS.items()}, "results": {}}
for name, ref in REFORMS.items():
    reform = Reform.from_dict({k: {FOREVER: v} for k, v in ref.items()}, country_id="us") if ref else None
    res = {v: [] for v in VARS}
    for b in range(0, len(hs), 400):
        sim = Simulation(situation=situation(hs[b:b+400]), reform=reform)
        for v in VARS:
            res[v] += [round(float(x), 2) for x in sim.calculate(v, Y)]
    out["results"][name] = res
    print(name, "done", file=sys.stderr)
json.dump(out, open(sys.argv[1], "w"))
