#!/usr/bin/env python3
"""Health and safety group fetcher for "How New York Is Doing" (edition: New York in 2025).

Run from the project folder:  python3 -I fetch/health_safety.py
Options:  --refresh  re-download everything, ignoring the cache
          --offline  use only files already in data/raw/health_safety/ (fails if one is missing)

By default a raw file younger than 7 days is reused.

Measures written to data/indicators/:
  life_expectancy, overdose_deaths, infant_mortality, murders, shooting_victims,
  major_felonies, traffic_deaths, jail_population

Sources:
  * NYC Health Department Summary of Vital Statistics PDFs (2020-2023 editions), the
    HealthyNYC page and Epi Data Brief No. 150 (overdose deaths 2000-2024).
  * CDC NCHS VSRR provisional drug overdose death counts (data.cdc.gov xkb8-kh2a, state
    level; gb4e-yj24, county level).
  * NYC Open Data (Socrata): NYPD complaint data historic (qgea-i56i) and year to date
    (5uac-w243); NYPD Shootings (5ucz-vwe8) and Shooting Victims (pztn-9bne); Motor
    Vehicle Collisions - Crashes (h9gi-nx95); Infant Mortality (fcau-jc6k); DOC Daily
    Inmates In Custody (7479-ugqb).
  * NYC DOT 2025 year-end Vision Zero press release (official 2024 and 2025 counts).
  * NHTSA FARS 2023 national CSV (final file).
  * Real-Time Crime Index (AH Datalytics) historical file of FBI annual agency counts.
  * New York State DCJS jail population by county (data.ny.gov nymx-kgkn).
  * Vera Institute of Justice, Incarceration Trends (county file on GitHub).
  * Census Bureau Vintage 2025 county population estimates (for peer rates).

PDF text is read with pypdf. Under `python3 -I` the user site-packages folder is not on the
path, so the script adds it explicitly (and only it) if pypdf is not otherwise importable.
"""
import csv
import datetime
import gzip
import html
import io
import json
import os
import re
import site
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "health_safety")
IND = os.path.join(ROOT, "data", "indicators")
TODAY = datetime.date.today().isoformat()
UA = "Mozilla/5.0 (compatible; civic-data-fetcher/1.0)"
REFRESH = "--refresh" in sys.argv
OFFLINE = "--offline" in sys.argv
MAX_AGE = 7 * 86400
LATEST = 2025

NYC_OD = "https://data.cityofnewyork.us"
CDC = "https://data.cdc.gov"
NYS = "https://data.ny.gov"

NYC_COUNTIES = [("36005", "Bronx"), ("36047", "Brooklyn"), ("36061", "Manhattan"),
                ("36081", "Queens"), ("36085", "Staten Island")]

# Principal county of each peer city (same table as fetch/census.py).
PRINCIPAL_COUNTY = {
    "Los Angeles": ("06", "037", "Los Angeles County"),
    "Chicago": ("17", "031", "Cook County"),
    "Houston": ("48", "201", "Harris County"),
    "Phoenix": ("04", "013", "Maricopa County"),
    "Philadelphia": ("42", "101", "Philadelphia County"),
    "San Antonio": ("48", "029", "Bexar County"),
    "San Diego": ("06", "073", "San Diego County"),
    "Dallas": ("48", "113", "Dallas County"),
    "Fort Worth": ("48", "439", "Tarrant County"),
    "Jacksonville": ("12", "031", "Duval County"),
    "Austin": ("48", "453", "Travis County"),
    "San Jose": ("06", "085", "Santa Clara County"),
    "Charlotte": ("37", "119", "Mecklenburg County"),
    "Columbus": ("39", "049", "Franklin County"),
    "Indianapolis": ("18", "097", "Marion County"),
    "San Francisco": ("06", "075", "San Francisco County"),
    "Seattle": ("53", "033", "King County"),
    "Denver": ("08", "031", "Denver County"),
    "Nashville-Davidson": ("47", "037", "Davidson County"),
    "Oklahoma City": ("40", "109", "Oklahoma County"),
    "Washington, D.C.": ("11", "001", "District of Columbia"),
    "El Paso": ("48", "141", "El Paso County"),
    "Las Vegas": ("32", "003", "Clark County"),
    "Boston": ("25", "025", "Suffolk County"),
}

USED_FIPS = {f for f, _ in NYC_COUNTIES} | {st + co for st, co, _ in PRINCIPAL_COUNTY.values()}

# Police agency (FBI ORI) serving each city, as identified in the Real-Time Crime Index file.
# Each is checked below against the city's Census population.
CITY_ORI = {
    "New York": ("NY0303000", "New York City Police Department"),
    "Los Angeles": ("CA0194200", "Los Angeles Police Department"),
    "Chicago": ("ILCPD0000", "Chicago Police Department"),
    "Houston": ("TXHPD0000", "Houston Police Department"),
    "Phoenix": ("AZ0072300", "Phoenix Police Department"),
    "Philadelphia": ("PAPEP0000", "Philadelphia Police Department"),
    "San Antonio": ("TXSPD0000", "San Antonio Police Department"),
    "San Diego": ("CA0371100", "San Diego Police Department"),
    "Dallas": ("TXDPD0000", "Dallas Police Department"),
    "Fort Worth": ("TX2201200", "Fort Worth Police Department"),
    "Jacksonville": ("FL0160000", "Jacksonville Sheriff's Office (consolidated city-county)"),
    "Austin": ("TX2270100", "Austin Police Department"),
    "San Jose": ("CA0431300", "San Jose Police Department"),
    "Charlotte": ("NC0600100", "Charlotte-Mecklenburg Police Department"),
    "Columbus": ("OHCOP0000", "Columbus Division of Police"),
    "Indianapolis": ("INIPD0000", "Indianapolis Metropolitan Police Department"),
    "San Francisco": ("CA0380100", "San Francisco Police Department"),
    "Seattle": ("WASPD0000", "Seattle Police Department"),
    "Denver": ("CODPD0000", "Denver Police Department"),
    "Nashville-Davidson": ("TN0190100", "Metropolitan Nashville Police Department"),
    "Oklahoma City": ("OK0550600", "Oklahoma City Police Department"),
    "Washington, D.C.": ("DCMPD0000", "Metropolitan Police Department of the District of Columbia"),
    "El Paso": ("TX0710200", "El Paso Police Department"),
    "Las Vegas": ("NV0020100", "Las Vegas Metropolitan Police Department"),
    "Boston": ("MA0130100", "Boston Police Department"),
}
# Agencies whose jurisdiction is knowingly larger than the city (population check relaxed).
ORI_WIDER = {"Las Vegas", "Charlotte"}

MURDER = "101"
MAJOR7 = [("101", "Murder and non-negligent manslaughter", "MURDER & NON-NEGL. MANSLAUGHTER"),
          ("104", "Rape", "RAPE"),
          ("105", "Robbery", "ROBBERY"),
          ("106", "Felony assault", "FELONY ASSAULT"),
          ("107", "Burglary", "BURGLARY"),
          ("109", "Grand larceny", "GRAND LARCENY"),
          ("110", "Grand larceny of motor vehicle", "GRAND LARCENY OF MOTOR VEHICLE")]
