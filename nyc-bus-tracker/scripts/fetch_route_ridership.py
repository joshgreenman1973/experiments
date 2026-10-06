#!/usr/bin/env python3
"""Fetch per-route monthly bus ridership for the tracker UI and write
data/ridership/routes-monthly.json.

Two independent measures, side by side:

  * Passenger counters: MTA Bus Stop Level Ridership (data.ny.gov fvdm-uavx),
    boardings recorded by Automatic Passenger Counters on board buses.
    Fields: total, wdAvg (unchanged since the first version of this file).
  * Fare taps: MTA Bus Hourly Ridership (data.ny.gov kv7t-n8in for 2020-2024,
    gxb3-akrn for 2025 onward), paid OMNY and MetroCard entries including free
    transfers. Fields: tapsTotal, tapsWdAvg, and ratio = wdAvg / tapsWdAvg.

If NYC buses go fare-free the tap series stops, and counters are all that is
left. The ratio, route by route, is the calibration between the two.

Route keys are rewritten to the live-feed / GTFS spelling used everywhere else
in the tracker (Q06 not Q6), read from data/routes/routes.geojson.

Network-redesign breaks (Queens 2025) are recorded in `breaks` and per route in
`breakMonths`; the dates and route lists come from MTA primary sources quoted
below in QUEENS_REDESIGN.

Run monthly by .github/workflows/bus-tracker-ridership.yml (the counter dataset
is published with roughly a one-month lag) and safe to run by hand.

FAILS LOUD: exits nonzero if a counter query returns no rows, if the latest
month regresses, if totals look implausibly small, if a fully covered fare-tap
month has fewer than MIN_TAP_ROUTES routes, if system weekday taps fall outside
a plausible band, or if the tap queries disagree with each other. Never writes
an empty file over a good one. Socrata throttling (403 authentication_required,
429) and transient 5xx errors are retried with backoff, not treated as fatal.
"""
import calendar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
SODA = 'https://data.ny.gov/resource/'
BASE = SODA + 'fvdm-uavx.json'
TAPS_2020_2024 = 'kv7t-n8in'   # MTA Bus Hourly Ridership: 2020-2024
TAPS_2025_ON = 'gxb3-akrn'     # MTA Bus Hourly Ridership: Beginning 2025
OUT = os.path.join(HERE, '..', 'data', 'ridership', 'routes-monthly.json')
GEO = os.path.join(HERE, '..', 'data', 'routes', 'routes.geojson')

# Sanity floor: NYC buses carry ~30M+ riders in any real month. If the
# latest month is below this, the dataset is truncated or the query broke.
MIN_MONTH_TOTAL = 10_000_000
# Every fully covered fare-tap month should have taps on at least this many of
# the tracker's routes (about 330 do in a normal month).
MIN_TAP_ROUTES = 250
# Plausible band for system-wide average weekday fare taps (about 1.1-1.3M in
# 2024-2026). Outside it, a query or the dataset is broken.
TAP_WD_BAND = (800_000, 1_500_000)
# The publisher's note on bus_route: "Data for the Q52 SBS and Q53 SBS are
# reported together." Their taps are stored as one combined figure.
TAP_JOINT = ('Q52+', 'Q53+')

APP_TOKEN = os.environ.get('SOCRATA_APP_TOKEN', '').strip()  # optional


def get(url, params, label):
    """GET a SODA query, retrying throttles (403 authentication_required, 429)
    and transient server errors with backoff. Returns the parsed rows."""
    full = url + '?' + urllib.parse.urlencode(params)
    headers = {'User-Agent': 'nyc-bus-tracker'}
    if APP_TOKEN:
        headers['X-App-Token'] = APP_TOKEN
    waits = [10, 20, 40, 80, 160, 240, 240]
    for attempt in range(len(waits) + 1):
        try:
            req = urllib.request.Request(full, headers=headers)
            with urllib.request.urlopen(req, timeout=560) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504) or attempt == len(waits):
                sys.exit(f'FATAL: HTTP {e.code} from Socrata for {label}: {e.read()[:300]!r}')
            why = f'HTTP {e.code}'
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            if attempt == len(waits):
                sys.exit(f'FATAL: {type(e).__name__} from Socrata for {label}: {e}')
            why = type(e).__name__
        print(f'  {label}: {why}, retrying in {waits[attempt]}s', flush=True)
        time.sleep(waits[attempt])


