#!/usr/bin/env python3
"""Build the Mamdani administration organizational chart.

Reads the verified roster from ../mamdani-appointee-tracker/data.json and writes a
single self-contained index.html. Nothing here retypes a name: every person, title,
date and source link is pulled from that file, so the chart cannot drift from the
tracker. The only thing this script adds is the reporting structure - which column
each person sits in - and that mapping is below, in COLUMNS.
"""

import json
import html
import re
from pathlib import Path

HERE = Path(__file__).parent
# The roster lives in the sibling tracker project. A snapshot of exactly what was
# used is written to data/roster.json on every build, so this repo can rebuild the
# page on its own if the tracker is not checked out beside it.
_LIVE = HERE.parent / "mamdani-appointee-tracker" / "data.json"
_SNAP = HERE / "data" / "roster.json"
ROSTER = json.loads((_LIVE if _LIVE.exists() else _SNAP).read_text())
PEOPLE = {p["name"]: p for p in ROSTER["appointees"]}

# ---------------------------------------------------------------------------
# Reporting structure. Each column is a principal who reports to the mayor.
# Entries are (person, short label for the box). A label of None reuses the
# person's agency from the roster.
# ---------------------------------------------------------------------------
COLUMNS = [
    ("Dean Fuleihan", "First deputy mayor", [
        ("Sherif Soliman", "Management and Budget"),
        ("Richard Lee", "Finance"),
        ("Edwin Raymond", "Sheriff"),
        ("Peter White", "Deed Theft Prevention"),
        ("Ahmer Qadeer", "Pensions and Investments"),
        ("Renee Campion", "Labor Relations"),
        ("Kamar Samuels", "Education"),
        ("Celeste Ramirez", "School Construction Authority"),
        ("Stanley Richards", "Correction"),
        ("Sharun Goodwin", "Probation"),
        ("Justine Olderman", "Criminal justice coordinator"),
        ("Deanna Logan", "Criminal Justice"),
        ("Dana Kaplan", "Close Rikers"),
        ("Bharti Sharma", "Innovation through Data Intelligence"),
        ("Asim Rehman", "Business Integrity Commission"),
        ("Elizabeth Adams", "Fast and free buses"),
        ("Bitta Mostofi", "Strategic coordination"),
    ]),
    ("Leila Bozorg", "Deputy mayor for housing and planning", [
        ("Lisa Bova-Hiatt", "Housing Authority"),
        ("Dina Levy", "Housing Preservation and Development"),
        ("Eric Enderlin", "Housing Development Corporation"),
        ("Sideya Sherman", "City Planning"),
        ("Edith Hsu-Chen", "City Planning"),
        ("Ahmed Tigani", "Buildings"),
        ("Cea Weaver", "Office to Protect Tenants"),
        ("Lisa Kersavage", "Landmarks Preservation Commission"),
        ("John Mangin", "Standards and Appeals"),
        ("Erich Bilal", "Public Design Commission"),
    ]),
    ("Julia Kerson", "Deputy mayor for operations", [
        ("Lisa Garcia", "Environmental Protection"),
        ("Gregory Anderson", "Sanitation"),
        ("Javier Lojan", "Sanitation"),
        ("Mike Flynn", "Transportation"),
        ("Tricia Shimamura", "Parks and Recreation"),
        ("Paul Ochoa", "Design and Construction"),
        ("Yume Kitasei", "Citywide Administrative Services"),
        ("Kim L. Yu", "Contract Services"),
        ("Lillian Bonsignore", "Fire Department"),
        ("Christina Farrell", "Emergency Management"),
        ("Lisa Gelobter", "Technology and Innovation"),
        ("Annie Levers", "Mayor's Office of Operations"),
        ("Shawn(ta) Smith-Cruz", "Records and Information Services"),
        ("Annie Elisa Minguez", "Nonprofit Services"),
        ("Louise Yeung", "Climate and Environmental Justice"),
        ("Annel Hernandez", "Public utility advocate"),
    ]),
    ("Helen Arteaga", "Deputy mayor for health and human services", [
        ("Mitchell Katz", "Health + Hospitals"),
        ("Alister Martin", "Health and Mental Hygiene"),
        ("Jason Graham", "Chief Medical Examiner"),
        ("Erin Dalton", "Social Services"),
        ("Rebecca Jones Gaston", "Children's Services"),
        ("Winette Saunders", "Children's Services"),
        ("Sandra Escamilla-Davies", "Youth and Community Development"),
        ("Emmy Liss", "Child Care and Early Childhood Education"),
        ("Lisa Scott-McKenzie", "Aging"),
        ("Yesenia Mata", "Veterans' Services"),
        ("Nisha Agarwal", "People with Disabilities"),
        ("Siddhartha Sanchez", "Food Policy"),
    ]),
    ("Julie Su", "Deputy mayor for economic justice", [
        ("Anthony Shorris", "Economic Development Corporation"),
        ("Lina Khan", "Economic Development Corporation"),
        ("Midori Valdivia", "Taxi and Limousine Commission"),
        ("Kenny Minaya", "Small Business Services"),
        ("Sam Levine", "Consumer and Worker Protection"),
        ("Michael Garner", "Minority and Women-Owned Business"),
        ("Diya Vij", "Cultural Affairs"),
        ("Rafael Espinal", "Media and Entertainment"),
        ("Christine Clarke", "Human Rights"),
        ("Afua Atta-Mensah", "Equity and Racial Justice"),
        ("Faiza Ali", "Immigrant Affairs"),
    ]),
    ("Renita Francois", "Deputy mayor for community safety", [
        ("Ayesha Delany-Brumsey", "Community Safety"),
    ]),
    ("Elle Bisgaard-Church", "Chief of staff", [
        ("Jahmila Edwards", "Intergovernmental Affairs"),
        ("Odetty Tineo", "City Legislative Affairs"),
        ("Tascha Van Auken", "Mass Engagement"),
        ("Stephanie Silkowski", "Appointments"),
        ("Ana Maria Archila", "International Affairs"),
        ("Kate Smith", "Mayor's Fund"),
        ("Dawn Tolson", "Citywide Event Coordination"),
        ("Maya Handa", "World Cup"),
        ("Simonia Brown", "Policy and strategy"),
        ("Mir Bashar", "Chief administrative officer"),
    ]),
    ("Ramzi Kassem", "Chief counsel", [
        ("Vilda Vera Mayuga", "Administrative Trials and Hearings"),
        ("Ali Najmi", "Advisory Committee on the Judiciary"),
    ]),
    ("Steven Banks", "Corporation counsel", []),
    ("Anna Bahr", "Communications director", [
        ("Joe Calvello", "Press secretary"),
        ("Dora Pekec", "Senior spokesperson"),
        ("Monica Klein", "Senior adviser"),
        ("Lekha Sunder", "Deputy director"),
        ("Julian Gerson", "Speechwriting"),
        ("Cassio Mendoza", "Press office"),
    ]),
    ("Jessica Tisch", "Police commissioner", []),
    ("__MAYOR__", "Reporting to the mayor", [
        ("Nadia Shihata", "Investigation"),
        ("Taylor Brown", "LGBTQIA+ Affairs"),
        ("Phylisa Wisdom", "Combat Antisemitism"),
    ]),
]