BORO_NAME = {"BRONX": "Bronx", "BROOKLYN": "Brooklyn", "MANHATTAN": "Manhattan",
             "QUEENS": "Queens", "STATEN ISLAND": "Staten Island"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


class FetchError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- helpers

def log(*a):
    print(*a, flush=True)


def raw_path(name):
    return os.path.join(RAW, name)


def cached(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    if OFFLINE:
        return True
    if REFRESH:
        return False
    return (time.time() - os.path.getmtime(path)) < MAX_AGE


def http_bytes(url, tries=6, timeout=600):
    """GET with retry and backoff. Socrata 403/429 is throttling, so it is retried."""
    if OFFLINE:
        raise FetchError("offline mode: no cached copy for " + url)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
            if not data:
                raise FetchError("empty response from " + url)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429, 500, 502, 503, 504):
                wait = 5 * (2 ** i)
                log(f"    HTTP {e.code}, retrying in {wait}s: {url[:120]}")
                time.sleep(wait)
                continue
            raise FetchError(f"HTTP {e.code} for {url}")
        except (urllib.error.URLError, OSError) as e:
            last = e
            wait = 5 * (2 ** i)
            log(f"    network error ({e}), retrying in {wait}s")
            time.sleep(wait)
    raise FetchError(f"failed after {tries} tries: {url} ({last})")


def download(url, name, min_bytes=100):
    """Download url into data/raw/health_safety/<name> (cached). Returns the path."""
    path = raw_path(name)
    if cached(path):
        return path
    log(f"  downloading {name}")
    data = http_bytes(url)
    if len(data) < min_bytes:
        raise FetchError(f"download too small ({len(data)} bytes): {url}")
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return path


def soql(host, dataset, params, name):
    """Run a SoQL query, cache the JSON result, and return rows. Raises if empty."""
    p = dict(params)
    p.setdefault("$limit", "50000")
    url = f"{host}/resource/{dataset}.json?" + urllib.parse.urlencode(p)
    path = raw_path(name)
    if not cached(path):
        log(f"  querying {dataset} -> {name}")
        data = http_bytes(url)
        rows = json.loads(data.decode("utf-8"))
        if not isinstance(rows, list):
            raise FetchError(f"unexpected response from {url}: {str(rows)[:200]}")
        if not rows:
            raise FetchError(f"empty result from {url}")
        if len(rows) >= int(p["$limit"]):
            raise FetchError(f"result hit the $limit of {p['$limit']}: {url}")
        with open(path, "w") as fh:
            json.dump({"url": url, "fetched": TODAY, "rows": rows}, fh)
    with open(path) as fh:
        d = json.load(fh)
    if not d["rows"]:
        raise FetchError("empty cached result " + name)
    return d["rows"], d["url"]


def socrata_meta(host, dataset, name):
    path = download(f"{host}/api/views/{dataset}.json", name)
    with open(path) as fh:
        return json.load(fh)


def num(x):
    if x is None or x == "":
        return None
    return float(str(x).replace(",", ""))


def write_indicator(obj):
    assert obj["status"] in ("ok", "partial", "missing")
    if obj["status"] != "ok":
        assert obj.get("status_reason"), obj["id"]
    if obj["status"] != "missing":
        if not obj["series"]:
            raise FetchError(obj["id"] + ": empty series")
        periods = [s["period"] for s in obj["series"]]
        assert periods == sorted(periods), obj["id"] + " series not oldest-first"
        assert len(set(periods)) == len(periods), obj["id"] + " duplicate periods"
        for s in obj["series"]:
            if s["value"] is None:
                raise FetchError(obj["id"] + ": null value in series")
    path = os.path.join(IND, obj["id"] + ".json")
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    log(f"  wrote data/indicators/{obj['id']}.json")


def load_peers():
    with open(os.path.join(ROOT, "data", "peers.json")) as fh:
        return json.load(fh)["cities"]


def pdf_reader():
    try:
        import pypdf  # noqa
    except ImportError:
        usp = site.getusersitepackages()
        if usp and usp not in sys.path:
            sys.path.append(usp)
        try:
            import pypdf  # noqa
        except ImportError:
            raise FetchError("pypdf is required to read the Health Department PDFs "
                             "(pip3 install --user pypdf)")
    import pypdf
    return pypdf.PdfReader


def pdf_pages(path):
    Reader = pdf_reader()
    r = Reader(path)
    return [(p.extract_text() or "") for p in r.pages]


def page_text(html_bytes):
    t = html_bytes.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))


_county_pop = None


def county_pop():
    """Census Vintage 2025 county estimates: {fips5: {year: pop}}."""
    global _county_pop
    if _county_pop is None:
        url = ("https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/"
               "totals/co-est2025-alldata.csv")
        path = download(url, "co-est2025-alldata.csv", 100000)
        out = {}
        with open(path, encoding="latin-1") as fh:
            for r in csv.DictReader(fh):
                if r["SUMLEV"] != "050":
                    continue
                f = r["STATE"].zfill(2) + r["COUNTY"].zfill(3)
                out[f] = {y: int(r[f"POPESTIMATE{y}"]) for y in range(2020, 2026)
                          if r.get(f"POPESTIMATE{y}")}
        if len(out) < 3000:
            raise FetchError("county population file looks incomplete")
        _county_pop = (out, url)
    return _county_pop


def peer_county_rates(counts, year, label):
    """counts: {fips5: count}. Returns peers values list (NYC = five counties)."""
    pops, _ = county_pop()
    values, missing = [], []
    nyc_c = sum(counts.get(f, 0) for f, _ in NYC_COUNTIES)
    nyc_missing = [f for f, _ in NYC_COUNTIES if f not in counts]
    if nyc_missing:
        raise FetchError(f"{label}: NYC counties missing {nyc_missing}")
    nyc_p = sum(pops[f][year] for f, _ in NYC_COUNTIES)
    values.append({"city": "New York", "value": round(nyc_c / nyc_p * 1e5, 1), "moe": None,
                   "geo_name": "New York City (Bronx, Kings, New York, Queens and Richmond counties)",
                   "count": nyc_c, "population": nyc_p})
    for city, (st, co, cname) in PRINCIPAL_COUNTY.items():
        f = st + co
        if f not in counts or counts[f] is None:
            missing.append(city)
            continue
        p = pops[f][year]
        values.append({"city": city, "value": round(counts[f] / p * 1e5, 1), "moe": None,
                       "geo_name": cname, "count": counts[f], "population": p})
    return values, missing


# ----------------------------------------------------------------------------- life expectancy

VS_URL = "https://www.nyc.gov/assets/doh/downloads/pdf/vs/{y}sum.pdf"


def parse_m25(pages):
    """Table M25 (life expectancy at specified ages, 10 years). Returns {section: {year: e0}}."""
    for t in pages:
        if "Table M25" not in t or "Exact Age" not in t:
            continue
        lines = t.split("\n")
        sections = []
        years = None
        for ln in lines:
            m = re.search(r"in Years\s+((?:(?:19|20)\d\d\s*)+)$", ln.strip())
            if m:
                years = [int(y) for y in m.group(1).split()]
                continue
            if years and re.match(r"^0\s+\d", ln.strip()):
                vals = [float(v) for v in ln.split()[1:]]
                if len(vals) != len(years):
                    raise FetchError("Table M25 row length mismatch")
                sections.append(dict(zip(years, vals)))
                years = None
        if len(sections) >= 3:
            return {"Total": sections[0], "Male": sections[1], "Female": sections[2]}
    raise FetchError("Table M25 not found")


def life_expectancy():
    log("life_expectancy")
    editions = [2023, 2022, 2021, 2020]
    tables, urls = {}, {}
    pages23 = None
    for y in editions:
        url = VS_URL.format(y=y)
        path = download(url, f"vs_summary_{y}.pdf", 100000)
        pages = pdf_pages(path)
        tables[y] = parse_m25(pages)
        urls[y] = url
        if y == 2023:
            pages23 = pages
    series, src_of, diffs = {}, {}, []
    for ed in editions:  # newest edition first wins
        for yr, v in tables[ed]["Total"].items():
            if yr in series:
                if abs(series[yr] - v) > 0.05:
                    diffs.append(f"{yr}: {ed} edition {v} vs {src_of[yr]} edition {series[yr]}")
                continue
            series[yr] = v
            src_of[yr] = ed
    log(f"  years {min(series)}-{max(series)}; overlap disagreements: {diffs or 'none'}")
    latest = max(series)
    if latest != 2023:
        raise FetchError(f"expected 2023 as latest life expectancy year, got {latest}")
    # Race/ethnicity 2023 from the report text
    txt = " ".join(pages23)
    txt = re.sub(r"\s+", " ", txt)
    m = re.search(r"2023 life expectancy at birth was ([\d.]+) years among Hispanic/Latino people, "
                  r"([\d.]+) years among non-Hispanic/Latino white people, and ([\d.]+) years "
                  r"among non-Hispanic/Latino Black people", txt)
    m2 = re.search(r"Asian and Pacific Islander people increased from ([\d.]+) to ([\d.]+) years "
                   r"between 2022 and 2023", txt)
    breakdowns = []
    if m and m2:
        breakdowns.append({"by": "race/ethnicity", "period": "2023", "source_url": urls[2023],
                           "values": [
                               {"name": "Asian and Pacific Islander", "value": float(m2.group(2)), "moe": None},
                               {"name": "Hispanic/Latino", "value": float(m.group(1)), "moe": None},
                               {"name": "White (non-Hispanic/Latino)", "value": float(m.group(2)), "moe": None},
                               {"name": "Black (non-Hispanic/Latino)", "value": float(m.group(3)), "moe": None}]})
    else:
        log("  WARNING: race/ethnicity sentence not found in 2023 report")
    breakdowns.append({"by": "sex", "period": "2023", "source_url": urls[2023],
                       "values": [{"name": "Female", "value": tables[2023]["Female"][2023], "moe": None},
                                  {"name": "Male", "value": tables[2023]["Male"][2023], "moe": None}]})
    # Provisional 2024 from the HealthyNYC page
    extra = None
    hurl = "https://www.nyc.gov/site/doh/about/about-doh/healthynyc.page"
    try:
        hp = download(hurl, "healthynyc_page.html", 1000)
        with open(hp, "rb") as fh:
            ht = page_text(fh.read())
        mm = re.search(r"provisional (20\d\d) data[^.]{0,80}?life expectancy of ([\d.]+) years", ht)
        if mm:
            extra = {"period": mm.group(1) + " (provisional)", "value": float(mm.group(2)),
                     "note": "Provisional figure stated by the NYC Health Department on its HealthyNYC "
                             "page; the final figure will appear in the 2024 Summary of Vital Statistics.",
                     "source_url": hurl}
    except FetchError as e:
        log(f"  HealthyNYC page not read: {e}")
    caveats = [
        "The Health Department revised life expectancy for 2011-2019 when it adopted updated citywide "
        "population estimates (the Cornell Jeb E. Brooks School of Public Policy county estimates). Editions "
        "from 2019 and earlier printed lower figures for those years. This series uses only the revised "
        "basis, taken from the 2020-2023 editions, so it starts in 2011; 2010 on the revised basis is not "
        "published.",
        "2023 is the latest final year. The 2024 Summary of Vital Statistics had not been posted when "
        "this was fetched; nyc.gov returned 404 for 2024sum.pdf.",
        "No borough-level annual life expectancy is published in the summary (it gives community "
        "districts for 2014-2023 pooled), so there is no borough breakdown.",
    ]
    if diffs:
        caveats.append("Editions disagreed on overlapping years; the newest edition was used: " + "; ".join(diffs))
    if extra is None:
        caveats.append("No provisional 2024 figure could be read from the Health Department's site.")
    write_indicator({
        "id": "life_expectancy", "status": "ok", "status_reason": None,
        "name": "Life expectancy at birth",
        "definition": "Period life expectancy at birth for New York City residents, in years, from NYC death "
                      "certificates and population estimates.",
        "units": "years", "format": "dec1", "better": "up", "frequency": "annual",
        "series": [{"period": str(y), "value": series[y], "moe": None} for y in sorted(series)],
        "latest_period": str(latest),
        "latest_extra": extra,
        "source": {"name": "NYC Department of Health and Mental Hygiene, Summary of Vital Statistics "
                           "(2020-2023 editions), Table M25",
                   "url": urls[2023], "endpoint": ", ".join(urls[y] for y in editions),
                   "fetched": TODAY},
        "peers": None,
        "peer_series": None,
        "breakdowns": breakdowns,
        "method": "Life expectancy at age 0 read from Table M25 ('Life Expectancy at Specified Ages, Overall "
                  "and by Sex') of the 2023, 2022, 2021 and 2020 Summary of Vital Statistics. Each edition "
                  "covers ten years; for each year the newest edition's value is used, and overlapping years "
                  "were checked for agreement. Race/ethnicity figures for 2023 come from the 2023 report's "
                  "text (Hispanic/Latino, non-Hispanic white and Black) and its note on Asian and Pacific "
                  "Islander New Yorkers; sex figures from Table M25.",
        "caveats": caveats + [
            "Peers: no source publishes city-level life expectancy for the other 24 cities on the same "
            "basis (annual, city boundaries, same population estimates), so peers are left out.",
        ],
    })


