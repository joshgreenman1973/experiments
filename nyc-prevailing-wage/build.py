#!/usr/bin/env python3
"""Build the site data.

Inputs (all in data/source/):
  certified-payroll-nyc-area.csv          from fetch.py (data.ny.gov w2zp-sf2x)
  comptroller-construction-schedule-2025-2026.pdf
  comptroller-construction-schedule-2026-2027.pdf

Outputs (data/):
  meta.json        counts, date range, filter notes
  schedule.json    every classification in both comptroller schedules
  trades.json      one record per state payroll category found in the city
  projects.json    one record per project (PRC number + name)
  contractors.json one record per contractor
  crosswalk.json   the state-category to comptroller-classification map used

Everything the site shows is derived here. See methodology.html.
"""
import csv, json, re, collections, datetime, pathlib, statistics, gzip, io
import fitz  # pymupdf

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / 'data' / 'source'
OUT = ROOT / 'data'

# ---------------------------------------------------------------- schedules
def parse_schedule(pdf, label):
    """Return a list of {section, sub, start, end, wage, supp} from a
    comptroller construction schedule PDF. Section is the all-caps trade
    heading; sub is the classification line above each effective period."""
    doc = fitz.open(pdf)
    lines = []
    for p in doc:
        for l in p.get_text().split('\n'):
            s = l.strip()
            if not s or s.startswith(('OFFICE OF THE COMPTROLLER', 'CONSTRUCTION WORKER PREVAILING', 'PUBLISH DATE')):
                continue
            lines.append(s)
    toc = [i for i, l in enumerate(lines) if re.search(r'\.{5,}\s*\d+\s*$', l)]
    lines = lines[toc[-1] + 1:]
    BOILER = ('Wage Rate', 'Supplemental', '* Supplemental', 'Overtime', 'Time and', 'Double time', 'Triple time',
              'Paid Holiday', 'Shift Rate', 'None', 'New Year', 'President', 'Memorial', 'Independence', 'Labor Day',
              'Thanksgiving', 'Christmas', 'Columbus', 'Martin Luther', 'Veteran', 'Election', 'Day after', 'Day before',
              'Good Friday', 'Juneteenth', 'Lincoln', 'Washington', 'Effective Period', 'Saturday', 'Sunday', 'Monday',
              'When ', 'The ', 'All ', 'If ', 'Where ', 'For ', 'In ', 'A ', 'An ', 'On ', 'Any ', 'Each ', 'Employees',
              'Workers', 'Note', 'In accordance')
    def is_section(l):
        return (re.match(r'^[A-Z][A-Z0-9 ,&/\-–:()\'".]+$', l) and re.search('[A-Z]{3}', l) and l.upper() == l
                and not l.startswith('SEE ') and len(l) < 90)
    recs = []; section = None; sub = None; pending_section = None
    for i, l in enumerate(lines):
        if is_section(l):
            # headings that wrap onto a second all-caps line get joined
            if pending_section is not None and i > 0 and is_section(lines[i - 1]) and not l.endswith(')') is False and section == pending_section:
                section = (section + ' ' + l).replace('–', '-').strip(); pending_section = section; continue
            if i > 0 and is_section(lines[i - 1]) and section == lines[i - 1].replace('–', '-').strip():
                section = (section + ' ' + l).replace('–', '-').strip(); continue
            section = l.replace('–', '-').strip(); pending_section = section; sub = None; continue
        if l.startswith('Effective Period:'):
            m = re.match(r'Effective Period:\s*([\d/]+)\s*-\s*([\d/]+)', l)
            if not m:
                continue
            wage = supp = None
            for j in range(i + 1, min(i + 5, len(lines))):
                mw = re.match(r'Wage Rate per Hour:\s*\$?([\d,]+\.\d+)', lines[j])
                ms = re.match(r'Supplemental Benefit Rate per Hour:\s*\$?([\d,]+\.\d+)', lines[j])
                if mw: wage = float(mw.group(1).replace(',', ''))
                if ms: supp = float(ms.group(1).replace(',', ''))
                if lines[j].startswith('Effective Period'): break
            k = i - 1; cand = None
            while k >= 0 and k > i - 8:
                c = lines[k]
                if c.startswith(('Wage Rate', 'Supplemental', '*')):
                    k -= 1; continue
                if c.startswith('Effective Period') or is_section(c) or re.match(r'^\(.*\)$', c):
                    break
                if len(c) < 120 and not c.endswith('.') and not c.startswith(BOILER):
                    cand = c
                break
            if cand: sub = cand
            recs.append(dict(schedule=label, section=section, sub=sub or section,
                             start=m.group(1), end=m.group(2), wage=wage, supp=supp))
    return recs

def mdy(s):
    m, d, y = s.split('/'); return datetime.date(int(y), int(m), int(d))

