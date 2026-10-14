"""Pull how 311 complaints ended, citywide and for the busiest addresses.

Writes:
  build/cache/outcomes/city/<quarter>.csv   complaint_type x status x resolution_description counts
  build/cache/outcomes/top/<batch>.csv      the same, by address, for the top 0.1% of addresses
  build/cache/outcomes/spellings.json       every raw spelling of each top address

Top addresses come from data/points.json (ranked by build_data.py). Raw
spellings come from the quarterly cache, because older records store some
addresses with doubled spaces and an exact match on the clean form misses them.

Usage: python3 scripts/fetch_outcomes.py
"""
import glob, json, os, subprocess, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
CACHE = os.path.join(ROOT, 'build', 'cache')
OUT = os.path.join(CACHE, 'outcomes')
URL = 'https://data.cityofnewyork.us/resource/erm2-nwe9.csv'
TOP_N = 1301   # the top 0.1% of addresses
BATCH = 40


def norm(s):
    s = s.str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
    for p, r in [(r' BLVD\b', ' BOULEVARD'), (r' AVE\b', ' AVENUE'), (r' ST$', ' STREET'),
                 (r' RD$', ' ROAD'), (r' PL$', ' PLACE'), (r' PKWY\b', ' PARKWAY')]:
        s = s.str.replace(p, r, regex=True)
    return s


def soql(select, where, group, path):
    if os.path.exists(path):
        return 'cached'
    for attempt in range(1, 7):
        r = subprocess.run(['curl', '-s', '-G', URL, '-o', path + '.tmp', '-w', '%{http_code}', '--max-time', '900',
                            '--data-urlencode', f'$select={select}', '--data-urlencode', f'$where={where}',
                            '--data-urlencode', f'$group={group}', '--data-urlencode', '$limit=5000000'],
                           capture_output=True, text=True)
        if r.stdout == '200':
            os.replace(path + '.tmp', path)
            return 'ok'
        time.sleep(20 * attempt)  # 403 and 429 are throttling and clear on their own
    raise SystemExit(f'FAILED {path}')


def spellings():
    path = os.path.join(OUT, 'spellings.json')
    if os.path.exists(path):
        return json.load(open(path))
    P = json.load(open(os.path.join(ROOT, 'data', 'points.json')))
    want = set(zip(P['addr'][:TOP_N], P['zip'][:TOP_N]))
    raw = set()
    for f in glob.glob(os.path.join(CACHE, 'types', '*.csv')):
        d = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['incident_address', 'incident_zip'])
        raw |= set(zip(d.incident_address, d.incident_zip))
    r = pd.DataFrame(sorted(raw), columns=['raw', 'zip_raw'])
    r['addr'] = norm(r.raw)
    r['zip'] = r.zip_raw.str.strip().str[:5]
    r = r[[k in want for k in zip(r.addr, r.zip)]]
    out = [[a, z, sorted(set(g.raw)), sorted(set(g.zip_raw))] for (a, z), g in r.groupby(['addr', 'zip'])]
    json.dump(out, open(path, 'w'))
    return out


def main():
    os.makedirs(os.path.join(OUT, 'city'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'top'), exist_ok=True)
    jobs = []
    sel = 'complaint_type, status, resolution_description, count(*) as n'
    grp = 'complaint_type, status, resolution_description'
    for f in sorted(glob.glob(os.path.join(CACHE, 'types', '*.csv'))):
        q = os.path.basename(f)[:-4]
        y, m = int(q[:4]), int(q[5:7])
        e = f'{y + 1}-01-01' if m == 10 else f'{y}-{m + 3:02d}-01'
        jobs.append((sel, f"created_date >= '{q}T00:00:00' AND created_date < '{e}T00:00:00'", grp,
                     os.path.join(OUT, 'city', q + '.csv')))
    sp = spellings()
    sel2 = 'incident_address, incident_zip, ' + sel
    grp2 = 'incident_address, incident_zip, ' + grp
    for b in range(0, len(sp), BATCH):
        part = sp[b:b + BATCH]
        names = sorted({s for _, _, raws, _ in part for s in raws})
        zips = sorted({z for _, _, _, zs in part for z in zs})
        inl = ', '.join("'" + s.replace("'", "''") + "'" for s in names)
        inz = ', '.join("'" + z + "'" for z in zips)
        jobs.append((sel2, f'incident_address in ({inl}) AND incident_zip in ({inz})', grp2,
                     os.path.join(OUT, 'top', f'{b // BATCH:03d}.csv')))
    with ThreadPoolExecutor(5) as ex:
        res = list(ex.map(lambda j: soql(*j), jobs))
    print(len(res), 'queries;', res.count('ok'), 'fetched,', res.count('cached'), 'cached;', len(sp), 'top addresses matched')


if __name__ == '__main__':
    main()