# ----------------------------------------------------------------------------- overdose deaths

DB150 = "https://www.nyc.gov/assets/doh/downloads/pdf/epi/databrief150-unintentional-drug-death-2025.pdf"


def overdose_deaths():
    log("overdose_deaths")
    path = download(DB150, "epi_databrief150_overdose_2024.pdf", 100000)
    pages = pdf_pages(path)
    lines = pages[0].split("\n")
    years = counts = None
    for i, ln in enumerate(lines):
        if "Number and age-adjusted rate per 100,000 residents of unintentional drug poisoning" in ln \
                and "2000 to 2024" in ln:
            counts = [int(t.replace(",", "")) for t in lines[i + 1].split()]
        if re.fullmatch(r"(?:(?:19|20)\d\d\s+){10,}(?:19|20)\d\d", ln.strip()):
            years = [int(t) for t in ln.split()]
    if not counts or not years or len(counts) != len(years):
        raise FetchError(f"could not parse Epi Data Brief 150 chart ({counts}, {years})")
    doh = dict(zip(years, counts))
    kf = re.search(r"In 2024, there were ([\d,]+) unintentional drug\s+poisoning", re.sub(r"\s+", " ", pages[0]))
    if not kf or int(kf.group(1).replace(",", "")) != doh[2024]:
        raise FetchError("Epi Data Brief 2024 count does not match key finding")
    log(f"  DOHMH {min(doh)}-{max(doh)}: 2024={doh[2024]}")

    # CDC VSRR state-level (jurisdiction "New York City")
    rows, cdc_url = soql(CDC, "xkb8-kh2a", {
        "$select": "year, month, data_value, predicted_value, percent_complete, percent_pending_investigation, footnote",
        "$where": "state_name='New York City' and indicator='Number of Drug Overdose Deaths'",
        "$order": "year, month"}, "cdc_vsrr_nyc_overdose.json")
    cdc = {}
    for r in rows:
        cdc[(int(r["year"]), r["month"])] = r
    dec = {y: int(num(r["data_value"])) for (y, mth), r in cdc.items() if mth == "December" and r.get("data_value")}
    if 2025 not in dec:
        raise FetchError("CDC 12-month ending December 2025 value missing")
    latest_key = max(cdc, key=lambda k: (k[0], MONTHS.index(k[1])))
    lr = cdc[latest_key]
    log(f"  CDC Dec 2025={dec[2025]}; latest 12-mo ending {latest_key[1]} {latest_key[0]}={lr['data_value']}")
    overlap = [(y, dec[y], doh[y]) for y in sorted(dec) if y in doh]
    gaps = [f"{y}: CDC {c:,} vs Health Department {d:,} ({(c - d) / d * 100:+.1f}%)" for y, c, d in overlap]

    cyears = sorted(dec)
    if cyears != list(range(cyears[0], cyears[-1] + 1)) or cyears[-1] != LATEST:
        raise FetchError(f"CDC December series has gaps or wrong end year: {cyears}")
    series = [{"period": str(y), "value": dec[y], "moe": None} for y in cyears]
    dohmh_series = [{"period": str(y), "value": doh[y]} for y in sorted(doh)]
    footed = [y for (y, mth), r in cdc.items() if mth == "December" and r.get("footnote")]

    # Peers + borough breakdown: CDC county file, 12-month ending December 2025
    crow, county_url = soql(CDC, "gb4e-yj24", {
        "$select": "fips, countyname, st_abbrev, provisional_drug_overdose, footnote, percentage_of_records_pending, data_as_of",
        "$where": "year='2025' and month='12'"}, "cdc_county_overdose_2025_12.json")
    ccounts, seen, pend = {}, set(), {}
    for r in crow:
        f = str(r["fips"]).zfill(5)
        v = r.get("provisional_drug_overdose")
        v = int(num(v)) if v not in (None, "") else None
        if f in seen:
            # A few Virginia FIPS codes carry two rows (county and former independent city);
            # only a problem if it touches a county used here.
            if f in USED_FIPS:
                raise FetchError("duplicate county rows in gb4e-yj24 for " + f)
            continue
        seen.add(f)
        ccounts[f] = v
        pend[f] = r.get("percentage_of_records_pending")
    values, missing = peer_county_rates(ccounts, 2025, "overdose")
    log(f"  peers: {len(values)} values, missing {missing}")
    pops, pop_url = county_pop()
    boro = []
    for f, b in NYC_COUNTIES:
        boro.append({"name": b, "value": round(ccounts[f] / pops[f][2025] * 1e5, 1), "moe": None,
                     "count": ccounts[f]})
    nyc_county_sum = sum(ccounts[f] for f, _ in NYC_COUNTIES)

    write_indicator({
        "id": "overdose_deaths", "status": "ok", "status_reason": None,
        "name": "Drug overdose deaths",
        "definition": "Drug overdose deaths of all intents occurring in New York City in the calendar year, as "
                      "counted by CDC's National Center for Health Statistics (12-month-ending December value).",
        "units": "people", "format": "int", "better": "down", "frequency": "annual",
        "series": series,
        "latest_period": "2025",
        "latest_extra": {"period": f"12 months ending {latest_key[1]} {latest_key[0]}",
                         "value": int(num(lr["data_value"])),
                         "note": f"CDC provisional 12-month-ending count, reported value (CDC's adjusted "
                                 f"'predicted' value is {int(num(lr['predicted_value'])):,}); all intents, "
                                 f"deaths occurring in New York City."},
        "source": {"name": "CDC NCHS VSRR Provisional Drug Overdose Death Counts (xkb8-kh2a), jurisdiction "
                           "New York City, indicator 'Number of Drug Overdose Deaths'",
                   "url": "https://data.cdc.gov/d/xkb8-kh2a",
                   "endpoint": cdc_url,
                   "fetched": TODAY},
        "dohmh_series": dohmh_series,
        "dohmh_source": {"name": "NYC Health Department, Epi Data Brief No. 150 (October 2025): unintentional "
                                 "drug poisoning deaths, ages 15-84, occurring in New York City, 2000-2024 "
                                 "(2023 and 2024 provisional)",
                         "url": DB150, "endpoint": DB150, "fetched": TODAY},
        "peers": {
            "period": "2025", "geography": "county",
            "note": "Deaths per 100,000 residents in each city's principal county (New York = its five counties), "
                    "CDC provisional county counts for the 12 months ending December 2025 by county of residence, "
                    "all intents, divided by Census Vintage 2025 county population. County counts are by residence "
                    "while the New York City series is by place of death, so the New York peer value uses "
                    f"{nyc_county_sum:,} deaths rather than {dec[2025]:,}.",
            "source": {"name": "CDC NCHS VSRR Provisional County-Level Drug Overdose Death Counts; Census Bureau "
                               "Vintage 2025 county population estimates",
                       "url": "https://data.cdc.gov/d/gb4e-yj24",
                       "endpoint": county_url + " ; " + pop_url, "fetched": TODAY},
            "values": values},
        "peer_series": None,
        "breakdowns": [{"by": "borough", "period": "2025", "source_url": "https://data.cdc.gov/d/gb4e-yj24",
                        "note": "Deaths per 100,000 residents, CDC provisional county counts by county of "
                                "residence, 12 months ending December 2025, all intents.",
                        "values": boro}],
        "method": "Series: for every year CDC publishes (2015 on), the CDC VSRR 'Number of Drug Overdose "
                  "Deaths' for jurisdiction New York City, 12 months ending December, reported (data_value, not "
                  "predicted_value), so the definition is the same in every year. dohmh_series (context only, "
                  "not scored): counts read from the chart in Epi Data Brief No. 150 (unintentional drug "
                  "poisoning deaths, New York City, 2000 to 2024), checked against the brief's key finding for "
                  "2024. Peers: CDC county file "
                  "(gb4e-yj24), year 2025, month 12, divided by Census Vintage 2025 POPESTIMATE2025, times 100,000.",
        "caveats": [
            "The 2025 value is CDC provisional and could change when final data are released. CDC's file "
            f"notes for {min(footed)}-{max(footed)} that the numbers may differ from published reports using "
            "final data." if footed else "The 2025 value is CDC provisional and could change.",
            f"CDC's series starts in {cyears[0]}, so history is shorter than the Health Department's. CDC counts "
            "overdose deaths of all intents (ICD-10 X40-X44, X60-X64, X85, Y10-Y14) by the jurisdiction where "
            "the death occurred.",
            f"For context, the file also carries the Health Department's own count (dohmh_series, "
            f"{min(doh)}-{max(doh)}): unintentional overdoses only, ages 15-84, deaths in the city; it labels "
            "2023 and 2024 provisional. Where both exist CDC runs a little higher: " + "; ".join(gaps) + ".",
            ("County peer counts suppress values of 1-9; none of the peer counties are affected." if not missing
             else "County counts of 1-9 are suppressed; no 2025 value for: " + ", ".join(missing) + "."),
        ],
    })


