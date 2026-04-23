#!/usr/bin/env python3
"""Merge raw NYC schools data sources into compact JSON for the frontend."""
import json, re, os
from collections import defaultdict

DATA = os.path.dirname(__file__)
OUT = os.path.join(DATA, '..', 'public', 'data')
os.makedirs(OUT, exist_ok=True)

def load(p):
    return json.load(open(os.path.join(DATA, p)))

# --- locations ---
locs = load('schools_locations.json')
# --- demo snapshots (multi-year) ---
demo = load('demo_snapshot.json')
# --- directories ---
hs = load('hs_directory.json')
ms = load('ms_directory.json')
es = load('es_directory.json')
# --- zones ---
zones_es = load('zones_elementary.geojson')
zones_ms = load('zones_middle.geojson')
# --- private ---
priv = load('private_schools_nyc.json')
# --- tracts geom ---
tracts_geo = load('tracts_2020.geojson')
# --- acs ---
acs = load('acs_children_raw.json')

# ===== build demographics lookup by dbn =====
demo_by_dbn = defaultdict(list)
for r in demo:
    demo_by_dbn[r['dbn']].append(r)
for dbn in demo_by_dbn:
    demo_by_dbn[dbn].sort(key=lambda r: r['year'])

def pct(s):
    if s is None or s == '': return None
    s = str(s).strip().rstrip('%')
    try: return float(s)
    except: return None

def latest_demo(dbn):
    rows = demo_by_dbn.get(dbn, [])
    if not rows: return None
    r = rows[-1]
    def f(k):
        v = r.get(k)
        try: return float(v) if v not in (None, '') else None
        except: return None
    return {
        'year': r['year'],
        'enrollment': f('total_enrollment'),
        'pct_asian': f('asian_1'),
        'pct_black': f('black_1'),
        'pct_hispanic': f('hispanic_1'),
        'pct_white': f('white_1'),
        'pct_multi': f('multi_racial_1'),
        'pct_native': f('native_american_1'),
        'pct_female': f('female_1'),
        'pct_male': f('male_1'),
        'pct_swd': f('students_with_disabilities_1'),
        'pct_ell': f('english_language_learners_1'),
        'poverty': pct(r.get('poverty_1')),
        'eni': pct(r.get('economic_need_index')),
    }

def enroll_trend(dbn):
    rows = demo_by_dbn.get(dbn, [])
    return [[r['year'], float(r['total_enrollment']) if r.get('total_enrollment') not in (None, '') else None] for r in rows]

# ===== build directory lookup by dbn =====
hs_by = {r.get('dbn') or r.get('schooldbn'): r for r in hs if (r.get('dbn') or r.get('schooldbn'))}
ms_by = {r.get('schooldbn') or r.get('dbn'): r for r in ms if (r.get('schooldbn') or r.get('dbn'))}
es_by = {r.get('dbn'): r for r in es if r.get('dbn')}

# ===== programs/badges extraction =====
SHSAT = {'10X445','10X696','02M475','13K430','14K449','28Q687','31R605','05M692','02M545'}  # 9 Specialized HS DBNs
# Stuy, Bronx Sci, Brooklyn Tech, HSMSE, HSAS, Lehman, Staten Island Tech, Brooklyn Latin, LaGuardia? LaGuardia is arts-audition not SHSAT
# Correct 8 SHSAT schools:
SHSAT = {
    '02M475': 'Stuyvesant HS',
    '10X445': 'Bronx HS of Science',
    '13K430': 'Brooklyn Technical HS',
    '05M692': 'HS of Math, Science & Engineering at CCNY',
    '02M545': 'HS for American Studies at Lehman',
    '10X696': 'HS of American Studies/Brooklyn Latin (check)',
    '14K449': 'Brooklyn Latin School',
    '28Q687': 'Queens HS for the Sciences at York',
    '31R605': 'Staten Island Technical HS',
}
LAGUARDIA_DBN = '03M485'

