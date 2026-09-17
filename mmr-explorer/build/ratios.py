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
    # ---- shelter --------------------------------------------------------
    {
        "id": "dhs-single", "agency": "DHS",
        "title": "Single adults leaving shelter for a home, per 100 arriving",
        "num": {"ind": ["1832"]}, "den": {"ind": ["1807"]}, "scale": 100, "unit": "per 100",
        "question": "The report counts how many single adults enter the shelter system and, separately, "
                    "how many leave it for permanent housing. It never puts the two side by side.",
        "caveat": "The people leaving in a year are not the people who arrived in it, so this is a "
                  "comparison of two flows over the same fiscal year, not the share of any group that "
                  "got housed. The entry count also excludes Safe Havens, veterans' short-term "
                  "housing, and anyone returning within a year of a previous stay.",
    },
    {
        "id": "dhs-families", "agency": "DHS",
        "title": "Families with children leaving shelter for a home, per 100 arriving",
        "num": {"ind": ["10947"]}, "den": {"ind": ["4398"]}, "scale": 100, "unit": "per 100",
        "question": "The same comparison for families with children, the population the shelter system "
                    "grew fastest in.",
        "caveat": "Two flows over the same fiscal year, not a cohort. The entry figure counts families "
                  "found eligible for shelter, which is not the same as families who applied.",
    },
    {
        "id": "dhs-adultfam", "agency": "DHS",
        "title": "Adult families leaving shelter for a home, per 100 arriving",
        "num": {"ind": ["10944"]}, "den": {"ind": ["4397"]}, "scale": 100, "unit": "per 100",
        "question": "The smallest of the three shelter populations, and the one least written about.",
        "caveat": "Two flows over the same fiscal year, not a cohort. Small counts, so single-year "
                  "moves are noisy.",
    },
    {
        "id": "dhs-sub-single", "agency": "DHS",
        "title": "Single-adult exits that needed a housing subsidy, per 100 exits",
        "num": {"ind": ["10950"]}, "den": {"ind": ["1832"]}, "scale": 100, "unit": "per 100",
        "question": "Every exit from shelter to permanent housing is filed as either subsidised or "
                    "unsubsidised. The split is printed; the share is not. It says how much of the "
                    "city's rehousing now depends on a voucher.",
        "caveat": "A subsidised exit is not a worse outcome than an unsubsidised one. This measures "
                  "what the exits rest on, not how good they are. Numerator and denominator are the "
                  "same flow over the same fiscal year, so the share is exact.",
    },
    {
        "id": "dhs-sub-fam", "agency": "DHS",
        "title": "Family exits that needed a housing subsidy, per 100 exits",
        "num": {"ind": ["10948"]}, "den": {"ind": ["10947"]}, "scale": 100, "unit": "per 100",
        "question": "The same split for families with children.",
        "caveat": "A subsidised exit is not a worse outcome than an unsubsidised one. Same flow, same "
                  "fiscal year, so the share is exact.",
    },
    # ---- what things cost ----------------------------------------------
    {
        "id": "doc-cost", "agency": "DOC",
        "title": "Correction Department spending per person in custody",
        "num": {"res": "exp", "mult": 1_000_000}, "den": {"ind": ["2381"]},
        "scale": 1, "unit": "$ a year", "money": True,
        "question": "The report prints what the Department of Correction spends and, in another table, "
                    "the average number of people it holds. The cost of a jail bed is the single most "
                    "quoted number about Rikers and the report never states it.",
        "caveat": "A year of spending divided by the average number held on a day in that year. It is "
                  "the Correction Department's own operating expenditure only: it leaves out fringe "
                  "benefits, debt service, the health care Health + Hospitals delivers in the jails, "
                  "and legal settlements, all of which sit in other agencies' budgets. Fully loaded "
                  "estimates published by the Comptroller are far higher. Dollars are as published and "
                  "not adjusted for inflation.",
    },
    {
        "id": "dsny-cost", "agency": "DSNY",
        "title": "Sanitation Department spending per ton of waste handled",
        "num": {"res": "exp", "mult": 1_000_000},
        "den": {"ind": ["1593", "1384"], "mult": 1000}, "scale": 1, "unit": "$ a ton", "money": True,
        "question": "The city published a refuse collection cost per ton until fiscal 2020 and then "
                    "stopped. This is the nearest thing the current report still lets you build.",
        "caveat": "Not the cost of collecting a ton. The Sanitation Department's budget also covers "
                  "street cleaning, snow, lot cleaning and enforcement, so this is total agency "
                  "spending for a fiscal year divided by everything it disposed of or recycled in that "
                  "same year. It is a different, larger number than the collection cost the city used "
                  "to print, and the two should not be compared. Dollars are as published.",
    },
    {
        "id": "dsny-tons", "agency": "DSNY",
        "title": "Tons of waste handled per Sanitation Department employee",
        "num": {"ind": ["1593", "1384"], "mult": 1000}, "den": {"res": "pers"},
        "scale": 1, "unit": "tons a year",
        "question": "Tonnage and headcount are both printed, in different tables, and never divided.",
        "caveat": "A crude measure. Most Sanitation employees are not on a collection truck, and "
                  "tonnage moves with what the city throws away rather than with how hard anyone "
                  "works. Headcount is the fiscal year's reported personnel, uniformed and civilian "
                  "together, against the same year's tonnage.",
    },
    {
        "id": "doc-ot", "agency": "DOC",
        "title": "Overtime as a share of Correction Department spending",
        "num": {"res": "ot"}, "den": {"res": "exp"}, "scale": 100, "unit": "per 100 dollars",
        "question": "Both figures sit in the agency resources table, one row apart. The share is the "
                    "number that says how much of a jail system runs on overtime.",
        "caveat": "Overtime paid and total expenditures, both for the same fiscal year, both as "
                  "published in the report's own resources table. It is a share of all agency "
                  "spending, not of the payroll, so the payroll share is higher still.",
    },
    {
        "id": "nypd-ot", "agency": "NYPD",
        "title": "Overtime as a share of Police Department spending",
        "num": {"res": "ot"}, "den": {"res": "exp"}, "scale": 100, "unit": "per 100 dollars",
        "question": "The same question for the city's largest uniformed agency.",
        "caveat": "Overtime paid and total expenditures for the same fiscal year, as published. A "
                  "share of all agency spending, not of the payroll.",
    },
    {
        "id": "fdny-ot", "agency": "FDNY",
        "title": "Overtime as a share of Fire Department spending",
        "num": {"res": "ot"}, "den": {"res": "exp"}, "scale": 100, "unit": "per 100 dollars",
        "question": "And for the Fire Department, which runs the ambulances too.",
        "caveat": "Overtime paid and total expenditures for the same fiscal year, as published. A "
                  "share of all agency spending, not of the payroll.",
    },
    # ---- does the city follow through -----------------------------------
    {
        "id": "dob-response-b", "agency": "DOB",
        "title": "Nonemergency building complaints responded to, per 100 received",
        "num": {"ind": ["5509"]}, "den": {"ind": ["5507"]}, "scale": 100, "unit": "per 100",
        "question": "The Buildings Department prints how many nonemergency complaints it takes in and "
                    "how many it goes out to, on the same page, without the share.",
        "caveat": "Responding means an inspector made an initial field visit, not that anyone got "
                  "inside or that anything was resolved. Both counts cover the same fiscal year but "
                  "do not follow the same complaints, so a backlog worked off later lands in a later "
                  "year's numerator.",
    },
    {
        "id": "dob-response-a", "agency": "DOB",
        "title": "Emergency building complaints responded to, per 100 received",
        "num": {"ind": ["5508"]}, "den": {"ind": ["5506"]}, "scale": 100, "unit": "per 100",
        "question": "The same sum for the complaints the department treats as emergencies, which is "
                    "the comparison that makes the nonemergency figure mean something.",
        "caveat": "Same fiscal year on both sides, and the same caution: responding means a field "
                  "visit was made, not that the hazard was fixed.",
    },
    {
        "id": "dsny-graffiti", "agency": "DSNY",
        "title": "Graffiti requests closed, per 100 received",
        "num": {"ind": ["15182"]}, "den": {"ind": ["15181"]}, "scale": 100, "unit": "per 100",
        "allow_over": True,
        "question": "Received and closed are both printed. The share is not.",
        "caveat": "Both counts are for the same fiscal year but not the same requests, so a figure "
                  "near or above 100 means the agency cleared roughly as many as came in, not that "
                  "every request was handled.",
    },
    {
        "id": "hpd-violations", "agency": "HPD",
        "title": "Housing violations closed, per 100 issued",
        "num": {"ind": ["2684"]}, "den": {"ind": ["2664"]}, "scale": 100, "unit": "per 100",
        "allow_over": True,
        "question": "Housing Preservation and Development issues hundreds of thousands of violations a "
                    "year and closes a comparable number. Whether it is keeping up is not printed.",
        "caveat": "Closures in a fiscal year against violations issued in that same year, and they are "
                  "not the same violations. Above 100 means the agency closed more than it issued that "
                  "year, which means it worked into a backlog; below 100 means the backlog grew. It "
                  "does not mean any particular violation was fixed.",
    },
    # ---- who gets through ------------------------------------------------
    {
        "id": "ccrb-sub", "agency": "CCRB",
        "title": "Complaints against officers substantiated, per 100 cases closed",
        "num": {"ind": ["15057"]}, "den": {"ind": ["9166"]}, "scale": 100, "unit": "per 100",
        "question": "The Civilian Complaint Review Board publishes how many cases it closes and, "
                    "separately, how many it closes as substantiated. The substantiation rate that "
                    "follows is the number everyone argues about, and it is not printed.",
        "caveat": "Both are closures in the same fiscal year, but the board counts complaints and "
                  "cases in slightly different units: the nine published closure categories sum to "
                  "within about one and a half per cent of the total cases closed, not exactly to it. "
                  "Read this as close to the substantiation rate rather than as it.",
    },
    {
        "id": "nypd-arrests", "agency": "NYPD",
        "title": "Major felony arrests per 100 major felonies reported",
        "num": {"ind": ["10201"]}, "den": {"ind": ["3943"]}, "scale": 100, "unit": "per 100",
        "question": "Both figures are printed in the police chapter, a few rows apart, and never divided.",
        "caveat": "Not a clearance rate and not a solve rate. Both counts cover the same fiscal year "
                  "but not the same crimes: an arrest made this year may be for a crime reported in an "
                  "earlier one, a single crime can produce several arrests or none, and an arrest is "
                  "not a conviction. One further wrinkle: the printed report restated the major felony "
                  "count for fiscal 2022 to 2025 by about a fifth of a per cent, so the years to 2025 "
                  "use the open data figures and fiscal 2026 uses the report's.",
    },
    {
        "id": "nycha-homeless", "agency": "NYCHA",
        "title": "Public housing placements that went to homeless applicants, per 100",
        "num": {"ind": ["11072"]}, "den": {"ind": ["3178"]}, "scale": 100, "unit": "per 100",
        "question": "The Housing Authority prints how many applicants it places and, separately, how "
                    "many of those came from the shelter system. The share is the rationing decision.",
        "caveat": "Same flow, same fiscal year, so the share is exact. It says how placements were "
                  "allocated, not whether there were enough of them.",
    },
    {
        "id": "tlc-pass", "agency": "TLC",
        "title": "Medallion taxi inspections passed, per 100 conducted",
        "num": {"ind": ["3112"]}, "den": {"ind": ["3111"]}, "scale": 100, "unit": "per 100",
        "question": "Taxi and Limousine prints inspections conducted and inspections passed. The pass "
                    "rate is the number that says what condition the fleet is in.",
        "caveat": "Same inspections, same fiscal year, so the rate is exact. A failed inspection is "
                  "usually re-presented after repair, so this is a first-pass rate rather than the "
                  "share of cabs that end up roadworthy.",
    },
    # ---- what the city gets for it ---------------------------------------
    {
        "id": "bpl-circ", "agency": "BPL",
        "title": "Items borrowed per active Brooklyn library card",
        "num": {"ind": ["2291"]}, "den": {"ind": ["10287"]}, "scale": 1, "unit": "items a year",
        "question": "Circulation and active cards are both printed, both in thousands. How much the "
                    "average active borrower actually borrows is not.",
        "caveat": "Read the level, not the trend. Both figures cover the same fiscal year, but the "
                  "active-card count moves in a way no borrowing pattern explains -- Brooklyn reports "
                  "846,000 active cards in fiscal 2021 and 494,000 in fiscal 2022 -- which means the "
                  "definition has been changed more than once. Comparing the three library systems "
                  "against each other in the same year is sound; reading the line as a change in how "
                  "much people borrow is not. An active card is also a card, not a person, and "
                  "circulation includes renewals and e-book loans.",
    },
    {
        "id": "nypl-circ", "agency": "NYPL",
        "title": "Items borrowed per active New York Public Library card",
        "num": {"ind": ["3062"]}, "den": {"ind": ["10291"]}, "scale": 1, "unit": "items a year",
        "question": "The same sum for the system covering Manhattan, the Bronx and Staten Island.",
        "caveat": "Read the level, not the trend: the active-card count is redefined more than once "
                  "across this run, which is why the line moves more than borrowing does. The New "
                  "York Public Library reports 522,000 active cards in fiscal 2021 and 1,327,000 in "
                  "fiscal 2024. Comparing the three systems in the same year is sound.",
    },
    {
        "id": "qpl-circ", "agency": "QPL",
        "title": "Items borrowed per active Queens library card",
        "num": {"ind": ["3259"]}, "den": {"ind": ["10295"]}, "scale": 1, "unit": "items a year",
        "question": "And for Queens, which lets the three systems be read against one another.",
        "caveat": "Read the level, not the trend, for the same reason as the other two systems: the "
                  "active-card count is redefined more than once across this run. Comparing Queens, "
                  "Brooklyn and the New York Public Library in the same year is the sound use of it.",
    },
    {
        "id": "dot-potholes", "agency": "DOT",
        "title": "Potholes repaired per pothole work order",
        "num": {"ind": ["2902", "2915"]}, "den": {"ind": ["2900"]}, "scale": 1, "unit": "per order",
        "question": "Transportation prints how many pothole work orders it opens and, separately, how "
                    "many potholes it fills on local streets and on the arterial system. One order "
                    "clearly covers more than one hole, and the report never says how many.",
        "caveat": "Repairs and orders are both counted over the same fiscal year but are not tied to "
                  "one another in the data: a crew sent to one order may fill holes nobody reported. "
                  "Read it as filling intensity, not as a productivity rate.",
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

        # Both sides have to be measured over the same kind of period, or the
        # ratio compares a fiscal year against a calendar one and means nothing.
        periods = set()
        for part in (spec["num"], spec["den"]):
            for i in part.get("ind", []):
                r = byid.get(i)
                if r and r["rp"] >= 0:
                    periods.add(site["rp"][r["rp"]])
        if len(periods) > 1:
            failures.append(f'{spec["id"]}: components use different reporting periods {sorted(periods)}')
            continue

        n, d = side(spec["num"]), side(spec["den"])
        pts = []
        for y in years:
            if y in n and y in d and d[y]:
                pts.append({"y": y, "n": round(n[y], 4), "d": round(d[y], 4),
                            "v": round(n[y] / d[y] * spec["scale"], 4)})
        if len(pts) < 5:
            failures.append(f'{spec["id"]}: only {len(pts)} usable years')
            continue
        # A share of a universe cannot sit far outside that universe. Where it
        # legitimately can -- closures against a backlog -- the entry says so.
        if spec["scale"] == 100 and not spec.get("allow_over"):
            worst = max(p["v"] for p in pts)
            if worst > 150:
                failures.append(f'{spec["id"]}: reaches {worst:.0f} per 100, which cannot be a share '
                                f'-- check the indicator ids')
                continue
        # And the two sides must cover the same years, not merely overlap.
        span = [p["y"] for p in pts]
        if span != list(range(span[0], span[-1] + 1)):
            failures.append(f'{spec["id"]}: the usable years have gaps, {span}')
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

    json.dump({"ratios": out}, open(os.path.join(OUT, "ratios.json"), "w"), separators=(",", ":"))
    print(f'\n{len(out)} ratios written to data/ratios.json')


if __name__ == "__main__":
    main()
