#!/usr/bin/env python3
"""Give every MTA timepoint segment a street geometry and measure how much of it runs in each corridor.

Input: mta/<ROUTE>.csv (this folder first, then ../mta), corridors.json.
Geometry: the route's current GTFS shape between the two timepoint stops (stop coordinates from the MTA data,
snapped within 60 m), choosing the shape slice whose length best matches the MTA road_distance (within 20%).
If no shape of the route fits, any shape in the GTFS feeds that fits; failing that, the straight line between stops.
Overlap: share of the segment's length within 60 m of a corridor feature that runs parallel to it and, for one-way
treatments, in the same direction (geo.Corridor).
Output: segments.csv
"""
import csv, glob, json, os, statistics, sys, collections
import numpy as np
from geo import to_xy, to_ll, cumlen, candidates, slice_line, Corridor
from projects import PROJECTS
import gtfs_lib

HERE = os.path.dirname(os.path.abspath(__file__))
DIRS = [os.path.join(HERE, 'mta'), os.path.join(HERE, '..', 'mta')]
SNAP = 60.0
TOL = 0.20


def route_files():
    seen = {}
    for d in DIRS:
        for f in sorted(glob.glob(os.path.join(d, '*.csv'))):
            r = os.path.basename(f)[:-4]
            seen.setdefault(r, f)
    return seen


def needed_routes():
    s = set()
    for p in PROJECTS:
        s.update(p['routes'])
        s.update(p.get('extraRoutes', []))
    return s


def unique_segments(path):
    segs = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if not r['next_timepoint_stop_id'] or not r['next_timepoint_stop_latitude'] or not r['timepoint_stop_latitude']:
                continue
            k = (r['route_id'], r['direction'], r['timepoint_stop_id'], r['next_timepoint_stop_id'])
            s = segs.get(k)
            if s is None:
                s = segs[k] = dict(names=(r['timepoint_stop_name'], r['next_timepoint_stop_name']),
                                   a=(float(r['timepoint_stop_latitude']), float(r['timepoint_stop_longitude'])),
                                   b=(float(r['next_timepoint_stop_latitude']), float(r['next_timepoint_stop_longitude'])),
                                   rd=[], months=set())
            try:
                s['rd'].append(float(r['road_distance']))
            except ValueError:
                pass
            s['months'].add(f"{int(r['year'])}-{int(r['month']):02d}")
            s['names'] = (r['timepoint_stop_name'], r['next_timepoint_stop_name'])
    return segs


def best_slice(shapes, pa, pb, target):
    best = None
    for f, sid, P, C in shapes:
        ca = candidates(P, C, pa, SNAP)
        if not ca:
            continue
        cb = candidates(P, C, pb, SNAP)
        for a, _ in ca:
            for b, _ in cb:
                if b <= a:
                    continue
                err = abs((b - a) - target) / target
                if best is None or err < best[0]:
                    best = (err, f, sid, P, C, a, b)
    return best


_ALL = None


def geometry(route, seg):
    global _ALL
    pa = to_xy([seg['a'][0]], [seg['a'][1]])[0]
    pb = to_xy([seg['b'][0]], [seg['b'][1]])[0]
    target = statistics.median(seg['rd']) * 1609.344
    b = best_slice(gtfs_lib.route_shapes(route), pa, pb, target)
    if b and b[0] <= TOL:
        return slice_line(b[3], b[4], b[5], b[6]), f'route shape {b[2]}', b[0]
    if _ALL is None:
        _ALL = gtfs_lib.all_shapes(list(gtfs_lib.FEEDS))
    b2 = best_slice(_ALL, pa, pb, target)
    if b2 and b2[0] <= TOL:
        return slice_line(b2[3], b2[4], b2[5], b2[6]), f'other shape {b2[2]}', b2[0]
    P = np.array([pa, pb])
    return P, 'straight line', abs(np.hypot(*(pb - pa)) - target) / target


def main():
    cj = json.load(open(os.path.join(HERE, 'corridors.json')))
    mk = lambda feats: Corridor([(to_xy([c[1] for c in f['coords']], [c[0] for c in f['coords']]), f['dir'])
                                 for f in feats])
    cors = {pid: mk(feats) for pid, feats in cj['projects'].items()}
    other = mk(cj['other'])
    files = route_files()
    want = needed_routes() if len(sys.argv) < 2 else set(sys.argv[1:])
    missing = sorted(want - set(files))
    if missing:
        print('MISSING route files:', missing, file=sys.stderr)
    out = []
    geo_out = []
    for route in sorted(want & set(files)):
        segs = unique_segments(files[route])
        for k, s in sorted(segs.items()):
            P, method, err = geometry(route, s)
            row = dict(route=k[0], direction=k[1], from_id=k[2], to_id=k[3], from_name=s['names'][0],
                       to_name=s['names'][1], from_lat=s['a'][0], from_lon=s['a'][1], to_lat=s['b'][0], to_lon=s['b'][1],
                       miles=round(statistics.median(s['rd']), 3),
                       miles_min=min(s['rd']), miles_max=max(s['rd']),
                       first_month=min(s['months']), last_month=max(s['months']), n_months=len(s['months']),
                       geom=method, geom_len_err=round(err, 3))
            for pid, C in cors.items():
                row[f'ov{pid}'] = round(C.overlap(P)[0], 3)
            row['ov_other'] = round(other.overlap(P)[0], 3)
            out.append(row)
            lat, lon = to_ll(P)
            geo_out.append({'type': 'Feature', 'properties': {kk: row[kk] for kk in ('route', 'direction', 'from_name', 'to_name', 'geom')},
                            'geometry': {'type': 'LineString', 'coordinates': [[float(x), float(y)] for x, y in zip(lon, lat)]}})
        print(route, len(segs), 'segments', flush=True)
    with open(os.path.join(HERE, 'segments.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    with open(os.path.join(HERE, 'segments.geojson'), 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': geo_out}, fh)


if __name__ == '__main__':
    main()
