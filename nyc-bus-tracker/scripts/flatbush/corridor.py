#!/usr/bin/env python3
"""Bus speeds along Flatbush Avenue, by stretch, from the tracker's GPS extracts.

Method (same rules as the tracker's history):
- reference line = GTFS shape B410126 (B41 southbound, Livingston St to Kings Plaza)
- each fix is projected onto that line; fixes more than LAT_TOL metres off it are ignored
- consecutive fixes of the same bus, 15-180 s apart by GPS timestamp, form a pair;
  the pair's along-line distance and time are split across stretches in proportion
  to how much of the pair's span falls in each (a stationary pair goes to the stretch it sits in)
- speed for a stretch = total distance / total time (time-weighted, includes stops and dwell)
- layover phases dropped; any bus on Flatbush counts (B41 and others) unless --route given
Output: corridor_pairs.csv with date, hour, direction, stretch, route, metres, seconds
"""
import csv, glob, gzip, math, os, sys, collections
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
LAT_TOL = 35.0

# Cut points north to south (lat, lon)
CUTS = [
    ('Livingston St', 40.68730, -73.97990),
    ('Atlantic Av', 40.68448, -73.97772),
    ('Grand Army Plaza', 40.67500, -73.97090),
    ('Empire Blvd', 40.66301, -73.96221),
    ('Church Av', 40.65032, -73.95871),
    ('Nostrand Av', 40.63230, -73.94722),
    ('Avenue P', 40.61920, -73.93331),
    ('Kings Plaza', 40.60930, -73.92154),
]
STRETCH = [f'{CUTS[i][0]} to {CUTS[i+1][0]}' for i in range(len(CUTS) - 1)]

R = 6371000.0
LAT0 = math.radians(40.65)


def xy(lat, lon):
    return (math.radians(lon) * R * math.cos(LAT0), math.radians(lat) * R)


def load_shape():
    pts = []
    with open(os.path.join(HERE, 'gtfs/b/shapes.txt')) as fh:
        for r in csv.DictReader(fh):
            if r['shape_id'] == 'B410126':
                pts.append((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon'])))
    pts.sort()
    P = [xy(la, lo) for _, la, lo in pts]
    cum = [0.0]
    for i in range(1, len(P)):
        cum.append(cum[-1] + math.dist(P[i - 1], P[i]))
    return P, cum


P, CUM = load_shape()
# grid index of segments for fast projection
CELL = 200.0
GRID = collections.defaultdict(list)
for i in range(len(P) - 1):
    (x1, y1), (x2, y2) = P[i], P[i + 1]
    for gx in range(int(min(x1, x2) // CELL) - 1, int(max(x1, x2) // CELL) + 2):
        for gy in range(int(min(y1, y2) // CELL) - 1, int(max(y1, y2) // CELL) + 2):
            GRID[(gx, gy)].append(i)


def project(lat, lon):
    x, y = xy(lat, lon)
    best = None
    for i in GRID.get((int(x // CELL), int(y // CELL)), ()):
        (x1, y1), (x2, y2) = P[i], P[i + 1]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        px, py = x1 + t * dx, y1 + t * dy
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            best = (d, CUM[i] + t * math.sqrt(L2))
    if best is None or best[0] > LAT_TOL:
        return None
    return best[1]


CUT_S = [project(la, lo) for _, la, lo in CUTS]
assert all(c is not None for c in CUT_S), CUT_S
assert all(CUT_S[i] < CUT_S[i + 1] for i in range(len(CUT_S) - 1)), CUT_S

ET = timezone(timedelta(hours=-5))


def et_hour(t):
    # DST-correct local hour via zoneinfo
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(t, ZoneInfo('America/New_York'))


def main():
    out = open(os.path.join(HERE, 'corridor_pairs.csv'), 'w', newline='')
    w = csv.writer(out)
    w.writerow(['date', 'hour', 'dir', 'stretch', 'route', 'm', 's'])
    from zoneinfo import ZoneInfo
    NY = ZoneInfo('America/New_York')
    for f in sorted(glob.glob(os.path.join(HERE, 'extracts/*.csv.gz'))):
        date = os.path.basename(f)[:10]
        fixes = collections.defaultdict(list)
        with gzip.open(f, 'rt') as fh:
            for r in csv.DictReader(fh):
                if 'LAYOVER' in r['phase'].upper():
                    continue
                lat, lon = float(r['lat']), float(r['lon'])
                if not (40.600 <= lat <= 40.692 and -73.985 <= lon <= -73.915):
                    continue
                s = project(lat, lon)
                if s is None or s < CUT_S[0] - 50 or s > CUT_S[-1] + 50:
                    continue
                fixes[r['vid']].append((int(r['t']), s, r['route']))
        acc = collections.defaultdict(lambda: [0.0, 0.0])
        for vid, fx in fixes.items():
            fx = sorted(set(fx))
            pairs = []
            for (t1, s1, r1), (t2, s2, r2) in zip(fx, fx[1:]):
                dt = t2 - t1
                if dt < 15 or dt > 180 or r1 != r2:
                    pairs.append(None)
                    continue
                ds = s2 - s1
                if abs(ds) / dt > 22:   # >49 mph: GPS jump
                    pairs.append(None)
                    continue
                d = 'S' if ds > 5 else ('N' if ds < -5 else None)
                pairs.append([t1, s1, s2, dt, d, r1])
            # stationary pairs take the direction of the nearest moving pair (earlier first)
            last = None
            for p in pairs:
                if p is None:
                    last = None
                    continue
                if p[4] is None:
                    p[4] = last
                else:
                    last = p[4]
            nxt = None
            for p in reversed(pairs):
                if p is None:
                    nxt = None
                    continue
                if p[4] is None:
                    p[4] = nxt
                else:
                    nxt = p[4]
            for p in pairs:
                if p is None or p[4] is None:
                    continue
                t1, s1, s2, dt, direction, r1 = p
                lo, hi = min(s1, s2), max(s1, s2)
                hr = datetime.fromtimestamp(t1, NY).hour
                for k in range(len(STRETCH)):
                    a, b = CUT_S[k], CUT_S[k + 1]
                    if hi - lo <= 5:
                        if a <= (lo + hi) / 2 < b:
                            acc[(hr, direction, k, r1)][0] += hi - lo
                            acc[(hr, direction, k, r1)][1] += dt
                        continue
                    ov = min(hi, b) - max(lo, a)
                    if ov <= 0:
                        continue
                    frac = ov / (hi - lo)
                    acc[(hr, direction, k, r1)][0] += ov
                    acc[(hr, direction, k, r1)][1] += dt * frac
        for (hr, d, k, route), (m, s) in acc.items():
            w.writerow([date, hr, d, k, route, round(m, 1), round(s, 1)])
        print(date, len(fixes), flush=True)
    out.close()


if __name__ == '__main__':
    main()
