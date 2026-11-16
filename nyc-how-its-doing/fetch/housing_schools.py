#!/usr/bin/env python3
"""Fetcher for the "housing_schools" group of How New York Is Doing (edition: New York in 2025).

Run from the project folder:   python3 -I fetch/housing_schools.py
Offline rerun from the cache:  HS_OFFLINE=1 python3 -I fetch/housing_schools.py

Writes data/indicators/<id>.json for:
  new_homes, rental_vacancy, homelessness_pit, shelter_census, evictions,
  reading_proficiency, math_proficiency, naep_reading, graduation_rate,
  chronic_absenteeism, public_school_enrollment, child_care_seats
Raw downloads are cached under data/raw/housing_schools/.

Standard library only. Excel files are read with a small built-in xlsx reader (zipfile + XML).
PDFs are read with macOS PDFKit through osascript (JavaScript for Automation), because pdftotext is
not installed on this machine; the script stops with an error if that is unavailable.
Any empty or failed download raises an exception and exits non-zero.
"""
import csv
import datetime
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "housing_schools")
OUT = os.path.join(ROOT, "data", "indicators")
PEERS = json.load(open(os.path.join(ROOT, "data", "peers.json")))
REGISTRY = json.load(open(os.path.join(ROOT, "data", "registry.json")))
TODAY = datetime.date.today().isoformat()
UA = "Mozilla/5.0 (compatible; civic-data-fetcher/1.0)"
OFFLINE = os.environ.get("HS_OFFLINE") == "1"
SOCRATA = "https://data.cityofnewyork.us/resource/"
BORO_BY_DIGIT = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}

os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------
# Download helpers
# --------------------------------------------------------------------------------------------
def http_get(url, cache_name, min_bytes=200, expect=None, tries=6):
    """Download url into RAW/cache_name and return bytes. Retries with backoff on 403/429/5xx."""
    path = os.path.join(RAW, cache_name)
    if OFFLINE:
        if not os.path.exists(path):
            raise FetchError("offline mode but no cache for " + cache_name)
        return open(path, "rb").read()
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if len(data) < min_bytes:
                raise FetchError("download too small (%d bytes): %s" % (len(data), url))
            if expect == "pdf" and not data.startswith(b"%PDF"):
                raise FetchError("not a PDF: " + url)
            if expect == "xlsx" and not data.startswith(b"PK"):
                raise FetchError("not an xlsx/zip file: " + url)
            with open(path, "wb") as f:
                f.write(data)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(min(60, 3 * 2 ** i))
                continue
            raise FetchError("HTTP %s for %s" % (e.code, url))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(min(60, 3 * 2 ** i))
    raise FetchError("failed after retries: %s (%s)" % (url, last))


def soql(dataset, query, cache_name, allow_empty=False):
    """Run a SoQL query against NYC Open Data (keyless). 403 = throttling, retried with backoff."""
    url = SOCRATA + dataset + ".json?" + urllib.parse.urlencode({"$query": query})
    data = http_get(url, cache_name, min_bytes=2)
    rows = json.loads(data.decode("utf-8"))
    if isinstance(rows, dict):
        raise FetchError("SoQL error for %s: %s" % (dataset, str(rows)[:300]))
    if not rows and not allow_empty:
        raise FetchError("SoQL returned no rows: %s %s" % (dataset, query))
    return rows


def socrata_meta(dataset, cache_name):
    url = "https://data.cityofnewyork.us/api/views/%s.json" % dataset
    return json.loads(http_get(url, cache_name).decode("utf-8"))


# --------------------------------------------------------------------------------------------
# Minimal xlsx reader (standard library)
# --------------------------------------------------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _colidx(ref):
    s = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(data, only=None):
    z = zipfile.ZipFile(io.BytesIO(data))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rmap = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for sh in wb.find("m:sheets", _NS):
        name = sh.get("name")
        if only and name not in only:
            continue
        tgt = rmap[sh.get("{%s}id" % _NS["r"])].lstrip("/")
        tgt = tgt if tgt.startswith("xl/") else "xl/" + tgt
        rows = []
        for _, el in ET.iterparse(z.open(tgt)):
            if el.tag == "{%s}row" % _NS["m"]:
                row = {}
                for c in el.findall("m:c", _NS):
                    t = c.get("t")
                    v = c.find("m:v", _NS)
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
                    elif v is None:
                        continue
                    elif t == "s":
                        val = ss[int(v.text)]
                    elif t in ("str", "e"):
                        val = v.text
                    elif t == "b":
                        val = v.text == "1"
                    else:
                        try:
                            f = float(v.text)
                            val = int(f) if f.is_integer() else f
                        except ValueError:
                            val = v.text
                    row[_colidx(c.get("r"))] = val
                n = max(row) + 1 if row else 0
                rows.append([row.get(i) for i in range(n)])
                el.clear()
        out[name] = rows
    return out


def sheet_records(rows):
    """Turn a sheet (first row = header) into dicts."""
    hdr = [str(h).strip() if h is not None else "" for h in rows[0]]
    recs = []
    for r in rows[1:]:
        if not r or all(x is None for x in r):
            continue
        recs.append({hdr[i]: (r[i] if i < len(r) else None) for i in range(len(hdr))})
    return recs


# --------------------------------------------------------------------------------------------
# PDF text via macOS PDFKit (osascript JXA)
# --------------------------------------------------------------------------------------------
_JXA = r"""
ObjC.import('PDFKit');
function run(argv) {
  var doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
  if (!doc || doc.isNil()) { return ""; }
  var out = [];
  for (var i = 0; i < doc.pageCount; i++) {
    out.push("=== page " + (i + 1));
    out.push(ObjC.unwrap(doc.pageAtIndex(i).string));
  }
  return out.join("\n");
}
"""


