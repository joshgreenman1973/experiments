"""
Pull the MTA's own published bus metrics and line them up against the tracker.
Writes data/mta/official.json (folded into findings.json for the "Checked
against the MTA" section), data/mta/routes.json (MTA monthly speed per route,
for route.html) and appends to data/mta/nowcasts.json (the tracker's running
forecasts of the MTA's next monthly figure, kept so they can be scored).

Runs from bus-tracker-findings.yml. The MTA publishes monthly, about six weeks
behind, so most runs change nothing; that is expected.

Datasets (data.ny.gov, SODA):
  r6db-kkzj  MTA bus speeds by route, month, day type (Weekday/Weekend),
             hour and route type (Local, Limited, SBS, Express)
  cudb-vcni  MTA Bus Speeds: Beginning 2015 (the headline monthly speed,
             weighted by miles driven)
  v4z4-2h6n  Wait assessment;  8mkn-d32t  customer journey metrics
  sayj-mze2  Daily ridership (mode = Bus)

Matching. The tracker's index (method version 2) counts each local, limited
and Select Bus Service route once, gives each Eastern clock hour from 6 a.m.
to 10:59 p.m. equal weight, keeps weekdays and weekends apart and blends them
5 to 2. The MTA side is built the same way from r6db-kkzj: per day type and
hour, the plain mean of route speeds (route miles / route hours) over the same
route types, then the mean over hours, then 5:2. Express routes are compared
separately. The tracker's "speed with stops" is the like-for-like figure;
its moving-only speed is shown alongside to explain the old 9% gap.

Fails loud (exit 1) on empty or implausible responses.
"""
import json, os, re, sys, time, statistics as st, calendar, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, date

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'data', 'mta', 'official.json')
ROUTES_OUT = os.path.join(ROOT, 'data', 'mta', 'routes.json')
NOWCASTS = os.path.join(ROOT, 'data', 'mta', 'nowcasts.json')
SODA = 'https://data.ny.gov/resource/{}.json'
START = '2025-10'          # months of context on the tracker-vs-MTA chart
SEASON_START = '2019-01'   # months of context on the season chart
HOURS = (6, 22)
LOCAL_TYPES = {'Local', 'Limited', 'SBS'}
EXPRESS = re.compile(r'^(BM|BXM|QM|SIM|X)\d', re.I)


def die(msg):
    print(f'fetch_mta_official: {msg}', file=sys.stderr)
    sys.exit(1)


def soda(ds, query, tries=6):
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


def read(p, optional=False):
    path = os.path.join(ROOT, p)
    if optional and not os.path.exists(path):
        return None
    with open(path) as f:
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


def prev_month(m):
    y, mo = map(int, m.split('-'))
    return f'{y - 1:04d}-12' if mo == 1 else f'{y:04d}-{mo - 1:02d}'


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


# ── MTA side ────────────────────────────────────────────────────────────────
latest = soda('cudb-vcni', 'SELECT max(month) AS m')
if not latest or not latest[0].get('m'):
    die('cudb-vcni returned no max month')
LAST = latest[0]['m'][:7]
MONTHS = months_between(START, LAST)
print('MTA speeds published through', LAST)

full = {r['month'][:7]: float(r['mi']) / float(r['hrs']) for r in soda('cudb-vcni',
        f"SELECT month, sum(total_mileage) AS mi, sum(total_operating_time) AS hrs WHERE month >= '{SEASON_START}-01T00:00:00' GROUP BY month")}
if len(full) < 60:
    die(f'cudb-vcni returned only {len(full)} months of history')
head = {m: v for m, v in full.items() if m >= START}

