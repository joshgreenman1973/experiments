"""Turn the daily link x hour files into the page's data.

Input:  ~/.vital-city/street-pace/raw/YYYY-MM-DD.json   (from fetch_days.py; days and hours are UTC)
        ~/.vital-city/street-pace/links/links_2026-11-12.json (link names and encoded polylines)
        ~/.vital-city/street-pace/links/cbd.geojson     (MTA Central Business District geofence, data.ny.gov srxy-5nxn)
Output: data/links.json, data/profiles.json, data/monthly.json, data/summary.json

Timestamps in the source are UTC through May 16, 2025, and New York local time from June 30, 2025,
when the feed resumed after a six-week outage. Evidence: before the outage the fastest hour sits at 8 UTC
in summer and 9 UTC in winter (4 a.m. local, shifting with daylight saving); after it, the fastest hour
sits at 4 in every month. UTC cells are moved to local time; local cells are used as they are.
Speeds: source is feet per second; mph = fps * 3600 / 5280.
Each link-hour-day cell counts once (equal weight), whatever the number of underlying rows.
"""
import datetime as dt, glob, json, os, statistics
from collections import defaultdict
from zoneinfo import ZoneInfo
from shapely.geometry import LineString, shape, Point

HOME = os.path.expanduser('~/.vital-city/street-pace')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
NY, UTC = ZoneInfo('America/New_York'), dt.timezone.utc
MPH = 3600 / 5280
PRICING_START = dt.date(2025, 1, 5)
LOCAL_FROM = dt.date(2025, 6, 30)   # first day of local-time stamps

def decode(s):
    """Google encoded polyline -> [(lat, lon)]"""
    i, lat, lon, out = 0, 0, 0, []
    while i < len(s):
        vals = []
        for _ in range(2):
            shift = res = 0
            while True:
                b = ord(s[i]) - 63; i += 1
                res |= (b & 0x1f) << shift; shift += 5
                if b < 0x20: break
            vals.append(~(res >> 1) if res & 1 else res >> 1)
        lat += vals[0]; lon += vals[1]
        out.append((lat / 1e5, lon / 1e5))
    return out

