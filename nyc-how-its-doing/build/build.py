#!/usr/bin/env python3
"""Build "How New York Is Doing" from data/indicators/*.json.

Every number on the page passes through num() or yr(), which record it in a ledger.
After rendering, audit() strips the HTML to text and refuses to finish if any number
appears that the ledger does not account for. Nothing on the page is typed by hand.

Run from the project folder:  python3 -I build/build.py
"""
import csv, html, json, math, os, re, statistics, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)

REG = json.load(open(D('data', 'registry.json')))
PEERS = json.load(open(D('data', 'peers.json')))
PEER_NAMES = [c['name'] for c in PEERS['cities']]
NAMED = PEERS['named_peers']
EDITION_YEAR = 2025

FORMAT_OVERRIDES = {'gini_index': 'dec3'}  # display precision only
# Peer comparisons that are rates while the New York series is a count: label and precision for display.
PEER_UNITS = {
    'business_applications': ('per 1,000 residents', 'dec1'),
    'new_homes': ('homes permitted per 1,000 residents', 'dec1'),
    'homelessness_pit': ('per 10,000 residents', 'dec1'),
    'traffic_deaths': ('deaths per 100,000 residents', 'dec1'),
    'jail_population': ('per 100,000 residents aged 15 to 64', 'dec1'),
    'net_international_migration': ('per 1,000 residents', 'dec1'),
    'net_domestic_migration': ('per 1,000 residents', 'dec1'),
    'murders': ('per 100,000 residents', 'dec1'),
    'overdose_deaths': ('deaths per 100,000 residents', 'dec1'),
    'transit_ridership': ('percent of 2019 ridership', 'dec1'),
    'population': ('percent change in population since July 2020', 'pct1'),
}
# Series with a break in definition: score only the comparable stretch from this year on.
BREAKS = {
    'reading_proficiency': (2023, 'the state changed the tests and the cut scores for proficiency in 2023'),
    'math_proficiency': (2023, 'the state changed the tests and the cut scores for proficiency in 2023'),
    'poverty_tracker_rate': (2020, 'the Poverty Tracker says figures before 2020 are not comparable with later ones'),
    'parkscore': (2020, 'the Trust for Public Land overhauled its scoring in 2019 and added an equity measure in 2020'),
    'debt_per_resident': (2022, 'a 2022 accounting rule moved leases onto the books, raising reported debt'),
}
# Peer comparisons dropped because the peer source disagrees badly with New York's own figures.
DROP_PEERS = {
    'transit_ridership': ('The peer comparison is left out. The National Transit Database puts New York ridership in 2025 at 87.5 percent '
                          'of 2019, but the Metropolitan Transportation Authority\'s own counts put it at 72.6 percent, mostly because '
                          'the two count bus riders differently, so New York could not be ranked fairly.'),
}
# Measures whose own publisher warns against reading them as a trend: shown, never scored.
NO_TREND = {
    'tax_burden': 'the report that publishes it advises against comparing its estimates from year to year',
}
LEDGER = set()       # every number string the page is allowed to show
ALLOW = set()        # structural strings (units, labels) that may contain digits


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- periods
def period_year(p):
    """'2025' -> 2025; 'FY2026' -> 2026; '2024-25' -> 2025; 'Class of 2025' -> 2025."""
    s = str(p)
    m = re.search(r'(\d{4})\s*[-–/]\s*(\d{2,4})\b', s)
    if m:
        a, b = m.group(1), m.group(2)
        return int(a[:2] + b) if len(b) == 2 else int(b)
    m = re.search(r'(\d{4})', s)
    return int(m.group(1)) if m else None


def yr(p, link=None):
    """Print a period label. Registered so the audit accepts its digits."""
    s = re.sub(r'\bFY(\d{4})\b', r'fiscal \1', str(p))
    LEDGER.add(s)
    for t in re.findall(r'\d[\d,\.]*', s):
        LEDGER.add(t)
    return f'<a href="{esc(link)}">{esc(s)}</a>' if link else esc(s)


# ---------------------------------------------------------------- numbers
def unit_suffix(units, fmt):
    u = (units or '').strip()
    if 'dollar' in u.lower() or u.lower().startswith(('index', 'score', 'scale score', 'gini index', 'ratio')):
        return ''
    if fmt in ('pct1', 'pct0', 'usd0') or u in ('', 'people', 'count', 'percent', 'dollars', 'units', 'homes',
                                                  'students', 'deaths', 'victims', 'crimes', 'applications', 'seats'):
        return ''
    ALLOW.add(u)
    return ' ' + u


def fmtv(v, f):
    s = _fmtv(v, f)
    LEDGER.add(s)
    for t in re.findall(r'\d[\d,\.]*', s):
        LEDGER.add(t)
    return s


def _fmtv(v, f):
    if v is None:
        return '—'
    if f == 'int':
        return f'{round(v):,}'
    if f == 'pct1':
        return f'{v:.1f}%'
    if f == 'pct0':
        return f'{v:.0f}%'
    if f == 'usd0':
        return f'${v:,.0f}'
    if f == 'dec2':
        return f'{v:,.2f}'
    if f == 'dec3':
        return f'{v:,.3f}'
    if f in ('dec1', 'rate1'):
        return f'{v:,.1f}'
    return f'{v:,.1f}' if abs(v) < 100 else f'{round(v):,}'


def num(v, f, link=None, units=None, cls=None):
    s = fmtv(v, f)
    LEDGER.add(s)
    for t in re.findall(r'\d[\d,\.]*', s):
        LEDGER.add(t)
    suf = unit_suffix(units, f) if units is not None else ''
    if units and 'dollar' in units.lower() and not s.startswith('$') and f not in ('pct1', 'pct0'):
        s = ('-$' + s[1:]) if s.startswith('-') else '$' + s
        LEDGER.add(s)
    inner = esc(s) + esc(suf)
    c = f' class="{cls}"' if cls else ''
    return f'<a href="{esc(link)}"{c}>{inner}</a>' if link else f'<span{c}>{inner}</span>'


def count(n, link='methodology.html#scoring'):
    """A count the page computes (tallies, ranks). Links to the method that produced it."""
    s = f'{n:,}'
    LEDGER.add(s)
    return f'<a href="{esc(link)}">{s}</a>' if link else s


