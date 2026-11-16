"""For a sample of days (the 8th and 22nd of each month), count each link's full-window readings and how many
are at or above 100 feet per second, the cap analyze.py applies. Links whose readings often hit the cap
are truncated by it rather than cleaned, so analyze.py sets them aside.
Output: ~/.vital-city/street-pace/overcap.json  {sid: [rows, rows_at_or_over_100fps]}
"""
import datetime as dt, json, os, urllib.parse, urllib.request
from collections import defaultdict

DS = {2022: '2dzd-mqxq', 2023: 'pi8f-savx', 2024: '7ank-n7rd', 2025: '5dxh-vk2s', 2026: '6a2s-2t65'}
OUT = os.path.expanduser('~/.vital-city/street-pace/overcap.json')
tot = defaultdict(lambda: [0, 0])
days = [dt.date(y, m, d) for y in DS for m in range(1, 13) for d in (8, 22)]
days = [d for d in days if dt.date(2022, 2, 1) <= d <= dt.date(2026, 11, 8)]
for d in days:
    q = ("SELECT sid, count(*) AS n, sum(case(median_speed_fps >= 100, 1, true, 0)) AS hi "
         f"WHERE aggregation_period_sec = 900 AND n_samples >= 3 AND median_speed_fps > 0 "
         f"AND median_calculation_timestamp >= '{d}T00:00:00' AND median_calculation_timestamp < '{d + dt.timedelta(1)}T00:00:00' "
         "GROUP BY sid LIMIT 5000")
    url = f'https://data.cityofnewyork.us/resource/{DS[d.year]}.json?' + urllib.parse.urlencode({'$query': q})
    try:
        rows = json.load(urllib.request.urlopen(url, timeout=120))
    except Exception as e:
        print(d, 'failed', e); continue
    for r in rows:
        t = tot[int(r['sid'])]; t[0] += int(r['n']); t[1] += int(float(r.get('hi') or 0))
    print(d, len(rows), flush=True)
json.dump(tot, open(OUT, 'w'))
print('links', len(tot), 'over 10%:', sorted([(s, round(h / n, 2)) for s, (n, h) in tot.items() if n and h / n > .1], key=lambda x: -x[1]))