# ----------------------------------------------------------------------------- infant mortality

def infant_mortality():
    log("infant_mortality")
    url = VS_URL.format(y=2023)
    path = download(url, "vs_summary_2023.pdf", 100000)
    pages = pdf_pages(path)
    pc1 = [t for t in pages if "Table PC1. Population, Live Births" in t and "Rate per" in t
           and "Under One" in t]
    if not pc1:
        raise FetchError("Table PC1 not found")
    series = {}
    for ln in "\n".join(pc1).split("\n"):
        m = re.match(r"^((?:19|20)\d\d)‡?\s+([\d,]+)\s+([\d,]+)\s+.*\s([\d,]+)\s+(\d+\.\d)$", ln.strip())
        if not m:
            continue
        yr = int(m.group(1))
        if yr < 2000 or yr in series:
            continue
        births = int(m.group(3).replace(",", ""))
        deaths = int(m.group(4).replace(",", ""))
        rate = float(m.group(5))
        if abs(deaths / births * 1000 - rate) > 0.06:
            raise FetchError(f"PC1 {yr}: rate {rate} inconsistent with {deaths}/{births}")
        series[yr] = (rate, deaths, births)
    if 2023 not in series or 2010 not in series:
        raise FetchError("PC1 parse incomplete: " + str(sorted(series)))
    log(f"  PC1 {min(series)}-{max(series)}: 2023={series[2023]}")
    rows, od_url = soql(NYC_OD, "fcau-jc6k", {"$order": "year"}, "nycod_infant_mortality.json")
    r23 = [r for r in rows if r["year"] == "2023"]
    tot = [r for r in r23 if r["materal_race_or_ethnicity"] == "Total"]
    if not tot or float(tot[0]["infant_mortality_rate"]) != series[2023][0]:
        raise FetchError("Open Data 2023 total does not match the Summary of Vital Statistics")
    race = []
    for r in r23:
        n = r["materal_race_or_ethnicity"]
        if n in ("Total",):
            continue
        race.append({"name": n, "value": float(r["infant_mortality_rate"]), "moe": None,
                     "infant_deaths": int(r["infant_deaths"]), "live_births": int(r["number_of_live_births"])})
    race.sort(key=lambda x: x["name"])
    write_indicator({
        "id": "infant_mortality", "status": "ok", "status_reason": None,
        "name": "Infant mortality rate",
        "definition": "Deaths of infants under 1 year old per 1,000 live births to New York City residents.",
        "units": "per 1,000 live births", "format": "dec1", "better": "down", "frequency": "annual",
        "series": [{"period": str(y), "value": series[y][0], "moe": None} for y in sorted(series)],
        "latest_period": str(max(series)),
        "latest_extra": None,
        "source": {"name": "NYC Department of Health and Mental Hygiene, Summary of Vital Statistics 2023, "
                           "Table PC1; NYC Open Data Infant Mortality (fcau-jc6k)",
                   "url": url, "endpoint": url + " ; " + od_url, "fetched": TODAY},
        "peers": None, "peer_series": None,
        "breakdowns": [{"by": "mother's race/ethnicity", "period": "2023",
                        "source_url": "https://data.cityofnewyork.us/d/fcau-jc6k", "values": race}],
        "method": "Infant deaths under one year and the rate per 1,000 live births read from Table PC1 "
                  "('Population, Live Births ... and Infant Mortality, New York City, 1898-2023') of the 2023 "
                  "Summary of Vital Statistics, 2000-2023; each year's printed rate was checked against "
                  "deaths / live births x 1,000. Race/ethnicity of mother for 2023 from NYC Open Data fcau-jc6k, "
                  "whose 2023 citywide total matches Table PC1.",
        "caveats": [
            "2023 is the latest published year; 2024 and 2025 vital statistics were not out when this was fetched.",
            f"Since 2010 annual rates rest on {min(series[y][1] for y in series if y >= 2010)} to "
            f"{max(series[y][1] for y in series if y >= 2010)} infant deaths a year, so small year-to-year moves "
            "can be chance.",
            "Race/ethnicity groups with few births (Puerto Rican; Other and Unknown) have unstable rates.",
            "Peers: no same-definition annual city series for the other cities was pulled, so peers are left out.",
        ],
    })


# ----------------------------------------------------------------------------- NYPD complaints

