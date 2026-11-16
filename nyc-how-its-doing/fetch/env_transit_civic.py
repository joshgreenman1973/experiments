#!/usr/bin/env python3
"""Fetcher for the "env_transit_civic" group of How New York Is Doing (New York in 2025).

Run from the project folder:  python3 -I fetch/env_transit_civic.py

Downloads source files into data/raw/env_transit_civic/ and writes data/indicators/<id>.json for:
  fine_particle_pollution, heat_deaths, ghg_emissions, parkscore, transit_ridership, bus_speeds,
  street_cleanliness, voter_turnout, volunteering, debt_per_resident, tax_burden

Every number written comes from a file this script downloads (or, for street cleanliness, from the
read-only mmr-explorer project plus Mayor's Management Report PDFs it downloads). Nothing is typed in.
The script exits non-zero if any download is empty or fails, or if any measure cannot be built; a
measure that fails is not written.

Set OFFLINE=1 to rebuild from the cached raw files without touching the network.

PDF parsing uses PyMuPDF (fitz); Excel parsing uses openpyxl; the volunteering microdata (Stata) uses
pandas. Under `python3 -I` the user site-packages directory is not on sys.path, so it is appended
(at the end, after the standard library) when present.
"""
import csv
import datetime as dt
import html
import io
import json
import os
import re
import shutil
import site
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile

_us = site.getusersitepackages()
if os.path.isdir(_us) and _us not in sys.path:
    sys.path.append(_us)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "env_transit_civic")
OUT = os.path.join(ROOT, "data", "indicators")
PEERS = json.load(open(os.path.join(ROOT, "data", "peers.json")))
PEER_NAMES = [c["name"] for c in PEERS["cities"]]
NAMED_PEERS = PEERS.get("named_peers", [])
TODAY = dt.date.today().isoformat()
UA = "Mozilla/5.0 (compatible; civic-data-fetch/1.0)"
OFFLINE = os.environ.get("OFFLINE") == "1"
MMR_EXPLORER = os.path.join(os.path.dirname(ROOT), "mmr-explorer", "data", "indicators.json")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


class FetchError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------
# Download helpers
# --------------------------------------------------------------------------------------------
def http_get(url, tries=6, timeout=300, redact=None):
    """GET with retry/backoff. Socrata 403/429 are throttling, so they are retried too."""
    shown = url if not redact else url.replace(redact, "REDACTED")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = "HTTP %s" % e.code
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(min(60, 3 * 2 ** i))
                continue
            raise FetchError("%s for %s" % (last, shown)) from None
        except Exception as e:  # network errors
            last = type(e).__name__
            time.sleep(min(60, 3 * 2 ** i))
    raise FetchError("gave up after %d tries (%s): %s" % (tries, last, shown))


def fetch_file(url, name, min_bytes=200, expect=None):
    """Download url into RAW/name (or read the cache when OFFLINE=1). Raise if empty/short/wrong type."""
    path = os.path.join(RAW, name)
    if OFFLINE:
        if not os.path.exists(path):
            raise FetchError("OFFLINE and no cached file %s" % name)
        return path
    data = http_get(url)
    if not data or len(data) < min_bytes:
        raise FetchError("empty or short download (%d bytes): %s" % (len(data or b""), url))
    if expect == "pdf" and not data.startswith(b"%PDF"):
        raise FetchError("not a PDF: %s" % url)
    if expect == "zip" and not data.startswith(b"PK"):
        raise FetchError("not a zip/xlsx: %s" % url)
    with open(path, "wb") as f:
        f.write(data)
    return path


def socrata(domain, dataset, params, name):
    """SoQL query against a keyless Socrata endpoint; cached as JSON. Raise on empty result."""
    path = os.path.join(RAW, name)
    if OFFLINE:
        rows = json.load(open(path))
    else:
        url = "https://%s/resource/%s.json?%s" % (domain, dataset, urllib.parse.urlencode(params))
        rows = json.loads(http_get(url).decode("utf-8"))
        with open(path, "w") as f:
            json.dump(rows, f)
    if not rows:
        raise FetchError("empty Socrata result for %s %s" % (dataset, params))
    return rows


def socrata_url(domain, dataset, params):
    return "https://%s/resource/%s.json?%s" % (domain, dataset, urllib.parse.urlencode(params))


def census_key():
    try:
        k = subprocess.run(["security", "find-generic-password", "-s", "CENSUS_API_KEY", "-w"],
                           capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        raise FetchError("could not read CENSUS_API_KEY from the keychain") from None
    if not k:
        raise FetchError("empty CENSUS_API_KEY")
    return k


def census(year, dataset, getvars, geo_for, geo_in, name):
    """Census API call. The key is never printed or stored; only the response is cached."""
    path = os.path.join(RAW, name)
    if OFFLINE:
        data = json.load(open(path))
    else:
        key = census_key()
        q = {"get": ",".join(getvars), "for": geo_for}
        if geo_in:
            q["in"] = geo_in
        url = "https://api.census.gov/data/%s/%s?%s&key=%s" % (year, dataset, urllib.parse.urlencode(q), key)
        data = json.loads(http_get(url, redact=key).decode("utf-8"))
        with open(path, "w") as f:
            json.dump(data, f)
    if not data or len(data) < 2:
        raise FetchError("empty Census response %s %s" % (year, getvars))
    hdr = data[0]
    return [dict(zip(hdr, r)) for r in data[1:]]


def html_text(raw):
    t = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))


def fitz_mod():
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise FetchError("PyMuPDF (fitz) is required to read the PDF sources") from None
    return fitz


def pdf_pages(path):
    fitz = fitz_mod()
    d = fitz.open(path)
    return [p.get_text() for p in d]


def num(s):
    s = str(s).replace(",", "").replace("$", "").replace("%", "").strip()
    return float(s)