mta_local, mta_express, mta_route_wd, mta_route_all = {}, {}, {}, {}
for m in MONTHS:
    rows = soda('r6db-kkzj', f"SELECT day_type, route_type, hour_of_day, route_id, sum(sum_mileage) AS mi, sum(sum_time) AS hrs "
                             f"WHERE month = '{m}-01T00:00:00' AND hour_of_day >= {HOURS[0]} AND hour_of_day <= {HOURS[1]} "
                             f"GROUP BY day_type, route_type, hour_of_day, route_id LIMIT 100000")
    if not rows:
        print(f'  r6db-kkzj has nothing for {m} yet')
        continue
    cell = defaultdict(list)                      # (group, day_type, hour) -> route speeds
    rwd = defaultdict(list)                       # route -> weekday hour speeds
    rtot = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        mi, hrs = float(r['mi']), float(r['hrs'])
        if hrs <= 0:
            continue
        group = 'local' if r['route_type'] in LOCAL_TYPES else 'express' if r['route_type'] == 'Express' else None
        if group is None:
            continue
        cell[(group, r['day_type'], int(r['hour_of_day']))].append(mi / hrs)
        if r['day_type'] == 'Weekday':
            rwd[r['route_id']].append(mi / hrs)
        rtot[r['route_id']][0] += mi
        rtot[r['route_id']][1] += hrs

    def blend(group):
        vals = {}
        for dt in ('Weekday', 'Weekend'):
            hs = [st.mean(cell[(group, dt, h)]) for h in range(HOURS[0], HOURS[1] + 1) if cell.get((group, dt, h))]
            if len(hs) < HOURS[1] - HOURS[0] + 1:
                return None
            vals[dt] = st.mean(hs)
        return (5 * vals['Weekday'] + 2 * vals['Weekend']) / 7
    mta_local[m], mta_express[m] = blend('local'), blend('express')
    mta_route_wd[m] = {k: st.mean(v) for k, v in rwd.items()}
    mta_route_all[m] = {k: v[0] / v[1] for k, v in rtot.items() if v[1] > 0}
    if mta_local[m] is None or not 4 < mta_local[m] < 15 or len(mta_route_wd[m]) < 250:
        die(f'implausible r6db-kkzj {m}: local {mta_local[m]}, {len(mta_route_wd[m])} routes')
    time.sleep(1)

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

daily = soda('sayj-mze2', f"SELECT date, count WHERE mode = 'Bus' AND date >= '2024-10-01T00:00:00' ORDER BY date LIMIT 50000")
daily = [r for r in daily if r.get('count') not in (None, '')]
if len(daily) < 300:
    die(f'sayj-mze2 returned only {len(daily)} counted days')
wd_sum, days_seen = defaultdict(float), defaultdict(set)
for r in daily:
    d = datetime.strptime(r['date'][:10], '%Y-%m-%d').date()
    days_seen[r['date'][:7]].add(d.day)
    if d.weekday() < 5:
        wd_sum[r['date'][:7]] += float(r['count'])
daily_wd = {m: wd_sum[m] / weekdays_in(m) for m in wd_sum
            if len(days_seen[m]) == calendar.monthrange(*map(int, m.split('-')))[1]}

# ── our side (method version 2) ─────────────────────────────────────────────
monthly = read('data/summary/monthly.json')
if monthly.get('methodVersion') != 2:
    die('data/summary/monthly.json is not method version 2')
ours = {p['period']: p for p in monthly['periods']}
ours_routes = read('data/summary/monthly-routes.json')
counter = read('data/ridership/routes-monthly.json')
counter_wd = dict(zip(counter['months'], counter['system']['wdAvg']))


def usable(m):
    p = ours.get(m)
    return bool(p and p['comparable'] and p['idx']['all'] is not None)


paired = [m for m in MONTHS if mta_local.get(m) and usable(m)]
if not paired:
    die('no month has both comparable tracker data and MTA speeds')
P = paired[-1]
print('latest paired month', P, '; all paired', paired)

