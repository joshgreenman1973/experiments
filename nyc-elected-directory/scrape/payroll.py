#!/usr/bin/env python3
"""Who works for each state legislator, from the Legislature's own payroll records.

Two official records tie staff to a member's office by name and job title:

  * the Assembly's semiannual Expenditure Report (CSV), which lists every employee
    under the member's own unit, and
  * the Senate's biweekly Payroll Report (CSV), which prints the employing office
    beside each name.

This reads both and writes data/payroll_staff.json: for every New York City
legislator in data/base.json, the people on that office's payroll in the latest
period who hold a chief-of-staff, communications or other senior title.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scrape"))
from build_base import name_tokens, same_person  # noqa: E402

RAW = os.path.join(ROOT, "raw", "payroll")
DATA = os.path.join(ROOT, "data")

ASSEMBLY = dict(
    file="assembly_20260331.csv",
    url="https://nyassembly.gov/write/upload/expenditure/20260331.csv",
    page="https://nyassembly.gov/expenditure/",
    name="Assembly Expenditure Report, Oct. 1, 2025 to March 31, 2026",
    through="March 11, 2026", last_period_end="03/11/26",
)
SENATE = dict(
    file="senate_payroll_20261104.csv",
    url="https://www.nysenate.gov/sites/default/files/open-data/PRPRESS21_20260411_0.csv",
    page="https://www.nysenate.gov/open-data/payroll-report-end-date-110426",
    name="Senate Payroll Report, pay period Oct. 22 to Nov. 4, 2026",
    through="Nov. 4, 2026",
)

SMALL = {"of", "and", "for", "the", "to", "in", "on"}
FIX_TITLE = {"Director Communications": "Director of communications", "Director Public Affairs": "Director of public affairs",
             "Director Constituent/support Services": "Director of constituent services"}


def person(n):
    """'ARACENA VELEZ, IGNACIO J' -> 'Ignacio J. Aracena Velez'"""
    last, _, first = n.partition(",")

    def cap(w):
        w = w.lower()
        w = re.sub(r"(^|[\-' ])([a-z])", lambda m: m.group(1) + m.group(2).upper(), w)
        w = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), w)
        return w
    first = " ".join((cap(w) + "." if len(w) == 1 else cap(w)) for w in first.split())
    first = re.sub(r"\b(Jr|Sr)$", r"\1.", first)
    return f"{first} {cap(last.strip())}".strip()


def title(t, limit=0):
    t = t.strip()
    if limit and len(t) >= limit:
        # the record cuts long titles off mid-word; drop the fragment
        t = re.sub(r"\s+\S*$", "", t)
        t = re.sub(r"(\s+(&|AND|FOR|OF|TO|THE))+$", "", t)
    t = re.sub(r"\bLEG DIR\b", "LEGISLATIVE DIRECTOR", t)
    words = t.lower().split()
    out = " ".join(w if (i and w in SMALL) else w for i, w in enumerate(words))
    out = out[:1].upper() + out[1:]
    out = re.sub(r"\bchf\b", "chief", out)
    out = FIX_TITLE.get(out.title() if out.title() in FIX_TITLE else out, out)
    for k, v in FIX_TITLE.items():
        if out.lower() == k.lower():
            out = v
    return out


def rank(t):
    t = t.lower()
    if re.match(r"chief of staff", t):
        return 0
    if re.search(r"communicat|press|media|public affairs|public relations|spokes", t):
        return 1
    if re.search(r"deputy chief of staff", t):
        return 2
    if re.search(r"district (office )?director|office director|executive director|director of operations", t):
        return 3
    if re.search(r"legislative director|counsel|senior advis|policy director|schedul", t):
        return 4
    return 9


def pick(rows):
    """Chief of staff, communications titles and deputy chief; if neither a chief nor a
    communications title exists, the most senior other staff, so no office comes back empty."""
    rows = sorted(rows, key=lambda r: (rank(r["title"]), -r.get("pay", 0)))
    top = [r for r in rows if rank(r["title"]) <= 2]
    if not any(rank(r["title"]) <= 1 for r in top):
        top += [r for r in rows if 3 <= rank(r["title"]) <= 4][:2]
    if not top:
        top = rows[:1]
    return top[:5]


def main():
    base = json.load(open(os.path.join(DATA, "base.json")))["people"]
    out = dict(assembly={}, senate={}, sources=dict(assembly=ASSEMBLY, senate=SENATE), former={})

    # ---- Assembly
    rows = list(csv.reader(open(os.path.join(RAW, ASSEMBLY["file"]), encoding="utf-8-sig", errors="ignore")))
    rows = [[c.strip() for c in r] for r in rows[2:] if len(r) >= 9 and r[1].strip() == "PERSSERV"]
    units = {}
    for r in rows:
        units.setdefault(r[0], []).append(r)
    members = [p for p in base if p["section"] == "State Assembly" and p["status"] == "sitting"]
    for m in members:
        cands = [u for u in units if "," in u and same_person(m["name"], person(u.rstrip(".")))
                 and name_tokens(person(u.rstrip(".")))[0][:3] == name_tokens(m["name"])[0][:3]]
        if len(cands) != 1:
            # fall back on the surname alone when it is unique among units
            sur = name_tokens(m["name"])[-1]
            cands = [u for u in units if "," in u and name_tokens(u.split(",")[0])[-1:] == [sur]] if len(cands) == 0 else cands
        if len(cands) != 1:
            print(f"  ! Assembly unit not matched for {m['name']}: {cands}")
            continue
        active, gone = [], []
        for r in units[cands[0]]:
            if r[6] in ("MEMBER OF ASSEMBLY", "LUMP SUM VACATION PAYMENT") or "-" not in r[5]:
                continue
            rec = dict(name=person(r[4]), printed=r[4], title=title(r[6], 40), dates=r[5], pay=float(r[8] or 0))
            (active if r[5].split("-")[-1] == ASSEMBLY["last_period_end"] else gone).append(rec)
        if m["name"].startswith("Carl E. Heastie"):
            # the speaker's own staff sit in two central units that name him in their titles
            for u in ("SPEAKER OF THE ASSEMBLY", "PRESS OPERATIONS"):
                for r in units.get(u, []):
                    if "-" in r[5] and r[5].split("-")[-1] == ASSEMBLY["last_period_end"] and re.search(
                            r"^CHIEF OF STAFF$|PRESS SECRETARY TO THE SPEAKER|^DIRECTOR COMMUNICATIONS$|^DEPUTY PRESS SECRETARY$", r[6]):
                        active.append(dict(name=person(r[4]), printed=r[4], title=title(r[6]) + (", speaker’s office" if u.startswith("SPEAKER") and "speaker" not in r[6].lower() else ""),
                                           dates=r[5], pay=float(r[8] or 0)))
        out["assembly"][str(m["district"])] = dict(member=m["name"], unit=cands[0], staff=pick(active), all=[a["name"] for a in active])
        out["former"][m["id"]] = [dict(name=g["name"], title=g["title"], ended=g["dates"].split("-")[-1]) for g in gone]

    # ---- Senate
    srows = list(csv.DictReader(open(os.path.join(RAW, SENATE["file"]), encoding="utf-8-sig", errors="ignore")))
    offices = {}
    for r in srows:
        offices.setdefault(r["OFFICE"].strip(), []).append(r)
    # The payroll uses two senators' formal names; their districts settle who they are.
    FORMAL = {"Liz Krueger": "SENATOR ELIZABETH KRUEGER", "Gustavo Rivera": "SENATOR JOSE G. RIVERA"}
    for m in [p for p in base if p["section"] == "State Senate" and p["status"] == "sitting"]:
        cands = [o for o in offices if o.startswith("SENATOR ") and same_person(m["name"], person_from_office(o))
                 and name_tokens(person_from_office(o))[0][:3] == name_tokens(m["name"])[0][:3]]
        if not cands and m["name"] in FORMAL and FORMAL[m["name"]] in offices:
            cands = [FORMAL[m["name"]]]
        if len(cands) != 1:
            print(f"  ! Senate office not matched for {m['name']}: {cands}")
            continue
        recs = [dict(name=person(r["EMPLOYEE_NAME"]), printed=r["EMPLOYEE_NAME"], title=title(r["EMPLOYEE_TITLE"], 35),
                     city=r["CITY"].title(), pay=float(r["BIWEEKLY/HOURLY_RATE"] or 0)) for r in offices[cands[0]]]
        out["senate"][str(m["district"])] = dict(member=m["name"], unit=cands[0], staff=pick(recs), all=[a["name"] for a in recs])

    json.dump(out, open(os.path.join(DATA, "payroll_staff.json"), "w"), indent=1, ensure_ascii=False)
    for ch in ("assembly", "senate"):
        d = out[ch]
        cos = sum(1 for v in d.values() if any(rank(s["title"]) == 0 for s in v["staff"]))
        com = sum(1 for v in d.values() if any(rank(s["title"]) == 1 for s in v["staff"]))
        print(f"  {ch}: {len(d)} offices matched; {cos} with a chief of staff; {com} with a communications title")


def person_from_office(o):
    # "SENATOR KEVIN S. PARKER" -> "Kevin S. Parker"
    return " ".join(w.capitalize() if not re.search(r"[.']", w) else w.title() for w in o.replace("SENATOR ", "").split())


if __name__ == "__main__":
    main()