def write(ind):
    if ind["status"] != "missing" and not ind.get("series"):
        raise FetchError("refusing to write %s with an empty series" % ind["id"])
    for s in ind.get("series") or []:
        if s["value"] is None:
            raise FetchError("null value in series for %s" % ind["id"])
    if ind.get("peers"):
        for v in ind["peers"]["values"]:
            if v["city"] not in PEER_NAMES:
                raise FetchError("unknown peer city %r in %s" % (v["city"], ind["id"]))
    path = os.path.join(OUT, ind["id"] + ".json")
    with open(path, "w") as f:
        json.dump(ind, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("  wrote", os.path.relpath(path, ROOT))


def base(id_, name, definition, units, fmt, better):
    return {"id": id_, "status": "ok", "status_reason": None, "name": name, "definition": definition,
            "units": units, "format": fmt, "better": better, "frequency": "annual", "series": [],
            "latest_period": None, "latest_extra": None, "source": None, "peers": None,
            "peer_series": None, "breakdowns": [], "method": "", "caveats": []}


def src(name, url, endpoint):
    return {"name": name, "url": url, "endpoint": endpoint, "fetched": TODAY}


# --------------------------------------------------------------------------------------------
# 1. Fine particles (PM2.5)
# --------------------------------------------------------------------------------------------
PEER_COUNTY = {  # principal county of each peer city (state FIPS, county FIPS)
    "Los Angeles": ("06", "037", "Los Angeles County, CA"), "Chicago": ("17", "031", "Cook County, IL"),
    "Houston": ("48", "201", "Harris County, TX"), "Phoenix": ("04", "013", "Maricopa County, AZ"),
    "Philadelphia": ("42", "101", "Philadelphia County, PA"), "San Antonio": ("48", "029", "Bexar County, TX"),
    "San Diego": ("06", "073", "San Diego County, CA"), "Dallas": ("48", "113", "Dallas County, TX"),
    "Fort Worth": ("48", "439", "Tarrant County, TX"), "Jacksonville": ("12", "031", "Duval County, FL"),
    "Austin": ("48", "453", "Travis County, TX"), "San Jose": ("06", "085", "Santa Clara County, CA"),
    "Charlotte": ("37", "119", "Mecklenburg County, NC"), "Columbus": ("39", "049", "Franklin County, OH"),
    "Indianapolis": ("18", "097", "Marion County, IN"), "San Francisco": ("06", "075", "San Francisco County, CA"),
    "Seattle": ("53", "033", "King County, WA"), "Denver": ("08", "031", "Denver County, CO"),
    "Nashville-Davidson": ("47", "037", "Davidson County, TN"), "Oklahoma City": ("40", "109", "Oklahoma County, OK"),
    "Washington, D.C.": ("11", "001", "District of Columbia"), "El Paso": ("48", "141", "El Paso County, TX"),
    "Las Vegas": ("32", "003", "Clark County, NV"), "Boston": ("25", "025", "Suffolk County, MA"),
}
NYC_COUNTIES = {"005": "Bronx", "047": "Kings (Brooklyn)", "061": "New York (Manhattan)",
                "081": "Queens", "085": "Richmond (Staten Island)"}


def fine_particle_pollution():
    ind = base("fine_particle_pollution", "Fine-particle air pollution (PM2.5)",
               "Citywide annual average concentration of fine particulate matter (PM2.5), in micrograms per "
               "cubic meter, from the NYC Community Air Survey (NYCCAS).",
               "micrograms per cubic meter", "dec1", "down")
    params = {"$select": "name,measure,geo_type_name,geo_place_name,time_period,start_date,data_value",
              "$where": "name='Fine particles (PM 2.5)' AND measure='Annual mean' AND "
                        "geo_type_name in ('Citywide','Borough')",
              "$order": "start_date,geo_place_name", "$limit": "5000"}
    rows = socrata("data.cityofnewyork.us", "c3uy-2p5r", params, "nycod_air_quality_pm25.json")
    city = {}
    boro = {}
    for r in rows:
        y = r["time_period"].strip()
        if not re.fullmatch(r"\d{4}", y):
            raise FetchError("unexpected NYCCAS time_period %r" % y)
        v = round(float(r["data_value"]), 2)
        if r["geo_type_name"] == "Citywide":
            if y in city:
                raise FetchError("duplicate citywide PM2.5 row for %s" % y)
            city[y] = v
        else:
            boro.setdefault(y, {})[r["geo_place_name"]] = v
    years = sorted(city)
    if len(years) < 10:
        raise FetchError("too few NYCCAS years")
    ind["series"] = [{"period": y, "value": city[y], "moe": None} for y in years]
    latest = years[-1]
    ind["latest_period"] = latest
    if latest in boro and len(boro[latest]) == 5:
        ind["breakdowns"].append({"by": "borough", "period": latest,
                                  "source_url": "https://data.cityofnewyork.us/Environment/Air-Quality/c3uy-2p5r",
                                  "values": [{"name": k, "value": v, "moe": None} for k, v in sorted(boro[latest].items())]})
    ind["source"] = src("NYC Department of Health and Mental Hygiene, NYC Community Air Survey, via NYC Open Data "
                        "'Air Quality' (c3uy-2p5r), indicator 'Fine particles (PM 2.5)', measure 'Annual mean'",
                        "https://data.cityofnewyork.us/Environment/Air-Quality/c3uy-2p5r",
                        socrata_url("data.cityofnewyork.us", "c3uy-2p5r", params))
    ind["method"] = ("Rows of the NYC Open Data Air Quality dataset with name 'Fine particles (PM 2.5)', measure "
                     "'Annual mean' and geography 'Citywide' (series) or 'Borough' (breakdown). Values are the "
                     "Health Department's published modeled annual averages in micrograms per cubic meter, "
                     "rounded to two decimals here. Years are labeled as the dataset labels them.")
    ind["caveats"] = [
        "NYCCAS annual averages are modeled from a network of street-level monitors and land-use data; they are "
        "the Health Department's estimates of typical exposure, not regulatory monitor readings.",
        "The latest published NYCCAS annual average is for %s; a 2025 value had not been released when this "
        "was fetched." % latest,
    ]

    # Peers: EPA annual PM2.5 design values by county (regulatory monitors).
    epa_page = "https://www.epa.gov/air-trends/air-quality-design-values"
    page = http_get(epa_page).decode("utf-8", "replace") if not OFFLINE else open(os.path.join(RAW, "epa_design_values_page.html")).read()
    if not OFFLINE:
        open(os.path.join(RAW, "epa_design_values_page.html"), "w").write(page)
    links = re.findall(r'href="([^"]*pm25_designvalues_(\d{4})_(\d{4})_final[^"]*\.xlsx)"', page, re.I)
    if not links:
        raise FetchError("no PM2.5 design value workbook link found on EPA page")
    links.sort(key=lambda x: int(x[2]))
    xurl, y0, y1 = links[-1]
    xurl = urllib.parse.urljoin(epa_page, xurl)
    xpath = fetch_file(xurl, "epa_pm25_designvalues_%s_%s.xlsx" % (y0, y1), min_bytes=100000, expect="zip")
    import openpyxl
    wb = openpyxl.load_workbook(xpath, read_only=True)
    ws = [w for w in wb.worksheets if w.title.lower().startswith("table4a")]
    if not ws:
        raise FetchError("EPA workbook has no Table4a sheet")
    dv = {}
    hdr = None
    for r in ws[0].iter_rows(values_only=True):
        if r and r[0] == "State Name":
            hdr = list(r)
            continue
        if hdr and r and r[2] and r[3]:
            col = [i for i, h in enumerate(hdr) if h and "Design Value" in str(h)][0]
            try:
                dv[(str(r[2]).zfill(2), str(r[3]).zfill(3))] = (float(r[col]), r[1], r[0])
            except (TypeError, ValueError):
                pass
    if len(dv) < 300:
        raise FetchError("EPA county design value table looks incomplete (%d rows)" % len(dv))
    nyc = {c: dv.get(("36", c)) for c in NYC_COUNTIES}
    have = {c: v for c, v in nyc.items() if v}
    vals = []
    missing = []
    if have:
        top = max(have.items(), key=lambda kv: kv[1][0])
        vals.append({"city": "New York", "value": top[1][0], "moe": None,
                     "geo_name": "Highest of NYC's five counties (%s County)" % top[1][1]})
    for city, (sf, cf, label) in PEER_COUNTY.items():
        v = dv.get((sf, cf))
        if v:
            vals.append({"city": city, "value": v[0], "moe": None, "geo_name": label})
        else:
            missing.append("%s (%s)" % (city, label))
    nyc_txt = "; ".join("%s %s" % (NYC_COUNTIES[c], ("%.1f" % v[0]) if v else "no valid value") for c, v in nyc.items())
    note = ("Different method from the NYC series: these are EPA regulatory annual PM2.5 design values for %s-%s "
            "(the three-year average of annual means at the highest valid monitor in each county), for each peer "
            "city's principal county. New York is shown as the highest of its five counties, which is how a "
            "county-style design value is defined; by county: %s." % (y0, y1, nyc_txt))
    if missing:
        note += " No valid design value for: %s." % ", ".join(missing)
    ind["peers"] = {"period": "%s-%s" % (y0, y1), "geography": "county", "note": note,
                    "source": src("U.S. EPA, Air Quality Design Values, PM2.5 %s-%s, Table 4a (county-level annual "
                                  "design values)" % (y0, y1), epa_page, xurl),
                    "values": vals}
    write(ind)


# --------------------------------------------------------------------------------------------
# 2. Heat deaths
# --------------------------------------------------------------------------------------------
def heat_deaths():
    ind = base("heat_deaths", "Heat-related deaths",
               "Deaths of New York City residents caused directly by heat (heat stroke and other heat illness "
               "coded X30 or T67 on the death certificate), May through September, by year.",
               "deaths", "int", "down")
    rep_url = "https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/heat-report/"
    rep = fetch_file(rep_url, "heat_report_current.html", min_bytes=20000)
    rep_html = open(rep, encoding="utf-8", errors="replace").read()
    rep_txt = html_text(rep_html)
    title = re.search(r"<title>\s*(\d{4}) Heat Mortality Report", rep_html)
    if not title:
        raise FetchError("could not identify the edition of the current heat mortality report")
    edition = title.group(1)
    dw = re.search(r"Figure 1\s*</strong>\s*:?\s*Heat-stress deaths by year.*?datawrapper\.dwcdn\.net/([A-Za-z0-9]{5})/",
                   rep_html, re.S)
    if not dw:
        raise FetchError("could not find the Figure 1 chart in the heat report")
    chart = dw.group(1)
    embed = http_get("https://datawrapper.dwcdn.net/%s/embed.js" % chart).decode("utf-8", "replace") if not OFFLINE else ""
    vers = sorted(set(int(v) for v in re.findall(r"%s/(\d+)/" % chart, embed))) or [1]
    csv_url = "https://datawrapper.dwcdn.net/%s/%d/dataset.csv" % (chart, vers[-1])
    cpath = fetch_file(csv_url, "heat_report_%s_fig1.csv" % edition, min_bytes=20)
    recent = {}
    for line in open(cpath).read().strip().splitlines()[1:]:
        p = re.split(r"[\t,]", line.strip())
        recent[p[0]] = int(float(p[1]))
    if len(recent) < 8:
        raise FetchError("heat-stress chart data too short")
    tot = re.search(r"there were (\d+) heat-stress deaths from (\d{4})-(\d{4})", rep_txt)
    if tot and sum(recent.values()) != int(tot.group(1)):
        raise FetchError("heat chart counts do not sum to the report's stated total")

    # Earlier years: table in the 2021 report (2010-2019; 2019 provisional there).
    old_url = "https://a816-dohbesp.nyc.gov/IndicatorPublic/data-features/heat-report-archive/2021/"
    old = html_text(open(fetch_file(old_url, "heat_report_2021.html", min_bytes=20000), encoding="utf-8",
                         errors="replace").read())
    i = old.find("Year n (deaths)")
    if i < 0:
        raise FetchError("2021 heat report table not found")
    early = {}
    for m in re.finditer(r"\b(20[01]\d)\*?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", old[i:i + 1200]):
        early[m.group(1)] = int(m.group(2))
    if len(early) < 8:
        raise FetchError("could not parse the 2021 heat report table")
    # Cross-check overlapping years.
    overlap = [y for y in early if y in recent and int(y) <= 2018]
    for y in overlap:
        if early[y] != recent[y]:
            raise FetchError("heat-stress deaths for %s differ between reports (%s vs %s)" % (y, early[y], recent[y]))
    series = {}
    for y, v in early.items():
        if y not in recent:
            series[y] = (v, "2021 report")
    for y, v in recent.items():
        series[y] = (v, "%s report" % edition)
    years = sorted(series)
    ind["series"] = [{"period": y, "value": series[y][0], "moe": None} for y in years]
    ind["latest_period"] = years[-1]
    ex = re.search(r"average of about (\d+) heat-exacerbated deaths \(caused indirectly[^)]*\) per year from (\d{4})-(\d{4})", rep_txt)
    ex_txt = ("The report's estimate of heat-exacerbated (excess) deaths, about %s a year on average for %s-%s, is "
              "published only as a multi-year average from a statistical model, not as annual counts, so it cannot "
              "be used as the annual series." % (ex.group(1), ex.group(2), ex.group(3))) if ex else \
        "The report's heat-exacerbated (excess) death estimate is published only as a multi-year average, not annually."
    ind["source"] = src("NYC Department of Health and Mental Hygiene, %s NYC Heat-Related Mortality Report "
                        "(Figure 1) and 2021 report (heat-stress death table)" % edition, rep_url, csv_url)
    ind["method"] = ("Annual counts of heat-stress deaths among NYC residents, May-September. %s-%s are the Figure 1 "
                     "values of the %s Heat-Related Mortality Report (read from the chart's published data file); "
                     "%s-%s are from the table in the 2021 report (%s). Overlapping years %s match in both reports."
                     % (min(recent), max(recent), edition, years[0], max(y for y in early if y not in recent),
                        old_url, ", ".join(sorted(overlap))))
    ind["caveats"] = [
        "This is the heat-stress (directly caused) count, not the larger heat-exacerbated estimate. " + ex_txt,
        "Counts are small and swing with single heat waves: the %s report counts 21 heat-stress deaths in 2025, "
        "19 of them from the June 22-25 heat wave." % edition if "2025" in recent else
        "Counts are small and swing with single heat waves.",
        "The %s report says the most recent year's count is provisional because mortality records are not yet "
        "final." % edition,
    ]
    write(ind)


# --------------------------------------------------------------------------------------------
# 3. Greenhouse gas emissions
# --------------------------------------------------------------------------------------------
def ghg_emissions():
    ind = base("ghg_emissions", "Citywide greenhouse gas emissions",
               "Total citywide greenhouse gas emissions from the City's annual inventory, in million metric tons of "
               "CO2-equivalent (100-year global warming potential), by calendar year.",
               "million metric tons CO2e", "dec1", "down")
    params = {"$limit": "5000"}
    rows = socrata("data.cityofnewyork.us", "wq7q-htne", params, "nycod_ghg_inventory.json")
    meta_raw = http_get("https://data.cityofnewyork.us/api/views/wq7q-htne.json") if not OFFLINE else \
        open(os.path.join(RAW, "nycod_ghg_inventory_meta.json"), "rb").read()
    if not OFFLINE:
        open(os.path.join(RAW, "nycod_ghg_inventory_meta.json"), "wb").write(meta_raw)
    meta = json.loads(meta_raw)
    total = [r for r in rows if r.get("inventory_type") == "Total"]
    if len(total) != 1:
        raise FetchError("expected exactly one Total row in the GHG inventory")
    t = total[0]
    yearcol = {}
    for k in t:
        m = re.fullmatch(r"cy_(\d{4})_tco2e(_100_yr_gwp)?", k)
        if m:
            yearcol[m.group(1)] = k
    years = sorted(yearcol)
    if len(years) < 15:
        raise FetchError("GHG inventory has too few years")
    series = []
    for y in years:
        tot = float(t[yearcol[y]])
        parts = sum(float(r.get(yearcol[y]) or 0) for r in rows if r.get("inventory_type") != "Total")
        if abs(parts - tot) > 0.001 * tot:
            raise FetchError("GHG sector rows do not sum to the Total row for %s" % y)
        series.append({"period": y, "value": round(tot / 1e6, 2), "moe": None})
    ind["series"] = series
    latest = years[-1]
    ind["latest_period"] = latest
    sect = {}
    for r in rows:
        if r.get("inventory_type") == "Total":
            continue
        sect[r["sectors_sector"]] = sect.get(r["sectors_sector"], 0) + float(r.get(yearcol[latest]) or 0)
    ind["breakdowns"].append({"by": "sector", "period": latest,
                              "source_url": "https://data.cityofnewyork.us/Environment/NYC-Greenhouse-Gas-Emissions-Inventory/wq7q-htne",
                              "values": [{"name": k, "value": round(v / 1e6, 2), "moe": None}
                                         for k, v in sorted(sect.items(), key=lambda kv: -kv[1]) if v > 0]})
    clcpa = [r for r in rows if r.get("inventory_type") == "CLCPA Addition"]
    clcpa_nonzero = any(float(r.get(yearcol[y]) or 0) for r in clcpa for y in years)
    ind["source"] = src("NYC Mayor's Office of Climate and Environmental Justice, Inventory of New York City "
                        "Greenhouse Gas Emissions, via NYC Open Data (wq7q-htne)",
                        "https://data.cityofnewyork.us/Environment/NYC-Greenhouse-Gas-Emissions-Inventory/wq7q-htne",
                        socrata_url("data.cityofnewyork.us", "wq7q-htne", params))
    ind["method"] = ("The dataset's 'Total' row, column tCO2e for each calendar year (100-year global warming "
                     "potential; the 2005-2009 columns are labeled tco2e_100_yr_gwp and later ones tco2e), divided by "
                     "one million. The script checks that the sector rows add up to the Total row each year. The sector "
                     "breakdown sums the rows of each sector for %s." % latest)
    ind["caveats"] = [
        "The open dataset carries the whole 2005-%s series as recalculated in the current inventory, so earlier "
        "years can differ from the figures first published in older inventory reports; the dataset itself does not "
        "describe the restatements (dataset description: %r)." % (latest, (meta.get("description") or "")[:160]),
        "Covers emissions inside the city plus electricity generated elsewhere for city use, under the Global "
        "Protocol for Community-Scale inventories; a 20-year-GWP version of each value is also in the dataset.",
    ]
    if clcpa:
        ind["caveats"].append("The dataset includes 'CLCPA Addition' rows (state climate-law accounting additions); "
                              + ("they are nonzero in some years and are included in the Total." if clcpa_nonzero
                                 else "they are zero in every year, so they do not affect the totals."))
    write(ind)


# --------------------------------------------------------------------------------------------
# 4. ParkScore
# --------------------------------------------------------------------------------------------
TPL_PEER = {"New York": "New York", "Los Angeles": "Los Angeles", "Chicago": "Chicago", "Houston": "Houston",
            "Phoenix": "Phoenix", "Philadelphia": "Philadelphia", "San Antonio": "San Antonio",
            "San Diego": "San Diego", "Dallas": "Dallas", "Fort Worth": "Fort Worth",
            "Jacksonville": "Jacksonville", "Austin": "Austin", "San Jose": "San Jose", "Charlotte": "Charlotte",
            "Columbus": "Columbus", "Indianapolis": "Indianapolis", "San Francisco": "San Francisco",
            "Seattle": "Seattle", "Denver": "Denver", "Nashville": "Nashville-Davidson",
            "Oklahoma City": "Oklahoma City", "Washington": "Washington, D.C.", "El Paso": "El Paso",
            "Las Vegas": "Las Vegas", "Boston": "Boston"}


def parse_parkscore(path, year):
    """Rows by word position: rank, city name, ..., total score (then the city name repeated, from 2016 on)."""
    fitz = fitz_mod()
    dec = re.compile(r"^\d{1,3}\.\d$")
    out = []
    for page in fitz.open(path):
        words = page.get_text("words")
        if page.rotation in (90, 270):
            sgn = -1 if page.rotation == 90 else 1
            words = [(w[1] * sgn, w[0], w[3] * sgn, w[2], w[4]) for w in words]
            words = [(min(a, c), b, max(a, c), d, e) for a, b, c, d, e in words]
        rows = []
        for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
            yc = (w[1] + w[3]) / 2
            if rows and abs(rows[-1][0] - yc) < 2.5:
                rows[-1][1].append(w)
            else:
                rows.append([yc, [w]])
        for _, ws in rows:
            t = [w[4] for w in sorted(ws, key=lambda w: w[0])]
            if not t or not re.fullmatch(r"T?\d{1,3}", t[0]):
                continue
            name, k = [], 1
            while k < len(t) and re.match(r"[A-Za-z]", t[k]):
                name.append(t[k])
                k += 1
            if not name or k >= len(t):
                continue
            rest = t[k:]
            while rest and re.match(r"[A-Za-z]", rest[-1]):
                rest = rest[:-1]
            sc = None
            if year <= 2017:  # ..., total score, park-bench rating
                for j in range(len(rest) - 1, 0, -1):
                    if re.fullmatch(r"[0-5]\.[05]", rest[j]) and dec.match(rest[j - 1]) and float(rest[j - 1]) >= 15:
                        sc = rest[j - 1]
                        break
            elif rest and dec.match(rest[-1]):
                sc = rest[-1]
            if sc is None:
                continue
            out.append({"rank": int(t[0].lstrip("T")), "name": " ".join(name), "score": float(sc)})
    return out


def tpl_peer(name):
    base_name = re.split(r",|-| County", name)[0].strip()
    base_name = base_name.replace("D.C.", "").strip()
    if base_name.startswith("New York"):
        return "New York"
    if base_name == "North Las Vegas":
        return None
    return TPL_PEER.get(base_name)


def parkscore():
    ind = base("parkscore", "Trust for Public Land ParkScore",
               "New York City's overall ParkScore (0-100) from the Trust for Public Land's annual index of park "
               "systems in the largest U.S. cities, by index year.", "score (0-100)", "dec1", "up")
    results = {}
    urls = {}
    first_year, last_year = 2012, dt.date.today().year
    for y in range(first_year, last_year + 1):
        url = "https://parkserve.tpl.org/downloads/historic/%d_ParkScoreRank.pdf" % y
        try:
            p = fetch_file(url, "tpl_parkscore_%d.pdf" % y, min_bytes=20000, expect="pdf")
        except FetchError:
            if y == last_year:  # the current year's index may not be out yet
                continue
            raise
        rows = parse_parkscore(p, y)
        if len(rows) < 35:
            raise FetchError("ParkScore %d: parsed only %d rows" % (y, len(rows)))
        results[y] = rows
        urls[y] = url
    series, ranks = [], []
    for y, rows in sorted(results.items()):
        ny = [r for r in rows if r["name"].startswith("New York")]
        if len(ny) != 1:
            raise FetchError("ParkScore %d: New York row not found uniquely" % y)
        series.append({"period": str(y), "value": ny[0]["score"], "moe": None})
        ranks.append({"period": str(y), "rank": ny[0]["rank"], "cities_ranked": len(rows)})
    ind["series"] = series
    latest = max(results)
    ind["latest_period"] = str(latest)
    ind["rank_series"] = ranks
    peer_vals, seen = [], {}
    for r in results[latest]:
        c = tpl_peer(r["name"])
        if c and c not in seen:
            seen[c] = r
            peer_vals.append({"city": c, "value": r["score"], "moe": None,
                              "geo_name": "%s (rank %d)" % (r["name"], r["rank"])})
    absent = [c for c in PEER_NAMES if c not in seen]
    ind["peers"] = {"period": str(latest), "geography": "city",
                    "note": "Overall ParkScore from the %d index (ranks among the %d cities in the PDF). Not in "
                            "the %d ranking PDF: %s." % (latest, len(results[latest]), latest, ", ".join(absent) or "none"),
                    "source": src("Trust for Public Land, %d ParkScore rankings" % latest,
                                  "https://www.tpl.org/parkscore", urls[latest]),
                    "values": peer_vals}
    ps = {}
    for nm in NAMED_PEERS:
        pts = []
        for y, rows in sorted(results.items()):
            m = [r for r in rows if tpl_peer(r["name"]) == nm]
            if m:
                pts.append({"period": str(y), "value": m[0]["score"]})
        ps[nm] = pts
    ind["peer_series"] = ps
    ind["source"] = src("Trust for Public Land, ParkScore index ranking PDFs, %d-%d" % (min(results), latest),
                        "https://www.tpl.org/parkscore", urls[latest])
    ind["method"] = ("Each year's official ranking PDF (parkserve.tpl.org/downloads/historic/<year>_ParkScoreRank.pdf) "
                     "is read by word position; for each city row the script takes the rank and the total score "
                     "out of 100. For 2012-2017 the score is the column just before the park-bench rating; from 2018 "
                     "on it is the last number before the repeated city name. NYC's rank by year is in "
                     "rank_series.")
    nyl = ranks[-1]
    ind["caveats"] = [
        "Index years are the years TPL published the rankings; the %d index is built mostly from data gathered in "
        "%d." % (latest, latest - 1),
        "TPL changed the scoring several times (scores through 2017 were published alongside a park-bench "
        "rating, the system was overhauled in 2019 and an equity component was added in 2020), and the number of "
        "cities ranked grew from %d in %d to about 100, so scores and ranks are not strictly comparable across years."
        % (ranks[0]["cities_ranked"], min(results)),
        "New York ranked %d in %d." % (nyl["rank"], latest),
    ]
    if latest >= 2026 and "Las Vegas" in absent:
        ind["caveats"].append("In the 2026 PDF the row ranked 95 is labeled Louisville-Jefferson County at the left "
                              "and Las Vegas at the right; its figures match Louisville's 2025 row, so it is read as "
                              "Louisville and Las Vegas is left out of the peers.")
    write(ind)


# --------------------------------------------------------------------------------------------
# 5. Transit ridership
# --------------------------------------------------------------------------------------------
NTD_AGENCY = {  # main transit agency per peer city, by NTD ID
    "New York": (["20008", "20188"], "MTA New York City Transit + MTA Bus Company"),
    "Los Angeles": (["90154"], "Los Angeles County Metropolitan Transportation Authority"),
    "Chicago": (["50066"], "Chicago Transit Authority"),
    "Houston": (["60008"], "Metropolitan Transit Authority of Harris County"),
    "Phoenix": (["90032"], "City of Phoenix Public Transit"),
    "Philadelphia": (["30019"], "SEPTA"),
    "San Antonio": (["60011"], "VIA Metropolitan Transit"),
    "San Diego": (["90026"], "San Diego Metropolitan Transit System"),
    "Dallas": (["60056"], "Dallas Area Rapid Transit"),
    "Fort Worth": (["60007"], "Fort Worth Transportation Authority (Trinity Metro)"),
    "Jacksonville": (["40040"], "Jacksonville Transportation Authority"),
    "Austin": (["60048"], "Capital Metropolitan Transportation Authority"),
    "San Jose": (["90013"], "Santa Clara Valley Transportation Authority"),
    "Charlotte": (["40008"], "City of Charlotte (CATS)"),
    "Columbus": (["50016"], "Central Ohio Transit Authority"),
    "Indianapolis": (["50050"], "Indianapolis Public Transportation Corp. (IndyGo)"),
    "San Francisco": (["90015"], "San Francisco Municipal Transportation Agency"),
    "Seattle": (["00001"], "King County Metro"),
    "Denver": (["80006"], "Denver Regional Transportation District"),
    "Nashville-Davidson": (["40004"], "Metropolitan Transit Authority (WeGo)"),
    "Oklahoma City": (["60017"], "Central Oklahoma Transportation and Parking Authority (EMBARK)"),
    "Washington, D.C.": (["30030"], "Washington Metropolitan Area Transit Authority"),
    "El Paso": (["60006"], "City of El Paso (Sun Metro)"),
    "Las Vegas": (["90045"], "Regional Transportation Commission of Southern Nevada"),
    "Boston": (["10003"], "Massachusetts Bay Transportation Authority"),
}


def transit_ridership():
    ind = base("transit_ridership", "Subway and bus ridership",
               "Annual MTA subway ridership plus MTA New York City Transit and MTA Bus Company bus ridership, in "
               "millions of trips.", "million trips", "dec1", "up")
    # 2014-2018: MTA's published annual totals (2019 ridership page).
    page_url = "https://www.mta.info/agency/new-york-city-transit/subway-bus-ridership-2019"
    txt = html_text(open(fetch_file(page_url, "mta_subway_bus_ridership_2019.html", min_bytes=20000),
                         encoding="utf-8", errors="replace").read())

    def table(label):
        i = txt.find(label)
        if i < 0:
            raise FetchError("MTA page: %r not found" % label)
        seg = txt[i + len(label):i + 2000]
        stops = [seg.find(x) for x in ("Summary of", "Top 10") if seg.find(x) > 0]
        seg = seg[:min(stops)] if stops else seg
        out = {}
        for m in re.finditer(r"\b(20\d\d) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)", seg):
            out[m.group(1)] = num(m.group(6))
        if len(out) < 5:
            raise FetchError("MTA page: could not parse %r" % label)
        return out
    sub_pg = table("Summary of subway ridership")
    nyct_pg = table("Summary of bus ridership (New York City Transit)")
    mtab_pg = table("Summary of bus ridership (MTA Bus Company)")

    # 2019 on: MTA monthly ridership dataset.
    mparams = {"$select": "date_extract_y(month) as y,agency,count(*) as n,sum(ridership) as r",
               "$where": "agency in ('Subway','NYCT Bus','MTA Bus')", "$group": "y,agency", "$order": "y,agency"}
    mrows = socrata("data.ny.gov", "xfre-bxip", mparams, "mta_monthly_ridership_by_year.json")
    monthly = {}
    for r in mrows:
        monthly.setdefault(r["y"], {})[r["agency"]] = (float(r["r"]), int(r["n"]))
    series = {}
    for y in sorted(sub_pg):
        if int(y) <= 2018:
            series[y] = (sub_pg[y] + nyct_pg[y] + mtab_pg[y], "MTA 2019 ridership page")
    for y, d in sorted(monthly.items()):
        if int(y) < 2019 or len(d) != 3 or any(n != 12 for _, n in d.values()):
            continue
        series[y] = (sum(v for v, _ in d.values()), "MTA monthly ridership dataset")
    # continuity check for 2019 (in both sources)
    if "2019" in monthly:
        pg19 = sub_pg["2019"] + nyct_pg["2019"] + mtab_pg["2019"]
        ds19 = sum(v for v, _ in monthly["2019"].values())
        if abs(pg19 - ds19) / pg19 > 0.005:
            raise FetchError("MTA page and monthly dataset disagree on 2019 by more than 0.5%")
    years = sorted(series)
    ind["series"] = [{"period": y, "value": round(series[y][0] / 1e6, 1), "moe": None} for y in years]
    latest = years[-1]
    ind["latest_period"] = latest
    share = series[latest][0] / series["2019"][0] * 100
    ind["breakdowns"].append({"by": "mode", "period": latest,
                              "source_url": "https://data.ny.gov/Transportation/MTA-Monthly-Ridership-Traffic-Data-Beginning-Janua/xfre-bxip",
                              "values": [{"name": "Subway", "value": round(monthly[latest]["Subway"][0] / 1e6, 1), "moe": None},
                                         {"name": "NYC Transit bus", "value": round(monthly[latest]["NYCT Bus"][0] / 1e6, 1), "moe": None},
                                         {"name": "MTA Bus Company", "value": round(monthly[latest]["MTA Bus"][0] / 1e6, 1), "moe": None}]})

    # Daily dataset: cross-check and 2026-to-date versus the same days of 2025.
    dmax = socrata("data.ny.gov", "sayj-mze2", {"$select": "max(date) as d", "$where": "mode in ('Subway','Bus')"},
                   "mta_daily_maxdate.json")[0]["d"][:10]
    dparams = {"$select": "date_extract_y(date) as y,mode,count(*) as n,sum(count) as c",
               "$where": "mode in ('Subway','Bus')", "$group": "y,mode", "$order": "y,mode"}
    drows = socrata("data.ny.gov", "sayj-mze2", dparams, "mta_daily_by_year.json")
    daily = {}
    for r in drows:
        daily.setdefault(r["y"], {})[r["mode"]] = (float(r["c"]), int(r["n"]))
    end = dt.date.fromisoformat(dmax)
    prev_end = end.replace(year=end.year - 1)

    def ytd(y0, y1):
        q = {"$select": "sum(count) as c, count(*) as n",
             "$where": "mode in ('Subway','Bus') AND date between '%s' and '%sT23:59:59'" % (y0, y1)}
        r = socrata("data.ny.gov", "sayj-mze2", q, "mta_daily_ytd_%s.json" % y0[:4])[0]
        return float(r["c"]), int(r["n"])
    cur, ncur = ytd("%d-01-01" % end.year, end.isoformat())
    prv, nprv = ytd("%d-01-01" % prev_end.year, prev_end.isoformat())
    if ncur != nprv:
        raise FetchError("daily ridership: unequal day counts for YTD comparison")
    pct = (cur / prv - 1) * 100
    ind["latest_extra"] = {"period": "Jan. 1-%s, %d" % (end.strftime("%b. %-d"), end.year), "value": round(cur / 1e6, 1),
                           "note": "Subway plus bus trips so far this year, from the MTA daily ridership dataset; "
                                   "compares with %s million trips on the same dates of %d, %s %.1f percent."
                                   % (format(round(prv / 1e6, 1), ",.1f"), prev_end.year, "up" if pct >= 0 else "down",
                                      abs(pct))}
    cross = []
    for y in years:
        if y in daily and daily[y].get("Subway", (0, 0))[1] >= 365 and int(y) >= 2021:
            dsum = daily[y]["Subway"][0] + daily[y]["Bus"][0]
            msub = monthly[y]["Subway"][0]
            mbus = monthly[y]["NYCT Bus"][0] + monthly[y]["MTA Bus"][0]
            cross.append("%s subway %+.1f%%, bus %+.1f%%" % (y, (daily[y]["Subway"][0] / msub - 1) * 100,
                                                            (daily[y]["Bus"][0] / mbus - 1) * 100))

    # Peers: FTA National Transit Database monthly ridership (unlinked passenger trips, all modes).
    ids = sorted({i for v in NTD_AGENCY.values() for i in v[0]})
    nparams = {"$select": "ntd_id,date_extract_y(date) as y,sum(upt) as u,count(distinct date) as m",
               "$where": "ntd_id in (%s) AND ((date >= '2019-01-01' AND date < '2020-01-01') OR "
                         "(date >= '%s-01-01' AND date < '%d-01-01'))" % (",".join("'%s'" % i for i in ids), latest, int(latest) + 1),
               "$group": "ntd_id,y", "$limit": "5000"}
    nrows = socrata("data.transportation.gov", "8bui-9xvu", nparams, "ntd_monthly_upt_2019_%s.json" % latest)
    ntd = {}
    for r in nrows:
        ntd[(r["ntd_id"], r["y"])] = (float(r.get("u") or 0), int(r["m"]))
    mq = {"$select": "mode,date_extract_y(date) as y,sum(upt) as u",
          "$where": "ntd_id in ('20008','20188') AND date_extract_y(date) in (2019,%s)" % latest, "$group": "mode,y"}
    mr = socrata("data.transportation.gov", "8bui-9xvu", mq, "ntd_nyc_upt_by_mode.json")
    nm = {}
    for r in mr:
        nm[(r["mode"], r["y"])] = nm.get((r["mode"], r["y"]), 0) + float(r["u"])
    ntd_bus = (nm[("MB", latest)] + nm.get(("RB", latest), 0)) / (nm[("MB", "2019")] + nm.get(("RB", "2019"), 0)) * 100
    ntd_sub = nm[("HR", latest)] / nm[("HR", "2019")] * 100
    mta_bus = (monthly[latest]["NYCT Bus"][0] + monthly[latest]["MTA Bus"][0]) / \
        (monthly["2019"]["NYCT Bus"][0] + monthly["2019"]["MTA Bus"][0]) * 100
    mta_sub = monthly[latest]["Subway"][0] / monthly["2019"]["Subway"][0] * 100
    vals, skipped = [], []
    for city, (aids, label) in NTD_AGENCY.items():
        try:
            a19 = [ntd[(a, "2019")] for a in aids]
            a25 = [ntd[(a, latest)] for a in aids]
        except KeyError:
            skipped.append(city)
            continue
        if any(m != 12 for _, m in a19 + a25):
            skipped.append(city)
            continue
        u19 = sum(u for u, _ in a19)
        u25 = sum(u for u, _ in a25)
        vals.append({"city": city, "value": round(u25 / u19 * 100, 1), "moe": None,
                     "geo_name": "%s (NTD %s)" % (label, "+".join(aids))})
    ind["peers"] = {"period": latest, "geography": "transit agency",
                    "note": "%s ridership as a percent of 2019 for each city's main transit agency, using unlinked "
                            "passenger trips summed over all modes and service types in the FTA National Transit "
                            "Database monthly file. NYC here is MTA New York City Transit plus MTA Bus Company; NTD "
                            "counts every boarding (including transfers) and is estimated differently, and for NYC it recovers "
                            "much more than MTA's own counts: on NTD, NYC subway is %.1f%% and bus %.1f%% of 2019; on "
                            "MTA's own counts, subway %.1f%%, bus %.1f%%, combined %.1f%%. Treat the peer comparison as "
                            "rough. Agencies serve different areas than the city limits.%s" % (latest, ntd_sub, ntd_bus,
                                                                                     mta_sub, mta_bus, share,
                                                        (" Left out for incomplete months: " + ", ".join(skipped) + ".") if skipped else ""),
                    "source": src("Federal Transit Administration, National Transit Database, Complete Monthly "
                                  "Ridership (with adjustments and estimates)",
                                  "https://data.transportation.gov/Public-Transit/Complete-Monthly-Ridership-with-Adjustments-and-Es/8bui-9xvu",
                                  socrata_url("data.transportation.gov", "8bui-9xvu", nparams)),
                    "values": vals}
    ind["source"] = src("MTA, 'Subway and bus ridership for 2019' page (2014-2018) and MTA Monthly Ridership & "
                        "Traffic Data (data.ny.gov xfre-bxip, 2019 on)",
                        "https://data.ny.gov/Transportation/MTA-Monthly-Ridership-Traffic-Data-Beginning-Janua/xfre-bxip",
                        socrata_url("data.ny.gov", "xfre-bxip", mparams))
    ind["method"] = ("Annual subway ridership plus NYC Transit bus plus MTA Bus Company ridership. 2014-2018 are "
                     "the annual totals in the three summary tables on MTA's 2019 ridership page; 2019-%s are sums of "
                     "the twelve monthly values for agencies 'Subway', 'NYCT Bus' and 'MTA Bus' in the MTA monthly "
                     "dataset (years with fewer than 12 months are left out). The two sources agree on 2019 (checked "
                     "within 0.5%%). %s was %.1f%% of 2019. latest_extra compares the sum of daily Subway and Bus counts "
                     "from 1 January through the dataset's latest date (%s) with the same dates a year earlier."
                     % (latest, latest, share, dmax))
    ind["caveats"] = [
        "Staten Island Railway, commuter rail and paratransit are excluded.",
        "The MTA daily dataset (sayj-mze2) starts on 1 March 2020, so it cannot give full-year 2020; the monthly "
        "dataset is used for every year from 2019 so the series has one consistent source. Annual sums of the daily "
        "data differ from the monthly totals by: %s." % "; ".join(cross),
        "Pre-2014 annual totals were not used: the MTA pages carrying them could not be retrieved.",
        "2020-2022 reflect the pandemic collapse and recovery.",
    ]
    write(ind)


# --------------------------------------------------------------------------------------------
# 6. Bus speeds
# --------------------------------------------------------------------------------------------
def bus_speeds():
    ind = base("bus_speeds", "Average bus speed",
               "Average speed of MTA local, limited, Select Bus Service and express buses in New York City, in "
               "miles per hour: total bus miles divided by total operating hours across all routes and months.",
               "miles per hour", "dec1", "up")
    params = {"$select": "date_extract_y(month) as y,count(distinct month) as m,sum(total_mileage) as mi,"
                         "sum(total_operating_time) as hr", "$group": "y", "$order": "y"}
    rows = socrata("data.ny.gov", "cudb-vcni", params, "mta_bus_speeds_by_year.json")
    series = []
    partial = None
    for r in rows:
        y, m = r["y"], int(r["m"])
        sp = float(r["mi"]) / float(r["hr"])
        if m == 12:
            series.append({"period": y, "value": round(sp, 2), "moe": None})
        else:
            partial = (y, m)
    if len(series) < 5:
        raise FetchError("too few full years of bus speeds")
    ind["series"] = series
    latest = series[-1]["period"]
    ind["latest_period"] = latest
    if partial:
        y, m = partial
        q = {"$select": "date_extract_y(month) as y,sum(total_mileage) as mi,sum(total_operating_time) as hr,"
                        "count(distinct month) as m",
             "$where": "date_extract_m(month) <= %d AND date_extract_y(month) in (%s,%s)" % (m, int(y) - 1, y),
             "$group": "y", "$order": "y"}
        pr = socrata("data.ny.gov", "cudb-vcni", q, "mta_bus_speeds_ytd.json")
        d = {r["y"]: float(r["mi"]) / float(r["hr"]) for r in pr}
        mon = dt.date(2000, m, 1).strftime("%B")
        ind["latest_extra"] = {"period": "January-%s %s" % (mon, y), "value": round(d[y], 2),
                               "note": "Same calculation for January-%s; January-%s %d was %.2f mph."
                                       % (mon, mon, int(y) - 1, d[str(int(y) - 1)])}
    bq = {"$select": "borough,sum(total_mileage) as mi,sum(total_operating_time) as hr",
          "$where": "date_extract_y(month) = %s" % latest, "$group": "borough"}
    br = socrata("data.ny.gov", "cudb-vcni", bq, "mta_bus_speeds_borough_%s.json" % latest)
    ind["breakdowns"].append({"by": "borough", "period": latest,
                              "source_url": "https://data.ny.gov/Transportation/MTA-Bus-Speeds-Beginning-2015/cudb-vcni",
                              "values": [{"name": r["borough"], "value": round(float(r["mi"]) / float(r["hr"]), 2), "moe": None}
                                         for r in sorted(br, key=lambda r: r["borough"])]})
    meta = json.loads(http_get("https://data.ny.gov/api/views/cudb-vcni.json")) if not OFFLINE else {"name": "MTA Bus Speeds"}
    first = series[0]["period"]
    ind["source"] = src("MTA Bus Speeds (data.ny.gov cudb-vcni, '%s')" % meta.get("name"),
                        "https://data.ny.gov/Transportation/MTA-Bus-Speeds-Beginning-2015/cudb-vcni",
                        socrata_url("data.ny.gov", "cudb-vcni", params))
    ind["method"] = ("For each calendar year with all 12 months: sum of total_mileage divided by sum of "
                     "total_operating_time over every route, borough, trip type (local/limited, Select Bus Service, "
                     "express), day type and peak/off-peak period. This weights each route-month by its operating "
                     "hours (equivalently, it is total bus miles over total bus hours), rather than averaging route "
                     "speeds. The borough breakdown applies the same formula within each borough.")
    ind["caveats"] = [
        "The dataset is titled 'Beginning 2015' but its rows start in January %s, so there is no earlier history "
        "from this source." % first,
        "The dataset's column descriptions for mileage and operating time are swapped; the values (and the "
        "dataset's own average_speed field) confirm mileage divided by hours gives mph.",
    ]
    if len(series) < 10:
        ind["status"] = "partial"
        ind["status_reason"] = ("Only %d full years (%s-%s) are available, fewer than the 5-year baseline plus "
                                "10-year swing the report uses." % (len(series), first, latest))
    write(ind)


# --------------------------------------------------------------------------------------------
# 7. Street cleanliness
# --------------------------------------------------------------------------------------------
def mmr_row(path, label):
    pages = pdf_pages(path)
    for i, t in enumerate(pages):
        m = re.search(re.escape(label) + r"\s*\n((?:\s*(?:\d+\.\d%|NA)\s*\n){5})", t)
        if m:
            hdr = re.findall(r"FY\s?(\d{2})", t[max(0, m.start() - 2500):m.start()])
            vals = re.findall(r"(\d+\.\d|NA)", m.group(1))
            yrs = []
            for h in hdr:  # first run of five consecutive fiscal years before the row
                yrs.append(int(h))
            run = None
            for k in range(len(yrs) - 4):
                if yrs[k:k + 5] == list(range(yrs[k], yrs[k] + 5)):
                    run = yrs[k:k + 5]
            if not run:
                raise FetchError("could not read fiscal-year header in %s" % os.path.basename(path))
            return i + 1, {2000 + fy: (None if v == "NA" else float(v)) for fy, v in zip(run, vals)}
    raise FetchError("%r not found in %s" % (label, os.path.basename(path)))


def street_cleanliness():
    ind = base("street_cleanliness", "Streets rated acceptably clean",
               "Share of city streets rated acceptably clean by the Mayor's Office of Operations Scorecard "
               "inspection program, fiscal year average, as reported in the Mayor's Management Report.",
               "percent", "pct1", "up")
    vals, where = {}, {}
    pdfs = {}
    for fy in (2013, 2018, 2022):
        url = "https://www.nyc.gov/assets/operations/downloads/pdf/mmr%d/dsny.pdf" % fy
        p = fetch_file(url, "mmr%d_dsny.pdf" % fy, min_bytes=50000, expect="pdf")
        page, row = mmr_row(p, "Streets rated acceptably clean (%)")
        pdfs[fy] = (url, page, row)
    # Oldest edition first; later editions overwrite (they carry the latest restatements).
    for fy in sorted(pdfs):
        url, page, row = pdfs[fy]
        for y, v in row.items():
            if v is not None:
                vals[y] = v
                where[y] = "FY%d MMR, Department of Sanitation chapter, PDF page %d" % (fy, page)
    # mmr-explorer (read-only reuse): FY2023 comes from MMR open data, the indicator's final year.
    mx = json.load(open(MMR_EXPLORER))
    with open(os.path.join(RAW, "mmr_explorer_streets_acceptably_clean.json"), "w") as f:
        recs = [i for i in mx["ind"] if i["id"] == "13752"]
        json.dump({"builtAt": mx.get("builtAt"), "years": mx["years"], "records": recs}, f, indent=1)
    if len(recs) != 1 or "Streets rated acceptably clean" not in recs[0]["n"]:
        raise FetchError("mmr-explorer record 13752 (Streets rated acceptably clean) not found")
    for y, v in zip(mx["years"], recs[0]["v"]):
        if v is None:
            continue
        if y in vals and abs(vals[y] - v) > 0.05:
            raise FetchError("FY%d street cleanliness differs between MMR PDF (%s) and mmr-explorer (%s)" % (y, vals[y], v))
        if y not in vals:
            vals[y] = v
            where[y] = "MMR open data (rbed-zzin, June year-to-date value) via mmr-explorer"
    years = sorted(vals)
    ind["series"] = [{"period": "FY%d" % y, "value": vals[y], "moe": None} for y in years]
    ind["latest_period"] = "FY%d" % years[-1]
    # The FY2023 MMR's note on removing the indicator.
    u23 = "https://www.nyc.gov/assets/operations/downloads/pdf/mmr2023/2023_mmr.pdf"
    p23 = fetch_file(u23, "mmr2023_full.pdf", min_bytes=1000000, expect="pdf")
    rm_page = None
    for k, t in enumerate(pdf_pages(p23)):
        flat = re.sub(r"\s+", " ", t)
        if "Removed" in flat and "Streets rated acceptably clean" in flat and "being overhauled" in flat:
            rm_page = k + 1
            has70s = "1970s" in flat
            fixed = ("from 89.6 percent to 93.7 percent in Fiscal 2021" in flat and
                     "from 90.8 percent to 89.6 percent in Fiscal 2022" in flat)
            break
    if rm_page is None:
        raise FetchError("FY2023 MMR note removing the street cleanliness indicator not found")
    # Scorecard open data end date.
    sc = socrata("data.cityofnewyork.us", "rqhp-hivt", {"$select": "max(month) as m"}, "nycod_scorecard_maxmonth.json")
    sc_end = sc[0]["m"]
    gaps = [y for y in range(years[0], years[-1] + 1) if y not in vals]
    ind["status"] = "partial"
    ind["status_reason"] = ("The indicator ended after FY%d: the FY2023 MMR removed it while the Scorecard inspection "
                            "program is overhauled, and no FY2024-FY2026 values exist. %s"
                            % (years[-1], ("FY" + ", FY".join(map(str, gaps)) + " has no rating (MMR prints NA).") if gaps else ""))
    ind["source"] = src("Mayor's Management Report, Department of Sanitation indicator 'Streets rated acceptably "
                        "clean (%)' (FY2013, FY2018 and FY2022 editions), plus MMR open data for FY2023",
                        "https://www.nyc.gov/site/operations/performance/mmr.page", pdfs[2022][0])
    ind["method"] = ("Fiscal-year values printed in the Mayor's Management Report: each edition prints five fiscal "
                     "years, so the FY2013 edition supplies FY2009-FY2013, the FY2018 edition FY2014-FY2018 and the "
                     "FY2022 edition FY2018-FY2022 (where editions overlap the later one is used). FY2023 was never "
                     "printed in an MMR; it is the June year-to-date value in the MMR open data, as assembled in the "
                     "mmr-explorer project, which the script also uses to check FY2018 and FY2020-FY2022. Sources by "
                     "year: " + "; ".join("FY%d: %s" % (y, where[y]) for y in years) + ".")
    ind["caveats"] = [
        "No ratings were reported for FY2019 (the MMR prints NA).",
        "The FY2023 MMR (%s, PDF page %d) removed the indicator, saying the Scorecard street cleanliness inspection "
        "program is being overhauled%s.%s" % (u23, rm_page,
                                              " because its scoring system was developed in the 1970s" if has70s else "",
                                              (" The same note corrects values first misreported in the FY2022 MMR "
                                               "(FY2021 from 89.6 to 93.7, FY2022 from 90.8 to 89.6); the corrected "
                                               "values are used here.") if fixed else ""),
        "The Scorecard open dataset (rqhp-hivt) has no ratings after %s." % sc_end,
    ]
    write(ind)


# --------------------------------------------------------------------------------------------
# 8. Voter turnout
# --------------------------------------------------------------------------------------------
VOTE_FILES = {
    2025: ("https://www.vote.nyc/sites/default/files/pdf/election_results/2025/20251104General%20Election/"
           "00000100000Citywide%20Mayor%20Citywide%20Recap.csv", "csv"),
    2021: ("https://www.vote.nyc/sites/default/files/pdf/election_results/2021/20211102General%20Election/"
           "00000200000Citywide%20Mayor%20Citywide%20Recap.csv", "csv"),
    2017: ("https://www.vote.nyc/sites/default/files/pdf/election_results/2017/20171107General%20Election/"
           "00001100000Citywide%20Mayor%20Citywide%20Recap.csv", "csv"),
    2013: ("https://www.vote.nyc/sites/default/files/downloads/pdf/results/2013/2013GeneralElection/"
           "00001100000Citywide%20Mayor%20Citywide%20Recap.pdf", "pdf"),
    2009: ("https://www.vote.nyc/sites/default/files/downloads/pdf/results/2009/General/1.11CitywideMayorRecap.pdf", "pdf"),
    2005: ("https://www.vote.nyc/sites/default/files/downloads/pdf/results/2005/general/Manhattan/"
           "Croossover%20Mayor%20Re-Cap%20NYC.pdf", "pdf"),
}
COUNTY_BORO = {"New York County": ("Manhattan", "061"), "Bronx County": ("Bronx", "005"),
               "Kings County": ("Brooklyn", "047"), "Queens County": ("Queens", "081"),
               "Richmond County": ("Staten Island", "085")}


def mayor_votes(year):
    url, kind = VOTE_FILES[year]
    p = fetch_file(url, "boe_%d_general_mayor_recap.%s" % (year, kind), min_bytes=5000,
                   expect="pdf" if kind == "pdf" else None)
    out = {}
    if kind == "csv":
        rows = list(csv.reader(open(p, encoding="utf-8", errors="replace")))
        ballots, unrec = {}, {}
        for r in rows:
            if len(r) < 6:
                continue
            cty = r[3]
            if "Total Applicable Ballots" in r:
                ballots[cty] = num(r[r.index("Total Applicable Ballots") + 1])
            if "Unrecorded" in r:
                unrec[cty] = num(r[r.index("Unrecorded") + 1])
        for cty in ballots:
            out[cty] = {"ballots": ballots[cty], "votes": ballots[cty] - unrec[cty]}
    else:
        t = "\n".join(pdf_pages(p))
        # County blocks end with "Total Votes" / "Unrecorded"; the last block is the citywide total.
        blocks = re.findall(r"(?is)(New York|Bronx|Kings|Queens|Richmond) County\s*\n(?:(?!Total Votes).)*?"
                            r"Total Ballots\s*\n\s*([\d,]+).*?Total Votes\s*\n\s*([\d,]+)\s*\n\s*Unrecorded\s*\n\s*([\d,]+)", t)
        for name, b, v, u in blocks:
            out["%s County" % name.title() if name.lower() != "new york" else "New York County"] = \
                {"ballots": num(b), "votes": num(v)}
        tot = re.findall(r"(?i)Total Ballots\s*\n\s*([\d,]+)", t)
        tv = re.findall(r"(?i)Total Votes\s*\n\s*([\d,]+)", t)
        out["citywide"] = {"ballots": num(tot[-1]), "votes": num(tv[-1])}
    cw = [k for k in out if k.startswith("Total for") or k == "citywide"]
    if len(cw) != 1:
        raise FetchError("%d mayoral recap: citywide total not found" % year)
    city = out.pop(cw[0])
    counties = {k: v for k, v in out.items() if k in COUNTY_BORO}
    if len(counties) != 5:
        raise FetchError("%d mayoral recap: expected five counties, got %s" % (year, list(counties)))
    s = sum(v["votes"] for v in counties.values())
    if abs(s - city["votes"]) > 1:
        raise FetchError("%d mayoral recap: county votes (%d) do not add to citywide (%d)" % (year, s, city["votes"]))
    return city, counties, url


def cvap(year, geo="place"):
    if year >= 2017:
        if geo == "place":
            r = census(year, "acs/acs1", ["B29001_001E", "B29001_001M"], "place:51000", "state:36",
                       "acs1_%d_B29001_nyc.json" % year)[0]
        else:
            rr = census(year, "acs/acs1", ["B29001_001E", "B29001_001M"], "county:005,047,061,081,085", "state:36",
                        "acs1_%d_B29001_nyc_counties.json" % year)
            return {r["county"]: (int(r["B29001_001E"]), int(r["B29001_001M"])) for r in rr}, "B29001"
        return (int(r["B29001_001E"]), int(r["B29001_001M"])), "B29001"
    v = ["B05003_008E", "B05003_012E", "B05003_019E", "B05003_023E"]
    r = census(year, "acs/acs1", v, "place:51000", "state:36", "acs1_%d_B05003_nyc.json" % year)[0]
    c = int(r["B05003_008E"]) - int(r["B05003_012E"]) + int(r["B05003_019E"]) - int(r["B05003_023E"])
    return (c, None), "B05003"


def voter_turnout():
    ind = base("voter_turnout", "Turnout in mayoral general elections",
               "Votes cast for mayor in the November general election as a share of the city's citizen voting-age "
               "population (U.S. citizens 18 and older) that year.", "percent", "pct1", "up")
    series, notes = [], []
    for y in sorted(VOTE_FILES):
        city, counties, url = mayor_votes(y)
        (den, den_moe), table = cvap(y)
        # check: B05003 derivation equals B29001 in a year where both exist
        series.append({"period": str(y), "value": round(city["votes"] / den * 100, 1), "moe": None})
        notes.append("%d: %s votes for mayor (%s ballots) / %s CVAP (ACS 1-year %s%s)" % (
            y, format(int(city["votes"]), ","), format(int(city["ballots"]), ","), format(den, ","), table,
            (", MOE +/-%s" % format(den_moe, ",")) if den_moe else ""))
        if y == max(VOTE_FILES):
            latest_counties = counties
    # Consistency check of the two CVAP constructions.
    chk_b29, _ = cvap(2017)
    v = ["B05003_008E", "B05003_012E", "B05003_019E", "B05003_023E"]
    r = census(2017, "acs/acs1", v, "place:51000", "state:36", "acs1_2017_B05003_nyc.json")[0]
    alt = int(r["B05003_008E"]) - int(r["B05003_012E"]) + int(r["B05003_019E"]) - int(r["B05003_023E"])
    if alt != chk_b29[0]:
        raise FetchError("B05003-derived CVAP does not match B29001 for 2017")
    ind["series"] = series
    latest = series[-1]["period"]
    ind["latest_period"] = latest
    cc, _ = cvap(int(latest), geo="county")
    ind["breakdowns"].append({"by": "borough", "period": latest, "source_url": VOTE_FILES[int(latest)][0],
                              "values": [{"name": COUNTY_BORO[k][0],
                                          "value": round(v["votes"] / cc[COUNTY_BORO[k][1]][0] * 100, 1), "moe": None}
                                         for k, v in sorted(latest_counties.items())]})
    ind["source"] = src("NYC Board of Elections certified Statement and Return reports, Mayor (citywide recap), "
                        "general elections 2005-2025; Census Bureau ACS 1-year estimates",
                        "https://www.vote.nyc/page/election-results-summary", VOTE_FILES[int(latest)][0])
    ind["method"] = ("Turnout = votes recorded for mayor / citizen voting-age population x 100. Votes recorded for "
                     "mayor are the Board of Elections' certified 'Total Votes' for the office (all candidates and "
                     "write-ins; ballots left blank or overvoted for mayor, shown as 'Unrecorded', are excluded). The "
                     "denominator is ACS 1-year table B29001 (citizen voting-age population) for New York city for "
                     "the same year; B29001 is not published for 2005-2013, so for those years it is built from table "
                     "B05003 as people 18+ minus non-citizens 18+ (male B05003_008-B05003_012 plus female "
                     "B05003_019-B05003_023), which reproduces B29001 exactly in 2017 (checked). Borough breakdown "
                     "uses the county recap totals over county B29001. Figures: " + "; ".join(notes) + ".")
    ind["caveats"] = [
        "The denominator is a survey estimate with a margin of error; turnout margins of error are not published and "
        "are not computed here.",
        "Total ballots cast (including ballots with no vote for mayor) run about 1-2 percent higher than votes for "
        "mayor; the figures are in method.",
        "The CVAP counts all adult citizens, including those not registered, so this is lower than turnout of "
        "registered voters.",
    ]
    write(ind)


# --------------------------------------------------------------------------------------------
# 9. Volunteering
# --------------------------------------------------------------------------------------------
CEV_PEERS = {1: ["New York"], 2: ["Los Angeles"], 3: ["Chicago"], 4: ["Dallas", "Fort Worth"], 5: ["Houston"],
             6: ["Philadelphia"], 7: ["Washington, D.C."], 10: ["Boston"], 11: ["San Francisco"], 12: ["Phoenix"]}


def volunteering():
    ind = base("volunteering", "Adults who volunteered",
               "Share of people 16 and older in the New York metro area who volunteered through or for an "
               "organization in the previous 12 months (formal volunteering), from the Current Population Survey "
               "Civic Engagement and Volunteering Supplement.", "percent", "pct1", "up")
    meta_url = "https://data.americorps.gov/api/views/be5g-4c5r.json"
    meta = json.loads(http_get(meta_url)) if not OFFLINE else json.load(open(os.path.join(RAW, "americorps_cev_meta.json")))
    if not OFFLINE:
        json.dump(meta, open(os.path.join(RAW, "americorps_cev_meta.json"), "w"))
    att = [a for a in meta.get("metadata", {}).get("attachments", []) if "Stacked" in (a.get("name") or "")]
    if not att:
        raise FetchError("CEV stacked analytic file not listed on data.americorps.gov")
    aurl = "https://data.americorps.gov/api/views/be5g-4c5r/files/%s?download=true&filename=cev_stacked.zip" % att[0]["assetId"]
    zpath = fetch_file(aurl, "cev_2017_2023_stacked.zip", min_bytes=1000000, expect="zip")
    agg_path = os.path.join(RAW, "cev_2017_2023_rates_by_year_msa.csv")
    import pandas as pd
    tmp = os.path.join(RAW, "_cev_tmp")
    os.makedirs(tmp, exist_ok=True)
    try:
        with zipfile.ZipFile(zpath) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".dta")]
            if len(names) != 1:
                raise FetchError("CEV zip: expected one .dta file")
            z.extract(names[0], tmp)
            dta = os.path.join(tmp, names[0])
        it = pd.read_stata(dta, iterator=True)
        labels = it.value_labels().get("topmsa", {})
        df = pd.read_stata(dta, columns=["year", "state", "topmsa", "volunteer", "supwgt"], convert_categoricals=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    df = df[df.volunteer.notna() & (df.supwgt > 0)]
    if len(df) < 100000:
        raise FetchError("CEV microdata look incomplete")

    def rate(g):
        return float((g.volunteer * g.supwgt).sum() / g.supwgt.sum() * 100)
    nat = {int(y): rate(g) for y, g in df.groupby("year")}
    nys = {int(y): rate(g) for y, g in df[df.state == 36].groupby("year")}
    msa = {}
    for (y, m), g in df[df.topmsa.notna()].groupby(["year", "topmsa"]):
        msa[(int(y), int(m))] = (rate(g), len(g))
    with open(agg_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "topmsa", "msa_name", "formal_volunteering_rate_pct", "unweighted_respondents"])
        for (y, m), (r, n) in sorted(msa.items()):
            w.writerow([y, m, labels.get(m, ""), round(r, 3), n])
    # Validate against AmeriCorps' published state rates (New York State).
    pub = socrata("data.americorps.gov", "4r6x-re58", {"$where": "state='NY'"}, "americorps_cev_state_rates_ny.json")[0]
    for y, k in ((2017, "state_2017_formal_volunteering"), (2019, "state_2019_formal_volunteering"),
                 (2021, "state_2021_formal_volunteering"), (2023, "state_2023_formal_volunteering_rate")):
        if abs(float(pub[k]) * 100 - nys[y]) > 0.15:
            raise FetchError("CEV computed NY State rate %d (%.2f) does not match AmeriCorps (%.1f)" % (y, nys[y], float(pub[k]) * 100))
    years = sorted({y for y, _ in msa})
    ind["series"] = [{"period": str(y), "value": round(msa[(y, 1)][0], 1), "moe": None} for y in years]
    ind["status"] = "partial"
    ind["status_reason"] = ("The survey is every two years and the consistent 2017-2023 analytic file gives only %d "
                            "points (%s); the 2025 wave is not released yet. Too short for the five-year baseline and "
                            "ten-year swing." % (len(years), ", ".join(map(str, years))))
    latest = str(years[-1])
    ind["latest_period"] = latest
    vals = []
    for m, cities in CEV_PEERS.items():
        r, n = msa[(int(latest), m)]
        for c in cities:
            vals.append({"city": c, "value": round(r, 1), "moe": None, "geo_name": labels.get(m, "")})
    ind["peers"] = {"period": latest, "geography": "metro",
                    "note": "Metro areas, not cities. AmeriCorps says the CEV supports reliable estimates only for the "
                            "12 largest metro areas, so only peers whose metro is among them are shown (Dallas and Fort "
                            "Worth share one metro). Rates computed from the same microdata with the same weights as the "
                            "New York figure.",
                    "source": src("AmeriCorps and Census Bureau, CPS Civic Engagement and Volunteering Supplement "
                                  "2017-2023 stacked analytic file", "https://data.americorps.gov/d/be5g-4c5r", aurl),
                    "values": vals}
    ps = {}
    for c in NAMED_PEERS:
        m = [k for k, v in CEV_PEERS.items() if c in v]
        if m:
            ps[c] = [{"period": str(y), "value": round(msa[(y, m[0])][0], 1)} for y in years]
    ind["peer_series"] = ps
    ind["source"] = src("AmeriCorps and U.S. Census Bureau, Current Population Survey Civic Engagement and "
                        "Volunteering Supplement, 2017-2023 stacked analytic file (data.americorps.gov be5g-4c5r)",
                        "https://data.americorps.gov/d/be5g-4c5r", aurl)
    nsz = ", ".join("%d: %d" % (y, msa[(y, 1)][1]) for y in years)
    ind["method"] = ("Computed from AmeriCorps' CEV analytic microdata: weighted share of respondents (ages 16+) with "
                     "volunteer = 1, using the supplement weight supwgt, among respondents with a non-missing "
                     "volunteer answer and positive weight, for the New York-Newark-Jersey City metro area (topmsa = 1). "
                     "The same calculation reproduces AmeriCorps' published national rates (2017 %.1f, 2019 %.1f, 2021 "
                     "%.1f, 2023 %.1f) and New York State rates, which the script checks. Unweighted NY metro "
                     "respondents: %s." % (nat[2017], nat[2019], nat[2021], nat[2023], nsz))
    ind["caveats"] = [
        "The geography is the 2020-definition New York metro area (including northern New Jersey, the lower Hudson "
        "Valley and Long Island), not the five boroughs; the CEV is not designed for city-level estimates.",
        "Survey estimates with sampling error; margins of error are not published for metro rates and are not computed "
        "here (no replicate weights in the file).",
        "The survey runs every two years; the September 2025 wave is scheduled for public release on 1 December "
        "2026, after this was fetched.",
        "2021 was collected during the pandemic and is low everywhere.",
    ]
    write(ind)


