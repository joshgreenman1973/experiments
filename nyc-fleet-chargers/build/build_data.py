"""Build data/sites.json and data/chargers.csv for the NYC fleet charger map.

Source: NYC Open Data, "NYC EV Fleet Station Network" (fc53-9hrv), published by DCAS.
One row per charging station. 318 rows arrive without coordinates; every one of those is placed
below by an explicit, logged rule, and every placement is written to build/placement_log.csv.

Run:  python3 build/build_data.py            (uses the cached snapshot in build/fc53-9hrv.json)
      python3 build/build_data.py --refresh  (downloads the dataset again first)
"""
import csv, collections, json, math, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from lookup import geosearch, nominatim, census, corners, save as save_cache
from curbside import CURB, CORNER

SRC = os.path.join(HERE, 'fc53-9hrv.json')
if '--refresh' in sys.argv or not os.path.exists(SRC):
    urllib.request.urlretrieve('https://data.cityofnewyork.us/resource/fc53-9hrv.json?$limit=50000', SRC)
rows = json.load(open(SRC))
if len(rows) < 1000:
    sys.exit(f'FAIL: only {len(rows)} rows in the source; refusing to build')

AGENCY = {
    'DPR': 'Parks Department', 'DEP': 'Environmental Protection', 'DSNY': 'Sanitation',
    'NYPD': 'Police Department', 'DOT': 'Transportation', 'DOE': 'Education Department',
    'DOC': 'Correction', 'DCAS': 'Citywide Administrative Services', 'FDNY': 'Fire Department',
    'NYCEM': 'Emergency Management', 'DHS': 'Homeless Services', 'HRA': 'Human Resources Administration',
    'NYCHA': 'Housing Authority', 'OCME': 'Medical Examiner', 'TLC': 'Taxi and Limousine Commission',
    'DOH': 'Health Department', 'DOF': 'Finance', 'DDC': 'Design and Construction',
    'ACS': "Children's Services", 'CITYHALL': 'City Hall', 'DOB': 'Buildings',
    'HPD': 'Housing Preservation and Development', 'OTI': 'Technology and Innovation',
    'QPL': 'Queens Public Library', 'PROB': 'Probation',
}
# charger type -> short key used by the page
KIND = {
    'Level 2 Charger': 'l2', 'Level 3 Fast Charger': 'dcfc', 'EV Solar Arc Charger': 'solar',
    'EV Solar Canopy Charger': 'canopy', 'L2 DOT Flo Curbside Charger': 'curb',
    'DOT Municipal Level 2 Charger': 'lot2', 'DOT Municipal Level 3 Charger': 'lot3',
    'Mobile Charger': 'mobile',
}

# DCAS "Public Charger Locations", updated 9/23/2026 (electric-vehicle-public-charging-rules.pdf).
# 26 fast-charger stations and 4 solar carports, matching the October 2026 map's legend.
DCAS_PUBLIC = {'DPR_VCP-S1', 'DPR_ICAHN_1_L3', 'DPR_ICAHN_2_L3', 'DPR_ICAHN_3_L3', 'DCASCSTHSE_1_L3',
               'DCASCSTHSE_2_L3', 'DCASCSTHSE_3_L3', 'DPRWFMARNA_1_L3', 'DPRWFMARNA_2_L3', 'DPRWFMARNA_3_L3',
               'DPRWFMARNA_4_L3', 'DPRWFMARNA_5_L3', 'DPRWFMARINA-S2', 'DPRWFMARINA-S3', 'DPRROCKAWAY30B',
               'DPRMBLOT8_1_L3', 'DPRMBLOT8_2_L3', 'DPROCBRZAC_1_L3', 'DPROCBRZAC_2_L3', 'DEP_ARKVLE_1_L3'} | \
              {f'DPR_FPBND_{i}_L3' for i in range(1, 11)}