# ---------------------------------------------------------------------------
# Where a bare reporting line would misdescribe an office, the Charter provision
# that governs it, quoted rather than paraphrased.
# ---------------------------------------------------------------------------
CHARTER_NOTES = {
    "Investigation":
        "The reporting line understates it. The Charter gives the department jurisdiction over "
        "&#8220;any agency, officer, or employee of the city&#8221; (&#167;&#8239;803(f)), and either "
        "the mayor or the Council may direct an investigation (&#167;&#8239;803(a)). The mayor may "
        "remove the commissioner only after filing written reasons and allowing the commissioner "
        "&#8220;an opportunity of making a public explanation&#8221; (&#167;&#8239;801).",
    "Community Safety":
        "Created by executive order in March 2026. It sets policy on violence prevention, survivor "
        "services and community mental health; it does not run the police, fire or correction "
        "departments.",
}

# ---------------------------------------------------------------------------
# Department charts. Maps a box label in COLUMNS to the agency name(s) used by
# the Greener Book (joshgreenman1973.github.io/nyc-green-book), which publishes
# the Green Book's own division hierarchy for 124 agencies and refreshes itself
# every four hours. A label absent from here has no published department chart,
# and the page says so rather than inventing one. Verified by hand: fuzzy
# matching produced false positives bad enough to mislead (it paired the public
# utility advocate with the public advocate, and the tenant protection office
# with the commission to combat police corruption).
# ---------------------------------------------------------------------------
DEPTS = {
    "Management and Budget": ["Management & Budget, Office of"],
    "Finance": ["Finance"],
    "Labor Relations": ["Labor Relations, Office of"],
    "Education": ["Education"],
    "School Construction Authority": ["School Construction Authority, NYC"],
    "Correction": ["Correction, Department of"],
    "Probation": ["Probation"],
    "Investigation": ["Investigation"],
    "Business Integrity Commission": ["Business Integrity Commission"],
    "Records and Information Services": ["Records & Information Services"],
    "Housing Authority": ["Housing Authority, NYC"],
    "Housing Preservation and Development": ["Housing Preservation & Development"],
    "Housing Development Corporation": ["Housing Development Corporation, NYC"],
    "City Planning": ["City Planning", "City Planning Commission"],
    "Buildings": ["Buildings"],
    "Landmarks Preservation Commission": ["Landmarks Preservation Commission"],
    "Standards and Appeals": ["Standards And Appeals, Board of"],
    "Environmental Protection": ["Environmental Protection"],
    "Sanitation": ["Sanitation"],
    "Transportation": ["Transportation"],
    "Taxi and Limousine Commission": ["Taxi & Limousine Commission"],
    "Parks and Recreation": ["Parks, NYC"],
    "Design and Construction": ["Design and Construction"],
    "Citywide Administrative Services": ["Citywide Administrative Services"],
    "Contract Services": ["Contract Services, Mayor's Office of"],
    "Fire Department": ["Fire Department"],
    "Emergency Management": ["Emergency Management, NYC"],
    "Technology and Innovation": ["Office of Technology & Innovation"],
    "Health + Hospitals": ["Health + Hospitals NYC, (NYC H+H)"],
    "Health and Mental Hygiene": ["Health & Mental Hygiene, Department of"],
    "Chief Medical Examiner": ["Medical Examiner, Office of Chief"],
    "Social Services": ["Human Resources Administration / Department of Social Services",
                        "Homeless Services, Department of"],
    "Children's Services": ["Children's Services, Administration for"],
    "Youth and Community Development": ["Youth and Community Development"],
    "Aging": ["Aging, Department for the"],
    "Veterans' Services": ["Veterans' Services, Department of"],
    "Economic Development Corporation": ["Economic Development Corporation, NYC"],
    "Small Business Services": ["Small Business Services"],
    "Consumer and Worker Protection": ["Consumer and Worker Protection"],
    "Cultural Affairs": ["Cultural Affairs"],
    "Media and Entertainment": ["Media and Entertainment, Mayor's Office of"],
    "Human Rights": ["Human Rights, City Commission on"],
    "Equity and Racial Justice": ["Mayor's Office of Equity & Racial Justice"],
    "Administrative Trials and Hearings": ["Administrative Trials And Hearings, Office of"],
}

