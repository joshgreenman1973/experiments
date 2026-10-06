"""
Build data/events/events.json and data/events/weather.json: the things that
explain bumps in the series, for markers on every chart.

  holiday   weekdays typed "holiday" by rollup.js (holiday or service cut)
  gap       days the collector caught fewer than 12 of 17 hours, or missed
  weather   rainy (0.5 in. or more) and snowy (1 in. or more) days at the
            Central Park station (NOAA GHCN-Daily, free, no key)
  method    changes to how the tracker collects or computes
  network   bus network redesigns, from data/ridership/routes-monthly.json

Weather is auxiliary: if NOAA is unreachable, the previous weather file
is kept and marked stale rather than failing the daily run. Everything else
comes from files in the repo and fails loud if those are missing.
"""
import json, os, sys, time, urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT_DIR = os.path.join(ROOT, 'data', 'events')
RAIN_IN, SNOW_IN, GAP_HOURS = 0.5, 1.0, 12

# How collection and the method changed. Dates from the repo's history.
METHOD = [
    ('2026-04-22', 'Automatic collection starts', 'Hourly six-minute bursts of the whole fleet.'),
    ('2026-05-26', 'Collection moves to twice an hour', 'Bursts at :09 and :39 to dodge dropped runs.'),
    ('2026-06-30', 'Collector timeouts fixed', 'Most of June was caught only in the evening; those weeks are not comparable.'),
    ('2026-10-01', 'GitHub stops starting most scheduled runs', 'Only three to five bursts a day are caught until the collector is redesigned.'),
    ('2026-10-06', 'Self-renewing collector; method version 2', 'One long-running collector replaces cron runs. Every day reprocessed: Eastern-time hours, weekdays and weekends apart, routes counted equally, GPS time, layovers dropped, speed with stops added.'),
]


def read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print(f'build_events: missing {rel}', file=sys.stderr)
        sys.exit(1)
    with open(p) as f:
        return json.load(f)


def fetch_json(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'nyc-bus-tracker'}), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(4 * (i + 1))


def weather(first, last):
    """Daily rain and snow at the Central Park weather station (NOAA GHCN-Daily
    USW00094728), inches. NOAA posts these about a week behind."""
    url = ('https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries'
           f'&stations=USW00094728&dataTypes=PRCP,SNOW&startDate={first}&endDate={last}&format=json&units=standard')
    rows = fetch_json(url)
    days = {}
    for r in rows:
        try:
            days[r['DATE']] = (float(r.get('PRCP') or 0), float(r.get('SNOW') or 0))
        except ValueError:
            continue
    span = (date.fromisoformat(last) - date.fromisoformat(first)).days + 1
    if len(days) < 0.8 * (span - 10):
        raise RuntimeError(f'only {len(days)} of {span} days of weather')
    ks = sorted(days)
    return {'dates': ks, 'rainIn': [days[k][0] for k in ks], 'snowIn': [days[k][1] for k in ks]}


def main():
    days = read('data/summary/days.json')['days']
    first, last = days[0]['date'], days[-1]['date']
    events = []

    for d in days:
        if d['dayType'] == 'holiday':
            events.append({'date': d['date'], 'kind': 'holiday', 'label': d.get('holiday') or 'Reduced service',
                           'detail': d.get('reason') or ''})

    # Gaps: thin days and missing days, merged into runs.
    have = {d['date']: d for d in days}
    cur = date.fromisoformat(first)
    end = date.fromisoformat(last)
    run = None
    while cur <= end:
        k = cur.isoformat()
        d = have.get(k)
        thin = d is None or d['hoursCollected'] < GAP_HOURS
        if thin:
            if run is None:
                run = {'date': k, 'end': k, 'missing': 0, 'thin': 0}
            run['end'] = k
            run['missing' if d is None else 'thin'] += 1
        elif run:
            events.append(run); run = None
        cur += timedelta(days=1)
    if run:
        events.append(run)
    for e in events:
        if 'missing' in e:
            n = e.pop('missing'); t = e.pop('thin')
            e['kind'] = 'gap'
            e['label'] = 'Collection gap'
            parts = ([f'{n} day(s) with no data'] if n else []) + ([f'{t} day(s) with fewer than {GAP_HOURS} of 17 hours'] if t else [])
            e['detail'] = '; '.join(parts)

    for dt_, label, detail in METHOD:
        if first <= dt_ <= max(last, dt_):
            events.append({'date': dt_, 'kind': 'method', 'label': label, 'detail': detail})

    rm = read('data/ridership/routes-monthly.json')
    for b in rm.get('breaks', []) or []:
        events.append({'date': b.get('date'), 'kind': 'network', 'label': b.get('label', 'Network change'),
                       'detail': b.get('routes', ''), 'source': b.get('source_url')})

    os.makedirs(OUT_DIR, exist_ok=True)
    wpath = os.path.join(OUT_DIR, 'weather.json')
    try:
        w = weather(first, last)
        w.update({'source': 'NOAA GHCN-Daily, Central Park station USW00094728', 'fetchedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'stale': False})
    except Exception as e:
        print(f'build_events: weather fetch failed ({e}); keeping the previous file', file=sys.stderr)
        w = json.load(open(wpath)) if os.path.exists(wpath) else {'dates': [], 'rainIn': [], 'snowIn': []}
        w['stale'] = True
    with open(wpath, 'w') as f:
        json.dump(w, f)
    for t, r, s in zip(w['dates'], w['rainIn'], w['snowIn']):
        if s >= SNOW_IN:
            events.append({'date': t, 'kind': 'weather', 'label': f'Snow, {s:g} in.', 'detail': 'Central Park'})
        elif r >= RAIN_IN:
            events.append({'date': t, 'kind': 'weather', 'label': f'Rain, {r:.2f} in.', 'detail': 'Central Park'})

    events.sort(key=lambda e: (e['date'] or '', e['kind']))
    with open(os.path.join(OUT_DIR, 'events.json'), 'w') as f:
        json.dump({'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'events': events}, f, indent=1)
    kinds = {}
    for e in events:
        kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    print(f'events.json: {len(events)} events {kinds}; weather {len(w["dates"])} days{" (STALE)" if w.get("stale") else ""}')


if __name__ == '__main__':
    main()
