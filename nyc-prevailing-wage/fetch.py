#!/usr/bin/env python3
"""Pull the New York City-area rows of the state Department of Labor's
Certified Payroll Registration dataset (data.ny.gov, w2zp-sf2x) into
data/source/certified-payroll-nyc-area.csv.gz.

The pull is deliberately wide: every ZIP from 10000 to 10499, 11000 to 11499
and 11600 to 11699, plus any row whose project city is a borough name. That
over-includes Nassau County, and build.py narrows it to the five boroughs.
The wide file is kept so the narrowing is reproducible.

Exits non-zero if the portal returns nothing, so a broken pull cannot be
published as an empty site.
"""
import sys, urllib.request, urllib.parse, pathlib, gzip

OUT = pathlib.Path(__file__).parent / 'data' / 'source' / 'certified-payroll-nyc-area.csv.gz'
WHERE = ("(project_zipcode between '10000' and '10499') OR "
         "(project_zipcode between '11000' and '11499') OR "
         "(project_zipcode between '11600' and '11699') OR "
         "upper(project_city) in('NEW YORK','BROOKLYN','BRONX','QUEENS','STATEN ISLAND',"
         "'MANHATTAN','NYC','NEW YORK CITY')")
URL = 'https://data.ny.gov/resource/w2zp-sf2x.csv?' + urllib.parse.urlencode(
    {'$where': WHERE, '$limit': 2000000, '$order': ':id'})

def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'nyc-prevailing-wage build'})
    with urllib.request.urlopen(req, timeout=900) as r:
        body = r.read()
    lines = body.count(b'\n')
    if lines < 1000:
        sys.exit(f'FETCH FAILED: only {lines} lines came back from data.ny.gov')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, 'wb') as g:
        g.write(body)
    print(f'wrote {OUT} ({lines:,} lines)')

if __name__ == '__main__':
    main()