def programs_for(dbn, name):
    tags = []
    name_l = (name or '').lower()
    # HS directory
    h = hs_by.get(dbn)
    if h:
        ints = []
        for k in h:
            if k.startswith('interest'):
                v = h[k]
                if v: ints.append(str(v))
        blob = ' '.join([str(h.get(f)) for f in ('overview_paragraph','academicopportunities1','academicopportunities2','academicopportunities3','academicopportunities4','academicopportunities5','program1','addtl_info1') if h.get(f)])
        blob_l = blob.lower()
        if 'international baccalaureate' in blob_l or ' ib ' in blob_l or 'ib program' in blob_l or 'ib diploma' in blob_l:
            tags.append('International Baccalaureate')
        if 'career and technical' in blob_l or 'cte program' in blob_l or re.search(r'\bCTE\b', blob):
            tags.append('Career and Technical Education')
        if 'early college' in blob_l:
            tags.append('Early College')
        if 'dual language' in blob_l or 'dual-language' in blob_l:
            tags.append('Dual language')
        if 'asd nest' in blob_l or 'autism spectrum disorder nest' in blob_l:
            tags.append('ASD Nest')
        if 'asd horizon' in blob_l or ('horizon' in blob_l and 'autism' in blob_l):
            tags.append('ASD Horizon')
        if 'aims' in blob_l and 'academic' in blob_l:
            tags.append('AIMS')
        # language classes
        lc = h.get('language_classes')
        if lc:
            tags.append('Languages: ' + lc)
        ap = h.get('advancedplacement_courses')
        if ap:
            tags.append('AP: ' + ap)
        acc = h.get('school_accessibility_description') or h.get('school_accessibility')
        if acc:
            if 'fully accessible' in str(acc).lower(): tags.append('Fully accessible')
            elif 'partially accessible' in str(acc).lower(): tags.append('Partially accessible')
            elif 'not accessible' in str(acc).lower(): tags.append('Not accessible')
    m = ms_by.get(dbn)
    if m:
        blob = ' '.join([str(m.get(f)) for f in ('overview','electiveclasses','ellprograms') if m.get(f)])
        blob_l = blob.lower()
        if 'dual language' in blob_l or 'dual-language' in blob_l:
            if 'Dual language' not in tags: tags.append('Dual language')
        if 'asd nest' in blob_l:
            if 'ASD Nest' not in tags: tags.append('ASD Nest')
        if 'asd horizon' in blob_l or ('horizon' in blob_l and 'autism' in blob_l):
            if 'ASD Horizon' not in tags: tags.append('ASD Horizon')
        acc = m.get('accessibility_description')
        if acc:
            al = str(acc).lower()
            if 'fully accessible' in al and 'Fully accessible' not in tags: tags.append('Fully accessible')
            elif 'partially accessible' in al and 'Partially accessible' not in tags: tags.append('Partially accessible')
            elif 'not accessible' in al and 'Not accessible' not in tags: tags.append('Not accessible')
    e = es_by.get(dbn)
    if e:
        if e.get('g_t_in_kindergarten') in ('Yes','Y','YES'):
            tags.append('Gifted and Talented')
        acc = e.get('accessibility')
        if acc:
            al = str(acc).lower()
            if 'full' in al and 'Fully accessible' not in tags: tags.append('Fully accessible')
            elif 'partial' in al and 'Partially accessible' not in tags: tags.append('Partially accessible')
            elif 'not accessible' in al and 'Not accessible' not in tags: tags.append('Not accessible')
    # district 75
    if dbn and dbn[:2] == '75':
        tags.append('District 75 (special education)')
    # specialized HS
    if dbn in SHSAT:
        tags.append('Specialized High School')
    if dbn == LAGUARDIA_DBN:
        tags.append('LaGuardia (arts audition)')
    # name-based hints
    if 'gifted' in name_l or 'talented' in name_l:
        if 'Gifted and Talented' not in tags: tags.append('Gifted and Talented')
    if 'bilingual' in name_l:
        tags.append('Bilingual')
    return tags

def admissions_method(dbn):
    h = hs_by.get(dbn)
    if h and h.get('method1'):
        return h.get('method1')
    m = ms_by.get(dbn)
    if m and m.get('admissionsmethod_prog1'):
        return m['admissionsmethod_prog1']
    e = es_by.get(dbn)
    if e and e.get('school_type'):
        return e['school_type']  # 'Zoned School' or 'Non-Zoned School'
    return None

