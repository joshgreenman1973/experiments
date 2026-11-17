#!/usr/bin/env python3
"""Build data/spotlight/flatbush.json for the Flatbush Avenue spotlight page.

Inputs (all produced in this folder):
  corridor_pairs.csv        from corridor.py (tracker GPS, Flatbush stretches)
  days.json                 tracker day types (holidays and school-closed days excluded)
  mta/B41.csv               MTA Bus Route Segment Speeds, B41, weekdays (mta_seg.py)
  control.py                background change on other Brooklyn routes (re-run here)
Every figure on the page comes out of this file; print() lines echo the key ones.
"""
import csv, collections, json, math, random, sys
from datetime import date
from corridor import STRETCH, CUT_S, CUTS

OUT = sys.argv[1] if len(sys.argv) > 1 else 'flatbush.json'
rows = list(csv.DictReader(open('corridor_pairs.csv')))
days = {d['date']: d for d in json.load(open('days.json'))['days']}
HRS = list(range(7, 19))
MPH = 2.23694

# Days with at least 10 of the 12 daytime hours caught on the B41
cov = collections.defaultdict(set)
for r in rows:
    if r['route'] == 'B41' and int(r['hour']) in HRS:
        cov[r['date']].add(int(r['hour']))
weekday = lambda d: days.get(d, {}).get('dayType') == 'weekday'
good = sorted(d for d in cov if weekday(d) and len(cov[d]) >= 10)

OPEN = '2026-11-07'          # first day the faster speeds appear (a Saturday)
DUR = ('2026-10-13', '2026-11-06')
AFT = ('2026-11-09', '2026-11-16')
in_p = lambda d, p: p[0] <= d <= p[1]
dur_days = [d for d in good if in_p(d, DUR)]
aft_days = [d for d in good if in_p(d, AFT)]
print('during days', len(dur_days), dur_days[0], dur_days[-1])
print('after days', len(aft_days), aft_days)


def cube(pred):
    a = collections.defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        if int(r['hour']) in HRS and pred(r):
            k = (r['date'], int(r['hour']))
            a[k][0] += float(r['m']); a[k][1] += float(r['s'])
    return a


def hour_equal(c, dates, min_hours=11):
    """Average the 12 daytime hours equally (by time per mile), so a day or period
    that caught more rush hours than another still compares fairly."""
    dates = set(dates)
    h = collections.defaultdict(lambda: [0.0, 0.0])
    for (d, hr), (m, s) in c.items():
        if d in dates:
            h[hr][0] += m; h[hr][1] += s
    sp = [h[x][0] / h[x][1] * MPH for x in HRS if h[x][1] > 60 and h[x][0] > 0]
    if len(sp) < min_hours:
        return None
    return len(sp) / sum(1 / s for s in sp)


def by_hour(c, dates):
    dates = set(dates)
    h = collections.defaultdict(lambda: [0.0, 0.0])
    for (d, hr), (m, s) in c.items():
        if d in dates:
            h[hr][0] += m; h[hr][1] += s
    return {hr: round(h[hr][0] / h[hr][1] * MPH, 2) for hr in HRS if h[hr][1] > 60}


def boot(c, n=500):
    rnd = random.Random(7)
    out = []
    for _ in range(n):
        b = hour_equal(c, [rnd.choice(dur_days) for _ in dur_days])
        a = hour_equal(c, [rnd.choice(aft_days) for _ in aft_days])
        if a and b:
            out.append(a - b)
    out.sort()
    return round(out[int(0.05 * len(out))], 2), round(out[int(0.95 * len(out))], 2)


def pred(stretches, d, routes=('B41',)):
    s = set(str(k) for k in stretches)
    return lambda r: r['stretch'] in s and r['dir'] == d and (routes is None or r['route'] in routes)


R = lambda v, n=2: None if v is None else round(v, n)
miles = [round((CUT_S[k + 1] - CUT_S[k]) / 1609.34, 2) for k in range(len(STRETCH))]

