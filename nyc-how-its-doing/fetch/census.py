#!/usr/bin/env python3
"""Census group fetcher for "How New York Is Doing" (edition: New York in 2025).

Run from the project folder:  python3 -I fetch/census.py
Options:  --refresh  re-download everything, ignoring the cache
          --offline  use only files already in data/raw/census/ (fails if one is missing)

By default a raw file younger than 7 days is reused, so reruns do not hammer the
Census and BLS servers (the keyless BLS v1 API allows 25 requests a day).

Sources:
  * Census Bureau population estimates (PEP): city totals (Vintage 2025 and the
    2010-2020 intercensal file) and county components of change (Vintages 2025 and 2020).
  * American Community Survey 1-year detailed tables through api.census.gov.
  * BLS CPI-U, New York-Newark-Jersey City, all items (CUURS12ASA0), to put incomes
    in 2025 dollars.

The Census API key is read from the macOS keychain and is never printed or written out.
"""
import csv
import datetime
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "census")
IND = os.path.join(ROOT, "data", "indicators")
TODAY = datetime.date.today().isoformat()
UA = "Mozilla/5.0 (compatible; civic-data-fetcher/1.0)"
REFRESH = "--refresh" in sys.argv
OFFLINE = "--offline" in sys.argv
MAX_AGE = 7 * 86400

ACS_YEARS = [y for y in range(2005, 2026) if y != 2020]
LATEST = 2025
NAMED = ["Los Angeles", "Chicago", "Houston", "Philadelphia"]
NYC_COUNTIES = [("005", "Bronx"), ("047", "Brooklyn"), ("061", "Manhattan"),
                ("081", "Queens"), ("085", "Staten Island")]
NYC_COUNTY_NAMES = {"005": "Bronx County", "047": "Kings County", "061": "New York County",
                    "081": "Queens County", "085": "Richmond County"}

# Principal county of each peer city (state FIPS, county FIPS, expected county name).
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

URL_SUB2025 = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/cities/totals/sub-est2025.csv"
URL_SUBINT = "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/intercensal/cities/sub-est2020int.csv"
URL_CO2025 = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv"
URL_CO2020 = "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/counties/totals/co-est2020-alldata.csv"
URL_BLS = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
CPI_SERIES = "CUURS12ASA0"


class FetchError(RuntimeError):
    pass


# ---------------------------------------------------------------- plumbing

def census_key():
    r = subprocess.run(["security", "find-generic-password", "-s", "CENSUS_API_KEY", "-w"],
                       capture_output=True, text=True)
    k = r.stdout.strip()
    if r.returncode != 0 or not k:
        raise FetchError("Census API key not found in keychain (service CENSUS_API_KEY)")
    return k


_KEY = None


def key():
    global _KEY
    if _KEY is None:
        _KEY = census_key()
    return _KEY


def redact(url):
    return url.split("&key=")[0].split("?key=")[0]


def http(url, data=None, headers=None, allow_404=False):
    """GET (or POST when data is given). Returns bytes, or None on 404 when allow_404."""
    if OFFLINE:
        raise FetchError("offline mode, but a download was needed: " + redact(url))
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
                if resp.status == 204 or not body:
                    raise FetchError("empty response from " + redact(url))
                return body
        except urllib.error.HTTPError as e:
            if e.code == 404 and allow_404:
                return None
            last = "HTTP %s" % e.code
            if e.code in (400, 404):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = type(e).__name__
        time.sleep(2 * (attempt + 1))
    raise FetchError("download failed (%s): %s" % (last, redact(url)))


