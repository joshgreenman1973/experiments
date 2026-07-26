#!/usr/bin/env python3
"""Fetch per-route monthly bus ridership (people carried) from the MTA's
Bus Stop Level Ridership dataset (data.ny.gov fvdm-uavx) and write
data/ridership/routes-monthly.json for the tracker UI.

Run monthly by .github/workflows/bus-tracker-ridership.yml (the dataset is
published with roughly a one-month lag) and safe to run by hand.

FAILS LOUD: exits nonzero if either query returns no rows, if the latest
month regresses, or if totals look implausibly small — never writes an
empty file over a good one.
"""
import json
import calendar
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

BASE = 'https://data.ny.gov/resource/fvdm-uavx.json'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                   'data', 'ridership', 'routes-monthly.json')

# Sanity floor: NYC buses carry ~30M+ riders in any real month. If the
# latest month is below this, the dataset is truncated or the query broke.
MIN_MONTH_TOTAL = 10_000_000


def fetch(params):
    url = BASE + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'nyc-bus-tracker'})
    with urllib.request.urlopen(req, timeout=560) as r:
        rows = json.load(r)
    if not rows:
        sys.exit(f'FATAL: empty response from Socrata for {params}')
    return rows

print('fetching per-route monthly totals…', flush=True)
all_rows = fetch({
    '$select': 'route_id,date_trunc_ym(date) as m,sum(boardings) as b',
    '$group': 'route_id,m', '$limit': '50000'})
print(f'  {len(all_rows)} route-months', flush=True)

print('fetching weekday-only totals…', flush=True)
wd_rows = fetch({
    '$select': 'route_id,date_trunc_ym(date) as m,sum(boardings) as b',
    '$where': 'date_extract_dow(date) between 1 and 5',
    '$group': 'route_id,m', '$limit': '50000'})
print(f'  {len(wd_rows)} route-months', flush=True)

months = sorted({r['m'][:7] for r in all_rows})
if len(months) < 20:
    sys.exit(f'FATAL: only {len(months)} months returned ({months[:3]}…) — expected 20+')

def wd_count(ym):
    y, m = map(int, ym.split('-'))
    return sum(1 for d in range(1, calendar.monthrange(y, m)[1] + 1)
               if date(y, m, d).weekday() < 5)

midx = {m: i for i, m in enumerate(months)}
wd_days = {m: wd_count(m) for m in months}

routes = {}
for r in all_rows:
    rec = routes.setdefault(r['route_id'], {'total': [0] * len(months), 'wdAvg': [0] * len(months)})
    rec['total'][midx[r['m'][:7]]] = int(float(r['b']))
for r in wd_rows:
    rec = routes.get(r['route_id'])
    if rec:
        m = r['m'][:7]
        rec['wdAvg'][midx[m]] = round(int(float(r['b'])) / wd_days[m])

system = {
    'total': [sum(rec['total'][i] for rec in routes.values()) for i in range(len(months))],
    'wdAvg': [sum(rec['wdAvg'][i] for rec in routes.values()) for i in range(len(months))],
}
if system['total'][-1] < MIN_MONTH_TOTAL:
    sys.exit(f"FATAL: latest month ({months[-1]}) total {system['total'][-1]:,} "
             f'below sanity floor {MIN_MONTH_TOTAL:,} — refusing to write')

# never regress: if an existing file has a newer latest month, something is wrong
if os.path.exists(OUT):
    old = json.load(open(OUT))
    if old.get('months') and old['months'][-1] > months[-1]:
        sys.exit(f"FATAL: existing file ends {old['months'][-1]} but fetch ends {months[-1]}")

out = {
    'updated': date.today().isoformat(),
    'source': 'MTA Bus Stop Level Ridership (data.ny.gov fvdm-uavx), APC-derived boardings; '
              'wdAvg = month weekday boardings / calendar weekdays (holidays counted as weekdays)',
    'months': months,
    'wdDays': wd_days,
    'system': system,
    'routes': routes,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print(f"wrote {os.path.normpath(OUT)}: {len(routes)} routes × {len(months)} months "
      f"(latest {months[-1]}: {system['total'][-1]:,} boardings, "
      f"{system['wdAvg'][-1]:,} avg weekday)")
