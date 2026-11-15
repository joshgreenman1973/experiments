"""Pull NYC DOT E-ZPass reader speeds, one day at a time, aggregated to link x hour.

Source: NYC Open Data, "EZ Pass Readers <year>" (DOT), one dataset per year.
Each raw row is a rolling 15-minute median for one link, recomputed about once a minute.
Kept rows: aggregation_period_sec = 900 (rows with 0 carry no reading), 0 < median_speed_fps < 100,
n_samples >= 3. Writes ~/.vital-city/street-pace/raw/YYYY-MM-DD.json.
"""
import datetime as dt, json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

IDS = {2021: 's7y8-dkgd', 2022: '2dzd-mqxq', 2023: 'pi8f-savx', 2024: '7ank-n7rd', 2025: '5dxh-vk2s', 2026: '6a2s-2t65'}
RAW = os.path.expanduser('~/.vital-city/street-pace/raw')

def fetch(day):
    out = os.path.join(RAW, day.isoformat() + '.json')
    if os.path.exists(out):
        return 'skip'
    nxt = day + dt.timedelta(days=1)
    q = ("SELECT sid, date_extract_hh(median_calculation_timestamp) as h, avg(median_speed_fps) as v, "
         "avg(median_tt_sec) as tt, count(*) as n "
         f"WHERE median_calculation_timestamp >= '{day}T00:00:00' AND median_calculation_timestamp < '{nxt}T00:00:00' "
         "AND aggregation_period_sec = 900 AND median_speed_fps > 0 AND median_speed_fps < 100 AND n_samples >= 3 "
         "GROUP BY sid, h LIMIT 50000")
    url = f"https://data.cityofnewyork.us/resource/{IDS[day.year]}.json?" + urllib.parse.urlencode({'$query': q})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=240) as r:
                rows = json.load(r)
            rows = [[int(x['sid']), int(x['h']), round(float(x['v']), 2), round(float(x['tt']), 1), int(x['n'])] for x in rows]
            tmp = out + '.tmp'
            json.dump(rows, open(tmp, 'w'), separators=(',', ':'))
            os.replace(tmp, out)
            return len(rows)
        except Exception as e:
            err = e
            time.sleep(5 * (attempt + 1))
    return f'FAIL {err}'

if __name__ == '__main__':
    start = dt.date.fromisoformat(sys.argv[1]); end = dt.date.fromisoformat(sys.argv[2])
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    with ThreadPoolExecutor(4) as ex:
        for d, res in zip(days, ex.map(fetch, days)):
            if res != 'skip':
                print(d, res, flush=True)
