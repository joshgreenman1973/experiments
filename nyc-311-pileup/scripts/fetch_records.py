"""Pull every individual 311 record for the busiest addresses, for the timing analysis.

Writes build/cache/records/<address>_<zip>.csv with created_date, closed_date,
complaint_type, descriptor, open_data_channel_type, agency and status.

Usage: python3 scripts/fetch_records.py
"""
import os, subprocess, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'build', 'cache', 'records')
URL = 'https://data.cityofnewyork.us/resource/erm2-nwe9.csv'
# Raw spellings as 311 stores them; a few addresses appear under two.
TARGETS = [
    (['655 EAST 230 STREET'], '10466'), (['672 EAST 231 STREET'], '10466'),
    (['674 EAST 231 STREET'], '10466'), (['661 EAST 230 STREET'], '10466'),
    (['78-15 PARSONS BOULEVARD', '78-15 PARSONS BLVD'], '11366'), (['82-68 164 STREET'], '11432'),
    (['159-06 UNION TURNPIKE'], '11366'), (['158-33 78 AVENUE'], '11366'),
    (['71-01 PARSONS BOULEVARD', '71-01 PARSONS BLVD'], '11365'),
    (['5-47 50 AVENUE'], '11101'), (['191 UNION STREET'], '11231'), (['100 MESEROLE AVENUE'], '11222'),
    (['34-16 ASTORIA BOULEVARD SOUTH', '34-16 ASTORIA BLVD SOUTH'], '11103'),
    (['1869 83 STREET'], '11214'), (['1465 WASHINGTON AVENUE'], '10456'), (['177 SANDS STREET'], '11201'),
    (['18-11 129 STREET'], '11356'), (['88-08 151 AVENUE'], '11414'), (['88-12 151 AVENUE'], '11414'),
    (['1040B EAST 217 STREET'], '10469'), (['2176 TIEBOUT AVENUE'], '10457'), (['640 8 AVENUE'], '10036'),
]
SEL = 'incident_address, created_date, closed_date, complaint_type, descriptor, open_data_channel_type, agency, status'

def fetch(spellings, zipc):
    name = spellings[0].replace(' ', '_') + '_' + zipc
    path = os.path.join(OUT, name + '.csv')
    if os.path.exists(path):
        return name + ' cached'
    # Older records store some addresses with doubled spaces ("655 EAST  230 STREET"),
    # so match with wildcards between words and keep exact matches after cleanup
    # (see analyze_cadence.py).
    likes = ' OR '.join("incident_address like '" + s.replace(' ', '%') + "'" for s in spellings)
    where = f"({likes}) AND incident_zip = '{zipc}'"
    for attempt in range(1, 7):
        r = subprocess.run(['curl', '-s', '-G', URL, '-o', path + '.tmp', '-w', '%{http_code}', '--max-time', '900',
                            '--data-urlencode', f'$select={SEL}', '--data-urlencode', f'$where={where}',
                            '--data-urlencode', '$order=created_date', '--data-urlencode', '$limit=5000000'],
                           capture_output=True, text=True)
        if r.stdout == '200':
            os.replace(path + '.tmp', path)
            return name + ' ok'
        time.sleep(20 * attempt)  # 403 and 429 are throttling and clear on their own
    raise SystemExit(name + ' FAILED')

os.makedirs(OUT, exist_ok=True)
with ThreadPoolExecutor(5) as ex:
    for m in ex.map(lambda t: fetch(*t), TARGETS):
        print(m, flush=True)
