#!/usr/bin/env python3
"""Build the geography layers used by the bus tracker and The People on the Bus.

Outputs:
  data/ridership/subway.json          subway lines (reference basemap) + stations
  data/ridership/crz.json             MTA congestion relief zone, split into
                                      the CBD polygon and the excluded roadways
  data/ridership/stops.json           adds m_to_subway + in_crz to each stop
  data/summary/route-classes.json     per route: bus-lane share + CBD relation

Every distance here is straight-line (haversine), never network distance.
Run: python3 scripts/build_geo_layers.py  (needs the source files under
scripts/geo-cache/, fetched by the same script when absent).

FAILS LOUD: exits nonzero if a source is empty or a sanity check trips.
"""
import json, csv, io, math, os, sys, zipfile, collections
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geo-cache')
os.makedirs(CACHE, exist_ok=True)

# Effective match tolerance for the bus-lane test, and the "beyond the subway"
# threshold. Both are stated verbatim in the pages' methodology.
LANE_MATCH_M = 60          # a route point counts as "on a bus lane" within this
LANE_DENSIFY_M = 15        # interpolation step along lane + route geometry
SUBWAY_FAR_M = 800         # "beyond the subway" cutoff (~half a mile)


def fetch(url, name, timeout=180):
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    print(f'  fetching {name}…', flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'nyc-bus-tracker'})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path, 'wb') as f:
        f.write(r.read())
    if os.path.getsize(path) < 1000:
        sys.exit(f'FATAL: {name} came back empty')
    return path


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def densify(coords, step_m):
    """Insert points so consecutive vertices are never more than step_m apart.
    Source geometry is vertex-only; without this, long straight runs of bus lane
    (median gap 57 m, max 563 m) would be invisible to a point-sampled test."""
    out = []
    for i in range(len(coords) - 1):
        (x1, y1), (x2, y2) = coords[i][:2], coords[i + 1][:2]
        out.append((x1, y1))
        d = haversine_m(x1, y1, x2, y2)
        n = int(d // step_m)
        for k in range(1, n + 1):
            t = k / (n + 1)
            out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    if coords:
        out.append(tuple(coords[-1][:2]))
    return out


def point_in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lon, lat, poly):
    """poly = list of rings, [0] outer, rest holes."""
    if not point_in_ring(lon, lat, poly[0]):
        return False
    return not any(point_in_ring(lon, lat, h) for h in poly[1:])


def ring_area_km2(ring):
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(a / 2) * (111.32 * 111.32 * math.cos(math.radians(40.75)))


print('── subway ──')
gtfs_path = fetch('http://web.mta.info/developers/data/nyct/subway/google_transit.zip',
                  'subway_gtfs.zip')
OFFICIAL = {'1': '#EE352E', '2': '#EE352E', '3': '#EE352E', '4': '#00933C', '5': '#00933C',
            '6': '#00933C', '7': '#B933AD', 'A': '#0039A6', 'C': '#0039A6', 'E': '#0039A6',
            'B': '#FF6319', 'D': '#FF6319', 'F': '#FF6319', 'M': '#FF6319', 'G': '#6CBE45',
            'J': '#996633', 'Z': '#996633', 'L': '#A7A9AC', 'N': '#FCCC0A', 'Q': '#FCCC0A',
            'R': '#FCCC0A', 'W': '#FCCC0A', 'S': '#808183', 'GS': '#808183', 'FS': '#808183',
            'H': '#808183', 'SI': '#0078C6'}

with zipfile.ZipFile(gtfs_path) as zf:
    with zf.open('trips.txt') as f:
        trips = collections.defaultdict(collections.Counter)
        for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
            if row.get('shape_id'):
                trips[row['route_id']][row['shape_id']] += 1
    with zf.open('shapes.txt') as f:
        shape_pts = collections.defaultdict(list)
        for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
            shape_pts[row['shape_id']].append(
                (int(row['shape_pt_sequence']), float(row['shape_pt_lon']), float(row['shape_pt_lat'])))

line_feats = []
for route, counter in trips.items():
    for shape_id, _ in counter.most_common(2):   # 2 busiest shapes ≈ both directions
        pts = sorted(shape_pts[shape_id])
        coords = [[round(lon, 5), round(lat, 5)] for _, lon, lat in pts][::3]  # decimated for size
        if len(coords) >= 2:
            line_feats.append({'type': 'Feature',
                               'properties': {'route': route, 'color': OFFICIAL.get(route, '#808183')},
                               'geometry': {'type': 'LineString', 'coordinates': coords}})

