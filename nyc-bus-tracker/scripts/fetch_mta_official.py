#!/usr/bin/env python3
"""
Pull the MTA's own published bus metrics and line them up against the tracker.
Writes data/mta/official.json, which build_findings.js folds into findings.json
for the "Checked against the MTA" section of findings.html.

Runs weekly (bus-tracker-findings.yml). The MTA publishes these monthly, about
six weeks behind, so most weeks nothing changes; that is expected.

Datasets (data.ny.gov, SODA):
  r6db-kkzj  MTA Central Business District Bus Speeds: Beginning 2023
             route x month x day type x hour, timepoint to timepoint, all routes
  cudb-vcni  MTA Bus Speeds: Beginning 2015 (the headline monthly speed)
  v4z4-2h6n  MTA Bus Wait Assessment: Beginning 2015
  8mkn-d32t  MTA Bus Customer Journey-Focused Metrics: Beginning 2017
  sayj-mze2  MTA Daily Ridership and Traffic: Beginning 2020 (mode = Bus)

Our side comes from data/summary/monthly.json, monthly-routes.json and
data/ridership/routes-monthly.json (the MTA passenger-counter data).

How the speeds are matched: the tracker averages routes equally and gives each
hour of the day equal weight, 6 a.m. to midnight. The MTA series here is built
the same way from r6db-kkzj: for each hour 6-23, the plain mean of route speeds
(route miles / route hours), then the plain mean across hours. The MTA's
headline figure (cudb-vcni, weighted by mileage) is reported alongside.

Fails loud (exit 1) on empty or implausible responses.
"""
import json, os, re, sys, time, statistics as st, calendar, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, date

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'data', 'mta', 'official.json')
SODA = 'https://data.ny.gov/resource/{}.json'
START = '2025-10'          # months of context shown on the chart
EXPRESS = re.compile(r'^(BM|BXM|QM|SIM|X)\d', re.I)


def die(msg):
    print(f'fetch_mta_official: {msg}', file=sys.stderr)
    sys.exit(1)


def soda(ds, query, tries=5):
    url = SODA.format(ds) + '?' + urllib.parse.urlencode({'$query': query})
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'nyc-bus-tracker'}), timeout=120) as r:
                rows = json.load(r)
            if not isinstance(rows, list):
                raise ValueError(f'unexpected response: {str(rows)[:200]}')
            return rows
        except Exception as e:  # keyless SODA throttles with 403/429; back off
            if i == tries - 1:
                die(f'{ds} failed after {tries} tries: {e}')
            time.sleep(5 * (i + 1))


def read(p):
    with open(os.path.join(ROOT, p)) as f:
        return json.load(f)


def months_between(a, b):
    y, m = map(int, a.split('-'))
    out = []
    while f'{y:04d}-{m:02d}' <= b:
        out.append(f'{y:04d}-{m:02d}')
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0


def weekdays_in(month):
    y, m = map(int, month.split('-'))
    return sum(1 for d in range(1, calendar.monthrange(y, m)[1] + 1) if date(y, m, d).weekday() < 5)


def month_name(m):
    return datetime.strptime(m, '%Y-%m').strftime('%B %Y')


# ── MTA: latest month ──
latest = soda('cudb-vcni', 'SELECT max(month) AS m')
if not latest or not latest[0].get('m'):
    die('cudb-vcni returned no max month')
LAST = latest[0]['m'][:7]
MONTHS = months_between(START, LAST)
print('MTA speeds published through', LAST)

# ── MTA: headline speed (mileage weighted) ──
head = {r['month'][:7]: float(r['mi']) / float(r['hrs']) for r in soda('cudb-vcni',
        f"SELECT month, sum(total_mileage) AS mi, sum(total_operating_time) AS hrs WHERE month >= '{START}-01T00:00:00' GROUP BY month")}

