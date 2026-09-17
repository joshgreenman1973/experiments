#!/usr/bin/env python3
"""Read fiscal 2026 out of the printed Mayor's Management Report.

The city published the fiscal 2026 report on 17 September 2026. The open data
table behind it still stops in March 2026, so the finished year exists only in
a 544-page PDF. This reads it.

Nothing is matched by name. Printed row labels and dataset indicator names
disagree often enough that name matching would quietly attach the wrong number
to the wrong indicator -- three Department of City Planning goals each print a
row called "Median days for projects to enter public review". Instead every
printed row is located by requiring its fiscal 2022 to 2025 columns to equal
that indicator's own figures in the dataset. That identifies the row and proves
in the same step that nothing was restated.

The printed tables also carry something the open data has never published: the
target the agency set for each indicator. Those are read too.

Writes data/fy2026.json.
"""
import json, os, re, sys, math, difflib, hashlib, urllib.request, datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.abspath(os.path.join(HERE, "..", "data"))
PDF_URL = "https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf"
PDF = os.path.join(RAW, "mmr2026.pdf")
TXT = os.path.join(RAW, "mmr2026.txt")
FYS = [2022, 2023, 2024, 2025]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"

# Open Data agency code -> the chapter header printed in the report.
# Verified against the 60 headers the report actually prints; the five agencies
# with no fiscal 2026 chapter are the retired initiative sections.
CHAPTER = {
    "3-1-1": "311 CUSTOMER SERVICE CENTER",
    "ACS": "ADMINISTRATION FOR CHILDREN’S SERVICES",
    "BOE": "BOARD OF ELECTIONS",
    "BIC": "BUSINESS INTEGRITY COMMISSION",
    "CCHR": "CITY COMMISSION ON HUMAN RIGHTS",
    "CUNY": "CITY UNIVERSITY OF NEW YORK",
    "CCRB": "CIVILIAN COMPLAINT REVIEW BOARD",
    "DFTA": "DEPARTMENT FOR THE AGING",
    "DOB": "DEPARTMENT OF BUILDINGS",
    "DCP": "DEPARTMENT OF CITY PLANNING",
    "DCAS": "DEPARTMENT OF CITYWIDE ADMINISTRATIVE SERVICES",
    "DCWP": "DEPARTMENT OF CONSUMER AND WORKER PROTECTION",
    "DOC": "DEPARTMENT OF CORRECTION",
    "DCLA": "DEPARTMENT OF CULTURAL AFFAIRS",
    "DDC": "DEPARTMENT OF DESIGN AND CONSTRUCTION",
    "DOE": "DEPARTMENT OF EDUCATION",
    "DEP": "DEPARTMENT OF ENVIRONMENTAL PROTECTION",
    "DOF": "DEPARTMENT OF FINANCE",
    "DOHMH": "DEPARTMENT OF HEALTH AND MENTAL HYGIENE",
    "DHS": "DEPARTMENT OF HOMELESS SERVICES",
    "DOI": "DEPARTMENT OF INVESTIGATION",
    "DPR": "DEPARTMENT OF PARKS & RECREATION",
    "DOP": "DEPARTMENT OF PROBATION",
    "DORIS": "DEPARTMENT OF RECORDS & INFORMATION SERVICES",
    "DSNY": "DEPARTMENT OF SANITATION",
    "SBS": "DEPARTMENT OF SMALL BUSINESS SERVICES",
    "DOT": "DEPARTMENT OF TRANSPORTATION",
    "DVS": "DEPARTMENT OF VETERANS’ SERVICES",
    "DYCD": "DEPARTMENT OF YOUTH AND COMMUNITY DEVELOPMENT",
    "FDNY": "FIRE DEPARTMENT",
    "HPD": "HOUSING PRESERVATION AND DEVELOPMENT",
    "HRA": "HUMAN RESOURCES ADMINISTRATION",
    "LPC": "LANDMARKS PRESERVATION COMMISSION",
    "LAW": "LAW DEPARTMENT",
    "EDC": "NEW YORK CITY ECONOMIC DEVELOPMENT CORPORATION",
    "NYCEM": "NEW YORK CITY EMERGENCY MANAGEMENT",
    "NYCHA": "NEW YORK CITY HOUSING AUTHORITY",
    "NYPD": "NEW YORK CITY POLICE DEPARTMENT",
    "NYCHH": "NYC HEALTH + HOSPITALS",
    "OATH": "OFFICE OF ADMINISTRATIVE TRIALS AND HEARINGS",
    "OCME": "OFFICE OF CHIEF MEDICAL EXAMINER",
    "OTI": "OFFICE OF TECHNOLOGY AND INNOVATION",
    "BPL": "PUBLIC LIBRARIES", "NYPL": "PUBLIC LIBRARIES", "QPL": "PUBLIC LIBRARIES",
    "SCA": "SCHOOL CONSTRUCTION AUTHORITY",
    "TLC": "TAXI AND LIMOUSINE COMMISSION",
    "VZ": "COLLABORATING TO DELIVER RESULTS: VISION ZERO: BUILDING A SAFER CITY",
}