stations_raw = json.load(open(fetch('https://data.ny.gov/resource/39hk-dx4f.json?$limit=1000',
                                    'subway_stations.json')))
if len(stations_raw) < 400:
    sys.exit(f'FATAL: only {len(stations_raw)} subway stations returned')
stations = [[r['stop_name'], round(float(r['gtfs_longitude']), 5),
             round(float(r['gtfs_latitude']), 5), r.get('daytime_routes', '')]
            for r in stations_raw]
json.dump({'source': 'Lines: MTA subway GTFS shapes (two busiest shapes per route, every third '
                     'vertex) — a reference basemap layer, not a complete track map. '
                     'Stations: MTA Subway Stations (data.ny.gov 39hk-dx4f), all entrances '
                     'collapsed to one point per station.',
           'lines': {'type': 'FeatureCollection', 'features': line_feats},
           'stations': stations},
          open(f'{ROOT}/data/ridership/subway.json', 'w'), separators=(',', ':'))
print(f'  subway.json: {len(line_feats)} line segments, {len(stations)} stations')

print('── congestion relief zone ──')
crz_rows = json.load(open(fetch('https://data.ny.gov/resource/srxy-5nxn.json?$limit=100', 'crz.json')))
polys = []
for r in crz_rows:
    g = r['polygon']
    if g['type'] == 'Polygon':
        polys.append(g['coordinates'])
    elif g['type'] == 'MultiPolygon':
        polys.extend(g['coordinates'])
# The dataset ships unlabeled polygons. Per its own description the zone is
# "Manhattan south of and inclusive of 60th Street, NOT including the FDR Drive
# and the West Side Highway/Route 9A, the Battery Park Underpass and any surface
# roadway portion of the Hugh L. Carey Tunnel". The single large polygon is the
# CBD; the small ones are those excluded roadways. Verified below by area and by
# checking each small polygon sits inside the large one.
areas = [ring_area_km2(p[0]) for p in polys]
cbd_i = max(range(len(polys)), key=lambda i: areas[i])
cbd, exclusions = polys[cbd_i], [p for i, p in enumerate(polys) if i != cbd_i]
if areas[cbd_i] < 15 or areas[cbd_i] > 30:
    sys.exit(f'FATAL: CBD polygon area {areas[cbd_i]:.1f} km2 outside expected 15-30 km2')
for i, ex in enumerate(exclusions):
    cx = sum(p[0] for p in ex[0]) / len(ex[0])
    cy = sum(p[1] for p in ex[0]) / len(ex[0])
    if not point_in_ring(cx, cy, cbd[0]):
        print(f'  NOTE: exclusion polygon {i} centroid falls outside the CBD outline')
print(f'  CBD {areas[cbd_i]:.1f} km2 + {len(exclusions)} excluded roadway polygons '
      f'({", ".join(f"{a:.2f}" for i, a in enumerate(areas) if i != cbd_i)} km2)')
json.dump({'type': 'FeatureCollection',
           'source': 'MTA Central Business District Geofence (data.ny.gov srxy-5nxn). The '
                     'dataset does not label its polygons; the largest is taken as the CBD and '
                     'the remainder as the roadways the law excludes (FDR Drive, West Side '
                     'Highway/Route 9A, Battery Park Underpass, Hugh L. Carey Tunnel surface '
                     'connections).',
           'features': [{'type': 'Feature', 'properties': {'role': 'cbd'},
                         'geometry': {'type': 'Polygon', 'coordinates': cbd}}]
                       + [{'type': 'Feature', 'properties': {'role': 'excluded_roadway'},
                           'geometry': {'type': 'Polygon', 'coordinates': p}} for p in exclusions]},
          open(f'{ROOT}/data/ridership/crz.json', 'w'), separators=(',', ':'))

print('── stops: distance to subway + zone membership ──')
sp = json.load(open(f'{ROOT}/data/ridership/stops.json'))
st_pts = [(s[1], s[2]) for s in stations]
# Exact nearest-station search over all stations — no distance cap, no sentinel.
# Cheap equirectangular prefilter, exact haversine for the winner.
KX = 111320 * math.cos(math.radians(40.72))
KY = 110570
n_in, n_far = 0, 0
for s in sp['stops']:
    lon, lat = s[2], s[3]
    best_sq, best = None, None
    for slon, slat in st_pts:
        dx = (slon - lon) * KX
        dy = (slat - lat) * KY
        d2 = dx * dx + dy * dy
        if best_sq is None or d2 < best_sq:
            best_sq, best = d2, (slon, slat)
    d = haversine_m(lon, lat, best[0], best[1])
    inside = point_in_polygon(lon, lat, cbd) and not any(
        point_in_polygon(lon, lat, ex) for ex in exclusions)
    n_in += inside
    n_far += d > SUBWAY_FAR_M
    vals = [int(round(d)), 1 if inside else 0]
    if len(s) >= 11:
        s[9], s[10] = vals
    else:
        s.extend(vals)
