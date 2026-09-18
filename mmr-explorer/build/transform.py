#!/usr/bin/env python3
"""Turn the raw MMR tables into the files the site reads.

Rules that took reading the data to work out, and that the site depends on:

* One row per indicator per month. The row dated June 1 of a fiscal year
  carries that year's full-year figure, whatever the reporting period says --
  school-year and calendar-year indicators land their annual number there too.
* acceptedvalueytd is fiscal-year-to-date. For additive indicators the monthly
  rows accumulate through the year; for the rest they are running averages.
* measurement_type TimeSpan covers two incompatible encodings and the title
  is the only thing that distinguishes them. Where the title names a colon
  pair -- "(minutes:seconds)", "(hours:minutes)" -- 6.41 means six hours and
  forty-one minutes. Where it names a single unit -- "(minutes)", "(days)" --
  the value is an ordinary decimal, and 39 of those 101 indicators publish
  fractions above .59, which settles it. FDNY response times carry no unit in
  the dataset at all; the published chapter labels every one of them
  "(minutes:seconds)", so they are decoded as such.
* The indicator title lies often enough that the description field is the
  only trustworthy statement of what is being counted. Carry it everywhere.
* Fiscal 2026 does not come from this table at all. The open data stops in
  March 2026; the finished year is read out of the printed report by
  build/pdf2026.py and merged here, flagged so the site can say which years
  came from where.
"""
import json, os, re, sys, math, datetime as dt
from collections import defaultdict, Counter

import stats as ST

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.abspath(os.path.join(HERE, "..", "data"))

FLAT = 0.01          # |relative change| under this reads as unchanged
MT_LIST = ["Number", "Percentage", "Currency", "TimeSpan", "Ratio"]
GEOTYPE = {"B": "Borough", "CB": "Community district", "PP": "Police precinct",
           "SD": "School district"}

# Agency chapter of the Fiscal 2026 Mayor's Management Report, as filed at
# nyc.gov/assets/operations/downloads/pdf/mmr2026/. Only mappings confirmed
# against the published chapter are listed; anything unconfirmed is left out
# and falls back to the report's own landing page.
MMR_BASE = "https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/"
CHAPTER = {a: a.lower() + ".pdf" for a in (
    "ACS BIC BOE CCHR CCRB CUNY DCAS DCLA DCP DCWP DDC DEP DFTA DHS DOB DOC "
    "DOE DOF DOHMH DOI DOP DOT DPR DSNY DVS DYCD EDC FDNY HPD HRA LAW LPC "
    "NYCEM NYCHA NYPD OATH OCME OTI SBS SCA TLC").split()}
CHAPTER.update({
    "3-1-1": "311.pdf",
    "NYCHH": "hhc.pdf",
    "DORIS": "dor.pdf",
    "BPL": "lib.pdf", "NYPL": "lib.pdf", "QPL": "lib.pdf",
    "VZ": "vision_zero.pdf",
})


def rows(name):
    p = os.path.join(RAW, name + ".ndjson")
    if not os.path.exists(p):
        sys.exit(f"FAIL: {p} missing. Run build/fetch.py first.")
    with open(p) as fh:
        for line in fh:
            yield json.loads(line)


NUMRE = re.compile(r"^-?[\d,]*\.?\d+$")
COLON_UNIT = re.compile(r"\(\s*(hours?\s*:\s*minutes?|minutes?\s*:\s*seconds?)\s*\)", re.I)
PLAIN_UNIT = re.compile(r"\((minutes?|hours?|days?|seconds?)\)", re.I)


def timespan_mode(row):
    """True when this indicator's TimeSpan values are h.mm / m.ss, not decimals."""
    title = row.get("indicator") or ""
    if COLON_UNIT.search(title):
        return True
    # FDNY files its response times with no unit in the title. The Fiscal 2026
    # chapter labels every one of them "(minutes:seconds)", e.g. "End-to-end
    # average response time to life-threatening medical emergencies by
    # ambulances (minutes:seconds) 10:17 10:43 10:52 11:21 13:09".
    if row.get("agency") == "FDNY" and "response time" in title.lower():
        return True
    return False


def timespan_unit(title):
    m = COLON_UNIT.search(title or "") or PLAIN_UNIT.search(title or "")
    return re.sub(r"\s*:\s*", ":", m.group(1).lower()) if m else None

