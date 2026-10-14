"""Pull quarterly aggregates of NYC 311 service requests (Socrata erm2-nwe9).

Two pulls, each one query per calendar quarter from Jan. 1, 2020:
  types  -> incident_address, incident_zip, complaint_type, count
  coords -> incident_address, incident_zip, borough, avg(latitude), avg(longitude), count(latitude)

Files land in build/cache/<kind>/<quarter-start>.csv. Existing files are kept
unless --refresh is passed, so a rerun only fetches what is missing. The most
recent quarter is always refetched because the feed is still filling it.

Usage: python3 scripts/fetch_311.py [--refresh]
"""
import datetime, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '..', 'build', 'cache')
URL = 'https://data.cityofnewyork.us/resource/erm2-nwe9.csv'
QUERIES = {
    'types': ('incident_address, incident_zip, complaint_type, count(*) as n',
              'incident_address, incident_zip, complaint_type', ''),
    'coords': ('incident_address, incident_zip, borough, avg(latitude) as lat, avg(longitude) as lon, count(latitude) as nl',
               'incident_address, incident_zip, borough', ' AND latitude IS NOT NULL'),
}

def quarters(today):
    out = []
    for y in range(2020, today.year + 1):
        for m in (1, 4, 7, 10):
            s = datetime.date(y, m, 1)
            if s > today:
                break
            e = datetime.date(y + 1, 1, 1) if m == 10 else datetime.date(y, m + 3, 1)
            out.append((s, e))
    return out

def fetch(kind, s, e, force):
    path = os.path.join(CACHE, kind, f'{s}.csv')
    if os.path.exists(path) and not force:
        return f'{kind} {s} cached'
    sel, grp, extra = QUERIES[kind]
    where = f"created_date >= '{s}T00:00:00' AND created_date < '{e}T00:00:00'{extra}"
    for attempt in range(1, 7):
        r = subprocess.run(['curl', '-s', '-G', URL, '-o', path + '.tmp', '-w', '%{http_code}', '--max-time', '900',
                            '--data-urlencode', f'$select={sel}', '--data-urlencode', f'$where={where}',
                            '--data-urlencode', f'$group={grp}', '--data-urlencode', '$limit=20000000'],
                           capture_output=True, text=True)
        if r.stdout == '200':
            os.replace(path + '.tmp', path)
            return f'{kind} {s} ok'
        # Socrata answers throttling with 403 or 429; both clear on their own.
        time.sleep(20 * attempt)
    raise SystemExit(f'{kind} {s} FAILED after retries (last status {r.stdout})')

def fetch_meta():
    # Row count and newest record, used by the build to check the quarterly sums.
    r = subprocess.run(['curl', '-s', '-G', URL.replace('.csv', '.json'), '--max-time', '300',
                        '--data-urlencode', '$select=count(*) as n, max(created_date) as newest'],
                       capture_output=True, text=True)
    open(os.path.join(CACHE, 'meta.json'), 'w').write(r.stdout)
    return 'meta ' + r.stdout.strip()

def main():
    refresh = '--refresh' in sys.argv
    qs = quarters(datetime.date.today())
    jobs = []
    for kind in QUERIES:
        os.makedirs(os.path.join(CACHE, kind), exist_ok=True)
        for i, (s, e) in enumerate(qs):
            jobs.append((kind, s, e, refresh or i == len(qs) - 1))
    with ThreadPoolExecutor(5) as ex:
        for msg in ex.map(lambda j: fetch(*j), jobs):
            print(msg, flush=True)
    print(fetch_meta())

if __name__ == '__main__':
    main()