# --------------------------------------------------------------------------------------------
# 10. Debt per resident
# --------------------------------------------------------------------------------------------
FISC_NAME = {"New York": "NY: New York", "Los Angeles": "CA: Los Angeles", "Chicago": "IL: Chicago",
             "Houston": "TX: Houston", "Phoenix": "AZ: Phoenix", "Philadelphia": "PA: Philadelphia",
             "San Antonio": "TX: San Antonio", "San Diego": "CA: San Diego", "Dallas": "TX: Dallas",
             "Jacksonville": "FL: Jacksonville", "Austin": "TX: Austin", "San Jose": "CA: San Jose",
             "Charlotte": "NC: Charlotte", "Columbus": "OH: Columbus", "Indianapolis": "IN: Indianapolis",
             "San Francisco": "CA: San Francisco", "Seattle": "WA: Seattle", "Denver": "CO: Denver",
             "Nashville-Davidson": "TN: Nashville", "Oklahoma City": "OK: Oklahoma", "Washington, D.C.": "DC: Washington",
             "El Paso": "TX: El Paso", "Las Vegas": "NV: Las Vegas", "Boston": "MA: Boston"}


def acfr_per_capita(path, fy_report):
    """Per-capita column of 'Ratios of Outstanding Debt by Type' (ten-year table). Tries every page that has the
    title and a Capita column; returns the first that yields ten years ending in the report year."""
    pages = pdf_pages(path)
    tried = []
    for i, t in enumerate(pages):
        if "Ratios of Outstanding Debt by Type" not in t or "Capita" not in t or ". . ." in t:
            continue
        printed = re.search(r"^\s*(\d{3})\s*$", t, re.M)
        out = {}
        lines = [x.strip() for x in t.split("\n") if x.strip()]
        one_line = [l for l in lines if re.match(r"^20\d\d\s+\$?\s*[\d,]", l)]
        if len(one_line) >= 10:  # one row per line
            for l in one_line:
                p = l.split()
                out[int(p[0])] = num(p[-1])
        else:  # tokens split across lines: per capita is the last token before the next year
            idx = [k for k, x in enumerate(lines) if re.fullmatch(r"20\d\d", x)]
            for n, k in enumerate(idx):
                end = idx[n + 1] if n + 1 < len(idx) else len(lines)
                seg = [x for x in lines[k + 1:end] if re.search(r"\d", x) and re.fullmatch(r"[$\d,.\s]+", x)]
                if seg and re.fullmatch(r"\$?\s*[\d,]{5,7}", seg[-1]):
                    out[int(lines[k])] = num(seg[-1])
        years = sorted(out)
        tried.append((i + 1, years))
        if len(years) == 10 and years[-1] == fy_report and years[0] == fy_report - 9:
            return out, i + 1, (printed.group(1) if printed else None)
    raise FetchError("ACFR %d: per-capita debt table not parsed (pages tried: %s)" % (fy_report, tried))