def num(raw):
    """Parse a published cell. Anything that is not plainly a number is None."""
    if raw is None:
        return None
    s = str(raw).strip().replace(",", "").replace("$", "").replace("%", "")
    if not s or s.upper() in ("NA", "N/A", "*", "**", "-", "--", "NAN", "TBD"):
        return None
    if not NUMRE.match(s):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def timespan(v):
    """6.41 hours-and-minutes -> 6.6833 of the leading unit.

    Returns (decoded, ok). ok is False when the fraction exceeds .59, which
    cannot be a count of minutes or seconds: that value is left exactly as
    filed and flagged, rather than quietly turned into something it is not.
    """
    if v is None:
        return None, True
    whole = math.floor(abs(v))
    frac = round((abs(v) - whole) * 100)
    if frac > 59:
        return v, False
    out = whole + frac / 60.0
    return (-out if v < 0 else out), True


class Intern:
    def __init__(self):
        self.vals, self.idx = [], {}
    def __call__(self, s):
        s = (s or "").strip()
        if not s:
            return -1
        if s not in self.idx:
            self.idx[s] = len(self.vals)
            self.vals.append(s)
        return self.idx[s]



# ---------------------------------------------------------------------------
# Agency resources: what each agency spent and how many people it employed.
# The published labels drift in case, footnote markers and units, so every
# label is normalised before use and the unit is read off the label itself.
# ---------------------------------------------------------------------------
RES_KEYS = [
    ("exp", "expenditures"),
    ("rev", "revenues"),
    ("ot", "overtime paid"),
    ("cap", "capital commitments"),
    ("hsc", "human services contract budget"),
]

def _reslabel(s):
    s = (s or "").strip().lower()
    s = re.sub(r"\s*\(see [^)]*\)", "", s)
    s = re.sub(r"^-\s*", "", s)
    s = re.sub(r"\d+$", "", s).strip()
    return s


def resources():
    """agency -> fiscal year -> {exp, rev, ot, cap, hsc in $ millions; pers headcount}"""
    out = defaultdict(lambda: defaultdict(dict))
    names = {}
    # MMR current-year actuals are provisional. The next PMMR publishes final
    # prior-year actuals, so that later vintage wins. Never use current-year plans.
    for table in ("resources", "resources_pmmr"):
        for r in rows(table):
            a, fy = r.get("agency"), r.get("reporting_fiscal_year")
            if not a or not fy:
                continue
            fy = int(fy)
            report_fy = fy
            if table == "resources_pmmr":
                fy -= 1
            a = {"311": "3-1-1", "H + H": "NYCHH"}.get(a, a)
            if r.get("agency_name"):
                names.setdefault(a, r["agency_name"])
            lab = _reslabel(r.get("resource_indicators"))
            field = "previous_fy_actual" if table == "resources_pmmr" else "current_fy_projected_actual"
            v = num(r.get(field))
            if v is None:
                continue
            scale = 1.0
            if "($000,000)" in lab:
                lab_base = lab.split("($000,000)")[0].strip()
            elif "($000)" in lab:
                lab_base, scale = lab.split("($000)")[0].strip(), 0.001
            else:
                lab_base = lab
            if lab_base in ("personnel", "personnel (total ft and fte)"):
                out[a][fy]["pers"] = v
                key = "pers"
            elif lab_base == "personnel (uniformed)":
                out[a][fy]["_unif"] = v
                key = "unif"
            elif lab_base == "personnel (civilian)":
                out[a][fy]["_civ"] = v
                key = "civ"
            else:
                key = None
                for key, want in RES_KEYS:
                    if lab_base == want:
                        out[a][fy][key] = round(v * scale, 3)
                        break
                else:
                    key = None
            if key:
                out[a][fy].setdefault("_sources", {})[key] = {
                    "dataset": "nvzu-6t9y" if table == "resources_pmmr" else "4qmi-txnk",
                    "reportFy": report_fy, "field": field,
                    "status": "final prior-year actual" if table == "resources_pmmr" else "provisional actual",
                }
    for a in out:
        for fy, d in out[a].items():
            if "pers" not in d and "_unif" in d and "_civ" in d:
                d["pers"] = d["_unif"] + d["_civ"]
                d["_sources"]["pers"] = d["_sources"]["unif"]
            if "_unif" in d:
                d["unif"] = d.pop("_unif")
            if "_civ" in d:
                d["civ"] = d.pop("_civ")
    return {a: {str(fy): d for fy, d in sorted(v.items())} for a, v in out.items()}, names


YEARS = []