pairs = []   # (route, ours with stops, ours moving, MTA) — weekdays, hour-equal
for route, periods in ours_routes['routes'].items():
    rec = next((x for x in periods if x['p'] == P and x['cwd'] and x['wd'] and x['wd'].get('all') is not None), None)
    mta = mta_route_wd[P].get(route) or mta_route_wd[P].get(re.sub(r'^([A-Z]+)0+(\d)', r'\1\2', route))
    if rec and mta:
        pairs.append((route, rec['wd']['all'], rec['wd']['mov'], mta))
if len(pairs) < 200:
    die(f'only {len(pairs)} routes paired for {P}')
rho = spearman([p[1] for p in pairs], [p[3] for p in pairs])
local = [p for p in pairs if not EXPRESS.match(p[0])]
sim = [p for p in pairs if p[0].upper().startswith('SIM')]
ratio_all = st.median(p[1] / p[3] for p in local)
ratio_mov = st.median(p[2] / p[3] for p in local)
sim_ratio = st.median(p[1] / p[3] for p in sim) if sim else None
by_route = {p[0]: p for p in pairs}
examples = [by_route[r] for r in ['B41', 'M15+', 'BX19', 'SIM22'] if r in by_route]

shared = [m for m in counter['months'] if m in daily_wd][-12:]
ratios = [counter_wd[m] / daily_wd[m] for m in shared]
lastR = shared[-1] if shared else None

pct = lambda x: f'{round(abs(x - 1) * 100)}%'
f1 = lambda x: f'{x:.1f}'
fd = lambda x: f'{x:+.1f}'
side = lambda x: 'faster' if x > 1 else 'slower'

metrics = [
    {'label': 'Local routes, whole system', 'period': month_name(P),
     'ours': f"{f1(ours[P]['idx']['all'])} mph", 'mta': f"{f1(mta_local[P])} mph",
     'why': "Built the same way on both sides: local, limited and Select Bus Service routes each count once; every hour from 6 a.m. to 11 p.m. counts equally; weekdays and weekends are averaged separately and blended 5 to 2. The tracker's figure includes time stopped and reads below the MTA's; the next two rows say why. "
            f"The MTA's headline figure, which weights routes by the miles they run and covers all hours, was {f1(head[P])} mph."},
    {'label': 'Typical local route, speed with stops', 'period': month_name(P),
     'ours': f'{pct(ratio_all)} {side(ratio_all)}', 'mta': 'baseline',
     'why': f'Median across {len(local)} local, limited and Select Bus Service routes, weekdays. Straight lines between GPS fixes about 40 seconds apart cut corners on turning routes, which makes it read low.'},
    {'label': 'Typical local route, moving speed only', 'period': month_name(P),
     'ours': f'{pct(ratio_mov)} {side(ratio_mov)}', 'mta': 'baseline',
     'why': 'The tracker\'s original measure, which drops readings under 0.5 mph. Leaving out time stopped makes it read fast.'},
]
if sim_ratio:
    metrics.append({'label': 'Staten Island express (SIM)', 'period': month_name(P),
                    'ours': f'{pct(sim_ratio)} {side(sim_ratio)}', 'mta': 'baseline',
                    'why': f'Median across {len(sim)} SIM routes, speed with stops. Express buses are kept out of the tracker\'s index.'})
if lastR:
    metrics.append({'label': 'Weekday riders', 'period': month_name(lastR),
                    'ours': f"{counter_wd[lastR] / 1e6:.2f}M (MTA counters)", 'mta': f"{daily_wd[lastR] / 1e6:.2f}M (MTA daily count)",
                    'why': 'Both are MTA numbers. The first comes from passenger counters on board; the second is the MTA\'s daily bus ridership estimate. The riders chart above uses the counters.'})