BLS_CPI = "CUURS12ASA0"  # CPI-U, New York-Newark-Jersey City, all items, not seasonally adjusted


def ny_cpi(first_year, last_year):
    """Monthly and annual-average NY-area CPI-U from the keyless BLS API (10 years per request)."""
    monthly, annual, notes = {}, {}, {}
    y = first_year
    while y <= last_year:
        y2 = min(y + 9, last_year)
        name = "bls_%s_%d_%d.json" % (BLS_CPI, y, y2)
        path = os.path.join(RAW, name)
        if OFFLINE:
            d = json.load(open(path))
        else:
            body = json.dumps({"seriesid": [BLS_CPI], "startyear": str(y), "endyear": str(y2),
                               "annualaverage": True}).encode()
            last = None
            for i in range(5):
                try:
                    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body,
                                                 headers={"Content-Type": "application/json", "User-Agent": UA})
                    d = json.loads(urllib.request.urlopen(req, timeout=120).read())
                    break
                except Exception as e:
                    last = e
                    time.sleep(3 * 2 ** i)
            else:
                raise FetchError("BLS API failed: %s" % last)
            with open(path, "w") as f:
                json.dump(d, f)
        if d.get("status") != "REQUEST_SUCCEEDED" or not d["Results"]["series"][0]["data"]:
            raise FetchError("BLS API returned no CPI data for %d-%d: %s" % (y, y2, d.get("message")))
        for x in d["Results"]["series"][0]["data"]:
            yr, per = int(x["year"]), x["period"]
            fn = "; ".join(f.get("text", "") for f in x.get("footnotes") or [] if f)
            try:
                v = float(x["value"])
            except ValueError:
                notes[(yr, per)] = fn or "no value"
                continue
            if per == "M13":
                annual[yr] = v
            elif re.fullmatch(r"M(0[1-9]|1[0-2])", per):
                monthly[(yr, int(per[1:]))] = v
        y = y2 + 1
    return monthly, annual, notes


