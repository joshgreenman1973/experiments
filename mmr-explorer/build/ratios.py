#!/usr/bin/env python3
"""Build curated subset shares with explicitly reviewed five-year histories.

Each numerator is part of its denominator. Reviewed year bounds are deliberate:
do not extend them automatically without checking definitions and source notes.
The build rejects incomplete, flagged, discontinuous or non-reconciling inputs.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "data"))

RATIOS = [{'id': 'dhs-sub-single',
  'agency': 'DHS',
  'title': 'Subsidized housing as a share of single-adult housing exits',
  'num': {'ind': ['10950']},
  'den': {'ind': ['1832']},
  'scale': 100,
  'unit': '%',
  'question': 'What share of single adults leaving shelter for permanent housing went to subsidized housing?',
  'caveat': 'Both counts require at least 30 days out of shelter and exclude Safe Havens and veterans’ '
            'short-term housing. This describes recorded exits, not whether a subsidy caused or was '
            'necessary for an exit.',
  'kind': 'share',
  'reviewedYears': [2022, 2026],
  'sourceUrl': 'https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf#page=265',
  'historyNote': 'FY2022–2026 uses both components from the same five-year table in the FY2026 report. '
                 'Definitions and chapter change notes were reviewed for this span; earlier years are not '
                 'included.',
  'complementIds': ['10951']},
 {'id': 'dhs-sub-fam',
  'agency': 'DHS',
  'title': 'Subsidized housing as a share of family housing exits',
  'num': {'ind': ['10948']},
  'den': {'ind': ['10947']},
  'scale': 100,
  'unit': '%',
  'question': 'What share of families with children leaving shelter for permanent housing went to subsidized '
              'housing?',
  'caveat': 'Both counts require at least 30 days out of shelter. This describes recorded exits, not whether '
            'a subsidy caused or was necessary for an exit.',
  'kind': 'share',
  'reviewedYears': [2022, 2026],
  'sourceUrl': 'https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf#page=265',
  'historyNote': 'FY2022–2026 uses both components from the same five-year table in the FY2026 report. '
                 'Definitions and chapter change notes were reviewed for this span; earlier years are not '
                 'included.',
  'complementIds': ['10949']},
 {'id': 'nycha-homeless',
  'agency': 'NYCHA',
  'title': 'Homeless applicants’ share of public-housing placements',
  'num': {'ind': ['11072']},
  'den': {'ind': ['3178']},
  'scale': 100,
  'unit': '%',
  'question': 'What share of conventional NYCHA public-housing placements went to homeless applicants?',
  'caveat': 'Both counts cover conventional public-housing placements. Section 8 placements are excluded. '
            'The share describes allocation among placements, not the share of homeless applicants who '
            'obtained housing.',
  'kind': 'share',
  'reviewedYears': [2022, 2026],
  'sourceUrl': 'https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf#page=429',
  'historyNote': 'FY2022–2026 uses both components from the same five-year table in the FY2026 report. '
                 'Definitions and chapter change notes were reviewed for this span; earlier years are not '
                 'included.'},
 {'id': 'oath-default',
  'agency': 'OATH',
  'title': 'Default decisions as a share of OATH decisions',
  'num': {'ind': ['15920']},
  'den': {'ind': ['15918']},
  'scale': 100,
  'unit': '%',
  'question': 'What share of OATH Hearings Division decisions were recorded in its default-decision '
              'category?',
  'caveat': 'The category includes auto-defaults, defaults and guilty decisions after inquest hearings. '
            'These are decisions, not unique people. The share does not establish why someone did not '
            'contest a summons.',
  'kind': 'share',
  'reviewedYears': [2022, 2026],
  'sourceUrl': 'https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf#page=136',
  'historyNote': 'FY2022–2026 uses both components from the same five-year table in the FY2026 report. '
                 'Definitions and chapter change notes were reviewed for this span; earlier years are not '
                 'included.',
  'complementIds': ['15919']},
 {'id': 'tlc-pass',
  'agency': 'TLC',
  'title': 'Taxi inspections passed as a share of inspections conducted',
  'num': {'ind': ['3112']},
  'den': {'ind': ['3111']},
  'scale': 100,
  'unit': '%',
  'question': 'Taxi and Limousine prints inspections conducted and inspections passed. Their ratio shows the '
              'share of inspection events passed, including retests.',
  'caveat': 'Both counts include initial inspections and retests. This is the share of inspection events '
            'passed, not a first-pass rate or the share of unique taxis that are roadworthy. The MMR '
            'separately publishes the initial-inspection failure rate.',
  'kind': 'share',
  'reviewedYears': [2022, 2026],
  'sourceUrl': 'https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf#page=196',
  'historyNote': 'FY2022–2026 uses both components from the same five-year table in the FY2026 report. '
                 'Definitions and chapter change notes were reviewed for this span; earlier years are not '
                 'included.'},
 {'id': 'doc-ot',
  'agency': 'DOC',
  'title': 'Overtime as a share of Correction Department spending',
  'num': {'res': 'ot'},
  'den': {'res': 'exp'},
  'scale': 100,
  'unit': '%',
  'question': 'What share of total agency expenditures went to overtime?',
  'caveat': 'Overtime divided by total agency expenditures, not payroll. Changes can reflect overtime, other '
            'spending, or both; this is not a measure of service quality.',
  'kind': 'share',
  'reviewedYears': [2021, 2025],
  'historyNote': 'FY2021–2025 uses final prior-year actuals from the FY2022–2026 PMMR resource tables. Both '
                 'components retain the same overtime/expenditure scope and monetary units. No FY2026 budget '
                 'plan is used.'},
 {'id': 'nypd-ot',
  'agency': 'NYPD',
  'title': 'Overtime as a share of Police Department spending',
  'num': {'res': 'ot'},
  'den': {'res': 'exp'},
  'scale': 100,
  'unit': '%',
  'question': 'What share of total agency expenditures went to overtime?',
  'caveat': 'Overtime divided by total agency expenditures, not payroll. Changes can reflect overtime, other '
            'spending, or both; this is not a measure of service quality.',
  'kind': 'share',
  'reviewedYears': [2021, 2025],
  'historyNote': 'FY2021–2025 uses final prior-year actuals from the FY2022–2026 PMMR resource tables. Both '
                 'components retain the same overtime/expenditure scope and monetary units. No FY2026 budget '
                 'plan is used.'},
 {'id': 'fdny-ot',
  'agency': 'FDNY',
  'title': 'Overtime as a share of Fire Department spending',
  'num': {'res': 'ot'},
  'den': {'res': 'exp'},
  'scale': 100,
  'unit': '%',
  'question': 'What share of total agency expenditures went to overtime?',
  'caveat': 'Overtime divided by total agency expenditures, not payroll. Changes can reflect overtime, other '
            'spending, or both; this is not a measure of service quality.',
  'kind': 'share',
  'reviewedYears': [2021, 2025],
  'historyNote': 'FY2021–2025 uses final prior-year actuals from the FY2022–2026 PMMR resource tables. Both '
                 'components retain the same overtime/expenditure scope and monetary units. No FY2026 budget '
                 'plan is used.'}]

def main():
    with open(os.path.join(OUT, "indicators.json")) as source:
        site = json.load(source)
    years = site["years"]
    yi = {y: i for i, y in enumerate(years)}
    byid = {r["id"]: r for r in site["ind"]}
    codes = [a["c"] for a in site["agencies"]]
    res = site["res"]
    out, failures = [], []

    for spec in RATIOS:
        reviewed_years = list(range(spec["reviewedYears"][0], spec["reviewedYears"][1] + 1))
        def side(part):
            if "res" in part:
                r = res.get(spec["agency"], {})
                for y in reviewed_years:
                    source = r.get(str(y), {}).get("_sources", {}).get(part["res"], {})
                    if source.get("field") != "previous_fy_actual" or source.get("reportFy") != y + 1:
                        failures.append(f'{spec["id"]}: FY{y} lacks a final prior-year resource actual')
                        return {}
                return {y: (r.get(str(y), {}).get(part["res"]) or 0) * part.get("mult", 1)
                        for y in reviewed_years if r.get(str(y), {}).get(part["res"]) is not None}
            vals = {}
            recs = [byid.get(i) for i in part["ind"]]
            if any(r is None for r in recs):
                failures.append(f'{spec["id"]}: indicator id not found in {part["ind"]}')
                return {}
            for y in reviewed_years:
                if any(str(y) in r.get("sus", {}) or any(reviewed_years[0] < b <= reviewed_years[-1] for b in r.get("breaks", [])) for r in recs):
                    continue
                parts = [r["v"][yi[y]] for r in recs]
                if any(p is None for p in parts):
                    continue
                vals[y] = sum(parts) * part.get("mult", 1)
            return vals

        # Both sides have to be measured over the same kind of period, or the
        # ratio compares a fiscal year against a calendar one and means nothing.
        periods = set()
        unknown_period = False
        for part in (spec["num"], spec["den"]):
            if "res" in part:
                periods.add("Fiscal Year")
            for i in part.get("ind", []):
                r = byid.get(i)
                if r and r["rp"] >= 0:
                    periods.add(site["rp"][r["rp"]])
                else:
                    unknown_period = True
        if unknown_period or len(periods) != 1:
            failures.append(f'{spec["id"]}: components use different reporting periods {sorted(periods)}')
            continue

        n, d = side(spec["num"]), side(spec["den"])
        pts = []
        for y in reviewed_years:
            if y in n and y in d and d[y]:
                pts.append({"y": y, "n": round(n[y], 4), "d": round(d[y], 4),
                            "v": round(n[y] / d[y] * spec["scale"], 4)})
        if len(pts) < 5:
            failures.append(f'{spec["id"]}: only {len(pts)} usable years')
            continue
        # Every retained numerator is a subset of its denominator.
        if spec["kind"] == "share":
            worst = max(p["v"] for p in pts)
            if worst > 100 + 1e-6 or min(p["v"] for p in pts) < 0:
                failures.append(f'{spec["id"]}: reaches {worst:.0f} per 100, which cannot be a share '
                                f'-- check the indicator ids')
                continue
        # And the two sides must cover the same years, not merely overlap.
        span = [p["y"] for p in pts]
        if span != reviewed_years:
            failures.append(f'{spec["id"]}: the usable years have gaps, {span}')
            continue

        if spec.get("complementIds"):
            other = side({"ind": spec["complementIds"]})
            if any(y not in other or abs(n[y] + other[y] - d[y]) > 1e-6 for y in reviewed_years):
                failures.append(f'{spec["id"]}: component categories do not reconcile with the total')
                continue

        def label(part):
            if "res" in part:
                if part["res"] == "pers":
                    return "Personnel (full-time and FTE)"
                name = "Agency expenditures" if part["res"] == "exp" else "Overtime paid"
                return name + (" ($)" if part.get("mult") == 1_000_000 else " ($ millions)")
            text = " plus ".join(byid[i]["n"] for i in part["ind"])
            return text + (f" × {part['mult']:,}" if part.get("mult", 1) != 1 else "")

        out.append({
            "id": spec["id"], "agency": spec["agency"], "title": spec["title"],
            "kind": spec["kind"], "reviewedYears": spec["reviewedYears"],
            "historyNote": spec["historyNote"],
            "sourceUrl": spec.get("sourceUrl"),
            "resourceComponents": [p["res"] for p in (spec["num"], spec["den"]) if "res" in p],
            "unit": spec["unit"], "money": spec.get("money", False),
            "question": spec["question"], "caveat": spec["caveat"],
            "numLabel": label(spec["num"]), "denLabel": label(spec["den"]),
            "numIds": spec["num"].get("ind", []), "denIds": spec["den"].get("ind", []),
            "period": (sorted(periods)[0] if periods else "Fiscal Year"),
            "years": f'fiscal {pts[0]["y"]} to {pts[-1]["y"]}',
            "pts": pts,
        })
        first, last = pts[0], pts[-1]
        print(f'  {spec["agency"]:6s} {spec["title"][:58]:60s} FY{first["y"]} {first["v"]:,.1f} '
              f'-> FY{last["y"]} {last["v"]:,.1f}')

    if failures:
        print("\nFAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)

    with open(os.path.join(OUT, "ratios.json"), "w") as target:
        json.dump({"ratios": out}, target, separators=(",", ":"))
    print(f'\n{len(out)} ratios written to data/ratios.json')


if __name__ == "__main__":
    main()