flags = [
    {'head': 'Routes line up almost exactly',
     'text': f'Rank the {len(pairs)} routes both sources cover from slowest to fastest, and the two lists nearly match (rank correlation {rho:.2f}, where 1 is identical).',
     'detail': 'For comparing routes with each other, the tracker and the MTA tell the same story.'},
    {'head': 'The MTA figure falls between the tracker\'s two measures' if ratio_all < 1 < ratio_mov else 'How the two measures compare with the MTA',
     'text': f'On the typical local route, moving-only speed reads {pct(ratio_mov)} {side(ratio_mov)} than the MTA, and speed with stops reads {pct(ratio_all)} {side(ratio_all)}. '
             + '; '.join(f'{r}: {f1(a)} mph with stops, {f1(mv)} moving, {f1(t)} MTA' for r, a, mv, t in examples if not r.startswith('SIM')) + '.',
     'detail': 'Moving speed leaves out time stopped, so it reads high. Speed with stops measures straight lines between GPS fixes about 40 seconds apart, which cut corners on routes that turn, so it reads low. Both rank routes the same way and move with the MTA from month to month, which is what the tracker is for.'},
]
if sim_ratio and abs(sim_ratio - 1) > 0.05:
    s22 = by_route.get('SIM22')
    flags.append({'head': 'Staten Island express buses read slower here',
                  'text': f'SIM express routes read {pct(sim_ratio)} {side(sim_ratio)} than the MTA.'
                          + (f' SIM22: {f1(s22[1])} mph here, {f1(s22[3])} MTA.' if s22 else ''),
                  'detail': 'Not yet explained. Candidates include positions that refresh less often on highway stretches. Express routes are kept out of the index for this reason.'})
prev_paired = [m for m in paired if m < P]
if prev_paired:
    a = prev_paired[-1]
    d_ours = ours[P]['idx']['all'] - ours[a]['idx']['all']
    d_mta = mta_local[P] - mta_local[a]
    flags.append({'head': 'Month to month, the two move together',
                  'text': f'From {month_name(a)} to {month_name(P)} the tracker moved {fd(d_ours)} mph and the MTA, built the same way, {fd(d_mta)} mph.',
                  'detail': 'Moves of a tenth or two are within the noise of either source.'})
if ratios:
    flags.append({'head': 'The MTA\'s two ridership counts disagree',
                  'text': f'Over the last {len(ratios)} months, the passenger-counter figure ran anywhere from {round(min(ratios) * 100)}% to {round(max(ratios) * 100)}% of the MTA\'s daily bus ridership count.',
                  'detail': 'So a month-to-month change in riders depends on which count you use. Say which one.'})

# ── nowcast of the MTA headline ─────────────────────────────────────────────
# Next month's MTA headline ≈ last published headline × the tracker's own
# change (speed with stops, local index) between the two months. Scored
# against every month where both are known.
backtest = []
for m in paired:
    a = prev_month(m)
    if a in head and usable(a):
        pred = head[a] * ours[m]['idx']['all'] / ours[a]['idx']['all']
        backtest.append({'month': m, 'predicted': round(pred, 2), 'actual': round(head[m], 2), 'error': round(pred - head[m], 2)})
nowcast = None
target = [m for m in sorted(ours) if m > LAST and usable(m) and prev_month(m) in head and usable(prev_month(m))]
if target:
    m = target[0]
    a = prev_month(m)
    value = round(head[a] * ours[m]['idx']['all'] / ours[a]['idx']['all'], 2)
    errs = [abs(b['error']) for b in backtest]
    nowcast = {'month': m, 'value': value, 'basedOn': a, 'mtaBase': round(head[a], 2),
               'oursBase': ours[a]['idx']['all'], 'oursNow': ours[m]['idx']['all'],
               'backtest': backtest, 'typicalError': round(st.mean(errs), 2) if errs else None,
               'text': f"The MTA has not yet published {month_name(m)}. If its headline figure moves the way the tracker did, it will come in near {value:.2f} mph, "
                       f"{abs(value - head[a]):.2f} {'below' if value < head[a] else 'above'} {month_name(a)}'s {head[a]:.2f}."
                       + ((f" Made this way, the forecast for {month_name(backtest[-1]['month'])} would have missed by {abs(backtest[-1]['error']):.2f} mph." if len(errs) == 1
                           else f" Made this way, forecasts for the {len(errs)} earlier months missed by {st.mean(errs):.2f} mph on average.") if errs else ' There is no track record yet.')}