def complaint_counts():
    """Returns dict with yearly counts by ky_cd (historic), YTD info, borough splits."""
    hist_where = "ky_cd in(" + ",".join(f"'{k}'" for k, _, _ in MAJOR7) + ")"
    yrows, hurls = [], []
    for k, _, _ in MAJOR7:
        rr, u = soql(NYC_OD, "qgea-i56i", {
            "$select": "date_extract_y(rpt_dt) as y, ky_cd, ofns_desc, count(*) as n",
            "$where": f"ky_cd='{k}'", "$group": "y, ky_cd, ofns_desc", "$order": "y"},
            f"nypd_complaints_hist_by_year_ky{k}.json")
        yrows += rr
        hurls.append(u)
    hurl = hurls[0].replace("ky_cd%3D%27101%27", "ky_cd%3D%27<code>%27") + " (one query per offense code)"
    span, _ = soql(NYC_OD, "qgea-i56i", {"$select": "min(rpt_dt) as mn, max(rpt_dt) as mx"},
                   "nypd_complaints_hist_span.json")
    yspan, _ = soql(NYC_OD, "5uac-w243", {"$select": "min(rpt_dt) as mn, max(rpt_dt) as mx, count(*) as n"},
                    "nypd_complaints_ytd_span.json")
    hist_max = span[0]["mx"][:10]
    ytd_min, ytd_max = yspan[0]["mn"][:10], yspan[0]["mx"][:10]
    if hist_max > f"{LATEST}-12-31" or hist_max < f"{LATEST}-12-31":
        raise FetchError(f"historic complaint file ends {hist_max}, expected {LATEST}-12-31")
    if ytd_min <= hist_max:
        raise FetchError(f"year-to-date file starts {ytd_min}, overlapping the historic file (ends {hist_max})")
    ytd_year = int(ytd_max[:4])
    cut = ytd_max[5:10]
    ytd, yurl = soql(NYC_OD, "5uac-w243", {
        "$select": "ky_cd, count(*) as n", "$where": hist_where, "$group": "ky_cd"},
        "nypd_complaints_ytd_by_offense.json")
    prior, _ = soql(NYC_OD, "qgea-i56i", {
        "$select": "ky_cd, count(*) as n",
        "$where": hist_where + f" and rpt_dt between '{ytd_year - 1}-01-01T00:00:00' and '{ytd_year - 1}-{cut}T23:59:59'",
        "$group": "ky_cd"}, f"nypd_complaints_hist_{ytd_year - 1}_through_{cut}.json")
    boro, _ = soql(NYC_OD, "qgea-i56i", {
        "$select": "boro_nm, ky_cd, count(*) as n",
        "$where": hist_where + f" and rpt_dt between '{LATEST}-01-01T00:00:00' and '{LATEST}-12-31T23:59:59'",
        "$group": "boro_nm, ky_cd"}, f"nypd_complaints_{LATEST}_by_borough.json")
    by_year = {}
    descs = {}
    for r in yrows:
        by_year.setdefault(int(r["y"]), {})[r["ky_cd"]] = by_year.get(int(r["y"]), {}).get(r["ky_cd"], 0) + int(r["n"])
        descs.setdefault(r["ky_cd"], set()).add(r.get("ofns_desc"))
    nulldesc = {}
    for r in yrows:
        if r.get("ofns_desc") in (None, "", "(null)"):
            nulldesc[r["ky_cd"]] = nulldesc.get(r["ky_cd"], 0) + int(r["n"])
    for k, _, d in MAJOR7:
        named = {x for x in descs.get(k, set()) if x not in (None, "", "(null)")}
        if named != {d}:
            raise FetchError(f"ky_cd {k} maps to {descs.get(k)}, expected {d}")
    return {"by_year": by_year, "hist_url": hurl, "ytd_url": yurl, "hist_max": hist_max,
            "ytd_min": ytd_min, "ytd_max": ytd_max, "ytd_year": ytd_year,
            "ytd": {r["ky_cd"]: int(r["n"]) for r in ytd},
            "prior": {r["ky_cd"]: int(r["n"]) for r in prior},
            "boro": boro, "nulldesc": nulldesc}


def fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def boro_values(rows, codes):
    agg, other = {}, 0
    for r in rows:
        if r["ky_cd"] not in codes:
            continue
        b = BORO_NAME.get((r.get("boro_nm") or "").upper())
        if b:
            agg[b] = agg.get(b, 0) + int(r["n"])
        else:
            other += int(r["n"])
    vals = [{"name": b, "value": agg.get(b, 0), "moe": None} for b in sorted(BORO_NAME.values())]
    return vals, other


def crime_peers(cities):
    """Real-Time Crime Index historical file (FBI annual agency counts): 2025 murders per 100k."""
    page = download("https://crimeindex.org/download", "crimeindex_download_page.html", 1000)
    with open(page, encoding="utf-8", errors="replace") as fh:
        ptxt = fh.read()
    urls = re.findall(r"https://crimeindex-data\.s3\.[a-z0-9-]+\.amazonaws\.com/downloads/"
                      r"historical_crime_1930_\d{4}_\d+\.csv", ptxt)
    if not urls:
        raise FetchError("no historical crime file link on crimeindex.org/download")
    url = sorted(set(urls))[-1]
    extract = raw_path("crimeindex_historical_crime_peer_agencies.csv")
    if not cached(extract):
        log("  downloading Real-Time Crime Index historical file (about 120 MB, filtering to peer agencies)")
        data = http_bytes(url, timeout=900)
        want = {o for o, _ in CITY_ORI.values()}
        rdr = csv.DictReader(io.StringIO(data.decode("utf-8")))
        kept = [r for r in rdr if r["id"] in want]
        if not kept:
            raise FetchError("no peer agencies in the crime index file")
        with open(extract + ".part", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=rdr.fieldnames)
            w.writeheader()
            w.writerows(kept)
        os.replace(extract + ".part", extract)
        with open(raw_path("crimeindex_historical_crime_source.txt"), "w") as fh:
            fh.write(url + "\nfetched " + TODAY + "\nfiltered to ORIs: " + ", ".join(sorted(want)) + "\n")
    rows = {}
    with open(extract) as fh:
        for r in csv.DictReader(fh):
            rows[(r["id"], int(r["year"]))] = r
    pop2025 = {c["name"]: c["pop2025"] for c in cities}
    values, problems = [], []
    for c in cities:
        city = c["name"]
        ori, agency = CITY_ORI[city]
        r = rows.get((ori, LATEST))
        if not r or not r.get("murder_total") or not r.get("population"):
            problems.append(f"{city}: no {LATEST} row for {ori}")
            continue
        p = float(r["population"])
        ratio = p / pop2025[city]
        if city not in ORI_WIDER and not (0.9 <= ratio <= 1.1):
            raise FetchError(f"{city}: agency {ori} population {p:,.0f} vs city {pop2025[city]:,} - wrong ORI?")
        m = float(r["murder_total"])
        values.append({"city": city, "value": round(m / p * 1e5, 1), "moe": None,
                       "geo_name": f"{agency} (ORI {ori}); jurisdiction population {p:,.0f}",
                       "count": int(m), "population": int(p)})
    return values, problems, url, rows


def murders(cc, cities):
    log("murders")
    by_year = cc["by_year"]
    series = [{"period": str(y), "value": by_year[y].get(MURDER, 0), "moe": None}
              for y in sorted(by_year) if 2006 <= y <= LATEST]
    ytd, prior = cc["ytd"].get(MURDER, 0), cc["prior"].get(MURDER, 0)
    span = f"January 1 to {fmt_date(cc['ytd_max'])[:-6]}"
    bvals, bother = boro_values(cc["boro"], {MURDER})
    peers, problems, purl, prow = crime_peers(cities)
    nyc_fbi = {y: int(float(prow[("NY0303000", y)]["murder_total"])) for y in range(2006, LATEST + 1)
               if ("NY0303000", y) in prow and prow[("NY0303000", y)].get("murder_total")}
    comp = {int(s["period"]): s["value"] for s in series}
    mism = [f"{y}: complaint data {comp[y]}, FBI {nyc_fbi[y]}" for y in sorted(nyc_fbi)
            if y in comp and nyc_fbi[y] != comp[y]]
    log(f"  2025={comp[LATEST]}; YTD {cc['ytd_year']}={ytd} vs {prior}; peers {len(peers)}; FBI mismatches {mism}")
    write_indicator({
        "id": "murders", "status": "ok", "status_reason": None,
        "name": "Murders",
        "definition": "Murder and non-negligent manslaughter complaints recorded by the NYPD, by the year the "
                      "complaint was reported.",
        "units": "count", "format": "int", "better": "down", "frequency": "annual",
        "series": series, "latest_period": str(LATEST),
        "latest_extra": {"period": f"{span}, {cc['ytd_year']}", "value": ytd,
                         "comparison": {"period": f"{span}, {cc['ytd_year'] - 1}", "value": prior},
                         "note": f"{ytd} murders reported {span}, {cc['ytd_year']}, compared with {prior} in the "
                                 f"same span of {cc['ytd_year'] - 1}. Year-to-date file (5uac-w243) ends "
                                 f"{fmt_date(cc['ytd_max'])}."},
        "source": {"name": "NYPD Complaint Data Historic (qgea-i56i) and Current Year To Date (5uac-w243), NYC Open Data",
                   "url": "https://data.cityofnewyork.us/d/qgea-i56i",
                   "endpoint": cc["hist_url"] + " ; " + cc["ytd_url"], "fetched": TODAY},
        "peers": {
            "period": str(LATEST), "geography": "city",
            "note": "Murders per 100,000 residents of each city police agency's jurisdiction, from the Real-Time "
                    "Crime Index historical file, which compiles FBI annual agency counts. All cities, New York "
                    "included, come from that one file so they share a definition; New York's figure there "
                    f"({next((v['count'] for v in peers if v['city'] == 'New York'), 'n/a')}) differs from the "
                    "complaint-data series. Las Vegas is the Las Vegas Metropolitan Police Department, whose "
                    "jurisdiction includes unincorporated Clark County; Charlotte is the Charlotte-Mecklenburg "
                    "Police Department.",
            "source": {"name": "Real-Time Crime Index (AH Datalytics), historical crime file based on FBI "
                               "Uniform Crime Reporting data",
                       "url": "https://crimeindex.org/download", "endpoint": purl, "fetched": TODAY},
            "values": peers},
        "peer_series": None,
        "breakdowns": [{"by": "borough", "period": str(LATEST), "source_url": "https://data.cityofnewyork.us/d/qgea-i56i",
                        "values": bvals}],
        "method": "SoQL count of complaints with KY_CD 101 (OFNS_DESC 'MURDER & NON-NEGL. MANSLAUGHTER'), "
                  "grouped by the year of RPT_DT, the date the complaint was reported, in the historic file "
                  "(2006 to December 31, 2025). The historic file ends December 31, 2025 and the year-to-date "
                  f"file starts {fmt_date(cc['ytd_min'])}, so the two do not overlap and nothing is double "
                  "counted. Year-to-date comparison: 2026 rows in the year-to-date file versus 2025 rows in the "
                  "historic file with RPT_DT in the same January 1 to end-date window. Peers: murder_total / "
                  "population x 100,000 for 2025 in the Real-Time Crime Index file, one police agency per city; "
                  "each agency's population was checked against the city's Census population (within 10%, "
                  "except Las Vegas and Charlotte, whose agencies cover more than the city).",
        "caveats": [
            "These are counts of complaints in the open data, by report date. NYPD CompStat year-end murder "
            "figures are compiled separately and can differ by a few.",
            "Counts in the open data can be revised as cases are reclassified (for example, an assault "
            "becoming a murder when a victim dies).",
            ("The FBI figures for New York, used only for the peer ranking, differ from the complaint data in "
             "these years: " + "; ".join(mism) + ". The gap is small before 2023 and larger since.") if mism else
            "The FBI figures for New York match the complaint data in every year.",
        ] + ([f"Peers missing: {'; '.join(problems)}"] if problems else []) + (
            [f"{bother} 2025 murders had no borough recorded."] if bother else []),
    })