def admissions_programs(dbn):
    """Return program-level admissions details (HS and MS) as list of dicts."""
    out = []
    h = hs_by.get(dbn)
    if h:
        for i in range(1, 11):
            name = h.get(f'program{i}')
            method = h.get(f'method{i}') or h.get('method1')
            code = h.get(f'code{i}')
            if not (name or code): continue
            seats = h.get(f'seats9ge{i}') or h.get(f'seats101')
            apps = h.get(f'grade9geapplicants{i}')
            apps_per_seat = h.get(f'grade9geapplicantsperseat{i}')
            offer = h.get(f'offer_rate1_{i}') or h.get(f'offer_rate{i}_1')
            pri1 = h.get(f'admissionspriority1{i}') or h.get(f'admissionspriority11')
            pri2 = h.get(f'admissionspriority2{i}') or h.get(f'admissionspriority21')
            interest = h.get(f'interest{i}')
            out.append({
                'name': name, 'code': code, 'method': method,
                'interest': interest,
                'seats': seats, 'applicants': apps, 'apps_per_seat': apps_per_seat,
                'offer_rate': offer, 'priority1': pri1, 'priority2': pri2,
            })
    m = ms_by.get(dbn)
    if m:
        for i in range(1, 6):
            name = m.get(f'name_prog{i}')
            code = m.get(f'code_prog{i}')
            method = m.get(f'admissionsmethod_prog{i}')
            if not (name or code): continue
            out.append({
                'name': name, 'code': code, 'method': method,
                'seats': m.get(f'geseats_prog{i}'),
                'applicants': m.get(f'geapps_prog{i}'),
                'apps_per_seat': m.get(f'geappsperseat_prog{i}'),
                'eligibility': m.get(f'eligibility_prog{i}'),
                'priority1': m.get(f'priority1_prog{i}'),
                'priority2': m.get(f'priority2_prog{i}'),
            })
    return out

def grade_span(dbn):
    h = hs_by.get(dbn); m = ms_by.get(dbn); e = es_by.get(dbn)
    if h and h.get('gradespan'): return h['gradespan']
    if m and m.get('gradespan'): return m['gradespan']
    if e and e.get('grades'): return e['grades']
    return None

def website(dbn):
    h = hs_by.get(dbn); m = ms_by.get(dbn)
    if h:
        w = h.get('website') or h.get('url')
        if w: return w
    if m:
        w = m.get('independentwebsite') or m.get('url')
        if w: return w
    return None

def overview(dbn):
    h = hs_by.get(dbn); m = ms_by.get(dbn)
    if h and h.get('overview_paragraph'): return h['overview_paragraph']
    if m and m.get('overview'): return m['overview']
    return None

def neighborhood(dbn):
    h = hs_by.get(dbn); m = ms_by.get(dbn)
    if h and h.get('neighborhood'): return h['neighborhood']
    if m and m.get('neighborhood'): return m['neighborhood']
    return None

# ===== quality metrics =====
try:
    quality_rows = load('quality_2024.json')
except FileNotFoundError:
    quality_rows = []

quality_by_dbn = defaultdict(dict)
for r in quality_rows:
    try:
        v = float(r.get('metric_value'))
    except (TypeError, ValueError):
        continue
    quality_by_dbn[r['dbn']][r['metric_variable_name']] = v

def quality_for(dbn):
    q = quality_by_dbn.get(dbn)
    if not q: return None
    out = {}
    # attendance (K8 or HS)
    att = q.get('attendance_k8_all') or q.get('attendance_hs_all')
    if att is not None: out['attendance'] = att
    abs_ = q.get('chronic_absent_all') or q.get('chronic_absent_ems_all')
    if abs_ is not None: out['chronic_absent'] = abs_
    if q.get('ccr_4yr_all') is not None: out['ccr_4yr'] = q['ccr_4yr_all']
    if q.get('grad_pct_4_all') is not None: out['grad_4yr'] = q['grad_pct_4_all']
    return out or None

# ===== compile school list (public + charter) =====
BORO_NAMES = {'1':'Manhattan','2':'Bronx','3':'Brooklyn','4':'Queens','5':'Staten Island'}
MANAGED = {'1':'public','2':'charter'}  # 1=DOE, 2=Charter per DOE convention

# derive dbn from ats_code (already = dbn format: 02M475)
schools = []
for s in locs:
    if not s.get('the_geom'): continue
    coords = s['the_geom']['coordinates']
    dbn = s.get('ats_code')
    name = s.get('loc_name')
    mgd = s.get('managed_by')
    sector = 'charter' if mgd in ('2','3') else 'public'
    boro = BORO_NAMES.get(s.get('boronum'), '')
    school = {
        'dbn': dbn,
        'name': name,
        'sector': sector,
        'lat': coords[1], 'lon': coords[0],
        'address': s.get('address'),
        'zip': s.get('zip'),
        'boro': boro,
        'district': s.get('geodistric'),
        'neighborhood': neighborhood(dbn),
        'grades': grade_span(dbn),
        'website': website(dbn),
        'overview': overview(dbn),
        'admission': admissions_method(dbn),
        'demo': latest_demo(dbn),
        'trend': enroll_trend(dbn),
        'programs': programs_for(dbn, name),
        'admission_programs': admissions_programs(dbn),
        'quality': quality_for(dbn),
        'has_zone': False,  # filled below
    }
    schools.append(school)