SCHED = (parse_schedule(SRC / 'comptroller-construction-schedule-2025-2026.pdf', '2025-26') +
         parse_schedule(SRC / 'comptroller-construction-schedule-2026-2027.pdf', '2026-27'))

# Headings the parser cannot read because they wrap across two lines in the
# PDF. Values transcribed by hand from the PDFs; page cited in methodology.
MANUAL = [
    dict(schedule='2025-26', section='STEAMFITTER - REFRIGERATION AND AIR CONDITIONER', sub='Refrigeration and Air Conditioner Mechanic', start='7/1/2025', end='6/30/2026', wage=46.10, supp=21.96),
    dict(schedule='2025-26', section='LABORER - PAVER & ROADBUILDER LINE STRIPING (ROADWAY)', sub='Striping - Machine Operator (Thermoplastic & Epoxy)', start='7/1/2025', end='6/30/2026', wage=42.00, supp=21.17),
    dict(schedule='2025-26', section='LABORER - PAVER & ROADBUILDER LINE STRIPING (ROADWAY)', sub='Lineperson - Crew Chief', start='7/1/2025', end='6/30/2026', wage=46.00, supp=21.17),
    dict(schedule='2025-26', section='LABORER - PAVER & ROADBUILDER LINE STRIPING (ROADWAY)', sub='Laborer: Striping Assistant - Green Infrastructure - Traffic Control', start='7/1/2025', end='6/30/2026', wage=40.00, supp=21.17),
    dict(schedule='2025-26', section='POINTER, WATERPROOFER, CAULKER, SANDBLASTER, STEAMBLASTER', sub='Journeyperson', start='7/1/2025', end='6/30/2026', wage=65.33, supp=32.35),
    dict(schedule='2026-27', section='POINTER, WATERPROOFER, CAULKER, SANDBLASTER, STEAMBLASTER', sub='Journeyperson', start='7/1/2026', end='6/30/2027', wage=66.58, supp=33.85),
]
# drop parser records for those wrapped headings, then add the manual ones
BAD_SECTIONS = {'STEAMBLASTER', 'CONDITIONER', 'CONSTRUCTION)', 'AIR CONDITIONER'}
SCHED = [r for r in SCHED if r['section'] not in BAD_SECTIONS and not (r['section'] and r['section'].endswith('(ROADWAY)') and r['schedule'] == '2025-26' and r['wage'] is None)]
have = {(r['schedule'], r['section']) for r in SCHED}
for m in MANUAL:
    if (m['schedule'], m['section']) not in have or m['section'].startswith('LABORER - PAVER & ROADBUILDER LINE'):
        SCHED.append(m)
# de-duplicate
seen = set(); dedup = []
for r in SCHED:
    key = (r['schedule'], r['section'], r['sub'], r['start'], r['end'], r['wage'], r['supp'])
    if key in seen or r['wage'] is None: continue
    seen.add(key); dedup.append(r)
SCHED = dedup

BY_SECTION = collections.defaultdict(list)
for r in SCHED:
    BY_SECTION[(r['schedule'], r['section'])].append(r)