log = read('data/mta/nowcasts.json', optional=True) or {'about': 'Running forecasts of the MTA headline bus speed (cudb-vcni), recorded when made and scored when the MTA publishes.', 'forecasts': []}
if nowcast and not any(f['month'] == nowcast['month'] and f['value'] == nowcast['value'] for f in log['forecasts']):
    log['forecasts'].append({'month': nowcast['month'], 'value': nowcast['value'], 'madeAt': datetime.now(timezone.utc).isoformat(timespec='seconds')})
for f in log['forecasts']:
    if f['month'] in head:
        f['actual'] = round(head[f['month']], 2)
        f['error'] = round(f['value'] - f['actual'], 2)

# ── seasons ─────────────────────────────────────────────────────────────────
season_months = sorted(full)
lv = full[LAST]
earlier = [m for m in season_months if m < LAST and full[m] >= lv]
highest_since = earlier[-1] if earlier else None
aug_sep, aug_vs_year = [], []
for y in range(int(SEASON_START[:4]), int(LAST[:4]) + 1):
    a, sp = full.get(f'{y}-08'), full.get(f'{y}-09')
    if a and sp:
        aug_sep.append({'year': y, 'aug': round(a, 2), 'sep': round(sp, 2), 'delta': round(sp - a, 2)})
    yr = [v for mo, v in full.items() if mo.startswith(str(y))]
    if f'{y}-08' in full and len(yr) >= 6:
        aug_vs_year.append({'year': y, 'aug': round(full[f'{y}-08'], 2), 'yearMean': round(st.mean(yr), 2), 'months': len(yr),
                            'delta': round(full[f'{y}-08'] - st.mean(yr), 2)})
ours_aug_sep = None
aug_m, sep_m = f'{LAST[:4]}-08', f'{LAST[:4]}-09'
if usable(aug_m) and ours.get(sep_m) and ours[sep_m]['idx']['all'] is not None:
    sm = ours[sep_m]
    ours_aug_sep = {'aug': ours[aug_m]['idx']['all'], 'sep': sm['idx']['all'],
                    'delta': round(sm['idx']['all'] - ours[aug_m]['idx']['all'], 2),
                    'sepDays': sm['days'], 'partial': not sm['ended'], 'sepEnd': sm['endDate']}

season = {
    'monthly': [{'month': m, 'mph': round(full[m], 2)} for m in season_months],
    'latest': {'month': LAST, 'mph': round(lv, 2), 'highestSince': highest_since,
               'monthsSince': (season_months.index(LAST) - season_months.index(highest_since)) if highest_since else None},
    'augSep': aug_sep, 'augVsYear': aug_vs_year, 'oursAugSep': ours_aug_sep,
}

series_months = [m for m in MONTHS if m in mta_local and mta_local[m]]
for m in sorted(ours):
    if m > series_months[-1] and usable(m):
        series_months.append(m)