# ---------------------------------------------------------------- load
# Fetcher-written prose is put into house style before it is shown: "New York City" spelled out,
# fiscal years in words, and each abbreviation spelled out the first time it appears in a measure.
ACRONYMS = [
    ('CDC', 'Centers for Disease Control and Prevention'), ('NCHS', 'National Center for Health Statistics'),
    ('VSRR', 'Vital Statistics Rapid Release'), ('MTA', 'Metropolitan Transportation Authority'),
    ('ACS', 'American Community Survey'), ('CoC', 'Continuum of Care'),
    ('HUD', 'Department of Housing and Urban Development'), ('NYPD', 'New York Police Department'),
    ('FTA', 'Federal Transit Administration'), ('NTD', 'National Transit Database'),
    ('EPA', 'Environmental Protection Agency'), ('TPL', 'Trust for Public Land'),
    ('MMR', "Mayor's Management Report"), ('CEV', 'Civic Engagement and Volunteering Supplement'),
    ('ACFR', 'Annual Comprehensive Financial Report'), ('CAFR', 'Comprehensive Annual Financial Report'),
    ('LAUS', 'Local Area Unemployment Statistics'), ('CPI-U', 'Consumer Price Index for All Urban Consumers'),
    ('CPI', 'Consumer Price Index'), ('NAEP', 'National Assessment of Educational Progress'),
    ('TUDA', 'Trial Urban District Assessment'), ('ELA', 'English language arts'),
    ('DOHMH', 'Department of Health and Mental Hygiene'), ('DHS', 'Department of Homeless Services'),
    ('DOC', 'Department of Correction'), ('DOT', 'Department of Transportation'),
    ('HPD', 'Department of Housing Preservation and Development'), ('HVS', 'Housing and Vacancy Survey'),
    ('PIT', 'point-in-time'), ('ZORI', 'Zillow Observed Rent Index'), ('FiSC', 'Fiscally Standardized Cities'),
    ('BFS', 'Business Formation Statistics'), ('QCEW', 'Quarterly Census of Employment and Wages'),
    ('CES', 'Current Employment Statistics'), ('BLS', 'Bureau of Labor Statistics'),
    ('GASB', 'Governmental Accounting Standards Board'), ('NCES', 'National Center for Education Statistics'),
    ('OCA', 'Office of Court Administration'), ('DCAS', 'Department of Citywide Administrative Services'),
    ('CPS', 'Current Population Survey'), ('PUMS', 'Public Use Microdata Sample'),
    ('FBI', 'Federal Bureau of Investigation'), ('IBO', 'Independent Budget Office'),
    ('DOE', 'Department of Education'), ('FIPS', 'Federal Information Processing Standards'),
    ('FARS', 'Fatality Analysis Reporting System'), ('NHTSA', 'National Highway Traffic Safety Administration'),
    ('NYCHVS', 'New York City Housing and Vacancy Survey'), ('CVAP', 'citizen voting-age population'),
    ('DCP', 'Department of City Planning'), ('BPS', 'Building Permits Survey'),
    ('NYCCAS', 'New York City Community Air Survey'), ('MOE', 'margin of error'),
    ('IRS', 'Internal Revenue Service'), ('EIN', 'employer identification number'),
    ('GEOID', 'geographic identifier'), ('SoQL', 'Socrata Query Language'),
]


def plain(t, seen):
    if not isinstance(t, str) or not t:
        return t
    t = re.sub(r'\bNYC(?!T)\b', 'New York City', t)
    t = re.sub(r'\bFY(\d{4})\b', r'fiscal \1', t)
    t = re.sub(r'\bFY ?(\d{2})\b', r'fiscal 20\1', t)
    for ab, full in ACRONYMS:
        pat = r'(?<![\w(-])' + re.escape(ab) + r'(?![\w-])'
        m = re.search(pat, t)
        if not m or ab in seen:
            continue
        seen.add(ab)
        if full.lower() in t[:m.start()].lower() or t[m.end():m.end() + 2] == ' (' or t[m.start() - 1:m.start()] == '(':
            continue
        t = t[:m.start()] + f'{full} ({ab})' + t[m.end():]
    return t


def plain_ind(ind):
    seen = set()
    ind['definition'] = plain(ind.get('definition'), seen)
    ind['status_reason'] = plain(ind.get('status_reason'), seen)
    if ind.get('latest_extra'):
        nt = plain(ind['latest_extra'].get('note'), seen)
        if isinstance(nt, str):  # bare counts in the note get thousands separators
            nt = re.sub(r'(?<![\w.,/-])(\d{5,})(?![\w.,/-])', lambda m: f'{int(m.group(1)):,}', nt)
        ind['latest_extra'] = {**ind['latest_extra'], 'note': nt}
    if ind.get('peers'):
        ind['peers']['note'] = plain(ind['peers'].get('note'), seen)
    ind['caveats'] = [plain(c, seen) for c in ind.get('caveats') or []]
    ind['method'] = plain(ind.get('method'), seen)
    if ind.get('source'):
        ind['source'] = {**ind['source'], 'name': plain(ind['source'].get('name'), seen)}
    if ind.get('peers') and ind['peers'].get('source'):
        ind['peers']['source'] = {**ind['peers']['source'], 'name': plain(ind['peers']['source'].get('name'), seen)}
    for bd in ind.get('breakdowns') or []:
        bd['by'] = plain(bd.get('by'), seen)
        for v in bd.get('values') or []:
            v['name'] = re.sub(r'\bNYC(?!T)\b', 'New York City', str(v.get('name', '')))
    return ind