# ---------------------------------------------------------------- crosswalk
# State payroll category (as filed with the state Department of Labor) ->
# comptroller schedule section. 'subs' restricts which classifications in
# that section count; None means all of them. 'note' is shown on the site.
CROSSWALK = {
    'Laborer - Heavy & Highway': dict(section='LABORER - HEAVY & HIGHWAY'),
    'Laborer - Excavating': dict(section='LABORER - HEAVY & HIGHWAY', note='The comptroller folds excavation into Laborer - Heavy & Highway.'),
    'Laborer - Micro Paver': dict(section='LABORER - PAVER & ROADBUILDER'),
    'Laborer - Line Striping': dict(section='LABORER - PAVER & ROADBUILDER LINE STRIPING (ROADWAY)'),
    'Electrician': dict(section='ELECTRICIAN', subs=['Electrician "A" (Regular Day / Day Shift)']),
    'Electrician - Building/Wireman': dict(section='ELECTRICIAN', subs=['Electrician "A" (Regular Day / Day Shift)']),
    'Electrician - Heavy & Highway': dict(section='ELECTRICIAN', subs=['Electrician "A" (Regular Day / Day Shift)'], note='The comptroller has no separate heavy-and-highway electrician; the day-shift Electrician "A" rate is used.'),
    'Electrician - Teledata': dict(section='TELECOMMUNICATION WORKER'),
    'Electrician - Fire Alarm': dict(section='ELECTRICIAN - ALARM TECHNICIAN'),
    'Ironworker - Heavy & Highway': dict(section='IRON WORKER - STRUCTURAL'),
    'Ironworker - Structural': dict(section='IRON WORKER - STRUCTURAL'),
    'Ironworker - Ornamental': dict(section='IRON WORKER - ORNAMENTAL'),
    'Teamster - Heavy & Highway': dict(section='DRIVER: TRUCK (TEAMSTER)', subs=['Driver - Dump Truck', 'Driver - Tractor Trailer', 'Driver - Euclid & Turnapull Operator', 'Driver – Boom Truck', 'Driver – Goldhofer & Self Propelled Modular Trailer (SPMT)'], principal='Driver - Dump Truck'),
    'Teamster - All Dump Trucks': dict(section='DRIVER: TRUCK (TEAMSTER)', subs=['Driver - Dump Truck'], principal='Driver - Dump Truck'),
    'Carpenter - Building': dict(section='CARPENTER - BUILDING COMMERCIAL'),
    'Carpenter - Heavy & Highway': dict(section='CARPENTER - HEAVY CONSTRUCTION WORK'),
    'Carpenter - Dock Builder': dict(section='DOCKBUILDER - PILE DRIVER'),
    'Carpenter - Timberman': dict(section='TIMBERPERSON'),
    'Painter - Bridge/Structural Steel': dict(section='PAINTER - BRIDGE & STRUCTURAL STEEL', subs=['Painters on Structural Steel'], principal='Painters on Structural Steel'),
    'Painter - Brush/Roller/Spray': dict(section='PAINTER', principal='Painter - Brush & Roller'),
    'Plumber': dict(section='PLUMBER', principal='Plumber'),
    'Plumber - Pump and Tank': dict(section='PLUMBER: PUMP & TANK'),
    'Sheetmetal - Building': dict(section='SHEET METAL WORKER', subs=['Sheet Metal Worker'], principal='Sheet Metal Worker'),
    'Steamfitter - HVAC Mechanic': dict(section='STEAMFITTER - REFRIGERATION AND AIR CONDITIONER'),
    'Steamfitter - HVAC Piping': dict(section='STEAMFITTER', subs=['Steamfitter'], principal='Steamfitter'),
    'Elevator Constructor - Maintenance': dict(section='ELEVATOR REPAIR & MAINTENANCE'),
    'Elevator Constructor': dict(section='ELEVATOR CONSTRUCTOR'),
    'Roofer - Building': dict(section='ROOFER'),
    'Asbestos Worker': dict(section='HAZARDOUS MATERIAL HANDLER'),
    'Asbestos Worker - Hazardous': dict(section='HAZARDOUS MATERIAL HANDLER'),
    'Laborer - Asbestos/Hazardous Waste Removal': dict(section='HAZARDOUS MATERIAL HANDLER'),
    'Mason - Pointer/Caulker/Cleaner': dict(section='POINTER, WATERPROOFER, CAULKER, SANDBLASTER, STEAMBLASTER'),
    'Laborer - Mason Tender': dict(section='MASON TENDER'),
    'Laborer - Building': dict(section='MASON TENDER', note='The state\'s building laborer and the comptroller\'s mason tender are both set from the Mason Tenders District Council agreement.'),
    'Laborer - Concrete': dict(section='CEMENT & CONCRETE WORKER', subs=['Cement & Concrete Worker'], principal='Cement & Concrete Worker'),
    'Laborer - Demolition': dict(section='HOUSE WRECKER', principal='HOUSE WRECKER', note='The floor includes the comptroller\'s lower Tier B house wrecker rate.'),
    'Glazier - Building': dict(section='GLAZIER'),
    'Mason - Building': dict(section='BRICKLAYER'),
    'Mason - Cement Finisher': dict(section='CEMENT MASON'),
    'Mason - Stone Setter': dict(section='STONE MASON - SETTER'),
    'Insulator - Heat & Frost': dict(section='HEAT AND FROST INSULATOR'),
    'Millwright': dict(section='MILLWRIGHT'),
    'Boilermaker': dict(section='BOILERMAKER'),
    'Lather': dict(section='METALLIC LATHER'),
    'Tile Setter': dict(section='TILE LAYER - SETTER'),
    'Laborer - Tunnel': dict(section='TUNNEL WORKER'),
    'Operating Engineer - Heavy & Highway': dict(section='ENGINEER - OPERATING', range_only=True, note='Operating engineer rates depend on the machine; the schedule lists dozens. Shown as a range, no floor test.'),
    'Operating Engineer - Backhoes/All Types': dict(section='ENGINEER - OPERATING', range_only=True),
    'Operating Engineer - Excavation': dict(section='ENGINEER - OPERATING', range_only=True),
    'Operating Engineer - Maintenance': dict(section='ENGINEER - OPERATING', range_only=True),
    'Operating Engineer - Boom/All Types': dict(section='ENGINEER - OPERATING', range_only=True),
    'Operating Engineer - Building': dict(section='ENGINEER', range_only=True),
    'Survey Crew - Construction': dict(section='ENGINEER - FIELD (HEAVY CONSTRUCTION)', range_only=True, note='Party chief, instrument person and rodperson are paid differently; shown as a range.'),
    'Survey Crew - Consulting': dict(section='ENGINEER - CITY SURVEYOR AND CONSULTANT', range_only=True),
    'Mason - Brick/Block layer': dict(section='BRICKLAYER'),
    'Painter - Drywall Taper': dict(section='TAPER'),
    'Plumber - Steam/Sprinkler fitter': dict(section='STEAMFITTER', subs=['Steamfitter'], principal='Steamfitter', note='The comptroller has no sprinkler fitter classification; the steamfitter rate is used.'),
    'Steamfitter - Refrigeration Mechanic': dict(section='STEAMFITTER - REFRIGERATION AND AIR CONDITIONER'),
    'Carpenter - Floor Coverer': dict(section='FLOOR COVERER'),
    'Carpenter - Acoustic/Drywall': dict(section='CARPENTER - BUILDING COMMERCIAL'),
    'Carpenter - Piledriver': dict(section='DOCKBUILDER - PILE DRIVER'),
    'Plasterer - Building': dict(section='PLASTERER', subs=['Plasterer'], principal='Plasterer'),
    'Mason - Terrazzo Setter': dict(section='MOSAIC MECHANIC'),
    'Mason - Marble/Slate': dict(section='MARBLE MECHANIC', subs=['Marble Setter'], principal='Marble Setter'),
    'Mason - Stone': dict(section='STONE MASON - SETTER'),
    'Mason - Tile Setter': dict(section='TILE LAYER - SETTER'),
    'Laborer - Formsetter': dict(section='LABORER - PAVER & ROADBUILDER', subs=['Paver & Roadbuilder - Formsetter'], principal='Paver & Roadbuilder - Formsetter'),
    'Laborer - Asphalt': dict(section='LABORER - PAVER & ROADBUILDER'),
    'Laborer - Flagman': dict(section='LABORER - HEAVY & HIGHWAY', note='The comptroller pays a flagger at the rate of the trade doing the underlying work, or as a heavy-and-highway laborer where that trade has no flagger.'),
    'Painter - Power Tool': dict(section='PAINTER - BRIDGE & STRUCTURAL STEEL', subs=['Painter - Power Tool'], principal='Painter - Power Tool'),
    'Painter - Linerman Thermoplastic': dict(section='LABORER - PAVER & ROADBUILDER LINE STRIPING (ROADWAY)'),
    'Ironworker - Derrick/Rigger': dict(section='DERRICKPERSON AND RIGGER'),
    'Ironworker - Lather/Reinforcing': dict(section='METALLIC LATHER'),
    'Insulator - Heat & Frost - Insulator': dict(section='HEAT AND FROST INSULATOR'),
}
UNMAPPED_NOTES = {
    'Laborer - Residential': 'A state residential rate. The comptroller\'s construction schedule has no residential laborer classification.',
    'Sprinkler Fitter': 'The comptroller\'s construction schedule has no separate sprinkler fitter classification.',
    'Ironworker - Curtin Wall Installer': 'No matching comptroller classification.',
}