def fetch(params):
    rows = get(BASE, params, 'counters')
    if not rows:
        sys.exit(f'FATAL: empty response from Socrata for {params}')
    return rows


# ---------------------------------------------------------------- route ids
# The live MTA feed and GTFS spell four Queens routes with a leading zero
# (Q06, Q07, Q08, Q09); the counter dataset spells them Q6..Q9. Canonical form
# strips leading zeros right after the letter prefix so both meet, and every
# key is then written in the GTFS spelling the rest of the tracker uses.
def canon(rid):
    return re.sub(r'^([A-Z]+)0+(?=\d)', r'\1', rid.strip().upper())


geo = json.load(open(GEO))
gtfs_ids = sorted({f['properties']['routeId'].strip().upper()
                   for f in geo['features'] if f['properties'].get('routeId')})
LIVE = {}
for g in gtfs_ids:
    c = canon(g)
    if c in LIVE and LIVE[c] != g:
        sys.exit(f'FATAL: GTFS ids {LIVE[c]} and {g} collapse to the same route {c}')
    LIVE[c] = g
if len(LIVE) < 300:
    sys.exit(f'FATAL: only {len(LIVE)} route ids in {GEO} — expected 300+')


def live_id(rid):
    c = canon(rid)
    return LIVE.get(c, c)


# ------------------------------------------------------- counter boardings
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
N = len(months)

# Accumulate raw sums under the live/GTFS key. Two source ids landing on one
# key (say the dataset switches from Q6 to Q06 mid-series) are summed.
renamed = {}
raw_total, raw_wd = {}, {}
for r in all_rows:
    k = live_id(r['route_id'])
    if k != r['route_id']:
        renamed[r['route_id']] = k
    raw_total.setdefault(k, {}).setdefault(r['route_id'], [0] * N)[midx[r['m'][:7]]] = int(float(r['b']))
for r in wd_rows:
    k = live_id(r['route_id'])
    if k in raw_total:
        raw_wd.setdefault(k, {}).setdefault(r['route_id'], [0] * N)[midx[r['m'][:7]]] = int(float(r['b']))

routes = {}
for k in sorted(raw_total):
    srcs = raw_total[k]
    if len(srcs) > 1:
        print(f'  merging counter ids {sorted(srcs)} into {k}', flush=True)
    total = [sum(v[i] for v in srcs.values()) for i in range(N)]
    wd = [sum(v[i] for v in raw_wd.get(k, {}).values()) for i in range(N)]
    routes[k] = {'total': total,
                 'wdAvg': [round(wd[i] / wd_days[months[i]]) if wd[i] else 0 for i in range(N)]}
if renamed:
    print(f'  route keys rewritten to GTFS form: {renamed}', flush=True)
not_in_gtfs = sorted(k for k in routes if k not in set(gtfs_ids))

system = {
    'total': [sum(rec['total'][i] for rec in routes.values()) for i in range(N)],
    'wdAvg': [sum(rec['wdAvg'][i] for rec in routes.values()) for i in range(N)],
}
if system['total'][-1] < MIN_MONTH_TOTAL:
    sys.exit(f"FATAL: latest month ({months[-1]}) total {system['total'][-1]:,} "
             f'below sanity floor {MIN_MONTH_TOTAL:,} — refusing to write')

# never regress: if an existing file has a newer latest month, something is wrong
if os.path.exists(OUT):
    old = json.load(open(OUT))
    if old.get('months') and old['months'][-1] > months[-1]:
        sys.exit(f"FATAL: existing file ends {old['months'][-1]} but fetch ends {months[-1]}")