# Principals who run an agency in their own right rather than a portfolio.
COLUMN_DEPTS = {
    "Jessica Tisch": ["Police Department"],
    "Steven Banks": ["Law Department, Office of the Corporation Counsel"],
    "Elle Bisgaard-Church": ["Mayor, Office of the"],
}

# Appointed bodies that also have a Green Book roster.
BOARD_DEPTS = {
    "Rent Guidelines Board": ["Rent Guidelines Board"],
}

PANELS = [
    ("Mayor's Advisory Committee on the Judiciary",
     "Named July 23, 2026. Screens candidates for the mayor's judicial appointments. Chaired by Ali Najmi.",
     "Judicial screening committee"),
    ("Judicial appointments",
     "Criminal Court judges appointed or reappointed by the mayor. They sit outside the administration's agencies.",
     "Judiciary (mayoral judicial appointments)"),
]

BOARDS = [
    ("Rent Guidelines Board", ["Chantella Mitchell", "Sina Sinai", "Lauren Melodia",
                               "Brandon Mancilla", "Maksim Wynn", "Adan Soltren"]),
    ("Metropolitan Transportation Authority board", ["Melanie Hartzog", "Janette Sadik-Khan",
                                                     "Dan Garodnick", "David Jones"]),
    ("Quadrennial Advisory Commission", ["Carl Weisbrod", "Lilliam Barrios-Paoli", "Larian Angelo"]),
    ("Panel for Educational Policy", ["Karla Cordero", "Tariq Khan", "Mehrain Mahdi", "Alan Ong",
                                     "Amy Fair", "Courtney Rajwani", "Crystal Vera-Montalvo",
                                     "Marjorie Dienstag", "Lucas Koehler", "Primo Lasana",
                                     "Kristin Jefferson", "Maddy Fox", "Raysa Rodriguez"]),
]


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The city's own agency file (t3jq-9nkf), snapshotted by refresh_governance.py.
# It is the only published source for what an office reports to: 132 of its 306
# organizations carry a reporting line. Used three ways - to source the columns
# below, to add the offices the file lists that no announcement covered, and to
# show what reports into an office.
# ---------------------------------------------------------------------------
GOV = json.loads((HERE / "data" / "governance.json").read_text())

