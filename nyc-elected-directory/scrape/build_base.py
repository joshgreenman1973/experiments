#!/usr/bin/env python3
"""Build data/base.json: every elected official who represents New York City,
read off the official rosters saved in raw/ by fetch.sh.

Nothing here is typed from memory. Rosters are parsed; the handful of offices
whose pages have no common layout (House district offices, statewide and
citywide executives) are written out below, and every address line and phone
number written out is checked against the saved page it came from. If a string
is not on the page, the build stops.
"""
import html
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
DATA = os.path.join(ROOT, "data")
FETCHED = "2026-11-10"

BORO_ORDER = ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]


def read(path):
    with open(os.path.join(RAW, path), encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def cf_decode(hexstr):
    """Cloudflare hides published addresses behind data-cfemail. Decoding it is
    reading the page, not guessing: the bytes are the address XORed with a key."""
    k = int(hexstr[:2], 16)
    return "".join(chr(int(hexstr[i:i + 2], 16) ^ k) for i in range(2, len(hexstr), 2))


def page_text(path):
    raw = read(path)
    raw = re.sub(r'<a[^>]*data-cfemail="([0-9a-f]+)"[^>]*>.*?</a>',
                 lambda m: cf_decode(m.group(1)), raw, flags=re.S)
    raw = re.sub(r'<span[^>]*data-cfemail="([0-9a-f]+)"[^>]*>.*?</span>',
                 lambda m: cf_decode(m.group(1)), raw, flags=re.S)
    soup = BeautifulSoup(raw, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup, [l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip()]


def squash(s):
    s = html.unescape(s).replace(" ", " ").replace("​", "").replace("﻿", "")
    s = s.replace("’", "'").replace("–", "-")
    return re.sub(r"[\s,]+", " ", s).strip().lower()


_page_cache = {}


def must_have(path, *needles):
    """Stop the build if a hand-entered string is not on the saved page."""
    if path not in _page_cache:
        _, lines = page_text(path)
        # addresses that sit only in a mailto: link are on the page too
        mails = re.findall(r"mailto:([^\"'?>\s]+)", read(path))
        _page_cache[path] = squash(" ".join(lines + mails))
    hay = _page_cache[path]
    for n in needles:
        if n and squash(n) not in hay:
            sys.exit(f"NOT ON PAGE {path}: {n!r}")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def name_tokens(n):
    n = strip_accents(n).lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n)
    n = re.sub(r"[^a-z\- ]", " ", n)
    return [t for t in n.split() if len(t) > 1]


def same_person(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    sa = set(ta) | {p for t in ta for p in t.split("-")}
    sb = set(tb) | {p for t in tb for p in t.split("-")}
    return ta[-1] in sb or tb[-1] in sa


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(s).lower()).strip("-")


def boro_sort(bs):
    return sorted(bs, key=BORO_ORDER.index)


PEOPLE = []


def add(**kw):
    p = dict(
        id="", name="", role="", body="", level="", section="", district=None,
        seat="", area=[], beyond="", party="", status="sitting", status_note="",
        email="", email_kind="", offices=[], website="", form="", sources=[],
        staff=[], race=None, links={}, notes="",
    )
    p.update(kw)
    if not p["id"]:
        p["id"] = slug(p["name"])
    PEOPLE.append(p)
    return p


# ---------------------------------------------------------------- districts
DB = json.load(open(os.path.join(RAW, "district_boroughs.json")))
BEYOND = {  # districts that also take in territory outside the five boroughs
    "cd_3": "Nassau County", "cd_16": "Westchester County",
    "sd_34": "Westchester County", "sd_36": "Westchester County",
}


def area_for(key):
    return boro_sort([b for b, pct in DB.get(key, []) if pct >= 1])


def ad_boro(n):
    if 23 <= n <= 40:
        return ["Queens"]
    if 41 <= n <= 60:
        return ["Brooklyn"]
    if 61 <= n <= 63:
        return ["Staten Island"]
    if n == 64:
        return ["Brooklyn", "Staten Island"]
    if 65 <= n <= 76:
        return ["Manhattan"]
    if 77 <= n <= 87:
        return ["Bronx"]
    return []


PARTY = {"D": "Democrat", "R": "Republican"}

# ------------------------------------------------------------------ federal
HOUSE_XML = "https://clerk.house.gov/xml/lists/MemberData.xml"
SENATE_XML = "https://www.senate.gov/general/contact_information/senators_cfm.xml"

# District offices, as each member's own site lists them. (page, [(label, [address lines], phone, fax)])
HOUSE_OFFICES = {
    "03": ("house/ny03.off.html", "https://suozzi.house.gov/contact/offices", [
        ("Douglaston district office", ["242-09 Northern Boulevard", "Douglaston, NY 11363"], "(718) 631-0400", ""),
        ("Glen Cove district office", ["51 Glen Street, Second Floor", "Glen Cove, NY 11542"], "(516) 861-1070", ""),
    ]),
    "05": ("house/ny05.off.html", "https://meeks.house.gov/contact/offices", [
        ("Jamaica district office", ["153-01 Jamaica Avenue, 2nd floor", "Jamaica, NY 11432"], "(718) 725-6000", "(718) 725-9868"),
        ("Rockaway Peninsula district office", ["67-12 Rockaway Beach Boulevard", "Arverne, NY 11692"], "(347) 230-4032", "(347) 230-4045"),
    ]),
    "06": ("house/ny06.off.html", "https://meng.house.gov/contact/offices", [
        ("Flushing district office", ["40-13 159th St, STE A", "Flushing, NY 11358"], "(718) 358-6364", "(718) 445-7868"),
        ("Forest Hills district office (by appointment only)", ["118-35 Queens Blvd, STE 900", "Forest Hills, NY 11375"], "", ""),
    ]),
    "07": ("house/ny07.off.html", "https://velazquez.house.gov/contact/offices", [
        ("Brooklyn district office", ["266 Broadway, Suite 201", "Brooklyn, NY 11211"], "(718) 599-3658", ""),
        ("Sunnyside district office", ["39-16 47th Avenue", "Sunnyside, NY 11104"], "(718) 340-6244", ""),
    ]),
    "08": ("house/ny08.home.html", "https://jeffries.house.gov/", [
        ("Central Brooklyn district office", ["55 Hanson Place, Suite 603", "Brooklyn, NY 11217"], "(718) 237-2211", ""),
        ("South Brooklyn district office", ["445 Neptune Avenue, 1st Floor, Community Room 2C", "Brooklyn, NY 11224"], "(718) 373-0033", ""),
    ]),
    "09": ("house/ny09.home.html", "https://clarke.house.gov/", [
        ("Brooklyn office", ["222 Lenox Road, Suite 1&2", "Brooklyn, NY 11226"], "(718) 287-1142", "(718) 287-1223"),
    ]),
    "10": ("house/ny10.off.html", "https://goldman.house.gov/contact/offices", [
        ("Manhattan district office", ["Ted Weiss Federal Building, 290 Broadway, Suite 291", "New York, NY 10007"], "(212) 822-7878", ""),
        ("Brooklyn district office", ["Industry City, 254 36 Street, B-329", "Brooklyn, NY 11232"], "(718) 312-7575", ""),
    ]),
    "11": ("house/ny11.off.html", "https://malliotakis.house.gov/contact/offices", [
        ("Staten Island district office", ["1698 Victory Blvd, Suite 2L", "Staten Island, NY 10314"], "(718) 568-2870", ""),
        ("Brooklyn district office", ["7716 Third Avenue", "Brooklyn, NY 11209"], "(718) 306-1620", ""),
    ]),
    "12": ("house/ny12.home.html", "https://nadler.house.gov/", [
        ("Manhattan office", ["201 Varick Street, Suite 669", "New York, NY 10014"], "212-367-7350", ""),
    ]),
    "13": ("house/ny13.off.html", "https://espaillat.house.gov/contact/offices", [
        ("Harlem district office", ["163 West 125th Street, #508 Harlem State Office Building", "New York, NY 10027"], "(212) 663-3900", ""),
        ("Washington Heights district office", ["720 West 181st Street, Suite 2", "New York, NY 10033"], "(212) 497-5959", ""),
        ("Bronx district office (by appointment only)", ["Bronx, NY 10463"], "(646) 740-3632", ""),
    ]),
    "14": ("house/ny14.off.html", "https://ocasio-cortez.house.gov/contact/offices", [
        ("Hunts Point office (walk-ins Monday through Thursday)", ["1231 Lafayette Ave, Ste L-610", "Bronx, NY 10474"], "718-662-5970", ""),
        ("Astoria office (by appointment only)", ["30-83 31st St.", "Queens, NY 11102"], "718-662-5970", ""),
    ]),
    "15": ("house/ny15.off.html", "https://ritchietorres.house.gov/contact", [
        ("Bronx office (no walk-ins)", ["540 E Fordham Rd., Suite 2A", "Bronx, NY 10458"], "(718) 503-9610", ""),
    ]),
    "16": ("house/ny16.off.html", "https://latimer.house.gov/contact/office-contact-information", [
        ("Bronx district office", [], "(718) 530-7888", ""),
        ("White Plains district office", [], "(914) 323-5550", ""),
    ]),
}
HOUSE_BUILDINGS = {"CHOB": "Cannon House Office Building", "LHOB": "Longworth House Office Building",
                   "RHOB": "Rayburn House Office Building"}


def federal():
    sites = json.load(open(os.path.join(RAW, "house_sites.json")))
    root = ET.fromstring(read("house_clerk.xml"))
    pub = root.get("publish-date")
    for m in root.iter("member"):
        sd = (m.findtext("statedistrict") or "").strip()
        if not sd.startswith("NY") or sd[2:] not in HOUSE_OFFICES:
            continue
        d = sd[2:]
        info = m.find("member-info")
        name = (info.findtext("official-name") or "").strip()
        room = (info.findtext("office-room") or "").strip()
        bld = (info.findtext("office-building") or "").strip()
        phone = (info.findtext("phone") or "").strip()
        site = sites[d]["site"]
        page, url, offs = HOUSE_OFFICES[d]
        offices = [dict(label="Washington office",
                        addr=[f"{room} {HOUSE_BUILDINGS.get(bld, bld)}", "Washington, DC 20515"],
                        phone=phone, fax="")]
        for label, addr, ph, fx in offs:
            for line in addr:
                for part in line.split(", "):
                    must_have(page, part)
            must_have(page, ph, fx)
            offices.append(dict(label=label, addr=addr, phone=ph, fax=fx))
        # the form a constituent is sent to from the member's own site
        soup, _ = page_text(f"house/ny{d}.home.html")
        form = ""
        for a in soup.find_all("a", href=True):
            if re.search(r"email me|contact", a.get_text(" ", strip=True), re.I):
                h = a["href"]
                h = "https:" + h if h.startswith("//") else (site + h if h.startswith("/") else h)
                if h.startswith("http") and h.rstrip("/") != site:
                    form = h
                    break
        key = f"cd_{int(d)}"
        add(id=f"cd{int(d)}-{slug(name)}", name=name, role="U.S. representative",
            body="U.S. House of Representatives", level="Federal", section="U.S. House",
            district=int(d), seat=f"{ordinal(d)} Congressional District",
            area=area_for(key), beyond=BEYOND.get(key, ""),
            party=PARTY.get((info.findtext("party") or "").strip(), ""),
            offices=offices, website=site, form=form or site + "/contact",
            email_kind="none",
            sources=[dict(label=f"House Clerk member roster, published {pub}", url=HOUSE_XML),
                     dict(label="Member's office page", url=url)])

    senate_pages = {"Schumer": ("house/schumer.home.html", "https://www.schumer.senate.gov/",
                                ["780 Third Avenue, Suite 2301", "New York, NY 10017"], "(212) 486-4430", "(212) 486-7803"),
                    "Gillibrand": ("house/gillibrand.home.html", "https://www.gillibrand.senate.gov/",
                                   ["885 Third Avenue, Suite 2402", "New York, NY 10022"], "(212) 688-6262", "(866) 824-6340")}
    sroot = ET.fromstring(read("senate.xml"))
    for m in sroot.iter("member"):
        if (m.findtext("state") or "").strip() != "NY":
            continue
        last = m.findtext("last_name").strip()
        page, url, addr, ph, fx = senate_pages[last]
        for line in addr:
            must_have(page, line)
        must_have(page, ph, fx)
        dc = m.findtext("address").strip()
        dc_lines = [dc.replace(" Washington DC 20510", ""), "Washington, DC 20510"]
        add(name=f"{m.findtext('first_name').strip()} {last}", role="U.S. senator",
            body="U.S. Senate", level="Federal", section="U.S. Senate", seat="New York, statewide",
            area=BORO_ORDER[:], party=PARTY.get(m.findtext("party").strip(), ""),
            offices=[dict(label="New York City office", addr=addr, phone=ph, fax=fx),
                     dict(label="Washington office", addr=dc_lines, phone=m.findtext("phone").strip(), fax="")],
            website=m.findtext("website").strip().rstrip("/"), form=m.findtext("email").strip(),
            email_kind="none",
            notes=(m.findtext("leadership_position") or "").strip(),
            sources=[dict(label="U.S. Senate contact directory", url=SENATE_XML),
                     dict(label="Senator's office locations", url=url)])


# ------------------------------------------------------------- state senate
PH = re.compile(r"\(?\b\d{3}\)?[\s.\-]\s?\d{3}[\s.\-]\d{4}")


def state_senate():
    slugs = json.load(open(os.path.join(RAW, "senate_slugs.json")))
    nyc = set(list(range(10, 35)) + [36, 47, 59])
    for sl, v in sorted(slugs.items(), key=lambda x: x[1]["district"]):
        n = v["district"]
        if n not in nyc:
            continue
        path = f"senate/{sl}.contact.html"
        soup, lines = page_text(path)
        offices = []
        for loc in soup.select(".location.vcard"):
            ll = [l.strip() for l in loc.get_text("\n", strip=True).split("\n") if l.strip()]
            # walk up for the office title
            title = ""
            blk = loc.find_parent(class_=re.compile("c-office|office"))
            node = loc
            for _ in range(6):
                node = node.parent
                if node is None:
                    break
                h = node.find(class_=re.compile("office-info--title|c-office-info--title"))
                if h:
                    title = h.get_text(" ", strip=True)
                    break
            addr, phone, fax = [], "", ""
            i = 0
            while i < len(ll):
                l = ll[i]
                if l.lower().startswith("phone"):
                    nxt = l.split(":", 1)[1].strip() or (ll[i + 1] if i + 1 < len(ll) else "")
                    phone = nxt
                    i += 2 if not l.split(":", 1)[1].strip() else 1
                    continue
                if l.lower().startswith("fax"):
                    nxt = l.split(":", 1)[1].strip() or (ll[i + 1] if i + 1 < len(ll) else "")
                    fax = nxt
                    i += 2 if not l.split(":", 1)[1].strip() else 1
                    continue
                if l.lower().startswith(("office hours", "map", "email")):
                    break
                addr.append(l)
                i += 1
            # join "City," "NY" "ZIP" fragments into one line
            joined, buf = [], ""
            for a in addr:
                if a.endswith(",") or re.fullmatch(r"[A-Z]{2}", a) or re.fullmatch(r"\d{5}(-\d{4})?", a):
                    buf = (buf + " " + a).strip()
                else:
                    if buf:
                        joined.append(buf)
                        buf = ""
                    joined.append(a)
            if buf:
                joined.append(buf)
            if not title:
                title = "Albany office" if any("Albany" in a for a in joined) else "District office"
            title = title.replace("Office", "office")
            if joined or phone:
                offices.append(dict(label=title, addr=joined, phone=phone if PH.search(phone or "") else "",
                                    fax=fax if PH.search(fax or "") else ""))
        emails = []
        raw = read(path)
        for e in re.findall(r"mailto:([^\"'?>\s]+)", raw):
            e = e.strip().lower()
            if e.endswith("@nysenate.gov") and e not in emails:
                emails.append(e)
        offices.sort(key=lambda o: "albany" in o["label"].lower())
        name = v["name"]
        raw_party = v["party_raw"]
        party = "Democrat" if raw_party.startswith("D") else "Republican" if raw_party.startswith("R") else raw_party
        key = f"sd_{n}"
        add(id=f"sd{n}-{slug(name)}", name=name, role="State senator", body="New York State Senate",
            level="State", section="State Senate", district=n, seat=f"{ordinal(n)} Senate District",
            area=area_for(key), beyond=BEYOND.get(key, ""), party=party,
            email=emails[0] if emails else "", email_kind="member" if emails else "none",
            offices=offices, website=f"https://www.nysenate.gov/senators/{sl}",
            form=f"https://www.nysenate.gov/senators/{sl}/contact",
            sources=[dict(label="State Senate contact page", url=f"https://www.nysenate.gov/senators/{sl}/contact")])


# ----------------------------------------------------------------- assembly
def assembly():
    soup = BeautifulSoup(read("assembly_index.html"), "html.parser")
    for sec in soup.select("section.mem-item"):
        a = sec.select_one("h3.mem-name a")
        sp = a.find("span")
        n = int(re.search(r"\d+", sp.get_text()).group())
        sp.extract()
        if not 23 <= n <= 87:
            continue
        name = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        href = a["href"]
        url = "https://nyassembly.gov" + href if href.startswith("/") else "https://nyassembly.gov/mem/" + href
        mail = sec.select_one('.mem-email a[href^="mailto:"]')
        email = mail["href"].split("mailto:", 1)[1].strip().lower() if mail else ""
        offices = []
        for blk in sec.select(".mem-address .full-addr"):
            ll = [l.strip() for l in blk.get_text("\n", strip=True).split("\n") if l.strip()]
            addr, phone, fax = [], "", ""
            for l in ll:
                if l.lower().startswith("fax"):
                    fax = l.split(":", 1)[1].strip()
                elif PH.fullmatch(l):
                    phone = phone or l
                else:
                    addr.append(l)
            albany = any("Albany" in x for x in addr)
            offices.append(dict(label="Albany office" if albany else "District office",
                                addr=addr, phone=phone, fax=fax))
        offices.sort(key=lambda o: o["label"] == "Albany office")
        add(id=f"ad{n}-{slug(name)}", name=name, role="Assembly member", body="New York State Assembly",
            level="State", section="State Assembly", district=n, seat=f"{ordinal(n)} Assembly District",
            area=ad_boro(n), email=email, email_kind="member" if email else "none",
            offices=offices, website=url,
            sources=[dict(label="Assembly member directory", url="https://nyassembly.gov/mem/")])


# ------------------------------------------------------------------ council
def council():
    soup = BeautifulSoup(read("council_districts.html"), "html.parser")
    for tr in soup.select("tbody tr"):
        dc = tr.select_one("td.sort-district")
        mc = tr.select_one("td.sort-member a")
        if not dc or not mc:
            continue
        n = int(dc.get_text(strip=True))
        listed = mc.get("data-member-name") or mc.get_text(strip=True)
        title = ""
        name = listed
        for t in ("Speaker", "Majority Leader", "Minority Leader", "Deputy Speaker", "Majority Whip", "Minority Whip"):
            if listed.startswith(t + " "):
                title, name = t, listed[len(t) + 1:]
        boro = tr.select_one("td.sort-borough").get_text(strip=True)
        party = tr.select_one("td.sort-party").get_text(strip=True)
        hoods = tr.select_one("td.sort-neighborhoods").get_text(" ", strip=True)
        mail = tr.select_one('a[href^="mailto:"]')
        email = mail["href"].split("mailto:", 1)[1].strip() if mail else ""
        url = mc["href"]
        _, lines = page_text(f"council/d{n}.html")
        offices = []
        seen_blocks = set()
        SKIP = re.compile(r"^(hours|office hours|visit us|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                          r"m-f|mon|other weekdays|summer office|regular business|open |walk-in|by appointment|for scheduling)", re.I)
        i = 0
        while i < len(lines):
            if re.fullmatch(r"(District|Legislative) Office", lines[i]):
                kind = lines[i].split()[0]
                j = i + 1
                cur = dict(label=f"{kind} office", addr=[], phone="", fax="")
                block = []
                while j < len(lines) and j < i + 22:
                    l = lines[j].replace("\u00a0", " ")
                    if re.fullmatch(r"(District|Legislative) Office", l) or l.startswith(("Send Email", "Visit the Council", "Staff Directory")):
                        break
                    nums = PH.findall(l)
                    if nums:
                        if "fax" in l.lower():
                            cur["fax"] = cur["fax"] or nums[0]
                        elif not cur["phone"]:
                            cur["phone"] = nums[0]
                        elif "phone 2" in l.lower():
                            cur["phone"] += " or " + nums[0]
                    elif "@" in l or SKIP.match(l) or len(l) > 70 or re.search(r"\d ?[ap]\.?m\b", l, re.I):
                        pass
                    else:
                        if cur["phone"] or cur["fax"]:      # a second office under the same heading
                            block.append(cur)
                            cur = dict(label=f"{kind} office", addr=[], phone="", fax="")
                        cur["addr"].append(l)
                    j += 1
                block.append(cur)
                for o in block:
                    if not (o["addr"] or o["phone"]):
                        continue
                    # a first line that names the office rather than a street
                    if len(o["addr"]) > 2 and not re.search(r"\d", o["addr"][0]):
                        o["label"] = o["addr"].pop(0).rstrip(":")
                    key = (tuple(o["addr"]), o["phone"])
                    if key not in seen_blocks and any(re.search(r"\d", x) for x in o["addr"]):
                        seen_blocks.add(key)
                        offices.append(o)
                i = j
            else:
                i += 1
        boros = [b.strip() for b in re.split(r",|/|&| and ", boro) if b.strip() in BORO_ORDER]
        add(id=f"cc{n}-{slug(name)}", name=name, role="Council member", body="New York City Council",
            level="City", section="City Council", district=n, seat=f"{ordinal(n)} Council District",
            area=boro_sort(boros) if boros else [boro], party=party, notes=title,
            email=email, email_kind="district office" if email else "none",
            offices=offices, website=url, links={"neighborhoods": hoods},
            sources=[dict(label="City Council district roster", url="https://council.nyc.gov/districts/"),
                     dict(label="Member's Council page", url=url)])


# --------------------------------------------------------------- executives
def executives():
    ALL = BORO_ORDER[:]

    # Governor and lieutenant governor: governor.ny.gov answers scripted requests
    # with a challenge page, so their rows are filled from the research file
    # (data/staff_exec.json), where each line carries its own source and quote.
    add(id="governor-kathy-hochul", name="Kathy Hochul", role="Governor", body="State of New York",
        level="State", section="Statewide", seat="Statewide", area=ALL, party="Democrat",
        website="https://www.governor.ny.gov", form="https://www.governor.ny.gov/content/governor-contact-form",
        email_kind="none", sources=[dict(label="Governor's office", url="https://www.governor.ny.gov")])
    add(id="lieutenant-governor-antonio-delgado", name="Antonio Delgado", role="Lieutenant governor",
        body="State of New York", level="State", section="Statewide", seat="Statewide", area=ALL,
        party="Democrat", website="https://www.ny.gov/lieutenant-governor", email_kind="none",
        sources=[dict(label="Lieutenant governor's page", url="https://www.ny.gov/lieutenant-governor")])

    must_have("exec/ag_contact.html", "The Capitol", "Albany NY 12224-0341", "1-800-771-7755", "Letitia James")
    add(name="Letitia James", role="Attorney general", body="State of New York", level="State",
        section="Statewide", seat="Statewide", area=ALL, party="Democrat",
        offices=[dict(label="Albany (mailing address)", addr=["The Capitol", "Albany, NY 12224-0341"],
                      phone="1-800-771-7755", fax="", phone_note="general helpline")],
        website="https://ag.ny.gov", form="https://ag.ny.gov/contact-attorney-general-letitia-james",
        email_kind="none",
        sources=[dict(label="Attorney general's contact page", url="https://ag.ny.gov/contact-attorney-general-letitia-james")])

    must_have("exec/osc_press.html", "press@osc.ny.gov", "518-474-4015", "212-383-1388", "Jennifer Freeman",
              "jfreeman@osc.ny.gov", "518-669-7444")
    add(name="Thomas P. DiNapoli", role="State comptroller", body="State of New York", level="State",
        section="Statewide", seat="Statewide", area=ALL, party="Democrat",
        offices=[dict(label="Press office, Albany", addr=[], phone="518-474-4015", fax=""),
                 dict(label="Press office, New York City", addr=[], phone="212-383-1388", fax="")],
        email="press@osc.ny.gov", email_kind="press office",
        website="https://www.osc.ny.gov", form="https://www.osc.ny.gov/help",
        staff=[dict(name="Jennifer Freeman", title="Communications director", email="jfreeman@osc.ny.gov",
                    phone="518-669-7444", src="https://www.osc.ny.gov/press", src_label="Comptroller's newsroom page",
                    date="", checked=True)],
        sources=[dict(label="Comptroller's newsroom page", url="https://www.osc.ny.gov/press")])

    # ---- city
    must_have("exec/mayor_contact.html", "Mayor Zohran Mamdani", "City Hall", "New York, NY 10007")
    add(name="Zohran Mamdani", role="Mayor", body="City of New York", level="City", section="Citywide",
        seat="Citywide", area=ALL, party="Democrat",
        offices=[dict(label="Mailing address", addr=["City Hall", "New York, NY 10007"], phone="", fax="")],
        website="https://www.nyc.gov/mayors-office", form="https://www.nyc.gov/mayors-office/contact-the-mayor",
        email_kind="none",
        sources=[dict(label="Contact the mayor", url="https://www.nyc.gov/mayors-office/contact-the-mayor")])

    must_have("exec/compt.html", "One Centre Street", "New York, NY 10007", "(212) 669-3916", "action@comptroller.nyc.gov")
    add(name="Mark Levine", role="Comptroller", body="City of New York", level="City", section="Citywide",
        seat="Citywide", area=ALL, party="Democrat",
        offices=[dict(label="Main office", addr=["One Centre Street", "New York, NY 10007"],
                      phone="(212) 669-3916", fax="", phone_note="help hotline")],
        email="action@comptroller.nyc.gov", email_kind="office inbox",
        website="https://comptroller.nyc.gov", form="https://comptroller.nyc.gov/about/contact-our-office/",
        sources=[dict(label="Comptroller's contact page", url="https://comptroller.nyc.gov/about/contact-our-office/")])

    must_have("exec/pa_home.html", "1 Centre Street 15th Floor North", "New York, NY 10007",
              "gethelp@advocate.nyc.gov", "(212) 669-7250")
    add(name="Jumaane D. Williams", role="Public advocate", body="City of New York", level="City",
        section="Citywide", seat="Citywide", area=ALL, party="Democrat",
        offices=[dict(label="Main office", addr=["David N. Dinkins Municipal Building", "1 Centre Street, 15th Floor North", "New York, NY 10007"],
                      phone="(212) 669-7250", fax="", phone_note="hotline")],
        email="gethelp@advocate.nyc.gov", email_kind="office inbox",
        website="https://advocate.nyc.gov",
        sources=[dict(label="Public advocate's site", url="https://advocate.nyc.gov/")])

    must_have("exec/council_speaker.html", "SpeakerMenin@council.nyc.gov", "(212) 788-7210")

    # ---- borough presidents
    _, mn = page_text("exec/bp_mn.html")
    mn_txt = " ".join(mn)
    mn_emails = re.findall(r"[A-Za-z0-9._%+\-]+@manhattanbp\.nyc\.gov", mn_txt)
    must_have("exec/bp_mn.html", "1 Centre Street, 19th floor", "431 West 125th Street", "212-669-8300", "212-531-1609")
    gi = cs = ""
    for i, l in enumerate(mn):
        if l == "General Inquiries" and i + 1 < len(mn) and "@" in mn[i + 1]:
            gi = mn[i + 1]
        if l == "Constituent Services" and i + 1 < len(mn) and "@" in mn[i + 1]:
            cs = mn[i + 1]
    add(name="Brad Hoylman-Sigal", role="Borough president", body="Borough of Manhattan", level="Borough",
        section="Borough presidents", seat="Manhattan", area=["Manhattan"], party="Democrat",
        offices=[dict(label="Main office", addr=["The David N. Dinkins Municipal Building", "1 Centre Street, 19th floor", "New York, NY 10007"], phone="212-669-8300", fax=""),
                 dict(label="Northern Manhattan office", addr=["431 West 125th Street", "New York, NY 10027"], phone="212-531-1609", fax="", phone_note="constituent services")],
        email=gi, email_kind="office inbox", links={"constituent_email": cs},
        website="https://www.manhattanbp.nyc.gov",
        sources=[dict(label="Manhattan borough president's site", url="https://www.manhattanbp.nyc.gov/")])

    _, bk = page_text("exec/bp_bk.html")
    bk_txt = " ".join(bk)
    must_have("exec/bp_bk.html", "209 Joralemon Street", "(718) 802-3700")
    bk_em = re.findall(r"[A-Za-z0-9._%+\-]+@brooklynbp\.nyc\.gov", bk_txt)
    bk_press = ""
    for i, l in enumerate(bk):
        if l.startswith("For Press Inquiries") and i + 1 < len(bk) and "@" in bk[i + 1]:
            bk_press = bk[i + 1]
    add(name="Antonio Reynoso", role="Borough president", body="Borough of Brooklyn", level="Borough",
        section="Borough presidents", seat="Brooklyn", area=["Brooklyn"], party="Democrat",
        offices=[dict(label="Brooklyn Borough Hall", addr=["209 Joralemon Street", "Brooklyn, NY 11201"], phone="(718) 802-3700", fax="")],
        email=bk_em[0] if bk_em else "", email_kind="office inbox", links={"press_email": bk_press},
        website="https://www.brooklynbp.nyc.gov", form="https://www.brooklynbp.nyc.gov/contact/",
        sources=[dict(label="Brooklyn borough president's contact page", url="https://www.brooklynbp.nyc.gov/contact/")])

    must_have("exec/bp_bx.html", "851 Grand Concourse, 3rd Floor", "Bronx, New York 10451", "(718) 590-3500",
              "(718) 590-3554", "(718) 590-3557", "webmail@bronxbp.nyc.gov", "pressinquiry@bronxbp.nyc.gov",
              "scheduling@bronxbp.nyc.gov")
    add(name="Vanessa L. Gibson", role="Borough president", body="Borough of the Bronx", level="Borough",
        section="Borough presidents", seat="Bronx", area=["Bronx"], party="Democrat",
        offices=[dict(label="Main office", addr=["851 Grand Concourse, 3rd Floor", "Bronx, NY 10451"], phone="(718) 590-3500", fax=""),
                 dict(label="Executive office", addr=[], phone="(718) 590-3557", fax=""),
                 dict(label="Constituent services", addr=[], phone="(718) 590-3554", fax="")],
        email="webmail@bronxbp.nyc.gov", email_kind="office inbox",
        links={"press_email": "pressinquiry@bronxbp.nyc.gov", "scheduling_email": "scheduling@bronxbp.nyc.gov"},
        website="https://bronxboropres.nyc.gov",
        sources=[dict(label="Bronx borough president's contact page", url="https://bronxboropres.nyc.gov/contact/")])

    must_have("exec/bp_qn.html", "120-55 Queens Blvd", "718-286-3000")
    add(name="Donovan Richards Jr.", role="Borough president", body="Borough of Queens", level="Borough",
        section="Borough presidents", seat="Queens", area=["Queens"], party="Democrat",
        offices=[dict(label="Queens Borough Hall", addr=["120-55 Queens Blvd., second floor", "Kew Gardens, NY 11424"], phone="718-286-3000", fax="")],
        email_kind="none", website="https://queensbp.nyc.gov", form="https://queensbp.nyc.gov/contact/",
        sources=[dict(label="Queens borough president's contact page", url="https://queensbp.nyc.gov/contact/")])

    must_have("exec/bp_si.html", "10 Richmond Terrace", "Borough Hall, Room 120", "718-816-2000")
    add(name="Vito Fossella", role="Borough president", body="Borough of Staten Island", level="Borough",
        section="Borough presidents", seat="Staten Island", area=["Staten Island"], party="Republican",
        offices=[dict(label="Staten Island Borough Hall", addr=["10 Richmond Terrace, Room 120", "Staten Island, NY 10301"], phone="718-816-2000", fax="")],
        email_kind="none", website="https://www.statenislandusa.com", form="https://www.statenislandusa.com/contact.html",
        sources=[dict(label="Staten Island borough president's contact page", url="https://www.statenislandusa.com/contact.html")])

    # ---- district attorneys
    must_have("exec/da_mn.html", "One Hogan Place", "New York, NY 10013", "212.335.9000")
    add(name="Alvin Bragg", role="District attorney", body="New York County", level="Borough",
        section="District attorneys", seat="Manhattan", area=["Manhattan"], party="Democrat",
        offices=[dict(label="Main office", addr=["One Hogan Place", "New York, NY 10013"], phone="212-335-9000", fax="")],
        email_kind="none", website="https://manhattanda.org", form="https://manhattanda.org/contact-us/",
        sources=[dict(label="Manhattan district attorney's contact page", url="https://manhattanda.org/contact-us/")])

    must_have("exec/da_bk_home.html", "District Attorney's Action Center", "350 Jay Street", "Brooklyn, NY 11201", "718-250-2340")
    add(name="Eric Gonzalez", role="District attorney", body="Kings County", level="Borough",
        section="District attorneys", seat="Brooklyn", area=["Brooklyn"], party="Democrat",
        offices=[dict(label="District attorney's action center", addr=["350 Jay Street", "Brooklyn, NY 11201"], phone="718-250-2340", fax="")],
        email_kind="none", website="https://www.brooklynda.org",
        sources=[dict(label="Brooklyn district attorney's site", url="https://www.brooklynda.org/")])

    must_have("exec/da_bx.html", "Darcel D. Clark", "718-590-2000")
    add(name="Darcel D. Clark", role="District attorney", body="Bronx County", level="Borough",
        section="District attorneys", seat="Bronx", area=["Bronx"], party="Democrat",
        offices=[dict(label="Main number", addr=[], phone="718-590-2000", fax="")],
        email_kind="none", website="https://www.bronxda.nyc.gov",
        sources=[dict(label="Bronx district attorney's contact page", url="https://www.bronxda.nyc.gov/html/contact/contact.shtml")])

    must_have("exec/da_qn.html", "125-01 Queens Boulevard", "Kew Gardens, New York 11415", "718.286.6000",
              "info@queensda.org", "qdacommunications@queensda.org", "718.286.6315")
    add(name="Melinda Katz", role="District attorney", body="Queens County", level="Borough",
        section="District attorneys", seat="Queens", area=["Queens"], party="Democrat",
        offices=[dict(label="Main office", addr=["125-01 Queens Boulevard", "Kew Gardens, NY 11415"], phone="718-286-6000", fax=""),
                 dict(label="Communications", addr=[], phone="718-286-6315", fax="")],
        email="info@queensda.org", email_kind="office inbox", links={"press_email": "qdacommunications@queensda.org"},
        website="https://queensda.org", form="https://queensda.org/contact-us/",
        sources=[dict(label="Queens district attorney's contact page", url="https://queensda.org/contact-us/")])

    must_have("exec/da_si.html", "130 Stuyvesant Place, 7th Floor", "Staten Island, NY 10301", "(718) 876-6300",
              "info@rcda.nyc.gov", "press@rcda.nyc.gov", "(718) 524-0188")
    add(name="Michael E. McMahon", role="District attorney", body="Richmond County", level="Borough",
        section="District attorneys", seat="Staten Island", area=["Staten Island"], party="Democrat",
        offices=[dict(label="Main office", addr=["130 Stuyvesant Place, 7th Floor", "Staten Island, NY 10301"], phone="(718) 876-6300", fax=""),
                 dict(label="Communications director", addr=[], phone="(718) 524-0188", fax="")],
        email="info@rcda.nyc.gov", email_kind="office inbox", links={"press_email": "press@rcda.nyc.gov"},
        website="https://www.statenislandda.org", form="https://www.statenislandda.org/contact/",
        sources=[dict(label="Staten Island district attorney's contact page", url="https://www.statenislandda.org/contact/")])


# ---------------------------------------------- Green Book direct lines (city)
GB_PATH = os.path.join(os.path.dirname(ROOT), "nyc-green-book", "docs", "data", "greenbook.json")
GB_KEEP = re.compile(
    r"chief of staff|deputy borough president|first deputy|press secretary|communications|"
    r"scheduler|scheduling|general counsel|counsel to|intergovernmental|constituent services|"
    r"community affairs|director, policy|policy director|chief assistant|first assistant|"
    r"executive secretary|legislative affairs|external affairs|deputy comptroller|public affairs|"
    r"deputy public advocate|chief administrative officer", re.I)
GB_MAP = {
    "Mayor, Office of the": "zohran-mamdani",
    "Comptroller": "mark-levine",
    "Public Advocate for the City of New York": "jumaane-d-williams",
    "Borough President - Manhattan": "brad-hoylman-sigal",
    "Borough President - Brooklyn": "antonio-reynoso",
    "Borough President - Bronx": "vanessa-l-gibson",
    "Borough President - Queens": "donovan-richards-jr",
    "Borough President - Staten Island": "vito-fossella",
}
GB_DA = {"New York County": "alvin-bragg", "Kings County": "eric-gonzalez", "Bronx County": "darcel-d-clark",
         "Queens County": "melinda-katz", "Richmond County": "michael-e-mcmahon"}
GB_URL = "https://joshgreenman1973.github.io/nyc-green-book/"


def green_book():
    if not os.path.exists(GB_PATH):
        print("  ! Greener Book data not found; skipping city direct lines")
        return
    gb = json.load(open(GB_PATH))
    upd = gb["sources"]["greenbook"]["updated"][:10]
    byid = {p["id"]: p for p in PEOPLE}
    n = 0
    for r in gb["people"]:
        if r.get("v") or not r.get("n"):
            continue
        target = GB_MAP.get(r["a"])
        if r["a"] == "District Attorney":
            div = " ".join(r.get("d") or [])
            target = next((v for k, v in GB_DA.items() if k in div), None)
        if not target or target not in byid:
            continue
        holder = byid[target]
        if same_person(r["n"], holder["name"]):
            if r.get("p"):
                holder["links"]["direct_line"] = r["p"]
            continue
        mayor = target == "zohran-mamdani"
        if not GB_KEEP.search(r["t"]) and not (mayor and re.search(r"deputy mayor|press|communications|chief", r["t"], re.I)):
            continue
        if target == "mark-levine" and not re.search(r"^chief of staff$|press secretary|^director, communications|first deputy comptroller|intergovernmental|public affairs|scheduling", r["t"], re.I):
            continue
        holder["staff"].append(dict(name=re.sub(r",? Esq\.?$", "", r["n"]), title=r["t"], email="",
                                    phone=r.get("p", ""), src=GB_URL,
                                    src_label=f"City Green Book, as updated {upd}", date=upd, checked=True,
                                    kind="greenbook"))
        n += 1
    print(f"  Green Book: {n} named staff with the city's listed lines")


# ------------------------------------------------------------------ results
def results():
    """Attach the Board of Elections' unofficial count to each seat, and add a
    row for anyone who won a seat they do not hold yet."""
    def parse(page, kind):
        t = read("enr/" + page)
        txt = re.sub(r"<[^>]+>", "|", t).replace("&nbsp;", " ")
        txt = re.sub(r"[ \t\r\n]+", " ", txt)
        txt = re.sub(r"(\| *)+", "|", txt)
        parts = re.split(r"\|(?=(?:Representative in Congress|State Senator|Member of the Assembly) \d+)", txt)
        out = {}
        for part in parts[1:]:
            m = re.match(r"[A-Za-z ]+ (\d+)\w+ [A-Za-z ]+District", part)
            if not m:
                continue
            n = int(m.group(1))
            seg = part.split("Totals by Candidate", 1)[1] if "Totals by Candidate" in part else part
            rows = re.findall(r"\|\d+\|([^|]+?) ?\|(?:([^|%\d][^|%]*?)\|)?(\d+)\|([\d.]+)%", seg)
            agg = {}
            for nm, party, v, pc in rows:
                nm = nm.strip()
                agg[nm] = agg.get(nm, 0) + int(v)
            parties = {}
            for nm, party, v, pc in re.findall(r"\|\d+\|([^|]+?) ?\|([^|%\d][^|%]*?) ?\|(\d+)\|([\d.]+)%", part.split("Totals by Candidate")[0]):
                parties.setdefault(nm.strip(), []).append(party.strip())
            tot = sum(agg.values())
            rk = sorted(agg.items(), key=lambda x: -x[1])
            rep = re.search(r"Scanners Reported: ?\|? ?([\d.]+) ?%", part)
            asof = re.search(r"Information As Of: ([^|]+)", part)
            out[n] = dict(cands=[dict(name=k, votes=v, pct=round(100 * v / tot, 1), parties=parties.get(k, []))
                                 for k, v in rk if k != "WRITE-IN"][:3],
                          total=tot, scanners=rep.group(1) if rep else "", asof=asof.group(1).strip() if asof else "")
        return out

    res = {"cd": parse("OFA3CY0PY3.html", "cd"), "sd": parse("OFA7CY0PY1.html", "sd"),
           "ad": parse("OFA8CY0PY15.html", "ad")}
    json.dump(res, open(os.path.join(DATA, "results_unofficial.json"), "w"), indent=1)
    meta = {"cd": ("U.S. House", "U.S. representative-elect", "U.S. House of Representatives", "Federal", "Congressional", "Jan. 3, 2027", "https://enr.boenyc.gov/OFA3CY0PY3.html"),
            "sd": ("State Senate", "State senator-elect", "New York State Senate", "State", "Senate", "Jan. 1, 2027", "https://enr.boenyc.gov/OFA7CY0PY1.html"),
            "ad": ("State Assembly", "Assembly member-elect", "New York State Assembly", "State", "Assembly", "Jan. 1, 2027", "https://enr.boenyc.gov/OFA8CY0PY15.html")}
    partial = {("cd", 3), ("cd", 16), ("sd", 34), ("sd", 36)}
    changes = []
    for kind, table in res.items():
        section, erole, body, level, word, start, url = meta[kind]
        for n, r in sorted(table.items()):
            top = r["cands"][0]
            second = r["cands"][1] if len(r["cands"]) > 1 else None
            margin = top["pct"] - (second["pct"] if second else 0)
            close = margin < 6
            inc = next((p for p in PEOPLE if p["section"] == section and p["district"] == n and p["status"] == "sitting"), None)
            race = dict(leader=top["name"], pct=top["pct"], second=second["name"] if second else "",
                        second_pct=second["pct"] if second else None, scanners=r["scanners"],
                        asof=r["asof"], url=url, city_portion_only=(kind, n) in partial, close=close)
            party = "Republican" if "Republican" in top["parties"][:1] else "Democrat" if "Democratic" in top["parties"][:1] else ""
            if inc and same_person(inc["name"], top["name"]):
                inc["race"] = dict(race, outcome="leading" if close else "re-elected")
                continue
            # someone else leads or won
            key = f"{kind}_{n}"
            if inc:
                inc["race"] = dict(race, outcome="trailing" if close else "leaving")
            new = add(id=f"{kind}{n}-elect-{slug(top['name'])}", name=top["name"], role=erole, body=body,
                      level=level, section=section, district=n, seat=f"{ordinal(n)} {word} District",
                      area=area_for(key) if kind != "ad" else ad_boro(n), beyond=BEYOND.get(key, ""),
                      party=party, status="leading" if close else "elect", email_kind="none",
                      race=dict(race, outcome="leading" if close else "elected"),
                      links={"takes_office": start, "succeeds": inc["name"] if inc else "", "succeeds_id": inc["id"] if inc else ""},
                      sources=[dict(label="NYC Board of Elections unofficial election night results", url=url)])
            if inc:
                inc["links"]["successor"] = top["name"]
                inc["links"]["successor_id"] = new["id"]
            changes.append((kind, n, inc["name"] if inc else "(vacant)", top["name"], round(margin, 1), "CLOSE" if close else ""))
    print("  seats changing hands or undecided:")
    for c in changes:
        print("    ", *c)


def main():
    federal()
    state_senate()
    assembly()
    council()
    executives()
    green_book()
    results()
    order = ["U.S. Senate", "U.S. House", "Statewide", "State Senate", "State Assembly", "Citywide",
             "Borough presidents", "District attorneys", "City Council"]
    PEOPLE.sort(key=lambda p: (order.index(p["section"]), p["district"] or 0, p["status"] != "sitting"))
    ids = [p["id"] for p in PEOPLE]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    json.dump(dict(fetched=FETCHED, people=PEOPLE), open(os.path.join(DATA, "base.json"), "w"),
              indent=1, ensure_ascii=False)
    from collections import Counter
    c = Counter((p["section"], p["status"]) for p in PEOPLE)
    for k, v in sorted(c.items(), key=lambda x: order.index(x[0][0])):
        print(f"  {k[0]:20} {k[1]:8} {v}")
    no_office = [p["name"] for p in PEOPLE if p["status"] == "sitting" and not p["offices"]]
    print("  sitting with no office parsed:", no_office)
    no_phone = [p["name"] for p in PEOPLE if p["status"] == "sitting" and not any(o["phone"] for o in p["offices"])]
    print("  sitting with no phone:", no_phone)


if __name__ == "__main__":
    main()