def rates_for(section, subs, label, when):
    """Journey-level (wage, supp, sub) tuples in force on date `when`."""
    out = []
    for r in BY_SECTION.get((label, section), []):
        if subs and not any(r['sub'].startswith(s) for s in subs):
            continue
        if mdy(r['start']) <= when <= mdy(r['end']):
            out.append((r['wage'], r['supp'], r['sub']))
    return out

def schedule_label(d):
    return '2025-26' if d < datetime.date(2026, 7, 1) else '2026-27'

# ---------------------------------------------------------------- payroll rows
NYC_CITIES = {'NEW YORK', 'BROOKLYN', 'BRONX', 'QUEENS', 'STATEN ISLAND', 'MANHATTAN', 'NYC', 'NEW YORK CITY'}
def nyc_zip(z):
    if not (z.isdigit() and len(z) == 5): return False
    n = int(z)
    return (10000 <= n <= 10499) or n in (11004, 11005) or (11100 <= n <= 11499) or (11690 <= n <= 11699)
def borough(z, city):
    if z.isdigit() and len(z) == 5:
        n = int(z)
        if 10000 <= n <= 10299: return 'Manhattan'
        if 10300 <= n <= 10399: return 'Staten Island'
        if 10400 <= n <= 10499: return 'Bronx'
        if 11200 <= n <= 11256: return 'Brooklyn'
        if n in (11004, 11005) or 11100 <= n <= 11199 or 11350 <= n <= 11499 or 11690 <= n <= 11699: return 'Queens'
    c = (city or '').upper().strip()
    return {'NEW YORK': 'Manhattan', 'MANHATTAN': 'Manhattan', 'BROOKLYN': 'Brooklyn', 'BRONX': 'Bronx',
            'QUEENS': 'Queens', 'STATEN ISLAND': 'Staten Island'}.get(c, 'Unknown')