def debt_per_resident():
    ind = base("debt_per_resident", "City debt per resident",
               "Total outstanding debt of New York City's primary government (general obligation bonds, Transitional "
               "Finance Authority and other city-backed debt, plus lease and other obligations), per resident, at "
               "fiscal year end, as reported in the Comptroller's Annual Comprehensive Financial Report, adjusted "
               "for inflation to 2025 dollars with the New York-area consumer price index.",
               "dollars (2025)", "usd0", "down")
    page = http_get("https://comptroller.nyc.gov/reports/annual-comprehensive-financial-reports/").decode("utf-8", "replace") \
        if not OFFLINE else open(os.path.join(RAW, "comptroller_acfr_page.html")).read()
    if not OFFLINE:
        open(os.path.join(RAW, "comptroller_acfr_page.html"), "w").write(page)
    links = {}
    for u in re.findall(r'href="(https://comptroller\.nyc\.gov/wp-content/uploads/documents/(?:ACFR|CAFR|cafr)-?(\d{4})[^"]*\.pdf)"', page):
        links.setdefault(int(u[1]), u[0])
    if not links:
        raise FetchError("no ACFR links found on the Comptroller page")
    newest = max(links)
    want = [newest, newest - 10]
    vals, cites = {}, []
    for fy in sorted(want):
        if fy not in links:
            raise FetchError("ACFR for FY%d not linked on the Comptroller page" % fy)
        p = fetch_file(links[fy], "comptroller_acfr_fy%d.pdf" % fy, min_bytes=1000000, expect="pdf")
        pc, pdfpage, printed = acfr_per_capita(p, fy)
        for y, v in pc.items():
            vals[y] = v
        cites.append("FY%d-FY%d: Comptroller's %s for Fiscal %d, 'Ratios of Outstanding Debt by Type-Ten Year Trend', "
                     "printed page %s (PDF page %d), %s" % (min(pc), max(pc), "ACFR" if fy >= 2021 else "CAFR", fy,
                                                         printed or "?", pdfpage, links[fy]))
    years = sorted(vals)
    # Deflate to 2025 dollars: fiscal-year (July-June) average of monthly NY-area CPI-U; base = BLS 2025 annual average.
    cpi_m, cpi_a, cpi_notes = ny_cpi(years[0] - 1, years[-1])
    if 2025 not in cpi_a:
        raise FetchError("BLS 2025 annual average CPI not available")
    base_cpi = cpi_a[2025]
    fy_cpi, fy_gaps = {}, {}
    for y in years:
        months = [(y - 1, m) for m in range(7, 13)] + [(y, m) for m in range(1, 7)]
        have = [cpi_m[k] for k in months if k in cpi_m]
        gone = [k for k in months if k not in cpi_m]
        if len(have) < 10:
            raise FetchError("CPI for FY%d has only %d months" % (y, len(have)))
        fy_cpi[y] = sum(have) / len(have)
        if gone:
            fy_gaps[y] = gone
    real = {y: round(vals[y] * base_cpi / fy_cpi[y]) for y in years}
    ind["series"] = [{"period": "FY%d" % y, "value": real[y], "moe": None} for y in years]
    ind["nominal_series"] = [{"period": "FY%d" % y, "value": vals[y]} for y in years]
    ind["deflator"] = {"series": BLS_CPI, "base": "2025 annual average = %.3f" % base_cpi,
                       "fiscal_year_cpi": [{"period": "FY%d" % y, "value": round(fy_cpi[y], 3)} for y in years]}
    ind["units"] = "dollars (2025)"
    ind["latest_period"] = "FY%d" % years[-1]
    gap_txt = "; ".join("FY%d averages %d months because BLS published no value for %s (%s)" % (
        y, 12 - len(g), ", ".join(dt.date(a, b, 1).strftime("%B %Y") for a, b in g),
        "; ".join(sorted({cpi_notes.get((a, "M%02d" % b), "not published") for a, b in g})))
        for y, g in sorted(fy_gaps.items()))
    ind["source"] = src("NYC Comptroller, Annual Comprehensive Financial Report, Part III Statistical Information, "
                        "'Ratios of Outstanding Debt by Type-Ten Year Trend'",
                        "https://comptroller.nyc.gov/reports/annual-comprehensive-financial-reports/", links[newest])
    ind["method"] = ("The 'Per Capita' column of the ten-year table in two ACFRs: " + "; ".join(cites) +
                     ". Per capita is the Comptroller's figure: total primary government debt divided by the prior "
                     "year's city population (table footnote 4). Each fiscal year's nominal figure is converted to "
                     "2025 dollars by multiplying by the ratio of the 2025 annual-average New York-Newark-Jersey City "
                     "CPI-U (BLS %s, not seasonally adjusted, %.3f) to the average of that index over the fiscal year "
                     "(July of the prior year through June), from the BLS public API. %s The nominal figures are in "
                     "nominal_series and the fiscal-year index values in deflator." % (
                         BLS_CPI, base_cpi, (gap_txt + ".") if gap_txt else "Every fiscal year has all 12 months."))
    ind["caveats"] = [
        "Lease obligations rose sharply in FY2022 when the City implemented GASB Statement 87 (ACFR FY%d table "
        "footnote 5), so much of the FY2021-FY2022 jump (from $%s to $%s per resident in nominal dollars) is an accounting change, "
        "not new borrowing." % (newest, format(int(vals[2021]), ","), format(int(vals[2022]), ",")),
        "Values are in 2025 dollars using the New York-area consumer price index, a measure of household prices, "
        "not of the costs the City borrows for; the Comptroller's nominal figures are kept in nominal_series.",
        "New York's debt covers functions that elsewhere belong to counties, school districts and some state "
        "agencies, so per-resident city debt is not directly comparable with other city governments.",
    ]
    # Peers: Lincoln Institute Fiscally Standardized Cities.
    fpage = "https://apps.lincolninst.edu/data/fiscally-standardized-cities/access-fisc-database"
    ph = http_get(fpage).decode("utf-8", "replace") if not OFFLINE else open(os.path.join(RAW, "fisc_access_page.html")).read()
    if not OFFLINE:
        open(os.path.join(RAW, "fisc_access_page.html"), "w").write(ph)
    m = re.search(r"downloadFile\('(files/fisc-database/[^']+\.xlsx)'\)", ph)
    if not m:
        raise FetchError("FiSC full dataset link not found")
    furl = "https://apps.lincolninst.edu/storage/" + m.group(1)
    fpath = fetch_file(furl, os.path.basename(m.group(1)), min_bytes=1000000, expect="zip")
    import openpyxl
    wb = openpyxl.load_workbook(fpath, read_only=True)
    it = wb["Data"].iter_rows(values_only=True)
    hdr = next(it)
    ix = {h: i for i, h in enumerate(hdr)}
    rows = {}
    maxy = 0
    for r in it:
        rows[(r[ix["city_name"]], r[ix["year"]])] = r
        maxy = max(maxy, r[ix["year"]])
    cpi1 = [r[ix["cpi"]] for (c, y), r in rows.items() if y == maxy][0]
    if abs(float(cpi1) - 1) > 1e-9:
        raise FetchError("FiSC CPI factor for %d is %s, not 1; dollar base unclear" % (maxy, cpi1))
    if maxy not in cpi_a:
        _, more, _ = ny_cpi(maxy, maxy)
        cpi_a.update(more)
    fisc_scale = base_cpi / cpi_a[maxy]
    vals_p, missing = [], []
    for city in PEER_NAMES:
        nm = FISC_NAME.get(city)
        r = rows.get((nm, maxy)) if nm else None
        if r is None or r[ix["debt_outstanding"]] is None:
            missing.append(city)
            continue
        vals_p.append({"city": city, "value": round(float(r[ix["debt_outstanding"]]) * fisc_scale), "moe": None,
                       "geo_name": "FiSC %s" % nm})
    ind["peers"] = {"period": str(maxy), "geography": "city",
                    "note": "Different source and definition from the NYC series: Lincoln Institute of Land Policy "
                            "Fiscally Standardized Cities (FiSC), total debt outstanding per resident in %d (Census of "
                            "Governments data). FiSC states values in %d dollars (its CPI factor is %s that year); they "
                            "are moved to 2025 dollars here with the same New York-area CPI-U as the NYC series "
                            "(2025 annual average / %d annual average = %.4f). FiSC adds "
                            "the shares of county, school district and special district debt that serve each city's "
                            "residents, which adjusts for New York's roles as city, county and school district. Not in "
                            "FiSC: %s." % (maxy, maxy, cpi1, maxy, fisc_scale, ", ".join(missing) or "none"),
                    "source": src("Lincoln Institute of Land Policy, Fiscally Standardized Cities database (full dataset)",
                                  "https://www.lincolninst.edu/data/fiscally-standardized-cities/", furl),
                    "values": vals_p}
    write(ind)