# ── MTA: method-matched speed + route speeds, 6am-midnight ──
mta_matched, mta_route = {}, {}
for m in MONTHS:
    rows = soda('r6db-kkzj', f"SELECT hour_of_day, route_id, sum(sum_mileage) AS mi, sum(sum_time) AS hrs "
                             f"WHERE month = '{m}-01T00:00:00' AND hour_of_day >= 6 GROUP BY hour_of_day, route_id LIMIT 50000")
    if not rows:
        print(f'  r6db-kkzj has nothing for {m} yet')
        continue
    by_hour = defaultdict(list)
    route_tot = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        mi, hrs = float(r['mi']), float(r['hrs'])
        if hrs <= 0:
            continue
        by_hour[int(r['hour_of_day'])].append(mi / hrs)
        route_tot[r['route_id']][0] += mi
        route_tot[r['route_id']][1] += hrs
    if len(by_hour) < 15 or len(route_tot) < 250:
        die(f'r6db-kkzj {m}: only {len(by_hour)} hours / {len(route_tot)} routes')
    mta_matched[m] = st.mean(st.mean(v) for v in by_hour.values())
    mta_route[m] = {k: v[0] / v[1] for k, v in route_tot.items()}
    if not 5 < mta_matched[m] < 15:
        die(f'implausible matched speed {m}: {mta_matched[m]}')
    time.sleep(1)

# ── MTA: wait assessment and extra time at stops ──
wa = {r['month'][:7]: float(r['p']) / float(r['s']) for r in soda('v4z4-2h6n',
      f"SELECT month, sum(number_of_trips_passing_wait) AS p, sum(number_of_scheduled_trips) AS s WHERE month >= '{START}-01T00:00:00' GROUP BY month")}
cj_rows = soda('8mkn-d32t', f"SELECT month, number_of_customers, additional_bus_stop_time WHERE month >= '{START}-01T00:00:00' LIMIT 50000")
cj_acc = defaultdict(lambda: [0.0, 0.0])
for r in cj_rows:
    try:
        n, t = float(r['number_of_customers']), float(r['additional_bus_stop_time'])
    except (KeyError, TypeError, ValueError):
        continue
    cj_acc[r['month'][:7]][0] += n * t
    cj_acc[r['month'][:7]][1] += n
abst = {m: a / n for m, (a, n) in cj_acc.items() if n}
if not wa or not abst:
    die('wait assessment or journey metrics came back empty')

# ── MTA: fare-based daily ridership, weekday average per month ──
daily = soda('sayj-mze2', f"SELECT date, count WHERE mode = 'Bus' AND date >= '2024-10-01T00:00:00' ORDER BY date LIMIT 50000")
if len(daily) < 300:
    die(f'sayj-mze2 returned only {len(daily)} days')
wd_sum, days_seen = defaultdict(float), defaultdict(set)
for r in daily:
    d = datetime.strptime(r['date'][:10], '%Y-%m-%d').date()
    days_seen[r['date'][:7]].add(d.day)
    if d.weekday() < 5:
        wd_sum[r['date'][:7]] += float(r['count'])
daily_wd = {m: wd_sum[m] / weekdays_in(m) for m in wd_sum
            if len(days_seen[m]) == calendar.monthrange(*map(int, m.split('-')))[1]}

# ── ours ──
ours_month = {r['period']: r for r in read('data/summary/monthly.json')}
ours_routes = read('data/summary/monthly-routes.json')
counter = read('data/ridership/routes-monthly.json')
counter_wd = dict(zip(counter['months'], counter['system']['wdAvg']))


def ours_usable(m):
    r = ours_month.get(m)
    if not r or r.get('avgSpeedHourNorm') is None:
        return False
    full_days = calendar.monthrange(*map(int, m.split('-')))[1]
    return r['days'] == full_days and r['coveragePct'] >= 50


paired = [m for m in MONTHS if m in mta_matched and ours_usable(m)]
if not paired:
    die('no month has both usable tracker data and MTA speeds')
P = paired[-1]
print('latest paired month', P, '; all paired', paired)

# route-level comparison for the latest paired month
pairs = []
for route, recs in ours_routes.items():
    rec = next((x for x in recs if x['period'] == P and x.get('avgSpeed') is not None and x.get('daysSeen', 0) >= 20), None)
    if rec and route in mta_route[P]:
        pairs.append((route, rec['avgSpeed'], mta_route[P][route]))