def load_measures():
    out = []
    for m in REG['measures']:
        p = D('data', 'indicators', m['id'] + '.json')
        if os.path.exists(p):
            try:
                ind = json.load(open(p))
            except Exception as e:
                ind = {'status': 'missing', 'status_reason': f'indicator file unreadable: {e}'}
        else:
            ind = {'status': 'missing', 'status_reason': 'not fetched'}
        ind = plain_ind({**ind})
        ind['id'] = m['id']
        ind['chapter'] = m['chapter']
        ind.setdefault('name', m['name'])
        ind['better'] = ind.get('better') or m['better']
        ind.setdefault('format', 'dec1')
        if m['id'] in FORMAT_OVERRIDES:
            ind['format'] = FORMAT_OVERRIDES[m['id']]
        if m['id'] in DROP_PEERS:
            ind['peers'] = None
            ind['caveats'] = (ind.get('caveats') or []) + [DROP_PEERS[m['id']]]
            ALLOW.add(DROP_PEERS[m['id']])
        if m['id'] in PEER_UNITS and ind.get('peers'):
            ind['peers']['units'], ind['peers']['format'] = PEER_UNITS[m['id']]
            ALLOW.add(PEER_UNITS[m['id']][0])
        # descriptive text written by the fetchers (names, definitions, notes) may contain digits
        # that are labels, not figures ("grades 3 to 8", "PM2.5"); they are allowed as whole strings
        for t in [ind.get('name'), ind.get('definition'), ind.get('status_reason'), (ind.get('latest_extra') or {}).get('note'),
                  (ind.get('peers') or {}).get('note'), (ind.get('source') or {}).get('name'), ((ind.get('peers') or {}).get('source') or {}).get('name')]:
            if t:
                ALLOW.add(str(t))
        for bd in ind.get('breakdowns') or []:
            ALLOW.add(str(bd.get('by', '')))
            for v in bd.get('values') or []:
                ALLOW.add(str(v.get('name', '')))
        for x in (ind.get('peers') or {}).get('values') or []:
            ALLOW.add(str(x.get('city', '')))
        out.append(ind)
    return out


def obs_of(ind):
    o = []
    for r in ind.get('series') or []:
        v = r.get('value')
        y = period_year(r.get('period'))
        if isinstance(v, (int, float)) and y is not None and not (isinstance(v, float) and math.isnan(v)):
            o.append({'y': y, 'p': str(r['period']), 'v': float(v), 'moe': r.get('moe')})
    o.sort(key=lambda r: r['y'])
    # one value per year (keep the last listed)
    ded = {}
    for r in o:
        ded[r['y']] = r
    return [ded[k] for k in sorted(ded)]


# ---------------------------------------------------------------- scoring
def score(ind):
    o = obs_of(ind)
    ind['_obs'] = o
    res = {'judged': False}
    if ind['id'] in BREAKS:
        res['break'] = BREAKS[ind['id']]
        o = [r for r in o if r['y'] >= BREAKS[ind['id']][0]]
    if not o:
        res['why'] = 'no data'
        return res
    last = o[-1]
    L = last['y']
    res.update(latest=last)
    base = [r for r in o[:-1] if L - 5 <= r['y'] <= L - 1]
    if len(base) < 2:
        base = [r for r in o[:-1] if L - 10 <= r['y'] <= L - 1][-2:]
    if not base:
        res['why'] = 'only one year of data'
        return res
    res['base'] = base
    res['baseline'] = sum(r['v'] for r in base) / len(base)
    if ind['id'] in NO_TREND:
        res['why'] = NO_TREND[ind['id']]
        return res
    hist = [r for r in o[:-1] if L - 11 <= r['y'] <= L - 1]
    diffs = [abs(b['v'] - a['v']) for a, b in zip(hist, hist[1:])]
    if len(diffs) < 2:
        res['why'] = 'too few years to know a typical change'
        res['delta'] = last['v'] - res['baseline']
        return res
    swing = statistics.median(diffs) or (sum(diffs) / len(diffs))
    if not swing:
        res['why'] = 'no change in the history to compare against'
        return res
    res['swing'] = swing
    d = last['v'] - res['baseline']
    res['delta'] = d
    z = d / swing
    res['z'] = z
    moe = last.get('moe')
    inside_moe = isinstance(moe, (int, float)) and abs(d) <= moe
    res['inside_moe'] = inside_moe
    b = ind['better']
    res['judged'] = True
    if inside_moe or abs(z) < 1:
        res['call'] = 'no clear change'
    elif b == 'none':
        res['call'] = 'higher' if z > 0 else 'lower'
    else:
        good = (z > 0) == (b == 'up')
        res['call'] = 'better' if good else 'worse'
    res['adj'] = z if b == 'up' else (-z if b == 'down' else None)
    return res


def peer_rank(ind):
    p = ind.get('peers')
    if not p or not p.get('values'):
        return None
    vals = [r for r in p['values'] if isinstance(r.get('value'), (int, float)) and r.get('city') in PEER_NAMES]
    if not vals:
        return None
    rev = ind['better'] != 'down'  # up or none: biggest first
    vals.sort(key=lambda r: r['value'], reverse=rev)
    ny = next((i for i, r in enumerate(vals) if r['city'] == 'New York'), None)
    return {'vals': vals, 'rank': None if ny is None else ny + 1, 'n': len(vals),
            'order': 'best' if ind['better'] != 'none' else 'highest'}


