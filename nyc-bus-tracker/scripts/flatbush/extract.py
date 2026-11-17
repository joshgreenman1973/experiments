#!/usr/bin/env python3
"""Pull bus fixes for a set of corridors out of the bus-data snapshot archive.

For each date: reads every hour file from the blobless clone (lazily fetched),
keeps any fix inside one of the corridor boxes, plus every fix on the control
routes, and writes extracts/<date>.csv.gz. Skips dates already extracted.
"""
import csv, gzip, json, os, subprocess, sys
from datetime import datetime
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, 'busdata')
OUT = os.path.join(HERE, 'extracts')
SNAP = 'nyc-bus-tracker/data/snapshots'

# (name, south, west, north, east) generous boxes around each corridor
BOXES = [
    ('flatbush',   40.6380, -73.9850, 40.6960, -73.9200),  # Livingston St to Kings Plaza side
    ('midtown_e',  40.7360, -73.9920, 40.7620, -73.9640),  # Madison/Lexington/5th/3rd, 23rd-50th
    ('e116',       40.7930, -73.9560, 40.8060, -73.9270),
    ('fordham',    40.8520, -73.9180, 40.8760, -73.8650),
    ('bx161',      40.8150, -73.9350, 40.8350, -73.8950),
    ('tremont',    40.8350, -73.9200, 40.8560, -73.8300),
    ('baypkwy',    40.5800, -74.0150, 40.6350, -73.9650),
]
CONTROL_ROUTES = {'B41', 'B44', 'B44+', 'B46', 'B46+', 'B35', 'B6', 'B103', 'B67', 'B69', 'B45', 'B63'}


def in_box(lat, lon):
    for _, s, w, n, e in BOXES:
        if s <= lat <= n and w <= lon <= e:
            return True
    return False


def epoch(ts):
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return None


def do_date(date):
    dst = os.path.join(OUT, f'{date}.csv.gz')
    if os.path.exists(dst):
        return date, 'skip'
    ls = subprocess.run(['git', '-C', REPO, 'ls-tree', '--name-only', f'HEAD:{SNAP}/{date}'],
                        capture_output=True, text=True)
    hours = [h for h in ls.stdout.split() if h.endswith('.jsonl')]
    if not hours:
        return date, 'no files'
    n = 0
    tmp = dst + '.tmp'
    with gzip.open(tmp, 'wt', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['t', 'snap', 'vid', 'route', 'dir', 'lat', 'lon', 'phase', 'trip'])
        for h in sorted(hours):
            p = subprocess.Popen(['git', '-C', REPO, 'cat-file', '-p', f'HEAD:{SNAP}/{date}/{h}'],
                                 stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                snap = d.get('ts', '')
                for v in d.get('vehicles', []):
                    lat, lon = v.get('lat'), v.get('lon')
                    if lat is None or lon is None:
                        continue
                    r = v.get('route', '')
                    if r in CONTROL_ROUTES or in_box(lat, lon):
                        t = epoch(v.get('timestamp', ''))
                        if t is None:
                            continue
                        w.writerow([int(t), snap[11:19], v.get('id', '').replace('MTA NYCT_', '').replace('MTABC_', 'C'),
                                    r, v.get('dir', ''), lat, lon, v.get('phase', ''), v.get('trip', '')[-24:]])
                        n += 1
            p.wait()
    os.replace(tmp, dst)
    return date, n


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    dates = sys.argv[1:]
    with Pool(4) as pool:
        for date, res in pool.imap_unordered(do_date, dates):
            print(date, res, flush=True)