# mark zones
zone_dbns = set()
for z in zones_es['features']:
    d = z['properties'].get('dbn')
    if d: zone_dbns.add(d)
for z in zones_ms['features']:
    d = z['properties'].get('dbn')
    if d: zone_dbns.add(d)
for s in schools:
    s['has_zone'] = s['dbn'] in zone_dbns

# ===== private schools =====
for p in priv:
    if p['LAT'] is None or p['LON'] is None: continue
    schools.append({
        'dbn': f"PRIV-{p['PPIN']}",
        'name': p['NAME'].title() if p['NAME'].isupper() else p['NAME'],
        'sector': 'private',
        'lat': p['LAT'], 'lon': p['LON'],
        'address': (p['STREET'] or '').title(),
        'zip': str(p['ZIP'])[:5] if p['ZIP'] else None,
        'boro': p['NMCNTY'].replace(' County','').replace('New York','Manhattan').replace('Kings','Brooklyn').replace('Richmond','Staten Island'),
        'district': None,
        'neighborhood': None,
        'grades': None,
        'website': None,
        'overview': None,
        'admission': None,
        'demo': None,
        'trend': [],
        'programs': [],
        'admission_programs': [],
        'quality': None,
        'has_zone': False,
    })

# ===== write schools.json =====
with open(os.path.join(OUT, 'schools.json'), 'w') as f:
    json.dump(schools, f, separators=(',', ':'))
print(f'schools.json: {len(schools)} schools')

# ===== zones.geojson (merged, indexed by dbn) =====
zones_merged = {'type': 'FeatureCollection', 'features': []}
for z in zones_es['features']:
    z['properties']['zone_type'] = 'elementary'
    zones_merged['features'].append(z)
for z in zones_ms['features']:
    z['properties']['zone_type'] = 'middle'
    zones_merged['features'].append(z)
with open(os.path.join(OUT, 'zones.geojson'), 'w') as f:
    json.dump(zones_merged, f, separators=(',', ':'))
print(f'zones.geojson: {len(zones_merged["features"])} zones')

# ===== tracts.geojson with ACS data joined =====
# parse acs
hdr = acs[0]
rows = acs[1:]
idx = {k: hdr.index(k) for k in hdr}
def safe_int(v):
    try: return int(v)
    except: return None

acs_by_geoid = {}
for r in rows:
    geoid = r[idx['state']] + r[idx['county']] + r[idx['tract']]
    total = safe_int(r[idx['B09001_001E']]) or 0
    u3 = safe_int(r[idx['B09001_003E']]) or 0
    a34 = safe_int(r[idx['B09001_004E']]) or 0
    a5 = safe_int(r[idx['B09001_005E']]) or 0
    a68 = safe_int(r[idx['B09001_006E']]) or 0
    a911 = safe_int(r[idx['B09001_007E']]) or 0
    a1213 = safe_int(r[idx['B09001_008E']]) or 0
    a14 = safe_int(r[idx['B09001_009E']]) or 0
    a1517 = safe_int(r[idx['B09001_010E']]) or 0
    acs_by_geoid[geoid] = {
        'total': total,
        'age_0_4': u3 + a34,
        'age_5_11': a5 + a68 + a911,
        'age_12_17': a1213 + a14 + a1517,
    }

missing = 0
for f in tracts_geo['features']:
    g = f['properties'].get('geoid')
    a = acs_by_geoid.get(g)
    if a:
        f['properties']['children'] = a
    else:
        missing += 1
        f['properties']['children'] = {'total': 0, 'age_0_4': 0, 'age_5_11': 0, 'age_12_17': 0}
# strip unused props to shrink
for f in tracts_geo['features']:
    p = f['properties']
    new_p = {
        'geoid': p.get('geoid'),
        'nta': p.get('ntaname'),
        'boro': p.get('boroname'),
        'children': p.get('children'),
    }
    f['properties'] = new_p

with open(os.path.join(OUT, 'tracts.geojson'), 'w') as f:
    json.dump(tracts_geo, f, separators=(',', ':'))
print(f'tracts.geojson: {len(tracts_geo["features"])} tracts; {missing} missing ACS join')

# ===== summary =====
sectors = defaultdict(int)
for s in schools: sectors[s['sector']] += 1
print('Sectors:', dict(sectors))
tagged = sum(1 for s in schools if s['programs'])
print(f'Schools with >=1 program tag: {tagged}')