AGENCY_RULES = [
    (r'\bMTA\b|METROPOLITAN TRANS|NYCT\b|NYC TRANSIT|TRANSIT AUTHORITY|LIRR|LONG ISLAND RAIL|METRO.?NORTH|MTA C&D|BRIDGES AND TUNNELS|B&T', 'Metropolitan Transportation Authority'),
    (r'PORT AUTHORITY|PANYNJ|PA ?NY ?NJ', 'Port Authority of New York and New Jersey'),
    (r'DASNY|DORMITORY AUTH', 'Dormitory Authority of the State of New York'),
    (r'NYSDOT|NYS ?DOT|DEPARTMENT OF TRANSPORTATION|DEPT\.? OF TRANSPORTATION|STATE DOT|NEW YORK DOT|^DOT$', 'New York State Department of Transportation'),
    (r'DEPARTMENT OF LABOR|DEPT\.? OF LABOR|NYS ?DOL|^DOL$|NYSDOL', 'New York State Department of Labor'),
    (r'OGS|OFFICE OF GENERAL SERVICES', 'New York State Office of General Services'),
    (r'POWER AUTHORITY|NYPA', 'New York Power Authority'),
    (r'\bSUNY\b|STATE UNIVERSITY|SUCF|MARITIME COLLEGE|DOWNSTATE|STONY BROOK', 'State University of New York'),
    (r'\bCUNY\b|CITY UNIVERSITY|CITY COLLEGE|HUNTER COLLEGE|BROOKLYN COLLEGE|QUEENS COLLEGE|LEHMAN|BARUCH|JOHN JAY|LAGUARDIA|KINGSBOROUGH|MEDGAR|YORK COLLEGE', 'City University of New York'),
    (r'SCA\b|SCHOOL CONSTRUCTION', 'New York City School Construction Authority'),
    (r'NYCHA|HOUSING AUTHORITY', 'New York City Housing Authority'),
    (r'\bDEP\b|ENVIRONMENTAL PROTECTION', 'New York City Department of Environmental Protection'),
    (r'PARKS', 'Parks (city or state)'),
    (r'SANITATION|DSNY', 'New York City Department of Sanitation'),
    (r'\bDDC\b|DESIGN AND CONSTRUCTION|DESIGN & CONSTRUCTION', 'New York City Department of Design and Construction'),
    (r'THRUWAY', 'New York State Thruway Authority'),
    (r'ESD\b|EMPIRE STATE DEV', 'Empire State Development'),
    (r'ENVIRONMENTAL CONSERVATION|\bDEC\b', 'New York State Department of Environmental Conservation'),
    (r'HEALTH \+|H\+H|HHC|HEALTH AND HOSPITALS', 'New York City Health and Hospitals'),
    (r'BATTERY PARK', 'Battery Park City Authority'),
    (r'ROOSEVELT ISLAND', 'Roosevelt Island Operating Corporation'),
    (r'OMH|MENTAL HEALTH|PSYCHIATRIC', 'New York State Office of Mental Health'),
    (r'HOMELESS|DHS\b', 'New York City Department of Homeless Services'),
    (r'CORRECTION', 'Corrections (city or state)'),
    (r'HUDSON RIVER PARK', 'Hudson River Park Trust'),
    (r'NYS\b|NEW YORK STATE|STATE OF NEW YORK', 'New York State (agency not stated)'),
    (r'NYC\b|CITY OF NEW YORK|NEW YORK CITY', 'New York City (agency not stated)'),
]
def agency(s):
    u = (s or '').upper().strip()
    if not u or u in ('UNKNOWN', 'N/A', 'NA', 'NONE'): return 'Not stated'
    for pat, name in AGENCY_RULES:
        if re.search(pat, u): return name
    return s.strip()

def num(x):
    try: return float(x)
    except: return None

rows = []
with gzip.open(SRC / 'certified-payroll-nyc-area.csv.gz', 'rt', newline='') as f:
    for r in csv.DictReader(f):
        z = (r['project_zipcode'] or '').strip()[:5]
        city = (r['project_city'] or '').strip()
        if not (nyc_zip(z) or city.upper() in NYC_CITIES):
            continue
        r['zip5'] = z; r['borough'] = borough(z, city); r['agency'] = agency(r['department_of_jurisdiction'])
        for c in ('st_total_hours', 'ot_total_hours', 'st_hourly_rate', 'ot_hourly_rate', 'wages'):
            r[c] = num(r[c])
        r['week'] = datetime.date.fromisoformat(r['week_ending_date'][:10]) if r['week_ending_date'] else None
        rows.append(r)