# --- placement rules for rows without usable coordinates ------------------------------------
# kinds: same = put with another listed address (named), geo = city geocoder, nom = OpenStreetMap
# place search, cen = Census geocoder. precision: address | facility | approx
RIKERS = ('same', 'Rikers Island', 'approx', 'Rikers Island; the listed address does not pin down a spot on the island')
BY_STREET = {
    'Union Tpke/Queens Blvd': ('same', '120-55 Queens Blvd', 'facility', 'Queens Borough Hall, with the rest of its station group'),
    '2 31St St': ('same', '30-20 Thomson Ave', 'facility', 'Design and Construction headquarters in Long Island City, with the rest of its station group'),
    '165 Schroeders Ave': ('same', '1540 Van Siclen Ave', 'facility', '26th Ward wastewater plant, with the rest of its station group'),
    '4 Central Rd': ('same', '116 K Rd', 'facility', 'Wards Island wastewater plant, with the rest of its station group'),
    '3002 Knapp St': ('same', '2509 Knapp St', 'facility', 'Coney Island wastewater plant, with the rest of its station group'),
    '106 Beach Channel Dr': ('geo', '106-21 Beach Channel Drive, Queens', 'facility', 'Rockaway wastewater plant, 106-21 Beach Channel Drive'),
    '5-36 Beach Channel Dr': ('geo', '106-21 Beach Channel Drive, Queens', 'facility', 'Rockaway wastewater plant, 106-21 Beach Channel Drive'),
    '182 Powells Cove Blvd': ('geo', '127-01 Powells Cove Boulevard, Queens', 'facility', 'Tallman Island wastewater plant, 127-01 Powells Cove Boulevard'),
    'Rivers Edge Rd': ('same', '10 Central Rd', 'facility', 'Icahn Stadium on Randalls Island, with the rest of its station group'),
    'West Facility Cib': ('geo', 'West Facility Cib, 11370', 'facility', 'West Facility, Rikers Island'),
    '11-11 Hazen Street': ('geo', '11-11 Hazen Street, Queens', 'address', None),
    'Hazen St': RIKERS, '0 Hazen St': RIKERS, '14 Hazen St': RIKERS, '15 Hazen St': RIKERS, 'Hillside Ave': RIKERS,
    'SDC OFFICE': RIKERS, '15B West 5th Street East Elmhurst': RIKERS, '15 W 5th St': RIKERS,
    '1 Construction Way': RIKERS, '50 Construction Way': RIKERS, '120 Construction Way': RIKERS,
    'Rikers Is Br Appr': RIKERS, '30 N Perimeter Rd': RIKERS,
    '21 Safety City Blvd': ('nom', 'Michael J. Petrides School, Staten Island', 'facility', 'Michael J. Petrides School campus'),
    '2195 Bathgate Ave': ('geo', '2195 Bathgate Avenue, Bronx', 'address', 'listed with a Manhattan ZIP code; the address is in the Bronx'),
    '5-1-5-41 44Th Dr': ('geo', '5-41 44 Drive, Queens', 'address', None),
    '90-24-90-26 Sutphin Blvd': ('geo', '90-24 Sutphin Boulevard, Queens', 'address', None),
    '58-50 57th R': ('same', '58-50 57th Rd', 'address', None),
    '57-39 58th Pl': ('geo', '57-39 58 Place, Queens', 'address', None),
    '3551 Richmond Terrace': ('geo', '3551 Richmond Terrace, Staten Island', 'address', None),
    '240- 2 128th Ave': ('geo', '240-02 128 Avenue, Queens', 'address', None),
    '300 Altamont st': ('geo', '300 Altamont Street, Staten Island', 'approx', 'on Altamont Street; the house number could not be matched'),
    '875 Exterior Street': ('nom', 'Mill Pond Park, Bronx', 'facility', 'Mill Pond Park'),
    'Major Deegan Expy': ('nom', 'Mill Pond Park, Bronx', 'facility', 'Mill Pond Park'),
    'East Dr': ('same', '830 5th Avenue', 'facility', 'the Arsenal in Central Park, Parks Department headquarters; listed only as "East Dr"'),
    '13 Bronx Shore Rd': ('same', '14 Bronx Shore Rd', 'facility', 'Parks yard on Randalls Island, with the rest of its station group'),
    '15 Bronx Shore Rd': ('same', '14 Bronx Shore Rd', 'facility', 'Parks yard on Randalls Island, with the rest of its station group'),
    'Main Roadway/Opp Park & Recreation': ('same', '14 Bronx Shore Rd', 'facility', 'Parks yard on Randalls Island, with the rest of its station group'),
    '196-5 Grand Central Parkway N Svc Rd': ('same', '196-03 Grand Central Pkwy', 'facility', 'Cunningham Park, with the rest of its station group'),
    'Unnamed Road': ('nom', 'Freshkills Park', 'approx', 'Freshkills Park; listed only as "Unnamed Road"'),
    '638 Bayside St': ('nom', 'Fort Totten Park, Queens', 'approx', 'Fort Totten; the listed address could not be matched'),
    'Murray Ave': ('nom', 'Fort Totten Park, Queens', 'approx', 'Fort Totten; listed only as "Murray Ave"'),
    '302 Sgt. Charles M. Beer': ('nom', 'Fort Totten Park, Queens', 'approx', 'Fort Totten; the listed address could not be matched'),
    '135 Shore Road': ('nom', 'Fort Totten Park, Queens', 'approx', 'Fort Totten; the listed address could not be matched'),
    '325 Pratt Ave': ('geo', '325 Pratt Avenue, Queens', 'address', None),
    'Father Capodanno Blvd': ('same', '920 Father Capodanno Blvd', 'facility', 'Midland Beach Lot 8, with the rest of its station group'),
    '97Th St Transverse': ('same', '151 97th Street Transverse', 'facility', 'North Meadow, Central Park, with the rest of the Parks chargers there'),
    'Forest Park Dr': ('same', '1 Forest Park Dr', 'facility', 'Oak Ridge, Forest Park, with the rest of its station group'),
    '117 Roosevelt Avenue': ('same', '117-2 Roosevelt Ave', 'facility', 'Olmsted Center, Flushing Meadows Corona Park'),
    'Avenue Of The States': ('nom', 'Queens Museum, Queens', 'facility', 'Queens Museum, Flushing Meadows Corona Park'),
    'Hudson River Greenway': ('same', '223 Riverside Dr', 'approx', 'Riverside Park, with the rest of its station group'),
    'Ny-9A': ('same', '223 Riverside Dr', 'approx', 'Riverside Park, with the rest of its station group'),
    '350 80 St': ('geo', '350 Beach 80 Street, Queens', 'address', 'listed as "80 St"; in Rockaway it is Beach 80th Street'),
    '1 Flushing Bay Promenade': ('same', '1 Marina Rd', 'facility', "World's Fair Marina"),
    '109-5 Marina Rd': ('same', '1 Marina Rd', 'facility', "World's Fair Marina"),
    'Independence Ave': ('same', '330 Bay 8th St', 'facility', 'Bay 8th Street Parks yard, with the rest of its station group'),
    '437-401-437-407 W 27Th St': ('nom', 'Chelsea Park, Manhattan', 'facility', 'Chelsea Park'),
    '42-12 Queens Plaza S': ('geo', 'Queens Plaza South, Queens', 'approx', 'on Queens Plaza South; the house number could not be matched'),
    '2 Orchard Beach Road': ('geo', '2 Orchard Beach Road, 10464', 'facility', 'Orchard Beach'),
    'Park Dr': ('geo', '2 Orchard Beach Road, 10464', 'facility', 'Orchard Beach'),
    '189 Van Cortlandt Ave W': ('geo', '189 Van Cortlandt Avenue West, Bronx', 'approx', 'Van Cortlandt Park golf course; placed on Van Cortlandt Avenue West'),
    '5901 Mosholu Ave': ('geo', '5901 Mosholu Avenue, Bronx', 'approx', 'Van Cortlandt Park; placed on Mosholu Avenue, house number not matched'),
    '6477 US-9': ('geo', '6477 Broadway, Bronx', 'address', 'US 9 is Broadway'),
    'South Street Pier 36': ('nom', 'Pier 36, Manhattan', 'facility', 'Pier 36'),
    '52 58th St': ('same', '52-07 58th St', 'facility', 'Sanitation complex at 52-07 58th Street; the listed number was incomplete'),
    '52 58Th St': ('same', '52-07 58th St', 'facility', 'Sanitation complex at 52-07 58th Street; the listed number was incomplete'),
    '2720 53Rd Ave': ('same', '58-73 53rd Ave', 'approx', 'Sanitation complex on 53rd Avenue; the listed number (2720) could not be matched'),
    '2720 53rd Ave': ('same', '58-73 53rd Ave', 'approx', 'Sanitation complex on 53rd Avenue; the listed number (2720) could not be matched'),
    '2720 53rd Avenue': ('same', '58-73 53rd Ave', 'approx', 'Sanitation complex on 53rd Avenue; the listed number (2720) could not be matched'),
    '53rd Avenue': ('same', '58-73 53rd Ave', 'approx', 'Sanitation complex on 53rd Avenue; no house number listed'),
    '1964 Northern Blvd': ('geo', '45-06 215 Street, Queens', 'approx', '111th Precinct station house; the listed address could not be matched'),
    '9096 Meserole Ave': ('geo', '96 Meserole Avenue, Brooklyn', 'approx', '94th Precinct, Meserole Avenue; the listed number could not be matched'),
    'W 86 St/Traverse Rd': ('nom', 'Central Park Precinct, New York', 'facility', 'Central Park Precinct, 86th Street Transverse'),
    'Rose St': ('same', '1 Police Plaza Path', 'facility', 'Police headquarters, with the rest of its station group'),
    '970 Sanders St': ('same', '970 Richmond Ave', 'facility', '121st Precinct, with the rest of its station group'),
    '1000 Sutter Ave': ('geo', '1000 Sutter Avenue, Brooklyn', 'address', None),
    '480 Morris Park Ave': ('same', '460 Morris Park Avenue', 'facility', 'with the rest of its station group at 460 Morris Park Avenue'),
    '71-01 Parsons Boulevard': ('geo', '71-01 Parsons Boulevard, Queens', 'address', None),
    '37 49Th Ave': ('geo', '37 49Th Ave, 11101', 'approx', 'on 49th Avenue; the listed numbers (36 and 37) could not be matched'),
    '36 49Th Ave': ('geo', '37 49Th Ave, 11101', 'approx', 'on 49th Avenue; the listed numbers (36 and 37) could not be matched'),
    '58th St Brooklyn Army Terminal': ('nom', 'Brooklyn Army Terminal', 'facility', 'Brooklyn Army Terminal'),
    # upstate (Census geocoder handles the rest)
    'Co Rd 38': ('same', '669 County Road 38', 'facility', 'Environmental Protection, Arkville, with the rest of its station group'),
    '2471 B W S Rd': ('same', '2398 NY-28A', 'approx', 'Ashokan Reservoir area, Olivebridge; the listed address could not be matched'),
    '16 Samantha Lane': ('nom', '16 Samantha Lane, Carmel, NY', 'address', None),
    '1020 Croton Dam Road': ('same', '1120 Croton Dam Road', 'approx', 'Croton Dam Road; the listed number could not be matched'),
    '7892 42': ('same', '7870 Ny-42', 'approx', 'Route 42, Grahamsville; the listed number could not be matched'),
    '570 Van Aken Road': ('nom', '570 Van Aken Road, Grand Gorge, NY', 'address', None),
    '41158 New York 28': ('nom', '41158 State Highway 28, Margaretville, NY', 'address', None),
    '41158 NY-28': ('nom', '41158 State Highway 28, Margaretville, NY', 'address', None),
    '130 Allen Lane': ('nom', '130 Allen Lane, Tannersville, NY', 'address', None),
    '3525 State Highway 10': ('nom', '3525 State Highway 10, Deposit, NY', 'approx', 'on State Highway 10 in Deposit; the house number could not be matched'),
    '20 New York City Highway 30A': ('nom', 'Downsville Dam', 'approx', 'Downsville, at the Pepacton Reservoir dam; the listed address could not be matched'),
    '40 New York City Highway 30A': ('nom', 'Downsville Dam', 'approx', 'Downsville, at the Pepacton Reservoir dam; the listed address could not be matched'),
    '20 NYC Highway 30A': ('nom', 'Downsville Dam', 'approx', 'Downsville, at the Pepacton Reservoir dam; the listed address could not be matched'),
}
BY_STREET_AGENCY = {
    ('Hell Gate Cir', 'DEP'): ('same', '116 K Rd', 'facility', 'Wards Island wastewater plant, with the rest of its station group'),
    ('Hell Gate Cir', 'DPR'): ('same', '10 Central Rd', 'facility', 'Icahn Stadium on Randalls Island, with the rest of its station group'),
}
BY_STATION = {
    'DOC_HAZENLOT-S1': ('same', '15-15 Hazen St', 'facility', 'Rikers Island, with the rest of its station group'),
    'DOC_HAZENLOT-S2': ('same', '15-15 Hazen St', 'facility', 'Rikers Island, with the rest of its station group'),
    'DOC_HAZENLOT-S3': ('same', '15-15 Hazen St', 'facility', 'Rikers Island, with the rest of its station group'),
    'DOC_CHAPEL_1_L3': ('same', '16-16 Hazen St', 'facility', 'Rikers Island, with the rest of its station group'),
}
# rows whose published coordinates are wrong (checked against the address, BBL and station group)
CORRECT = {
    **{s: ('geo', '10501 Foster Avenue, Brooklyn', 'corrected',
           'the city placed this Canarsie garage at Foster Avenue in Midwood, about 4.7 km west; moved to 10501 Foster Avenue')
       for s in ('DSNY_BK18-1', 'DSNY_BK18-2', 'DSNY_BK18-DCFC1', 'DSNY_BK18-DCFC2')},
    'DSNY_HENRY-3': ('same', '80 Henry Street', 'corrected',
                     'the city placed this one charger at 80 Henry Street in Brooklyn Heights; its three siblings and the ZIP code are in Manhattan'),
}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def zip5(r):
    z = str(r.get('postcode') or '').split('.')[0]
    return z if re.fullmatch(r'\d{5}', z) else ''


