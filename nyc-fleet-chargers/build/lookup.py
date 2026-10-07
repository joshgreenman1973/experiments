"""Cached lookups against four free geocoders. Every response is kept in cache_lookups.json,
so a rebuild never re-hits the services and the placements stay reproducible.

- GeoSearch: NYC Planning Labs, built on the city's own address file (PAD)
- Overpass: OpenStreetMap street network, used to find street intersections
- Nominatim: OpenStreetMap place search, used for named facilities (parks, piers, plants)
- Census: U.S. Census Bureau geocoder, used for the upstate watershed sites
"""
import json, os, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache_lookups.json')
_c = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
UA = 'nyc-fleet-chargers/1.0 (https://joshgreenman1973.github.io/experiments/nyc-fleet-chargers/)'


def _get(url, data=None, pause=0):
    key = url + ('|' + data if data else '')
    if key in _c:
        return _c[key]
    urls = [url]
    if 'overpass-api.de' in url:  # the main Overpass server rate-limits; fall back to mirrors
        urls += ['https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter']
    for attempt in range(6):
        u = urls[attempt % len(urls)]
        try:
            req = urllib.request.Request(u, data=data.encode() if data else None, headers={'User-Agent': UA})
            out = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except Exception as e:
            time.sleep(4 * (attempt + 1))
    else:
        raise RuntimeError(f'lookup failed: {url}')
    _c[key] = out
    save()
    if pause:
        time.sleep(pause)
    return out


def save():
    json.dump(_c, open(CACHE, 'w'))


def geosearch(text):
    j = _get('https://geosearch.planninglabs.nyc/v2/search?' + urllib.parse.urlencode({'text': text, 'size': 1}))
    return j['features'][0] if j.get('features') else None


def nominatim(q):
    j = _get('https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(
        {'q': q, 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'us'}), pause=1.1)
    return j[0] if j else None


def census(address):
    j = _get('https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?' + urllib.parse.urlencode(
        {'address': address, 'benchmark': 'Public_AR_Current', 'format': 'json'}))
    m = j['result']['addressMatches']
    return m[0] if m else None


OSM_BORO = {'MN': 'Manhattan', 'BK': 'Brooklyn', 'QN': 'Queens', 'BX': 'The Bronx', 'SI': 'Staten Island'}


def intersection(boro, street_a, street_b):
    """Nodes shared by two named streets inside one borough. Names are regexes (case-insensitive)."""
    q = f'''[out:json][timeout:90];
area["name"="{OSM_BORO[boro]}"]["boundary"="administrative"]->.b;
way(area.b)["highway"]["name"~"^({street_a})$",i]->.a;
way(area.b)["highway"]["name"~"^({street_b})$",i]->.c;
node(w.a)(w.c);
out;'''
    j = _get('https://overpass-api.de/api/interpreter', data='data=' + urllib.parse.quote(q), pause=1)
    pts = [(e['lat'], e['lon']) for e in j.get('elements', [])]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


# ---- City street centerline (CSCL, NYC Open Data inkn-q76z) -------------------------------
BOROCODE = {'MN': '1', 'BX': '2', 'BK': '3', 'QN': '4', 'SI': '5'}


def centerline(boro, name):
    """Street segments for one CSCL full_street_name in one borough. Directional prefixes in CSCL
    carry two spaces ("E  67 ST"); try the name as written, then that form."""
    from shapely.geometry import shape
    names = [name]
    parts = name.split(' ', 1)
    if parts[0] in ('E', 'W', 'N', 'S') and len(parts) == 2:
        names.append(parts[0] + '  ' + parts[1])
    for n in names:
        url = 'https://data.cityofnewyork.us/resource/inkn-q76z.json?' + urllib.parse.urlencode({
            '$select': 'the_geom', '$limit': 5000,
            '$where': f"full_street_name='{n}' AND boroughcode='{BOROCODE[boro]}'"})
        rows = _get(url)
        if rows:
            return [shape(r['the_geom']) for r in rows if r.get('the_geom')]
    return []


def corners(boro, a, b):
    """Every point where street a meets street b (a list; divided roads give several)."""
    from shapely.ops import unary_union
    ga, gb = centerline(boro, a), centerline(boro, b)
    if not ga or not gb:
        return []
    x = unary_union(ga).intersection(unary_union(gb))
    pts = [g for g in getattr(x, 'geoms', [x]) if not g.is_empty]
    out = []
    for g in pts:
        c = g.centroid
        out.append((c.y, c.x))
    return out