all_rows = len(rows)
weeks = [r['week'] for r in rows if r['week']]
work = [r for r in rows if r['work_category']]           # rows describing a worker-week
noneg = [r for r in rows if not r['work_category']]       # statement rows with no work detail

# ---------------------------------------------------------------- classify each worker-week
TOL = 0.01  # 1 percent
def classify(r):
    cat = r['work_category']; rate = r['st_hourly_rate']; d = r['week']
    if not rate or rate <= 0 or not d: return 'norate', None
    if r['job_title'] == 'Apprentice': return 'apprentice', None
    m = CROSSWALK.get(cat)
    if not m: return 'unmapped', None
    label = schedule_label(d)
    rs = rates_for(m['section'], m.get('subs'), label, d)
    if not rs: return 'noschedule', None
    floor = min(w for w, s, n in rs)
    ctx = dict(floor=floor, rates=rs, label=label)
    if m.get('range_only'): return 'range', ctx
    for w, s, n in rs:
        if s is not None and abs(rate - (w + s)) <= max(0.5, TOL * (w + s)): return 'package', ctx
    for w, s, n in rs:
        if abs(rate - w) <= TOL * w: return 'at', ctx
    if rate < floor * (1 - TOL): return 'below', ctx
    return 'above', ctx

for r in work:
    r['cls'], r['ctx'] = classify(r)

# ---------------------------------------------------------------- aggregate: trades
def pct(a, b): return round(100 * a / b, 1) if b else None
def median(xs): return round(statistics.median(xs), 2) if xs else None

trades = []
by_cat = collections.defaultdict(list)
for r in work: by_cat[r['work_category']].append(r)
for cat, rs in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
    m = CROSSWALK.get(cat)
    journey = [r for r in rs if r['cls'] in ('below', 'at', 'above', 'package', 'range')]
    counts = collections.Counter(r['cls'] for r in rs)
    rates = sorted(r['st_hourly_rate'] for r in journey)
    rec = dict(
        category=cat, rows=len(rs), hours=round(sum((r['st_total_hours'] or 0) for r in rs)),
        apprentice_rows=counts['apprentice'], norate_rows=counts['norate'],
        journey_rows=len(journey), median_rate=median(rates),
        p10=round(rates[int(len(rates) * .1)], 2) if rates else None,
        p90=round(rates[int(len(rates) * .9) - 1], 2) if rates else None,
        below=counts['below'], at=counts['at'], above=counts['above'], package=counts['package'],
        pct_below=pct(counts['below'], len(journey)), pct_at=pct(counts['at'], len(journey)),
        pct_above=pct(counts['above'], len(journey)), pct_package=pct(counts['package'], len(journey)),
        contractors=len({r['account'] for r in rs}), projects=len({r['prc_number'] for r in rs}),
        boroughs=dict(collections.Counter(r['borough'] for r in rs).most_common()),
        mapped=bool(m), range_only=bool(m and m.get('range_only')),
        note=(m or {}).get('note') or UNMAPPED_NOTES.get(cat),
    )
    if m:
        rec['section'] = m['section']
        sch = {}
        for label, when in (('2025-26', datetime.date(2026, 3, 1)), ('2026-27', datetime.date(2026, 8, 1))):
            rl = rates_for(m['section'], m.get('subs'), label, when)
            principal = m.get('principal')
            pr = next((x for x in rl if principal and x[2].startswith(principal)), rl[0] if rl else None)
            sch[label] = dict(
                wage=pr[0] if pr else None, supp=pr[1] if pr else None, sub=pr[2] if pr else None,
                floor=min(x[0] for x in rl) if rl else None, ceiling=max(x[0] for x in rl) if rl else None,
                n_subs=len(rl))
        rec['schedule'] = sch
    # rate histogram for the strip: bucket by dollar
    if rates:
        # window the strip to the 2nd to 98th percentile so a few typed-in
        # outliers do not flatten it; rates outside are counted separately
        lo = int(rates[int(len(rates) * .02)]); hi = int(rates[max(0, int(len(rates) * .98) - 1)]) + 1
        lo = max(0, lo - 2); hi = hi + 2
        buckets = collections.Counter(int(x) for x in rates if lo <= x < hi + 1)
        rec['hist'] = dict(lo=lo, hi=hi, counts=[buckets.get(v, 0) for v in range(lo, hi + 1)],
                           outside=sum(1 for x in rates if x < lo or x >= hi + 1))
        rec['modes'] = [dict(rate=v, n=n) for v, n in collections.Counter(round(x, 2) for x in rates).most_common(4)]
    # top contractors and projects in this trade
    rec['top_contractors'] = [dict(name=k, rows=n, below=sum(1 for r in rs if r['account'] == k and r['cls'] == 'below'))
                              for k, n in collections.Counter(r['account'] for r in rs).most_common(6)]
    trades.append(rec)