# --------------------------------------------------------------------------------------------
# 11. Tax burden
# --------------------------------------------------------------------------------------------
DC_EDITIONS = {
    2023: "https://ora-cfo.dc.gov/sites/default/files/dc/sites/ora-cfo/documents/2023%2051City%20Study_FINAL.pdf",
    2022: "https://ora-cfo.dc.gov/sites/default/files/dc/sites/ora-cfo/publication/attachments/2022%2051City%20Study_Final.pdf",
    2021: "https://ora-cfo.dc.gov/sites/default/files/dc/sites/ora-cfo/publication/attachments/2021%2051City%20Study.pdf",
    2020: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2020%20Tax%20Rates%20and%20Tax%20Burdens_Nationwide%20Comparison.pdf",
    2019: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2019%2051City%20Study_Final.pdf",
    2018: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2018%2051City%20Study_June%202020.pdf",
    2017: "https://ora-cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/Tax%20Rates%20and%20Tax%20Burdens%202017_A%20Nationwide%20Comparison.pdf",
    2016: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2016%2051City%20Study.pdf",
    2015: "https://ora-cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2015%2051City%20Tax%20Burden%20Study%20Final.pdf",
    2014: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2014%2051City%20Study.pdf",
    2013: "https://ora-cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2013%2051City%20Study%20FINAL.pdf",
    2012: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/2012%20Tax%20Rates%20and%20Tax%20Burdens_NATIONWIDE.pdf",
    2010: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/ocfo_10study.pdf",
    2009: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/ocfo_09STUDY.pdf",
    2008: "https://cfo.dc.gov/sites/default/files/dc/sites/ocfo/publication/attachments/ocfo_08study_final.pdf",
}
DC_PEER = {("New York", "NY"): "New York", ("New York City", "NY"): "New York", ("Los Angeles", "CA"): "Los Angeles",
           ("Chicago", "IL"): "Chicago", ("Houston", "TX"): "Houston", ("Phoenix", "AZ"): "Phoenix",
           ("Philadelphia", "PA"): "Philadelphia", ("Jacksonville", "FL"): "Jacksonville", ("Charlotte", "NC"): "Charlotte",
           ("Columbus", "OH"): "Columbus", ("Indianapolis", "IN"): "Indianapolis", ("Seattle", "WA"): "Seattle",
           ("Denver", "CO"): "Denver", ("Nashville", "TN"): "Nashville-Davidson", ("Oklahoma City", "OK"): "Oklahoma City",
           ("Washington", "DC"): "Washington, D.C.", ("Las Vegas", "NV"): "Las Vegas", ("Boston", "MA"): "Boston"}