def fresh(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    if OFFLINE:
        return True
    if REFRESH:
        return False
    return time.time() - os.path.getmtime(path) < MAX_AGE


def write_bytes(path, b):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(b)
    os.replace(tmp, path)


def download_file(url, path, min_bytes=1000):
    if fresh(path):
        return path
    b = http(url)
    if len(b) < min_bytes:
        raise FetchError("suspiciously small download (%d bytes): %s" % (len(b), url))
    write_bytes(path, b)
    return path


def read_csv(path):
    with open(path, encoding="latin-1", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise FetchError("no rows in " + path)
    return rows


# ---------------------------------------------------------------- ACS helpers

def acs_url(year, dataset="acs/acs1"):
    return "https://api.census.gov/data/%d/%s" % (year, dataset)


def group_meta(year, table, dataset="acs/acs1"):
    """{var_base: normalized label path} for the estimate variables of a table, or None if
    the table does not exist in that year's 1-year release."""
    path = os.path.join(RAW, "meta", "%d_%s.json" % (year, table))
    if fresh(path):
        with open(path) as f:
            d = json.load(f)
    else:
        b = http(acs_url(year, dataset) + "/groups/%s.json" % table, allow_404=True)
        if b is None or not b.lstrip().startswith(b"{"):
            d = {"missing": True}
        else:
            d = json.loads(b)
            if not d.get("variables"):
                raise FetchError("empty metadata for %s %d" % (table, year))
            # keep only estimate labels; the full group files are large
            d = {"variables": {k: {"label": v["label"]} for k, v in d["variables"].items()
                               if k.endswith("E") and k.startswith(table + "_")}}
        write_bytes(path, json.dumps(d).encode())
    if d.get("missing"):
        return None
    out = {}
    for k, v in d["variables"].items():
        if k.endswith("E") and k.startswith(table + "_"):
            out[k[:-1]] = norm(v["label"])
    if not out:
        raise FetchError("no estimate variables for %s %d" % (table, year))
    return out


def norm(label):
    parts = [p.strip().rstrip(":").strip().lower().replace("foreign-born", "foreign born")
             for p in label.split("!!")]
    return tuple(p for p in parts if p != "estimate")


def find(meta, *path):
    hits = [k for k, p in meta.items() if p == tuple(path)]
    if len(hits) != 1:
        raise FetchError("label %r matched %d variables" % (path, len(hits)))
    return hits[0]


def find_prefix(meta, prefix, length=1):
    hits = [k for k, p in meta.items() if len(p) == length and p[0].startswith(prefix)]
    if len(hits) != 1:
        raise FetchError("label prefix %r matched %d variables" % (prefix, len(hits)))
    return hits[0]


def acs_rows(year, bases, geo_for, geo_in, tag, dataset="acs/acs1"):
    """Fetch E and M for the variable bases. Returns list of dicts. Cached per year/tag and
    re-fetched if the cached file lacks any requested variable."""
    path = os.path.join(RAW, "%s_%d_%s.json" % (dataset.replace("acs/", "").replace("/", "_"), year, tag))
    want = sorted(set(b + s for b in bases for s in ("E", "M")))
    if fresh(path):
        with open(path) as f:
            cached = json.load(f)
        if set(want) <= set(cached["vars"]):
            return cached["rows"]
    merged = {}
    geo_cols = None
    for i in range(0, len(want), 48):
        chunk = want[i:i + 48]
        q = {"get": ",".join(["NAME"] + chunk), "for": geo_for}
        if geo_in:
            q["in"] = geo_in
        url = acs_url(year, dataset) + "?" + urllib.parse.urlencode(q, safe=":,*") + "&key=" + key()
        data = json.loads(http(url))
        if len(data) < 2:
            raise FetchError("no rows: %s %d %s" % (tag, year, geo_for))
        hdr = data[0]
        geo_cols = [c for c in hdr if c not in chunk and c != "NAME"]
        for r in data[1:]:
            rec = dict(zip(hdr, r))
            gk = tuple(rec[c] for c in geo_cols)
            merged.setdefault(gk, {}).update(rec)
    rows = list(merged.values())
    if not rows:
        raise FetchError("no rows: %s %d" % (tag, year))
    write_bytes(path, json.dumps({"vars": want, "source": acs_url(year, dataset), "for": geo_for,
                                  "in": geo_in, "rows": rows}).encode())
    return rows


def est(row, base):
    s = row.get(base + "E")
    if s is None or s == "":
        return None
    v = float(s)
    return None if v <= -100000000 else v


def moe(row, base):
    s = row.get(base + "M")
    if s is None or s == "":
        return None
    v = float(s)
    if v == -555555555:   # estimate is controlled: no sampling error
        return 0.0
    return None if v < 0 else v


def total(row, bases):
    vals = [est(row, b) for b in bases]
    if any(v is None for v in vals):
        return None, None
    ms = [moe(row, b) for b in bases]
    m = None if any(x is None for x in ms) else math.sqrt(sum(x * x for x in ms))
    return sum(vals), m


def proportion(x, mx, y, my):
    """Share x/y as a percent, with the ACS handbook MOE formula for proportions."""
    if x is None or y in (None, 0):
        return None, None
    p = x / y
    if mx is None or my is None:
        return 100 * p, None
    rad = mx * mx - p * p * my * my
    if rad < 0:   # handbook: fall back to the ratio formula
        rad = mx * mx + p * p * my * my
    return 100 * p, 100 * math.sqrt(rad) / y


def ratio(x, mx, y, my):
    if x is None or y in (None, 0):
        return None, None
    r = x / y
    if mx is None or my is None:
        return r, None
    return r, math.sqrt(mx * mx + r * r * my * my) / y


# ---------------------------------------------------------------- ACS measure definitions
# Each resolver takes {table: meta} and returns a dict of variable lists; compute() turns a
# row plus that dict into (value, moe).

PRIME_BANDS = ["25 to 29 years", "30 to 34 years", "35 to 44 years", "45 to 54 years"]


def r_foreign(m):
    t = m["B05002"]
    return {"num": [find(t, "total", "foreign born")], "den": [find(t, "total")]}


def r_prime(m, sexes=("male", "female")):
    t = m["B23001"]
    num, den = [], []
    for s in sexes:
        for b in PRIME_BANDS:
            den.append(find(t, "total", s, b))
            num.append(find(t, "total", s, b, "in labor force", "in armed forces"))
            num.append(find(t, "total", s, b, "in labor force", "civilian", "employed"))
    return {"num": num, "den": den}


def r_mhi(m):
    return {"val": [find_prefix(m["B19013"], "median household income")]}


def r_poverty(m, t="B17001"):
    g = m[t]
    return {"num": [find(g, "total", "income in the past 12 months below poverty level")],
            "den": [find(g, "total")]}


def r_gini(m):
    return {"val": [find_prefix(m["B19083"], "gini index")]}


def r_rent(m):
    t = m["B25070"]
    return {"num": [find(t, "total", "50.0 percent or more")], "den": [find(t, "total")],
            "minus": [find(t, "total", "not computed")]}


def r_uninsured(m, t="B27001"):
    """All 'No health insurance coverage' cells. The table's age/sex detail changed over the
    years (2008 has three age groups, later years 18 sex-by-age cells), so match by label and
    check that every 'no coverage' cell has a matching 'with coverage' sibling."""
    g = m[t]
    num = sorted(k for k, p in g.items() if p[-1] == "no health insurance coverage")
    wth = sorted(k for k, p in g.items() if p[-1] == "with health insurance coverage")
    if len(num) < 3 or len(num) != len(wth):
        raise FetchError("%s: unexpected structure (%d no-coverage, %d with-coverage cells)" % (t, len(num), len(wth)))
    return {"num": num, "den": [find(g, "total")]}


def r_commute(m):
    return {"num": [find_prefix(m["B08013"], "aggregate travel time to work")],
            "den": [find(m["B08134"], "total")]}


def c_pct(row, v):
    x, mx = total(row, v["num"])
    y, my = total(row, v["den"])
    if "minus" in v and y is not None:
        z, mz = total(row, v["minus"])
        if z is None:
            return None, None
        y = y - z
        my = None if (my is None or mz is None) else math.sqrt(my * my + mz * mz)
    return proportion(x, mx, y, my)


def c_val(row, v):
    return est(row, v["val"][0]), moe(row, v["val"][0])


def c_ratio(row, v):
    x, mx = total(row, v["num"])
    y, my = total(row, v["den"])
    return ratio(x, mx, y, my)


ACS = {
    "foreign_born_share": dict(tables=["B05002"], resolve=r_foreign, compute=c_pct, nd=2),
    "prime_age_employment": dict(tables=["B23001"], resolve=r_prime, compute=c_pct, nd=2),
    "median_household_income": dict(tables=["B19013"], resolve=r_mhi, compute=c_val, nd=0),
    "poverty_rate": dict(tables=["B17001"], resolve=r_poverty, compute=c_pct, nd=2),
    "gini_index": dict(tables=["B19083"], resolve=r_gini, compute=c_val, nd=4),
    "severe_rent_burden": dict(tables=["B25070"], resolve=r_rent, compute=c_pct, nd=2),
    "uninsured_rate": dict(tables=["B27001"], resolve=r_uninsured, compute=c_pct, nd=2),
    "commute_time": dict(tables=["B08013", "B08134"], resolve=r_commute, compute=c_ratio, nd=2),
}


# Published subject-table equivalents (2010 onward). Where the published estimate matches the
# value computed from the detailed table, its published margin of error replaces the derived one.
SUBJECT = {
    "poverty_rate": ("S1701", lambda p: p == ("percent below poverty level", "population for whom poverty status is determined")),
    "uninsured_rate": ("S2701", lambda p: len(p) == 2 and p[0] == "percent uninsured" and
                       p[1] in ("civilian noninstitutionalized population", "total civilian noninstitutionalized population")),
    "commute_time": ("S0801", lambda p: p[0] == "total" and p[-1] == "mean travel time to work (minutes)"
                     and "travel time to work" in p),
}


def subject_vars(year):
    out = {}
    for mid, (t, match) in SUBJECT.items():
        meta = group_meta(year, t, "acs/acs1/subject")
        if meta is None:
            continue
        hits = [k for k, p in meta.items() if match(p)]
        if len(hits) != 1:
            raise FetchError("%s %d: %d matching subject variables" % (t, year, len(hits)))
        out[mid] = hits[0]
    return out


def rnd(x, nd):
    if x is None:
        return None
    return int(round(x)) if nd == 0 else round(x, nd)


# ---------------------------------------------------------------- CPI

def cpi_annual():
    path = os.path.join(RAW, "bls_%s.json" % CPI_SERIES)
    if fresh(path):
        with open(path) as f:
            raw = json.load(f)
    else:
        raw = []
        for a, b in [(2005, 2014), (2015, 2024), (2025, 2025)]:
            payload = json.dumps({"seriesid": [CPI_SERIES], "startyear": str(a), "endyear": str(b)}).encode()
            d = json.loads(http(URL_BLS, data=payload, headers={"Content-Type": "application/json"}))
            if d.get("status") != "REQUEST_SUCCEEDED":
                raise FetchError("BLS request failed: %s" % d.get("message"))
            data = d["Results"]["series"][0]["data"]
            if not data:
                raise FetchError("BLS returned no data for %d-%d" % (a, b))
            raw.extend(data)
        write_bytes(path, json.dumps(raw).encode())
    months = {}
    for r in raw:
        if r["period"].startswith("M") and r["period"] != "M13":
            try:
                v = float(r["value"])
            except ValueError:
                continue   # "-" = not published
            months.setdefault(int(r["year"]), {})[r["period"]] = v
    out, missing = {}, {}
    for y in range(2005, 2026):
        ms = months.get(y, {})
        if len(ms) < 11:
            raise FetchError("CPI %d has only %d months" % (y, len(ms)))
        out[y] = sum(ms.values()) / len(ms)
        gone = sorted(set("M%02d" % i for i in range(1, 13)) - set(ms))
        if gone:
            missing[y] = gone
    return out, missing


# ---------------------------------------------------------------- output helpers

def load_json(p):
    with open(p) as f:
        return json.load(f)


PEERS = load_json(os.path.join(ROOT, "data", "peers.json"))["cities"]
REGISTRY = {m["id"]: m for m in load_json(os.path.join(ROOT, "data", "registry.json"))["measures"]}


def write_indicator(d):
    reg = REGISTRY[d["id"]]
    assert reg["group"] == "census", d["id"]
    d["name"] = reg["name"]
    d["better"] = reg["better"]
    if d["status"] == "ok" and not d["series"]:
        raise FetchError("refusing to write empty series for " + d["id"])
    order = ["id", "status", "status_reason", "name", "definition", "units", "format", "better",
             "frequency", "series", "latest_period", "latest_extra", "source", "peers", "peer_series",
             "breakdowns", "method", "caveats"]
    out = {k: d.get(k) for k in order}
    for k in d:
        if k not in out:
            out[k] = d[k]
    os.makedirs(IND, exist_ok=True)
    path = os.path.join(IND, d["id"] + ".json")
    with open(path + ".tmp", "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(path + ".tmp", path)
    print("wrote", os.path.relpath(path, ROOT), "-", len(out["series"]), "years, latest",
          out["latest_period"], "=", out["series"][-1]["value"] if out["series"] else None)


def dc_table(year, table, geo=None):
    u = "https://data.census.gov/table/ACSDT1Y%d.%s" % (year, table)
    return u + ("?g=" + geo if geo else "")


NYC_G = "160XX00US3651000"
BORO_G = "050XX00US36005,36047,36061,36081,36085"


# ---------------------------------------------------------------- population (PEP)

def population():
    sub25_path = os.path.join(ROOT, "data", "raw", "pep", "sub-est2025.csv")
    if not os.path.exists(sub25_path):
        sub25_path = download_file(URL_SUB2025, os.path.join(RAW, "sub-est2025.csv"), 1000000)
    subint = download_file(URL_SUBINT, os.path.join(RAW, "sub-est2020int.csv"), 1000000)
    co25 = read_csv(download_file(URL_CO2025, os.path.join(RAW, "co-est2025-alldata.csv"), 100000))
    s25 = {(r["STATE"], r["PLACE"]): r for r in read_csv(sub25_path) if r["SUMLEV"] == "162"}
    sint = {(r["STATE"], r["PLACE"]): r for r in read_csv(subint) if r["SUMLEV"] == "162"}

    def series_for(sf, pf):
        a, b = sint.get((sf, pf)), s25.get((sf, pf))
        if a is None or b is None:
            raise FetchError("population: place %s%s missing from a file" % (sf, pf))
        out = [{"period": str(y), "value": int(a["POPESTIMATE%d" % y]), "moe": None,
                "vintage": "2010-2020 intercensal"} for y in range(2010, 2020)]
        out += [{"period": str(y), "value": int(b["POPESTIMATE%d" % y]), "moe": None,
                 "vintage": "Vintage 2025"} for y in range(2020, 2026)]
        return out

    nyc = series_for("36", "51000")
    if s25[("36", "51000")]["NAME"] != "New York city":
        raise FetchError("population: NYC row name mismatch")
    intercensal_2020 = int(sint[("36", "51000")]["CENSUS2020POP"])
    v25_base = int(s25[("36", "51000")]["ESTIMATESBASE2020"])

    pvals = []
    for c in PEERS:
        r = s25.get((c["state_fips"], c["place_fips"]))
        if r is None or r["NAME"] != c["census_name"]:
            raise FetchError("population peer mismatch: " + c["name"])
        p20, p25 = int(r["POPESTIMATE2020"]), int(r["POPESTIMATE2025"])
        pvals.append({"city": c["name"], "value": round((p25 - p20) / p20 * 100, 2), "moe": None,
                      "pop_2020": p20, "pop_2025": p25,
                      "geo_name": "%s, %s" % (r["NAME"], r["STNAME"])})
    peer_series = {}
    for name in NAMED:
        c = next(p for p in PEERS if p["name"] == name)
        peer_series[name] = [{"period": p["period"], "value": p["value"]}
                             for p in series_for(c["state_fips"], c["place_fips"])]

    boro = []
    cty = {r["COUNTY"]: r for r in co25 if r["STATE"] == "36" and r["SUMLEV"] == "050"}
    for code, label in NYC_COUNTIES:
        r = cty[code]
        if r["CTYNAME"] != NYC_COUNTY_NAMES[code]:
            raise FetchError("county name mismatch " + code)
        boro.append({"name": label, "value": int(r["POPESTIMATE2025"]), "moe": None})
    if sum(b["value"] for b in boro) != nyc[-1]["value"]:
        boro_note = "Borough figures come from the county file and may not sum exactly to the city figure."
    else:
        boro_note = None

    caveats = [
        "The series joins two Census Bureau products. 2010 through 2019 come from the 2010-2020 intercensal "
        "estimates for cities (sub-est2020int.csv), which were revised to agree with the 2010 and 2020 censuses. "
        "2020 through 2025 come from Vintage 2025 (sub-est2025.csv), which starts from the 2020 Census and carries "
        "the newest revisions. The two files are not one consistent series; the change from 2019 to 2020 crosses that seam.",
        "Every figure is a July 1 estimate. The intercensal file's April 1, 2020 census population for New York City is "
        "%s; the Vintage 2025 estimates base for that date is %s." % (format(intercensal_2020, ","), format(v25_base, ",")),
        "Vintage 2025 revised every year from 2020 to 2024. Do not compare these numbers with figures from earlier "
        "vintages (for example the Vintage 2024 release) without saying so.",
        "Vintage 2024 introduced a revised method for net international migration that raised immigration estimates for "
        "2022-2024 well above earlier vintages; Vintage 2025 population figures include that change.",
    ]
    if boro_note:
        caveats.append(boro_note)
    write_indicator({
        "id": "population", "status": "ok", "status_reason": None,
        "definition": "Resident population of New York City on July 1 of each year, Census Bureau estimate.",
        "units": "people", "format": "int", "frequency": "annual",
        "series": nyc, "latest_period": "2025", "latest_extra": None,
        "source": {"name": "Census Bureau, Population Estimates Program: Vintage 2025 city and town totals "
                           "(2020-2025) and 2010-2020 intercensal city and town estimates (2010-2019)",
                   "url": "https://www.census.gov/data/tables/time-series/demo/popest/2020s-total-cities-and-towns.html",
                   "endpoint": URL_SUB2025 + " ; " + URL_SUBINT, "fetched": TODAY},
        "peers": {"period": "2020-2025", "geography": "city",
                  "note": "Percent change in population from July 1, 2020, to July 1, 2025, so that cities of different sizes "
                          "can be compared; each value also carries both totals. Incorporated-place estimates. "
                          "Indianapolis and Nashville are the balance of their consolidated governments.",
                  "source": {"name": "Census Bureau, Vintage 2025 city and town population estimates",
                             "url": "https://www.census.gov/data/tables/time-series/demo/popest/2020s-total-cities-and-towns.html",
                             "endpoint": URL_SUB2025, "fetched": TODAY},
                  "values": pvals},
        "peer_series": peer_series,
        "breakdowns": [{"by": "borough", "period": "2025",
                        "source_url": URL_CO2025, "values": boro}],
        "method": "City total for New York city (place 3651000), July 1 of each year. 2010-2019 from the 2010-2020 "
                  "intercensal estimates; 2020-2025 from Vintage 2025. Each series point carries a 'vintage' field "
                  "naming its file. Borough figures are the Vintage 2025 county estimates for the five counties "
                  "(Bronx, Kings, New York, Queens, Richmond). Peer cities come from the same Vintage 2025 place file and are "
                  "compared on growth, (July 1, 2025 estimate - July 1, 2020 estimate) / July 1, 2020 estimate x 100, not on size.",
        "caveats": caveats,
    })


# ---------------------------------------------------------------- migration (PEP components)

def migration():
    co25 = read_csv(download_file(URL_CO2025, os.path.join(RAW, "co-est2025-alldata.csv"), 100000))
    co20 = read_csv(download_file(URL_CO2020, os.path.join(RAW, "co-est2020-alldata.csv"), 100000))
    idx25 = {(r["STATE"], r["COUNTY"]): r for r in co25 if r["SUMLEV"] == "050"}
    idx20 = {(r["STATE"], r["COUNTY"]): r for r in co20 if r["SUMLEV"] == "050"}
    for code, _ in NYC_COUNTIES:
        for idx in (idx25, idx20):
            if idx[("36", code)]["CTYNAME"] != NYC_COUNTY_NAMES[code]:
                raise FetchError("county name mismatch " + code)
    for name, (sf, cf, cname) in PRINCIPAL_COUNTY.items():
        for idx in (idx25, idx20):
            if idx[(sf, cf)]["CTYNAME"] != cname:
                raise FetchError("principal county mismatch for %s: %s" % (name, idx[(sf, cf)]["CTYNAME"]))

    # (year, file index, vintage label). Year = 12 months ending July 1 of that year.
    plan = [(y, idx20, "Vintage 2020") for y in range(2011, 2021)] + \
           [(y, idx25, "Vintage 2025") for y in range(2021, 2026)]

    def rate(rows, comp, y):
        mig = sum(int(r["%s%d" % (comp, y)]) for r in rows)
        pop = sum((int(r["POPESTIMATE%d" % (y - 1)]) + int(r["POPESTIMATE%d" % y])) / 2 for r in rows)
        return 1000 * mig / pop

    # check our rate formula reproduces published county rates
    for y, idx, _ in plan:
        for code, _ in NYC_COUNTIES:
            r = idx[("36", code)]
            for comp in ("INTERNATIONALMIG", "DOMESTICMIG"):
                if abs(rate([r], comp, y) - float(r["R%s%d" % (comp, y)])) > 0.001:
                    raise FetchError("rate formula does not reproduce published rate %s %d %s" % (comp, y, code))

    common_caveats = [
        "Periods run July 1 to June 30 and are labeled by the year they end: '2025' means July 1, 2024 to June 30, 2025.",
        "The series joins two vintages. 2011-2020 come from Vintage 2020 (co-est2020-alldata.csv), the last "
        "estimates built on the 2010 Census; 2021-2025 come from Vintage 2025 (co-est2025-alldata.csv), built on the "
        "2020 Census. The vintage of every year is recorded in its series point. The Vintage 2020 components used for "
        "2011-2020 were not revised to agree with the 2020 Census.",
        "Partial periods are left out: Vintage 2020's '2010' column covers only April 1 to July 1, 2010, and Vintage "
        "2025's '2020' column covers only April 1 to July 1, 2020.",
        "Components of change are modeled estimates, not counts, and are revised with every vintage. They carry no "
        "published margin of error.",
    ]
    peer_note = ("Rates are per 1,000 residents for each city's principal county, because the Census Bureau publishes "
                 "components of change for counties, not cities. New York is the five boroughs combined, which matches "
                 "the city exactly; Philadelphia, San Francisco, Denver and Washington, D.C. are also coextensive with "
                 "their counties, and Jacksonville, Indianapolis, Nashville and Boston are close. Elsewhere the county is "
                 "much larger than the city (Los Angeles, Cook, Harris, Maricopa, Clark, King and others) or the city "
                 "spills into neighboring counties (Houston, Dallas, Austin, Fort Worth, Oklahoma City, Columbus). "
                 "Rate = net migrants / average of the July 1 populations at the start and end of the period x 1,000, "
                 "the Census Bureau's own formula, which this script checks against the published county rates.")

    for comp, mid, definition, extra in [
        ("INTERNATIONALMIG", "net_international_migration",
         "Net international migration into New York City's five counties in the 12 months ending July 1: people "
         "arriving from abroad minus people leaving for abroad, Census Bureau estimate.",
         ["Vintage 2024 changed the method for net international migration, adding administrative data on humanitarian "
          "and other recent arrivals, and its estimates for 2022-2024 were much higher than earlier vintages had shown. "
          "Vintage 2025 revises every year from 2021 on. Years 2011-2020 come from Vintage 2020, which used the older "
          "method, so part of the jump after 2021 reflects a change in measurement, not only a change in arrivals.",
          "Net international migration includes net movement between the United States and Puerto Rico."]),
        ("DOMESTICMIG", "net_domestic_migration",
         "Net domestic migration for New York City's five counties in the 12 months ending July 1: people moving in from "
         "elsewhere in the United States minus people moving out to elsewhere in the United States, Census Bureau estimate.",
         ["Domestic migration is estimated from IRS tax-return addresses, Medicare enrollment and other administrative "
          "records.",
          "Moves between the five boroughs cancel out in the city total but are counted in the borough figures."]),
    ]:
        series = []
        for y, idx, vint in plan:
            v = sum(int(idx[("36", c)]["%s%d" % (comp, y)]) for c, _ in NYC_COUNTIES)
            series.append({"period": str(y), "value": v, "moe": None, "vintage": vint})
        boro = [{"name": label, "value": int(idx25[("36", c)]["%s2025" % comp]), "moe": None}
                for c, label in NYC_COUNTIES]
        nyc_rows = [idx25[("36", c)] for c, _ in NYC_COUNTIES]
        pvals = [{"city": "New York", "value": round(rate(nyc_rows, comp, 2025), 2), "moe": None,
                  "geo_name": "New York City (Bronx, Kings, New York, Queens and Richmond counties), New York"}]
        for c in PEERS:
            if c["name"] == "New York":
                continue
            sf, cf, cname = PRINCIPAL_COUNTY[c["name"]]
            r = idx25[(sf, cf)]
            pvals.append({"city": c["name"], "value": round(float(r["R%s2025" % comp]), 2), "moe": None,
                          "geo_name": "%s, %s" % (r["CTYNAME"], r["STNAME"])})
        pvals.sort(key=lambda p: [x["name"] for x in PEERS].index(p["city"]))
        peer_series = {}
        for name in ["New York"] + NAMED:
            pts = []
            for y, idx, vint in plan:
                if name == "New York":
                    val = rate([idx[("36", c)] for c, _ in NYC_COUNTIES], comp, y)
                else:
                    sf, cf, _ = PRINCIPAL_COUNTY[name]
                    val = float(idx[(sf, cf)]["R%s%d" % (comp, y)])
                pts.append({"period": str(y), "value": round(val, 2)})
            peer_series[name] = pts
        write_indicator({
            "id": mid, "status": "ok", "status_reason": None,
            "definition": definition, "units": "people", "format": "int", "frequency": "annual",
            "series": series, "latest_period": "2025", "latest_extra": None,
            "source": {"name": "Census Bureau, Population Estimates Program, county population totals and components "
                               "of change: Vintage 2025 (2021-2025) and Vintage 2020 (2011-2020)",
                       "url": "https://www.census.gov/data/tables/time-series/demo/popest/2020s-counties-total.html",
                       "endpoint": URL_CO2025 + " ; " + URL_CO2020, "fetched": TODAY},
            "peers": {"period": "2025", "geography": "county", "units": "per 1,000 residents", "note": peer_note,
                      "source": {"name": "Census Bureau, Vintage 2025 county components of change (published rate columns R%s2025)" % comp,
                                 "url": "https://www.census.gov/data/tables/time-series/demo/popest/2020s-counties-total.html",
                                 "endpoint": URL_CO2025, "fetched": TODAY},
                      "values": pvals},
            "peer_series": peer_series,
            "breakdowns": [{"by": "borough", "period": "2025", "source_url": URL_CO2025, "values": boro}],
            "method": "Sum of the %s<year> columns for the five New York City counties (FIPS 36005, 36047, 36061, 36081, 36085). "
                      "2011-2020 from Vintage 2020; 2021-2025 from Vintage 2025. The city series is a count of people. "
                      "Peer values and peer_series are rates per 1,000 residents, so they are not in the same units as the "
                      "city series: for the four named peers they are the Census Bureau's published county rates; for New "
                      "York (included in peer_series so the lines are comparable) the rate is computed from the five-county "
                      "sums with the Bureau's formula, net migrants / mean of the starting and ending July 1 populations x 1,000. "
                      "Borough values are counts for July 2024-June 2025." % comp,
            "caveats": common_caveats + extra + [peer_note],
        })


# ---------------------------------------------------------------- ACS measures

def acs_all(cpi, cpi_missing):
    # metadata per year and the variables each measure needs
    tables = sorted({t for spec in ACS.values() for t in spec["tables"]})
    resolved = {}   # (measure, year) -> var dict
    for y in ACS_YEARS:
        meta = {t: group_meta(y, t) for t in tables}
        for mid, spec in ACS.items():
            if all(meta[t] is not None for t in spec["tables"]):
                resolved[(mid, y)] = spec["resolve"](meta)
    place = {}
    for y in ACS_YEARS:
        bases = sorted({b for (mid, yy), v in resolved.items() if yy == y for lst in v.values() for b in lst})
        rows = acs_rows(y, bases, "place:*", "state:*", "place")
        place[y] = {(r["state"], r["place"]): r for r in rows}
        if ("36", "51000") not in place[y]:
            raise FetchError("ACS %d: New York city missing" % y)
    subj_vars, subj_place = {}, {}
    for y in ACS_YEARS:
        if y < 2010:
            continue
        sv = subject_vars(y)
        if sv:
            subj_vars[y] = sv
            rows = acs_rows(y, sorted(sv.values()), "place:*", "state:*", "place", "acs/acs1/subject")
            subj_place[y] = {(r["state"], r["place"]): r for r in rows}
    subj_county = {r["county"]: r for r in acs_rows(LATEST, sorted(subj_vars[LATEST].values()),
                   "county:005,047,061,081,085", "state:36", "nyc_counties", "acs/acs1/subject")}
    overlay_log = {}

    def overlay(mid, y, row_subj, v, m):
        """Swap in the published MOE when the published estimate agrees with ours."""
        if v is None or row_subj is None or mid not in subj_vars.get(y, {}):
            return v, m, False
        b = subj_vars[y][mid]
        pv, pm = est(row_subj, b), moe(row_subj, b)
        if pv is None or pm is None:
            return v, m, False
        if abs(pv - v) > 0.051 + 1e-9:
            overlay_log.setdefault(mid, []).append("%d %s: computed %.2f, published %.1f" % (y, row_subj.get("NAME"), v, pv))
            return v, m, False
        return v, pm, True

    # 2025 boroughs
    bases25 = sorted({b for (mid, yy), v in resolved.items() if yy == LATEST for lst in v.values() for b in lst})
    county = {r["county"]: r for r in acs_rows(LATEST, bases25, "county:005,047,061,081,085", "state:36", "nyc_counties")}
    if len(county) != 5:
        raise FetchError("ACS county rows: expected 5, got %d" % len(county))
    # 2025 race/ethnicity (iterated tables), NYC only
    races = [("B", "Black alone"), ("D", "Asian alone"), ("H", "White alone, not Hispanic"), ("I", "Hispanic or Latino (any race)")]
    race_meta = {}
    for code, _ in races:
        for t in ("B19013", "B17001", "C27001"):
            race_meta[t + code] = group_meta(LATEST, t + code)
            if race_meta[t + code] is None:
                raise FetchError("missing iterated table %s%s" % (t, code))
    race_res = {}
    for code, _ in races:
        race_res[("median_household_income", code)] = {"val": [find_prefix(race_meta["B19013" + code], "median household income")]}
        race_res[("poverty_rate", code)] = r_poverty(race_meta, "B17001" + code)
        race_res[("uninsured_rate", code)] = r_uninsured(race_meta, "C27001" + code)
    rbases = sorted({b for v in race_res.values() for lst in v.values() for b in lst})
    race_row = acs_rows(LATEST, rbases, "place:51000", "state:36", "nyc_race")[0]

    peer_geo = {c["name"]: (c["state_fips"], c["place_fips"]) for c in PEERS}
    cpi_base = cpi[LATEST]

    TEXT = {
        "foreign_born_share": dict(
            table="B05002", units="percent", format="pct1",
            definition="Share of all residents who were born outside the United States and were not U.S. citizens at birth.",
            source="Census Bureau, American Community Survey 1-year estimates, table B05002 (place of birth by nativity and citizenship status)",
            method="Foreign born (B05002_013) divided by total population (B05002_001), times 100. People born in Puerto Rico, "
                   "U.S. island areas or abroad to American parents count as native. Margins of error for the share are "
                   "derived from the published margins of the two counts with the Census Bureau's formula for proportions "
                   "(ACS General Handbook, chapter 8).",
            caveats=[]),
        "prime_age_employment": dict(
            table="B23001", units="percent", format="pct1",
            definition="Share of residents aged 25 to 54 who have a job (civilian employed or in the Armed Forces).",
            source="Census Bureau, American Community Survey 1-year estimates, table B23001 (sex by age by employment status for the population 16 and over)",
            method="Formula: prime-age employment rate = 100 x (sum over men and women, ages 25-29, 30-34, 35-44 and 45-54, of "
                   "[civilian employed + in Armed Forces]) / (sum over the same eight sex-and-age groups of total population). "
                   "The denominator is everyone in those age groups, including people in group quarters such as jails and "
                   "nursing homes and people not in the labor force. Margins of error: sums use the root-sum-of-squares of the "
                   "published cell margins, and the share uses the Census Bureau's formula for proportions.",
            caveats=["Armed Forces members count as employed; in New York City they are a tiny share of 25- to 54-year-olds.",
                     "ACS employment status refers to the week before the survey, spread across the whole year; it is not "
                     "the same concept or source as the BLS household-survey employment-population ratio."]),
        "median_household_income": dict(
            table="B19013", units="dollars", format="usd0",
            definition="Median household income, New York City, in 2025 dollars (adjusted with the New York-area consumer price index).",
            source="Census Bureau, American Community Survey 1-year estimates, table B19013 (median household income in the past 12 months); "
                   "Bureau of Labor Statistics CPI-U, New York-Newark-Jersey City, all items (CUURS12ASA0)",
            method="Each year's published median (B19013_001, in that survey year's dollars) is multiplied by CPI(2025) / CPI(year), "
                   "where CPI is the annual average of the monthly BLS CPI-U for New York-Newark-Jersey City, all items, not "
                   "seasonally adjusted (series CUURS12ASA0), averaged by this script from the monthly values. The published "
                   "margin of error is scaled by the same factor. Peer values for 2025 are the published medians, unadjusted, "
                   "since every city is measured in the same year's dollars; the 2025 peer values and the city's 2025 value are "
                   "therefore directly comparable. Borough and race breakdowns are 2025 published medians.",
            caveats=["The deflator is the New York-area CPI-U, not the national price index the Census Bureau uses in its own "
                     "historical income tables, so inflation-adjusted figures here will differ from Census Bureau reports.",
                     "peer_series values are nominal (each year's own dollars), not inflation-adjusted, because a New York "
                     "price index is wrong for other cities. 'New York' is included in peer_series in the same nominal "
                     "dollars so the five lines can be compared with each other; do not plot it against the inflation-adjusted series.",
                     "Race groups B (Black) and D (Asian) are race alone and include Hispanic members of those races; "
                     "H is white alone, not Hispanic; I is Hispanic or Latino of any race."]),
        "poverty_rate": dict(
            table="B17001", units="percent", format="pct1",
            definition="Share of residents with family income below the federal poverty threshold (official measure).",
            source="Census Bureau, American Community Survey 1-year estimates, table B17001 (poverty status in the past 12 months by sex by age)",
            method="People with income in the past 12 months below the poverty level (B17001_002) divided by the population for "
                   "whom poverty status is determined (B17001_001), times 100. That universe excludes people in institutions, "
                   "military group quarters and college dormitories, and unrelated children under 15. Margins of error derived "
                   "with the Census Bureau's formula for proportions.",
            caveats=["The federal poverty thresholds are the same nationwide and do not reflect New York's housing costs; "
                     "see the separate Poverty Tracker measure for a cost-adjusted rate.",
                     "Race groups B (Black) and D (Asian) are race alone and include Hispanic members of those races; "
                     "H is white alone, not Hispanic; I is Hispanic or Latino of any race."]),
        "gini_index": dict(
            table="B19083", units="index", format="dec2",
            definition="Gini index of household income inequality: 0 means every household has the same income, 1 means one household has all of it.",
            source="Census Bureau, American Community Survey 1-year estimates, table B19083 (Gini index of income inequality)",
            method="Published Gini index of household income (B19083_001) and its published margin of error. No calculation.",
            caveats=["Table B19083 starts in 2006 in the 1-year release; there is no 2005 value.",
                     "Year-to-year changes in the Gini index are often smaller than the margin of error; check the moe before "
                     "describing a change. Values are stored to four decimals; two-decimal display hides most annual movement."]),
        "severe_rent_burden": dict(
            table="B25070", units="percent", format="pct1",
            definition="Share of renter households paying 50 percent or more of household income for gross rent (rent plus utilities).",
            source="Census Bureau, American Community Survey 1-year estimates, table B25070 (gross rent as a percentage of household income)",
            method="Renter households paying 50.0 percent or more (B25070_010) divided by renter households for whom the ratio "
                   "is computed: all renter-occupied units (B25070_001) minus 'not computed' (B25070_011), times 100. 'Not "
                   "computed' covers units with no cash rent and households with zero or negative income. Margin of error for "
                   "the denominator is the root-sum-of-squares of the two published margins; the share uses the formula for proportions.",
            caveats=["Gross rent is what the household pays, after any rent subsidy; households in rent-regulated and subsidized "
                     "apartments are included."]),
        "uninsured_rate": dict(
            table="B27001", units="percent", format="pct1",
            definition="Share of the civilian noninstitutionalized population with no health insurance coverage.",
            source="Census Bureau, American Community Survey 1-year estimates, table B27001 (health insurance coverage status by sex by age)",
            method="Sum of the 'No health insurance coverage' cells in B27001 (18 sex-by-age cells from 2009 on; three age cells in the 2008 release) divided by the "
                   "civilian noninstitutionalized population (B27001_001), times 100. The sum's margin of error is the root-sum-of-squares "
                   "of the published cell margins, which slightly overstates the true margin; the share uses the formula for proportions. "
                   "Race breakdowns use the collapsed iterated tables C27001B/D/H/I the same way (three age groups).",
            caveats=["The ACS health insurance question starts in 2008; there are no earlier values.",
                     "The ACS counts people with only Indian Health Service coverage as uninsured.",
                     "Race groups B (Black) and D (Asian) are race alone and include Hispanic members of those races; "
                     "H is white alone, not Hispanic; I is Hispanic or Latino of any race."]),
        "commute_time": dict(
            table="B08013", units="minutes", format="dec1",
            definition="Average one-way travel time to work, in minutes, for workers 16 and over who do not work from home.",
            source="Census Bureau, American Community Survey 1-year estimates, tables B08013 (aggregate travel time to work) and B08134 (workers who did not work from home, by travel time)",
            method="Mean travel time = aggregate travel time to work in minutes (B08013_001) / workers 16 and over who did not work "
                   "from home (B08134_001). This reproduces the Census Bureau's published 'mean travel time to work' (table S0801). "
                   "Margin of error from the published margins with the Census Bureau's formula for ratios.",
            caveats=["People who work from home are excluded. Remote work rose sharply after 2019, so the mix of people who "
                     "commute changed; 2021 onward is not strictly comparable to earlier years.",
                     "Travel time is self-reported for the week before the survey, door to door, one way."]),
    }

    common = ["The ACS 1-year 2020 standard tables were never released (the Census Bureau published only experimental "
              "estimates because of pandemic data-collection problems), so 2020 is missing from every ACS series.",
              "The 2005 ACS covered only people in households; group quarters (dorms, prisons, nursing homes, shelters) were "
              "added in 2006. 2005 values are not strictly comparable to later years.",
              "All ACS figures are survey estimates. moe is the 90 percent margin of error, published by the Census Bureau "
              "for single cells and derived with the Bureau's approximation formulas for sums, shares and ratios."]

    for mid, spec in ACS.items():
        T = TEXT[mid]
        nd = spec["nd"]
        years = [y for y in ACS_YEARS if (mid, y) in resolved]

        def val(row, y):
            v, m = spec["compute"](row, resolved[(mid, y)])
            return v, m

        series = []
        skipped = []
        pub_years = []
        for y in years:
            v, m = val(place[y][("36", "51000")], y)
            if v is None:
                skipped.append(y)
                continue
            v, m, used = overlay(mid, y, subj_place.get(y, {}).get(("36", "51000")), v, m)
            if used:
                pub_years.append(y)
            if mid == "median_household_income":
                f = cpi_base / cpi[y]
                v, m = v * f, (None if m is None else m * f)
            series.append({"period": str(y), "value": rnd(v, nd), "moe": rnd(m, nd)})
        if not series or series[-1]["period"] != str(LATEST):
            raise FetchError("%s: no %d value for New York" % (mid, LATEST))
        # peers 2025
        pvals = []
        for c in PEERS:
            r = place[LATEST].get(peer_geo[c["name"]])
            if r is None:
                raise FetchError("%s: peer %s missing in ACS %d" % (mid, c["name"], LATEST))
            v, m = val(r, LATEST)
            if v is None:
                raise FetchError("%s: peer %s has no value" % (mid, c["name"]))
            v, m, _ = overlay(mid, LATEST, subj_place.get(LATEST, {}).get(peer_geo[c["name"]]), v, m)
            pvals.append({"city": c["name"], "value": rnd(v, nd), "moe": rnd(m, nd), "geo_name": r["NAME"]})
        peer_series = {}
        names = NAMED + (["New York"] if mid == "median_household_income" else [])
        for name in names:
            pts = []
            for y in years:
                r = place[y].get(peer_geo[name])
                if r is None:
                    continue
                v, m = val(r, y)
                if v is not None:
                    pts.append({"period": str(y), "value": rnd(v, nd)})
            peer_series[name] = pts
        # breakdowns
        boro = []
        for code, label in NYC_COUNTIES:
            v, m = val(county[code], LATEST)
            v, m, _ = overlay(mid, LATEST, subj_county.get(code), v, m)
            boro.append({"name": label, "value": rnd(v, nd), "moe": rnd(m, nd)})
        breakdowns = [{"by": "borough", "period": str(LATEST), "source_url": dc_table(LATEST, T["table"], BORO_G),
                       "values": boro}]
        if mid in ("median_household_income", "poverty_rate", "uninsured_rate"):
            comp = c_val if mid == "median_household_income" else c_pct
            tbl = {"median_household_income": "B19013", "poverty_rate": "B17001", "uninsured_rate": "C27001"}[mid]
            vals = []
            for code, label in races:
                v, m = comp(race_row, race_res[(mid, code)])
                vals.append({"name": label, "value": rnd(v, nd), "moe": rnd(m, nd)})
            breakdowns.append({"by": "race/ethnicity", "period": str(LATEST),
                               "source_url": dc_table(LATEST, tbl + "B", NYC_G) + " (and %sD, %sH, %sI)" % (tbl, tbl, tbl),
                               "values": vals})
        if mid == "prime_age_employment":
            meta25 = {"B23001": group_meta(LATEST, "B23001")}
            vals = []
            for sex, label in (("male", "Men"), ("female", "Women")):
                v, m = c_pct(place[LATEST][("36", "51000")], r_prime(meta25, (sex,)))
                vals.append({"name": label, "value": rnd(v, nd), "moe": rnd(m, nd)})
            breakdowns.append({"by": "sex", "period": str(LATEST), "source_url": dc_table(LATEST, "B23001", NYC_G),
                               "values": vals})

        caveats = list(T["caveats"]) + common
        if mid in SUBJECT:
            t = SUBJECT[mid][0]
            caveats.append("Margins of error: for %s the moe is the one the Census Bureau publishes in subject table %s "
                           "(which matches this estimate to its published rounding) for the city, the 2025 peers and the "
                           "boroughs. Other years, and the race breakdowns, use the derived margin described in the method."
                           % (", ".join(map(str, pub_years)) or "no year", t))
        if overlay_log.get(mid):
            caveats.append("Published subject-table estimate differed from the computed value, so the derived moe was kept: "
                           + "; ".join(overlay_log[mid]))
            print("WARNING", mid, overlay_log[mid])
        if skipped:
            caveats.append("No value could be computed for %s (estimate suppressed or missing in the API)." %
                           ", ".join(map(str, skipped)))
        first = series[0]["period"]
        if mid == "median_household_income":
            note = []
            for y, gone in sorted(cpi_missing.items()):
                note.append("%d (%s missing)" % (y, ", ".join(gone)))
            if note:
                caveats.append("CPI annual averages are the mean of the months BLS published. Months with no published value: %s. "
                               "BLS published no October 2025 index because prices were not collected during the 2025 federal "
                               "government shutdown, so the 2025 average uses the 11 published months." % "; ".join(note))
            caveats.append("2025 CPI annual average used as the base: %.3f (1982-84=100)." % cpi_base)
        src_tables = T["table"] + (", B08134" if mid == "commute_time" else "")
        endpoint = acs_url(LATEST) + " (and the same dataset for each year %s-%d, 2020 excepted; variables %s)" % (
            first, LATEST, src_tables)
        if mid == "median_household_income":
            endpoint += " ; " + URL_BLS + CPI_SERIES + " (POST, startyear/endyear)"
        write_indicator({
            "id": mid, "status": "ok", "status_reason": None,
            "definition": T["definition"], "units": T["units"], "format": T["format"], "frequency": "annual",
            "series": series, "latest_period": str(LATEST), "latest_extra": None,
            "source": {"name": T["source"], "url": dc_table(LATEST, T["table"], NYC_G),
                       "endpoint": endpoint, "fetched": TODAY},
            "peers": {"period": str(LATEST), "geography": "city",
                      "note": ("Values are nominal 2025 dollars (the same year for every city)." if mid == "median_household_income" else None),
                      "source": {"name": "Census Bureau, American Community Survey 2025 1-year estimates, table %s, places" % src_tables,
                                 "url": dc_table(LATEST, T["table"]),
                                 "endpoint": acs_url(LATEST) + "?for=place:*&in=state:*", "fetched": TODAY},
                      "values": pvals},
            "peer_series": peer_series,
            "breakdowns": breakdowns,
            "method": T["method"] + " Citywide figures are for New York city (place 3651000); peers are matched on place "
                                    "GEOID (state + place FIPS) from data/peers.json; borough figures are the five counties.",
            "caveats": caveats,
        })


# ---------------------------------------------------------------- main

def main():
    os.makedirs(RAW, exist_ok=True)
    population()
    migration()
    cpi, missing = cpi_annual()
    acs_all(cpi, missing)


if __name__ == "__main__":
    try:
        main()
    except FetchError as e:
        print("census fetch FAILED:", e, file=sys.stderr)
        sys.exit(1)
