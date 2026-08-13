"""Build a street-intersection gazetteer from the NYC Centerline file.

Centerline ships segments, not intersections. Where two segments share an
endpoint they meet, so snapping every endpoint to a ~1m grid and collecting the
street names that touch each node reconstructs the intersection set.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from streets import normalize

RAW = os.path.join(os.path.dirname(__file__), '..', 'raw')
BORO = {'1': 'MN', '2': 'BX', '3': 'BK', '4': 'QN', '5': 'ST'}


def main():
    segs = json.load(open(os.path.join(RAW, 'centerline.json')))
    print('segments', len(segs))

    # node key -> {normalized street name -> raw label}
    nodes = defaultdict(dict)
    node_boro = {}
    for s in segs:
        g = s.get('the_geom')
        label = s.get('stname_label') or s.get('full_street_name')
        if not g or not label:
            continue
        norm = normalize(label)
        if not norm:
            continue
        boro = BORO.get(str(s.get('boroughcode')), '')
        for line in g.get('coordinates', []):
            if len(line) < 2:
                continue
            for lon, lat in (line[0], line[-1]):
                # ~11m grid: tight enough to keep neighbouring corners apart on
                # a Manhattan block, loose enough to merge the several endpoints
                # a wide intersection contributes.
                key = (round(lon, 4), round(lat, 4))
                nodes[key][norm] = label
                node_boro[key] = boro

    print('endpoint nodes', len(nodes))

    # pair (streetA, streetB, borough) -> list of coordinates
    index = defaultdict(list)
    for key, names in nodes.items():
        if len(names) < 2:
            continue
        boro = node_boro.get(key, '')
        keys = sorted(names)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                index[(keys[i], keys[j], boro)].append(key)

    print('street pairs', len(index))

    # Collapse duplicate nodes for the same pair to their centroid; a wide
    # intersection contributes several endpoints only a few metres apart.
    out = {}
    for (a, b, boro), pts in index.items():
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        out['%s|%s|%s' % (a, b, boro)] = [round(lon, 6), round(lat, 6), len(pts)]

    if len(out) < 40000:
        raise SystemExit('FAIL: intersection index looks too small (%d)' % len(out))

    path = os.path.join(RAW, 'intersection_index.json')
    json.dump(out, open(path, 'w'))
    print('wrote', len(out), 'pairs ->', path)


if __name__ == '__main__':
    main()