def station(r):
    return (r.get('station_name') or '').replace('NYC FLEET / ', '').strip()


def hav(a, b):
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def alt_corners(boro, a, b):
    for x in a.split('|'):
        for y in b.split('|'):
            c = corners(boro, x, y)
            if c:
                return c
    return []


def block_label(s):
    m = re.match(r'(.+?):\s*(.+?),\s*(.+)', s)
    if m:
        return f'{m.group(1)} between {m.group(2)} and {m.group(3)}'
    return s


# --- pass 1: placements that do not depend on other rows ------------------------------------
recs = []
for r in rows:
    st = station(r)
    rec = {
        'station': st, 'agency': r.get('agency') or '', 'type': r.get('type_of_charger') or '',
        'ports': int(num(r.get('no_of_ports')) or 0), 'street': (r.get('street') or '').strip(),
        'city': (r.get('city') or '').strip(), 'zip': zip5(r), 'borough': r.get('borough') or '',
        'public_col': r.get('public_charger_') or '', 'fee': r.get('fee_for_city_drivers') or '',
        'nta': r.get('nta') or '', 'source': 'NYC Open Data fc53-9hrv',
    }
    lat, lon = num(r.get('latitude')), num(r.get('longitude'))
    rule = CORRECT.get(st)
    if rule is None and lat is not None:
        rec.update(lat=lat, lon=lon, how='city', note='')
    elif rule is None and rec['type'] == 'Mobile Charger':
        rec.update(lat=None, lon=None, how='none', note='mobile charger; no fixed location')
    elif rule is None and rec['street'] in CURB:
        boro, main, x1, x2 = CURB[rec['street']]
        c1, c2 = alt_corners(boro, main, x1), alt_corners(boro, main, x2)
        if not (c1 and c2):
            sys.exit(f'FAIL: block not found for {rec["street"]}')
        p1, p2 = min(((a, b) for a in c1 for b in c2), key=lambda ab: hav(*ab))
        rec.update(lat=(p1[0] + p2[0]) / 2, lon=(p1[1] + p2[1]) / 2, how='block',
                   note='mid-block, from the city street centerline')
    elif rule is None and rec['street'] in CORNER:
        boro, a, b = CORNER[rec['street']]
        c = alt_corners(boro, a, b)
        if not c:
            sys.exit(f'FAIL: corner not found for {rec["street"]}')
        rec.update(lat=sum(p[0] for p in c) / len(c), lon=sum(p[1] for p in c) / len(c), how='corner',
                   note=f'at the corner of {a.title()} and {b.title()}, from the city street centerline')
    else:
        rule = rule or BY_STATION.get(st) or BY_STREET_AGENCY.get((rec['street'], rec['agency'])) or BY_STREET.get(rec['street'])
        rec['rule'] = rule
        rec.update(lat=None, lon=None, how='pending', note='')
    recs.append(rec)

