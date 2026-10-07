"""The check behind the two corrections: for every station the city published with coordinates,
does the point fall inside its listed ZIP code (city MODZCTA boundaries), and how far is it from
where the city's address search (GeoSearch) puts the same address? Prints the worst cases for a
person to read; it changes nothing. Corrections it led to live in CORRECT in build_data.py."""
import json, math, os, sys, urllib.request
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lookup import geosearch, save

ZF = os.path.join(HERE, 'modzcta.geojson')
if not os.path.exists(ZF):
    urllib.request.urlretrieve('https://data.cityofnewyork.us/api/geospatial/pri4-ifjk?method=export&format=GeoJSON', ZF)
polys, zips = [], []
for f in json.load(open(ZF))['features']:
    g = shape(f['geometry'])
    for z in f['properties']['zcta'].split(', '):
        polys.append(g); zips.append(z)
tree = STRtree(polys)


def zip_at(lat, lon):
    p = Point(lon, lat)
    return next((zips[i] for i in tree.query(p) if polys[i].contains(p)), None)


def metres(a, b, c, d):
    R = 6371000; p1, p2 = math.radians(a), math.radians(c)
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2))


seen, out = set(), []
for r in json.load(open(os.path.join(HERE, 'fc53-9hrv.json'))):
    if not r.get('latitude'):
        continue
    z = str(r.get('postcode') or '').split('.')[0]
    lat, lon = float(r['latitude']), float(r['longitude'])
    key = (r['street'].strip().lower(), z, lat, lon)
    if key in seen:
        continue
    seen.add(key)
    f = geosearch(f"{r['street'].strip()}, {z}")
    gd = metres(lat, lon, f['geometry']['coordinates'][1], f['geometry']['coordinates'][0]) if f else None
    out.append((zip_at(lat, lon) != z, gd or 0, r['station_name'], r['street'], z, zip_at(lat, lon), f['properties']['label'] if f else None))
save()
print(f'{len(out)} distinct published points; {sum(o[0] for o in out)} fall outside their listed ZIP code')
for o in sorted(out, key=lambda o: -o[1])[:40]:
    print(f'{o[1]:8.0f} m  outside-zip={o[0]!s:5}  {o[2]} | {o[3]} {o[4]} (point in {o[5]}) | GeoSearch: {o[6]}')