def major_felonies(cc):
    log("major_felonies")
    by_year = cc["by_year"]
    codes = {k for k, _, _ in MAJOR7}
    series = [{"period": str(y), "value": sum(by_year[y].get(k, 0) for k in codes), "moe": None}
              for y in sorted(by_year) if 2006 <= y <= LATEST]
    ytd = sum(cc["ytd"].get(k, 0) for k in codes)
    prior = sum(cc["prior"].get(k, 0) for k in codes)
    span = f"January 1 to {fmt_date(cc['ytd_max'])[:-6]}"
    bvals, bother = boro_values(cc["boro"], codes)
    offense = [{"name": lab, "value": by_year[LATEST].get(k, 0), "moe": None} for k, lab, _ in MAJOR7]
    rape = {y: by_year[y].get("104", 0) for y in (2022, 2023, 2024, 2025)}
    log(f"  2025={series[-1]['value']}; YTD {ytd} vs {prior}; rape {rape}")
    write_indicator({
        "id": "major_felonies", "status": "ok", "status_reason": None,
        "name": "Major felony crimes reported",
        "definition": "Complaints recorded by the NYPD in its seven major felony categories (murder, rape, "
                      "robbery, felony assault, burglary, grand larceny, grand larceny of a motor vehicle), by "
                      "the year the complaint was reported.",
        "units": "count", "format": "int", "better": "down", "frequency": "annual",
        "series": series, "latest_period": str(LATEST),
        "latest_extra": {"period": f"{span}, {cc['ytd_year']}", "value": ytd,
                         "comparison": {"period": f"{span}, {cc['ytd_year'] - 1}", "value": prior},
                         "note": f"{ytd:,} major felonies reported {span}, {cc['ytd_year']}, compared with "
                                 f"{prior:,} in the same span of {cc['ytd_year'] - 1}."},
        "source": {"name": "NYPD Complaint Data Historic (qgea-i56i) and Current Year To Date (5uac-w243), NYC Open Data",
                   "url": "https://data.cityofnewyork.us/d/qgea-i56i",
                   "endpoint": cc["hist_url"] + " ; " + cc["ytd_url"], "fetched": TODAY},
        "peers": None, "peer_series": None,
        "breakdowns": [
            {"by": "offense", "period": str(LATEST), "source_url": "https://data.cityofnewyork.us/d/qgea-i56i",
             "values": offense},
            {"by": "borough", "period": str(LATEST), "source_url": "https://data.cityofnewyork.us/d/qgea-i56i",
             "values": bvals}],
        "method": "SoQL count of complaints grouped by year of RPT_DT (report date) and offense key code. "
                  "Offense mapping (KY_CD = OFNS_DESC): 101 = MURDER & NON-NEGL. MANSLAUGHTER; 104 = RAPE; "
                  "105 = ROBBERY; 106 = FELONY ASSAULT; 107 = BURGLARY; 109 = GRAND LARCENY; 110 = GRAND "
                  "LARCENY OF MOTOR VEHICLE. The script checks that each code carries exactly that "
                  "description (a few rows carry the code with a blank description; they are counted by "
                  "code). All rows in these codes are felonies (LAW_CAT_CD = FELONY). Historic file "
                  "through December 31, 2025; the year-to-date file starts January 1, 2026, so there is no "
                  "overlap.",
        "caveats": [
            "Totals from complaint data can differ slightly from NYPD CompStat figures, which are compiled "
            "separately.",
            "New York State broadened its legal definition of rape effective September 2024, which affects "
            f"comparisons of the rape component (complaints: {rape[2023]:,} in 2023, {rape[2024]:,} in 2024, "
            f"{rape[2025]:,} in 2025).",
            "Peers: crime categories and counting rules differ across police departments (the FBI uses its own "
            "definitions, and the NYPD's seven majors are a local grouping), so no peer comparison is given.",
        ] + ([f"{bother:,} 2025 complaints had no borough recorded."] if bother else []) + (
            ["Rows with an offense code but a blank offense description, counted by code: " +
             ", ".join(f"KY_CD {k}: {v:,}" for k, v in sorted(cc["nulldesc"].items())) + " (all years)."]
            if cc["nulldesc"] else []),
    })


# ----------------------------------------------------------------------------- shootings

def shooting_victims():
    log("shooting_victims")
    meta = socrata_meta(NYC_OD, "pztn-9bne", "nycod_shooting_victims_meta.json")
    desc = meta.get("description") or ""
    if "every shooting victim" not in desc:
        raise FetchError("pztn-9bne description no longer says it lists every shooting victim")
    imeta = socrata_meta(NYC_OD, "5ucz-vwe8", "nycod_shootings_meta.json")
    if "every shooting incident" not in (imeta.get("description") or ""):
        raise FetchError("5ucz-vwe8 description changed")
    inc, iurl = soql(NYC_OD, "5ucz-vwe8", {"$select": "incident_key, occur_date, boro", "$limit": "200000"},
                     "nycod_shootings_incidents.json")
    vic, vurl = soql(NYC_OD, "pztn-9bne", {"$select": "incident_key, victim_id, stat_murder_flg", "$limit": "200000"},
                     "nycod_shooting_victims.json")
    incd = {}
    for r in inc:
        if r["incident_key"] in incd:
            raise FetchError("duplicate incident_key in 5ucz-vwe8")
        incd[r["incident_key"]] = r
    seen, dups, orphans = set(), 0, set()
    by_year, by_boro = {}, {}
    max_date = max(r["occur_date"] for r in inc)[:10]
    ytd_year = int(max_date[:4])
    cut = max_date[5:10]
    ytd = prior = 0
    noid = 0
    for n, r in enumerate(vic):
        vid = r.get("victim_id")
        if not vid:
            noid += 1
            vid = f"{r['incident_key']}-noid-{n}"
        if vid in seen:
            dups += 1
            continue
        seen.add(vid)
        i = incd.get(r["incident_key"])
        if not i:
            orphans.add(r["incident_key"])
            continue
        d = i["occur_date"][:10]
        y = int(d[:4])
        by_year[y] = by_year.get(y, 0) + 1
        if y == LATEST:
            b = BORO_NAME.get((i.get("boro") or "").upper(), "Unknown")
            by_boro[b] = by_boro.get(b, 0) + 1
        if y == ytd_year:
            ytd += 1
        if y == ytd_year - 1 and d[5:10] <= cut:
            prior += 1
    log(f"  victims {len(seen)} unique ({dups} duplicate rows, {len(orphans)} orphan incident keys); "
        f"2025={by_year.get(LATEST)}; YTD {ytd} vs {prior}")
    series = [{"period": str(y), "value": by_year[y], "moe": None} for y in sorted(by_year) if 2006 <= y <= LATEST]
    span = f"January 1 to {fmt_date(max_date)[:-6]}"
    write_indicator({
        "id": "shooting_victims", "status": "ok", "status_reason": None,
        "name": "Shooting victims",
        "definition": "People shot in New York City shooting incidents recorded by the NYPD, by the year the "
                      "shooting occurred.",
        "units": "people", "format": "int", "better": "down", "frequency": "annual",
        "series": series, "latest_period": str(LATEST),
        "latest_extra": {"period": f"{span}, {ytd_year}", "value": ytd,
                         "comparison": {"period": f"{span}, {ytd_year - 1}", "value": prior},
                         "note": f"{ytd} shooting victims {span}, {ytd_year}, compared with {prior} in the same "
                                 f"span of {ytd_year - 1}; latest incident date in the data is {fmt_date(max_date)}."},
        "source": {"name": "NYPD Shooting Victims (2006-Present), pztn-9bne, joined to NYPD Shootings "
                           "(2006-Present), 5ucz-vwe8, NYC Open Data",
                   "url": "https://data.cityofnewyork.us/d/pztn-9bne",
                   "endpoint": vurl + " ; " + iurl, "fetched": TODAY},
        "peers": None, "peer_series": None,
        "breakdowns": [{"by": "borough", "period": str(LATEST), "source_url": "https://data.cityofnewyork.us/d/5ucz-vwe8",
                        "values": [{"name": b, "value": by_boro.get(b, 0), "moe": None}
                                   for b in sorted(BORO_NAME.values())] +
                                  ([{"name": "Unknown", "value": by_boro["Unknown"], "moe": None}]
                                   if by_boro.get("Unknown") else [])}],
        "method": "The Shootings dataset (5ucz-vwe8) now has one row per shooting incident, not per victim (its "
                  "description says it 'identifies every shooting incident'). Victims are in the companion "
                  "Shooting Victims dataset (pztn-9bne), which has no date, so each victim was joined to its "
                  "incident on INCIDENT_KEY and counted by the year of the incident's OCCUR_DATE. Rows repeating "
                  "the same VICTIM_ID were counted once. Borough is the incident's borough.",
        "caveats": [
            f"{dups} exact duplicate victim rows in pztn-9bne were dropped (same VICTIM_ID).",
            f"{len(orphans)} victim incident keys had no matching incident and were left out.",
            f"{noid} victim row(s) had no VICTIM_ID; each was counted as one victim.",
            "Shooting victims include people killed and people wounded.",
            "Peers: shooting victim counts are not published on a common definition across the 25 cities, so "
            "peers are left out.",
        ],
    })


