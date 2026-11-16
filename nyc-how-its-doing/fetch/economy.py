#!/usr/bin/env python3
"""Fetcher for the "economy" group of How New York Is Doing (edition: New York in 2025).

Run from the project folder:  python3 -I fetch/economy.py  [--refresh]

Writes data/indicators/<id>.json for:
  payroll_jobs, unemployment_rate, real_hourly_earnings, business_applications,
  poverty_tracker_rate, asking_rent

Raw downloads are cached in data/raw/economy/. Without --refresh, cached files are reused so
the build can be rerun offline and BLS's keyless daily query limit is not spent again.
Standard library only. Any failed or empty download raises and the script exits non-zero.
"""
import csv
import datetime
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "economy")
OUT = os.path.join(ROOT, "data", "indicators")
UA = "Mozilla/5.0 (compatible; civic-data-fetcher/1.0)"
TODAY = datetime.date.today().isoformat()
REFRESH = "--refresh" in sys.argv
EDITION_YEAR = 2025

BLS_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_QUERIES_LIVE = 0

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]

BOROUGHS = [("Bronx", "36005"), ("Brooklyn", "36047"), ("Manhattan", "36061"),
            ("Queens", "36081"), ("Staten Island", "36085")]
NYC_COUNTIES = [f for _, f in BOROUGHS]


class FetchError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- helpers

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_indicator(obj):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, obj["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote", os.path.relpath(path, ROOT))


def http(url, data=None, headers=None, timeout=120, tries=3):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status != 200:
                    raise FetchError(f"HTTP {r.status} for {url}")
                body = r.read()
            if not body:
                raise FetchError(f"empty response from {url}")
            return body
        except Exception as e:  # retry network errors, then give up loudly
            last = e
            time.sleep(2 * (i + 1))
    raise FetchError(f"download failed for {url}: {last}")


