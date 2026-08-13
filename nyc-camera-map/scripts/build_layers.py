"""Assemble every camera source into the layer files the map loads.

Layers come from four kinds of evidence, and the map keeps them separate on
purpose because they are not equally trustworthy:

  official   NYC DOT's own live traffic camera feed. Exact.
  derived    Enforcement cameras reconstructed from the tickets they wrote.
  surveyed   Amnesty International's 2021 volunteer survey of intersections.
  crowdsourced  OpenStreetMap / DeFlock contributions. Real but very patchy.
"""
import csv
import json
import math
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw')
DATA = os.path.join(HERE, '..', 'data')


# ---------------------------------------------------------------- geography

def load_boroughs():
    gj = json.load(open(os.path.join(RAW, 'borough_boundaries.geojson')))
    polys = []
    for f in gj['features']:
        name = f['properties']['boroname']
        for poly in f['geometry']['coordinates']:
            ring = poly[0]
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            polys.append((name, ring, min(xs), min(ys), max(xs), max(ys)))
    return polys


def borough_of(lon, lat, polys):
    for name, ring, x0, y0, x1, y1 in polys:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        inside = False
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > lat) != (yj > lat):
                if lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
                    inside = not inside
            j = i
        if inside:
            return name
    return None


# ------------------------------------------------------------------ sources

def dot_traffic_cameras(polys):
    cams = json.load(open(os.path.join(RAW, 'dot_traffic_cameras.json')))
    out = []
    for c in cams:
        try:
            lon, lat = float(c['longitude']), float(c['latitude'])
        except (TypeError, ValueError, KeyError):
            continue
        if not borough_of(lon, lat, polys):
            continue
        out.append({
            'lon': round(lon, 6), 'lat': round(lat, 6),
            'name': c.get('name', ''),
            'boro': c.get('area', ''),
            'online': str(c.get('isOnline')).lower() == 'true',
            'img': c.get('imageUrl', ''),
        })
    if len(out) < 500:
        raise SystemExit('FAIL: DOT traffic cameras look wrong (%d)' % len(out))
    return out


def enforcement_cameras(polys):
    src = json.load(open(os.path.join(RAW, 'enforcement_located.json')))
    out = {}
    for kind, recs in src.items():
        rows = []
        for r in recs:
            boro = borough_of(r['lon'], r['lat'], polys) or r.get('borough') or ''
            rows.append({
                'lon': r['lon'], 'lat': r['lat'],
                'street': r['street'], 'cross': r['cross'],
                'dir': r.get('direction', ''),
                'boro': boro,
                'tickets': r['tickets'],
                'first': (r.get('first_seen') or '')[:10],
                'last': (r.get('last_seen') or '')[:10],
                'fuzzy': 1 if r.get('match') == 'fuzzy' else 0,
            })
        rows.sort(key=lambda r: -r['tickets'])
        out[kind] = rows
    if len(out.get('speed', [])) < 1500:
        raise SystemExit('FAIL: too few speed cameras located')
    return out


# OSM operator strings, normalized to the body that actually runs the camera.
OPERATORS = [
    ('nypd', r'\bnypd\b|police department of the city|new york (city )?police|n\.?y\.?p\.?d'),
    ('dot', r'department of transportation|\bd\.?o\.?t\b|dept of transportation'),
    ('mta', r'\bmta\b|m\.?t\.?a|metropolitan trans|bridges and tunnels|metropolitan transit'),
    ('panynj', r'panynj|port authority|port of authority'),
    ('other_gov', r'department of environmental|sanitation|parks|nycha|dep\b|'
                  r'new york state|nysdot|county police|state police|'
                  r'fire department|correction'),
]


def classify_operator(op):
    if not op:
        return 'unknown'
    o = op.lower()
    for key, pattern in OPERATORS:
        if re.search(pattern, o):
            return key
    return 'private'


def osm_surveillance(polys):
    els = json.load(open(os.path.join(RAW, 'osm_surveillance.json')))['elements']
    out = defaultdict(list)
    for e in els:
        lon = e.get('lon') or (e.get('center') or {}).get('lon')
        lat = e.get('lat') or (e.get('center') or {}).get('lat')
        if lon is None or lat is None:
            continue
        boro = borough_of(lon, lat, polys)
        if not boro:
            continue                       # New Jersey, Westchester, Nassau
        t = e.get('tags', {})
        stype = (t.get('surveillance:type') or '').lower()
        if t.get('highway') == 'speed_camera':
            stype = 'speed_camera'
        if not stype:
            stype = 'camera'
        op = t.get('operator') or t.get('operator:short') or ''
        rec = {
            'lon': round(lon, 6), 'lat': round(lat, 6),
            'boro': boro,
            'op': op,
            'opkey': classify_operator(op),
            'zone': t.get('surveillance:zone') or t.get('surveillance') or '',
            'mount': t.get('camera:mount') or t.get('support') or '',
            'dir': t.get('camera:direction') or t.get('direction') or '',
            'make': t.get('manufacturer') or t.get('brand') or '',
            'name': t.get('name') or '',
            'osm': '%s/%s' % (e['type'], e['id']),
        }
        if stype == 'alpr':
            out['alpr'].append(rec)
        elif stype == 'gunshot_detector':
            out['gunshot'].append(rec)
        elif stype == 'speed_camera':
            out['osm_speed'].append(rec)
        elif stype in ('camera', 'guard', 'sensor'):
            out['cctv'].append(rec)
    if len(out['alpr']) < 800:
        raise SystemExit('FAIL: OSM ALPR count looks wrong (%d)' % len(out['alpr']))
    return out