def fetch():
    if os.path.exists(PDF) and os.path.getsize(PDF) > 1_000_000:
        blob = open(PDF, "rb").read()
        return hashlib.sha256(blob).hexdigest(), len(blob), "local copy"
    req = urllib.request.Request(PDF_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        blob = r.read()
        last_mod = r.headers.get("Last-Modified", "")
    if len(blob) < 1_000_000 or blob[:5] != b"%PDF-":
        sys.exit(f"FAIL: {PDF_URL} did not return a PDF ({len(blob)} bytes)")
    os.makedirs(RAW, exist_ok=True)
    open(PDF, "wb").write(blob)
    return hashlib.sha256(blob).hexdigest(), len(blob), last_mod


def text_of():
    if os.path.exists(TXT) and os.path.getsize(TXT) > 100_000:
        return open(TXT).read()
    import pypdf
    reader = pypdf.PdfReader(PDF)
    parts = [f"\n<<<PAGE {i+1}>>>\n" + (p.extract_text() or "") for i, p in enumerate(reader.pages)]
    t = "".join(parts)
    open(TXT, "w").write(t)
    return t


def page_chapters(pages):
    """Chapter per page. Even pages print only the report's own name in the
    running head, so an unlabelled page inherits the chapters on either side."""
    hdr = {}
    for n, t in pages.items():
        for a, b in re.findall(r"^(?:Page \d+\s+\|\s+(.+)|(.+?)\s+\|\s+Page \d+)\s*$", t, re.M):
            s = (a or b).strip()
            if s and "MAYOR" not in s.upper():
                hdr[n] = s
                break
    labeled = sorted(hdr)
    out = {}
    for n in sorted(pages):
        if n in hdr:
            out[n] = {hdr[n]}
            continue
        before = [p for p in labeled if p < n]
        after = [p for p in labeled if p > n]
        out[n] = set()
        if before:
            out[n].add(hdr[before[-1]])
        if after:
            out[n].add(hdr[after[0]])
    return out


VAL = re.compile(r"^(?:NA|\*|†|‡|\$?-?[\d,]+(?:\.\d+)?%?|\d+:\d{2}(?::\d{2})?|\(?\d+(?:\.\d+)?\)?%?)$")
TREND = re.compile(r"^(?:Up|Down|Neutral|NA|\*|ñ|ò|Higher|Lower)$")


HEADER = re.compile(r"(Desired\s+Direction|5-?Year\s+Trend|Performance\s+Indicators|FY\d\d\s+FY\d\d\s+FY\d\d)", re.I)
# The marks the report sets in the margin. The symbol font puts several of
# them in the private use area, which is why \uf0ab and friends appear here
# alongside their ordinary Unicode twins.
BULLET = "\u00ab\u00ae\u2020\u2021\u25ba\u00a7\uf0ab\uf0ae\uf0a7\uf0b7\uf0a8\uf071\uf0d8"
HEADWORDS = re.compile(r"^(?:FY\s?\d\d|Desired|Direction|5-?Year|Trend|Actual|Target|Performance|Indicators|[" + BULLET + r"\s])+", re.I)
LEADDASH = re.compile(r"^[" + BULLET + r"\s]*[\u2013\u2014\-]\s")
SEP = re.compile(r"\s[\u2013\u2014]\s")


def join_wrapped(parts):
    """Rebuild a label split across lines. The report hyphenates at the break
    ("... - Eng -" / "lish Language Arts (%)"), so a fragment ending in a
    hyphen joins the next one with no space."""
    out = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.search(r"[A-Za-z]\s*-$", out):
            out = re.sub(r"\s*-$", "", out) + part
        else:
            out = (out + " " + part).strip()
    return re.sub(r"\s+", " ", out)


def strip_marks(s):
    return re.sub(r"^[" + BULLET + r"\s]+", "", s).strip()


def parse_rows(pages, chapters):
    """Indicator rows out of the performance tables.

    Columns run FY22 FY23 FY24 FY25 FY26 actual | FY26 target | FY27 target |
    5-year trend | desired direction, so the five actuals are the five tokens
    before the last four and the two targets are the two after them.

    Two things about the printed layout have to be handled or the labels come
    out wrong. The column header sits directly above the first row of every
    table and carries no figures, so it would be swallowed into that row's
    label. And sub-rows print only their own variant -- "- Heat", "- Math (%)"
    -- under a parent that carries the stem; the stem is the parent's label up
    to its own last dash, so "Students in grades 3 to 8 below standards -
    English Language Arts (%)" followed by "- Math (%)" reads as "Students in
    grades 3 to 8 below standards - Math (%)" and not as both at once.
    """
    rows = []
    stem = ""
    for pg in sorted(pages):
        chap = chapters.get(pg)
        if not chap:
            continue
        wrapped = []
        for raw in pages[pg].split("\n"):
            s = raw.strip()
            if not s or s.startswith("Critical Indicator"):
                wrapped = []
                continue
            if HEADER.search(s):
                wrapped, stem = [], ""
                continue
            toks = s.split()
            i = len(toks)
            while i > 0 and (VAL.match(toks[i - 1]) or TREND.match(toks[i - 1])):
                i -= 1
            tail, label = toks[i:], " ".join(toks[:i]).strip()
            if len(tail) >= 9 and i > 0:
                own = join_wrapped(wrapped + [label])
                if LEADDASH.match(own) and stem:
                    full = stem + " " + strip_marks(own)
                else:
                    full = strip_marks(own)
                    cut = list(SEP.finditer(full))
                    stem = full[:cut[-1].start()].strip() if cut else full
                full = HEADWORDS.sub("", full).strip() or full
                rows.append({
                    "page": pg, "chapters": sorted(chap),
                    "label": re.sub(r"\s+", " ", full).strip(),
                    "actuals": tail[-9:-4],
                    "t26": tail[-4], "t27": tail[-3],
                    "trend": tail[-2], "want": tail[-1], "line": s,
                })
                wrapped = []
            else:
                if len(s) < 200:
                    wrapped.append(s)
                wrapped = wrapped[-3:]
    return rows


def cell(t):
    """A printed cell as (value, decimals shown). Times print as h:mm and are
    converted to the same decimal-of-the-leading-unit the site stores."""
    if t is None:
        return None, None
    t = t.strip()
    if t in ("NA", "*", "", "†", "‡", "ñ", "ò", "Up", "Down", "Neutral"):
        return None, None
    neg = t.startswith("(") and t.endswith(")")
    t = t.replace("$", "").replace(",", "").replace("%", "").strip("()")
    m = re.match(r"^(\d+):(\d{2})$", t)
    if m:
        v = int(m.group(1)) + int(m.group(2)) / 60.0
        return (-v if neg else v), "time"
    try:
        v = float(t)
    except ValueError:
        return None, None
    dec = len(t.split(".")[1]) if "." in t else 0
    return (-v if neg else v), dec


def agrees(stored, printed_text):
    """Does the dataset's own figure round to what the report printed?"""
    p, dec = cell(printed_text)
    if p is None or stored is None:
        return None
    if dec == "time":
        return abs(stored - p) < 0.009
    return abs(round(stored, dec) - p) <= 10 ** (-dec) * 0.51 + 1e-9


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def main():
    sha, size, last_mod = fetch()
    text = text_of()
    parts = re.split(r"\n<<<PAGE (\d+)>>>\n", text)
    pages = {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}
    chapters = page_chapters(pages)
    rows = parse_rows(pages, chapters)
    print(f"{len(pages)} pages, {len(rows):,} indicator rows parsed, sha256 {sha[:12]}…")

    site = json.load(open(os.path.join(OUT, "indicators.json")))
    years = site["years"]
    yi = {y: i for i, y in enumerate(years)}
    codes = [a["c"] for a in site["agencies"]]

    # every indicator, citywide and geographic breakout alike
    inds = list(site["ind"])
    geo_dir = os.path.join(OUT, "geo")
    for fn in sorted(os.listdir(geo_dir)):
        for kids in json.load(open(os.path.join(geo_dir, fn))).values():
            inds.extend(kids)
    print(f"  {len(inds):,} indicators to place")

    by_chapter = defaultdict(list)
    for r in inds:
        ch = CHAPTER.get(codes[r["a"]])
        if ch:
            by_chapter[ch].append(r)
    rows_by_chapter = defaultdict(list)
    for row in rows:
        for ch in row["chapters"]:
            rows_by_chapter[ch].append(row)

    # ---- pair rows with indicators on history alone -----------------------
    pairs = defaultdict(list)     # indicator id -> [row]
    claimed = defaultdict(list)   # id(row)     -> [indicator]
    for ch, cands in by_chapter.items():
        for row in rows_by_chapter.get(ch, []):
            for rec in cands:
                ok = tot = 0
                for k, fy in enumerate(FYS):
                    stored = rec["v"][yi[fy]] if fy in yi else None
                    a = agrees(stored, row["actuals"][k])
                    if a is None:
                        continue
                    tot += 1
                    ok += 1 if a else 0
                if tot >= 3 and ok == tot:
                    pairs[rec["id"]].append(row)
                    claimed[id(row)].append(rec)

    def pick(options, name):
        """When history alone leaves more than one, the name has to win clearly."""
        if len(options) == 1:
            return options[0]
        scored = sorted(options, key=lambda o: difflib.SequenceMatcher(
            None, norm(name), norm(o["label"] if isinstance(o, dict) and "label" in o else o["n"])).ratio(), reverse=True)
        s = lambda o: difflib.SequenceMatcher(
            None, norm(name), norm(o["label"] if isinstance(o, dict) and "label" in o else o["n"])).ratio()
        if s(scored[0]) >= 0.72 and s(scored[0]) - s(scored[1]) >= 0.15:
            return scored[0]
        return None

    # ---- second pass: series the report has restated ----------------------
    # A row whose history is close to an indicator's but not equal to it has
    # been revised between the open data release and the printed report. The
    # police chapter's headline is one: the report prints 119,748 major
    # felonies for fiscal 2022 where the dataset says 119,313. Those rows are
    # accepted only on a much tighter leash -- every year within 1.5 per cent,
    # a name that clearly matches, and no competition -- and are carried
    # separately so the site can say the series was restated.
    restated = defaultdict(list)
    claimed_r = defaultdict(list)
    for ch, cands in by_chapter.items():
        for row in rows_by_chapter.get(ch, []):
            if claimed[id(row)]:
                continue
            for rec in cands:
                if pairs.get(rec["id"]):
                    continue
                if difflib.SequenceMatcher(None, norm(rec["n"]), norm(row["label"])).ratio() < 0.75:
                    continue
                ok = tot = 0
                for k, fy in enumerate(FYS):
                    stored = rec["v"][yi[fy]] if fy in yi else None
                    p, dec = cell(row["actuals"][k])
                    if stored is None or p is None:
                        continue
                    tot += 1
                    ok += 1 if abs(stored - p) <= max(abs(stored), abs(p)) * 0.015 else 0
                if tot >= 3 and ok == tot:
                    restated[rec["id"]].append(row)
                    claimed_r[id(row)].append(rec)

    out, amb_ind, amb_row = {}, 0, 0
    for rec in inds:
        opts = pairs.get(rec["id"], [])
        was_restated = False
        if not opts:
            opts = restated.get(rec["id"], [])
            if not opts or len(claimed_r[id(opts[0])]) > 1:
                continue
            was_restated = True
        row = pick(opts, rec["n"])
        if row is None:
            amb_ind += 1
            continue
        if len(claimed[id(row)]) > 1 and pick(claimed[id(row)], row["label"]) is not rec:
            amb_row += 1
            continue
        v, _ = cell(row["actuals"][4])
        t26, _ = cell(row["t26"])
        t27, _ = cell(row["t27"])
        if v is None and t26 is None and t27 is None:
            continue
        rowdata = {"p": row["page"], "lbl": row["label"][:160], "line": row["line"][:240]}
        if was_restated:
            rowdata["restated"] = [row["actuals"][k] for k in range(4)]
        if v is not None:
            rowdata["v"] = round(v, 6)
            rowdata["raw"] = row["actuals"][4]
        if t26 is not None:
            rowdata["t26"] = round(t26, 6)
        if t27 is not None:
            rowdata["t27"] = round(t27, 6)
        out[rec["id"]] = rowdata

    withval = sum(1 for d in out.values() if "v" in d)
    witht = sum(1 for d in out.values() if "t26" in d)
    withre = sum(1 for d in out.values() if "restated" in d)
    print(f"  {withre:,} of those sit on a series the report has restated since the open data release")
    print(f"  placed {len(out):,} indicators: {withval:,} with a fiscal 2026 figure, "
          f"{witht:,} with a fiscal 2026 target")
    print(f"  left out: {amb_ind:,} where several printed rows share an indicator's history, "
          f"{amb_row:,} where several indicators share a row's")

    if withval < 1500:
        sys.exit(f"FAIL: only {withval} fiscal 2026 figures placed; the parse or the layout changed")

    json.dump({
        "source": {
            "title": "Mayor's Management Report, Fiscal 2026",
            "publisher": "Mayor's Office of Operations, City of New York",
            "url": PDF_URL, "released": "2026-09-17",
            "sha256": sha, "bytes": size, "last_modified_header": last_mod,
            "retrieved": dt.date.today().isoformat(),
            "why": "NYC Open Data's indicator table (rbed-zzin) still carries fiscal 2026 only "
                   "through March, so the finished year is read from the printed report. Every "
                   "row is located by matching its fiscal 2022-2025 columns against the dataset's "
                   "own figures for the same indicator, never by name.",
        },
        "fy": 2026,
        "ind": out,
    }, open(os.path.join(OUT, "fy2026.json"), "w"), separators=(",", ":"))
    print(f"  wrote data/fy2026.json  {os.path.getsize(os.path.join(OUT, 'fy2026.json'))/1e6:.2f} MB")


if __name__ == "__main__":
    main()
