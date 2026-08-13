"""Pull every distinct camera-ticket location out of the FY2026 violations file.

Three violation codes are written by fixed cameras rather than by a person:
  36  PHTO SCHOOL ZN SPEED VIOLATION   school-zone speed cameras
   7  FAILURE TO STOP AT RED LIGHT     red light cameras
   5  BUS LANE VIOLATION               fixed bus lane cameras

Grouping by location collapses millions of tickets down to the set of corners
that were writing them, which is the camera list the city will not publish.
min/max issue_date give the window each camera was active in.
"""
import json
import os
import time
import urllib.parse
import urllib.request

DATASET = 'pvqr-7yc4'          # Parking Violations Issued - Fiscal Year 2026
BASE = 'https://data.cityofnewyork.us/resource/%s.json?' % DATASET
CODES = {'36': 'speed', '7': 'redlight', '5': 'buslane'}


def soda(params, timeout=600):
    url = BASE + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            print('retry', e, flush=True)
            time.sleep(8)
    raise SystemExit('FAILED ' + url)


def main():
    out = {}
    for code, kind in CODES.items():
        t = time.time()
        rows = soda({
            '$select': ('street_name,intersecting_street,violation_county,'
                        'count(*) as n,min(issue_date) as first_seen,'
                        'max(issue_date) as last_seen'),
            '$where': "violation_code='%s'" % code,
            '$group': 'street_name,intersecting_street,violation_county',
            '$limit': 50000,
        })
        if not rows:
            raise SystemExit('FAIL: no rows for %s' % kind)
        out['%s|%s' % (kind, DATASET)] = rows
        print('DONE', kind, len(rows), '%.1fs' % (time.time() - t), flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'violation_locations.json'), 'w'))
    print('ALL DONE')


if __name__ == '__main__':
    main()
