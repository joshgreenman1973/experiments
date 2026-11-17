"""Load MTA GTFS shapes (route -> shapes) from the unzipped feeds."""
import csv, os, collections
import numpy as np
from geo import to_xy, cumlen

HERE = os.path.dirname(os.path.abspath(__file__))
FEEDS = {
    'b': os.path.join(HERE, '..', 'gtfs', 'b'),
    'm': os.path.join(HERE, '..', 'gtfs', 'm'),
    'bx': os.path.join(HERE, '..', 'gtfs', 'bx'),
    'q': os.path.join(HERE, 'gtfs', 'q'),
    'busco': os.path.join(HERE, 'gtfs', 'busco'),
    'si': os.path.join(HERE, 'gtfs', 'si'),
}
_cache = {}


def load(feed):
    """Returns (route -> set(shape_id), shape_id -> (xy, cum))."""
    if feed in _cache:
        return _cache[feed]
    d = FEEDS[feed]
    r2s = collections.defaultdict(set)
    with open(os.path.join(d, 'trips.txt')) as fh:
        for r in csv.DictReader(fh):
            if r['shape_id']:
                r2s[r['route_id'].upper()].add(r['shape_id'])
    pts = collections.defaultdict(list)
    with open(os.path.join(d, 'shapes.txt')) as fh:
        for r in csv.DictReader(fh):
            pts[r['shape_id']].append((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon'])))
    shapes = {}
    for sid, L in pts.items():
        L.sort()
        P = to_xy([x[1] for x in L], [x[2] for x in L])
        shapes[sid] = (P, cumlen(P))
    _cache[feed] = (r2s, shapes)
    return _cache[feed]


def route_shapes(route):
    """All shapes for a route id across feeds (route ids upper-cased)."""
    out = []
    for f in FEEDS:
        r2s, shapes = load(f)
        for sid in sorted(r2s.get(route.upper(), ())):
            out.append((f, sid) + shapes[sid])
    return out


def all_shapes(feeds):
    out = []
    for f in feeds:
        _, shapes = load(f)
        for sid, (P, C) in shapes.items():
            out.append((f, sid, P, C))
    return out