# ── stretch table ──
stretches = []
for k, name in enumerate(STRETCH):
    item = {'name': name, 'from': CUTS[k][0], 'to': CUTS[k + 1][0], 'miles': miles[k], 'rebuilt': k in (0, 1)}
    for d in 'SN':
        c = cube(pred([k], d))
        b, a = hour_equal(c, dur_days), hour_equal(c, aft_days)
        lo, hi = boot(c)
        item[d] = {'during': R(b), 'after': R(a), 'change': R(a - b), 'ci90': [lo, hi]}
    stretches.append(item)
    print(f"{name:34} S {item['S']['during']}->{item['S']['after']} {item['S']['ci90']}  N {item['N']['during']}->{item['N']['after']} {item['N']['ci90']}")

groups = {}
for key, ks in (('rebuilt', [0, 1]), ('rest', [2, 3, 4, 5, 6]), ('atlGap', [1])):
    groups[key] = {'miles': round(sum(miles[k] for k in ks), 2)}
    for d in 'SN':
        c = cube(pred(ks, d))
        b, a = hour_equal(c, dur_days), hour_equal(c, aft_days)
        groups[key][d] = {'during': R(b), 'after': R(a), 'change': R(a - b), 'pct': R((a / b - 1) * 100, 0), 'ci90': list(boot(c))}
    print(key, groups[key])

# whole Flatbush trip, Livingston St to Kings Plaza, minutes
trip = {}
for d in 'SN':
    t = {}
    for per, dd in (('during', dur_days), ('after', aft_days)):
        mins = 0.0
        for k in range(len(STRETCH)):
            mins += miles[k] / hour_equal(cube(pred([k], d)), dd) * 60
        t[per] = round(mins, 1)
    t['saved'] = round(t['during'] - t['after'], 1)
    trip[d] = t
print('trip minutes', trip)

# other routes on the rebuilt mile
others = {}
for rt in ('B67', 'B45', 'B103'):
    others[rt] = {}
    for d in 'SN':
        c = cube(pred([0, 1], d, (rt,)))
        b, a = hour_equal(c, dur_days, 9), hour_equal(c, aft_days, 9)
        hrs_obs = sum(v[1] for (dd, _), v in c.items() if dd in set(aft_days)) / 3600
        others[rt][d] = {'during': R(b), 'after': R(a), 'hoursObservedAfter': round(hrs_obs, 1)}
print('others', others)

# hour of day on the rebuilt mile
hourly = {}
for d in 'SN':
    c = cube(pred([0, 1], d))
    hourly[d] = {'during': by_hour(c, dur_days), 'after': by_hour(c, aft_days)}

# daily series: every extracted day with >=10 daytime hours, weekdays and weekends flagged
daily = []
all_days = sorted(d for d in cov if len(cov[d]) >= 10)
cubes = {(g, d): cube(pred(ks, d)) for g, ks in (('rebuilt', [0, 1]), ('rest', [2, 3, 4, 5, 6])) for d in 'SN'}
for dd in all_days:
    dt = days.get(dd, {}).get('dayType') or ('weekend' if date.fromisoformat(dd).weekday() >= 5 else 'weekday')
    rec = {'d': dd, 'type': dt}
    for (g, d), c in cubes.items():
        rec[f'{g}{d}'] = R(hour_equal(c, [dd], 10))
    daily.append(rec)

# ── MTA monthly, B41 timepoint segments that contain the rebuilt mile ──
mta = collections.defaultdict(lambda: [0.0, 0.0])
dist = collections.defaultdict(set)
for r in csv.DictReader(open('mta/B41.csv')):
    h = int(r['hour_of_day'])
    if h not in HRS:
        continue
    a, b = r['timepoint_stop_name'], r['next_timepoint_stop_name']
    key = None
    if r['direction'] == 'S' and a.startswith('FLATBUSH AV/ATLANTIC') and 'OCEAN' in b:
        key = 'S'
    elif r['direction'] == 'N' and a.startswith('FLATBUSH AV/EMPIRE') and 'ATLANTIC' in b:
        key = 'N'
    elif r['direction'] == 'S' and a.startswith('CADMAN') and 'ATLANTIC' in b:
        key = 'S_downtown'
    if not key:
        continue
    try:
        dm, tt, n = float(r['road_distance']), float(r['average_travel_time']), float(r['bus_trip_count'])
    except ValueError:
        continue
    if tt <= 0 or n <= 0:
        continue
    ym = f"{int(r['year'])}-{int(r['month']):02d}"
    mta[(key, ym)][0] += dm * n; mta[(key, ym)][1] += tt * n / 60
    dist[key].add(round(dm, 2))