# ----------------------------------------------------------------------------- traffic deaths

DOT_PR = "https://www.nyc.gov/html/dot/html/pr2026/traffic-deaths-reach-all-time-low.shtml"
FARS_YEAR = 2023
FARS_URL = f"https://static.nhtsa.gov/nhtsa/downloads/FARS/{FARS_YEAR}/National/FARS{FARS_YEAR}NationalCSV.zip"


def traffic_deaths():
    log("traffic_deaths")
    rows, curl = soql(NYC_OD, "h9gi-nx95", {
        "$select": "date_extract_y(crash_date) as y, sum(number_of_persons_killed) as k, count(*) as n, max(crash_date) as mx",
        "$group": "y", "$order": "y"}, "nycod_collisions_killed_by_year.json")
    by = {int(r["y"]): int(float(r["k"])) for r in rows}
    mx = max(r["mx"] for r in rows)[:10]
    series = [{"period": str(y), "value": by[y], "moe": None} for y in sorted(by) if 2013 <= y <= LATEST]
    ytd_year = int(mx[:4])
    prior_rows, _ = soql(NYC_OD, "h9gi-nx95", {
        "$select": "sum(number_of_persons_killed) as k",
        "$where": f"crash_date between '{ytd_year - 1}-01-01T00:00:00' and '{ytd_year - 1}-{mx[5:10]}T23:59:59'"},
        f"nycod_collisions_killed_{ytd_year - 1}_through_{mx[5:10]}.json")
    prior = int(float(prior_rows[0]["k"]))
    # DOT official counts from the year-end release
    dot_total = dot_prev = None
    dot_boro = []
    try:
        p = download(DOT_PR, "dot_pr2026_traffic_deaths_all_time_low.html", 1000)
        with open(p, "rb") as fh:
            t = page_text(fh.read())
        m = re.search(r"There were (\d+) recorded traffic deaths in 2025, a \d+ percent decline from (\d+) "
                      r"fatalities last year", t)
        if m:
            dot_total, dot_prev = int(m.group(1)), int(m.group(2))
        for b in ["Bronx", "Queens", "Manhattan", "Brooklyn", "Staten Island"]:
            mb = re.search(re.escape(b) + r" (?:experienced|remained|saw)[^;]{0,160}?from (\d+)(?: \w+)? in 2024 "
                           r"to (\d+)(?: \w+)? in 2025", t)
            if mb:
                dot_boro.append({"name": b, "value": int(mb.group(2)), "moe": None})
        if dot_total is None or len(dot_boro) != 5 or sum(v["value"] for v in dot_boro) != dot_total:
            log(f"  DOT release parse incomplete (total {dot_total}, boroughs {dot_boro}); not used")
            dot_boro = []
    except FetchError as e:
        log(f"  DOT release not read: {e}")
    # FARS peers (county)
    zpath = download(FARS_URL, f"FARS{FARS_YEAR}NationalCSV.zip", 1000000)
    z = zipfile.ZipFile(zpath)
    an = [n for n in z.namelist() if n.lower().endswith("/accident.csv")]
    if not an:
        raise FetchError("accident.csv not in FARS zip")
    fat = {}
    nrows = 0
    for r in csv.DictReader(io.TextIOWrapper(z.open(an[0]), encoding="latin-1")):
        nrows += 1
        f = r["STATE"].zfill(2) + r["COUNTY"].zfill(3)
        fat[f] = fat.get(f, 0) + int(r["FATALS"])
    if nrows < 30000:
        raise FetchError("FARS accident file looks incomplete")
    values, missing = peer_county_rates(fat, FARS_YEAR, "FARS")
    nyc_fars = sum(fat.get(f, 0) for f, _ in NYC_COUNTIES)
    log(f"  NYPD 2025={by[LATEST]}; DOT 2025={dot_total}; FARS NYC {FARS_YEAR}={nyc_fars}; peers {len(values)}")
    caveats = [
        "NYPD collision reports and DOT's official Vision Zero count are compiled differently; DOT reviews "
        "each death before counting it, and its release does not spell out the criteria, so the gap between "
        "the two cannot be broken down here.",
    ]
    if dot_total is not None:
        caveats.insert(0, f"DOT's official count is lower than the NYPD collision data, not higher: DOT reported "
                          f"{dot_total} traffic deaths in 2025 and {dot_prev} in 2024; the NYPD collision data "
                          f"sum to {by[LATEST]} and {by[LATEST - 1]}. DOT publishes its count in press releases "
                          f"rather than as an annual data series, so the NYPD series is used here and DOT is the "
                          f"cross-check. Source: {DOT_PR}")
    caveats += [
        "2012 is left out because the collision dataset starts in July 2012.",
        f"Peers use NHTSA FARS {FARS_YEAR}, the latest final FARS year (NHTSA's {FARS_YEAR + 1} file, released "
        f"April 2026, is the annual report file, not yet final). FARS counts deaths within 30 days of a crash "
        f"on a public road. For New York "
        f"City FARS records {nyc_fars} deaths in {FARS_YEAR}, versus {by[FARS_YEAR]} in the NYPD collision data.",
        "Peers are counties, not cities: FARS city codes are inconsistent (much of Queens is coded under "
        "neighborhood names, and Nashville under Antioch, Madison and others), so each city's principal "
        "county is used, with the five counties for New York. Suburban and highway mileage in large counties "
        "such as Harris, Maricopa or Los Angeles differs from the city itself.",
    ]
    write_indicator({
        "id": "traffic_deaths", "status": "ok", "status_reason": None,
        "name": "Traffic deaths",
        "definition": "People killed in motor vehicle crashes in New York City, as recorded in NYPD collision "
                      "reports, by year of the crash.",
        "units": "people", "format": "int", "better": "down", "frequency": "annual",
        "series": series, "latest_period": str(LATEST),
        "latest_extra": {"period": f"January 1 to {fmt_date(mx)[:-6]}, {ytd_year}", "value": by.get(ytd_year),
                         "comparison": {"period": f"January 1 to {fmt_date(mx)[:-6]}, {ytd_year - 1}", "value": prior},
                         "note": f"NYPD collision data; latest crash date in the data is {fmt_date(mx)}. Recent "
                                 f"weeks may be incomplete."},
        "source": {"name": "NYPD Motor Vehicle Collisions - Crashes (h9gi-nx95), NYC Open Data",
                   "url": "https://data.cityofnewyork.us/d/h9gi-nx95", "endpoint": curl, "fetched": TODAY},
        "peers": {
            "period": str(FARS_YEAR), "geography": "county",
            "note": f"Traffic deaths per 100,000 residents in each city's principal county (New York = its five "
                    f"counties), NHTSA FARS {FARS_YEAR} final file, divided by Census Vintage 2025 estimates of "
                    f"{FARS_YEAR} county population. FARS city codes proved unreliable, so counties are used.",
            "source": {"name": f"NHTSA Fatality Analysis Reporting System, {FARS_YEAR} national CSV; Census Bureau "
                               f"Vintage 2025 county population estimates",
                       "url": "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars",
                       "endpoint": FARS_URL + " ; " + county_pop()[1], "fetched": TODAY},
            "values": values},
        "peer_series": None,
        "breakdowns": ([{"by": "borough", "period": "2025", "source_url": DOT_PR,
                         "note": "NYC DOT official count (from its January 2, 2026 release), which totals "
                                 f"{dot_total} rather than the NYPD series value.",
                         "values": dot_boro}] if dot_boro else []),
        "method": "SoQL sum of NUMBER_OF_PERSONS_KILLED grouped by year of CRASH_DATE in h9gi-nx95, 2013-2025. "
                  "DOT's official 2025 and 2024 totals and 2025 borough counts were read from DOT's year-end "
                  "press release and checked to sum to the total. Peers: sum of FATALS in FARS accident.csv by "
                  "STATE and COUNTY, divided by county population, times 100,000.",
        "caveats": caveats,
    })