# ---------------------------------------------------------------- aggregate: projects
def proj_key(r): return (r['prc_number'] or '', (r['project_name'] or '').strip().upper())
projects = []
by_proj = collections.defaultdict(list)
for r in rows: by_proj[proj_key(r)].append(r)
for k, rs in by_proj.items():
    w = [r for r in rs if r['work_category']]
    j = [r for r in w if r['cls'] in ('below', 'at', 'above', 'package', 'range')]
    first = rs[0]
    addr = ', '.join(x for x in [first['project_street_1'], first['project_street_2']] if x)
    projects.append(dict(
        prc=k[0], name=(first['project_name'] or '').strip(), address=addr, city=first['project_city'],
        zip=first['zip5'], borough=collections.Counter(r['borough'] for r in rs).most_common(1)[0][0],
        agency=collections.Counter(r['agency'] for r in rs).most_common(1)[0][0],
        agency_raw=first['department_of_jurisdiction'], status=first['project_status'],
        start=(first['project_start_date'] or '')[:10], end=(first['project_end_date'] or '')[:10],
        rows=len(rs), worker_weeks=len(w), hours=round(sum((r['st_total_hours'] or 0) for r in w)),
        ot_hours=round(sum((r['ot_total_hours'] or 0) for r in w)),
        contractors=sorted({r['account'] for r in rs}),
        weeks=len({r['week'] for r in rs if r['week']}),
        first_week=min((r['week'] for r in rs if r['week']), default=None).isoformat() if any(r['week'] for r in rs) else None,
        last_week=max((r['week'] for r in rs if r['week']), default=None).isoformat() if any(r['week'] for r in rs) else None,
        trades=[dict(category=c, n=n) for c, n in collections.Counter(r['work_category'] for r in w).most_common()],
        journey=len(j), below=sum(1 for r in j if r['cls'] == 'below'), package=sum(1 for r in j if r['cls'] == 'package'),
        apprentice=sum(1 for r in w if r['cls'] == 'apprentice'),
    ))
projects.sort(key=lambda p: -p['worker_weeks'])

# ---------------------------------------------------------------- registry and non-responsible list
SUFFIX = re.compile(r'\b(INC|INCORPORATED|LLC|L\.L\.C|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|LP|L\.P|JV|JOINT VENTURE|THE|OF|AND|&)\b')
def norm(name):
    u = (name or '').upper().replace('&', ' AND ')
    u = re.sub(r'[^A-Z0-9 ]', ' ', u)
    u = SUFFIX.sub(' ', u)
    return re.sub(r'\s+', ' ', u).strip()

registry = {}
with open(SRC / 'contractor-registry.csv', newline='') as f:
    for r in csv.DictReader(f):
        for nm in (r['business_name'], r['dba_name']):
            k = norm(nm)
            if k and k not in registry:
                registry[k] = dict(
                    certificate=r['certificate_number'], name=r['business_name'], status=r['status'],
                    issued=(r['issued_date'] or '')[:10], expires=(r['expiration_date'] or '')[:10],
                    city=r['city'], state=r['state'], mwbe=r['business_is_mwbe_owned'],
                    debarred=r['business_has_been_debarred'], debar_start=(r['debarment_start_date'] or '')[:10],
                    debar_end=(r['debarment_end_date'] or '')[:10],
                    wage_assessments=r['business_has_outstanding_wage_assessments'],
                    labor_or_tax_violation=r['business_has_final_determination_for_violation_of_labor_or_tax_law'],
                    safety_violation=r['business_has_final_determination_safety_standard_violations'],
                    apprenticeship=r['business_is_associated_with_an_apprenticeship_program'])
nonresp = []
with open(SRC / 'non-responsible-entities.csv', newline='') as f:
    for r in csv.DictReader(f):
        raw = r['nonresponsiblecontractor'] or ''
        nonresp.append(dict(norm=norm(raw.split(',')[0]), raw=raw, agency=r['agencyauthorityname'],
                            date=(r['datenonresponsibilitydetermination'] or '')[:10]))

# ---------------------------------------------------------------- aggregate: contractors
contractors = []
by_con = collections.defaultdict(list)
for r in rows: by_con[r['account']].append(r)
for k, rs in by_con.items():
    w = [r for r in rs if r['work_category']]
    j = [r for r in w if r['cls'] in ('below', 'at', 'above', 'package', 'range')]
    contractors.append(dict(
        name=k, rows=len(rs), worker_weeks=len(w), hours=round(sum((r['st_total_hours'] or 0) for r in w)),
        projects=len({proj_key(r) for r in rs}),
        agencies=[a for a, n in collections.Counter(r['agency'] for r in rs).most_common(3)],
        trades=[dict(category=c, n=n) for c, n in collections.Counter(r['work_category'] for r in w).most_common(5)],
        journey=len(j), below=sum(1 for r in j if r['cls'] == 'below'), at=sum(1 for r in j if r['cls'] == 'at'),
        above=sum(1 for r in j if r['cls'] == 'above'), package=sum(1 for r in j if r['cls'] == 'package'),
        apprentice=sum(1 for r in w if r['cls'] == 'apprentice'),
        below_trades=[dict(category=c, n=n) for c, n in collections.Counter(r['work_category'] for r in j if r['cls'] == 'below').most_common(4)],
        registry=registry.get(norm(k)),
        nonresponsible=[dict(agency=x['agency'], date=x['date'], raw=x['raw']) for x in nonresp if x['norm'] and x['norm'] == norm(k)],
    ))