def dc_table_75k(path):
    pages = pdf_pages(path)
    for i, t in enumerate(pages):
        if "$75,000" not in t[:700] or t.count("\n") < 200 or "RANK" not in t.upper()[:900]:
            continue
        toks = []
        for x in t.split("\n"):
            x = x.strip()
            if not x:
                continue
            toks.append(x)
        rows = {}
        for k in range(len(toks) - 3):
            city, st = toks[k], toks[k + 1].strip()
            if not (re.fullmatch(r"[A-Z]{2}", st) and re.match(r"[A-Za-z]", city) and not re.fullmatch(r"[A-Z]{2}", city)):
                continue
            vals, j = [], k + 2
            while j < len(toks) and len(vals) <= 6 and not re.fullmatch(r"\d+(\.\d+)?%", toks[j]):
                vals += toks[j].split()
                j += 1
            if j < len(toks) and re.fullmatch(r"\d+(\.\d+)?%", toks[j]) and len(vals) == 5:
                rows[(city.strip(), st)] = {"total": num(vals[4]), "pct": num(toks[j]),
                                            "income": vals[0], "property": vals[1], "sales": vals[2], "auto": vals[3]}
        if len(rows) >= 45:
            return i + 1, rows
    raise FetchError("could not find the $75,000 burden table in %s" % os.path.basename(path))