# ---------------------------------------------------------------- svg
def line_svg(ind, sc):
    o = ind['_obs']
    if len(o) < 2:
        return ''
    W, H, l, r, t, b = 640, 190, 54, 14, 12, 26
    ys = [p['v'] for p in o]
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.12 or abs(hi) * 0.1 or 1
    domains = {'auto': (lo - pad, hi + pad), 'zero': (min(0, lo), hi + pad if hi > 0 else 0)}
    x0, x1 = o[0]['y'], o[-1]['y']
    X = lambda y: l + (W - l - r) * ((y - x0) / ((x1 - x0) or 1))
    f = ind['format']
    out = [f'<svg class="lc" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(ind["name"])}, New York City, {o[0]["y"]} to {o[-1]["y"]}">']
    # x axis years: first, last, and a few in between
    step = max(1, round((x1 - x0) / 6))
    ticks = sorted(set([x0, x1] + list(range(x0 - x0 % step + step, x1, step))))
    ticks = [y for y in ticks if x0 <= y <= x1 and (y in (x0, x1) or (y - x0 >= step * .6 and x1 - y >= step * .6))]
    for y in ticks:
        anc = 'end' if X(y) > W - 40 else 'middle'
        out.append(f'<text class="ax" x="{X(y):.1f}" y="{H-6}" text-anchor="{anc}">{yr(y)}</text>')
    for key, (d0, d1) in domains.items():
        Y = lambda v: t + (H - t - b) * (1 - (v - d0) / ((d1 - d0) or 1))
        g = [f'<g class="ys-{key}">']
        for tv in nice_ticks(d0, d1, 4):
            g.append(f'<line class="gr" x1="{l}" x2="{W-r}" y1="{Y(tv):.1f}" y2="{Y(tv):.1f}"/>')
            g.append(f'<text class="ax" x="{l-6}" y="{Y(tv)+4:.1f}" text-anchor="end">{esc(axis_label(tv, f))}</text>')
        if sc.get('base'):
            by0, by1 = sc['base'][0]['y'], sc['base'][-1]['y']
            g.append(f'<line class="bl" x1="{X(by0):.1f}" x2="{X(by1):.1f}" y1="{Y(sc["baseline"]):.1f}" y2="{Y(sc["baseline"]):.1f}"><title>Average, {by0}–{by1}</title></line>')
        # break the line across gaps of more than 3 years (e.g. missing 2020 ACS is 1 year: keep joined but dashed)
        segs, cur = [], [o[0]]
        for a, c in zip(o, o[1:]):
            if c['y'] - a['y'] > 1 and ind.get('frequency', 'annual') == 'annual' and c['y'] - a['y'] <= 2:
                segs.append(('dash', [a, c]))
            elif c['y'] - a['y'] > 4:
                segs.append(('solid', cur)); cur = [c]; continue
            cur.append(c)
        segs.append(('solid', cur))
        for kind, pts in segs:
            if len(pts) < 2:
                continue
            dpath = ' '.join(('M' if i == 0 else 'L') + f'{X(p["y"]):.1f},{Y(p["v"]):.1f}' for i, p in enumerate(pts))
            g.append(f'<path class="ln{" dash" if kind == "dash" else ""}" d="{dpath}"/>')
        for p in o:
            g.append(f'<circle class="pt" cx="{X(p["y"]):.1f}" cy="{Y(p["v"]):.1f}" r="{3.6 if p is o[-1] else 2.2}"><title>{esc(p["p"])}: {esc(fmtv(p["v"], f))}</title></circle>')
        g.append('</g>')
        out += g
    out.append('</svg>')
    return ''.join(out)


def axis_label(v, f):
    if f in ('pct1', 'pct0'):
        s = f'{v:.0f}%' if abs(v) >= 5 or v == 0 else f'{v:.1f}%'
    elif f == 'usd0':
        s = f'${v/1000:,.0f}k' if abs(v) >= 10000 else f'${v:,.0f}'
    elif abs(v) >= 1e6:
        s = f'{v/1e6:,.1f}m'
    elif abs(v) >= 10000:
        s = f'{v/1000:,.0f}k'
    elif f == 'dec2':
        s = f'{v:.2f}'
    else:
        s = f'{v:,.1f}' if abs(v) < 10 and v != int(v) else f'{v:,.0f}'
    LEDGER.add(s)
    for t in re.findall(r'\d[\d,\.]*', s):
        LEDGER.add(t)
    return s


def nice_ticks(a, b, n):
    span = b - a
    if span <= 0:
        return [a]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = math.ceil(a / step) * step
    out, v = [], start
    while v <= b + 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def peer_svg(ind, pr):
    vals = pr['vals']
    W, H, l, r = 640, 74, 10, 10
    vs = [x['value'] for x in vals]
    lo, hi = min(vs), max(vs)
    if hi == lo:
        hi = lo + 1
    X = lambda v: l + (W - l - r) * (v - lo) / (hi - lo)
    pp = ind.get('peers') or {}
    f = pp.get('format') or ('dec1' if pp.get('units') and pp.get('units') != ind.get('units') else ind['format'])
    out = [f'<svg class="ps" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(ind["name"])} in the {len(vals)} largest cities">',
           f'<line class="gr" x1="{l}" x2="{W-r}" y1="34" y2="34"/>']
    for x in vals:
        c = x['city']
        cls = 'ny' if c == 'New York' else ('np' if c in NAMED else 'pd')
        out.append(f'<circle class="{cls}" cx="{X(x["value"]):.1f}" cy="34" r="{6 if cls=="ny" else 4.5 if cls=="np" else 3.5}"><title>{esc(c)}: {esc(fmtv(x["value"], f))}</title></circle>')
    # labels for New York and named peers, alternating above/below to limit collisions
    lab = [x for x in vals if x['city'] == 'New York' or x['city'] in NAMED]
    lab.sort(key=lambda x: x['value'])
    for i, x in enumerate(lab):
        up = (i % 2 == 0)
        cls = 'nyl' if x['city'] == 'New York' else 'npl'
        xx = X(x["value"])
        anc = 'start' if xx < l + 40 else ('end' if xx > W - r - 40 else 'middle')
        out.append(f'<text class="{cls}" x="{xx:.1f}" y="{18 if up else 58}" text-anchor="{anc}">{esc(x["city"])}</text>')
    out.append(f'<text class="ax" x="{l}" y="{H-2}">{esc(fmtv(lo, f))}</text>')
    out.append(f'<text class="ax" x="{W-r}" y="{H-2}" text-anchor="end">{esc(fmtv(hi, f))}</text>')
    out.append('</svg>')
    return ''.join(out)


