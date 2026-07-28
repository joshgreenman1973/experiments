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

# Which months are actually COMPLETE? The series opens on 2024-09-30, so
# September 2024 holds a single day. Dividing one day's boardings by a full
# month's weekdays produces a near-zero point that drags every trend line
# upward, so partial months are dropped rather than shown.
print('checking month coverage…', flush=True)
cov = fetch({'$select': 'date_trunc_ym(date) as m,count(distinct date) as days',
             '$group': 'm', '$limit': '500'})
complete = set()
partial = []
for r in cov:
    ym = r['m'][:7]
    y, mo = map(int, ym.split('-'))
    have, need = int(r['days']), calendar.monthrange(y, mo)[1]
    (complete.add(ym) if have >= need else partial.append(f'{ym} ({have}/{need} days)'))
if partial:
    print(f'  dropping partial months: {", ".join(partial)}', flush=True)
if len(complete) < 12:
    sys.exit(f'FATAL: only {len(complete)} complete months — expected 12+')

print('fetching per-route monthly totals…', flush=True)
all_rows = fetch({
    '$select': 'route_id,date_trunc_ym(date) as m,sum(boardings) as b',
    '$group': 'route_id,m', '$limit': '50000'})
print(f'  {len(all_rows)} route-months', flush=True)
all_rows = [r for r in all_rows if r['m'][:7] in complete]

print('fetching weekday-only totals…', flush=True)
wd_rows = fetch({
    '$select': 'route_id,date_trunc_ym(date) as m,sum(boardings) as b',
    # Socrata date_extract_dow: 0 = Sunday … 6 = Saturday (verified against
    # 2026-06-07, a Sunday, which returns 0). So 1-5 is Monday-Friday.
    '$where': 'date_extract_dow(date) between 1 and 5',
    '$group': 'route_id,m', '$limit': '50000'})
print(f'  {len(wd_rows)} route-months', flush=True)
wd_rows = [r for r in wd_rows if r['m'][:7] in complete]

months = sorted({r['m'][:7] for r in all_rows})
if len(months) < 12:
    sys.exit(f'FATAL: only {len(months)} complete months ({months[:3]}…) — expected 12+')

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
    'source': 'MTA Bus Stop Level Ridership (data.ny.gov fvdm-uavx), boardings recorded by '
              'Automatic Passenger Counters on board MTA buses.',
    'definitions': {
        'total': 'All boardings recorded on the route that month, every day of the week.',
        'wdAvg': 'Monday-Friday boardings that month divided by the number of calendar '
                 'weekdays in the month. Public holidays are counted as weekdays, so months '
                 'containing them read slightly low.',
        'months': 'Only calendar months with data for every day are included; partial months '
                  'at either end of the series are dropped.',
        'caveat': 'Counters miss some riders and not every bus carries one. The MTA publishes '
                  'these as estimates.',
    },
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