# ----------------------------------------------------------------------------- jail population

VERA_URL = "https://raw.githubusercontent.com/vera-institute/incarceration-trends/main/incarceration_trends_county.csv"


def jail_population():
    log("jail_population")
    rows, jurl = soql(NYS, "nymx-kgkn", {"$where": "facility_name='All NYC Facilities'", "$order": "year"},
                      "dcjs_jail_population_nyc.json")
    by = {int(r["year"]): r for r in rows}
    if LATEST not in by:
        raise FetchError(f"DCJS has no {LATEST} row for NYC")
    series = [{"period": str(y), "value": int(float(by[y]["census_2"])), "moe": None} for y in sorted(by)]
    r25 = by[LATEST]
    status_vals = [("Awaiting trial or sentencing, and other unsentenced", "other_unsentenced"),
                   ("Sentenced to a city jail term", "sentenced"),
                   ("Sentenced to state prison, awaiting transfer", "state_readies"),
                   ("Held for a federal agency", "federal"),
                   ("Technical parole violators", "technical_parole_violators"),
                   ("Civil", "civil")]
    status = [{"name": n, "value": int(float(r25[k])), "moe": None} for n, k in status_vals]
    # Latest snapshot: DOC daily in-custody file
    extra = None
    try:
        snap, surl = soql(NYC_OD, "7479-ugqb", {"$select": "count(*) as n, max(admitted_dt) as mx"},
                          "nycod_doc_daily_in_custody_count.json")
        meta = socrata_meta(NYC_OD, "7479-ugqb", "nycod_doc_daily_in_custody_meta.json")
        upd = datetime.datetime.utcfromtimestamp(meta["rowsUpdatedAt"]).date()
        extra = {"period": f"{fmt_date(upd.isoformat())} (one day)", "value": int(snap[0]["n"]),
                 "note": "People in DOC custody on one day, from NYC Open Data 'Daily Inmates In Custody' "
                         "(7479-ugqb), which excludes sealed cases, so it runs slightly below an official count. "
                         "A single day, not an annual average.",
                 "source_url": "https://data.cityofnewyork.us/d/7479-ugqb"}
    except FetchError as e:
        log(f"  DOC snapshot not read: {e}")
    # Vera peers (county jail population per 100,000 aged 15-64)
    extract = raw_path("vera_incarceration_trends_peer_counties.csv")
    want = {f for f, _ in NYC_COUNTIES} | {st + co for st, co, _ in PRINCIPAL_COUNTY.values()}
    if not cached(extract):
        log("  downloading Vera incarceration trends county file (about 60 MB, filtering to peer counties)")
        data = http_bytes(VERA_URL, timeout=900)
        rdr = csv.DictReader(io.StringIO(data.decode("utf-8")))
        kept = [r for r in rdr if r["county_fips"].zfill(5) in want]
        if not kept:
            raise FetchError("no peer counties in Vera file")
        with open(extract + ".part", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=rdr.fieldnames)
            w.writeheader()
            w.writerows(kept)
        os.replace(extract + ".part", extract)
    vera = {}
    with open(extract) as fh:
        for r in csv.DictReader(fh):
            vera[(r["county_fips"].zfill(5), int(r["year"]))] = r
    vyear = max(y for (f, y), r in vera.items() if f == "36061" and r.get("total_jail_pop_rate"))
    peers, vmissing = [], []
    nyc_j = sum(float(vera[(f, vyear)]["total_jail_pop"]) for f, _ in NYC_COUNTIES)
    nyc_p = sum(float(vera[(f, vyear)]["total_pop_15to64"]) for f, _ in NYC_COUNTIES)
    peers.append({"city": "New York", "value": round(nyc_j / nyc_p * 1e5, 1), "moe": None,
                  "geo_name": "New York City (five counties)"})
    for city, (st, co, cname) in PRINCIPAL_COUNTY.items():
        r = vera.get((st + co, vyear))
        if not r or not r.get("total_jail_pop_rate"):
            vmissing.append(f"{city} ({cname})")
            continue
        peers.append({"city": city, "value": round(float(r["total_jail_pop_rate"]), 1), "moe": None,
                      "geo_name": cname})
    log(f"  DCJS {min(by)}-{max(by)} 2025={series[-1]['value']}; Vera {vyear} peers {len(peers)} missing {vmissing}")
    write_indicator({
        "id": "jail_population", "status": "ok", "status_reason": None,
        "name": "People in city jails",
        "definition": "Average daily number of people in the custody of the NYC Department of Correction "
                      "(the 'census' reported to the State Commission of Correction, including anyone boarded "
                      "out to another facility), calendar year.",
        "units": "people", "format": "int", "better": "none", "frequency": "annual",
        "series": series, "latest_period": str(LATEST),
        "latest_extra": extra,
        "source": {"name": "New York State Division of Criminal Justice Services, Jail Population By County: "
                           "Beginning 1997 (data.ny.gov nymx-kgkn), 'All NYC Facilities'",
                   "url": "https://data.ny.gov/d/nymx-kgkn", "endpoint": jurl, "fetched": TODAY},
        "peers": {
            "period": str(vyear), "geography": "county",
            "note": f"Jail population per 100,000 residents aged 15-64 in each city's principal county, from "
                    f"Vera's Incarceration Trends ({vyear} is its latest year with jail rates; there is no 2025). "
                    "Vera spreads New York City's jail population across the five counties; the New York value "
                    "is their combined jail population over their combined population aged 15-64."
                    + (f" Missing: {', '.join(vmissing)}." if vmissing else ""),
            "source": {"name": "Vera Institute of Justice, Incarceration Trends (county file)",
                       "url": "https://github.com/vera-institute/incarceration-trends",
                       "endpoint": VERA_URL, "fetched": TODAY},
            "values": peers},
        "peer_series": None,
        "breakdowns": [{"by": "legal status", "period": str(LATEST), "source_url": "https://data.ny.gov/d/nymx-kgkn",
                        "note": "Average daily in-house population by status; sums to the in-house census "
                                f"({int(float(r25['census'])):,}), which excludes the few people boarded out.",
                        "values": status}],
        "method": "CENSUS (field census_2: average daily number of people the facility is responsible for, "
                  "in house or boarded out) for facility 'All NYC Facilities', by year.",
        "caveats": [
            "DCJS publishes New York City figures only from 2016, so the series starts there. Earlier calendar-"
            "year averages were not found in a downloadable official source; the Mayor's Management Report "
            "gives fiscal-year averages, which are not comparable.",
            "Better is set to 'none': a falling jail population can reflect policy choices (bail law, diversion) "
            "as well as less crime.",
            "Vera's rate uses residents aged 15-64 as the denominator, not total population.",
        ],
    })


# ----------------------------------------------------------------------------- main

def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(IND, exist_ok=True)
    cities = load_peers()
    names = {c["name"] for c in cities}
    for k in list(PRINCIPAL_COUNTY) + list(CITY_ORI):
        if k not in names:
            raise FetchError(f"{k} not in data/peers.json")
    failures = []
    steps = [("life_expectancy", life_expectancy), ("overdose_deaths", overdose_deaths),
             ("infant_mortality", infant_mortality), ("shooting_victims", shooting_victims),
             ("traffic_deaths", traffic_deaths), ("jail_population", jail_population)]
    for name, fn in steps:
        try:
            fn()
        except Exception as e:  # keep going, fail at the end
            log(f"  FAILED {name}: {e}")
            failures.append(name)
    try:
        cc = complaint_counts()
        for name, fn in [("murders", lambda: murders(cc, cities)), ("major_felonies", lambda: major_felonies(cc))]:
            try:
                fn()
            except Exception as e:
                log(f"  FAILED {name}: {e}")
                failures.append(name)
    except Exception as e:
        log(f"  FAILED complaint data: {e}")
        failures += ["murders", "major_felonies"]
    if failures:
        log("FAILED: " + ", ".join(failures))
        sys.exit(1)
    log("done")


if __name__ == "__main__":
    main()