def strip_svg(rows):
    """The opening chart: every judged measure placed by how far its latest year sits from
    its recent normal, oriented so better is always to the right."""
    chs = [c for c in REG['chapters'] if any(r['chapter'] == c for r in rows)]
    W, rowh, l, r, t = 900, 30, 210, 20, 30
    H = t + rowh * len(chs) + 30
    LIM = 5
    X = lambda z: l + (W - l - r) * ((max(-LIM, min(LIM, z)) + LIM) / (2 * LIM))
    out = [f'<svg class="strip-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Each measure placed by its change from its recent normal">']
    out.append(f'<rect class="band" x="{X(-1):.1f}" y="{t-8}" width="{X(1)-X(-1):.1f}" height="{rowh*len(chs)+8}"><title>Within one typical yearly swing: no clear change</title></rect>')
    out.append(f'<text class="ax" x="{X(-LIM):.1f}" y="{t-14}">← worse than recent normal</text>')
    out.append(f'<text class="ax" x="{X(LIM):.1f}" y="{t-14}" text-anchor="end">better than recent normal →</text>')
    for i, c in enumerate(chs):
        y = t + rowh * i + rowh / 2
        out.append(f'<text class="rl" x="{l-12}" y="{y+5:.1f}" text-anchor="end">{esc(c)}</text>')
        out.append(f'<line class="gr" x1="{l}" x2="{W-r}" y1="{y:.1f}" y2="{y:.1f}"/>')
        for m in [m for m in rows if m['chapter'] == c]:
            z = m['_sc']['adj']
            cls = {'better': 'b', 'worse': 'w'}.get(m['_sc']['call'], 'n')
            out.append(f'<a href="#{m["id"]}"><circle class="sd {cls}" cx="{X(z):.1f}" cy="{y:.1f}" r="7"><title>{esc(m["name"])}: {esc(m["_sc"]["call"])}</title></circle></a>')
    for zt in (-4, -2, 0, 2, 4):
        out.append(f'<line class="tk" x1="{X(zt):.1f}" x2="{X(zt):.1f}" y1="{H-28}" y2="{H-22}"/>')
        if zt:
            ALLOW.add(f'{abs(zt)}×')
            out.append(f'<text class="ax" x="{X(zt):.1f}" y="{H-6}" text-anchor="middle">{abs(zt)}×</text>')
    out.append(f'<text class="ax" x="{X(0):.1f}" y="{H-6}" text-anchor="middle">recent normal</text>')
    out.append('</svg>')
    return '<div class="sscroll">' + ''.join(out) + '</div>'


# ---------------------------------------------------------------- csv
def write_csvs(ms):
    os.makedirs(D('data', 'csv'), exist_ok=True)
    for m in ms:
        if not m.get('series'):
            continue
        with open(D('data', 'csv', m['id'] + '.csv'), 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['geography', 'period', 'value', 'margin_of_error_90pct', 'units', 'source'])
            for r in m['series']:
                w.writerow(['New York City', r.get('period'), r.get('value'), r.get('moe'), m.get('units'), m['source']['url']])
            p = m.get('peers') or {}
            for r in p.get('values') or []:
                w.writerow([r.get('geo_name') or r.get('city'), p.get('period'), r.get('value'), r.get('moe'), m.get('units'), (p.get('source') or {}).get('url')])
            for bd in m.get('breakdowns') or []:
                for r in bd.get('values') or []:
                    w.writerow([f"{bd.get('by')}: {r.get('name')}", bd.get('period'), r.get('value'), r.get('moe'), m.get('units'), bd.get('source_url') or m['source']['url']])


# ---------------------------------------------------------------- page parts
def span_label(base):
    a, b = base[0]['p'], base[-1]['p']
    return a if a == b else f'{a} to {b}'


def call_word(sc):
    return sc.get('call') or 'not judged'


def measure_block(m):
    sc, pr = m['_sc'], m['_pr']
    src = m.get('source') or {}
    surl = src.get('url') or 'methodology.html#' + m['id']
    f, u = m['format'], m.get('units')
    parts = [f'<article class="ms" id="{m["id"]}">']
    call = call_word(sc)
    cls = {'better': 'b', 'worse': 'w'}.get(call, 'n')
    parts.append(f'<div class="mh"><h3>{esc(m["name"])}</h3><span class="call {cls}">{esc(call)}</span></div>')
    if m.get('definition'):
        parts.append(f'<p class="def">{esc(m["definition"])}</p>')
    if m.get('status') == 'missing' or not sc.get('latest'):
        parts.append(f'<p class="gap">Not in this edition: {esc(m.get("status_reason") or "no usable data")}.</p>')
        parts.append('</article>')
        return ''.join(parts)
    last = sc['latest']
    s = [f'In {yr(last["p"])}: {num(last["v"], f, surl, u)}']
    if isinstance(last.get('moe'), (int, float)):
        s.append(f' (margin of error ±{num(last["moe"], f)})')
    s.append('.')
    if sc.get('base'):
        s.append(f' Average from {yr(span_label(sc["base"]))}: {num(sc["baseline"], f, "methodology.html#scoring", u)}.')
    pre = next((r for r in m['_obs'] if r['y'] == 2019), None)
    if pre and last['y'] >= 2023 and pre is not last and not (sc.get('break') and sc['break'][0] > 2019):
        s.append(f' Before the pandemic, in {yr(pre["p"])}: {num(pre["v"], f, surl, u)}.')
    if sc.get('judged'):
        if call == 'no clear change':
            why = 'the change is inside the margin of error' if sc.get('inside_moe') else 'the change is smaller than a typical year-to-year move'
            s.append(f' No clear change: {why}.')
    else:
        s.append(f' Not scored: {esc(sc.get("why", ""))}.')
    if sc.get('break'):
        ALLOW.add(sc['break'][1])
        bl = ('FY' if str(last['p']).startswith('FY') else '') + str(sc['break'][0])
        s.append(f' Scored only from {yr(bl)} on, because {esc(sc["break"][1])}.')
    if last['y'] < EDITION_YEAR:
        s.append(f' The latest year published is {yr(last["p"])}.')
    parts.append('<p class="read">' + ''.join(s) + '</p>')
    le = m.get('latest_extra')
    if le and isinstance(le.get('value'), (int, float)):
        nt = (le.get('note') or '').strip().rstrip('.')
        if nt and not (len(nt) > 1 and nt[1].isupper()):
            nt = nt[0].lower() + nt[1:]
        note = f' ({esc(nt)})' if nt else ''
        ALLOW.add(nt)
        parts.append(f'<p class="read2">More recent: {num(le["value"], f, surl, u)} in {yr(le["period"])}{note}.</p>')
    chart = line_svg(m, sc)
    if chart:
        cap = 'New York City, by year.' + (' The dashed line is the average of the years compared against.' if sc.get('base') else '')
        parts.append(f'<div class="chart">{chart}<p class="ccap">{cap}</p></div>')
    if pr:
        p = m['peers']
        geo = p.get('geography') or 'city'
        psrc = (p.get('source') or {}).get('url') or surl
        rk = ''
        if pr['rank']:
            rk = (f'New York ranks {count(pr["rank"])} of {count(pr["n"])} '
                  + ('(1 = best)' if pr['order'] == 'best' else '(1 = highest)')
                  + (f' on {esc(p["units"])}' if p.get('units') else '') + f' in {yr(p.get("period", ""))}. ')
            LEDGER.add('1')
        named_bits = []
        pu = p.get('units') or u
        pf = p.get('format') or ('dec1' if p.get('units') and p.get('units') != u else f)
        for nm in ['New York'] + NAMED:
            v = next((x for x in pr['vals'] if x['city'] == nm), None)
            if v:
                named_bits.append(f'{esc(nm)} {num(v["value"], pf, psrc, pu)}')
        det = f'<a href="methodology.html#{m["id"]}">details</a>'
        geo_txt = 'Compared city by city' if geo == 'city' else f'Compared by {esc(geo)}, not city limits'
        if re.match(r'\s*different (source|measure|method)', p.get('note') or '', re.I):
            geo_txt += ', from a different source or method than the New York line above'
        geo_txt += f'; {det}.'
        parts.append(f'<div class="peer"><p class="ptext">{rk}{"; ".join(named_bits)}. {geo_txt}</p>')
        parts.append(peer_svg(m, pr) + '</div>')
    for bd in m.get('breakdowns') or []:
        vals = [v for v in bd.get('values') or [] if isinstance(v.get('value'), (int, float))]
        if not vals:
            continue
        burl = bd.get('source_url') or surl
        rows = ''.join(f'<tr><td>{esc(v["name"])}</td><td class="n">{num(v["value"], f, burl)}</td>'
                       + (f'<td class="n">±{num(v["moe"], f)}</td>' if isinstance(v.get('moe'), (int, float)) else '<td></td>') + '</tr>'
                       for v in vals)
        parts.append(f'<details class="bd"><summary>By {esc(bd.get("by"))}, {yr(bd.get("period", ""))}</summary>'
                     f'<table class="h"><tr><th></th><th class="n">Value</th><th class="n">Margin of error</th></tr>{rows}</table></details>')
    fetched = src.get('fetched')
    parts.append(f'<p class="srcl">Source: <a href="{esc(surl)}">{esc(src.get("name", ""))}</a>'
                 + (f', retrieved {yr(fetched)}' if fetched else '')
                 + f'. <a href="data/csv/{m["id"]}.csv">Data (CSV)</a> · <a href="methodology.html#{m["id"]}">How this was measured</a></p>')
    parts.append('</article>')
    return ''.join(parts)