out = {
    'fetchedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'intro': f'The tracker makes its own estimates from GPS positions. Here they are set beside what the MTA publishes, which runs about six weeks behind. The latest month both sources cover is {month_name(P)}.',
    'pairedMonth': P,
    'speedSeries': {
        'title': 'Local routes, built the same way',
        'sub': 'mph; each route counts once, every hour 6 a.m. to 11 p.m. counts equally, weekdays and weekends 5 to 2',
        'mtaLabel': 'MTA published data',
        'months': series_months,
        'ours': [ours[m]['idx']['all'] if usable(m) else None for m in series_months],
        'oursAll': [ours[m]['idx']['all'] if usable(m) else None for m in series_months],
        'oursMov': [ours[m]['idx']['mov'] if usable(m) else None for m in series_months],
        'mta': [round(mta_local[m], 2) if mta_local.get(m) else None for m in series_months],
        'notes': [None if usable(m) or m not in ours else 'Tracker left out: too little of the month captured.' for m in series_months],
    },
    'nowcast': nowcast,
    'nowcastLog': log['forecasts'],
    'season': season,
    'metrics': metrics,
    'flags': flags,
    'numbers': {
        'routesPaired': len(pairs), 'rankCorrelation': round(rho, 3),
        'localMedianRatio': round(ratio_all, 3), 'localMedianRatioMoving': round(ratio_mov, 3),
        'localPctWithStops': round(abs(ratio_all - 1) * 100), 'localPctMoving': round(abs(ratio_mov - 1) * 100),
        'simMedianRatio': round(sim_ratio, 3) if sim_ratio else None,
        'mtaHeadline': {m: round(v, 2) for m, v in head.items()},
        'mtaLocalMatched': {m: round(v, 2) for m, v in mta_local.items() if v},
        'mtaExpressMatched': {m: round(v, 2) for m, v in mta_express.items() if v},
        'waitAssessment': {m: round(v, 4) for m, v in wa.items()},
        'additionalBusStopTime': {m: round(v, 2) for m, v in abst.items()},
        'dailyRidershipWeekdayAvg': {m: round(v) for m, v in daily_wd.items() if m >= START},
        'counterToDailyRatio': {m: round(r, 3) for m, r in zip(shared, ratios)},
    },
    'sources': [
        {'name': 'Bus speeds by route and hour (r6db-kkzj)', 'url': 'https://data.ny.gov/d/r6db-kkzj', 'through': month_name(max(m for m in mta_local if mta_local[m]))},
        {'name': 'Bus speeds (cudb-vcni)', 'url': 'https://data.ny.gov/d/cudb-vcni', 'through': month_name(LAST)},
        {'name': 'Wait assessment (v4z4-2h6n)', 'url': 'https://data.ny.gov/d/v4z4-2h6n', 'through': month_name(max(wa))},
        {'name': 'Customer journey metrics (8mkn-d32t)', 'url': 'https://data.ny.gov/d/8mkn-d32t', 'through': month_name(max(abst))},
        {'name': 'Daily ridership (sayj-mze2)', 'url': 'https://data.ny.gov/d/sayj-mze2', 'through': daily[-1]['date'][:10]},
    ],
}
route_months = [m for m in MONTHS if m in mta_route_wd]
routes_doc = {
    'about': 'MTA monthly bus speed per route from r6db-kkzj, hours 6-22. weekday = plain mean of the route\'s weekday hourly speeds (comparable to the tracker\'s per-route weekday figure); all = route miles / route hours over both day types.',
    'months': route_months,
    'weekday': {}, 'all': {},
}
for m_i, m in enumerate(route_months):
    for r, v in mta_route_wd[m].items():
        routes_doc['weekday'].setdefault(r, [None] * len(route_months))[m_i] = round(v, 2)
    for r, v in mta_route_all[m].items():
        routes_doc['all'].setdefault(r, [None] * len(route_months))[m_i] = round(v, 2)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w') as f:
    json.dump(out, f, indent=1)
with open(ROUTES_OUT, 'w') as f:
    json.dump(routes_doc, f)
with open(NOWCASTS, 'w') as f:
    json.dump(log, f, indent=1)
print(json.dumps({k: out['numbers'][k] for k in ['routesPaired', 'rankCorrelation', 'localMedianRatio', 'localMedianRatioMoving', 'simMedianRatio', 'mtaLocalMatched']}, indent=1))
if nowcast:
    print('nowcast:', nowcast['text'])
for fl in flags:
    print('-', fl['head'], '|', fl['text'])
