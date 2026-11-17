#!/usr/bin/env python3
"""Build each project's corridor geometry -> corridors.json (+ corridors.geojson for eyeballing).

- DOT projects: NYC DOT bus lane features (../buslanes.csv, Open Data ycrg-ses3) matched on street + open date.
- 2026 projects: a GTFS shape of the named routes clipped between two cross-street points.
- 'other': every other DOT bus-lane feature dated 2023 or later (not one of the projects). These are only used
  to keep newly treated streets out of the control group.
"""
import csv, json, os, re
import numpy as np
from geo import to_xy, to_ll, cumlen, candidates, slice_line
from projects import PROJECTS
import gtfs_lib

HERE = os.path.dirname(os.path.abspath(__file__))
BUSLANES = os.path.join(HERE, '..', 'buslanes.csv')


def parse_geom(wkt):
    lines = []
    for part in re.findall(r'\(([^()]+)\)', wkt):
        pts = [tuple(map(float, p.split())) for p in part.split(',')]
        lines.append([[lo, la] for lo, la in pts])
    return lines


def dot_rows():
    with open(BUSLANES) as fh:
        return list(csv.DictReader(fh))


def gtfs_piece(feed, routes, start, end):
    r2s, shapes = gtfs_lib.load(feed)
    ps = to_xy([start[0]], [start[1]])[0]
    pe = to_xy([end[0]], [end[1]])[0]
    best = None
    for rt in routes:
        for sid in sorted(r2s.get(rt.upper(), ())):
            P, C = shapes[sid]
            ca = candidates(P, C, ps, 40)
            cb = candidates(P, C, pe, 40)
            for a, da in ca:
                for b, db in cb:
                    # shortest span wins (shapes can pass the same corner twice)
                    if b > a and (best is None or b - a < best[0]):
                        best = (b - a, rt, sid, slice_line(P, C, a, b))
    if best is None:
        raise SystemExit(f'no shape of {routes} passes both {start} and {end}')
    lat, lon = to_ll(best[3])
    return best[1], best[2], [[float(x), float(y)] for x, y in zip(lon, lat)]


def main():
    rows = dot_rows()
    out = {'projects': {}, 'other': []}
    used = set()
    gj = []
    for p in PROJECTS:
        feats = []
        kind = p['corridor'][0]
        if kind == 'dot':
            for street, datesub in p['corridor'][1]:
                for i, r in enumerate(rows):
                    if r['Street'] == street and datesub in r['Open_dates']:
                        used.add(i)
                        for line in parse_geom(r['the_geom']):
                            feats.append({'dir': r['Direction'].strip(), 'coords': line,
                                          'src': f"DOT {street} {r['Direction']} {r['Lane_Type']} open {r['Open_dates']}"})
        else:
            _, feed, routes, pieces = p['corridor']
            for start, end, d in pieces:
                rt, sid, line = gtfs_piece(feed, routes, start, end)
                feats.append({'dir': d, 'coords': line, 'src': f'GTFS {feed} {rt} shape {sid} clipped'})
        P = [to_xy([c[1] for c in f['coords']], [c[0] for c in f['coords']]) for f in feats]
        length = sum(cumlen(x)[-1] for x in P)
        out['projects'][str(p['id'])] = feats
        print(p['id'], p['name'], len(feats), 'features', f'{length:.0f} m of line (all directions)')
        for f in feats:
            gj.append({'type': 'Feature', 'properties': {'project': p['id'], 'dir': f['dir'], 'src': f['src']},
                       'geometry': {'type': 'LineString', 'coordinates': f['coords']}})
    for i, r in enumerate(rows):
        if i in used:
            continue
        yrs = [r['Year1'], r['Year2'], r['Year3']]
        if any(y >= '2023' for y in yrs if y):
            for line in parse_geom(r['the_geom']):
                out['other'].append({'dir': r['Direction'].strip(), 'coords': line,
                                     'src': f"DOT {r['Street']} {r['Direction']} open {r['Open_dates']}"})
    print('other 2023+ DOT features (control exclusion only):', len(out['other']))
    with open(os.path.join(HERE, 'corridors.json'), 'w') as fh:
        json.dump(out, fh)
    with open(os.path.join(HERE, 'corridors.geojson'), 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': gj}, fh)


if __name__ == '__main__':
    main()