if len(pairs) < 200:
    die(f'only {len(pairs)} routes paired for {P}')
rho = spearman([p[1] for p in pairs], [p[2] for p in pairs])
local = [p for p in pairs if not EXPRESS.match(p[0])]
sim = [p for p in pairs if p[0].upper().startswith('SIM')]
local_ratio = st.median(p[1] / p[2] for p in local)
sim_ratio = st.median(p[1] / p[2] for p in sim) if sim else None
by_route = {p[0]: p for p in pairs}
examples = [by_route[r] for r in ['B41', 'M15+', 'BX19', 'SIM22'] if r in by_route]

pct = lambda x: f'{round(abs(x - 1) * 100)}%'
f1 = lambda x: f'{x:.1f}'
paired_prev = paired[-2] if len(paired) > 1 else None

# ridership: how far apart the two MTA counts run, over the last 12 shared months
shared = [m for m in counter['months'] if m in daily_wd][-12:]
ratios = [counter_wd[m] / daily_wd[m] for m in shared]
lastR = shared[-1] if shared else None

metrics = [
    {'label': 'Average speed, whole system', 'period': month_name(P),
     'ours': f"{f1(ours_month[P]['avgSpeedHourNorm'])} mph", 'mta': f"{f1(mta_matched[P])} mph",
     'why': f"Both averaged the same way: every route counts equally, every hour from 6 a.m. to midnight counts equally. The MTA's headline figure, which weights by miles driven, was {f1(head[P])} mph; long, slow local runs pull it down."},
    {'label': 'Local routes, typical gap', 'period': month_name(P),
     'ours': f'{pct(local_ratio)} {"faster" if local_ratio > 1 else "slower"}', 'mta': 'baseline',
     'why': f"Median across {len(local)} local, limited and Select Bus Service routes. Likely cause: the tracker drops readings under 0.5 mph, so time spent stopped at stops and lights is left out, while the MTA counts it."},
]
if sim_ratio:
    metrics.append({'label': 'Staten Island express (SIM)', 'period': month_name(P),
                    'ours': f'{pct(sim_ratio)} {"faster" if sim_ratio > 1 else "slower"}', 'mta': 'baseline',
                    'why': f'Median across {len(sim)} SIM routes. This runs opposite to the local gap, and the cause is not yet known.'})
if lastR:
    metrics.append({'label': 'Weekday riders', 'period': month_name(lastR),
                    'ours': f"{counter_wd[lastR] / 1e6:.2f}M (MTA counters)", 'mta': f"{daily_wd[lastR] / 1e6:.2f}M (MTA daily count)",
                    'why': 'Both are MTA numbers. The first comes from passenger counters on board; the second is the MTA\'s daily bus ridership estimate. The riders chart above uses the counters.'})

flags = [
    {'head': 'Routes line up almost exactly',
     'text': f'Rank the {len(pairs)} routes both sources cover from slowest to fastest, and the two lists nearly match (rank correlation {rho:.2f}, where 1 is identical).',
     'detail': 'For comparing routes with each other, the tracker and the MTA tell the same story.'},
    {'head': 'Local buses read faster here',
     'text': f'On the typical local route the tracker reads {pct(local_ratio)} faster than the MTA. '
             + '; '.join(f'{r}: {f1(o)} mph here, {f1(t)} MTA' for r, o, t in examples if not r.startswith('SIM')) + '.',
     'detail': 'Treat the tracker\'s speed as speed while moving. The biggest gaps are on slow, crowded routes, where buses spend the most time stopped.'},
]
if sim_ratio:
    s22 = by_route.get('SIM22')
    flags.append({'head': 'Staten Island express buses read slower here',
                  'text': f'The opposite happens on SIM express routes: the tracker reads them {pct(sim_ratio)} slower.'
                          + (f' SIM22: {f1(s22[1])} mph here, {f1(s22[2])} MTA.' if s22 else ''),
                  'detail': 'Not yet explained. Candidates include positions that refresh less often on highway stretches. The borough chart keeps express routes in their own group for this reason.'})