sp['fields'] = sp['fields'][:9] + ['m_to_subway', 'in_crz']
sp['geo_notes'] = {
    'm_to_subway': 'Straight-line meters to the nearest MTA subway station (all 496 stations, '
                   'exact search, no cap). Not walking distance.',
    'in_crz': '1 if the stop is inside the MTA congestion relief zone: within the CBD polygon '
              'and not within one of the excluded roadway polygons.',
    'subway_far_threshold_m': SUBWAY_FAR_M,
}
json.dump(sp, open(f'{ROOT}/data/ridership/stops.json', 'w'), separators=(',', ':'))
dmax = max(s[9] for s in sp['stops'])
print(f'  {n_in} stops in the zone, {n_far} beyond {SUBWAY_FAR_M} m from a station '
      f'({100*n_far/len(sp["stops"]):.1f}%), farthest stop {dmax} m')

print('── route classes: bus lanes + CBD relation ──')
lanes = json.load(open(fetch('https://data.cityofnewyork.us/resource/ycrg-ses3.geojson?$limit=20000',
                             'bus_lanes.geojson')))
if len(lanes.get('features', [])) < 1000:
    sys.exit('FATAL: bus lane geometry looks truncated')
# Grid of densified lane points. Cell ≈ LANE_MATCH_M so a 3x3 lookup ≈ the
# tolerance we advertise.
CELL_LAT = LANE_MATCH_M / KY
CELL_LON = LANE_MATCH_M / KX
lane_cells = set()
for f in lanes['features']:
    g = f.get('geometry')
    if not g:
        continue
    parts = g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]
    for part in parts:
        for lon, lat in densify(part, LANE_DENSIFY_M):
            lane_cells.add((int(lon / CELL_LON), int(lat / CELL_LAT)))
print(f'  {len(lane_cells)} lane grid cells from densified geometry')


def near_lane(lon, lat):
    cx, cy = int(lon / CELL_LON), int(lat / CELL_LAT)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (cx + dx, cy + dy) in lane_cells:
                return True
    return False


cbd_routes = {r['route_id']: r['cbd_relation'] for r in
              json.load(open(fetch('https://data.ny.gov/resource/cgzt-smqf.json?$limit=500',
                                   'cbd_routes.json')))}
routes_fc = json.load(open(f'{ROOT}/data/routes/routes.geojson'))
classes = {}
for f in routes_fc['features']:
    rid = f['properties']['routeId']
    coords = f['geometry']['coordinates']
    if len(coords) < 2:
        continue
    pts = densify(coords, LANE_DENSIFY_M)   # evenly spaced, so share is by LENGTH
    hits = sum(1 for lon, lat in pts if near_lane(lon, lat))
    classes[rid] = {'busLaneShare': round(hits / len(pts), 3),
                    'cbd': cbd_routes.get(rid, 'Outside CBD')}
if len(classes) < 300:
    sys.exit(f'FATAL: only {len(classes)} routes classified')
json.dump({'generated_by': 'scripts/build_geo_layers.py',
           'busLaneShare': f'Share of a route\'s shape length running within about {LANE_MATCH_M} m '
                           f'of a marked bus lane or busway. Route and lane geometry are both '
                           f'densified to {LANE_DENSIFY_M} m before testing, so the figure is a '
                           f'length share, not a share of raw vertices. Source: NYC DOT Bus Lanes '
                           f'- Local Streets (data.cityofnewyork.us ycrg-ses3). Proximity does not '
                           f'prove the route uses the lane: a lane on a cross street it merely '
                           f'crosses can register.',
           'cbd': 'MTA Central Business District Bus Routes (data.ny.gov cgzt-smqf): "In CBD", '
                  '"Crossing CBD", or "Outside CBD" when the MTA does not list the route.',
           'routes': classes},
          open(f'{ROOT}/data/summary/route-classes.json', 'w'), separators=(',', ':'))
hi = sum(1 for c in classes.values() if c['busLaneShare'] >= 0.3)
lo = sum(1 for c in classes.values() if c['busLaneShare'] <= 0.1)
print(f'  {len(classes)} routes: {hi} at >=30% bus lane, {lo} at <=10%, '
      f'{len(classes)-hi-lo} in between; {sum(1 for c in classes.values() if c["cbd"]!="Outside CBD")} touch the CBD')
print('geo layers rebuilt.')
