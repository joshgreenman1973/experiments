#!/usr/bin/env python3
"""Download MTA Bus Route Segment Speeds for given routes (2023-24 + 2025-present).

Usage: mta_seg.py ROUTE [ROUTE...]  -> mta/<ROUTE>.csv
Weekday rows only (Mon-Fri), all hours; aggregation happens later.
"""
import csv, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'mta')
SETS = ['58t6-89vi', 'kufs-yh3x']
COLS = ['year', 'month', 'day_of_week', 'hour_of_day', 'route_id', 'direction', 'stop_order',
        'timepoint_stop_id', 'timepoint_stop_name', 'next_timepoint_stop_id', 'next_timepoint_stop_name',
        'timepoint_stop_latitude', 'timepoint_stop_longitude', 'next_timepoint_stop_latitude',
        'next_timepoint_stop_longitude', 'road_distance', 'average_travel_time', 'bus_trip_count']


def get(ds, where, offset):
    q = {'$select': ','.join(COLS), '$where': where, '$limit': 50000, '$offset': offset,
         '$order': 'year,month,route_id,direction,stop_order,day_of_week,hour_of_day'}
    url = f'https://data.ny.gov/resource/{ds}.json?' + urllib.parse.urlencode(q)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception as e:
            print('retry', ds, offset, e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f'failed {ds} {offset}')


def main():
    os.makedirs(OUT, exist_ok=True)
    for route in sys.argv[1:]:
        dst = os.path.join(OUT, f'{route}.csv')
        rows = []
        for ds in SETS:
            where = (f"route_id='{route}' and day_of_week in "
                     "('Monday','Tuesday','Wednesday','Thursday','Friday')")
            off = 0
            while True:
                b = get(ds, where, off)
                rows += b
                if len(b) < 50000:
                    break
                off += 50000
        if not rows:
            raise SystemExit(f'no rows for {route}')
        with open(dst, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, '') for k in COLS})
        print(route, len(rows), flush=True)


if __name__ == '__main__':
    main()