# addresses with city coordinates, for "same" placements (most common point per street)
by_addr = collections.defaultdict(collections.Counter)
for rec in recs:
    if rec['how'] == 'city':
        by_addr[rec['street']][(rec['lat'], rec['lon'])] += 1


def resolve(rec):
    rule = rec.get('rule')
    if rule is None:
        if rec['borough'] in ('Upstate', 'Westchester'):
            m = census(f"{rec['street']}, {rec['city']}, NY {rec['zip']}")
            if m:
                return m['coordinates']['y'], m['coordinates']['x'], 'address', 'geocoded by the Census Bureau'
        sys.exit(f'FAIL: no placement rule for {rec["station"]} | {rec["street"]} | {rec["zip"]}')
    kind, q, prec, note = rule
    if kind == 'same':
        if q in by_addr:
            (lat, lon), _ = by_addr[q].most_common(1)[0]
        else:
            return None  # resolved in pass 3 against another placed row
    elif kind == 'geo':
        f = geosearch(q)
        if not f:
            sys.exit(f'FAIL: GeoSearch found nothing for {q}')
        lon, lat = f['geometry']['coordinates']
        # a house-level placement must come back with the house number that was asked for
        num0 = q.split()[0]
        if prec != 'approx' and num0[0].isdigit() and not f['properties']['label'].startswith(num0 + ' '):
            sys.exit(f'FAIL: GeoSearch returned {f["properties"]["label"]} for {q}')
    elif kind == 'nom':
        f = nominatim(q)
        if not f:
            sys.exit(f'FAIL: Nominatim found nothing for {q}')
        lat, lon = float(f['lat']), float(f['lon'])
    elif kind == 'cen':
        m = census(q)
        lat, lon = m['coordinates']['y'], m['coordinates']['x']
    note = note or ''
    if kind == 'geo' and prec == 'address' and not note:
        note = 'geocoded by the city (Planning Labs GeoSearch)'
    return lat, lon, prec, note