# How the file writes a principal, mapped to the column it belongs in. The file
# is updated annually, so it still carries a few portfolio names from the last
# administration; those are mapped to the post that absorbed the work, and the
# ones with no successor are left out rather than guessed at.
CITY_PORTFOLIO = {
    "First Deputy Mayor": "Dean Fuleihan",
    "Deputy Mayor for Operations": "Julia Kerson",
    "Deputy Mayor for Economic Justice": "Julie Su",
    "Deputy Mayor for Health and Human Services": "Helen Arteaga",
    "Deputy Mayor for Housing and Planning": "Leila Bozorg",
    "Chief of Staff": "Elle Bisgaard-Church",
    "Chief of Staff to the Mayor": "Elle Bisgaard-Church",
    "Deputy Mayor for Administration and Chief of Staff": "Elle Bisgaard-Church",
    "Chief Counsel to the Mayor and City Hall": "Ramzi Kassem",
    "Deputy Mayor for Communications": "Anna Bahr",
    "Deputy Mayor for Community Safety": "Renita Francois",
    "Mayor": "__MAYOR__",
    "Office of the Mayor": "__MAYOR__",
}

# Offices the file lists but that this project does not carry as their own box,
# because the announced appointee already covers them or they are not mayoral.
CITY_SKIP = {
    "new york city police department", "new york city public schools",
    "city university of new york", "city university construction fund",
    "new york city law department", "human resources administration",
    "department of homeless services",
    "mayor's office of citywide events coordination and management",
}


def _norm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    for w in ("department of", "office of the", "mayor s office of the", "mayor s office of",
              "office of", "new york city", "nyc", "the", "department", "city of new york"):
        s = s.replace(w, " ")
    return " ".join(s.split())