print('MTA segment distances', {k: sorted(v) for k, v in dist.items()})
months = sorted({k[1] for k in mta})
mta_series = {key: [{'m': m, 'v': R(mta[(key, m)][0] / mta[(key, m)][1]) if mta[(key, m)][1] else None} for m in months]
              for key in ('S', 'N', 'S_downtown')}
M = {(k, x['m']): x['v'] for k in mta_series for x in mta_series[k]}

# Tracker GPS on the same 1.7 miles (stretches 1+2), pooled like the MTA figure, by month and for the first week
def gps_pooled(d, dates):
    a = [0.0, 0.0]
    dates = set(dates)
    for r in rows:
        if r['route'] == 'B41' and r['dir'] == d and r['stretch'] in ('1', '2') and int(r['hour']) in HRS and r['date'] in dates:
            a[0] += float(r['m']); a[1] += float(r['s'])
    return a[0] / a[1] * MPH if a[1] else None

calib = {}
for d in 'SN':
    gm = {}
    for m in ('2026-07', '2026-08', '2026-09', '2026-10'):
        gm[m] = gps_pooled(d, [x for x in good if x.startswith(m)])
    offs = [gm[m] - M[(d, m)] for m in gm]
    off = sum(offs) / len(offs)
    after = gps_pooled(d, aft_days)
    pre = [M[(d, m)] for m in ('2026-01', '2026-02', '2026-03', '2026-04')]
    calib[d] = {
        'gpsMonthly': {m: R(v) for m, v in gm.items()},
        'mtaMonthly': {m: M[(d, m)] for m in gm},
        'offset': R(off),
        'gpsAfter': R(after),
        'afterInMtaTerms': R(after - off),
        'preConstruction': R(sum(pre) / len(pre)),
        'preMonths': ['2026-01', '2026-04'],
        'yearAgoNov': M[(d, '2025-11')],
    }
    print('calib', d, calib[d])

# background: other Brooklyn routes, same days and hours
import subprocess
ctrl_txt = subprocess.run([sys.executable, 'control.py'], capture_output=True, text=True).stdout
control = {}
for line in ctrl_txt.strip().splitlines():
    rt, b, _, a, ch = line.split()
    control[rt] = {'during': float(b), 'after': float(a), 'change': float(ch)}
print('control', control)

out = {
    'built': date.today().isoformat(),
    'opened': OPEN,
    'unveiled': '2026-11-17',
    'periods': {'during': list(DUR), 'after': list(AFT), 'duringDays': len(dur_days), 'afterDays': len(aft_days),
                'afterDates': aft_days},
    'timeline': [
        {'date': '2025-09-25', 'label': 'Phase 1 work begins, Livingston St to State St'},
        {'date': '2025-10-02', 'label': 'Phase 1 center lanes in place, Livingston St to State St'},
        {'date': '2026-04-28', 'label': 'Phase 2 construction resumes, State St to Grand Army Plaza'},
        {'date': '2026-11-07', 'label': 'Faster speeds first appear in the tracker data'},
        {'date': '2026-11-17', 'label': 'City unveils the finished lanes'},
    ],
    'stretches': stretches,
    'groups': groups,
    'trip': trip,
    'others': others,
    'hourly': hourly,
    'daily': daily,
    'mta': {'months': months, 'series': mta_series, 'calibration': calib},
    'control': control,
}
json.dump(out, open(OUT, 'w'), indent=1)
print('wrote', OUT)