def pdf_text(cache_name):
    """Extract text from a cached PDF; caches the text next to it as .txt."""
    pdf = os.path.join(RAW, cache_name)
    txt = pdf[:-4] + ".txt"
    if OFFLINE and os.path.exists(txt):
        return open(txt, encoding="utf-8").read()
    try:
        p = subprocess.run(["osascript", "-l", "JavaScript", "-", pdf], input=_JXA.encode(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    except FileNotFoundError:
        raise FetchError("osascript (macOS PDFKit) not available to read PDFs, and pdftotext is not installed")
    text = p.stdout.decode("utf-8", "replace")
    if p.returncode != 0 or len(text.strip()) < 50:
        raise FetchError("could not extract text from " + cache_name)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def flat(text):
    return " ".join(text.split())


def num(s):
    return float(str(s).replace(",", ""))


# --------------------------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------------------------
def reg(id_):
    for m in REGISTRY["measures"]:
        if m["id"] == id_:
            return m
    raise KeyError(id_)


def write_indicator(obj):
    m = reg(obj["id"])
    obj.setdefault("better", m["better"])
    if obj["status"] != "ok" and not obj.get("status_reason"):
        raise FetchError("status_reason required for " + obj["id"])
    if obj["status"] in ("ok", "partial") and not obj.get("series"):
        raise FetchError("empty series for " + obj["id"])
    for p in obj.get("series", []):
        if p["value"] is None:
            raise FetchError("null value in series for " + obj["id"])
    order = ["id", "status", "status_reason", "name", "definition", "units", "format", "better",
             "frequency", "series", "latest_period", "latest_extra", "source", "peers", "peer_series",
             "breakdowns", "method", "caveats"]
    out = {k: obj.get(k) for k in order}
    for k in obj:
        if k not in out:
            out[k] = obj[k]
    with open(os.path.join(OUT, obj["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    s = out["series"]
    print("  wrote %-26s status=%-7s %d points, latest %s = %s" % (
        obj["id"], out["status"], len(s), out.get("latest_period"), s[-1]["value"] if s else None))


def pt(period, value, moe=None):
    return {"period": str(period), "value": value, "moe": moe}


def peer_names():
    return {c["name"] for c in PEERS["cities"]}


# --------------------------------------------------------------------------------------------
# 1. New homes (DCP Housing Database) + Census BPS permits for peers
# --------------------------------------------------------------------------------------------
def new_homes():
    ds = "dbdt-5s7j"
    meta = socrata_meta(ds, "dcp_housingdb_cd_meta.json")
    mver = re.search(r"Current version:\s*([0-9A-Za-z.]+)", meta.get("description", ""))
    version = mver.group(1) if mver else None
    if not version:
        raise FetchError("could not read Housing Database version from dataset description")
    years = list(range(2010, 2027))
    cols = ", ".join("comp%d" % y for y in years)
    rows = soql(ds, "SELECT commntydst, %s LIMIT 500" % cols, "dcp_housingdb_by_cd.json")
    if len(rows) < 59:
        raise FetchError("Housing Database by CD returned only %d rows" % len(rows))
    tot = {y: 0.0 for y in years}
    boro = {}
    for r in rows:
        b = BORO_BY_DIGIT.get(str(r["commntydst"])[0])
        if b is None:
            raise FetchError("unknown community district code " + str(r["commntydst"]))
        for y in years:
            v = float(r.get("comp%d" % y) or 0)
            tot[y] += v
            boro.setdefault(b, {}).setdefault(y, 0.0)
            boro[b][y] += v
    series = [pt(y, int(round(tot[y]))) for y in range(2010, 2026)]

    # Peers: Census Building Permits Survey, place-level annual file, 2025
    regions = {"Northeast Region": "ne", "Midwest Region": "mw", "South Region": "so", "West Region": "we"}
    units = {}
    months = {}
    names = {}
    for reg_name, code in regions.items():
        url = "https://www2.census.gov/econ/bps/Place/%s/%s2025a.txt" % (urllib.parse.quote(reg_name), code)
        txt = http_get(url, "bps_place_%s2025a.txt" % code, min_bytes=10000).decode("latin-1")
        lines = txt.splitlines()
        for line in lines[3:]:
            f = next(csv.reader([line]))
            if len(f) < 30 or not f[0].strip().startswith("2025"):
                continue
            st, fips_place = f[1].strip(), f[5].strip()
            if not fips_place or fips_place == "00000":
                continue
            u = sum(int(float(f[i] or 0)) for i in (18, 21, 24, 27))  # 1, 2, 3-4, 5+ unit columns (units)
            key = (st, fips_place)
            units[key] = units.get(key, 0) + u
            months.setdefault(key, set()).add(f[15].strip())
            names.setdefault(key, []).append(f[16].strip())
    pvals = []
    missing = []
    # Indianapolis: peers.json uses the "balance" place (36003); BPS reports the consolidated city (36000).
    alias = {("18", "36003"): ("18", "36000")}
    for c in PEERS["cities"]:
        key = (c["state_fips"], c["place_fips"])
        if key not in units and key in alias:
            key = alias[key]
        if key not in units:
            missing.append(c["name"])
            continue
        pvals.append({"city": c["name"], "value": round(units[key] / c["pop2025"] * 1000, 2), "moe": None,
                      "geo_name": "%s, %s (BPS rows: %s; %d units permitted in 2025)" % (
                          c["census_name"], c["state"], "; ".join(sorted(set(names[key]))), units[key])})
    if len(pvals) < 20:
        raise FetchError("BPS matched only %d peer cities" % len(pvals))
    nyc_bps = units[("36", "51000")]
    peers = {
        "period": "2025",
        "geography": "city",
        "note": ("Different measure from the New York series: these are housing units authorized by building permits in "
                 "2025 per 1,000 residents (Census Bureau Building Permits Survey, annual place file; permit-issuing places "
                 "matched on state and FIPS place code, summing every county part; New York City is the sum of its five "
                 "borough rows), not net units completed. Permits lead completions by a year or more and are gross, not "
                 "net of demolitions. Population: Census Vintage 2025 city estimates from data/peers.json. "
                 "New York City: %d units permitted in 2025." % nyc_bps
                 + " Indianapolis: BPS reports the consolidated city (FIPS 36000), divided here by the population of the "
                 "balance (36003), so its rate is slightly overstated."
                 + (" No row of its own in the BPS place file, so left out: "
                    + ", ".join(missing) + "." if missing else "")),
        "source": {"name": "U.S. Census Bureau, Building Permits Survey, annual place-level files, 2025 (ne/mw/so/we2025a.txt)",
                   "url": "https://www.census.gov/construction/bps/index.html",
                   "endpoint": "https://www2.census.gov/econ/bps/Place/",
                   "fetched": TODAY},
        "values": sorted(pvals, key=lambda v: -v["value"]),
    }
    write_indicator({
        "id": "new_homes", "status": "ok", "status_reason": None,
        "name": "New homes completed",
        "definition": ("Net change in Class A (permanent) housing units from completed new buildings, alterations and "
                       "demolitions in New York City, by calendar year of completion."),
        "units": "units", "format": "int", "frequency": "annual",
        "series": series, "latest_period": "2025",
        "latest_extra": {"period": "2026 to date", "value": int(round(tot[2026])),
                         "note": ("Partial year: net units completed in 2026 so far in Housing Database release %s "
                                  "(DCP's quarterly release naming; this release runs through the second quarter of 2026). "
                                  "Not comparable with full-year totals." % version)},
        "source": {"name": "NYC Department of City Planning, Housing Database, Community District summary (release %s), NYC Open Data dbdt-5s7j" % version,
                   "url": "https://data.cityofnewyork.us/d/dbdt-5s7j",
                   "endpoint": SOCRATA + "dbdt-5s7j.json",
                   "fetched": TODAY},
        "peers": peers, "peer_series": None,
        "breakdowns": [{"by": "borough", "period": "2025", "source_url": "https://data.cityofnewyork.us/d/dbdt-5s7j",
                        "values": [{"name": b, "value": int(round(boro[b][2025])), "moe": None}
                                   for b in ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"]]}],
        "method": ("Summed the compYYYY columns (net Class A units completed in that calendar year) over all %d community-"
                   "district rows of DCP's Housing Database summary table, including joint interest areas, so the total "
                   "covers the whole city. 2010 uses the full-year column comp2010, not comp2010ap (April 1 to December 31). "
                   "Borough = first digit of the community district code." % len(rows)),
        "caveats": [
            "Net figure: units added by new buildings and alterations minus units removed by demolitions and alterations.",
            "DCP counts units as completed when the Department of Buildings issues a certificate of occupancy, so recent years can be revised upward in later releases as certificates are recorded.",
            "Counts only Class A (permanent) units in jobs filed with the Department of Buildings since 2010; it excludes hotels, dormitories and other Class B units.",
            "The 2026 figure is a partial year and is shown only as a latest reading.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 2. Rental vacancy (NYC Housing and Vacancy Survey publications)
# --------------------------------------------------------------------------------------------
HVS_BASE = "https://www.nyc.gov/assets/hpd/downloads/pdfs/about/"


def rental_vacancy():
    docs = {
        "1996": HVS_BASE + "1996%20NYCHVS%20Selected%20Initial%20Findings.pdf",
        "1999": HVS_BASE + "1999%20NYCHVS%20Selected%20Initial%20Findings.pdf",
        "2002": HVS_BASE + "2002%20NYCHVS%20Selected%20Initial%20Findings.pdf",
        "2005": HVS_BASE + "2005%20NYCHVS%20Selected%20Initial%20Findings.pdf",
        "2008": HVS_BASE + "2008%20NYCHVS%20Selected%20Initial%20Findings.pdf",
        "2011": HVS_BASE + "2011%20NYCHVS%20Selected%20Initial%20Findings.pdf",
        "2017": HVS_BASE + "2017-hvs-initial-findings.pdf",
        "2023": HVS_BASE + "2023-nychvs-selected-initial-findings.pdf",
    }
    titles = {
        "1996": "HPD, 1996 New York City Housing and Vacancy Survey report summary",
        "1999": "HPD, Selected Initial Findings of the 1999 NYCHVS",
        "2002": "HPD, Selected Initial Findings of the 2002 NYCHVS",
        "2005": "HPD, Selected Initial Findings of the 2005 NYCHVS",
        "2008": "HPD, Selected Initial Findings of the 2008 NYCHVS (Feb. 10, 2009)",
        "2011": "HPD, Selected Initial Findings of the 2011 NYCHVS (Feb. 9, 2012)",
        "2017": "HPD, Selected Initial Findings of the 2017 NYCHVS (Feb. 9, 2018)",
        "2023": "HPD, 2023 New York City Housing and Vacancy Survey Selected Initial Findings",
    }
    text = {}
    for y, url in docs.items():
        http_get(url, "hvs_%s_selected_initial_findings.pdf" % y, min_bytes=20000, expect="pdf")
        text[y] = flat(pdf_text("hvs_%s_selected_initial_findings.pdf" % y))

    def grab(doc, pattern, group=1):
        m = re.search(pattern, text[doc])
        if not m:
            raise FetchError("pattern not found in HVS %s document: %s" % (doc, pattern))
        return float(m.group(group))

    vals = {}  # year -> (value, doc, moe)
    m96 = re.search(r"risen from (\d\.\d\d) percent in 1984, to (\d\.\d\d) percent in 1987, (\d\.\d\d) percent in 1991", text["1996"])
    if not m96:
        raise FetchError("1984/1987/1991 sentence not found in 1996 HVS document")
    vals["1984"] = (float(m96.group(1)), "1996", None)
    vals["1987"] = (float(m96.group(2)), "1996", None)
    vals["1991"] = (float(m96.group(3)), "1996", None)
    vals["1993"] = (grab("1996", r"vacancy rate from (\d\.\d\d) percent in 1993"), "1996", None)
    vals["1996"] = (grab("1996", r"between March and June 1996 was (\d\.\d\d) percent"), "1996", None)
    vals["1999"] = (grab("1999", r"February and May of 1999 to (\d\.\d\d) percent"), "1999", None)
    vals["2002"] = (grab("2002", r"rental vacancy rate of (\d\.\d\d) percent during the period between February and June of 2002"), "2002", None)
    vals["2005"] = (grab("2005", r"February and June of 2005 was (\d\.\d\d) percent"), "2005", None)
    vals["2008"] = (grab("2008", r"February and June of 2008 was (\d\.\d\d) percent"), "2008", None)
    vals["2011"] = (grab("2011", r"rental vacancy rate of (\d\.\d\d) percent during the period between February and May 2011"), "2011", None)
    vals["2014"] = (grab("2017", r"The 2014 vacancy rate was (\d\.\d\d) percent"), "2017", None)
    vals["2017"] = (grab("2017", r"rental vacancy rate of (\d\.\d\d) percent during the period between January and May 2017"), "2017", None)
    # 2021 and 2023, with published 90% confidence intervals (Table 9 of the 2023 report)
    ci = re.search(r"(\d+\.\d\d)% \[ ?(\d+\.\d\d)% ?, ?(\d+\.\d\d)% ?\] (\d+\.\d\d)% \[ ?(\d+\.\d\d)% ?, ?(\d+\.\d\d)% ?\] Citywide", text["2023"])
    if not ci:
        raise FetchError("citywide confidence-interval row not found in 2023 HVS Table 9")
    v21, lo21, hi21, v23, lo23, hi23 = [float(ci.group(i)) for i in range(1, 7)]
    chk23 = grab("2023", r"net rental vacancy rate in 2023 for all housing accommodations in New York City was (\d\.\d\d)")
    chk21 = grab("2023", r"net rental vacancy rate in 2021 of (\d\.\d\d) percent")
    if abs(chk23 - v23) > 0.001 or abs(chk21 - v21) > 0.001:
        raise FetchError("2023 HVS text and Table 9 disagree")
    vals["2021"] = (v21, "2023", round((hi21 - lo21) / 2, 2))
    vals["2023"] = (v23, "2023", round((hi23 - lo23) / 2, 2))
    # published standard errors (for the method note)
    ses = {}
    for y, pat in [("2005", r"vacancy rate of 3\.09 percent is (0\.\d\d) percent"),
                   ("2008", r"vacancy rate of 2\.88 percent is (0\.\d\d) percent"),
                   ("2011", r"\(SEE\)\d* of the rental vacancy rate of 3\.12 percent is (0\.\d\d)"),
                   ("2017", r"\(SEE\)\d* of the rental vacancy rate of 3\.63 percent is (0\.\d\d)")]:
        m = re.search(pat, text[y])
        if m:
            ses[y] = float(m.group(1))
    # borough breakdown 2023 (Table 9)
    bvals = []
    for b in ["Bronx", "Brooklyn", "Manhattan", "Queens"]:
        m = re.search(re.escape(b) + r" (\d+\.\d\d)% \[ ?[\d.]+% ?, ?[\d.]+% ?\][ *]*(\d+\.\d\d)% \[ ?(\d+\.\d\d)% ?, ?(\d+\.\d\d)% ?\]", text["2023"])
        if not m:
            raise FetchError("borough row not found in 2023 HVS Table 9: " + b)
        bvals.append({"name": b, "value": float(m.group(2)), "moe": round((float(m.group(4)) - float(m.group(3))) / 2, 2)})
    years = sorted(vals, key=int)
    series = [pt(y, vals[y][0], vals[y][2]) for y in years]
    cites = ["%s: %s%% (%s, %s)" % (y, vals[y][0], titles[vals[y][1]], docs[vals[y][1]]) for y in years]
    write_indicator({
        "id": "rental_vacancy", "status": "ok", "status_reason": None,
        "name": "Rental vacancy rate",
        "definition": ("Net rental vacancy rate: vacant units available for rent (not dilapidated) as a share of those units "
                       "plus renter-occupied units, from the New York City Housing and Vacancy Survey, which is taken about "
                       "every three years."),
        "units": "percent", "format": "pct1", "frequency": "annual",
        "series": series, "latest_period": "2023", "latest_extra": None,
        "source": {"name": "NYC Department of Housing Preservation and Development / U.S. Census Bureau, New York City Housing and Vacancy Survey, Selected Initial Findings reports (1996-2023)",
                   "url": docs["2023"], "endpoint": docs["2023"], "fetched": TODAY,
                   "documents": [{"survey_year": y, "title": titles[y], "url": docs[y]} for y in docs]},
        "peers": None, "peer_series": None,
        "breakdowns": [{"by": "borough", "period": "2023", "source_url": docs["2023"], "values": bvals,
                        "note": "Staten Island not reported in 2023 (too few sample units). Moe = half the published 90% confidence interval."}],
        "method": ("Each value was read from the text of an official HVS findings report downloaded and parsed by this script; "
                   "the series is only survey years (no interpolation). Value and source document per year: " + "; ".join(cites)
                   + ". 2021 and 2023 margins are half the 90% confidence intervals published in Table 9 of the 2023 report. "
                   "Earlier reports publish a standard error instead (" + ", ".join("%s: %.2f" % (k, v) for k, v in sorted(ses.items()))
                   + " percentage points); those years carry moe = null."),
        "caveats": [
            "Survey years only, about every three years; there is no value for the years in between. There was no 2020 survey; the cycle after 2017 was 2021.",
            "The rate is a sample-survey estimate. The 2023 value has a 90% confidence interval of about plus or minus 0.26 points.",
            "Survey design changes affect comparisons: the 2011 report says its results should not be compared directly with 2008 and earlier because the 2011 sample was drawn from the 2010 census and weighted to it, and the 2023 report warns that changes between cycles, including the 2021 cycle, may affect comparability over time.",
            "A rate below 5 percent legally sustains the housing emergency that keeps rent stabilization in force.",
            "The 2026 survey's results are expected in early 2027.",
            "No peer comparison: the survey covers New York City only.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 3. Homelessness, HUD point-in-time count (CoC Homeless Populations and Subpopulations reports)
# --------------------------------------------------------------------------------------------
POPSUB_PARTS = {}  # (coc, year) -> (emergency shelter, transitional housing, unsheltered)
POPSUB = "https://files.hudexchange.info/reports/published/CoC_PopSub_CoC_%s-%d_%s_%d.pdf"


def popsub_total(coc, year):
    st = coc.split("-")[0]
    url = POPSUB % (coc, year, st, year)
    name = "hud_popsub_%s_%d.pdf" % (coc, year)
    try:
        http_get(url, name, min_bytes=5000, expect="pdf", tries=2)
    except FetchError:
        return None, url, None, None
    t = flat(pdf_text(name))
    mname = re.search(re.escape(coc) + r"\s+(.+?CoC)\b", t)
    mdate = re.search(r"Point-in Time Date:\s*(\d{1,2}/\d{1,2}/\d{4})", t)
    m = re.search(r"Total Homeless Persons(?: in Households)?", t)
    if m:
        nums = [num(x) for x in re.findall(r"\d{1,3}(?:,\d{3})+|\d+", t[m.end():m.end() + 3000])]
        # The row is emergency shelter, transitional housing, unsheltered, total. The first two numbers follow the
        # label; in some report layouts the last two are printed further down the page, so look for the first later
        # pair (c, d) with ES + TH + c == d.
        if len(nums) >= 4:
            a, b = nums[0], nums[1]
            for j in range(2, len(nums) - 1):
                if a + b + nums[j] == nums[j + 1] and nums[j + 1] > 0:
                    POPSUB_PARTS[(coc, year)] = (int(a), int(b), int(nums[j]))
                    return int(nums[j + 1]), url, (mname.group(1) if mname else None), (mdate.group(1) if mdate else None)
    raise FetchError("could not find a validated Total Homeless Persons row in " + name)


COC_GEO = {
    # peer city: (CoC code, [population parts]); parts are ("county", "SSCCC") or ("place", "SS", "PPPPP", sign)
    "New York": ("NY-600", [("county", c) for c in ["36005", "36047", "36061", "36081", "36085"]]),
    "Los Angeles": ("CA-600", [("county", "06037"), ("place", "06", "43000", -1), ("place", "06", "56000", -1), ("place", "06", "30000", -1)]),
    "Chicago": ("IL-510", [("place", "17", "14000", 1)]),
    "Houston": ("TX-700", [("county", c) for c in ["48201", "48157", "48339"]]),
    "Phoenix": ("AZ-502", [("county", "04013")]),
    "Philadelphia": ("PA-500", [("county", "42101")]),
    "San Antonio": ("TX-500", [("county", "48029")]),
    "San Diego": ("CA-601", [("county", "06073")]),
    "Dallas": ("TX-600", [("county", "48113"), ("county", "48085")]),
    "Fort Worth": ("TX-601", [("county", "48439"), ("county", "48367")]),
    "Jacksonville": ("FL-510", [("county", c) for c in ["12031", "12019", "12089"]]),
    "Austin": ("TX-503", [("county", "48453")]),
    "San Jose": ("CA-500", [("county", "06085")]),
    "Charlotte": ("NC-505", [("county", "37119")]),
    "Columbus": ("OH-503", [("county", "39049")]),
    "Indianapolis": ("IN-503", [("county", "18097")]),
    "San Francisco": ("CA-501", [("county", "06075")]),
    "Seattle": ("WA-500", [("county", "53033")]),
    "Denver": ("CO-503", [("county", c) for c in ["08001", "08005", "08013", "08014", "08031", "08035", "08059"]]),
    "Nashville-Davidson": ("TN-504", [("county", "47037")]),
    "Oklahoma City": ("OK-502", [("place", "40", "55000", 1)]),
    "Washington, D.C.": ("DC-500", [("county", "11001")]),
    "El Paso": ("TX-603", [("county", "48141")]),
    "Las Vegas": ("NV-500", [("county", "32003")]),
    "Boston": ("MA-500", [("place", "25", "07000", 1)]),
}
COC_POP_NOTE = {
    "New York": "the five boroughs",
    "Los Angeles": "Los Angeles County minus Long Beach, Pasadena and Glendale, which run their own CoCs",
    "Chicago": "city of Chicago",
    "Houston": "Harris, Fort Bend and Montgomery counties",
    "Dallas": "Dallas and Collin counties",
    "Fort Worth": "Tarrant and Parker counties",
    "Jacksonville": "Duval, Clay and Nassau counties",
    "Denver": "Adams, Arapahoe, Boulder, Broomfield, Denver, Douglas and Jefferson counties",
    "Oklahoma City": "city of Oklahoma City",
    "Boston": "city of Boston",
}


def homelessness_pit():
    # NYC history
    hist = []
    gaps = []
    dates = {}
    for y in range(2007, 2026):
        v, url, cname, pdate = popsub_total("NY-600", y)
        if v is None:
            gaps.append(str(y))
            continue
        hist.append(pt(y, v))
        dates[str(y)] = pdate
    if not hist or hist[-1]["period"] != "2025":
        raise FetchError("NY-600 2025 count missing")
    # population denominators, Census Vintage 2025
    co = http_get("https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv",
                  "census_co-est2025-alldata.csv", min_bytes=100000).decode("latin-1")
    copop = {}
    for r in csv.DictReader(io.StringIO(co)):
        if r["SUMLEV"] == "050":
            copop[r["STATE"] + r["COUNTY"]] = (int(r["POPESTIMATE2025"]), r["CTYNAME"] + ", " + r["STNAME"])
    sub = http_get("https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/cities/totals/sub-est2025.csv",
                   "census_sub-est2025.csv", min_bytes=100000).decode("latin-1")
    plpop = {}
    for r in csv.DictReader(io.StringIO(sub)):
        if r["SUMLEV"] == "162":
            plpop[(r["STATE"], r["PLACE"])] = (int(r["POPESTIMATE2025"]), r["NAME"] + ", " + r["STNAME"])
    vals = []
    for c in PEERS["cities"]:
        coc, parts = COC_GEO[c["name"]]
        tot, url, cname, pdate = popsub_total(coc, 2025)
        if tot is None:
            raise FetchError("2025 PIT report missing for " + coc)
        pop = 0
        for p in parts:
            if p[0] == "county":
                pop += copop[p[1]][0]
            else:
                pop += p[3] * plpop[(p[1], p[2])][0]
        vals.append({"city": c["name"], "value": round(tot / pop * 10000, 1), "moe": None,
                     "geo_name": "%s %s (%s homeless on %s; population %s: %s)" % (
                         coc, cname, "{:,}".format(tot), pdate, "{:,}".format(pop),
                         COC_POP_NOTE.get(c["name"], "the county or counties the CoC name covers"))})
    gap_note = ("No report could be downloaded for %s." % ", ".join(gaps)) if gaps else ""
    write_indicator({
        "id": "homelessness_pit", "status": "ok", "status_reason": None,
        "name": "People counted as homeless",
        "definition": ("Total people experiencing homelessness on one night in January (sheltered in emergency shelter, "
                       "safe havens or transitional housing, plus unsheltered), HUD point-in-time count for the New York "
                       "City Continuum of Care (NY-600)."),
        "units": "people", "format": "int", "frequency": "annual",
        "series": hist, "latest_period": "2025", "latest_extra": None,
        "source": {"name": "U.S. Department of Housing and Urban Development, CoC Homeless Populations and Subpopulations reports, NY-600 New York City CoC, 2007-2025",
                   "url": POPSUB % ("NY-600", 2025, "NY", 2025),
                   "endpoint": "https://files.hudexchange.info/reports/published/CoC_PopSub_CoC_NY-600-<year>_NY_<year>.pdf",
                   "fetched": TODAY},
        "peers": {
            "period": "2025", "geography": "continuum of care",
            "note": ("Total homeless persons per 10,000 residents, January 2025 count, for the Continuum of Care that contains "
                     "each city. CoC boundaries do not match city limits: most cover a whole county or several counties, so "
                     "the denominator is the Census Vintage 2025 (July 1, 2025) population of the area the CoC covers, as "
                     "described in each row. Where a CoC's exact boundary differs from its name (for example Dallas also "
                     "covers Collin County) the area used is stated; the rates are approximate and depend on each CoC's own "
                     "counting method, especially for the unsheltered count. Large-shelter right-to-shelter cities such as "
                     "New York count far more sheltered people than cities without that obligation."),
            "source": {"name": "HUD CoC Homeless Populations and Subpopulations reports, 2025; Census Bureau Vintage 2025 county and city population estimates",
                       "url": "https://www.hudexchange.info/programs/coc/coc-homeless-populations-and-subpopulations-reports/",
                       "endpoint": "https://files.hudexchange.info/reports/published/CoC_PopSub_CoC_<CoC>-2025_<ST>_2025.pdf; co-est2025-alldata.csv; sub-est2025.csv",
                       "fetched": TODAY},
            "values": sorted(vals, key=lambda v: -v["value"]),
        },
        "peer_series": None, "breakdowns": [],
        "method": ("For each year, downloaded HUD's Homeless Populations and Subpopulations PDF for NY-600 and read the "
                   "'Total Homeless Persons' row (2007-2011 reports label it 'Total Homeless Persons in Households'). A value "
                   "was accepted only if emergency shelter + transitional housing + unsheltered equals the printed total. "
                   "Count dates: " + ", ".join("%s %s" % (k, v) for k, v in dates.items() if v) + ". " + gap_note),
        "caveats": [
            "HUD's preferred download, the 'PIT Counts by CoC' workbook on huduser.gov, refused automated requests and is in .xlsb format; these per-year CoC reports carry the same counts as submitted by the CoC.",
            "No value for %s: HUD's report for those years could not be found at its usual address. They are left out, not estimated." % ", ".join(gaps) if gaps else "All years 2007-2025 were found.",
            "2021: HUD let communities cancel or modify the unsheltered count because of COVID-19; HUD's report warns that unsheltered and total counts for 2021 may be incomplete.",
            "Most of New York's count is people in shelter: in January 2025, %s in emergency shelter, %s in transitional housing and %s unsheltered, per HUD's report." % tuple("{:,}".format(x) for x in POPSUB_PARTS[("NY-600", 2025)]),
            "The count is one night in January, not the number of people homeless over a year.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 4. Shelter census (DHS Daily Report)
# --------------------------------------------------------------------------------------------
def shelter_census():
    q = ("SELECT date_extract_y(date_of_census) AS y, sum(total_individuals_in_shelter) AS s, count(*) AS n, "
         "min(date_of_census) AS d0, max(date_of_census) AS d1 GROUP BY y ORDER BY y")
    hist = soql("dwrg-kzni", q, "dhs_daily_historical_by_year.json")
    cur = soql("k46n-sa2m", q, "dhs_daily_current_by_year.json")
    agg = {}
    for r in hist + cur:
        y = int(r["y"])
        a = agg.setdefault(y, [0.0, 0])
        a[0] += float(r["s"])
        a[1] += int(r["n"])
    series = []
    days = {}
    for y in range(2014, 2026):
        if y not in agg or agg[y][1] < 300:
            raise FetchError("too few daily reports for %d" % y)
        series.append(pt(y, int(round(agg[y][0] / agg[y][1]))))
        days[y] = agg[y][1]
    last = soql("k46n-sa2m", "SELECT date_of_census, total_individuals_in_shelter, total_single_adults_in_shelter, "
                "total_individuals_in_families_with_children_in_shelter_ ORDER BY date_of_census DESC LIMIT 1",
                "dhs_daily_latest.json")[0]
    ld = last["date_of_census"][:10]
    y26 = agg.get(2026)
    meta = socrata_meta("k46n-sa2m", "dhs_daily_meta.json")
    write_indicator({
        "id": "shelter_census", "status": "ok", "status_reason": None,
        "name": "People in city homeless shelters",
        "definition": "Average number of people sleeping in the city Department of Homeless Services shelter system each night, calendar-year average of the DHS Daily Report.",
        "units": "people", "format": "int", "frequency": "annual",
        "series": series, "latest_period": "2025",
        "latest_extra": {"period": datetime.date.fromisoformat(ld).strftime("%B %-d, %Y"),
                         "value": int(float(last["total_individuals_in_shelter"])),
                         "note": "Single day, DHS Daily Report. 2026 average to date: %d (%d daily reports)." % (
                             round(y26[0] / y26[1]), y26[1]) if y26 else "Single day, DHS Daily Report."},
        "source": {"name": "NYC Department of Homeless Services, DHS Daily Report, NYC Open Data k46n-sa2m (March 2021 on) and dwrg-kzni (historical, to February 2021)",
                   "url": "https://data.cityofnewyork.us/d/k46n-sa2m",
                   "endpoint": SOCRATA + "k46n-sa2m.json ; " + SOCRATA + "dwrg-kzni.json",
                   "fetched": TODAY},
        "peers": None, "peer_series": None, "breakdowns": [],
        "method": ("Annual value = mean of total_individuals_in_shelter over every daily report dated in that calendar year, "
                   "pooling the historical dataset (through Feb. 28, 2021) and the current one (from Mar. 1, 2021). Daily "
                   "reports per year: " + ", ".join("%d: %d" % (k, v) for k, v in days.items())
                   + ". Days with no published report are simply absent from the average."),
        "caveats": [
            "Covers only the Department of Homeless Services shelter system; the dataset describes itself as the daily number of families and individuals residing in the DHS shelter system and does not list other systems.",
            "Not included: HRA domestic-violence shelters, Department of Youth and Community Development youth shelters, HPD emergency housing, and the emergency asylum-seeker sites (HERRCs) run outside DHS. Asylum seekers placed in DHS shelters are included.",
            "No peer comparison: shelter systems and right-to-shelter rules differ too much between cities.",
        ],
        "dataset_description": meta.get("description", "")[:600],
    })


# --------------------------------------------------------------------------------------------
# 5. Evictions (city marshals)
# --------------------------------------------------------------------------------------------
def evictions():
    q = ("SELECT date_extract_y(executed_date) AS y, borough, count(*) AS n "
         "WHERE upper(residential_commercial_ind) IN ('RESIDENTIAL','R') AND executed_date IS NOT NULL "
         "GROUP BY y, borough ORDER BY y")
    rows = soql("6z8x-wfk4", q, "evictions_by_year_borough.json")
    codes = soql("6z8x-wfk4", "SELECT residential_commercial_ind, count(*) AS n GROUP BY residential_commercial_ind",
                 "evictions_codes.json")
    last = soql("6z8x-wfk4", "SELECT max(executed_date) AS d WHERE executed_date <= '%sT23:59:59'" % TODAY,
                "evictions_maxdate.json")[0]["d"][:10]
    tot = {}
    boro = {}
    for r in rows:
        y = int(r["y"])
        tot[y] = tot.get(y, 0) + int(r["n"])
        b = (r.get("borough") or "UNKNOWN").title()
        boro.setdefault(y, {})[b] = boro.get(y, {}).get(b, 0) + int(r["n"])
    series = [pt(y, tot[y]) for y in range(2017, 2026)]
    write_indicator({
        "id": "evictions", "status": "ok", "status_reason": None,
        "name": "Evictions carried out",
        "definition": "Residential evictions executed by New York City marshals, by calendar year of the executed date.",
        "units": "count", "format": "int", "frequency": "annual",
        "series": series, "latest_period": "2025",
        "latest_extra": {"period": "2026 through %s" % datetime.date.fromisoformat(last).strftime("%B %-d"),
                         "value": tot.get(2026, 0), "note": "Year to date; latest executed date in the data is %s." % last},
        "source": {"name": "NYC Department of Investigation, Evictions (city marshals), NYC Open Data 6z8x-wfk4",
                   "url": "https://data.cityofnewyork.us/d/6z8x-wfk4", "endpoint": SOCRATA + "6z8x-wfk4.json", "fetched": TODAY},
        "peers": None, "peer_series": None,
        "breakdowns": [{"by": "borough", "period": "2025", "source_url": "https://data.cityofnewyork.us/d/6z8x-wfk4",
                        "values": [{"name": k, "value": v, "moe": None} for k, v in sorted(boro[2025].items())]}],
        "method": ("Counted rows whose residential_commercial_ind is 'Residential' or 'R' (the dataset uses both codes; "
                   "code counts: " + ", ".join("%s=%s" % (c.get("residential_commercial_ind"), c["n"]) for c in codes)
                   + "), grouped by year of executed_date. Rows without an executed date are excluded."),
        "caveats": [
            "Possessions and evictions carried out by marshals only; it does not count tenants who leave after a court case or under threat of eviction.",
            "Data begin in 2017. Evictions nearly stopped in 2020-2021 under the pandemic moratoriums, so those years are not a normal baseline.",
            "Marshals can report late, so the most recent months may rise slightly.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 6-7. State test proficiency, grades 3-8
# --------------------------------------------------------------------------------------------
INFOHUB = "https://infohub.nyced.org/docs/default-source/default-document-library/"


def proficiency(subject):
    is_ela = subject == "ela"
    fname = "citywide-ela-results-public.xlsx" if is_ela else "citywide-math-results-public.xlsx"
    data = http_get(INFOHUB + fname, "doe_" + fname, min_bytes=50000, expect="xlsx")
    wb = read_xlsx(data)
    pre = "ELA" if is_ela else "Math"
    notes = " ".join(str(r[0]) for r in wb["NOTES"] if r and r[0])
    asof = re.search(r"as of ([A-Z][a-z]+ \d{1,2}, \d{4})", notes)
    allrecs = sheet_records(wb[pre + " - All"])
    doe = {}
    for r in allrecs:
        if str(r["Grade"]) == "All Grades" and r["Category"] == "All Students":
            doe[int(r["Year"])] = (float(r["% Level 3+4"]), int(r["Number Tested"]))
    # 2013-2017 from NYC Open Data (DOE's own archive of earlier results)
    if is_ela:
        od = soql("iebs-5yhr", "SELECT year, number_tested, level_3_4_1 AS pct WHERE report_category='Citywide' "
                  "AND grade='All Grades' AND category='All Students' ORDER BY year", "doe_ela_2013_2023_citywide.json")
        odid = "iebs-5yhr"
    else:
        od = soql("74kb-55u9", "SELECT year, number_tested, pct_level_3_and_4 AS pct WHERE report_category='Citywide' "
                  "AND grade='All Grades' AND student_category='All Students' ORDER BY year", "doe_math_2013_2023_citywide.json")
        odid = "74kb-55u9"
    odv = {int(r["year"]): (float(r["pct"]), int(r["number_tested"])) for r in od}
    diffs = [abs(odv[y][0] - doe[y][0]) for y in odv if y in doe]
    if diffs and max(diffs) > 0.15:
        raise FetchError("%s: Open Data and InfoHub disagree on overlapping years (max diff %.2f)" % (subject, max(diffs)))
    series = []
    for y in range(2013, 2018):
        if y in odv:
            series.append(pt(y, round(odv[y][0], 1)))
    for y in sorted(doe):
        if y <= 2025:
            series.append(pt(y, round(doe[y][0], 1)))
    if series[-1]["period"] != "2025":
        raise FetchError(subject + ": 2025 missing")
    bks = []
    for sheet, by in [(pre + " - Ethnicity", "race/ethnicity"), (pre + " - Econ Status", "economic status")]:
        vals = []
        for r in sheet_records(wb[sheet]):
            if str(r["Grade"]) == "All Grades" and int(r["Year"]) == 2025 and isinstance(r["% Level 3+4"], (int, float)):
                vals.append({"name": r["Category"], "value": round(float(r["% Level 3+4"]), 1), "moe": None})
        if vals:
            bks.append({"by": by, "period": "2025", "source_url": INFOHUB + fname, "values": vals})
    x26 = doe.get(2026)
    name = "Students in grades 3 to 8 proficient in reading" if is_ela else "Students in grades 3 to 8 proficient in math"
    write_indicator({
        "id": "reading_proficiency" if is_ela else "math_proficiency", "status": "ok", "status_reason": None,
        "name": name,
        "definition": ("Share of New York City public school students in grades 3 to 8 (district schools; charter schools "
                       "excluded) who scored proficient, Level 3 or 4, on the New York State %s exam." % ("English language arts" if is_ela else "mathematics")),
        "units": "percent", "format": "pct1", "frequency": "annual",
        "series": series, "latest_period": "2025",
        "latest_extra": ({"period": "Spring 2026", "value": round(x26[0], 1),
                          "note": "%s tested; results released August 2026 (file as of %s)." % ("{:,}".format(x26[1]), asof.group(1) if asof else "August 2026")}
                         if x26 else None),
        "source": {"name": "NYC Public Schools, citywide %s results 2018-2026 (InfoHub), and %s Test Results 2013-2023 (NYC Open Data %s)" % (pre, pre, odid),
                   "url": "https://infohub.nyced.org/reports/academics/test-results",
                   "endpoint": INFOHUB + fname + " ; " + SOCRATA + odid + ".json",
                   "fetched": TODAY},
        "peers": None, "peer_series": None, "breakdowns": bks,
        "method": ("Citywide, all grades (3-8), all students, '%% Level 3+4'. 2018 onward from the InfoHub citywide workbook "
                   "(sheet '%s - All'); 2013-2017 from the DOE's Open Data file of earlier results. In overlapping years the "
                   "two sources agree within %.2f points." % (pre, max(diffs) if diffs else 0)),
        "caveats": [
            "No results for 2020 (tests cancelled) or 2021 (tests optional; about 21 percent of eligible students took them), per the DOE's notes.",
            "Two breaks in comparability, per the DOE's notes: in 2018 the state shortened the tests from three days to two and rescaled them, so 2017 and earlier should not be compared directly with 2018 and later; in 2023 the state aligned the tests to new standards (Next Generation) with new scales and cut scores, so 2022 and earlier should not be compared directly with 2023 and later.",
            "Charter school students are not included.",
            "The state moved grades 5 and 8 to computer-based testing in 2024 and grades 4 and 6 in 2025.",
        ] + ([] if is_ela else ["Grade 7 and 8 students who take a Regents math exam instead of the grade-level test are not in the math results, which lowers the number tested."]) + [
            "No peer comparison: each state sets its own tests and proficiency bars.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 8. NAEP grade 4 reading (Trial Urban District Assessment)
# --------------------------------------------------------------------------------------------
NAEP = ("https://www.nationsreportcard.gov/DataService/GetAdhocData.aspx?type=data&subject=reading&grade=4"
        "&subscale=RRPCM&variable=TOTAL&jurisdiction=%s&stattype=MN:MN&Year=%s")
TUDA = {"New York": "XN", "Los Angeles": "XL", "Chicago": "XC", "Houston": "XH", "Philadelphia": "XP",
        "San Diego": "XD", "Dallas": "XS", "Fort Worth": "XZ", "Austin": "XU", "Jacksonville": "XE",
        "Charlotte": "XT", "Denver": "XY", "Washington, D.C.": "XW", "Boston": "XB", "Las Vegas": "XX"}
TUDA_NAME = {"XN": "New York City", "XL": "Los Angeles Unified", "XC": "Chicago Public Schools", "XH": "Houston ISD",
             "XP": "School District of Philadelphia", "XD": "San Diego Unified", "XS": "Dallas ISD",
             "XZ": "Fort Worth ISD", "XU": "Austin ISD", "XE": "Duval County Public Schools (Jacksonville)",
             "XT": "Charlotte-Mecklenburg Schools", "XY": "Denver Public Schools",
             "XW": "District of Columbia Public Schools (DCPS)", "XB": "Boston Public Schools",
             "XX": "Clark County School District (Las Vegas)"}


def naep_reading():
    years = "2002,2003,2005,2007,2009,2011,2013,2015,2017,2019,2022,2024"
    url = NAEP % ("XN", years)
    d = json.loads(http_get(url, "naep_g4_reading_XN_all_years.json").decode("utf-8"))
    res = d.get("result")
    if not res:
        raise FetchError("NAEP returned no data for NYC")
    series = [pt(r["year"], round(r["value"], 1)) for r in sorted(res, key=lambda r: r["year"]) if r["isStatDisplayable"] == 1]
    jur = ",".join(sorted(set(TUDA.values()))) + ",NL,NP"
    url2 = NAEP % (jur, "2024")
    d2 = json.loads(http_get(url2, "naep_g4_reading_2024_tuda.json").decode("utf-8"))
    by = {r["jurisdiction"]: r for r in d2["result"] if r["isStatDisplayable"] == 1}
    vals = []
    for city, code in TUDA.items():
        if code in by:
            vals.append({"city": city, "value": round(by[code]["value"], 1), "moe": None,
                         "geo_name": "%s (NAEP jurisdiction %s, '%s')" % (TUDA_NAME[code], code, by[code]["jurisLabel"])})
    if "NL" not in by:
        raise FetchError("NAEP large city average missing")
    nl, np_ = by["NL"]["value"], by["NP"]["value"]
    # peer series for the four named peers
    named = PEERS["named_peers"]
    url3 = NAEP % (",".join(TUDA[c] for c in named), years)
    d3 = json.loads(http_get(url3, "naep_g4_reading_named_peers.json").decode("utf-8"))
    ps = {}
    inv = {v: k for k, v in TUDA.items()}
    for r in sorted(d3["result"], key=lambda r: r["year"]):
        if r["isStatDisplayable"] == 1:
            ps.setdefault(inv[r["jurisdiction"]], []).append({"period": str(r["year"]), "value": round(r["value"], 1)})
    write_indicator({
        "id": "naep_reading", "status": "ok", "status_reason": None,
        "name": "Fourth-grade reading on the national test (NAEP)",
        "definition": "Average NAEP reading scale score (0-500) of fourth graders in New York City public schools, Trial Urban District Assessment.",
        "units": "scale score", "format": "int", "frequency": "annual",
        "series": series, "latest_period": series[-1]["period"], "latest_extra": None,
        "source": {"name": "National Center for Education Statistics, NAEP Data Service, grade 4 reading composite (RRPCM), jurisdiction XN (New York City)",
                   "url": "https://www.nationsreportcard.gov/ndecore/xplore/NDE", "endpoint": url, "fetched": TODAY},
        "peers": {"period": "2024", "geography": "school district",
                  "note": ("2024 average scores for Trial Urban District Assessment districts serving peer cities. Districts do "
                           "not match city limits (e.g., Clark County covers all of metro Las Vegas; Duval County covers "
                           "Jacksonville; DCPS excludes D.C. charter schools). Phoenix, San Antonio, San Jose, Columbus, "
                           "Indianapolis, San Francisco, Seattle, Nashville, Oklahoma City and El Paso have no TUDA district. "
                           "For reference, the 2024 large-city average was %.1f and the national public-school average %.1f. "
                           "Differences of a few points are often not statistically significant." % (nl, np_)),
                  "source": {"name": "NCES NAEP Data Service, grade 4 reading 2024", "url": "https://www.nationsreportcard.gov/",
                             "endpoint": url2, "fetched": TODAY},
                  "values": sorted(vals, key=lambda v: -v["value"])},
        "peer_series": ps, "breakdowns": [],
        "method": "Average scale score (stattype MN:MN) for all students, accommodations permitted (reporting sample R3 in every year, including 2002), every year New York City took part.",
        "caveats": [
            "NAEP tests a sample of students every two years (three between 2019 and 2022); 2024 is the latest result in the NAEP Data Service as of the fetch date (a request for 2026 returned no data).",
            "Scores are estimates from a sample of students and carry sampling error; small year-to-year changes may not be statistically significant.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 9. Graduation rate
# --------------------------------------------------------------------------------------------
def graduation_rate():
    new = http_get(INFOHUB + "2025-graduation-rates-public-citywide.xlsx", "doe_2025-graduation-rates-public-citywide.xlsx",
                   min_bytes=50000, expect="xlsx")
    old = http_get(INFOHUB + "2001-2011-graduation_rates_public_citywide.xlsx", "doe_2001-2011-graduation_rates_public_citywide.xlsx",
                   min_bytes=50000, expect="xlsx")
    deck_url = INFOHUB + "2025-graduation-rates---forweb.pdf"
    http_get(deck_url, "doe_2025-graduation-rates-forweb.pdf", min_bytes=20000, expect="pdf")
    deck = flat(pdf_text("doe_2025-graduation-rates-forweb.pdf"))
    wbn = read_xlsx(new)
    wbo = read_xlsx(old, only=["All"])
    vals = {}
    for wb in (wbo, wbn):
        for r in sheet_records(wb["All"]):
            if r["Category"] == "All Students" and r["Cohort"] == "4 year August":
                vals[int(r["Cohort Year"]) + 4] = (round(float(r["% Grads"]), 1), int(r["# Total Cohort"]))
    series = [pt(y, vals[y][0]) for y in sorted(vals)]
    if series[-1]["period"] != "2025":
        raise FetchError("class of 2025 missing")
    wv = re.search(r"Whereas (\d+\.\d)% of the Class of 2023 and (\d+\.\d)% of the Class of 2024 needed at least one waiver "
                   r"to meet exam requirements, the rate dropped to (\d+\.\d)% for the Class of 2025", deck)
    bks = []
    for sheet, by in [("Ethnicity", "race/ethnicity"), ("Poverty", "economic status")]:
        v = []
        for r in sheet_records(wbn[sheet]):
            if r["Cohort"] == "4 year August" and int(r["Cohort Year"]) == 2021 and isinstance(r["% Grads"], (int, float)):
                v.append({"name": r["Category"], "value": round(float(r["% Grads"]), 1), "moe": None})
        bks.append({"by": by, "period": "2025", "source_url": INFOHUB + "2025-graduation-rates-public-citywide.xlsx", "values": v})
    caveats = [
        "Waivers and appeals: " + (("the DOE's class of 2025 presentation says %s%% of the class of 2023 and %s%% of the class of 2024 'needed at least one waiver to meet exam requirements,' compared with %s%% of the class of 2025, after the state's COVID-era Regents exam waivers (June 2020 to January 2022, and U.S. History through January 2023) ended. The DOE says the availability of these waivers has impacted graduation rates, so rates for the classes of 2020-2024 are not directly comparable with earlier or later classes." % (wv.group(1), wv.group(2), wv.group(3)))
                                   if wv else "the DOE presentation's waiver figures could not be read, so they are not reported here."),
        "Regents appeals and, from the class of 2013, the compensatory score option for students with disabilities also raised rates over the period, per the DOE.",
        "City figures attribute students placed in non-public schools differently from the state, so they can differ slightly from NYSED's published NYC rate. The DOE revised the classes of 2020, 2021 and 2023.",
        "Classes before 2008 are omitted because the DOE file reports only the June (not August) rate for them.",
    ]
    write_indicator({
        "id": "graduation_rate", "status": "ok", "status_reason": None,
        "name": "Four-year high school graduation rate",
        "definition": "Share of students who entered ninth grade four years earlier who graduated with a Regents or local diploma by August of their fourth year, NYC public schools (city calculation).",
        "units": "percent", "format": "pct1", "frequency": "annual",
        "series": series, "latest_period": "2025", "latest_extra": None,
        "source": {"name": "NYC Public Schools, Graduation Results, citywide files (cohorts 2001-2011 and 2012-2021) and Class of 2025 presentation",
                   "url": "https://infohub.nyced.org/reports/academics/graduation-results",
                   "endpoint": INFOHUB + "2025-graduation-rates-public-citywide.xlsx ; " + INFOHUB + "2001-2011-graduation_rates_public_citywide.xlsx",
                   "fetched": TODAY},
        "peers": None, "peer_series": None, "breakdowns": bks,
        "method": "Sheet 'All', Category 'All Students', Cohort '4 year August', column '%% Grads'; period = cohort year + 4 (graduating class). Class of 2025 = cohort of 2021 (%s students)." % "{:,}".format(vals[2025][1]),
        "caveats": caveats,
    })


# --------------------------------------------------------------------------------------------
# 10. Chronic absenteeism
# --------------------------------------------------------------------------------------------
def chronic_absenteeism():
    fname = "public-citywide-attendance-results-2019-2025.xlsx"
    data = http_get(INFOHUB + fname, "doe_" + fname, min_bytes=50000, expect="xlsx")
    wb = read_xlsx(data)
    new = {}
    for r in sheet_records(wb["All Students"]):
        if r["Grade"] == "All Grades" and r["Category"] == "All Students":
            new[r["Year"]] = (round(float(r["% Chronically Absent"]), 1), int(r["# Contributing 10+ Total Days and 1+ Pres Day"]))
    old = soql("mg8s-7r2b", "SELECT year, contributing_20_total_days, chronically_absent, chronically_absent_1 WHERE "
               "report_type='Citywide' AND grade='All Grades' AND demographic_variable='All Students' ORDER BY year",
               "doe_attendance_2013_2019_citywide.json")
    oldv = {r["year"]: float(r["chronically_absent_1"]) for r in old}
    series = [pt(y, round(oldv[y], 1)) for y in sorted(oldv) if y < "2018-19"]
    series += [pt(y, new[y][0]) for y in sorted(new)]
    if series[-1]["period"] != "2024-25":
        raise FetchError("2024-25 attendance missing")
    bks = []
    for sheet, by in [("Ethnicity", "race/ethnicity"), ("Poverty", "economic status")]:
        v = [{"name": r["Category"], "value": round(float(r["% Chronically Absent"]), 1), "moe": None}
             for r in sheet_records(wb[sheet])
             if r["Grade"] == "All Grades" and r["Year"] == "2024-25" and isinstance(r["% Chronically Absent"], (int, float))]
        bks.append({"by": by, "period": "2024-25", "source_url": INFOHUB + fname, "values": v})
    overlap = "2018-19: %.1f%% under the old definition vs %.1f%% under the state definition" % (oldv.get("2018-19", float("nan")), new["2018-19"][0])
    write_indicator({
        "id": "chronic_absenteeism", "status": "ok", "status_reason": None,
        "name": "Students chronically absent",
        "definition": "Share of students in district schools (grades pre-K to 12, Districts 1-32 and 75) who missed 10 percent or more of the school days they were enrolled, by school year.",
        "units": "percent", "format": "pct1", "frequency": "annual",
        "series": series, "latest_period": "2024-25", "latest_extra": None,
        "source": {"name": "NYC Public Schools, End-of-Year Attendance and Chronic Absenteeism Data, citywide 2018-19 to 2024-25 (InfoHub); Attendance Results 2013-2019 (NYC Open Data mg8s-7r2b)",
                   "url": "https://infohub.nyced.org/reports/students-and-schools/school-quality/information-and-data-overview/end-of-year-attendance-and-chronic-absenteeism-data",
                   "endpoint": INFOHUB + fname + " ; " + SOCRATA + "mg8s-7r2b.json", "fetched": TODAY},
        "peers": None, "peer_series": None, "breakdowns": bks,
        "method": ("2018-19 onward: InfoHub citywide file, sheet 'All Students', All Grades, '% Chronically Absent'. 2013-14 to "
                   "2017-18: Open Data citywide rows (report_type Citywide, All Grades, All Students). Overlap check, " + overlap + "."),
        "caveats": [
            "Definition change: starting in 2020-21 the DOE adopted the state definition (enrolled at least 10 days and present at least 1; absent 10 percent or more of days) and applied it back to 2018-19. Values for 2013-14 to 2017-18 use the DOE's earlier definition (students enrolled at least 20 days). The two give nearly the same rate in 2018-19.",
            "2019-20 covers only September 2019 to March 13, 2020, before schools closed. 2020-21 counts both in-person and remote attendance.",
            "Charter schools, District 79 alternative programs and home instruction are excluded. Beginning in 2022-23 District 75 short-term-stay schools and district pre-K centers are included.",
            "The Open Data copy of the newer file stops at 2022-23; this series uses the DOE's InfoHub file through 2024-25.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 11. Public school enrollment (Demographic Snapshot), including charter schools
# --------------------------------------------------------------------------------------------
def public_school_enrollment():
    fname = "demographic-snapshot-2021-22-to-2025-26-public.xlsx"
    data = http_get(INFOHUB + fname, "doe_" + fname, min_bytes=100000, expect="xlsx")
    wb = read_xlsx(data, only=["Citywide", "Citywide with Charter Schools", "Borough with Charter Schools"])
    dist = {r["Year"]: int(r["Total Enrollment"]) for r in sheet_records(wb["Citywide"])}
    withc = {r["Year"]: int(r["Total Enrollment"]) for r in sheet_records(wb["Citywide with Charter Schools"])}
    early = soql("bvzk-auuz", "SELECT year, total_enrollment ORDER BY year", "doe_snapshot_2013_2018_citywide.json")
    mid = soql("smka-gz6w", "SELECT year, total_enrollment ORDER BY year", "doe_snapshot_2016_2021_citywide.json")
    vals = {}
    src = {}
    for r in early:
        vals[r["year"]] = int(r["total_enrollment"]); src[r["year"]] = "bvzk-auuz"
    for r in mid:
        if r["year"] in vals and vals[r["year"]] != int(r["total_enrollment"]):
            raise FetchError("snapshot vintages disagree for " + r["year"])
        vals[r["year"]] = int(r["total_enrollment"]); src[r["year"]] = "smka-gz6w"
    for y, v in withc.items():
        vals[y] = v; src[y] = "InfoHub"
    series = [pt(y, vals[y]) for y in sorted(vals)]
    if series[-1]["period"] != "2025-26":
        raise FetchError("2025-26 enrollment missing")
    boro = [{"name": r["Borough"], "value": int(r["Total Enrollment"]), "moe": None}
            for r in sheet_records(wb["Borough with Charter Schools"]) if r["Year"] == "2025-26"]
    y = "2025-26"
    write_indicator({
        "id": "public_school_enrollment", "status": "ok", "status_reason": None,
        "name": "Public school enrollment",
        "definition": "Students enrolled in New York City public schools, including charter schools, 3-K through grade 12, as of the fall audited register (October 31 in most years), by school year.",
        "units": "students", "format": "int", "frequency": "annual",
        "series": series, "latest_period": "2025-26", "latest_extra": None,
        "source": {"name": "NYC Public Schools, Demographic Snapshot: citywide with charter schools 2021-22 to 2025-26 (InfoHub); earlier citywide snapshots on NYC Open Data (bvzk-auuz, smka-gz6w)",
                   "url": "https://infohub.nyced.org/reports/students-and-schools/school-quality/information-and-data-overview",
                   "endpoint": INFOHUB + fname + " ; " + SOCRATA + "bvzk-auuz.json ; " + SOCRATA + "smka-gz6w.json", "fetched": TODAY},
        "peers": None, "peer_series": None,
        "breakdowns": [
            {"by": "school type", "period": y, "source_url": INFOHUB + fname,
             "values": [{"name": "District schools", "value": dist[y], "moe": None},
                        {"name": "Charter schools", "value": withc[y] - dist[y], "moe": None}]},
            {"by": "borough", "period": y, "source_url": INFOHUB + fname, "values": boro,
             "note": "Including charter schools."},
        ],
        "method": ("Total Enrollment, citywide including charter schools. Sources by year: " + ", ".join("%s %s" % (k, src[k]) for k in sorted(src))
                   + ". Where the Open Data vintages overlap they report identical totals. Charter enrollment in the breakdown = "
                   "'Citywide with Charter Schools' minus 'Citywide' for 2025-26."),
        "caveats": [
            "Includes charter schools and 3-K and pre-K students. Per the DOE's notes, charter counts are reported to the state as of BEDS day (early October) and, like counts for pre-K early education centers, are not audited. Excluding charters, enrollment in 2025-26 was %s." % "{:,}".format(dist[y]),
            "The series joins three releases of the snapshot (two Open Data releases through 2020-21, InfoHub from 2021-22). The two Open Data releases agree where they overlap; the InfoHub release does not overlap them, so the 2020-21 to 2021-22 step could not be cross-checked.",
            "2020-21 uses the November 13 register and 2021-22 the November 12 register because school started late.",
        ],
    })


# --------------------------------------------------------------------------------------------
# 12. Child care seats (Health Department permitted programs, current snapshot)
# --------------------------------------------------------------------------------------------
def child_care_seats():
    rows = soql("gy3q-4tzp", "SELECT dcid, facility_type, program_type, borough, capacity LIMIT 50000",
                "dohmh_child_care_active.json")
    if len(rows) < 1000:
        raise FetchError("child care dataset unexpectedly small: %d" % len(rows))
    meta = socrata_meta("gy3q-4tzp", "dohmh_child_care_meta.json")
    updated = datetime.datetime.utcfromtimestamp(meta.get("rowsUpdatedAt", 0)).date().isoformat()
    total = 0
    nodata = 0
    by_b = {}
    by_t = {}
    nod_t = {}
    for r in rows:
        cap = (r.get("capacity") or "").strip()
        ft = r.get("facility_type") or "unknown"
        if not re.fullmatch(r"\d+", cap):
            nodata += 1
            nod_t[ft] = nod_t.get(ft, 0) + 1
            continue
        c = int(cap)
        total += c
        b = (r.get("borough") or "Unknown").title()
        by_b[b] = by_b.get(b, 0) + c
        by_t[ft] = by_t.get(ft, 0) + c
    labels = {"GCC": "Group child care centers", "SBCC": "School-based child care"}
    write_indicator({
        "id": "child_care_seats", "status": "partial",
        "status_reason": ("Only a current snapshot is published (active programs as of %s), so there is no annual history "
                          "to compare against. %d of %d programs (%.0f%%) list no capacity and are left out of the total."
                          % (updated, nodata, len(rows), 100.0 * nodata / len(rows))),
        "name": "Licensed child care seats",
        "definition": ("Total licensed capacity of active child care programs regulated by the city Health Department under "
                       "Health Code Article 47 (group child care centers) and Article 43 (school-based child care)."),
        "units": "seats", "format": "int", "frequency": "annual",
        "series": [pt(updated[:4], total)], "latest_period": updated[:4], "latest_extra": None,
        "source": {"name": "NYC Department of Health and Mental Hygiene, Active NYC Health Code Regulated Child Care Programs, NYC Open Data gy3q-4tzp (data as of %s)" % updated,
                   "url": "https://data.cityofnewyork.us/d/gy3q-4tzp", "endpoint": SOCRATA + "gy3q-4tzp.json", "fetched": TODAY},
        "peers": None, "peer_series": None,
        "breakdowns": [
            {"by": "borough", "period": updated[:4], "source_url": "https://data.cityofnewyork.us/d/gy3q-4tzp",
             "values": [{"name": k, "value": v, "moe": None} for k, v in sorted(by_b.items())]},
            {"by": "program type", "period": updated[:4], "source_url": "https://data.cityofnewyork.us/d/gy3q-4tzp",
             "values": [{"name": labels.get(k, k), "value": v, "moe": None} for k, v in sorted(by_t.items())]},
        ],
        "method": ("Downloaded all %d active program rows and summed the capacity field where it is a whole number. Programs "
                   "with capacity 'NO DATA' (%s) are excluded." % (len(rows), ", ".join("%s: %d" % (k, v) for k, v in sorted(nod_t.items())))),
        "caveats": [
            "Snapshot only: the dataset lists programs active today, with no history, so it cannot show change over time.",
            "Undercounts total supply: programs without a listed capacity are excluded, and family and group family day care homes and school-age programs licensed by the New York State Office of Children and Family Services are not in this dataset.",
            "Capacity is the licensed maximum, not enrollment or the number of subsidized or affordable seats.",
            "Public school 3-K and pre-K seats in district schools are not included.",
        ],
    })


# --------------------------------------------------------------------------------------------
def main():
    steps = [("new_homes", new_homes), ("rental_vacancy", rental_vacancy), ("homelessness_pit", homelessness_pit),
             ("shelter_census", shelter_census), ("evictions", evictions),
             ("reading_proficiency", lambda: proficiency("ela")), ("math_proficiency", lambda: proficiency("math")),
             ("naep_reading", naep_reading), ("graduation_rate", graduation_rate),
             ("chronic_absenteeism", chronic_absenteeism), ("public_school_enrollment", public_school_enrollment),
             ("child_care_seats", child_care_seats)]
    only = set(sys.argv[1:])
    failed = []
    for name, fn in steps:
        if only and name not in only:
            continue
        print("[housing_schools] " + name)
        try:
            fn()
        except Exception as e:  # report every failure, then exit non-zero
            print("  FAILED: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            failed.append(name)
    if failed:
        print("Failed: " + ", ".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