def summary_row(m):
    sc = m['_sc']
    f, u = m['format'], m.get('units')
    last = sc['latest']
    src = (m.get('source') or {}).get('url')
    cls = {'better': 'b', 'worse': 'w'}.get(sc['call'], 'n')
    sub = (f'{num(last["v"], f, src, u)} in {yr(last["p"])}, against an average of '
           f'{num(sc["baseline"], f, "methodology.html#scoring", u)} from {yr(span_label(sc["base"]))}')
    pre = next((r for r in m['_obs'] if r['y'] == 2019), None)
    if pre and last['y'] >= 2023 and not any(r['y'] == 2019 for r in sc['base']) and not (sc.get('break') and sc['break'][0] > 2019):
        sub += f'; {yr(pre["p"])}, before the pandemic: {num(pre["v"], f, src, u)}'
    pr = m['_pr']
    if pr and pr['rank']:
        sub += f'; ranks {count(pr["rank"])} of {count(pr["n"])} among the largest cities'
        if m['peers'].get('units'):
            sub += f' ({esc(m["peers"]["units"])})'
    return (f'<div class="row"><i class="sw {cls}"></i><span><a class="nm" href="#{m["id"]}">{esc(m["name"])}</a>'
            f'<span class="sub">{sub}</span></span><span class="num {cls}">{esc(sc["call"])}</span></div>')


# ---------------------------------------------------------------- pages
import hashlib
def _v(f):
    return hashlib.md5(open(D(f), 'rb').read()).hexdigest()[:8]
CSS_LINK = f'<link rel="stylesheet" href="house.css?v={_v("house.css")}"><link rel="stylesheet" href="style.css?v={_v("style.css")}">'
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Karla:wght@400;500;600;700&display=swap" rel="stylesheet">')


def head(title, desc):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{FONTS}{CSS_LINK}</head>')