# pass 2 and 3
for _ in range(2):
    for rec in recs:
        if rec['how'] != 'pending':
            continue
        out = resolve(rec)
        if out:
            rec['lat'], rec['lon'], rec['how'], rec['note'] = out
            by_addr[rec['street']][(rec['lat'], rec['lon'])] += 1
pend = [r for r in recs if r['how'] == 'pending']
if pend:
    sys.exit(f'FAIL: {len(pend)} rows unplaced, e.g. {pend[0]["station"]} {pend[0]["street"]}')

# --- supplement: Forest Park bandshell public fast chargers (DCAS list, 9/23/2026) -----------
fp = nominatim('Forest Park Bandshell, Queens')
for i in range(1, 11):
    recs.append({'station': f'DPR_FPBND_{i}_L3', 'agency': 'DPR', 'type': 'Level 3 Fast Charger', 'ports': 1,
                 'street': '1-01 Forest Park Dr', 'city': 'Woodhaven', 'zip': '11421', 'borough': 'Queens',
                 'public_col': '', 'fee': '', 'nta': '', 'lat': float(fp['lat']), 'lon': float(fp['lon']),
                 'how': 'facility', 'note': 'Seuffert Bandshell parking lot, Forest Park',
                 'source': 'DCAS public charger list, Sept. 23, 2026 (not yet in the open dataset)'})


