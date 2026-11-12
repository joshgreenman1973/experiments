#!/usr/bin/env python3
"""Fill template.html from data/base.json plus the verified research files.

    python3 scrape/build_base.py     # official rosters -> data/base.json
    python3 scrape/verify_staff.py   # re-fetch every researched contact's source page
    python3 build.py                 # -> index.html, data/directory.csv, data/staff.csv
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "scrape"))
from build_base import same_person, name_tokens, slug, read  # noqa: E402
import verify_staff as V  # noqa: E402

DATA = os.path.join(ROOT, "data")
BUILT = "Nov. 10, 2026"

base = json.load(open(os.path.join(DATA, "base.json")))
P = base["people"]
byid = {p["id"]: p for p in P}


def strict_same(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    return bool(ta and tb and ta[-1] == tb[-1] and (ta[0] == tb[0] or ta[0] in tb or tb[0] in ta))


# ------------------------------------------------------------ term bookkeeping
SHORT = {"U.S. House": "NY-{n}", "State Senate": "State Senate {n}", "State Assembly": "Assembly {n}"}
for p in P:
    L = p["links"]
    if p["status"] == "sitting" and L.get("successor_id"):
        L["term_ends"] = "Jan. 3, 2027" if p["section"] == "U.S. House" else "Dec. 31, 2026"
    if p["status"] != "sitting":
        p["seat_short"] = SHORT.get(p["section"], "{n}").format(n=p["district"])
        if not L.get("succeeds_id"):
            L["succeeds_short"] = "Vacant"
            L["succeeds_note"] = "The seat is vacant."
        cur = [q for q in P if q["status"] == "sitting" and q["id"] != L.get("succeeds_id")
               and strict_same(q["name"], p["name"])]
        if len(cur) == 1:
            q = cur[0]
            L["current_id"] = q["id"]
            L["current_role"] = f"{q['role'].lower()}, {q['seat']}"
            q["links"]["next_id"] = p["id"]
            q["links"]["next_role"] = f"{p['seat']} ({p['section']})"

# ------------------------------------------------- lieutenant governor-elect
def gov_ticket():
    t = read("enr/OF4CY0PY3.html")
    txt = re.sub(r"<[^>]+>", "|", t).replace("&nbsp;", " ")
    txt = re.sub(r"[ \t\r\n]+", " ", txt)
    txt = re.sub(r"(\| *)+", "|", txt)
    seg = txt.split("Totals by Candidate", 1)[1]
    rows = re.findall(r"\|\d+\|([^|]+?) ?\|(\d+)\|([\d.]+)%", seg)
    asof = re.search(r"Information As Of: ([^|]+)", txt).group(1).strip()
    scan = re.search(r"Scanners Reported: ?\|? ?([\d.]+) ?%", txt).group(1)
    return rows, asof, scan


rows, asof, scan = gov_ticket()
assert "Hochul" in rows[0][0] and "Adrienne E. Adams" in rows[0][0], rows[0]
delgado = byid["lieutenant-governor-antonio-delgado"]
adams = dict(
    id="lg-elect-adrienne-adams", name="Adrienne E. Adams", role="Lieutenant governor-elect",
    body="State of New York", level="State", section="Statewide", district=None, seat="Statewide",
    seat_short="Lieutenant governor", area=delgado["area"], beyond="", party="Democrat", status="elect",
    status_note="", email="", email_kind="none", offices=[], website="", form="", staff=[], notes="",
    race=dict(leader="Hochul and Adams", pct=float(rows[0][2]), second="Blakeman and Hood", second_pct=float(rows[1][2]),
              scanners=scan, asof=asof, url="https://enr.boenyc.gov/OF4CY0PY3.html", city_portion_only=True,
              close=False, outcome="elected"),
    links={"takes_office": "Jan. 1, 2027", "succeeds": delgado["name"], "succeeds_id": delgado["id"]},
    sources=[dict(label="NYC Board of Elections unofficial election night results", url="https://enr.boenyc.gov/OF4CY0PY3.html")],
)
delgado["links"].update(successor="Adrienne E. Adams", successor_id=adams["id"], term_ends="Dec. 31, 2026")
delgado["race"] = dict(adams["race"], outcome="leaving")
P.insert(P.index(delgado) + 1, adams)
byid[adams["id"]] = adams

# ---------------------------------------------------------- researched staff
SECTION_BY_FILE = {
    "staff_federal.json": ["U.S. Senate", "U.S. House"],
    "staff_senate.json": ["State Senate"],
    "staff_assembly_a.json": ["State Assembly"], "staff_assembly_b.json": ["State Assembly"],
    "staff_council_a.json": ["City Council"], "staff_council_b.json": ["City Council"],
    "staff_exec.json": ["Statewide", "Citywide", "Borough presidents", "District attorneys"],
}
RANK = [r"communications|press|media|spokes", r"chief of staff", r"district director|constituent|community",
        r"schedul", r"legislative|counsel|policy"]


def rank(title):
    t = (title or "").lower()
    for i, pat in enumerate(RANK):
        if re.search(pat, t):
            return i
    return len(RANK)


def find_person(row):
    secs = SECTION_BY_FILE.get(row.get("file"), [])
    cands = [p for p in P if p["section"] in secs and p["status"] == "sitting"]
    name = row.get("official") or ""
    name = re.sub(r"^(Sen\.|Senator|Rep\.|Assembly ?member|Council ?Member|Speaker|Gov\.|Governor|Lt\. Gov\.|"
                  r"Attorney General|Comptroller|State Comptroller|Mayor|Public Advocate|Borough President|"
                  r"District Attorney|Majority Leader|Minority Leader|Deputy Speaker)\s+", "", name, flags=re.I)
    m = re.search(r"\d+", str(row.get("district") or ""))
    if m and secs and secs[0] in ("State Senate", "State Assembly", "City Council", "U.S. Senate"):
        n = int(m.group())
        hit = [p for p in cands if p["district"] == n]
        if len(hit) == 1 and (not name or same_person(hit[0]["name"], name)):
            return hit[0]
    hit = [p for p in cands if strict_same(p["name"], name)]
    if len(hit) == 1:
        return hit[0]
    hit = [p for p in cands if same_person(p["name"], name)]
    if len(hit) == 1:
        return hit[0]
    if m:
        n = int(m.group())
        hit = [p for p in hit or cands if p["district"] == n]
        if len(hit) == 1:
            return hit[0]
    return None


MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def digits(x):
    d = re.sub(r"\D", "", x or "")
    return d[-10:]


def fmt_date(s):
    """'page last modified 2026-09-17 (WordPress...)' -> 'page updated Sept. 17, 2026'"""
    s = re.sub(r"\(?fetched[^)]*\)?", "", s)
    FULL = {"January": "Jan.", "February": "Feb.", "August": "Aug.", "September": "Sept.", "October": "Oct.",
            "November": "Nov.", "December": "Dec."}
    m0 = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\.? (\d{1,2}), (20\d\d)", s)
    if m0:
        return f"{FULL.get(m0.group(1), m0.group(1))} {int(m0.group(2))}, {m0.group(3)}"
    m0 = re.search(r"\b(Jan|Feb|Aug|Sept|Oct|Nov|Dec)\.? (\d{1,2}), (20\d\d)", s)
    if m0:
        return f"{m0.group(1)}. {int(m0.group(2))}, {m0.group(3)}"
    m = re.search(r"(20\d\d)-(\d\d)-(\d\d)", s)
    if not m:
        m2 = re.search(r"(20\d\d)-(\d\d)\b", s)
        if m2:
            return f"{MONTHS[int(m2.group(2)) - 1]} {m2.group(1)}"
        m3 = re.fullmatch(r"\s*((Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)[a-z]*\.? )?(20\d\d)\s*", s)
        return s.strip() if m3 else ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    out = f"{MONTHS[mo - 1]} {d}, {y}"
    return ("page updated " + out) if re.search(r"modif|updated|undated", s, re.I) else out


# Short cautions for individual entries, written after reading the research notes.
CAVEATS = {
    "Anthony Hogrebe": "Named in a February 2025 statement; not confirmed since.",
    "Wendy Erdly": "Appointed in 2023 and still on the office’s leadership page.",
    "Renee Taylor": "The address is printed without a name. The name comes from a January 2025 hearing transcript.",
    "Julian Martin": "On releases through July 2025. The office advertised for a communications director in June 2026.",
    "Randi Malman": "On a budget page updated in May 2026 but not on the October staff directory.",
    "Maria Villalobos": "Named at an April 2025 hearing; not confirmed for 2026.",
    "Marci Bishop": "Named in a June 2025 City & State article; not confirmed since.",
    "Bill Matarazzo": "From a December 2023 release, the only one with a contact line; not confirmed since.",
    "David Montilla": "From a September 2024 release; not confirmed since.",
    "Christine Delius": "From a September 2025 release; none of the 2026 releases names a contact.",
    "Kara Clark": "The address is printed without a name on a 2025 job posting. The name comes from a 2021 release.",
}


def norm_title(t):
    """Where a page gives no job title, say what the person is listed as and nothing more."""
    t = t.strip()
    m = re.match(r"\(?(?:title )?not (?:given|stated)(?: on page)?\s*[;(]\s*(.+?)\)?\s*$", t, re.I)
    if m:
        inner = re.sub(r";?\s*a third-party directory[^;)]*", "", m.group(1)).strip(" ;)")
        inner = re.sub(r"^listed as (a |the )?", "", inner, flags=re.I)
        inner = re.sub(r"^named contact for job fair vendors$", "job fair vendor contact", inner)
        inner = re.sub(r"^address printed under '([^']+)',\s*", r"\1, ", inner)
        inner = inner.replace("MEDIA CONTACT", "media contact")
        return inner[:1].upper() + inner[1:]
    return re.sub(r"\s*\((?:title )?not (?:given|stated)[^)]*\)", "", t, flags=re.I).strip()


def src_label(url, date):
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
    return host


unmatched = []
stale_dropped = []
vpath = os.path.join(DATA, "staff_verified.json")
research = json.load(open(vpath)) if os.path.exists(vpath) else []
GB_STALE = {"mark-levine", "brad-hoylman-sigal"}   # office changed hands Jan. 1, 2026; the Green Book still lists the predecessor's staff
for r in research:
    p = find_person(r)
    if not p:
        unmatched.append((r.get("file"), r.get("official"), r.get("staff_name")))
        continue
    title = (r.get("staff_title") or "").strip()
    if not r.get("staff_name"):
        # an office line (press office, regional office), not a person
        if "form" in title.lower() or not (r.get("phone") or r.get("email")):
            continue
        title = re.sub(r"\s*\(unnamed on site\)", "", title)
        have = {digits(x) for o in p["offices"] for x in re.split(r" or ", o.get("phone") or "")}
        added = False
        for seg in [x.strip() for x in (r.get("phone") or "").split(";") if x.strip()] or [""]:
            m = re.match(r"([A-Za-z .]+):\s*(.+)", seg)
            where, num = (m.group(1).strip(), m.group(2).strip()) if m else ("", seg)
            m2 = re.match(r"(.+?)\s*\(([A-Za-z ]+)\)$", num)
            if m2:
                num, where = m2.group(1), m2.group(2)
            where = {"NYC": "New York City"}.get(where, where)
            if num and digits(num) in have:
                continue
            if num:
                p["offices"].append(dict(label=title + (", " + where if where else ""), addr=[], phone=num, fax=""))
                added = True
        em = r.get("email") or ""
        if em and re.search(r"press|communications|media", title, re.I) and not p["links"].get("press_email"):
            p["links"]["press_email"] = em
            added = True
        elif em and not p["email"] and re.match(r"main office", title, re.I):
            p["email"], p["email_kind"] = em, "office inbox"
            added = True
        if added and r.get("source_url"):
            p["sources"].append(dict(label=src_label(r["source_url"], ""), url=r["source_url"]))
        continue
    title = norm_title(title)
    # research commentary does not belong in a name or a job title
    nm = r["staff_name"]
    mp = re.search(r"\s*\(([^)]*)\)", nm)
    if mp and re.search(r"\b[a-z]{3,}", mp.group(1)):
        nm = (nm[:mp.start()] + nm[mp.end():]).strip()
    r["staff_name"] = nm
    title = re.sub(r"^Title not given \(named contact for job fair vendors\)$", "Job fair vendor contact", title)
    title = re.sub(r";\s*listed for .*$", "", title)
    mt = re.match(r"(?:Media|Press)[\w ]* contact \((.+)\)$", title)
    if mt:
        title = mt.group(1)
    if re.search(r"undated \(story number", r.get("notes") or "") and nm not in CAVEATS:
        CAVEATS[nm] = "From an undated staff page still linked from the member’s home page; it may be several years old."
    if not (r.get("email") or r.get("phone")) and len(nm.split()) < 2:
        continue                      # a first name with no contact is no help to anyone
    if re.search(r"\binfer", r.get("notes") or "", re.I) and nm not in CAVEATS:
        CAVEATS[nm] = "The address is printed without this name beside it; the pairing is an inference."
    title = re.sub(r"\s*\((?=[^)]*\b(named|listed|lists|previously|also|leave|chair|reconfirmed|inquiries|invitations)\b)[^)]*\)", "", title).strip()
    mains = {digits(x) for o in p["offices"] for x in re.split(r" or ", o.get("phone") or "")}
    # several numbers can sit beside one name. Keep the person's own (cell, direct, extension);
    # drop the office's main line, which is already in the row.
    kept = []
    for part in re.split(r";|\bor\b", r.get("phone") or ""):
        mnum = re.search(r"\(?\d{3}\)?[\s.\-]\s?\d{3}[\s.\-]\d{4}", part)
        if not mnum:
            continue
        num = mnum.group(0)
        ext = re.search(r"(?:ext\.?|x)\s*(\d{2,5})", part[mnum.end():], re.I)
        if digits(num) in mains and not ext:
            continue
        if re.search(r"office|main|district line|albany line", part, re.I) and not ext and not re.search(r"cell|direct|mobile", part, re.I):
            continue
        tag = " (cell)" if re.search(r"cell|mobile", part, re.I) else ""
        kept.append(num + (f" ext. {ext.group(1)}" if ext else "") + tag)
    phone = " or ".join(dict.fromkeys(kept))
    if not r["staff_name"] and not title:
        continue
    if r["staff_name"] and same_person(p["name"], r["staff_name"]) and strict_same(p["name"], r["staff_name"]):
        # the official's own published line or address
        if phone:
            p["links"]["direct_line"] = phone
            p["links"]["direct_src"] = r.get("source_url") or ""
        em = r.get("email") or ""
        if em and em.lower() != (p["email"] or "").lower():
            p["links"]["direct_email"] = em
            p["links"]["direct_src"] = r.get("source_url") or ""
        continue
    title = re.sub(r"\s*\((also )?(media|press) contact[^)]*\)", "", title)
    third = bool(re.search(r"third-party directory", title))
    m_ns = re.match(r"Not stated(?: on page)?\s*\((.+)\)\s*$", title)
    if m_ns:
        inner = re.sub(r";?\s*a third-party directory[^;)]*", "", m_ns.group(1)).strip(" ;")
        inner = re.sub(r"^listed as MEDIA CONTACT$", "Media contact", inner)
        inner = re.sub(r"^address printed under '([^']+)',\s*", r"\1, ", inner)
        title = inner[:1].upper() + inner[1:]
    title = re.sub(r"\s*\([^)]*third-party directory[^)]*\)", "", title).strip()
    if third and not (r.get("email") or r.get("phone")) and r["staff_name"] not in CAVEATS:
        CAVEATS[r["staff_name"]] = "Name and title from a third-party directory; not confirmed on an official page."
    yrs = re.findall(r"20\d\d", r.get("source_date") or "")
    yr = max(map(int, yrs)) if yrs else None
    if yr and yr <= 2022:
        stale_dropped.append((p["name"], r["staff_name"], yr))
        continue                     # too old to offer as a way to reach anyone
    if yr and yr <= 2024 and r["staff_name"] not in CAVEATS:
        CAVEATS[r["staff_name"]] = f"From a {yr} page; not confirmed since."
    entry = dict(name=r["staff_name"], title=title, email=r.get("email") or "", phone=phone,
                 src=r.get("source_url") or "", src_label=src_label(r.get("source_url") or "", ""),
                 date=fmt_date(r.get("source_date") or ""), checked=True, kind="research",
                 caveat=CAVEATS.get(r["staff_name"], ""))
    entry["title"] = re.sub(r"\s*\((as of|title)[^)]*\)", "", entry["title"])
    # the office's own page beats the Green Book: same person, or same job under another name
    def same_job(a, b):
        ja = "cos" if re.fullmatch(r"chief of staff.*", a, re.I) else "comms" if re.search(r"^(director,? (of )?communications|communications director|press secretary)", a, re.I) else ""
        jb = "cos" if re.fullmatch(r"chief of staff.*", b, re.I) else "comms" if re.search(r"^(director,? (of )?communications|communications director|press secretary)", b, re.I) else ""
        if ja == "comms" and jb == "comms":
            return ("press secretary" in a.lower()) == ("press secretary" in b.lower())
        return bool(ja) and ja == jb
    for old_s in [x for x in p["staff"] if x.get("kind") == "greenbook"]:
        ta, tb = name_tokens(old_s["name"]), name_tokens(entry["name"])
        near = ta and tb and ta[0] == tb[0] and sum(c1 != c2 for c1, c2 in zip(ta[-1], tb[-1])) + abs(len(ta[-1]) - len(tb[-1])) <= 1
        if strict_same(old_s["name"], entry["name"]) or near or same_job(old_s["title"], entry["title"]):
            if not entry["phone"] and (strict_same(old_s["name"], entry["name"]) or near):
                entry["phone"] = old_s.get("phone", "")
                if entry["phone"]:
                    entry["src_label"] += "; phone from the city Green Book"
            p["staff"].remove(old_s)
    p["staff"].append(entry)

for p in P:
    if p["id"] in GB_STALE:
        p["staff"] = [x for x in p["staff"] if x.get("kind") != "greenbook"]
        p["links"].pop("direct_line", None)
# ----------------------------------------------- names from press coverage
# For offices that publish no staff contact: the person news coverage most recently named as
# speaking for the official. Each article is downloaded again and must contain the name.
import glob
import unicodedata


def plain(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).lower()


def on_page(url, name):
    if not url or not url.startswith("http"):
        return False
    text = V.fetch(url)
    if not text or text == "__BLOCKED__":
        return False
    hay, toks = plain(text), [t for t in name_tokens(name)]
    if not toks:
        return False
    full = plain(name)
    if full in hay:
        return True
    # first and last name within a few words of each other (middle initials, nicknames)
    return bool(re.search(re.escape(toks[0]) + r"\W+(?:\S+\W+){0,2}" + re.escape(toks[-1]), hay))


OUTLET_FIX = {"amNY": "amNewYork", "amny": "amNewYork", "City & State New York": "City & State",
              "Spectrum News NY1": "NY1", "Spectrum News": "Spectrum News"}


def norm_role(role, side):
    """The article's wording, trimmed to the job: 'Bragg's spokesperson' -> 'Spokesperson'."""
    raw = role
    role = re.sub(r"\s*\([^)]*\)", "", role)
    role = re.sub(r"^(her|his|their)\s+", "", role, flags=re.I)
    if side == "campaign":
        low = role.lower()
        for pat, lab in ((r"manager", "Campaign manager"), (r"communications director", "Campaign communications director"),
                         (r"spokes", "Campaign spokesperson"), (r"strateg|\bled\b", "Campaign strategist"),
                         (r"poll", "Campaign pollster"), (r"consult|advis", "Campaign consultant")):
            if re.search(pat, low):
                return lab
    role = re.sub(r"^[A-Z][\w.\-]+(?: [A-Z][\w.\-]+)?['’]s\s+", "", role)           # "Bragg's spokesperson"
    role = re.sub(r"^(DA|District attorney|Mayor|Governor|Senator|Speaker)\s+(?=spokes)", "", role, flags=re.I)
    role = re.sub(r"\b(spokesman|spokeswoman)\b", "spokesperson", role, flags=re.I)
    role = re.sub(r"^(a|an|the)\s+", "", role, flags=re.I)
    role = re.sub(r"^[A-Z][\w.\-]+\s+(?=spokesperson)", "", role)                      # "Lasher spokesperson"
    role = re.sub(r"\s+(for|to|at|with)\s+(?!communications|policy|public|operations|external|intergovernmental|legislat|strateg|budget|press|media).*$", "", role, flags=re.I)
    role = re.sub(r"\s+of (the )?(attorney general|governor|mayor|speaker|district attorney|council|senat|assembl).*$", "", role, flags=re.I)
    role = re.sub(r",\s*(Office of|office of).*$", "", role)
    role = re.sub(r"^[A-Z][\w.\-]+ campaign ", "Campaign ", role)
    role = role.strip(" ,;.")
    if (side == "campaign" or "campaign" in raw.lower()) and "campaign" not in role.lower():
        role = "Campaign " + role[:1].lower() + role[1:]
    return role[:1].upper() + role[1:]
press_rows, press_dropped = [], []
# Held by the directory as name-only, shown by later coverage to have left the job.
SUPERSEDED = {("Rodneyse Bichotte Hermelyn", "James Christopher"): "called the Brooklyn Democratic Party’s former spokesperson in 2025 and 2026 coverage"}
for (off, who_), why in SUPERSEDED.items():
    for q_ in P:
        if q_["name"] == off:
            for x in [x for x in q_["staff"] if x["name"] == who_]:
                q_["staff"].remove(x)
                press_dropped.append((off, who_, why))
for f in sorted(glob.glob(os.path.join(DATA, "press_names_*.json")) + glob.glob(os.path.join(DATA, "hard_*.json"))):
    for r in json.load(open(f)):
        nm = (r.get("person_name") or "").strip()
        if not nm:
            continue
        nm = re.sub(r"\s*\([^)]*\)", "", nm).strip()
        who = re.sub(r"^(Gov\.|Lt\. Gov\.|Attorney General|Mayor|Speaker|District Attorney|Sen\.|Rep\.|Assembly ?member|Council ?Member)\s+", "", r.get("official") or "")
        cands = [q for q in P if strict_same(q["name"], who)] or [q for q in P if same_person(q["name"], who)]
        seat_n = re.search(r"\d+", r.get("seat") or "")
        if len(cands) > 1 and seat_n:
            cands = [q for q in cands if q["district"] == int(seat_n.group())] or cands
        side = (r.get("side") or "").lower()
        if len(cands) > 1:
            cands = [q for q in cands if (q["status"] != "sitting") == (side == "campaign")] or cands
        if len(cands) != 1:
            press_dropped.append((who, nm, "no single match in the directory"))
            continue
        q = cands[0]
        if side == "campaign" and q["links"].get("next_id"):
            q = next(x for x in P if x["id"] == q["links"]["next_id"])     # campaign staff belong with the seat just won
        url = r.get("url") or ""
        if not on_page(url, nm):
            url = r.get("second_url") or ""
            if not on_page(url, nm):
                press_dropped.append((q["name"], nm, "name not found on the article as downloaded"))
                continue
        def near(a, b):
            ta, tb = name_tokens(a), name_tokens(b)
            if not ta or not tb:
                return False
            d = lambda x, y: sum(c1 != c2 for c1, c2 in zip(x, y)) + abs(len(x) - len(y))
            return d(ta[0], tb[0]) <= 1 and d(ta[-1], tb[-1]) <= 1
        is_2026 = "2026" in (r.get("article_date") or "")
        cos = re.search(r"^chief of staff", (r.get("role_as_described") or ""), re.I)
        clash = next((x for x in q["staff"] if cos and re.match(r"chief of staff", x["title"], re.I) and (x.get("email") or x.get("phone"))
                      and name_tokens(x["name"])[:1] == name_tokens(nm)[:1] and not strict_same(x["name"], nm) and not near(x["name"], nm)), None)
        if clash:
            clash["caveat"] = f"{OUTLET_FIX.get(r.get('outlet') or '', r.get('outlet') or '')} named the chief of staff as {nm} on {fmt_date(r.get('article_date') or '')}."
            continue
        if any(strict_same(x["name"], nm) or near(x["name"], nm) for x in q["staff"]):
            ex = next(x for x in q["staff"] if strict_same(x["name"], nm) or near(x["name"], nm))
            host = lambda u: re.sub(r"^www\.", "", re.sub(r"^https?://", "", u or "").split("/")[0])
            if url != ex.get("src") and is_2026 and host(url) != host(ex.get("src")):
                ex["confirmed"] = dict(outlet=OUTLET_FIX.get(r.get("outlet") or "", r.get("outlet") or ""),
                                       date=fmt_date(r.get("article_date") or ""), url=url)
                if "2026" in (r.get("article_date") or "") and "not confirmed since" in (ex.get("caveat") or ""):
                    ex["caveat"] = ""
            if re.search(r"^CONFLICT|previously served", r.get("notes") or ""):
                ex["caveat"] = "Coverage conflicts on whether this person still holds the job."
                ex.pop("confirmed", None)
            ph0 = (r.get("phone") or "").strip()
            mains0 = {digits(x) for o in q["offices"] for x in re.split(r" or ", o.get("phone") or "")}
            if ph0 and not ex.get("phone") and digits(ph0) not in mains0 and V.check(url, "", ph0)[1]:
                ex["phone"] = ph0
            role_now = (r.get("role_as_described") or "").strip()
            if role_now and not ex.get("title"):
                ex["title"] = role_now[:1].upper() + role_now[1:]
            continue
        nts0 = r.get("notes") or ""
        if re.search(r"\bleft for\b|flagged as stale|has left the office|row is stale", nts0, re.I):
            press_dropped.append((q["name"], nm, "coverage says this person has left"))
            continue
        if re.search(r"^WEAK|\bWEAK:|tie is to the firm|Vendor-level|CAMPAIGN IS OVER", nts0):
            press_dropped.append((q["name"], nm, "weak tie, or a campaign that has ended"))
            continue
        if not re.search(r"spokes|chief|director|manager|secretary|advis|strateg|consult|communications|press|counsel|liaison|deputy|poll|led", r.get("role_as_described") or "", re.I):
            press_dropped.append((q["name"], nm, "no job title in the article"))
            continue
        raw_role = (r.get("role_as_described") or "").strip()
        yy0 = re.findall(r"20\d\d", r.get("article_date") or "")
        if re.search(r"\b(former|formerly|previous|previously|ex-)", raw_role, re.I) or (yy0 and int(yy0[0]) < 2025):
            press_dropped.append((q["name"], nm, "a former aide, or coverage from before 2025"))
            continue
        role = norm_role(raw_role, side)
        em, ph = (r.get("email") or "").strip(), (r.get("phone") or "").strip()
        alt = r.get("second_url") or ""
        if em and (not (V.check(url, em, "")[0] or V.check(alt, em, "")[0]) or em.lower() == (q["email"] or "").lower()):
            em = ""            # unconfirmed, or just the general inbox already in the row
        if ph and (not (V.check(url, "", ph)[1] or V.check(alt, "", ph)[1]) or digits(ph) in {digits(x) for o in q["offices"] for x in re.split(r" or ", o.get("phone") or "")}):
            ph = ""
        outlet = OUTLET_FIX.get(r.get("outlet") or "", r.get("outlet") or src_label(url, ""))
        yy = re.findall(r"20\d\d", r.get("article_date") or "")
        old_note = "Not found in 2026 coverage." if yy and int(yy[0]) < 2026 else ""
        label = "Listed on the candidate’s Citizens Union questionnaire" if "Citizens Union" in outlet else f"Named in {outlet}"
        kind = "press"
        site_host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", q.get("website") or "").split("/")[0])
        url_host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
        if re.search(r"press release|leadership page|team page|staff page|\boffice\b", outlet, re.I) or (site_host and url_host == site_host):
            kind, label = "research", url_host            # the office's own page, shown like any other office source
        if re.search(r"previously served|conflict", nts0, re.I):
            old_note = (old_note + " " if old_note else "") + "Coverage conflicts on whether this person still holds the job."
        if re.search(r"2025 (re-?election )?(campaign|race)|successful .* bid|win reelection", (r.get("role_as_described") or "") + " " + nts0, re.I) and side == "campaign":
            old_note = (old_note + " " if old_note else "") + "Worked on the 2025 campaign."
        nts = r.get("notes") or ""
        if re.search(r"\bmoved on\b|has since (left|moved)|may no longer speak for|now (leads|runs|heads)|left the campaign", nts, re.I):
            old_note = (old_note + " " if old_note else "") + "Later coverage says this person has moved on."
        elif re.search(r"through the primary|not seen in coverage after", nts, re.I):
            old_note = (old_note + " " if old_note else "") + "Quoted during the primary; not seen in coverage since."
        # a newer chief of staff in coverage replaces an older name the directory held without a contact
        if re.fullmatch(r"chief of staff", role, re.I):
            for ex in [x for x in q["staff"] if re.fullmatch(r"chief of staff", x["title"], re.I) and not (x.get("email") or x.get("phone")) and x.get("kind") != "press"]:
                q["staff"].remove(ex)
                press_dropped.append((q["name"], ex["name"], f"replaced by {nm}, named chief of staff in newer coverage"))
        q["staff"].append(dict(name=nm, title=role, email=em, phone=ph, src=url, src_label=label,
                               date=fmt_date(r.get("article_date") or ""), kind=kind, checked=True, caveat=old_note))
        press_rows.append((q["name"], nm, role, outlet))
if press_dropped:
    print("  press names left out:", press_dropped)
print(f"  press names added: {len(press_rows)}")

MAYOR_KEEP = re.compile(r"chief of staff|communications|press|spokes|intergovernmental|legislative affairs|first deputy mayor", re.I)
for p in P:
    main = {digits(x) for o in p["offices"] for x in re.split(r" or ", o.get("phone") or "")}
    for s_ in p["staff"]:
        if s_.get("phone") and digits(s_["phone"]) in main:
            s_["phone"] = ""                      # the switchboard, already in the row
            s_["src_label"] = s_["src_label"].replace("; phone from the city Green Book", "")
        if s_.get("kind") == "greenbook":
            s_["src_label"] = "City Green Book, updated " + fmt_date(s_.get("date") or "")
            s_["date"] = ""
    if p["id"] == "zohran-mamdani":
        p["staff"] = [x for x in p["staff"] if MAYOR_KEEP.search(x["title"]) or x.get("phone") or x.get("email")]
        p["links"]["see_also"] = dict(text="Deputy mayors, commissioners and the rest of the administration are in", label="the Mamdani administration org chart", url="../mamdani-org-chart/")
    # the same person listed twice under two spellings: the office's own page wins
    res = [x for x in p["staff"] if x.get("kind") != "greenbook"]
    for g in [x for x in p["staff"] if x.get("kind") == "greenbook"]:
        tg = set(name_tokens(g["name"])) - {"md", "dr", "esq"}
        for r_ in res:
            tr = set(name_tokens(r_["name"])) - {"md", "dr", "esq"}
            lg, lr = name_tokens(g["name"]), name_tokens(r_["name"])
            lg = [t for t in lg if t not in ("md", "dr", "esq")]
            lr = [t for t in lr if t not in ("md", "dr", "esq")]
            if not lg or not lr:
                continue
            a_, b_ = lg[-1].replace("-", ""), lr[-1].replace("-", "")
            last_ok = a_ == b_ or (len(a_) > 5 and a_ in b_) or (len(b_) > 5 and b_ in a_)
            if tg == tr or (last_ok and lg[0][:3] == lr[0][:3]):
                if tg == tr and name_tokens(g["name"]) != name_tokens(r_["name"]):
                    r_["name"] = "Dr. Ram Raju" if tg == {"ram", "raju"} else r_["name"]
                p["staff"].remove(g)
                break
    if p["links"].get("constituent_email") and p["links"]["constituent_email"] == p["email"]:
        p["links"].pop("constituent_email")
for p in P:
    seen = set()
    out = []
    for s in sorted(p["staff"], key=lambda s: (not (s.get("email") or s.get("phone")), rank(s["title"]), s["name"])):
        prev = next((o for o in out if strict_same(o["name"], s["name"])), None) if s["name"] else None
        if prev:
            prev["phone"] = prev.get("phone") or s.get("phone", "")
            prev["email"] = prev.get("email") or s.get("email", "")
            continue
        out.append(s)
    p["staff"] = out

# -------------------------------------------------- people who won on Nov. 3
epath = os.path.join(DATA, "elect_research.json")
checks = []
if os.path.exists(epath):
    er = json.load(open(epath))
    checks = er.get("checks", [])
    elect = [p for p in P if p["status"] != "sitting"]
    for r in er.get("people", []):
        hit = [p for p in elect if strict_same(p["name"], r.get("name", ""))] or \
              [p for p in elect if same_person(p["name"], r.get("name", ""))]
        if len(hit) != 1:
            if "Carl Wilson" not in r.get("name", ""):      # already seated; he is in the Council roster
                unmatched.append(("elect", r.get("name"), ""))
            continue
        p = hit[0]
        L = p["links"]
        m = re.match(r"https?://[^\s)]+", r.get("campaign_site") or "")
        site = m.group(0) if m else ""
        r["campaign_site"] = site
        joint = "kathyhochul.com" in site
        if site:
            p["website"] = site
            if joint:
                L["site_label"] = "Hochul-Adams campaign site"
        if (r.get("contact_form") or "").startswith("http") and r["contact_form"] != p["website"]:
            p["form"] = r["contact_form"]
        for field, src_field, dest in (("email", "email_source_url", "email"), ("press_email", "press_source_url", "press")):
            val = (r.get(field) or "").strip()
            if "@" not in val:
                continue
            ok, _, state = V.check(r.get(src_field) or r.get("campaign_site") or "", val, "")
            if not ok:
                print(f"  dropped unconfirmed {field} for {p['name']}: {val} ({state})")
                continue
            if dest == "email":
                p["email"], p["email_kind"] = val, ("Hochul campaign" if joint else "campaign")
            else:
                L["press_email"] = val
            p["sources"].append(dict(label="Campaign site", url=r.get(src_field) or r.get("campaign_site")))
        ph = (r.get("phone") or "").strip()
        if re.search(r"\d{3}.*\d{4}", ph):
            _, ok, state = V.check(r.get("phone_source_url") or r.get("campaign_site") or "", "", ph)
            if ok:
                p["offices"].append(dict(label="Campaign phone", addr=[], phone=ph, fax=""))
            else:
                print(f"  dropped unconfirmed phone for {p['name']}: {ph} ({state})")
        if r.get("background") and r.get("background") != "not found":
            bg = r["background"]
            q = bg.find(': "')
            first = bg
            if q > 0:
                m = re.search(r"^(.*?[a-z0-9)])\.\s+(?:[A-Za-z][\w&/' ]*?)(?:,\s*(?:Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, \d{4})?$", bg[:q], re.S)
                first = m.group(1) if m else bg[:q].split(". ")[0]
            if first:
                L["background"] = first.rstrip(".") + "."
                L["background_src"] = r.get("background_source_url") or ""
        soc = r.get("social")
        if isinstance(soc, str) and soc.startswith("http"):
            L["social"] = [dict(label="Social", url=soc)]
        elif isinstance(soc, list):
            L["social"] = [dict(label=s.get("label", "Social"), url=s["url"]) for s in soc if isinstance(s, dict) and s.get("url", "").startswith("http")]
        elif isinstance(soc, dict):
            L["social"] = [dict(label=k.capitalize(), url=v) for k, v in soc.items() if isinstance(v, str) and v.startswith("http")]

# ---------------------------------------------------- reported facts, each read from the page cited
REPORTED = {
    # Assembly 23: within six points in the count, but the opponent conceded.
    "ad23-elect-pesach-osina": dict(
        status="elect",
        note="Republican Thomas Sullivan conceded on election night, the Queens Daily Eagle reported.",
        url="https://queenseagle.com/all/2026/11/3/pesach-osina-claims-victory-in-closely-watched-south-queens-assembly-race"),
    "sd12-elect-aber-kawas": dict(
        note="The seat has been vacant since Michael Gianaris left the Senate Aug. 7, 2026, NY1 reported.",
        url="https://ny1.com/nyc/all-boroughs/inside-city-hall/2026/08/06/sen--gianaris-reflects-his-time-in-office"),
    "lg-elect-adrienne-adams": dict(
        note="The Associated Press projected the Hochul-Adams ticket the winner on election night, amNewYork reported.",
        url="https://www.amny.com/politics/nyc-midterm-election-results-governor-house-11032026/"),
}
for pid, f in REPORTED.items():
    q = byid.get(pid) or next((x for x in P if x["id"] == pid), None)
    if not q:
        print("  ! REPORTED id not found:", pid)
        continue
    if f.get("status"):
        q["status"] = f["status"]
        q["race"]["outcome"] = "elected"
        prev = next((x for x in P if x["id"] == q["links"].get("succeeds_id")), None)
        if prev and prev.get("race"):
            prev["race"]["outcome"] = "leaving"
            prev["links"]["term_ends"] = "Dec. 31, 2026"
    q["links"]["reported"] = f["note"]
    q["links"]["reported_src"] = f["url"]
    if pid.startswith("sd12"):
        q["links"]["succeeds_note"] = ""

if unmatched:
    print("  UNMATCHED research rows:", unmatched)
if stale_dropped:
    print("  left out as too old (2022 or earlier):", stale_dropped)

# A shared inbox (press@, info@, scheduling@) reaches an office, not a person. It is shown and labelled,
# and it does not count as a staff member's own contact.
SHARED = re.compile(r"^(press|media|info|contact|office|team|hello|schedul\w*|communications|comms|pressoffice|press\.office|webmail|"
                    r"gethelp|action|district\d+|d\d+[a-z]*|\w*schedul\w*|\w*press\w*|\w*inquir\w*|ask\w*|lgny)$", re.I)
for p in P:
    keep = []
    for s_ in p["staff"]:
        em = s_.get("email") or ""
        if em and p["email"] and em.lower() == p["email"].lower():
            s_["email"] = em = ""                       # the general inbox, already in the row
        if em and SHARED.match(em.split("@")[0]):
            s_["shared"] = True
            if not s_.get("name") and not s_.get("phone"):
                # an inbox with no person attached belongs with the office's contacts, not under "Named staff"
                lab = "scheduling_email" if "schedul" in (s_.get("title") or em).lower() else "press_email"
                p["links"].setdefault(lab, em)
                continue
        keep.append(s_)
    p["staff"] = keep
for p in P:
    for s_ in p["staff"]:
        pass
    for src in p["sources"]:
        src["label"] = src["label"].replace("November ", "Nov. ").replace("October ", "Oct. ")
# de-duplicate sources per person
for p in P:
    seen, out = set(), []
    for s in p["sources"]:
        if s["url"] not in seen:
            seen.add(s["url"])
            out.append(s)
    p["sources"] = out

# -------------------------------------------------------------- page framing
NOTES = {
    "U.S. Senate": "Senators publish no email addresses. Each takes written messages through a web form.",
    "U.S. House": "Thirteen congressional districts take in part of the city. House members publish no email addresses; each office takes written messages through a web form and answers the phone at its district offices.",
    "Statewide": "",
    "State Senate": "The 28 Senate districts that include part of the five boroughs. District 12 has been vacant since before the election.",
    "State Assembly": "The 65 Assembly districts in the five boroughs, 23 through 87.",
    "Citywide": "",
    "Borough presidents": "",
    "District attorneys": "Each county elects its own district attorney.",
    "City Council": "All 51 members. Each has a district office and a legislative office at 250 Broadway.",
}
order = ["U.S. Senate", "U.S. House", "Statewide", "State Senate", "State Assembly", "Citywide",
         "Borough presidents", "District attorneys", "City Council"]
sections = [dict(name=s, count=sum(1 for p in P if p["section"] == s), note=NOTES[s]) for s in order]

n_sit = sum(1 for p in P if p["status"] == "sitting")
n_new = sum(1 for p in P if p["status"] == "elect")
n_lead = sum(1 for p in P if p["status"] == "leading")
staff_all = [(p, s) for p in P for s in p["staff"]]
n_staff = len(staff_all)
own = lambda s: bool(s.get("phone") or (s.get("email") and not s.get("shared")))
n_staff_contact = sum(1 for _, s in staff_all if own(s))
n_staff_email = sum(1 for _, s in staff_all if s.get("email") and not s.get("shared"))
n_staff_research = sum(1 for _, s in staff_all if s.get("kind") == "research" and own(s))
n_off_with = sum(1 for p in P if p["status"] == "sitting" and any(own(s) for s in p["staff"]))
n_member_email = sum(1 for p in P if p["status"] == "sitting" and p["email"])

def num(n):
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    return words[n] if 0 <= n < 10 else str(n)


n_staff_phone = sum(1 for _, s in staff_all if s.get("phone"))
LEDE = (f"Phone numbers, emails and office addresses for the {n_sit} people elected to represent the five boroughs "
        f"in Washington, Albany and City Hall, from the two U.S. senators down to the 51 City Council members. "
        f"For {n_off_with} of those offices the page also names staff members and gives a direct line or address "
        f"that the office has published for them: {n_staff_contact} people in all, {n_staff_email} with an email address of their own "
        f"and {n_staff_phone} with a phone number of their own. Shared inboxes such as press@ are shown but not counted.")
n_press = sum(1 for _, s in staff_all if s.get("kind") == "press")
n_press_off = sum(1 for p in P if any(s.get("kind") == "press" for s in p["staff"]))
LEDE_PRESS = (f"Where an office publishes little or nothing about its staff, the page gives the name of the person news coverage "
              f"most recently identified as speaking for the official: {n_press} names across {n_press_off} offices and campaigns, each linked to the article.")
LEDE2 = (f"{num(n_new).capitalize()} people won seats on Nov. 3, 2026 that they do not hold yet"
         + (f", and {num(n_lead)} more {'leads a race' if n_lead == 1 else 'lead races'} too close to treat as settled" if n_lead else "")
         + ". They appear beside the officials they are set to replace in January.")

SOURCES_HTML = """
<ul>
<li>Congress: the <a href="https://clerk.house.gov/xml/lists/MemberData.xml">House Clerk’s member roster</a>, the <a href="https://www.senate.gov/general/contact_information/senators_cfm.xml">Senate’s contact directory</a> and each member’s own office page.</li>
<li>Albany: each senator’s contact page on <a href="https://www.nysenate.gov/senators-committees">nysenate.gov</a> and the Assembly’s <a href="https://nyassembly.gov/mem/">member directory</a>.</li>
<li>City Council: the Council’s <a href="https://council.nyc.gov/districts/">district roster</a> and each member’s page.</li>
<li>Statewide, citywide and borough offices: each office’s own contact page, linked in its row.</li>
<li>Direct lines for senior staff in city offices: the city’s Green Book, by way of <a href="https://joshgreenman1973.github.io/nyc-green-book/">the Greener Book</a>. The Green Book can lag after staff changes.</li>
<li>Other named staff: staff pages, press releases and newsletters the offices published. For Congress, also the invitee lists attached to House Clerk travel filings, the Senate Radio-TV Gallery’s press secretary list and an archive of the offices’ own emailed releases. Each entry links to the page it was read from.</li>
</ul>"""
RULE_HTML = f"""
<p>An address or number appears here only if a page published it. None was built from a naming pattern, even where the pattern is plain.</p>
<p>Staff contacts were gathered by searching the web, which can return an address that only looks right. So each one was checked a second way: the cited page was downloaded again and searched for the same characters. Contacts that failed that check were left out. {n_staff_research} researched staff contacts passed it.</p>
<p>Entries marked “Named in” come from news coverage, not from the office. Each article was downloaded and checked for the person’s name. They carry no contact unless the article prints one, and a spokesperson quoted last month may have moved on.</p>
<p>Members of Congress, the governor and the mayor publish no personal email address. Their rows give the web form and the people around them.</p>
<p>Press secretaries change jobs often. Check the date beside a staff entry before relying on it.</p>"""
RESULTS_HTML = f"""
<p>Winners come from the New York City Board of Elections’ <a href="https://enr.boenyc.gov/">unofficial election night results</a>, last updated {asof.replace(' EST','')} Eastern with about 97% of scanners reporting. They are not certified, and absentee and affidavit ballots were still to be counted.</p>
<p>For four districts that cross the city line (the 3rd and 16th Congressional, the 34th and 36th State Senate) the city count covers only the city portion.</p>
<p>A race is marked “not final” where the leader was ahead by fewer than six percentage points in that count.</p>
<p>New members of Congress take office Jan. 3, 2027. State offices change hands Jan. 1, 2027.</p>"""
CAUTION = ("The idea for this directory, who belongs in it and how it should look came from the author (a human). "
           "The code that gathered and assembled it was written by Anthropic’s Claude and Claude Code, under close direction. "
           "The quality checks: every roster was read from the government body that publishes it; every address and phone number typed in by hand "
           "was checked by script against a saved copy of the page it came from, and the build stops if one is missing; every staff contact found "
           "by web search was re-downloaded from its source and matched character for character before it was allowed in; and election winners "
           "were taken from the Board of Elections’ own count. The risks of using AI remain. Staff rosters go stale quickly. "
           "Please flag anything that looks wrong.")

turn_title = "Changing hands in January"
turn_note = (f"{num(n_new).capitalize()} seats that represent the city will have a new occupant"
             + (f"; {num(n_lead)} more {'is' if n_lead == 1 else 'are'} close" if n_lead else "") + ". Each name links to its row below.")

payload = dict(people=P, sections=sections, turn_title=turn_title, turn_note=turn_note)
tpl = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
rep = {"{{DATA}}": json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
       "{{BUILT}}": BUILT, "{{LEDE}}": LEDE, "{{LEDE2}}": LEDE2, "{{LEDE_PRESS}}": LEDE_PRESS, "{{SOURCES_HTML}}": SOURCES_HTML,
       "{{RULE_HTML}}": RULE_HTML, "{{RESULTS_HTML}}": RESULTS_HTML, "{{CAUTION}}": CAUTION,
       "{{N_SITTING}}": str(n_sit), "{{N_NEW}}": str(n_new)}
for k, v in rep.items():
    tpl = tpl.replace(k, v)
assert "{{" not in tpl.split('<script id="data"')[0], "unfilled placeholder"
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(tpl)

# ------------------------------------------------------------------- CSVs
with open(os.path.join(DATA, "directory.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["Name", "Office", "Body", "Level", "District", "Boroughs", "Party", "Status", "Email", "Email type",
                "Press email", "Main phone", "Main office", "Other offices", "Website", "Web form", "Named staff with contact",
                "Source", "Read on"])
    for p in P:
        offs = p["offices"]
        fmt = lambda o: f"{o['label']}: {', '.join(o.get('addr') or [])} {o.get('phone') or ''}".strip()
        status = {"sitting": "In office", "elect": f"Won Nov. 3, takes office {p['links'].get('takes_office','')}",
                  "leading": "Leads unofficial count, not final"}[p["status"]]
        if p["status"] == "sitting" and p["links"].get("successor"):
            status = f"In office until {p['links'].get('term_ends','January')}" if (p.get("race") or {}).get("outcome") == "leaving" else "In office; race not final"
        w.writerow([p["name"], p["role"], p["body"], p["level"], p["seat"], "; ".join(p["area"]) + (f"; {p['beyond']}" if p["beyond"] else ""),
                    p["party"], status, p["email"], p["email_kind"] if p["email"] else "", p["links"].get("press_email", ""),
                    next((o["phone"] for o in offs if o.get("phone")), ""), fmt(offs[0]) if offs else "",
                    " | ".join(fmt(o) for o in offs[1:]), p["website"], p["form"],
                    sum(1 for s in p["staff"] if s.get("phone") or (s.get("email") and not s.get("shared"))),
                    p["sources"][0]["url"] if p["sources"] else "", BUILT])
with open(os.path.join(DATA, "staff.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["Staff name", "Title", "Works for", "Office", "District", "Email", "Shared inbox?", "Phone", "How we know", "Source page", "Source date", "Caution"])
    for p, s in staff_all:
        how = "named in press coverage" if s.get("kind") == "press" else "city Green Book" if s.get("kind") == "greenbook" else "office's own page or release"
        w.writerow([s["name"], s["title"], p["name"], p["role"], p["seat"], s.get("email", ""), "yes" if s.get("shared") else "",
                    s.get("phone", ""), how, s.get("src", ""), s.get("date", ""), s.get("caveat", "")])

print(f"  {len(P)} people: {n_sit} sitting, {n_new} elected, {n_lead} leading")
print(f"  staff: {n_staff} named, {n_staff_contact} with a contact ({n_staff_email} emails); "
      f"{n_off_with} offices have at least one; {n_staff_research} from research")
print(f"  sitting officials with their own email: {n_member_email}")
print(f"  index.html {os.path.getsize(os.path.join(ROOT, 'index.html'))//1024} KB")