def holidays(y):
    """Weekday federal holidays plus the day after Thanksgiving and Christmas Eve, observed dates."""
    def nth(month, wd, n):  # nth weekday (0=Mon) of month; n=-1 last
        if n > 0:
            d = dt.date(y, month, 1); d += dt.timedelta((wd - d.weekday()) % 7); return d + dt.timedelta(7 * (n - 1))
        d = dt.date(y, month + 1, 1) - dt.timedelta(1); return d - dt.timedelta((d.weekday() - wd) % 7)
    def obs(d):
        return d - dt.timedelta(1) if d.weekday() == 5 else d + dt.timedelta(1) if d.weekday() == 6 else d
    tg = nth(11, 3, 4)
    return {obs(dt.date(y, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), nth(5, 0, -1), obs(dt.date(y, 6, 19)), obs(dt.date(y, 7, 4)),
            nth(9, 0, 1), nth(10, 0, 2), obs(dt.date(y, 11, 11)), tg, tg + dt.timedelta(1), dt.date(y, 12, 24), obs(dt.date(y, 12, 25)),
            obs(dt.date(y + 1, 1, 1))}
HOL = set().union(*[holidays(y) for y in range(2020, 2028)])

# ---------- links ----------
cbd = shape(json.load(open(os.path.join(HOME, 'links', 'cbd.geojson')))['features'][0]['geometry'])
raw_links = json.load(open(os.path.join(HOME, 'links', 'links_2026-11-12.json')))
links = {}
for r in raw_links:
    pts = decode(r['polyline'])
    line = LineString([(lon, lat) for lat, lon in pts])
    mid = line.interpolate(0.5, normalized=True)
    links[int(r['sid'])] = {'id': int(r['sid']), 'name': r['link_name'].strip(), 'boro': r['borough'],
                            'ft': round(float(r['link_length_ft'])), 'zone': bool(cbd.contains(mid)), 'poly': r['polyline']}

# ---------- accumulate ----------
PERIODS = {y: (dt.date(y, 2, 1), dt.date(y, 10, 31)) for y in (2022, 2023, 2024, 2025, 2026)}
# The source has no rows at all from May 16 to June 30, 2025. Drop the same calendar weeks from every year
# so each year's Feb-Oct window covers the same days of the year.
def in_gap(d):
    return (d.month, d.day) >= (5, 16) and (d.month, d.day) <= (6, 30)
prof = defaultdict(lambda: [0.0, 0])      # (sid, year, daytype, hour) -> [sum mph, cells]
month = defaultdict(lambda: [0.0, 0])     # (sid, 'YYYY-MM') -> weekday 7am-7pm
mdays = defaultdict(set)                  # (sid, month) -> local dates with data
dayzone = defaultdict(lambda: [0.0, 0])   # (local date, zone flag) -> weekday 7am-7pm, for the daily series
files = sorted(glob.glob(os.path.join(HOME, 'raw', '*.json')))
for f in files:
    day = dt.date.fromisoformat(os.path.basename(f)[:10])
    for sid, h, v, tt, n in json.load(open(f)):
        if sid not in links: continue
        if day >= LOCAL_FROM:
            ld, lh = day, h
        else:
            loc = dt.datetime(day.year, day.month, day.day, h, tzinfo=UTC).astimezone(NY)
            ld, lh = loc.date(), loc.hour
        dtype = 'we' if ld.weekday() >= 5 else ('hol' if ld in HOL else 'wd')
        mph = v * MPH
        for y, (a, b) in PERIODS.items():
            if a <= ld <= b and dtype != 'hol' and not in_gap(ld):
                c = prof[(sid, y, dtype, lh)]; c[0] += mph; c[1] += 1
        if dtype == 'wd' and 7 <= lh < 19:
            k = (sid, ld.strftime('%Y-%m')); c = month[k]; c[0] += mph; c[1] += 1; mdays[k].add(ld)
last_day = dt.date.fromisoformat(os.path.basename(files[-1])[:10])

# ---------- profiles: per link, per period, per daytype, 24 hourly mph ----------
profiles = {}
for sid in links:
    p = {}
    for y in PERIODS:
        for t in ('wd', 'we'):
            row = []
            for h in range(24):
                s, n = prof.get((sid, y, t, h), (0, 0))
                row.append(round(s / n, 1) if n >= 20 else None)   # need 20+ days behind an hourly value
            p[f'{y}{t}'] = row
    profiles[sid] = p

# ---------- monthly weekday daytime ----------
months = sorted({m for _, m in month})
monthly = {sid: [round(month[(sid, m)][0] / month[(sid, m)][1], 2) if len(mdays.get((sid, m), ())) >= 8 else None for m in months] for sid in links}

def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None

# Fixed panel: links with a monthly value in at least 90% of months, so the mix of streets stays constant
panel = [s for s in links if sum(v is not None for v in monthly[s]) >= 0.9 * len(months)]
series = {}
for g, test in (('zone', lambda s: links[s]['zone']), ('mn_out', lambda s: not links[s]['zone'] and links[s]['boro'] == 'Manhattan'),
                ('other', lambda s: links[s]['boro'] != 'Manhattan')):
    ids = [s for s in panel if test(s)]
    series[g] = {'n': len(ids), 'mph': [None if (m := mean([monthly[s][i] for s in ids])) is None else round(m, 2) for i in range(len(months))]}

# ---------- before / after (Feb-Oct weekdays, 7am-7pm) ----------
def daytime(sid, y):
    vals = [profiles[sid][f'{y}wd'][h] for h in range(7, 19)]
    return None if any(v is None for v in vals) else statistics.fmean(vals)
cmp = {}
for g, test in (('zone', lambda s: links[s]['zone']), ('mn_out', lambda s: not links[s]['zone'] and links[s]['boro'] == 'Manhattan'),
                ('other', lambda s: links[s]['boro'] != 'Manhattan'), ('all', lambda s: True)):
    ids = [s for s in links if test(s) and all(daytime(s, y) is not None for y in (2024, 2025, 2026))]
    r = {'n': len(ids)}
    for y in PERIODS:
        r[str(y)] = round(statistics.fmean([daytime(s, y) for s in ids if daytime(s, y) is not None]), 2) if ids else None
    r['y24'] = round(statistics.fmean([daytime(s, 2024) for s in ids]), 3)
    r['y25'] = round(statistics.fmean([daytime(s, 2025) for s in ids]), 3)
    r['y26'] = round(statistics.fmean([daytime(s, 2026) for s in ids]), 3)
    r['links_faster_25'] = sum(daytime(s, 2025) > daytime(s, 2024) for s in ids)
    cmp[g] = r
    # by hour, weekday, panel of these ids
    for y in (2024, 2025, 2026):
        r[f'hours{y}'] = [round(statistics.fmean([profiles[s][f'{y}wd'][h] for s in ids if profiles[s][f'{y}wd'][h] is not None]), 2) for h in range(24)]

per_link = []
for s in links:
    a, b, c = daytime(s, 2024), daytime(s, 2025), daytime(s, 2026)
    per_link.append({'id': s, 'd24': None if a is None else round(a, 2), 'd25': None if b is None else round(b, 2), 'd26': None if c is None else round(c, 2)})

os.makedirs(OUT, exist_ok=True)
json.dump(list(links.values()), open(os.path.join(OUT, 'links.json'), 'w'), separators=(',', ':'))
json.dump(profiles, open(os.path.join(OUT, 'profiles.json'), 'w'), separators=(',', ':'))
json.dump({'months': months, 'links': monthly}, open(os.path.join(OUT, 'monthly.json'), 'w'), separators=(',', ':'))
json.dump({'first_day': os.path.basename(files[0])[:10], 'last_day': str(last_day), 'days': len(files),
           'links': len(links), 'zone_links': sum(l['zone'] for l in links.values()), 'panel_links': len(panel),
           'months': months, 'series': series, 'compare': cmp, 'per_link': per_link,
           'boro_counts': {b: sum(1 for l in links.values() if l['boro'] == b) for b in sorted({l['boro'] for l in links.values()})}},
          open(os.path.join(OUT, 'summary.json'), 'w'), separators=(',', ':'))
print('days', len(files), 'links', len(links), 'zone', sum(l['zone'] for l in links.values()), 'panel', len(panel))
for g, r in cmp.items():
    print(g, r['n'], {k: r[k] for k in ('2022', '2023', '2024', '2025', '2026')}, 'faster25', r['links_faster_25'])