GOV_BY_NAME = {}
for _r in GOV:
    GOV_BY_NAME.setdefault(_norm(_r["name"]), _r)
    for _alt in (_r.get("alternate_or_former_names") or "").split(";"):
        if _alt.strip():
            GOV_BY_NAME.setdefault(_norm(_alt), _r)

# What reports into each organization, by the file's own account.
GOV_CHILDREN = {}
for _r in GOV:
    for _p in (_r.get("reports_to") or "").split(";"):
        if _p.strip():
            GOV_CHILDREN.setdefault(_norm(_p), []).append(_r)


# Exact normalized matches only. A containment match looked tempting and was
# wrong in practice: it tied Children's Services to an office under Mass
# Engagement and the tenant protection office to a police-corruption commission.
# Anything the normalizer cannot match exactly is listed here by hand or not at
# all, and a box with no match simply shows no reporting line.
GOV_ALIASES = {
    "management and budget": "Office of Management and Budget",
    "labor relations": "Office of Labor Relations",
    "education": "New York City Public Schools",
    "correction": "Department of Correction",
    "fire department": "Fire Department of the City of New York",
    "sanitation": "Department of Sanitation",
    "transportation": "Department of Transportation",
    "parks and recreation": "Department of Parks and Recreation",
    "environmental protection": "Department of Environmental Protection",
    "buildings": "Department of Buildings",
    "probation": "Department of Probation",
    "finance": "Department of Finance",
    "investigation": "Department of Investigation",
    "city planning": "Department of City Planning",
    "housing preservation and development": "Department of Housing Preservation and Development",
    "housing authority": "New York City Housing Authority",
    "housing development corporation": "Housing Development Corporation",
    "design and construction": "Department of Design and Construction",
    "citywide administrative services": "Department of Citywide Administrative Services",
    "records and information services": "Department of Records and Information Services",
    "small business services": "Department of Small Business Services",
    "consumer and worker protection": "Department of Consumer and Worker Protection",
    "cultural affairs": "Department of Cultural Affairs",
    "aging": "Department for the Aging",
    "children's services": "Administration for Children's Services",
    "youth and community development": "Department of Youth and Community Development",
    "veterans' services": "Department of Veterans' Services",
    "social services": "Department of Social Services",
    "health and mental hygiene": "Department of Health and Mental Hygiene",
    "health + hospitals": "NYC Health + Hospitals",
    "chief medical examiner": "Office of Chief Medical Examiner",
    "emergency management": "New York City Emergency Management",
    "technology and innovation": "Office of Technology and Innovation",
    "taxi and limousine commission": "New York City Taxi and Limousine Commission",
    "economic development corporation": "Economic Development Corporation",
    "landmarks preservation commission": "Landmarks Preservation Commission",
    "standards and appeals": "Board of Standards and Appeals",
    "business integrity commission": "Business Integrity Commission",
    "school construction authority": "School Construction Authority",
    "human rights": "Commission on Human Rights",
    "administrative trials and hearings": "Office of Administrative Trials and Hearings",
    "contract services": "Mayor's Office of Contract Services",
    "intergovernmental affairs": "Office of Intergovernmental Affairs",
    "sheriff": "Sheriff",
    "public design commission": "Public Design Commission",
}


def gov_row(label, agency=""):
    """The city's file row for a box. Exact normalized name, alias, or nothing."""
    for cand in (label, agency):
        k = _norm(cand)
        if not k:
            continue
        if k in GOV_ALIASES:
            hit = GOV_BY_NAME.get(_norm(GOV_ALIASES[k]))
            if hit:
                return hit
        if k in GOV_BY_NAME:
            return GOV_BY_NAME[k]
    return None


def esc(s):
    return html.escape(str(s), quote=True)


def flag(p):
    if p["status"] == "retained":
        return ("ret", "Retained")
    if "nominee" in p["title"].lower() or "recommended" in p["title"].lower():
        return ("pend", "Pending confirmation")
    return ("new", "New")