def amnesty_survey(polys):
    """2021 volunteer survey: cameras visible at each surveyed intersection."""
    path = os.path.join(RAW, 'amnesty_counts_per_intersections.csv')
    rows = []
    totals = {'surveyed': 0, 'cameras': 0, 'street': 0, 'building': 0,
              'dome': 0, 'bullet': 0, 'with_camera': 0}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                lat, lon = float(r['Lat']), float(r['Long'])
            except (TypeError, ValueError):
                continue
            n = int(float(r['n_cameras_median'] or 0))
            street = int(float(r['attached_street_median'] or 0))
            building = int(float(r['attached_building_median'] or 0))
            totals['surveyed'] += 1
            totals['cameras'] += n
            totals['street'] += street
            totals['building'] += building
            totals['dome'] += int(float(r['type_dome_median'] or 0))
            totals['bullet'] += int(float(r['type_bullet_median'] or 0))
            if n <= 0:
                continue
            totals['with_camera'] += 1
            rows.append([round(lon, 5), round(lat, 5), n, street, building,
                         (r.get('ImageDate') or '')[:7]])
    if totals['cameras'] < 20000:
        raise SystemExit('FAIL: Amnesty survey totals look wrong')
    return rows, totals


# ------------------------------------------------------------------- output

def near(a, b, metres):
    dy = (a['lat'] - b['lat']) * 111320.0
    dx = (a['lon'] - b['lon']) * 84000.0
    return dx * dx + dy * dy <= metres * metres


def flag_overlaps(osm_alpr, enforcement):
    """Mark OSM plate readers that sit on top of a camera we derived ourselves.

    DeFlock volunteers sometimes log a school-zone speed camera as a plate
    reader, so the two layers can double-count the same hardware.
    """
    grid = defaultdict(list)
    for kind, rows in enforcement.items():
        for r in rows:
            grid[(round(r['lon'], 3), round(r['lat'], 3))].append(r)
    n = 0
    for a in osm_alpr:
        gx, gy = round(a['lon'], 3), round(a['lat'], 3)
        hit = False
        for dx in (-0.001, 0, 0.001):
            for dy in (-0.001, 0, 0.001):
                for b in grid.get((round(gx + dx, 3), round(gy + dy, 3)), []):
                    if near(a, b, 40):
                        hit = True
        a['dup'] = 1 if hit else 0
        n += hit
    return n


def main():
    polys = load_boroughs()
    os.makedirs(DATA, exist_ok=True)

    dot = dot_traffic_cameras(polys)
    enf = enforcement_cameras(polys)
    osm = osm_surveillance(polys)
    amnesty_rows, amnesty_totals = amnesty_survey(polys)

    overlaps = flag_overlaps(osm['alpr'], enf)

    layers = {
        'dot_traffic': dot,
        'speed': enf['speed'],
        'redlight': enf['redlight'],
        'buslane': enf['buslane'],
        'alpr': osm['alpr'],
        'cctv': osm['cctv'],
        'gunshot': osm['gunshot'],
    }
    for name, rows in layers.items():
        json.dump(rows, open(os.path.join(DATA, '%s.json' % name), 'w'),
                  separators=(',', ':'))

    json.dump(amnesty_rows, open(os.path.join(DATA, 'amnesty.json'), 'w'),
              separators=(',', ':'))

    by_operator = defaultdict(int)
    for r in osm['alpr']:
        by_operator[r['opkey']] += 1
    cctv_by_operator = defaultdict(int)
    for r in osm['cctv']:
        cctv_by_operator[r['opkey']] += 1

    boro_counts = {}
    for name, rows in layers.items():
        c = defaultdict(int)
        for r in rows:
            c[r.get('boro') or 'Unknown'] += 1
        boro_counts[name] = dict(c)

    stats = json.load(open(os.path.join(DATA, 'enforcement_stats.json')))
    summary = {
        'counts': {k: len(v) for k, v in layers.items()},
        'alpr_by_operator': dict(by_operator),
        'cctv_by_operator': dict(cctv_by_operator),
        'by_borough': boro_counts,
        'amnesty': amnesty_totals,
        'amnesty_points': len(amnesty_rows),
        'alpr_overlapping_enforcement': overlaps,
        'enforcement_match': stats,
        'tickets': {k: sum(r['tickets'] for r in enf[k]) for k in enf},
    }
    json.dump(summary, open(os.path.join(DATA, 'summary.json'), 'w'), indent=1)

    print(json.dumps(summary['counts'], indent=1))
    print('ALPR by operator:', dict(by_operator))
    print('CCTV by operator:', dict(cctv_by_operator))
    print('Amnesty:', amnesty_totals)
    print('OSM plate readers within 40m of a derived enforcement camera:', overlaps)


if __name__ == '__main__':
    main()