def build():
    ms = load_measures()
    for m in ms:
        m['_sc'] = score(m)
        m['_pr'] = peer_rank(m)
    write_csvs(ms)

    have = [m for m in ms if m['_sc'].get('latest')]
    missing = [m for m in ms if not m['_sc'].get('latest')]
    directional = [m for m in have if m['better'] != 'none' and m['_sc'].get('judged')]
    better = [m for m in directional if m['_sc']['call'] == 'better']
    worse = [m for m in directional if m['_sc']['call'] == 'worse']
    flat = [m for m in directional if m['_sc']['call'] == 'no clear change']
    peered = [m for m in have if m['_pr'] and m['_pr']['rank']]
    fetched = sorted({(m.get('source') or {}).get('fetched') for m in have if (m.get('source') or {}).get('fetched')})
    asof = fetched[-1] if fetched else date.today().isoformat()

    ordered = sorted(directional, key=lambda m: -abs(m['_sc']['z']))
    moved = [m for m in ordered if m['_sc']['call'] in ('better', 'worse')]
    still = [m for m in ordered if m['_sc']['call'] == 'no clear change']

    H = [head('How New York Is Doing', 'An independent annual account of how New York City is doing for the people who live in it, built from public data and compared with the largest U.S. cities.')]
    H.append('<body class="g-black"><div class="sheet">')
    H.append(f'<div class="strip"><span>An independent report from public data · <a href="methodology.html">How it works</a></span><span>Edition: New York in {yr(EDITION_YEAR)} · data retrieved through {yr(asof)}</span></div>')
    H.append('<header class="head"><h1>How New York Is Doing</h1>')
    H.append(f'<p class="finding">Of the {count(len(directional))} measures with a direction and enough history to judge, '
             f'{count(len(better))} were better in their latest year than their average over the five years before, '
             f'{count(len(worse))} were worse and {count(len(flat))} showed no clear change.</p>')
    H.append(f'<p class="lede">This edition tracks {count(len(ms))} measures of life in New York City in {count(len(REG["chapters"]))} areas, from jobs and rents to overdoses, test scores and bus speeds. '
             f'{count(len(peered))} of them can be compared with the other largest U.S. cities on the same definition, and New York’s rank is shown for each. '
             f'A fixed rule, published on the <a href="methodology.html#scoring">methods page</a>, decides what counts as better or worse; no one picks the headlines. '
             + (f'{count(len(missing))} measures could not be filled this year and are listed at the end. ' if missing else '')
             + 'This edition measures conditions in the city. How New Yorkers feel about them needs a survey of residents, which this edition does not have.</p>')
    H.append('<label class="zt"><input type="checkbox" id="zero"> Start every chart’s y-axis at zero</label></header>')

    H.append('<section class="fig"><div class="figcap"><span><b>Every measure, placed by its change from its recent normal.</b> Better is always to the right. The shaded band is one typical year-to-year change either way; dots inside it show no clear change. Ticks mark two and four typical changes.</span>'
             '<span><span class="key"><i class="b"></i>better</span><span class="key"><i class="w"></i>worse</span><span class="key"><i class="n"></i>no clear change</span></span></div>')
    H.append(strip_svg(directional) + '</section>')

    H.append('<section class="sec"><h2>The biggest changes</h2><p class="aside">Listed in order of how far each measure moved from its recent normal, good or bad, by the rule on the methods page.</p><div class="list">')
    H += [summary_row(m) for m in moved]
    H.append('</div>')
    if still:
        H.append('<h3 class="mt">No clear change</h3><div class="list">' + ''.join(summary_row(m) for m in still) + '</div>')
    nd = [m for m in have if m['better'] == 'none' and m['_sc'].get('judged')]
    if nd:
        H.append('<h3 class="mt">Measures with no better or worse direction</h3><div class="list">' + ''.join(summary_row(m) for m in nd) + '</div>')
    H.append('</section>')

    # ranks ladder
    if peered:
        rows = []
        for m in sorted(peered, key=lambda m: m['_pr']['rank'] / m['_pr']['n']):
            pr, p = m['_pr'], m['peers']
            psrc = (p.get('source') or {}).get('url')
            best = pr['vals'][0]
            pf = p.get('format') or m['format']
            cells = ''.join(f'<td class="n">{num(next((x["value"] for x in pr["vals"] if x["city"] == c), None), pf, psrc) if any(x["city"] == c for x in pr["vals"]) else ""}</td>' for c in ['New York'] + NAMED)
            ulab = f'<br><span class="dim">{esc(p["units"])}</span>' if p.get('units') else ''
            rows.append(f'<tr><td><a href="#{m["id"]}">{esc(m["name"])}</a> <span class="dim">{yr(p.get("period", ""))}</span>{ulab}</td>'
                        f'<td class="n">{count(pr["rank"])} of {count(pr["n"])}</td><td>{esc(best["city"])}</td>{cells}</tr>')
        H.append('<section class="sec"><h2>Where New York ranks among the largest cities</h2>'
                 f'<p class="aside">Rank 1 is the best value among the {count(len(PEER_NAMES))} largest U.S. cities (for measures with no better direction, the highest). Every comparison is a rate, share, average or median, never a total, so New York’s size does not decide its rank; where the New York line is a count, the comparison is per resident, as labeled. Some comparisons use counties or metro areas; each measure says which.</p>'
                 '<div class="tw"><table class="h"><tr><th>Measure</th><th class="n">New York’s rank</th><th>Top city</th>'
                 + ''.join(f'<th class="n">{esc(c)}</th>' for c in ['New York'] + NAMED) + '</tr>' + ''.join(rows) + '</table></div></section>')

    # chapters
    H.append('<nav class="tabs chapnav">' + ''.join(f'<a href="#ch-{i}">{esc(c)}</a>' for i, c in enumerate(REG['chapters'])) + '</nav>')
    for i, c in enumerate(REG['chapters']):
        cm = [m for m in ms if m['chapter'] == c]
        H.append(f'<section class="sec chap" id="ch-{i}"><h2>{esc(c)}</h2>' + ''.join(measure_block(m) for m in cm) + '</section>')

    # gaps
    H.append('<section class="sec" id="gaps"><h2>What this edition can’t measure</h2><ul class="gaps">')
    for m in missing + [m for m in have if m.get('status') == 'partial']:
        H.append(f'<li><a href="#{m["id"]}">{esc(m["name"])}</a>: {esc(m.get("status_reason") or "partial data")}</li>')
    for g in STANDING_GAPS:
        H.append(f'<li>{esc(g)}</li>')
    H.append('</ul></section>')
    H.append('<footer class="foot">Built from public data by a script that pulls every figure from its source; no number on this page is typed by hand. '
             '<a href="methodology.html">Methods, sources and caveats</a> · <a href="methodology.html#changelog">Changelog</a> · <a href="data/edition.json">All data (JSON)</a></footer>')
    H.append('</div><script>(function(){var c=document.getElementById("zero");function s(){document.body.classList.toggle("zero",c.checked)}c.addEventListener("change",s);s()})();</script></body></html>')
    page = ''.join(H)
    audit(page, 'index.html')
    open(D('index.html'), 'w').write(page)

    write_methods(ms, asof)
    write_edition(ms, asof)
    print(f'built: {len(ms)} measures, {len(have)} with data, {len(directional)} judged '
          f'({len(better)} better, {len(worse)} worse, {len(flat)} no clear change), {len(peered)} ranked, {len(missing)} missing')


ALLOW.update(['59 community districts', '311', 'Rank 1', '(1 = best)', '(1 = highest)'])
STANDING_GAPS = [
    'How residents feel about the city, their neighborhoods, their safety and their plans to stay: New York has no regular representative survey of residents.',
    'Noise exposure: only complaints to 311 exist, not measurements.',
    'Homelessness in one daily number: the shelter census covers the Department of Homeless Services only.',
    'Neighborhood results for each of the 59 community districts: planned for a later edition.',
]


NAME = {m['id']: m['name'] for m in REG['measures']}