def public_kind(rec):
    if rec['station'] in DCAS_PUBLIC:
        return 'dcas'
    if rec['type'] == 'L2 DOT Flo Curbside Charger':
        return 'curb'
    if rec['type'].startswith('DOT Municipal'):
        return 'lot'
    if rec['public_col'] == '*adapter required for use':
        return 'adapter'
    return ''


for rec in recs:
    rec['public'] = public_kind(rec)
    rec['kind'] = KIND.get(rec['type'], 'other')
save_cache()

# --- neighborhoods (2020 NTAs) for search ------------------------------------------------------
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
NTA_F = os.path.join(HERE, 'nta2020.geojson')
if not os.path.exists(NTA_F):
    urllib.request.urlretrieve('https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON', NTA_F)
nta = json.load(open(NTA_F))['features']
geoms = [shape(f['geometry']) for f in nta]
tree = STRtree(geoms)


def hood(lat, lon, in_city):
    p = Point(lon, lat)
    for i in tree.query(p):
        if geoms[i].contains(p):
            pr = nta[i]['properties']
            return pr.get('ntaname'), pr.get('boroname')
    if in_city:  # a point on a beach or pier can fall just outside every NTA polygon
        i = min(range(len(geoms)), key=lambda j: geoms[j].distance(p))
        if geoms[i].distance(p) < 0.01:
            pr = nta[i]['properties']
            return pr.get('ntaname'), pr.get('boroname')
    return None, None