# ---------------------------------------------------------------- fare taps
# One month per query: whole-dataset GROUP BYs on these hourly tables time out
# with HTTP 500. Per month: daily system totals (coverage check), per-route
# totals, per-route weekday totals. The three must agree with each other.
print('fetching fare-tap coverage…', flush=True)
tap_hi = {}
for ds in (TAPS_2020_2024, TAPS_2025_ON):
    rng = get(SODA + ds + '.json',
              {'$select': 'min(transit_timestamp) as lo,max(transit_timestamp) as hi'}, ds)
    if not rng or not rng[0].get('hi'):
        sys.exit(f'FATAL: empty date range from fare-tap dataset {ds}')
    tap_hi[ds] = rng[0]['hi'][:19]
    print(f"  {ds}: {rng[0]['lo'][:10]} to {tap_hi[ds]}", flush=True)


def tap_month(ym):
    y, m = map(int, ym.split('-'))
    ndays = calendar.monthrange(y, m)[1]
    ds = TAPS_2020_2024 if ym <= '2024-12' else TAPS_2025_ON
    url = SODA + ds + '.json'
    nxt = f'{y + (m == 12)}-{m % 12 + 1:02d}-01'
    where = f"transit_timestamp >= '{ym}-01T00:00:00' AND transit_timestamp < '{nxt}T00:00:00'"
    # A month counts only if every day is present and the dataset runs through
    # the last hour of the month (24-hour routes always tap at 11 p.m.).
    if tap_hi[ds] < f'{ym}-{ndays:02d}T23:00:00':
        return ym, None, f'dataset ends {tap_hi[ds]}', ds
    daily = get(url, {'$select': 'date_trunc_ymd(transit_timestamp) as d,sum(ridership) as r',
                      '$where': where, '$group': 'd', '$limit': '100'}, f'{ds} {ym} daily')
    days = {r['d'][:10]: int(float(r.get('r') or 0)) for r in daily}
    if len(days) < ndays:
        return ym, None, f'{len(days)}/{ndays} days in dataset', ds
    # Days can be present with zero taps: January 2026 has rows for Jan 10-15
    # but no ridership. A day under a tenth of the month's median is a hole in
    # the upload, not a real day (the Jan 25, 2026 snowstorm Sunday was ~18%).
    med = sorted(days.values())[ndays // 2]
    thin = [d for d, v in sorted(days.items()) if v < 0.1 * med]
    if thin:
        return ym, None, f'{len(thin)} day(s) with almost no taps ({thin[0]} to {thin[-1]})', ds
    tot = get(url, {'$select': 'bus_route,sum(ridership) as r', '$where': where,
                    '$group': 'bus_route', '$limit': '5000'}, f'{ds} {ym} routes')
    wd = get(url, {'$select': 'bus_route,sum(ridership) as r',
                   # Socrata dow: 0 = Sunday, so 1-5 is Monday-Friday
                   '$where': where + ' AND date_extract_dow(transit_timestamp) between 1 and 5',
                   '$group': 'bus_route', '$limit': '5000'}, f'{ds} {ym} weekday routes')
    tot = {r['bus_route']: int(float(r.get('r') or 0)) for r in tot if r.get('bus_route')}
    wd = {r['bus_route']: int(float(r.get('r') or 0)) for r in wd if r.get('bus_route')}
    # Cross-checks: route totals must add up to the daily totals, and the
    # weekday query must match the Mon-Fri days counted here in Python (which
    # also proves the dow numbering).
    day_sum = sum(days.values())
    wd_day_sum = sum(v for d, v in days.items() if date.fromisoformat(d).weekday() < 5)
    if sum(tot.values()) != day_sum:
        sys.exit(f'FATAL: {ds} {ym}: route taps {sum(tot.values()):,} != daily taps {day_sum:,}')
    if sum(wd.values()) != wd_day_sum:
        sys.exit(f'FATAL: {ds} {ym}: weekday route taps {sum(wd.values()):,} '
                 f'!= Mon-Fri daily taps {wd_day_sum:,}')
    return ym, {'total': tot, 'wd': wd, 'day_sum': day_sum, 'wd_day_sum': wd_day_sum}, None, ds


print(f'fetching fare taps for {N} months (one query set per month)…', flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:
    tap_results = list(pool.map(tap_month, months))

taps = {}            # ym -> {'total': {live: n}, 'wd': {live: n}}
tap_unmatched = {}   # tap id -> taps over the series, for ids with no counter route
tap_sources = {}     # tap id -> live key, for ids that needed rewriting
sys_taps_total, sys_taps_wd = [None] * N, [None] * N
missing = []
for ym, res, why, ds in tap_results:
    i = midx[ym]
    if res is None:
        missing.append(f'{ym} ({why})')
        continue
    agg = {'total': {}, 'wd': {}}
    for part in ('total', 'wd'):
        for rid, n in res[part].items():
            k = live_id(rid)
            if k != rid:
                tap_sources[rid] = k
            agg[part][k] = agg[part].get(k, 0) + n
    for k, n in agg['total'].items():
        if k not in routes:
            tap_unmatched[k] = tap_unmatched.get(k, 0) + n
    taps[ym] = agg
    sys_taps_total[i] = res['day_sum']
    sys_taps_wd[i] = round(res['wd_day_sum'] / wd_days[ym])
    n_routes = sum(1 for k in routes if agg['total'].get(k, 0) > 0)
    matched = sum(agg['total'].get(k, 0) for k in routes)
    print(f'  {ym} [{ds}]: {res["day_sum"]:,} taps, {sys_taps_wd[i]:,} avg weekday, '
          f'{n_routes} tracker routes with taps, {matched / res["day_sum"]:.1%} on tracker routes',
          flush=True)
    if n_routes < MIN_TAP_ROUTES:
        sys.exit(f'FATAL: {ym}: only {n_routes} routes have fare taps — expected {MIN_TAP_ROUTES}+')
    if not TAP_WD_BAND[0] <= sys_taps_wd[i] <= TAP_WD_BAND[1]:
        sys.exit(f'FATAL: {ym}: system avg weekday taps {sys_taps_wd[i]:,} outside plausible band '
                 f'{TAP_WD_BAND[0]:,}-{TAP_WD_BAND[1]:,}')
if missing:
    print(f'  no fare taps (month not fully covered): {", ".join(missing)}', flush=True)
# Only the newest month or two may legitimately lack taps (weekly posting). A
# gap further back is either an upstream hole (tolerated for one or two months,
# left null) or broken queries (more than that: stop).
interior = [x for x in missing if x[:7] in set(months[:-2])]
if len(interior) > 2:
    sys.exit(f'FATAL: fare taps missing for {len(interior)} interior months: {interior}')
elif interior:
    print(f'  WARNING: fare taps missing for interior months: {interior}', flush=True)
if tap_sources:
    print(f'  fare-tap ids rewritten to GTFS form: {tap_sources}', flush=True)


def ratio(c, t):
    return round(c / t, 3) if c and t else None


for k, rec in routes.items():
    tt, tw = [None] * N, [None] * N
    for ym, agg in taps.items():
        i = midx[ym]
        if k in agg['total']:
            tt[i] = agg['total'][k]
            tw[i] = round(agg['wd'].get(k, 0) / wd_days[ym])
    rec['tapsTotal'], rec['tapsWdAvg'] = tt, tw
    rec['ratio'] = [ratio(rec['wdAvg'][i], tw[i]) for i in range(N)]

# Q52 SBS and Q53 SBS: the publisher reports their taps together, so the
# per-route split is not reliable. Both keys carry the COMBINED pair figure,
# flagged with tapsJoint, and the ratio is the pair's counters over the pair's
# taps. Never add these two routes' taps together.
if all(k in routes for k in TAP_JOINT):
    a, b = (routes[k] for k in TAP_JOINT)
    tt, tw = [None] * N, [None] * N
    for ym, agg in taps.items():
        if any(k in agg['total'] for k in TAP_JOINT):
            i = midx[ym]
            tt[i] = sum(agg['total'].get(k, 0) for k in TAP_JOINT)
            tw[i] = round(sum(agg['wd'].get(k, 0) for k in TAP_JOINT) / wd_days[ym])
    rr = [ratio(a['wdAvg'][i] + b['wdAvg'][i], tw[i]) if a['wdAvg'][i] and b['wdAvg'][i] else None
          for i in range(N)]
    for rec in (a, b):
        rec['tapsTotal'], rec['tapsWdAvg'], rec['ratio'] = list(tt), list(tw), list(rr)
        rec['tapsJoint'] = list(TAP_JOINT)
else:
    sys.exit(f'FATAL: expected counter routes {TAP_JOINT} for the joint-tap rule')

system['tapsTotal'] = sys_taps_total
system['tapsWdAvg'] = sys_taps_wd
system['ratio'] = [ratio(system['wdAvg'][i], sys_taps_wd[i]) for i in range(N)]

# ------------------------------------------------------- redesign breaks
# Queens Bus Network Redesign, implemented in two phases in 2025. Phase dates
# from the MTA's post-launch press release; per-route dates from the MTA's
# Project Phasing Guide (linked from that release). Routes marked "No changes"
# in the guide (Q44, Q53, Q70) are left out. Checked and NOT inside the series
# window (Oct 2024 on): the Bronx local redesign (June 2022) and the Brooklyn
# redesign (still in planning as of the project page updated Sep 11, 2026).
QUEENS_PHASING_GUIDE = 'https://www.mta.info/document/168506'
QUEENS_GUIDE_QUOTE = ('Most routes will change on either June 29 or August 31. Routes '
                      'without Sunday service will change on either June 30 or September 2.')
QUEENS_RELEASE = 'https://www.mta.info/press-release/mta-fully-implements-queens-bus-network-redesign'
QUEENS_ROUTE_DATES = {
    # Guide name: change date. "*" in the guide = discontinued on or after that date.
    'Q1': '06-29', 'Q2': '06-29', 'Q3': '06-29', 'Q4': '06-29', 'Q5': '06-29',
    'Q6': '08-31', 'Q7': '08-31', 'Q8': '08-31', 'Q9': '08-31', 'Q10': '08-31',
    'Q11': '08-31', 'Q12': '06-29', 'Q13': '06-29', 'Q14': '06-29', 'Q15': '06-29',
    'Q15A': '06-29', 'Q16': '06-29', 'Q17': '06-29', 'Q18': '08-31', 'Q19': '08-31',
    'Q20': '06-29', 'Q20A': '06-29', 'Q20B': '06-27', 'Q21': '08-31', 'Q22': '08-31',
    'Q23': '06-29', 'Q24': '08-31', 'Q25': '06-29', 'Q26': '06-29', 'Q27': '06-29',
    'Q28': '06-29', 'Q29': '06-29', 'Q30': '06-29', 'Q31': '06-29', 'Q32': '08-31',
    'Q33': '08-31', 'Q34': '06-27', 'Q35': '08-31', 'Q36': '06-29', 'Q37': '08-31',
    'Q38': '06-29', 'Q39': '06-29', 'Q40': '08-31', 'Q41': '08-31', 'Q42': '06-30',
    'Q43': '06-29', 'Q45': '06-29', 'Q46': '06-29', 'Q47': '08-31', 'Q48': '06-29',
    'Q49': '08-31', 'Q50': '06-29', 'Q51': '06-29', 'Q52': '08-31', 'Q54': '06-29',
    'Q55': '06-29', 'Q56': '08-31', 'Q58': '06-29', 'Q59': '06-29', 'Q60': '08-31',
    'Q61': '06-29', 'Q63': '06-29', 'Q64': '06-29', 'Q65': '06-29', 'Q66': '06-29',
    'Q67': '06-29', 'Q69': '08-31', 'Q72': '08-31', 'Q74': '06-29', 'Q75': '06-30',
    'Q76': '06-29', 'Q77': '06-29', 'Q80': '08-31', 'Q82': '06-29', 'Q83': '06-29',
    'Q84': '06-29', 'Q85': '06-29', 'Q86': '06-29', 'Q87': '06-29', 'Q88': '06-29',
    'Q89': '06-29', 'Q90': '06-29', 'Q98': '06-29', 'Q100': '08-31', 'Q101': '08-31',
    'Q102': '08-31', 'Q103': '08-31', 'Q104': '08-31', 'Q110': '06-29', 'Q111': '06-29',
    'Q112': '06-29', 'Q113': '06-29', 'Q114': '06-29', 'Q115': '06-29',
    'B57': '08-31', 'B62': '08-31',
    'QM1': '06-30', 'QM2': '06-29', 'QM3': '06-27', 'QM4': '06-29', 'QM5': '06-29',
    'QM6': '06-29', 'QM7': '06-30', 'QM8': '06-30', 'QM10': '06-30', 'QM11': '06-30',
    'QM12': '06-30', 'QM15': '09-02', 'QM16': '09-02', 'QM17': '09-02', 'QM18': '09-02',
    'QM20': '06-30', 'QM21': '06-30', 'QM24': '09-02', 'QM25': '09-02', 'QM31': '06-30',
    'QM32': '06-30', 'QM34': '09-02', 'QM35': '06-30', 'QM36': '06-30', 'QM40': '06-30',
    'QM42': '06-30', 'QM44': '06-30', 'X63': '06-30', 'QM63': '06-30', 'X64': '06-30',
    'QM64': '06-30', 'QM65': '06-30', 'X68': '06-30', 'QM68': '06-30',
}
QUEENS_PHASES = [
    {'id': 'queens-redesign-phase-1', 'group': 'queens-redesign', 'date': '2025-06-29',
     'label': 'Queens bus network redesign, phase 1',
     'source_url': QUEENS_RELEASE,
     'quote': 'The first phase, with nearly two thirds of the changes, launched on June 29.',
     'window': ('06-27', '06-30')},
    {'id': 'queens-redesign-phase-2', 'group': 'queens-redesign', 'date': '2025-08-31',
     'label': 'Queens bus network redesign, phase 2',
     'source_url': QUEENS_RELEASE,
     'quote': 'The second and last phase began Sunday, Aug. 31, and today marks the full '
              'implementation of the redesign.',
     'window': ('08-31', '09-02')},
]


def natural(rid):
    m = re.match(r'([A-Z]+)0*(\d+)(.*)', rid)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (rid, 0, '')


def route_key(guide_name):
    """Guide names are bare (Q52 means the Q52 SBS); find the tracker key."""
    for cand in (live_id(guide_name), live_id(guide_name + '+')):
        if cand in routes:
            return cand
    return None


breaks, unmatched_breaks = [], []
for ph in QUEENS_PHASES:
    lo, hi = ph['window']
    route_dates = {}
    for name, md in QUEENS_ROUTE_DATES.items():
        if not lo <= md <= hi:
            continue
        k = route_key(name)
        if k is None:
            unmatched_breaks.append(name)
            continue
        d = f'2025-{md}'
        route_dates[k] = d
        bm = routes[k].setdefault('breakMonths', [])
        if d[:7] not in bm:
            bm.append(d[:7])
            bm.sort()
    if ph['date'][:7] in midx:
        breaks.append({
            'id': ph['id'], 'group': ph['group'], 'date': ph['date'], 'label': ph['label'],
            'source_url': ph['source_url'], 'quote': ph['quote'],
            'routes': sorted(route_dates, key=natural),
            'routeDates': dict(sorted(route_dates.items())),
            'routes_source_url': QUEENS_PHASING_GUIDE,
            'routes_quote': QUEENS_GUIDE_QUOTE,
        })
print('redesign breaks: ' + ', '.join(f"{b['id']} {b['date']} ({len(b['routes'])} routes)"
                                    for b in breaks), flush=True)
if unmatched_breaks:
    print(f'  guide routes with no counter data: {unmatched_breaks}', flush=True)

# ------------------------------------------------------------------ write
out = {
    'updated': date.today().isoformat(),
    'source': 'MTA Bus Stop Level Ridership (data.ny.gov fvdm-uavx), boardings recorded by '
              'Automatic Passenger Counters on board MTA buses.',
    'tapsSource': 'MTA Bus Hourly Ridership (data.ny.gov kv7t-n8in for months through 2024, '
                  'gxb3-akrn from January 2025), OMNY and MetroCard entries by route.',
    'definitions': {
        'total': 'All boardings recorded on the route that month, every day of the week.',
        'wdAvg': 'Monday-Friday boardings that month divided by the number of calendar '
                 'weekdays in the month. Public holidays are counted as weekdays, so months '
                 'containing them read slightly low.',
        'months': 'Only calendar months with data for every day are included; partial months '
                  'at either end of the series are dropped.',
        'caveat': 'Counters miss some riders and not every bus carries one. The MTA publishes '
                  'these as estimates.',
        'tapsTotal': 'Fare taps: every OMNY tap and MetroCard swipe that let a rider onto a bus '
                     'on the route that month, including free transfers from another bus or the '
                     'subway. It is a count of paid entries, not of riders: people who board '
                     'without paying are not in it, and the MTA estimates that a very large share '
                     'of bus riders do not pay (about 45 to 50 percent on local buses in 2024-2026, '
                     'MTA Bus Fare Evasion dataset, data.ny.gov uv5h-dfhp). Null where the fare '
                     'dataset does not cover every day of the month (a day with almost no taps, '
                     'such as Jan 10-15, 2026, counts as missing), or where the route has no rows '
                     'in it that month.',
        'tapsWdAvg': 'Monday-Friday fare taps that month divided by the number of calendar '
                     'weekdays in the month, the same denominator as wdAvg.',
        'ratio': 'Passenger-counter boardings per fare tap: wdAvg divided by tapsWdAvg, rounded '
                 'to three decimals. Null where either is missing or zero. A ratio of 1.5 means '
                 'the counters logged three boardings for every two paid entries. Read it as a '
                 'calibration between two incomplete counts, not as an evasion rate. If the '
                 'counters caught every rider, the MTA evasion estimate implies a ratio near 2 on '
                 'local routes; in the 2024-2026 data the system-wide ratio sits only a little '
                 'above 1, and on about half of routes the counters log fewer boardings than '
                 'there were paid taps. So the counter figures in this file are not a complete '
                 'count of riders (see caveat), and a route\'s ratio reflects how much of its '
                 'service was counted as well as how many riders skipped the fare. That is why it '
                 'matters: when a route\'s counters fall while its taps hold steady, the counting '
                 'changed, not the riders. And if buses go fare-free, taps stop and counters are '
                 'the only measure left; this series records how the two lined up, route by '
                 'route, beforehand.',
        'system.tapsTotal': 'Every fare tap in the dataset that month, all routes, including any '
                            'that have no counter data (see tapsUnmatched).',
        'tapsJoint': 'The MTA notes that fare data for the Q52 SBS and Q53 SBS are reported '
                     'together, so the split between them is not reliable. Both routes carry the '
                     'COMBINED taps of the pair, and their ratio is the pair\'s combined counters '
                     'over the pair\'s combined taps. Do not add the two routes\' taps together.',
        'routeIds': 'Route keys use the spelling of the live MTA feed and GTFS (for example Q06, '
                    'not Q6). Counter and fare-tap ids are matched after uppercasing and '
                    'dropping leading zeros after the letter prefix; routeIdChanges lists every '
                    'counter id that was rewritten.',
        'breaks': 'Dates when a route\'s ridership stops being comparable with its own history '
                  'because the route itself changed. The Queens bus network redesign took effect '
                  'in two phases in 2025: routes were renumbered, rerouted, merged and created, so '
                  'a Queens route before its change date is not the same route afterward. Each '
                  'route\'s exact date is in routeDates; breakMonths on a route lists the '
                  'month(s) containing its change date. Checked and not inside this series: the '
                  'Bronx local bus network redesign, implemented June 2022, and the Brooklyn '
                  'redesign, still in planning (mta.info/project/brooklyn-bus-network-redesign, '
                  'updated Sep 11, 2026).',
    },
    'months': months,
    'wdDays': wd_days,
    'system': system,
    'routes': routes,
    'breaks': breaks,
    'routeIdChanges': dict(sorted(renamed.items())),
    'tapsUnmatched': dict(sorted((k, v) for k, v in tap_unmatched.items() if v > 0)),
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
li = N - 1
lt = max((i for i in range(N) if sys_taps_wd[i]), default=None)
print(f"wrote {os.path.normpath(OUT)}: {len(routes)} routes × {N} months "
      f"(latest {months[-1]}: {system['total'][-1]:,} boardings, "
      f"{system['wdAvg'][-1]:,} avg weekday)")
if lt is not None:
    print(f"  fare taps through {months[lt]}: {sys_taps_wd[lt]:,} avg weekday, "
          f"counters/taps {system['ratio'][lt]}")
if not_in_gtfs:
    print(f'  counter routes not in GTFS (kept as-is): {not_in_gtfs}')
print(f'  done in {time.time() - T0:.0f}s')
