"""Link list (id, name, borough, encoded polyline, length) as published in the first three hours of one mid-year day per file,
plus the latest day. Writes ~/.vital-city/street-pace/links/links_<day>.json"""
import json, os, urllib.parse, urllib.request, datetime as dt
from concurrent.futures import ThreadPoolExecutor
OUT = os.path.expanduser('~/.vital-city/street-pace/links')
DAYS = [('s7y8-dkgd', '2021-06-15'), ('2dzd-mqxq', '2022-06-15'), ('pi8f-savx', '2023-06-15'), ('7ank-n7rd', '2024-06-12'),
        ('7ank-n7rd', '2024-12-11'), ('5dxh-vk2s', '2025-06-11'), ('6a2s-2t65', '2026-11-12')]
def go(a):
    ds, day = a
    if os.path.exists(os.path.join(OUT, f'links_{day}.json')):
        return day, 'cached', ''
    nxt = dt.date.fromisoformat(day) + dt.timedelta(days=1)
    q = (f"SELECT sid, link_name, borough, polyline, link_length_ft, count(*) as n WHERE median_calculation_timestamp >= '{day}T00:00:00' "
         f"AND median_calculation_timestamp < '{day}T03:00:00' GROUP BY sid, link_name, borough, polyline, link_length_ft LIMIT 5000")
    url = f'https://data.cityofnewyork.us/resource/{ds}.json?' + urllib.parse.urlencode({'$query': q})
    d = json.load(urllib.request.urlopen(url, timeout=280))
    json.dump(d, open(os.path.join(OUT, f'links_{day}.json'), 'w'))
    return day, len(d), len({r['sid'] for r in d})
with ThreadPoolExecutor(3) as ex:
    for r in ex.map(go, DAYS): print(*r)