def cached_download(url, name, check=None):
    """Download url to data/raw/economy/<name> unless already cached. Returns bytes."""
    path = os.path.join(RAW, name)
    if os.path.exists(path) and not REFRESH:
        with open(path, "rb") as f:
            body = f.read()
        if not body:
            raise FetchError(f"cached file is empty: {path}")
    else:
        body = http(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(body)
    if check and not check(body):
        raise FetchError(f"unexpected content in {name} from {url}")
    return body


def mean(xs):
    return sum(xs) / len(xs)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# ----------------------------------------------------------------------------- BLS

def bls_fetch(series, start, end, tag):
    """One keyless v1 query (max 25 series, 10 years). Cached to data/raw/economy/bls_<tag>.json."""
    global BLS_QUERIES_LIVE
    assert len(series) <= 25 and end - start <= 9
    path = os.path.join(RAW, f"bls_{tag}.json")
    if os.path.exists(path) and not REFRESH:
        resp = load_json(path)
        if not set(series) <= set(resp.get("request", {}).get("seriesid", [])):
            raise FetchError(f"cache {path} lacks some requested series; rerun with --refresh")
    else:
        payload = json.dumps({"seriesid": series, "startyear": str(start), "endyear": str(end)}).encode()
        body = http(BLS_V1, data=payload, headers={"Content-Type": "application/json"})
        BLS_QUERIES_LIVE += 1
        resp = json.loads(body)
        if resp.get("status") != "REQUEST_SUCCEEDED":
            raise FetchError(f"BLS query {tag} failed: {resp.get('status')} {resp.get('message')}")
        resp["request"] = {"seriesid": series, "startyear": start, "endyear": end, "fetched": TODAY}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(resp, f)
    out = {}
    for s in resp["Results"]["series"]:
        pts = {}
        for d in s.get("data", []):
            if not re.fullmatch(r"M(0[1-9]|1[0-2])", d["period"]):
                continue
            try:
                v = float(d["value"])
            except ValueError:  # "-" = not available
                continue
            notes = [fn.get("code") for fn in d.get("footnotes", []) if fn and fn.get("code")]
            pts[(int(d["year"]), int(d["period"][1:]))] = (v, notes)
        out[s["seriesID"]] = pts
    return out, resp.get("message", [])


def merge(dst, src):
    for k, v in src.items():
        dst.setdefault(k, {}).update(v)


def annual(pts, year, need=12):
    vals = [pts[(year, m)][0] for m in range(1, 13) if (year, m) in pts]
    if len(vals) < need:
        return None, len(vals)
    return mean(vals), len(vals)


def latest(pts):
    if not pts:
        return None
    k = max(pts)
    return k, pts[k][0], pts[k][1]


def missing_months(pts, year):
    return [MONTHS[m - 1] for m in range(1, 13) if (year, m) not in pts]


# BLS series plan. Four keyless queries in all; responses cached so reruns cost nothing.
S_PAYROLL = "SMU36935610000000001"   # CES, New York City, total nonfarm, NSA, thousands
S_UR = "LAUCT365100000000003"        # LAUS, New York city, unemployment rate, NSA
S_AHE = "SMU36935610500000003"       # CES, New York City, total private, avg hourly earnings, NSA
S_CPI = "CUURS12ASA0"                # CPI-U, New York-Newark-Jersey City, all items, NSA, 1982-84=100
S_BORO = {name: f"LAUCN{fips}0000000003" for name, fips in BOROUGHS}
NAMED_PEERS_UR = ["Los Angeles", "Chicago", "Houston", "Philadelphia"]
# Fallback county-equivalent series in case LAUS has no city series for these consolidated cities.
FALLBACK_UR = {"Washington, D.C.": "LAUCN110010000000003",
               "Nashville-Davidson": "LAUCN470370000000003",
               "Indianapolis": "LAUCN180970000000003"}


def laus_city_id(c):
    return f"LAUCT{c['geoid']}00000003"


def bls_all(peers):
    """Five keyless v1 queries in all (the first run on 2026-11-16 used exactly five)."""
    core = [S_PAYROLL, S_UR, S_AHE, S_CPI]
    by_name = {c["name"]: c for c in peers["cities"]}
    named = [laus_city_id(by_name[n]) for n in NAMED_PEERS_UR]
    others = [laus_city_id(c) for c in peers["cities"]
              if c["name"] != "New York" and c["name"] not in NAMED_PEERS_UR]
    plan = [(core + named, 2005, 2014, "2005_2014"),
            (core + named, 2015, 2024, "2015_2024"),
            (core + named + others[:12], 2025, 2026, "2025_2026_a"),
            (others[12:] + list(FALLBACK_UR.values()), 2025, 2026, "2025_2026_b"),
            (list(S_BORO.values()), 2017, 2026, "boroughs_2017_2026")]
    data, msgs = {}, []
    for series, a, b, tag in plan:
        d, m = bls_fetch(series, a, b, tag)
        merge(data, d)
        msgs += m
    for s in core + list(S_BORO.values()):
        if not data.get(s):
            raise FetchError(f"BLS returned no data for {s}")
    return data, msgs


# Months BLS never published. October 2025 is absent from LAUS and CPI because data collection
# lapsed during the October-November 2025 federal shutdown. For 2025 only, an average of the
# 11 published months is used and the caveats say so; every other year needs all 12 months.
ALLOWED_GAPS = {(2025, 10)}


def bls_annual(pts, year):
    gaps = [(year, m) for m in range(1, 13) if (year, m) not in pts]
    if not gaps:
        return mean([pts[(year, m)][0] for m in range(1, 13)]), 12
    if all(g in ALLOWED_GAPS for g in gaps):
        vals = [pts[(year, m)][0] for m in range(1, 13) if (year, m) in pts]
        return mean(vals), len(vals)
    return None, 12 - len(gaps)


def bls_series(pts, first, last, digits):
    out, short = [], []
    for y in range(first, last + 1):
        v, n = bls_annual(pts, y)
        if v is None:
            raise FetchError(f"incomplete year {y} ({n} months)")
        out.append({"period": str(y), "value": round(v, digits), "moe": None})
        if n < 12:
            short.append(y)
    return out, short


def latest_extra(pts, digits, note):
    (y, m), v, notes = latest(pts)
    extra = " Preliminary." if "P" in notes else ""
    return {"period": f"{MONTHS[m - 1]} {y}", "value": round(v, digits), "note": note + extra}


def bls_source(series_id, label):
    return {"name": f"Bureau of Labor Statistics, {label}, series {series_id}",
            "url": f"https://data.bls.gov/timeseries/{series_id}",
            "endpoint": BLS_V1 + series_id,
            "fetched": TODAY}


# ----------------------------------------------------------------------------- measures

def build_payroll(bls):
    pts = bls[S_PAYROLL]
    series, short = bls_series(pts, 2005, EDITION_YEAR, 1)
    assert not short, "CES payroll should have all 12 months"
    return {
        "id": "payroll_jobs", "status": "ok", "status_reason": None,
        "name": "Payroll jobs",
        "definition": "Jobs on employer payrolls located in New York City (all five boroughs), total nonfarm, "
                      "annual average of monthly counts, in thousands, not seasonally adjusted.",
        "units": "thousand jobs", "format": "dec1", "better": "up", "frequency": "annual",
        "series": series, "latest_period": str(EDITION_YEAR),
        "latest_extra": latest_extra(pts, 1, "Monthly count in thousands, not seasonally adjusted; compare "
                                              "with the same month a year earlier, not with the annual average."),
        "source": bls_source(S_PAYROLL, "Current Employment Statistics (State and Metro Area), New York City, "
                                        "total nonfarm, not seasonally adjusted"),
        "peers": None, "peer_series": None, "breakdowns": [],
        "method": "Annual value = mean of the 12 monthly not-seasonally-adjusted CES employment levels for "
                  "the calendar year (thousands of jobs), rounded to one decimal. Monthly values come from "
                  "the keyless BLS v1 API, which does not return annual averages.",
        "caveats": [
            "Counts jobs, not people: someone with two jobs counts twice, and the jobs are those located in "
            "New York City, whoever holds them (commuters included). Self-employed workers are not counted.",
            "CES estimates are revised each year when BLS benchmarks them to unemployment-insurance records; "
            "the latest months are preliminary.",
            "Peers left out: CES publishes this city-level definition for New York City, but for most of "
            "the 25 peer cities it publishes only metropolitan-area or county figures, so there is no "
            "same-geography comparison.",
        ],
    }


def build_unemployment(bls, peers, msgs):
    pts = bls[S_UR]
    series, short = bls_series(pts, 2005, EDITION_YEAR, 1)
    by_name = {c["name"]: c for c in peers["cities"]}
    missing_city = {m.split()[-1] for m in msgs if m.startswith("Series does not exist")}
    values, notes = [], []
    for c in peers["cities"]:
        sid = laus_city_id(c)
        geo = f"{c['census_name']}, {c['state']}"
        if sid in missing_city or not bls.get(sid):
            if c["name"] in FALLBACK_UR and bls.get(FALLBACK_UR[c["name"]]):
                sid = FALLBACK_UR[c["name"]]
                county = {"Nashville-Davidson": "Davidson County, Tennessee",
                          "Indianapolis": "Marion County, Indiana",
                          "Washington, D.C.": "District of Columbia"}[c["name"]]
                geo = f"{county} (LAUS county series {sid})"
                notes.append(f"{c['name']}: BLS has no LAUS city series {laus_city_id(c)}, so the "
                             f"county series for {county} is used.")
            else:
                raise FetchError(f"no LAUS series for {c['name']}")
        v, n = bls_annual(bls[sid], EDITION_YEAR)
        if v is None:
            raise FetchError(f"incomplete 2025 for {c['name']}")
        values.append({"city": c["name"], "value": round(v, 1), "moe": None, "geo_name": geo,
                       "series_id": sid})
    peer_series = {}
    for n in NAMED_PEERS_UR:
        s, _ = bls_series(bls[laus_city_id(by_name[n])], 2005, EDITION_YEAR, 1)
        peer_series[n] = [{"period": x["period"], "value": x["value"]} for x in s]
    boro = []
    for name, sid in S_BORO.items():
        v, _ = bls_annual(bls[sid], EDITION_YEAR)
        boro.append({"name": name, "value": round(v, 1), "moe": None})
    nyc_check = [x for x in values if x["city"] == "New York"][0]["value"]
    assert nyc_check == series[-1]["value"]
    return {
        "id": "unemployment_rate", "status": "ok", "status_reason": None,
        "name": "Unemployment rate",
        "definition": "Share of New York City residents in the labor force who are without a job and looking "
                      "for one, annual average, not seasonally adjusted.",
        "units": "percent", "format": "pct1", "better": "down", "frequency": "annual",
        "series": series, "latest_period": str(EDITION_YEAR),
        "latest_extra": latest_extra(pts, 1, "Monthly rate, not seasonally adjusted."),
        "source": bls_source(S_UR, "Local Area Unemployment Statistics, New York city, unemployment rate, "
                                   "not seasonally adjusted"),
        "peers": {
            "period": str(EDITION_YEAR), "geography": "city",
            "note": "LAUS city series (LAUCT + state and place FIPS), 2025 average computed the same way as "
                    "New York's: mean of the published monthly rates (October 2025 was not published). "
                    + " ".join(notes),
            "source": {"name": "Bureau of Labor Statistics, Local Area Unemployment Statistics, city series",
                       "url": "https://www.bls.gov/lau/", "endpoint": BLS_V1, "fetched": TODAY},
            "values": values,
        },
        "peer_series": peer_series,
        "breakdowns": [{"by": "borough", "period": str(EDITION_YEAR),
                        "source_url": "https://data.bls.gov/timeseries/LAUCN360050000000003",
                        "note": "LAUS county series LAUCN<county FIPS>0000000003; 2025 mean of the 11 "
                                "published months.",
                        "values": boro}],
        "method": "Annual value = mean of the monthly not-seasonally-adjusted LAUS unemployment rates for the "
                  "calendar year, rounded to one decimal. The keyless BLS v1 API does not return BLS's own "
                  "annual averages, which BLS computes from annual-average unemployment and labor-force "
                  "levels, so a year here can differ from the published annual average by about 0.1 point. "
                  "Peers and boroughs are computed the same way.",
        "caveats": [
            "BLS published no October 2025 figure for LAUS areas (data collection lapsed during the "
            "October-November 2025 federal shutdown). The 2025 averages for New York, the peers and the "
            "boroughs are the mean of the 11 published months.",
            "Counts residents of the city by where they live, not where they work.",
            "LAUS city and county estimates are model-based and are revised each spring; the latest months "
            "are preliminary.",
        ],
    }


def build_real_ahe(bls):
    ahe, cpi = bls[S_AHE], bls[S_CPI]
    cpi_base, ncpi = bls_annual(cpi, EDITION_YEAR)
    series, nominal = [], []
    for y in range(2007, EDITION_YEAR + 1):
        a, n = bls_annual(ahe, y)
        c, nc = bls_annual(cpi, y)
        if a is None or c is None or n < 12:
            raise FetchError(f"incomplete AHE/CPI year {y}")
        series.append({"period": str(y), "value": round(a * cpi_base / c, 2), "moe": None})
        nominal.append({"period": str(y), "value": round(a, 2)})
    (ly, lm), lv, lnotes = latest(ahe)
    return {
        "id": "real_hourly_earnings", "status": "ok", "status_reason": None,
        "name": "Average hourly earnings after inflation",
        "definition": "Average hourly earnings of all private-sector employees on New York City payrolls, "
                      "annual average, in 2025 dollars (deflated with the New York-area consumer price index).",
        "units": "dollars (2025)", "format": "dec2", "better": "up", "frequency": "annual",
        "series": series, "latest_period": str(EDITION_YEAR),
        "latest_extra": {"period": f"{MONTHS[lm - 1]} {ly}", "value": round(lv, 2),
                         "note": "Monthly figure in current (nominal) dollars, not adjusted for inflation and "
                                 "not seasonally adjusted, so it is not directly comparable to the 2025-dollar "
                                 "annual series." + (" Preliminary." if "P" in lnotes else "")},
        "source": bls_source(S_AHE, "Current Employment Statistics (State and Metro Area), New York City, "
                                    "total private, average hourly earnings of all employees, not seasonally "
                                    "adjusted"),
        "deflator_source": bls_source(S_CPI, "Consumer Price Index for All Urban Consumers (CPI-U), "
                                             "New York-Newark-Jersey City, all items, not seasonally adjusted"),
        "nominal_series": nominal,
        "peers": None, "peer_series": None, "breakdowns": [],
        "method": "AHE_y = mean of the 12 monthly CES average-hourly-earnings values for year y. "
                  "CPI_y = mean of the monthly CPI-U values (CUURS12ASA0) for year y. "
                  "Real value in 2025 dollars = AHE_y x CPI_2025 / CPI_y, rounded to cents. "
                  f"CPI_2025 = {round(cpi_base, 3)} (mean of {ncpi} months). The series starts in 2007, the "
                  "first year CES published this earnings series for New York City.",
        "caveats": [
            "BLS published no October 2025 value for the New York-area CPI (data collection lapsed during "
            "the October-November 2025 federal shutdown), so CPI_2025 is the mean of the 11 published months.",
            "An average across all private jobs: it rises when low-wage jobs disappear (as in 2020) even if "
            "no one's pay went up, so read it alongside the jobs count.",
            "Covers jobs located in the city, whoever holds them; government workers are excluded.",
            "Peers left out: CES earnings series at the city level exist for New York City but not for most "
            "peer cities.",
        ],
    }


# ----------------------------------------------------------------------------- Census BFS

BFS_URL = "https://www.census.gov/econ/bfs/xlsx/bfs_county_apps_annual.xlsx"
COPOP_URL = ("https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/"
             "co-est2025-alldata.csv")
# Principal county for each peer city (the county containing most of the city, or the coterminous
# county for consolidated cities). New York uses the sum of its five counties.
PEER_COUNTY = {
    "Los Angeles": "06037", "Chicago": "17031", "Houston": "48201", "Phoenix": "04013",
    "Philadelphia": "42101", "San Antonio": "48029", "San Diego": "06073", "Dallas": "48113",
    "Fort Worth": "48439", "Jacksonville": "12031", "Austin": "48453", "San Jose": "06085",
    "Charlotte": "37119", "Columbus": "39049", "Indianapolis": "18097", "San Francisco": "06075",
    "Seattle": "53033", "Denver": "08031", "Nashville-Davidson": "47037", "Oklahoma City": "40109",
    "Washington, D.C.": "11001", "El Paso": "48141", "Las Vegas": "32003", "Boston": "25025",
}
COTERMINOUS = {"Philadelphia", "San Francisco", "Denver", "Washington, D.C."}


def read_xlsx_rows(body):
    """Minimal standard-library reader for the first worksheet of an .xlsx file."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    z = zipfile.ZipFile(io.BytesIO(body))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(ns + "si"):
            ss.append("".join(t.text or "" for t in si.iter(ns + "t")))
    rows = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(ns + "row"):
        r = {}
        for c in row.iter(ns + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v, t = c.find(ns + "v"), c.get("t")
            if t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(ns + "t"))
            elif v is None:
                val = None
            elif t == "s":
                val = ss[int(v.text)]
            else:
                val = v.text
            r[col] = val
        rows.append(r)
    return rows


def build_business_apps(peers):
    body = cached_download(BFS_URL, "bfs_county_apps_annual.xlsx", lambda b: b[:2] == b"PK")
    rows = read_xlsx_rows(body)
    hdr_i = next(i for i, r in enumerate(rows) if r.get("C") == "County Code")
    hdr = rows[hdr_i]
    col = {v: k for k, v in hdr.items() if v}
    years = sorted(int(v[2:]) for v in col if re.fullmatch(r"BA\d{4}", v or ""))
    county = {}
    for r in rows[hdr_i + 1:]:
        code = r.get("C")
        if code and re.fullmatch(r"\d{5}", code):
            county[code] = {"name": f"{r.get('B')}, {r.get('A')}",
                            "ba": {y: r.get(col[f"BA{y}"]) for y in years}}
    if len(county) < 3000:
        raise FetchError(f"BFS county file has only {len(county)} counties")

    def val(code, y):
        v = county[code]["ba"][y]
        if v in (None, "", "S", "D", "(S)", "(D)"):
            raise FetchError(f"BFS value missing for {code} {y}: {v!r}")
        return int(float(v))

    series = [{"period": str(y), "value": sum(val(c, y) for c in NYC_COUNTIES), "moe": None}
              for y in years if 2005 <= y <= EDITION_YEAR]
    if series[-1]["period"] != str(EDITION_YEAR):
        raise FetchError("BFS county file does not reach 2025")

    pop_body = cached_download(COPOP_URL, "co-est2025-alldata.csv", lambda b: b"POPESTIMATE2025" in b[:2000])
    pop, cname = {}, {}
    for r in csv.DictReader(io.StringIO(pop_body.decode("latin-1"))):
        if r["SUMLEV"] == "050":
            code = r["STATE"] + r["COUNTY"]
            pop[code] = int(r["POPESTIMATE2025"])
            cname[code] = f"{r['CTYNAME']}, {r['STNAME']}"
    values = []
    nyc_pop = sum(pop[c] for c in NYC_COUNTIES)
    nyc_apps = sum(val(c, EDITION_YEAR) for c in NYC_COUNTIES)
    values.append({"city": "New York", "value": round(nyc_apps / nyc_pop * 1000, 2), "moe": None,
                   "geo_name": "Bronx, Kings, New York, Queens and Richmond counties, New York (sum)",
                   "applications": nyc_apps, "population_2025": nyc_pop})
    for c in peers["cities"]:
        if c["name"] == "New York":
            continue
        code = PEER_COUNTY[c["name"]]
        a = val(code, EDITION_YEAR)
        values.append({"city": c["name"], "value": round(a / pop[code] * 1000, 2), "moe": None,
                       "geo_name": cname[code], "applications": a, "population_2025": pop[code]})
    boro = [{"name": n, "value": val(f, EDITION_YEAR), "moe": None} for n, f in BOROUGHS]
    return {
        "id": "business_applications", "status": "ok", "status_reason": None,
        "name": "New business applications",
        "definition": "Applications for a new employer identification number (EIN) filed with the IRS for "
                      "businesses located in New York City's five counties, calendar year.",
        "units": "count", "format": "int", "better": "up", "frequency": "annual",
        "series": series, "latest_period": str(EDITION_YEAR), "latest_extra": None,
        "source": {"name": "Census Bureau, Business Formation Statistics, county-level annual business "
                           "applications (bfs_county_apps_annual.xlsx)",
                   "url": "https://www.census.gov/econ/bfs/data/county.html",
                   "endpoint": BFS_URL, "fetched": TODAY},
        "peers": {
            "period": str(EDITION_YEAR), "geography": "county",
            "note": "Business applications per 1,000 residents, measured for each peer city's principal "
                    "county because BFS publishes no city-level data. Coterminous with the city only for "
                    "Philadelphia, San Francisco, Denver and Washington; Jacksonville, Indianapolis and "
                    "Nashville are consolidated with most of their county; for the others the county is much "
                    "larger than the city (Los Angeles, Cook, Harris, Maricopa, King, Clark counties and so "
                    "on). New York is the sum of its five counties. Denominator: Census Vintage 2025 county "
                    "population estimates for July 1, 2025. Unit differs from the citywide series (a count).",
            "source": {"name": "Census Bureau, Business Formation Statistics (county annual) and Vintage 2025 "
                               "county population estimates",
                       "url": "https://www.census.gov/econ/bfs/data/county.html",
                       "endpoint": BFS_URL + " ; " + COPOP_URL, "fetched": TODAY},
            "values": values,
        },
        "peer_series": None,
        "breakdowns": [{"by": "borough", "period": str(EDITION_YEAR),
                        "source_url": "https://www.census.gov/econ/bfs/data/county.html",
                        "values": boro}],
        "method": "Citywide value = sum of the BA (business applications) columns for counties 36005, 36047, "
                  "36061, 36081 and 36085 in the Census county-level annual BFS file. Peer value = 2025 "
                  "applications in the principal county / Vintage 2025 July 1 population x 1,000.",
        "caveats": [
            "An application for an EIN is not a business opening: many applications never become businesses "
            "with employees, and the count includes sole proprietors, holding companies and other entities.",
            "Applications are placed in a county from the address on the application, which may not be "
            "where the business actually operates.",
            "Applications jumped in 2020 and 2021 and have stayed well above pre-2020 levels; the county "
            "file does not show how many of them became operating businesses.",
        ],
    }


# ----------------------------------------------------------------------------- Zillow ZORI

ZORI_URL = "https://files.zillowstatic.com/research/public_csvs/zori/City_zori_uc_sfrcondomfr_sm_month.csv"
STATE_ABBR = {"New York": "NY", "California": "CA", "Illinois": "IL", "Texas": "TX", "Arizona": "AZ",
              "Pennsylvania": "PA", "Florida": "FL", "North Carolina": "NC", "Ohio": "OH", "Indiana": "IN",
              "Washington": "WA", "Colorado": "CO", "Tennessee": "TN", "Oklahoma": "OK",
              "District of Columbia": "DC", "Nevada": "NV", "Massachusetts": "MA"}
ZILLOW_NAME = {"Nashville-Davidson": "Nashville", "Washington, D.C.": "Washington"}


def build_asking_rent(peers):
    body = cached_download(ZORI_URL, "City_zori_uc_sfrcondomfr_sm_month.csv",
                           lambda b: b.startswith(b"RegionID") or b[:3] == b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    if len(rows) < 1000:
        raise FetchError(f"ZORI city file has only {len(rows)} rows")
    months = [k for k in rows[0] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k)]

    def find(c):
        name = ZILLOW_NAME.get(c["name"], c["name"])
        hits = [r for r in rows if r["RegionName"] == name and r["State"] == STATE_ABBR[c["state"]]
                and r["RegionType"] == "city"]
        if len(hits) != 1:
            raise FetchError(f"ZORI match for {c['name']}: {len(hits)} rows")
        return hits[0]

    gaps = []

    def yearly(r, y, min_months=12):
        ms = [m for m in months if m.startswith(f"{y}-")]
        vals = [float(r[m]) for m in ms if r[m] not in ("", None)]
        if len(vals) < min_months or not vals:
            return None
        if len(vals) < len(ms):
            gaps.append((r["RegionName"], r["State"], [m[:7] for m in ms if r[m] in ("", None)]))
        return mean(vals)

    by_name = {c["name"]: c for c in peers["cities"]}
    nyc = find(by_name["New York"])
    series = []
    for y in range(2015, EDITION_YEAR + 1):
        v = yearly(nyc, y, min_months=11)   # Zillow leaves September 2020 blank for New York
        if v is None:
            raise FetchError(f"ZORI New York incomplete for {y}")
        series.append({"period": str(y), "value": round(v), "moe": None})
    last_m = max(m for m in months if nyc[m] not in ("", None))
    ly, lm = int(last_m[:4]), int(last_m[5:7])
    values = []
    for c in peers["cities"]:
        r = find(c)
        v = yearly(r, EDITION_YEAR)
        if v is None:
            raise FetchError(f"ZORI 2025 incomplete for {c['name']}")
        values.append({"city": c["name"], "value": round(v), "moe": None,
                       "geo_name": f"{r['RegionName']}, {r['State']} (Zillow RegionID {r['RegionID']}; "
                                   f"county field: {r['CountyName']})"})
    nyc_gaps = [g for g in gaps if g[0] == "New York"]
    peer_series = {}
    for n in NAMED_PEERS_UR:
        r = find(by_name[n])
        peer_series[n] = [{"period": str(y), "value": round(yearly(r, y))}
                          for y in range(2015, EDITION_YEAR + 1) if yearly(r, y) is not None]
    gap_note = ("; ".join(f"{g[0]}, {g[1]}: blank {', '.join(g[2])}" for g in nyc_gaps) or "none")
    return {
        "id": "asking_rent", "status": "ok", "status_reason": None,
        "name": "Typical asking rent",
        "definition": "Zillow Observed Rent Index for New York City: the typical asking rent for homes and "
                      "apartments listed for rent, all homes plus multifamily, smoothed, annual average of "
                      "monthly values, in current dollars.",
        "units": "dollars per month", "format": "usd0", "better": "down", "frequency": "annual",
        "series": series, "latest_period": str(EDITION_YEAR),
        "latest_extra": {"period": f"{MONTHS[lm - 1]} {ly}", "value": round(float(nyc[last_m])),
                         "note": "Monthly index value (smoothed), current dollars."},
        "source": {"name": "Zillow Research, Zillow Observed Rent Index (ZORI), city level, all homes plus "
                           "multifamily, smoothed, monthly (City_zori_uc_sfrcondomfr_sm_month.csv)",
                   "url": "https://www.zillow.com/research/data/", "endpoint": ZORI_URL, "fetched": TODAY},
        "peers": {
            "period": str(EDITION_YEAR), "geography": "city",
            "note": "Zillow city regions matched on RegionName plus State. Nashville-Davidson is Zillow's "
                    "\"Nashville, TN\" and Washington, D.C. is Zillow's \"Washington, DC\"; Zillow's city "
                    "boundaries are its own and may not match Census place boundaries exactly.",
            "source": {"name": "Zillow Research, ZORI city file", "url": "https://www.zillow.com/research/data/",
                       "endpoint": ZORI_URL, "fetched": TODAY},
            "values": values,
        },
        "peer_series": peer_series,
        "breakdowns": [],
        "method": "Annual value = mean of the 12 monthly ZORI values for the calendar year (Zillow labels each "
                  "month by its last day), rounded to whole dollars. Not adjusted for inflation. Where Zillow "
                  "leaves a month blank, the year is the mean of the months it published (listed in caveats); "
                  "no month is filled in. Peer 2025 values require all 12 months.",
        "caveats": [
            "Measures asking rents on units listed for rent, not what sitting tenants pay, so it moves "
            "faster than rents across the whole housing stock (including rent-stabilized leases).",
            "Zillow revises past values when it updates the index, so earlier years can change between "
            "downloads.",
            "In current dollars: some of the rise over time is general inflation.",
            "Months Zillow leaves blank in the New York series, averaged over the remaining months of "
            "that year rather than filled in: " + gap_note + ".",
        ],
    }


# ----------------------------------------------------------------------------- Poverty Tracker

# Values transcribed by hand from Figure 1.1 ("Overall poverty rates in New York City and nationally
# (2015-2024)"), printed page 9 (viewer page 11 of 58) of "The State of Poverty and Disadvantage in
# New York City, Vol. 8" (Robin Hood and Columbia Center on Poverty and Social Policy, released
# March 16, 2026), opened on 2026-11-16 in the publisher's FlippingBook viewer. The report gives
# whole percentages only. Vols. 6 and 7 (PDFs below, Figure 1.1, printed page 9 = PDF page 11) show
# the same values for every year they cover. If a new volume is released, re-read it and update this table.
PT_VALUES = [(2015, 22), (2016, 22), (2017, 21), (2018, 20), (2019, 19), (2020, 17), (2021, 18),
             (2022, 23), (2023, 25), (2024, 26)]
PT_VOL8_VIEWER = "https://online.flippingbook.com/view/1056294867/"
PT_VOL8_PAGE = "https://robinhood.org/reports/poverty-tracker-annual-report-vol-8/"
PT_PDFS = [
    ("https://robinhood.org/wp-content/uploads/2025/02/PT_Annual24_final_digital.pdf",
     "poverty_tracker/PT_Annual24_final_digital.pdf"),          # Vol. 7, data through 2023
    ("https://robinhood.org/wp-content/uploads/2024/02/Annual-Poverty-Tracker-Report-2024.pdf",
     "poverty_tracker/Annual-Poverty-Tracker-Report-2024.pdf"),  # Vol. 6, data through 2022
]
NYCGOV_BRIEF = "https://www.nyc.gov/assets/opportunity/pdf/MOE-2022-Poverty-Measure-Comprehensive-Brief.pdf"


def build_poverty_tracker():
    hashes = {}
    for url, name in PT_PDFS + [(NYCGOV_BRIEF, "poverty_tracker/MOE-2022-Poverty-Measure-Comprehensive-Brief.pdf")]:
        b = cached_download(url, name, lambda b: b[:5] == b"%PDF-")
        hashes[name] = sha256(b)
    viewer = cached_download(PT_VOL8_VIEWER, "poverty_tracker/vol8_flippingbook_viewer.html",
                             lambda b: b"State of Poverty and Disadvantage in NYC Vol.8" in b)
    series = [{"period": str(y), "value": float(v), "moe": None} for y, v in PT_VALUES]
    return {
        "id": "poverty_tracker_rate", "status": "partial",
        "status_reason": "Values exist for 2015-2024 only and 2025 is not yet published. The publisher "
                         "warns that pre-2020 rates are not directly comparable with 2020 onward (a sampling "
                         "change), so the five-year comparison straddles a break in the series. Values are "
                         "whole percentages read from the report's chart labels; no table or margin of "
                         "error is published.",
        "name": "Poverty rate counting New York costs",
        "definition": "Share of New Yorkers whose family resources (after taxes and benefits, minus "
                      "necessary expenses) fall below a poverty line adjusted for New York City housing "
                      "costs, from the Poverty Tracker survey's Supplemental Poverty Measure.",
        "units": "percent", "format": "pct0", "better": "down", "frequency": "annual",
        "series": series, "latest_period": "2024", "latest_extra": None,
        "source": {"name": "Robin Hood and Columbia University Center on Poverty and Social Policy, The State "
                           "of Poverty and Disadvantage in New York City, Vol. 8 (March 2026), Figure 1.1, p. 9",
                   "url": PT_VOL8_PAGE, "endpoint": PT_VOL8_VIEWER, "fetched": TODAY},
        "source_documents": [
            {"volume": 8, "data_through": 2024, "url": PT_VOL8_VIEWER,
             "location": "Figure 1.1, printed page 9 (viewer page 11 of 58)",
             "used_for": "all values 2015-2024",
             "note": "Published only as a FlippingBook viewer (the PDF download asks for an email); the "
                     "viewer page is cached as a marker, the values were read from the rendered page."},
            {"volume": 7, "data_through": 2023, "url": PT_PDFS[0][0],
             "location": "Figure 1.1, printed page 9 (PDF page 11)", "sha256": hashes[PT_PDFS[0][1]],
             "used_for": "cross-check: 2015-2023 identical to Vol. 8"},
            {"volume": 6, "data_through": 2022, "url": PT_PDFS[1][0],
             "location": "Figure 1.1, printed page 9 (PDF page 11)", "sha256": hashes[PT_PDFS[1][1]],
             "used_for": "cross-check: 2015-2022 identical to Vol. 8"},
        ],
        "peers": None, "peer_series": None, "breakdowns": [],
        "method": "No computation. Each annual value is the New York City data label on Figure 1.1 of Vol. 8, "
                  "page 9, which states: More than 1 in 4 (26%) New Yorkers lived in poverty in 2024, up from "
                  "25% the year prior. The 2015-2023 labels match Vol. 7 (Figure 1.1, p. 9) and 2015-2022 "
                  "match Vol. 6 (Figure 1.1, p. 9).",
        "caveats": [
            "Vol. 8, Figure 1.1 note: in 2020 the Poverty Tracker sampling design changed to add an "
            "oversample of New Yorkers of Chinese descent, so pre-2020 results are not directly comparable "
            "with 2020 onward (the report draws a dashed line between 2019 and 2020).",
            "Vol. 8 says its 2023 rates differ slightly from those in Vol. 7 because of a change in the "
            "2023 sample composition; the rounded citywide 2023 figure (25%) is the same in both.",
            "Survey-based estimate with sampling error; the reports publish no margin of error for the "
            "citywide rate, and values are rounded to whole percentages.",
            "Context, not part of this series: the city's own NYCgov poverty measure (Mayor's Office for "
            "Economic Opportunity) was 20.5% for 2022, its latest published year, in \"New York City "
            "Government Poverty Measure 2022: Comprehensive Brief\" (July 2025), Table 1, p. 9. It uses "
            "American Community Survey data and a different method, so it is not comparable with the "
            "Poverty Tracker rate.",
            "No peers: the Poverty Tracker covers New York City only.",
        ],
    }


# ----------------------------------------------------------------------------- main

def main():
    os.makedirs(RAW, exist_ok=True)
    peers = load_json(os.path.join(ROOT, "data", "peers.json"))
    names = {c["name"] for c in peers["cities"]}
    assert set(PEER_COUNTY) | {"New York"} == names, "peer county map out of sync with peers.json"
    bls, msgs = bls_all(peers)
    out = [build_payroll(bls), build_unemployment(bls, peers, msgs), build_real_ahe(bls),
           build_business_apps(peers), build_poverty_tracker(), build_asking_rent(peers)]
    for o in out:
        if not o["series"]:
            raise FetchError(f"empty series for {o['id']}")
        if o["peers"]:
            got = {v["city"] for v in o["peers"]["values"]}
            if got != names:
                raise FetchError(f"{o['id']}: peers missing {sorted(names - got)}")
        write_indicator(o)
    print(f"BLS queries sent this run: {BLS_QUERIES_LIVE} (cached responses reused otherwise)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"economy fetch FAILED: {e}", file=sys.stderr)
        sys.exit(1)