if paired_prev:
    d_ours = ours_month[P]['avgSpeedHourNorm'] - ours_month[paired_prev]['avgSpeedHourNorm']
    d_mta = mta_matched[P] - mta_matched[paired_prev]
    flags.append({'head': 'Small monthly moves are noise here',
                  'text': f'From {month_name(paired_prev)} to {month_name(P)} the tracker moved {d_ours:+.1f} mph and the MTA, averaged the same way, {d_mta:+.1f} mph.',
                  'detail': 'Changes of a few tenths are within the tracker\'s noise: which late-evening hours the collector caught shifts from month to month.'})
if ratios:
    flags.append({'head': 'The MTA\'s two ridership counts disagree',
                  'text': f'Over the last {len(ratios)} months, the passenger-counter figure ran anywhere from {round(min(ratios) * 100)}% to {round(max(ratios) * 100)}% of the MTA\'s daily bus ridership count.',
                  'detail': 'So a month-to-month change in riders depends on which count you use. Say which one.'})

series_months = [m for m in MONTHS if m in mta_matched]
out = {
    'fetchedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'intro': f'The tracker makes its own estimates from GPS positions. Here they are set beside what the MTA publishes, which runs about six weeks behind. The latest month both sources cover is {month_name(P)}.',
    'pairedMonth': P,
    'speedSeries': {
        'title': 'Average speed, averaged the same way',
        'sub': 'mph; every route and every hour from 6 a.m. to midnight weighted equally',
        'mtaLabel': 'MTA published data',
        'months': series_months,
        'ours': [round(ours_month[m]['avgSpeedHourNorm'], 2) if ours_usable(m) else None for m in series_months],
        'mta': [round(mta_matched[m], 2) for m in series_months],
        'notes': [None if ours_usable(m) or m not in ours_month else 'Tracker left out: too little of the month captured.' for m in series_months],
    },
    'metrics': metrics,
    'flags': flags,
    'numbers': {
        'routesPaired': len(pairs), 'rankCorrelation': round(rho, 3),
        'localMedianRatio': round(local_ratio, 3), 'simMedianRatio': round(sim_ratio, 3) if sim_ratio else None,
        'mtaHeadline': {m: round(v, 2) for m, v in head.items()},
        'mtaMatched': {m: round(v, 2) for m, v in mta_matched.items()},
        'waitAssessment': {m: round(v, 4) for m, v in wa.items()},
        'additionalBusStopTime': {m: round(v, 2) for m, v in abst.items()},
        'dailyRidershipWeekdayAvg': {m: round(v) for m, v in daily_wd.items() if m >= START},
        'counterToDailyRatio': {m: round(r, 3) for m, r in zip(shared, ratios)},
    },
    'sources': [
        {'name': 'Bus speeds by hour (r6db-kkzj)', 'url': 'https://data.ny.gov/d/r6db-kkzj', 'through': month_name(max(mta_matched))},
        {'name': 'Bus speeds (cudb-vcni)', 'url': 'https://data.ny.gov/d/cudb-vcni', 'through': month_name(LAST)},
        {'name': 'Wait assessment (v4z4-2h6n)', 'url': 'https://data.ny.gov/d/v4z4-2h6n', 'through': month_name(max(wa))},
        {'name': 'Customer journey metrics (8mkn-d32t)', 'url': 'https://data.ny.gov/d/8mkn-d32t', 'through': month_name(max(abst))},
        {'name': 'Daily ridership (sayj-mze2)', 'url': 'https://data.ny.gov/d/sayj-mze2', 'through': daily[-1]['date'][:10]},
    ],
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    json.dump(out, f, indent=1)
print(json.dumps({k: out['numbers'][k] for k in ['routesPaired', 'rankCorrelation', 'localMedianRatio', 'simMedianRatio', 'mtaMatched']}, indent=1))
for fl in flags:
    print('-', fl['head'], '|', fl['text'])