def main():
    global YEARS
    os.makedirs(OUT, exist_ok=True)

    meta = {}            # id -> latest metadata row
    meta_fy = {}         # id -> fiscal year that metadata came from
    direction_rows = defaultdict(dict)
    annual = defaultdict(dict)    # id -> {fy: raw value}
    ytd = defaultdict(dict)       # id -> {fy: {month: raw value}}
    agency_name = {}
    seen = 0
    unparsed = Counter()

    for r in rows("indicators"):
        seen += 1
        iid = r.get("id")
        if not iid:
            continue
        fy = r.get("fiscalyear")
        vd = r.get("valuedate") or ""
        if not fy or len(vd) < 7:
            continue
        fy = int(fy)
        month = int(vd[5:7])

        if iid not in meta or (fy, vd) >= meta_fy.get(iid, (0, "")):
            meta[iid] = r
            meta_fy[iid] = (fy, vd)
        if vd >= direction_rows[iid].get(fy, ("", 0))[0]:
            direction_rows[iid][fy] = (vd, {"Up": 1, "Down": -1}.get(r.get("desireddirection"), 0))
        if r.get("agency") and r.get("agency_name"):
            agency_name.setdefault(r["agency"], r["agency_name"])

        rawv = r.get("acceptedvalueytd")
        v = num(rawv)
        if v is None:
            if rawv not in (None, "", "NA"):
                unparsed[str(rawv)[:24]] += 1
            continue
        ytd[iid].setdefault(fy, {})[month] = v
        if month == 6:
            annual[iid][fy] = v

    years = sorted({fy for d in annual.values() for fy in d})
    global YEARS
    YEARS = years
    print(f"read {seen:,} rows / {len(meta):,} indicators / FY{years[0]}-FY{years[-1]}")
    if unparsed:
        print("  non-numeric cells kept out:", dict(unparsed.most_common(8)))

    # ---- fiscal years that are complete vs still running -------------------
    # A year is complete when its June rows carry values. The most recent year
    # in the extract may only run partway, and must never be charted as a year.
    latest_ytd_fy = max(fy for d in ytd.values() for fy in d)
    complete = [y for y in years if sum(1 for i in annual if y in annual[i]) > 500]
    latest_complete = max(complete)
    od_complete = latest_complete        # last year the OPEN DATA finished
    partial_through = 0
    if latest_ytd_fy > od_complete:
        months = {m for i in ytd for m in ytd[i].get(latest_ytd_fy, {})}
        # fiscal months run July(7)..June(6)
        order = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
        have = [m for m in order if m in months]
        partial_through = have[-1] if have else 0
    print(f"  open data complete through FY{latest_complete}; "
          f"FY{latest_ytd_fy} partial through month {partial_through}")

    # ---- build the indicator records ---------------------------------------
    S_svc, S_goal, S_desc, S_src = Intern(), Intern(), Intern(), Intern()
    agencies = sorted(agency_name, key=lambda a: agency_name[a])
    aidx = {a: i for i, a in enumerate(agencies)}
    DIR = {"Up": 1, "Down": -1}
    MT = MT_LIST
    FREQ = ["Monthly", "Quarterly", "Annually", "Bi-Annually", "PMMR/MMR"]
    RP = ["Fiscal Year", "Calendar Year", "School Year"]

    ind = []
    by_id = {}
    for iid, m in meta.items():
        a = m.get("agency")
        if a not in aidx:
            continue
        ts = m.get("measurement_type") == "TimeSpan" and timespan_mode(m)
        bad_years = {}
        series, raw_series = {}, {}
        for fy, v in annual[iid].items():
            if ts:
                dec, ok = timespan(v)
                series[fy] = dec
                raw_series[fy] = v
                if not ok:
                    bad_years[str(fy)] = ("filed as a decimal where every other year in this "
                                          "series is minutes and seconds")
            else:
                series[fy] = v
        pace = {}
        for fy, mv in ytd[iid].items():
            if len(mv) > 1 or fy == latest_ytd_fy:
                pace[fy] = {str(k): (timespan(v)[0] if ts else v) for k, v in sorted(mv.items())}
        rec = {
            "id": iid,
            "a": aidx[a],
            "n": (m.get("indicator") or "").strip(),
            "d": S_desc(m.get("description")),
            "g": S_goal(m.get("goal")),
            "s": S_svc(m.get("service")),
            "src": S_src(m.get("source")),
            "dir": DIR.get(m.get("desireddirection"), 0),
            "dirs": {str(y): value[1] for y, value in direction_rows[iid].items()},
            "mt": MT.index(m["measurement_type"]) if m.get("measurement_type") in MT else -1,
            "fq": FREQ.index(m["frequency"]) if m.get("frequency") in FREQ else -1,
            "rp": RP.index(m["reporting_period"]) if m.get("reporting_period") in RP else -1,
            "cr": 1 if m.get("critical") == "Yes" else 0,
            "rt": 1 if m.get("retired") == "Yes" else 0,
            "ad": 1 if m.get("additive") == "Yes" else 0,
            "mf": int(m.get("multiplication_factor") or 1),
            "gt": m.get("geotype") or "",
            "gv": m.get("geovalue") or "",
            "pid": m.get("parentid") or "",
            "ts": 1 if ts else 0,
            "tu": timespan_unit(m.get("indicator")) or "",
            "_geo": m.get("geo") == "Yes",
            "v": [round(series[y], 6) if y in series else None for y in YEARS],
            "p": pace,
        }
        is_pct = m.get("measurement_type") == "Percentage"
        rec["st"] = ST.series_stats(rec["v"], YEARS, rec["dir"], is_pct)
        sus = ST.suspect(rec["v"], YEARS, is_pct) or {}
        sus.update(bad_years)
        if sus:
            rec["sus"] = sus
        if ts:
            rec["vr"] = [raw_series.get(y) for y in YEARS]
        ind.append(rec)
        by_id[iid] = rec

    # The report explicitly changes this denominator in FY2026 (PDF p.321).
    # Keep every value visible, but do not score a crossing as a service change.
    for iid in ("2285", "3056", "3072", "3253"):
        if iid in by_id:
            by_id[iid]["breaks"] = [2026]
            by_id[iid]["definitionNote"] = "FY2026 includes branches closed for long-term renovations in the six-day opening measure. Earlier years use a different denominator. See the report's changes on PDF page 321."

    # ---- fiscal 2026, read out of the printed report ----------------------
    pdf_path = os.path.join(OUT, "fy2026.json")
    pdf = json.load(open(pdf_path)) if os.path.exists(pdf_path) else None
    pdf_meta = None
    if pdf:
        pfy = pdf["fy"]
        if pfy not in years:
            years.append(pfy)
            YEARS = years
        pi = years.index(pfy)
        placed = tgt = 0
        for rec in ind:
            while len(rec["v"]) < len(years):
                rec["v"].append(None)
            d = pdf["ind"].get(rec["id"])
            if not d:
                continue
            from_pdf = rec["v"][pi] is None
            if "v" in d and from_pdf:
                rec["v"][pi] = d["v"]
                placed += 1
            if "t26" in d or "t27" in d:
                rec["tgt"] = {k: d[k] for k in ("t26", "t27") if k in d}
                tgt += 1
            rec["pdf"] = {"p": d["p"], "raw": d.get("raw"), "valueSource": "pdf" if from_pdf else "open-data"}
            rec["pdf"]["directionBefore"] = rec["dir"]
            if pfy > od_complete:
                rec["dir"] = d.get("direction", rec["dir"])
                rec["dirs"][str(pfy)] = rec["dir"]
                original = {}
                rec["pdf"]["historyYears"] = [int(y) for y, v in d.get("history", {}).items() if v is not None]
                for y, value in d.get("history", {}).items():
                    if int(y) in years and value is not None:
                        j = years.index(int(y))
                        if rec["v"][j] != value:
                            original[y] = rec["v"][j]
                            rec["v"][j] = value
                if original:
                    rec["pdf"]["original"] = original
            if d.get("directionalTargets"):
                rec["targetDirections"] = d["directionalTargets"]
            if d.get("reviewNote"):
                rec["pdf"]["reviewNote"] = d["reviewNote"]
            if "restated" in d:
                # The printed report revised this series' earlier years. Both
                # versions ship so a reader can see exactly what changed.
                rec["pdf"]["restated"] = d["restated"]
        # stats have to be recomputed now that the series runs a year longer
        for rec in ind:
            is_pct = rec["mt"] == MT_LIST.index("Percentage") if rec["mt"] >= 0 else False
            rec["st"] = ST.series_stats(rec["v"], YEARS, rec["dir"], is_pct)
            sus = ST.suspect(rec["v"], YEARS, is_pct) or {}
            sus.update(rec.get("sus") or {})
            rec["sus"] = sus or None
            if not rec["sus"]:
                rec.pop("sus", None)
        latest_complete = max(od_complete, pfy)
        pdf_meta = pdf["source"]
        print(f"  fiscal {pfy} from the printed report: {placed:,} figures, {tgt:,} with targets")


    nvals = sum(1 for r in ind if any(v is not None for v in r["v"]))
    for rec in ind:
        segment = max(rec.get("breaks", [0]))
        clean = [None if str(y) in rec.get("sus", {}) or y < segment else v for y, v in zip(YEARS, rec["v"])]
        rec["st"] = ST.series_stats(clean, YEARS, rec["dir"], rec["mt"] == 1)
    print(f"  {len(ind):,} indicator records, {nvals:,} with a full-year figure")

    payload = {
        "builtAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceRows": seen,
        "agencies": [{"c": a, "n": agency_name[a], "mmr": CHAPTER.get(a, "")}
                     for a in agencies],
        "svc": S_svc.vals, "goal": S_goal.vals, "desc": S_desc.vals, "src": S_src.vals,
        "mt": MT, "fq": FREQ, "rp": RP, "geotype": GEOTYPE,
        "years": years, "latest": latest_complete,
        "pdfYear": pdf["fy"] if pdf else None,
        "pdfSource": pdf_meta,
        "pdfPageBase": "https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf#page=",
        "mmrBase": MMR_BASE,
        "dataset": "rbed-zzin",
        "datasetUrl": "https://data.cityofnewyork.us/City-Government/Mayor-s-Management-Report-Agency-Performance-Indica/rbed-zzin",
        "rowsUrl": "https://data.cityofnewyork.us/resource/rbed-zzin.json?$order=valuedate&id=",
        "mmrPage": "https://www.nyc.gov/site/operations/reports/mmr.page",
        "dmmr": "https://dmmr.nyc.gov/",
        "odLatest": od_complete,
        "partialFy": latest_ytd_fy if latest_ytd_fy > od_complete else None,
        "partialThrough": partial_through,
        "ind": [r for r in ind if not r["_geo"]],
    }
    # Geographic breakouts hang off a citywide parent. They would triple the
    # search index for no gain, so they ship per agency and load on demand.
    geo_dir = os.path.join(OUT, "geo")
    os.makedirs(geo_dir, exist_ok=True)
    for f in os.listdir(geo_dir):
        os.remove(os.path.join(geo_dir, f))
    kids = defaultdict(lambda: defaultdict(list))
    for r in ind:
        if r["_geo"]:
            kids[agencies[r["a"]]][r["pid"]].append(r)
    gtot = 0
    for a, d in kids.items():
        fn = os.path.join(geo_dir, re.sub(r"[^A-Za-z0-9_+-]", "_", a) + ".json")
        with open(fn, "w") as fh:
            json.dump(d, fh, separators=(",", ":"))
        gtot += os.path.getsize(fn)
    print(f"  wrote data/geo/ for {len(kids)} agencies  {gtot/1e6:.1f} MB total, "
          f"{sum(1 for r in ind if r['_geo']):,} breakout series")
    for r in ind:
        r.pop("_geo", None)
    own = {x["id"] for x in payload["ind"]}
    payload["hasGeo"] = sorted({pid for d in kids.values() for pid in d} & own)
    res, res_names = resources()
    payload["res"] = res
    print(f"  resources for {len(res)} agencies, "
          f"FY{min(int(y) for d in res.values() for y in d)}-"
          f"FY{max(int(y) for d in res.values() for y in d)}")

    # Month-by-month year-to-date lines are only wanted once a reader opens an
    # indicator, so they ship per agency and load on demand.
    pace_dir = os.path.join(OUT, "pace")
    os.makedirs(pace_dir, exist_ok=True)
    for f in os.listdir(pace_dir):
        os.remove(os.path.join(pace_dir, f))
    bucket = defaultdict(dict)
    for rec in ind:
        p = rec.pop("p")
        if p:
            bucket[agencies[rec["a"]]][rec["id"]] = p
    total = 0
    for a, d in bucket.items():
        fn = os.path.join(pace_dir, re.sub(r"[^A-Za-z0-9_+-]", "_", a) + ".json")
        with open(fn, "w") as fh:
            json.dump(d, fh, separators=(",", ":"))
        total += os.path.getsize(fn)
    print(f"  wrote data/pace/ for {len(bucket)} agencies  {total/1e6:.1f} MB total")

    with open(os.path.join(OUT, "indicators.json"), "w") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    sz = os.path.getsize(os.path.join(OUT, "indicators.json"))
    print(f"  wrote data/indicators.json  {sz/1e6:.1f} MB")
    return payload


if __name__ == "__main__":
    main()
