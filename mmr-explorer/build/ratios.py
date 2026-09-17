#!/usr/bin/env python3
"""Ratios the city has the numbers for but does not publish.

Every one of these is two figures the Mayor's Management Report already
prints, divided. None of them is mined automatically: a machine looking for
pairs whose ratio stays under 1 will happily propose sewer miles over
satisfaction surveys returned. Each pair here was chosen because the two
indicators genuinely share a denominator universe, and each was checked
against the city's own description of both before it was included.

Each entry carries the question it answers and, just as important, the thing
it cannot be read as. The site shows both components beside the ratio so the
arithmetic is always visible.

Writes data/ratios.json.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "data"))

RATIOS = [
    {
        "id": "dhs-single",
        "agency": "DHS",
        "title": "Single adults leaving shelter for a home, per 100 arriving",
        "num": {"ind": ["1832"]}, "den": {"ind": ["1807"]},
        "scale": 100, "unit": "per 100",
        "question": "The report counts how many single adults enter the shelter system and, separately, "
                    "how many leave it for permanent housing. It never puts the two side by side.",
        "caveat": "The people leaving in a year are not the people who arrived in it, so this is a "
                  "comparison of two flows, not the share of any group that got housed. The entry "
                  "count also excludes Safe Havens, veterans' short-term housing, and anyone "
                  "returning within a year of a previous stay.",
    },
    {
        "id": "dhs-families",
        "agency": "DHS",
        "title": "Families with children leaving shelter for a home, per 100 arriving",
        "num": {"ind": ["10947"]}, "den": {"ind": ["4398"]},
        "scale": 100, "unit": "per 100",
        "question": "The same comparison for families with children, the population the shelter "
                    "system grew fastest in.",
        "caveat": "Two flows, not a cohort. The entry figure counts families found eligible for "
                  "shelter, which is not the same as families who applied.",
    },
    {
        "id": "dhs-adultfam",
        "agency": "DHS",
        "title": "Adult families leaving shelter for a home, per 100 arriving",
        "num": {"ind": ["10944"]}, "den": {"ind": ["4397"]},
        "scale": 100, "unit": "per 100",
        "question": "The smallest of the three shelter populations, and the one least written about.",
        "caveat": "Two flows, not a cohort. Small counts, so single-year moves are noisy.",
    },
    {
        "id": "doc-cost",
        "agency": "DOC",
        "title": "Correction Department spending per person in custody",
        "num": {"res": "exp", "mult": 1_000_000}, "den": {"ind": ["2381"]},
        "scale": 1, "unit": "$ a year", "money": True,
        "question": "The report prints what the Department of Correction spends and, in another "
                    "table, the average number of people it holds. The cost of a jail bed is the "
                    "single most quoted number about Rikers and the report never states it.",
        "caveat": "This is the Correction Department's own operating expenditure only. It leaves out "
                  "fringe benefits, debt service, the health care Health + Hospitals delivers in the "
                  "jails, and legal settlements, all of which sit in other agencies' budgets. "
                  "Fully loaded estimates published by the Comptroller are far higher. Dollars are "
                  "as published and not adjusted for inflation.",
    },
    {
        "id": "dsny-cost",
        "agency": "DSNY",
        "title": "Sanitation Department spending per ton of waste handled",
        "num": {"res": "exp", "mult": 1_000_000},
        "den": {"ind": ["1593", "1384"], "mult": 1000},
        "scale": 1, "unit": "$ a ton", "money": True,
        "question": "The city published a refuse collection cost per ton until fiscal 2020 and then "
                    "stopped. This is the nearest thing the current report still lets you build.",
        "caveat": "Not the cost of collecting a ton. The Sanitation Department's budget also covers "
                  "street cleaning, snow, lot cleaning and enforcement, so this is total agency "
                  "spending divided by everything it disposed of or recycled. It is a different, "
                  "larger number than the collection cost the city used to print, and the two "
                  "should not be compared. Dollars are as published.",
    },
    {
        "id": "ccrb-sub",
        "agency": "CCRB",
        "title": "Complaints against officers substantiated, per 100 cases closed",
        "num": {"ind": ["15057"]}, "den": {"ind": ["9166"]},
        "scale": 100, "unit": "per 100",
        "question": "The Civilian Complaint Review Board publishes how many cases it closes and, "
                    "separately, how many it closes as substantiated. The substantiation rate that "
                    "follows is the number everyone argues about, and it is not printed.",
        "caveat": "The board counts complaints and cases in slightly different units: the nine "
                  "published closure categories sum to within about one and a half per cent of the "
                  "total cases closed, not exactly to it. Read this as close to the substantiation "
                  "rate rather than as it.",
    },
    {
        "id": "nypd-arrests",
        "agency": "NYPD",
        "title": "Major felony arrests per 100 major felonies reported",
        "num": {"ind": ["10201"]}, "den": {"ind": ["3943"]},
        "scale": 100, "unit": "per 100",
        "question": "Both figures are printed in the police chapter, a few rows apart, and never "
                    "divided.",
        "caveat": "Not a clearance rate and not a solve rate. An arrest made this year may be for a "
                  "crime reported in an earlier one, a single crime can produce several arrests or "
                  "none, and an arrest is not a conviction. Read it as arrest activity relative to "
                  "reported crime, nothing more. One further wrinkle: the printed report restated "
                  "the major felony count for fiscal 2022 to 2025, by about a fifth of a per cent. "
                  "The years up to 2025 here use the open data figures and fiscal 2026 uses the "
                  "report's, which is a smaller inconsistency than the rounding but is worth knowing.",
    },
    {
        "id": "dob-response",
        "agency": "DOB",
        "title": "Nonemergency building complaints responded to, per 100 received",
        "num": {"ind": ["5509"]}, "den": {"ind": ["5507"]},
        "scale": 100, "unit": "per 100",
        "question": "The Buildings Department prints how many nonemergency complaints it takes in and "
                    "how many it goes out to, on the same page, without the share.",
        "caveat": "Responding means an inspector made an initial field visit, not that anyone got "
                  "inside or that anything was resolved. The two counts also cover the same period "
                  "rather than following the same complaints, so a backlog worked off in a later "
                  "year lands in that year's numerator.",
    },
]


def main():
    site = json.load(open(os.path.join(OUT, "indicators.json")))
    years = site["years"]
    yi = {y: i for i, y in enumerate(years)}
    byid = {r["id"]: r for r in site["ind"]}
    codes = [a["c"] for a in site["agencies"]]
    res = site["res"]
    out, failures = [], []

    for spec in RATIOS:
        def side(part):
            if "res" in part:
                r = res.get(spec["agency"], {})
                return {y: (r.get(str(y), {}).get(part["res"]) or 0) * part.get("mult", 1)
                        for y in years if r.get(str(y), {}).get(part["res"]) is not None}
            vals = {}
            recs = [byid.get(i) for i in part["ind"]]
            if any(r is None for r in recs):
                failures.append(f'{spec["id"]}: indicator id not found in {part["ind"]}')
                return {}
            for y in years:
                parts = [r["v"][yi[y]] for r in recs]
                if any(p is None for p in parts):
                    continue
                vals[y] = sum(parts) * part.get("mult", 1)
            return vals

        n, d = side(spec["num"]), side(spec["den"])
        pts = []
        for y in years:
            if y in n and y in d and d[y]:
                pts.append({"y": y, "n": round(n[y], 4), "d": round(d[y], 4),
                            "v": round(n[y] / d[y] * spec["scale"], 4)})
        if len(pts) < 5:
            failures.append(f'{spec["id"]}: only {len(pts)} usable years')
            continue

        def label(part):
            if "res" in part:
                return "Agency expenditures, as reported in the report's own resources table"
            return " plus ".join(byid[i]["n"] for i in part["ind"])

        out.append({
            "id": spec["id"], "agency": spec["agency"], "title": spec["title"],
            "unit": spec["unit"], "money": spec.get("money", False),
            "question": spec["question"], "caveat": spec["caveat"],
            "numLabel": label(spec["num"]), "denLabel": label(spec["den"]),
            "numIds": spec["num"].get("ind", []), "denIds": spec["den"].get("ind", []),
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

    json.dump({"ratios": out}, open(os.path.join(OUT, "ratios.json"), "w"), separators=(",", ":"))
    print(f'\n{len(out)} ratios written to data/ratios.json')


if __name__ == "__main__":
    main()