# --- group stations into sites -----------------------------------------------------------------
PREC_RANK = {'city': 0, 'address': 1, 'block': 1, 'corner': 1, 'corrected': 1, 'facility': 2, 'approx': 3}
sites = collections.OrderedDict()
for rec in recs:
    if rec['lat'] is None:
        continue
    key = (round(rec['lat'], 5), round(rec['lon'], 5))
    sites.setdefault(key, []).append(rec)

out = []
for (lat, lon), rs in sites.items():
    # label a site by the address the city itself geocoded there, when there is one
    named = [r for r in rs if r['how'] == 'city' and r['street']] or [r for r in rs if r['street']]
    street = collections.Counter(r['street'] for r in named).most_common(1)[0][0]
    name, boro = hood(lat, lon, any(r['borough'] in ('Manhattan', 'Bronx', 'Brooklyn', 'Queens', 'Staten Island') for r in rs))
    if not boro:
        name = collections.Counter(r['city'] for r in rs if r['city']).most_common(1)[0][0].title()
        boro = 'Outside the city'
    ports = collections.Counter()
    for r in rs:
        ports[r['kind']] += r['ports']
    worst = max(rs, key=lambda r: PREC_RANK.get(r['how'], 0))
    pub = sorted({r['public'] for r in rs if r['public']})
    fees = sorted({r['fee'] for r in rs if r['fee'] and r['fee'] != 'No' and r['public']})
    out.append({
        'lat': round(lat, 6), 'lon': round(lon, 6),
        'a': block_label(street), 'z': next((r['zip'] for r in rs if r['zip']), ''),
        'h': name or '', 'b': boro,
        'ag': sorted({r['agency'] for r in rs}),
        'p': dict(ports), 'n': sum(ports.values()), 'st': len(rs),
        'pub': pub, 'pp': sum(r['ports'] for r in rs if r['public']), 'fee': fees,
        'pk': dict(collections.Counter({r['public']: 0 for r in rs if r['public']}) + collections.Counter(
            {k: sum(x['ports'] for x in rs if x['public'] == k) for k in {r['public'] for r in rs if r['public']}})),
        'how': worst['how'], 'note': worst['note'],
        'ids': sorted(r['station'] for r in rs),
        'src': sorted({r['source'] for r in rs}),
    })
out.sort(key=lambda s: (-s['n'], s['a']))
for i, s in enumerate(out):
    s['id'] = i

os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
meta = {
    'source': 'NYC Open Data, NYC EV Fleet Station Network (fc53-9hrv), DCAS',
    'source_updated': '2026-05-12',
    'public_list_updated': '2026-09-23',
    'built': __import__('datetime').date.today().isoformat(),
    'agencies': AGENCY,
}
json.dump({'meta': meta, 'sites': out}, open(os.path.join(ROOT, 'data', 'sites.json'), 'w'), separators=(',', ':'), ensure_ascii=False)

with open(os.path.join(ROOT, 'data', 'chargers.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['station', 'agency', 'agency_name', 'charger_type', 'ports', 'address', 'city', 'zip', 'borough',
                'latitude', 'longitude', 'placement', 'placement_note', 'public_access', 'listed_fee', 'source'])
    for r in recs:
        w.writerow([r['station'], r['agency'], AGENCY.get(r['agency'], r['agency']), r['type'], r['ports'], r['street'],
                    r['city'], r['zip'], r['borough'], r['lat'] if r['lat'] is None else round(r['lat'], 6),
                    r['lon'] if r['lon'] is None else round(r['lon'], 6), r['how'], r['note'], r['public'], r['fee'], r['source']])

with open(os.path.join(HERE, 'placement_log.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['station', 'listed_address', 'zip', 'placement', 'note', 'latitude', 'longitude'])
    for r in recs:
        if r['how'] != 'city':
            w.writerow([r['station'], r['street'], r['zip'], r['how'], r['note'], r['lat'], r['lon']])

# --- summary --------------------------------------------------------------------------------------
c = collections.Counter(r['how'] for r in recs)
pc = collections.Counter()
for r in recs:
    pc[r['kind']] += r['ports']
print('stations', len(recs), 'ports', sum(r['ports'] for r in recs))
print('placement', dict(c))
print('ports by kind', dict(pc))
print('sites', len(out), 'outside city', sum(1 for s in out if s['b'] == 'Outside the city'))
print('public sites', sum(1 for s in out if s['pub']), 'public ports',
      sum(r['ports'] for r in recs if r['public'] and r['lat'] is not None))