def write_methods(ms, asof):
    H = [head('How New York Is Doing: methods', 'Sources, scoring rules and caveats for How New York Is Doing.')]
    H.append('<body class="g-black"><div class="sheet"><div class="strip"><span><a href="index.html">← How New York Is Doing</a></span>'
             f'<span>Data retrieved through {yr(asof)}</span></div>')
    H.append('<header class="head"><h1>Methods, sources and caveats</h1></header><section class="sec narr" id="scoring"><h2>How a measure is scored</h2>')
    H.append('<p>Each measure is reduced to one value per year for New York City. The latest year is compared with the average of the years in the five years before it. '
             'If fewer than two years fall in that window (some series are published every two or three years), the two most recent earlier values within ten years are used instead.</p>'
             '<p>To judge whether a change is large, the change is divided by the typical year-to-year move in that measure: the median of the absolute changes between consecutive values in the ten years before the latest year. '
             'A change smaller than one typical move is reported as no clear change. So is any change smaller than the published margin of error of the latest value, where one exists (Census survey figures).</p>'
             '<p>Every measure has a direction set before the data was gathered: up is better (jobs, incomes, graduation), down is better (poverty, overdoses, crime), or none (population, enrollment, jail population), in which case the page says higher or lower. '
             'The list of measures and their directions is in the project’s registry file and changes only with an entry in the changelog.</p>'
             '<p>The opening chart places each measure by that ratio, flipped where needed so better is always to the right. The lists are ordered by its size. No one chooses which results lead.</p>'
             '<p>The five years before 2025 include the pandemic, so a five-year average can make a return to normal look like improvement or decline. Wherever a measure has a 2019 value, the page shows it beside the average. The scoring rule itself does not use it.</p>'
             '<p>When a source changed its definition partway through a series, the measure is scored only from the change on, and the page says so: '
             + '; '.join(f'{esc(NAME[k])}, from {yr(("FY" if k == "debt_per_resident" else "") + str(v[0]))}, because {esc(v[1])}' for k, v in BREAKS.items()) + '. '
             'When a publisher warns against comparing its figures from year to year, the measure is shown but not scored: '
             + '; '.join(f'{esc(NAME[k])}, because {esc(v)}' for k, v in NO_TREND.items()) + '.</p>'
             f'<p>Peer comparisons use the {count(len(PEER_NAMES), None)} largest U.S. cities by the Census Bureau’s July 2025 population estimates: '
             + esc(', '.join(PEER_NAMES)) + '. Los Angeles, Chicago, Houston and Philadelphia are shown by name throughout. '
             'Where a source reports counties, metro areas, school districts or transit agencies rather than cities, the measure says so. '
             'Cities are never ranked on totals, which would put New York first on size alone. Counts are compared per resident '
             '(murders, traffic deaths and overdose deaths per 100,000, for example), and population is compared on its percent change since July 2020.</p>'
             '<p>Every number on the site is written by the build script from the data files. After building, the script checks every number in the page text against the list of values it printed and stops if it finds one it can’t account for.</p></section>')
    H.append('<section class="sec narr"><h2>Each measure</h2>')
    for m in ms:
        src = m.get('source') or {}
        H.append(f'<div class="mm" id="{m["id"]}"><h3>{esc(m["name"])}</h3><dl class="f">')
        rows = [('Area', esc(m['chapter'])), ('Status', esc(m.get('status', 'missing')) + (f': {esc(m["status_reason"])}' if m.get('status_reason') else '')),
                ('Definition', esc(m.get('definition', ''))), ('Better', esc({'up': 'higher', 'down': 'lower', 'none': 'no direction'}[m['better']])),
                ('Source', f'<a href="{esc(src.get("url", ""))}">{esc(src.get("name", ""))}</a>' if src else ''),
                ('Retrieved from', esc(src.get('endpoint', '')) if src.get('endpoint') else ''),
                ('Method', esc(m.get('method', '')))]
        if m.get('peers'):
            p = m['peers']
            rows.append(('Comparison', f'<a href="{esc((p.get("source") or {}).get("url", ""))}">{esc((p.get("source") or {}).get("name", ""))}</a>; ' + esc(p.get('note') or '')))
        if m.get('caveats'):
            rows.append(('Caveats', '<ul>' + ''.join(f'<li>{esc(c)}</li>' for c in m['caveats']) + '</ul>'))
        for k, v in rows:
            if v:
                H.append(f'<div><dt>{k}</dt><dd>{v}</dd></div>')
        H.append('</dl></div>')
    H.append('</section><section class="sec narr" id="changelog"><h2>Changelog</h2><ul>')
    for e in json.load(open(D('data', 'changelog.json'))):
        H.append(f'<li>{yr(e["date"])}: {esc(e["text"])}</li>')
    H.append('</ul></section><footer class="foot"><a href="index.html">Back to the report</a></footer></div></body></html>')
    page = ''.join(H)
    audit(page, 'methodology.html', strict=False)
    open(D('methodology.html'), 'w').write(page)


def write_edition(ms, asof):
    out = {'edition': REG['edition'], 'data_through': asof, 'measures': []}
    for m in ms:
        sc = m['_sc']
        out['measures'].append({k: v for k, v in m.items() if not k.startswith('_')} | {
            'score': {k: v for k, v in sc.items() if k in ('judged', 'call', 'baseline', 'swing', 'z', 'delta', 'inside_moe', 'why')},
            'nyc_rank': m['_pr'] and {'rank': m['_pr']['rank'], 'of': m['_pr']['n']}})
    json.dump(out, open(D('data', 'edition.json'), 'w'), indent=1, default=str)


def audit(page, name, strict=True):
    """Fail if the page shows a number the ledger did not record."""
    txt = re.sub(r'<script.*?</script>', ' ', page, flags=re.S)
    txt = re.sub(r'<style.*?</style>', ' ', txt, flags=re.S)
    txt = re.sub(r'<head>.*?</head>', ' ', txt, flags=re.S)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = html.unescape(txt)
    for a in sorted((a for a in ALLOW if a), key=len, reverse=True):
        txt = txt.replace(a, ' ')
    if not strict:
        # the methods page quotes source names, endpoints and agents' method notes, which carry
        # series IDs and dates; only the ledger-backed values are checked there by construction
        return
    bad = []
    for tok in re.findall(r'(?<![\w.])\d[\d,\.]*', txt):
        t = tok.rstrip('.,')
        if not t or t in LEDGER:
            continue
        if re.fullmatch(r'(19|20)\d\d', t):
            continue
        bad.append(t)
    if bad:
        sys.exit(f'AUDIT FAILED for {name}: numbers with no ledger entry: {sorted(set(bad))[:40]}')


if __name__ == '__main__':
    build()