contractors.sort(key=lambda c: -c['worker_weeks'])
reg_matched = [c for c in contractors if c['registry']]
meta_registry = dict(
    registry_rows=len(registry), contractors_matched=len(reg_matched),
    worker_weeks_matched=sum(c['worker_weeks'] for c in reg_matched),
    debarred=[c['name'] for c in reg_matched if (c['registry']['debarred'] or '').upper() == 'YES'],
    wage_assessments=[c['name'] for c in reg_matched if (c['registry']['wage_assessments'] or '').upper() == 'YES'],
    labor_or_tax=[c['name'] for c in reg_matched if (c['registry']['labor_or_tax_violation'] or '').upper() == 'YES'],
    apprenticeship=sum(1 for c in reg_matched if (c['registry']['apprenticeship'] or '').upper() == 'YES'),
    mwbe=sum(1 for c in reg_matched if (c['registry']['mwbe'] or '').upper() == 'YES'),
    nonresponsible=[c['name'] for c in contractors if c['nonresponsible']],
    nonresponsible_rows=len(nonresp),
)

# ---------------------------------------------------------------- schedule table for the site
schedule_out = []
for r in SCHED:
    schedule_out.append(dict(schedule=r['schedule'], section=r['section'], sub=r['sub'], start=r['start'], end=r['end'],
                             wage=r['wage'], supp=r['supp'], total=round((r['wage'] or 0) + (r['supp'] or 0), 2)))

# ---------------------------------------------------------------- meta
cls_counts = collections.Counter(r['cls'] for r in work)
journey_all = [r for r in work if r['cls'] in ('below', 'at', 'above', 'package', 'range')]
meta = dict(
    built=datetime.datetime.now().isoformat(timespec='minutes'),
    source_rows_pulled=sum(1 for _ in gzip.open(SRC / 'certified-payroll-nyc-area.csv.gz', 'rt')) - 1,
    rows_city=all_rows, worker_weeks=len(work), statement_rows=len(noneg),
    week_min=min(weeks).isoformat(), week_max=max(weeks).isoformat(),
    projects=len(projects), contractors=len(contractors), categories=len(by_cat),
    categories_mapped=sum(1 for t in trades if t['mapped']),
    hours=round(sum((r['st_total_hours'] or 0) for r in work)), ot_hours=round(sum((r['ot_total_hours'] or 0) for r in work)),
    cls=dict(cls_counts), journey_rows=len(journey_all),
    pct=dict(below=pct(cls_counts['below'], len(journey_all)), at=pct(cls_counts['at'], len(journey_all)),
             above=pct(cls_counts['above'], len(journey_all)), package=pct(cls_counts['package'], len(journey_all)),
             range=pct(cls_counts['range'], len(journey_all))),
    boroughs=dict(collections.Counter(r['borough'] for r in work).most_common()),
    agencies=[dict(agency=a, worker_weeks=n, projects=len({proj_key(r) for r in work if r['agency'] == a}))
              for a, n in collections.Counter(r['agency'] for r in work).most_common(30)],
    months=[dict(month=m, worker_weeks=n) for m, n in sorted(collections.Counter(r['week'].strftime('%Y-%m') for r in work if r['week']).items())],
    registry=meta_registry,
    schedule_records=len(SCHED),
    schedule_sections={lab: len({r['section'] for r in SCHED if r['schedule'] == lab}) for lab in ('2025-26', '2026-27')},
)

OUT.mkdir(exist_ok=True)
json.dump(meta, open(OUT / 'meta.json', 'w'), indent=1)
json.dump(trades, open(OUT / 'trades.json', 'w'))
json.dump(projects, open(OUT / 'projects.json', 'w'))
json.dump(contractors, open(OUT / 'contractors.json', 'w'))
json.dump(schedule_out, open(OUT / 'schedule.json', 'w'))
json.dump(dict(crosswalk=CROSSWALK, unmapped=UNMAPPED_NOTES), open(OUT / 'crosswalk.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in meta.items() if k not in ('agencies', 'months')}, indent=1))
print('unmapped categories with rows:', [(t['category'], t['rows']) for t in trades if not t['mapped']][:40])