def tax_burden():
    ind = base("tax_burden", "State and local taxes on a typical family",
               "Estimated state and local income, property, sales and auto taxes paid by a hypothetical family of "
               "three earning $75,000 a year in New York City, as a percent of income, from the D.C. Chief Financial "
               "Officer's annual nationwide comparison of the largest city in each state.",
               "percent of income", "pct1", "down")
    results, pages = {}, {}
    for y, url in sorted(DC_EDITIONS.items()):
        p = fetch_file(url, "dc_cfo_tax_burden_%d.pdf" % y, min_bytes=100000, expect="pdf")
        pg, rows = dc_table_75k(p)
        results[y], pages[y] = rows, pg
    series, cites = [], []
    for y, rows in sorted(results.items()):
        ny = [v for (c, s), v in rows.items() if s == "NY" and c.startswith("New York")]
        if len(ny) != 1:
            raise FetchError("tax burden %d: New York row not found" % y)
        r0 = ny[0]
        parts = sum(num(r0[k]) for k in ("income", "property", "sales", "auto"))
        if abs(parts - r0["total"]) > 3 or abs(r0["total"] / 750 - r0["pct"]) > 0.11:
            raise FetchError("tax burden %d: New York row does not add up (%s)" % (y, r0))
        series.append({"period": str(y), "value": r0["pct"], "moe": None})
        cites.append("%d edition PDF page %d ($%s total)" % (y, pages[y], format(int(ny[0]["total"]), ",")))
    ind["series"] = series
    latest = max(results)
    ind["latest_period"] = str(latest)
    vals = []
    for (c, s), v in results[latest].items():
        pc = DC_PEER.get((c, s))
        if pc:
            vals.append({"city": pc, "value": v["pct"], "moe": None,
                         "geo_name": "%s, %s ($%s on $75,000)" % (c, s, format(int(v["total"]), ","))})
    absent = [c for c in PEER_NAMES if c not in {v["city"] for v in vals}]
    ind["peers"] = {"period": str(latest), "geography": "city",
                    "note": "Same report and income level. The report covers only the largest city in each state, so "
                            "%s are not in it." % ", ".join(absent),
                    "source": src("Government of the District of Columbia, Office of the Chief Financial Officer, "
                                  "%d Tax Rates and Tax Burdens in the District of Columbia: A Nationwide Comparison, "
                                  "Table 1c (PDF page %d)" % (latest, pages[latest]),
                                  "https://ora-cfo.dc.gov/page/tax-burden-studies", DC_EDITIONS[latest]),
                    "values": vals}
    ps = {}
    for nm in NAMED_PEERS:
        pts = []
        for y, rows in sorted(results.items()):
            m = [v for (c, s), v in rows.items() if DC_PEER.get((c, s)) == nm]
            if m:
                pts.append({"period": str(y), "value": m[0]["pct"]})
        ps[nm] = pts
    ind["peer_series"] = ps
    ind["source"] = src("Government of the District of Columbia, Office of the Chief Financial Officer (Office of "
                        "Revenue Analysis), 'Tax Rates and Tax Burdens in the District of Columbia: A Nationwide "
                        "Comparison', editions %d-%d" % (min(results), latest),
                        "https://ora-cfo.dc.gov/page/tax-burden-studies", DC_EDITIONS[latest])
    ind["method"] = ("From each edition's table of estimated burdens of major taxes for a hypothetical family "
                     "earning $75,000 (Table 1c in recent editions), the New York City row's total burden as a percent "
                     "of income (income + property + sales + auto taxes). $75,000 is used because it is the income "
                     "level the report uses for its headline maps of total, income, property and sales tax burdens, "
                     "and it appears in every edition. Pages: " + "; ".join(cites) + ".")
    ind["caveats"] = [
        "The report itself advises readers not to compare its hypothetical burdens across years, because small "
        "changes in its assumptions can make such comparisons misleading (2023 edition, PDF page 11); treat the "
        "series as a sequence of single-year comparisons across cities, not a trend.",
        "Editions cover taxes in effect through December 31 of the edition year; the latest edition found is %d. "
        "No 2011 edition was found, so 2011 is missing." % latest,
        "The report assumes the family owns its home at this income level (only the $25,000 family is assumed to "
        "rent), so the property tax figure depends on the report's housing-value assumption for each city.",
    ]
    write(ind)


# --------------------------------------------------------------------------------------------
MEASURES = [fine_particle_pollution, heat_deaths, ghg_emissions, parkscore, transit_ridership, bus_speeds,
            street_cleanliness, voter_turnout, volunteering, debt_per_resident, tax_burden]


def main():
    only = set(sys.argv[1:])
    failed = []
    for fn in MEASURES:
        if only and fn.__name__ not in only:
            continue
        print("==", fn.__name__)
        try:
            fn()
        except Exception as e:
            failed.append(fn.__name__)
            print("  FAILED: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            if not isinstance(e, FetchError):
                traceback.print_exc()
    if failed:
        print("failed measures: %s" % ", ".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
