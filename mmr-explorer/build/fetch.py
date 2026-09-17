#!/usr/bin/env python3
"""Pull the raw Mayor's Management Report tables from NYC Open Data.

Writes newline-delimited JSON to build/raw/. Fails loud: a page that comes
back empty before the expected row count is an error, not a stopping point.
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "mmr-explorer/1.0 (github.com/joshgreenman1973; josh.greenman@gmail.com)"

SETS = {
    # Mayor's Management Report - Agency Performance Indicators
    "indicators": ("rbed-zzin", None),
    # MMR Agency Resources (expenditures, personnel, overtime) - full fiscal year
    "resources": ("4qmi-txnk", None),
    # Preliminary MMR Agency Resources - carries the current fiscal year
    "resources_pmmr": ("nvzu-6t9y", None),
}

def get(url, tries=6):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if n == tries - 1:
                raise
            wait = 4 * (n + 1)
            print(f"    retry {n+1} after {wait}s ({e})", file=sys.stderr)
            time.sleep(wait)

def count(res, where):
    q = f"https://data.cityofnewyork.us/resource/{res}.json?$select=count(1)"
    if where:
        q += "&$where=" + urllib.parse.quote(where)
    return int(get(q)[0]["count_1"])

def pull(name, res, where, page=25000):
    total = count(res, where)
    print(f"{name}: {total:,} rows expected")
    out = os.path.join(RAW, name + ".ndjson")
    got = 0
    with open(out, "w") as fh:
        off = 0
        while off < total:
            q = (f"https://data.cityofnewyork.us/resource/{res}.json"
                 f"?$limit={page}&$offset={off}&$order=:id")
            if where:
                q += "&$where=" + urllib.parse.quote(where)
            rows = get(q)
            if not rows:
                raise SystemExit(f"FAIL {name}: empty page at offset {off:,} of {total:,}")
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
            got += len(rows)
            off += len(rows)
            print(f"  {got:,}/{total:,}", end="\r", flush=True)
            time.sleep(0.4)
    print(f"  {got:,}/{total:,} written to {out}")
    if got < total * 0.99:
        raise SystemExit(f"FAIL {name}: got {got:,} of {total:,}")
    return got

if __name__ == "__main__":
    import urllib.parse
    os.makedirs(RAW, exist_ok=True)
    only = sys.argv[1:] or list(SETS)
    for name in only:
        res, where = SETS[name]
        pull(name, res, where)