def fmt_date(iso):
    if not iso:
        return ""
    y, m, d = iso.split("-")
    months = ["Jan.", "Feb.", "March", "April", "May", "June", "July",
              "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
    return f"{months[int(m) - 1]} {int(d)}, {y}"


# The Greener Book snapshot is read only to pre-fill staff counts and to fail
# loudly if a mapping in DEPTS no longer matches an agency. The page itself
# fetches the live file at runtime, so the department layer stays current
# without a rebuild.
GB_LOCAL = HERE.parent / "nyc-green-book" / "docs" / "data" / "greenbook.json"
GB = json.loads(GB_LOCAL.read_text()) if GB_LOCAL.exists() else None
GB_AGENCIES = {a["name"]: a for a in GB["agencies"]} if GB else {}
# Staff counts are only a teaser shown before the live directory loads. Cache them
# so a checkout without the Greener Book beside it still builds a complete page.
_COUNTS_FILE = HERE / "data" / "agency_counts.json"
if GB:
    _COUNTS = {n: a["n"] for n, a in GB_AGENCIES.items()}
elif _COUNTS_FILE.exists():
    _COUNTS = json.loads(_COUNTS_FILE.read_text())
else:
    _COUNTS = {}


def dept_attrs(label, extra=None):
    """data- attributes wiring a box to its department chart."""
    names = list(extra or DEPTS.get(label, []))
    if not names:
        return "", 0
    missing = [n for n in names if GB and n not in GB_AGENCIES]
    if missing:
        raise SystemExit(f"DEPTS maps {label!r} to unknown agency name(s): {missing}. "
                         f"The Greener Book agency list has changed; fix the mapping.")
    n = sum(_COUNTS.get(x, 0) for x in names)
    return f' data-dept="{esc("|".join(names))}" data-n="{n}"', n


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def entry(name, label, n, column_title=""):
    p = PEOPLE[name]
    cls, flabel = flag(p)
    date = "" if p.get("date") == "2026-01-01" and p["status"] == "retained" else fmt_date(p.get("date"))
    if not date:
        date = '<abbr title="announcement date not published">n.d.</abbr>'
    attrs, staff = dept_attrs(label)
    charter = CHARTER_NOTES.get(label, "")
    g = gov_row(label, p.get("agency", ""))
    gattrs = ""
    if g:
        kids = GOV_CHILDREN.get(_norm(g["name"]), [])
        gattrs = (f' data-cityline="{esc(g.get("reports_to") or "")}"'
                  f' data-govname="{esc(g["name"])}"'
                  f' data-kids="{esc("|".join(k["name"] for k in kids))}"')
    open_hint = (f'<span class="open">{staff} in the department directory</span>' if staff
                 else '<span class="open none">No department chart published</span>')
    return f"""<button type="button" class="ent {cls}{' has-dept' if staff else ''}"
   id="{slug(name)}"
   data-name="{esc(name.lower())}" data-label="{esc(label.lower())}" data-flag="{cls}"
   data-person="{esc(name)}" data-title="{esc(p['title'])}" data-agency="{esc(p['agency'])}"
   data-notes="{esc(p.get('notes') or '')}" data-source="{esc(p['source'])}" data-mine="{esc(column_title)}" data-charter="{charter}"
   data-date="{esc(date if not date.startswith('<') else '')}" data-status="{esc(flabel)}"{attrs}{gattrs}>
  <span class="num">{n:03d}</span>
  <span class="unit">{esc(label)}</span>
  <span class="who">{esc(name)}</span>
  <span class="meta">{date if date.startswith("<") else esc(date)}{'<b class="tag">' + flabel + '</b>' if cls != 'new' else ''}</span>
  {open_hint}
</button>"""



def city_extras():
    """Offices in the city's file that this chart has no announced appointee for,
    grouped by the column the file itself puts them in."""
    known = set()
    for principal, _t, reports in COLUMNS:
        known.add(_norm(principal))
        for nm, lb in reports:
            known.add(_norm(lb))
            known.add(_norm(PEOPLE[nm].get("agency", "")))
    out = {}
    for r in GOV:
        line = (r.get("reports_to") or "").split(";")[0].strip()
        col = CITY_PORTFOLIO.get(line)
        if not col:
            continue
        k = _norm(r["name"])
        if k in known or r["name"].lower() in CITY_SKIP:
            continue
        if any(len(k) > 6 and (k in x or x in k) for x in known):
            continue
        out.setdefault(col, []).append(r)
    for col in out:
        out[col].sort(key=lambda r: r["name"])
    return out


CITY_EXTRAS = city_extras()


def extra_html(col):
    rows = CITY_EXTRAS.get(col, [])
    if not rows:
        return ""
    items = []
    for r in rows:
        who = r.get("principal_officer_full_name") or ""
        title = r.get("principal_officer_title") or ""
        kids = GOV_CHILDREN.get(_norm(r["name"]), [])
        url = (r.get("principal_officer_contact_url") or {}).get("url") if isinstance(
            r.get("principal_officer_contact_url"), dict) else r.get("principal_officer_contact_url")
        site = (r.get("url") or {}).get("url") if isinstance(r.get("url"), dict) else r.get("url")
        items.append(
            f'<button type="button" class="ent listed" id="{slug(r["name"])}" '
            f'data-name="{esc((who or r["name"]).lower())}" data-label="{esc(r["name"].lower())}" '
            f'data-flag="listed" data-person="{esc(who or r["name"])}" '
            f'data-title="{esc(title + (", " if title and who else "") + r["name"] if who else r["name"])}" '
            f'data-agency="{esc(r["name"])}" data-notes="" '
            f'data-source="https://data.cityofnewyork.us/d/t3jq-9nkf" data-site="{esc(site or "")}" '
            f'data-date="" data-status="Listed by the city" '
            f'data-cityline="{esc(r.get("reports_to") or "")}" data-govname="{esc(r["name"])}" '
            f'data-kids="{esc("|".join(k["name"] for k in kids))}">'
            f'<span class="unit">{esc(r["name"])}</span>'
            f'<span class="who">{esc(who) if who else "<i>No officer named</i>"}</span>'
            f'</button>')
    return (f'<details class="extra"><summary>{len(rows)} more offices the city lists '
            f'in this portfolio</summary>{"".join(items)}</details>')


def build():
    n = [0]

    def nxt():
        n[0] += 1
        return n[0]

    cols = []
    for principal, title, reports in COLUMNS:
        if principal == "__MAYOR__":
            head = ('<div class="col-head direct"><span class="rank">Not in a deputy '
                    f'mayor\'s portfolio</span><h3>{esc(title)}</h3></div>')
        else:
            p = PEOPLE[principal]
            attrs, staff = dept_attrs(None, COLUMN_DEPTS.get(principal))
            gkids = GOV_CHILDREN.get(_norm(title), [])
            gattrs = f' data-kids="{esc("|".join(k["name"] for k in gkids))}"' if gkids else ""
            cls, flabel = flag(p)
            hint = f'<span class="open">{staff} in the department directory</span>' if staff else ""
            is_dm = title.lower().startswith(("first deputy mayor", "deputy mayor"))
            head = (f'<button type="button" class="col-head{" dm" if is_dm else ""}'
                    f'{" has-dept" if staff else ""}" '
                    f'id="{slug(principal)}" data-name="{esc(principal.lower())}" '
                    f'data-label="{esc(title.lower())}" data-flag="{cls}" '
                    f'data-person="{esc(principal)}" data-title="{esc(p["title"])}" '
                    f'data-agency="{esc(p["agency"])}" data-notes="{esc(p.get("notes") or "")}" '
                    f'data-source="{esc(p["source"])}" data-date="{esc(fmt_date(p.get("date")))}" '
                    f'data-status="{esc(flabel)}"{attrs}{gattrs}>'
                    f'<span class="rank">{esc(title)}</span><h3>{esc(principal)}</h3>'
                    f'<span class="since">{esc(fmt_date(p.get("date")))}</span>{hint}</button>')
        body = "\n".join(entry(nm, lb, nxt(), title) for nm, lb in reports)
        empty = '<p class="none">No agency reports listed.</p>' if not reports else ""
        cols.append(f'<section class="col" data-col="{esc(principal)}">{head}'
                    f'<div class="stack">{body}{empty}{extra_html(principal)}</div></section>')

    panels = []
    for heading, note, cat in PANELS:
        members = [p for p in ROSTER["appointees"] if p["category"] == cat]
        items = "\n".join(
            f'<a class="chip" href="{esc(m["source"])}" target="_blank" rel="noopener" '
            f'data-name="{esc(m["name"].lower())}" data-label="{esc(m["title"].lower())}" data-flag="new" '
            f'title="{esc(m["notes"][:150])}"><span class="num">{nxt():03d}</span>{esc(m["name"])}</a>'
            for m in members)
        panels.append(f'<div class="panel"><h4>{esc(heading)}<span class="count">{len(members)}</span></h4>'
                      f'<p class="note">{esc(note)}</p><div class="chips">{items}</div></div>')

    boards = []
    for heading, names in BOARDS:
        attrs, staff = dept_attrs(None, BOARD_DEPTS.get(heading))
        items = "\n".join(
            f'<a class="chip {flag(PEOPLE[nm])[0]}" href="{esc(PEOPLE[nm]["source"])}" target="_blank" rel="noopener" '
            f'data-name="{esc(nm.lower())}" data-label="{esc(PEOPLE[nm]["title"].lower())}" data-flag="{flag(PEOPLE[nm])[0]}" '
            f'title="{esc(PEOPLE[nm]["title"])}"><span class="num">{nxt():03d}</span>{esc(nm)}'
            f'{"<b class=tag>" + flag(PEOPLE[nm])[1] + "</b>" if flag(PEOPLE[nm])[0] != "new" else ""}</a>'
            for nm in names)
        more = (f'<button type="button" class="deptlink"{attrs} data-person="{esc(heading)}" '
                f'data-title="{esc(heading)}">Open the {staff}-person directory</button>' if staff else "")
        boards.append(f'<div class="panel"><h4>{esc(heading)}<span class="count">{len(names)}</span></h4>'
                      f'<div class="chips">{items}</div>{more}</div>')

    mapped = len(DEPTS) + len(COLUMN_DEPTS) + len(BOARD_DEPTS)
    extras = sum(len(v) for v in CITY_EXTRAS.values())
    citylines = sum(1 for r in GOV if r.get("reports_to"))
    total = len(ROSTER["appointees"])

    # Snapshot of exactly what went into the page, so the build is reproducible
    # from this repo alone even though the roster lives in a sibling project.
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "roster.json").write_text(json.dumps(ROSTER, indent=1, ensure_ascii=False))
    if GB:
        _COUNTS_FILE.write_text(json.dumps(_COUNTS, indent=0, sort_keys=True))

    tpl = (HERE / "template.html").read_text()
    out = (tpl
           .replace("{{COLUMNS}}", "\n".join(cols))
           .replace("{{PANELS}}", "\n".join(panels))
           .replace("{{BOARDS}}", "\n".join(boards))
           .replace("{{TOTAL}}", str(total))
           .replace("{{MAPPED}}", str(mapped))
           .replace("{{EXTRAS}}", str(extras))
           .replace("{{CITYLINES}}", str(citylines))
           .replace("{{UPDATED}}", fmt_date(ROSTER["meta"]["lastUpdated"])))
    (HERE / "index.html").write_text(out)
    print(f"wrote index.html - {total} appointees, "
          f"{n[0]} numbered boxes, {mapped} department charts wired, "
          f"{extras} offices added from the city's file, {citylines} published reporting lines")


if __name__ == "__main__":
    build()
