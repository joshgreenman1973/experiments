"""Build the page data for "Where 311 complaints pile up" from the cached pulls.

Reads build/cache/types/*.csv, build/cache/coords/*.csv and build/cache/meta.json
(written by fetch_311.py) and writes:
  data/summary.json      totals, cutoff steps, category and type mixes, top list
  data/points.json       the top 5% of addresses, for the map
  data/top-5-percent-addresses.csv
  build/checks.json      numbers the methodology page quotes and the checks run

Usage: python3 scripts/build_data.py
"""
import glob, json, math, os, re
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
CACHE = os.path.join(ROOT, 'build', 'cache')
DATA = os.path.join(ROOT, 'data')
TOP_SHARE = 0.05          # the slice the map, list and CSV cover
TYPE_MIN = 40000          # complaint types big enough for the per-type chart

# Address cleanup. 311 addresses come out of the city geocoder already
# standardized; these few abbreviations are the exceptions that split one
# building into two keys (e.g. "34-16 ASTORIA BLVD SOUTH").
ABBREV = [(r' BLVD\b', ' BOULEVARD'), (r' AVE\b', ' AVENUE'), (r' ST$', ' STREET'),
          (r' RD$', ' ROAD'), (r' PL$', ' PLACE'), (r' PKWY\b', ' PARKWAY')]

# A location is a street address: a house number followed by a street name.
# Entries with no house number ("BROADWAY", "CENTRAL PARK", "JFK") and bare
# numbered streets ("1 AVENUE", "85 STREET") cover a stretch of street or a
# whole park or airport, so they are counted with the complaints that have no
# address at all rather than ranked as one location.
ADDR_RE = (r'^\d[0-9A-Z-]*\s+'
           r'(?!(?:AVENUE|STREET|ROAD|PLACE|DRIVE|LANE|TERRACE|COURT|BOULEVARD|PARKWAY)$)\S')

# Categories. Every complaint type not listed falls into "other".
BUILDING = {'HEAT/HOT WATER', 'UNSANITARY CONDITION', 'PLUMBING', 'PAINT/PLASTER', 'DOOR/WINDOW',
            'WATER LEAK', 'GENERAL', 'ELECTRIC', 'FLOORING/STAIRS', 'APPLIANCE', 'SAFETY',
            'OUTSIDE BUILDING', 'ELEVATOR', 'BOILERS', 'INDOOR SEWAGE', 'NON-RESIDENTIAL HEAT'}
VEHICLES = {'ILLEGAL PARKING', 'BLOCKED DRIVEWAY', 'ABANDONED VEHICLE', 'DERELICT VEHICLES',
            'DERELICT VEHICLE'}
STREETS = {'REQUEST LARGE BULKY ITEM COLLECTION', 'STREET CONDITION', 'WATER SYSTEM',
           'STREET LIGHT CONDITION', 'TRAFFIC SIGNAL CONDITION', 'DIRTY CONDITION', 'DIRTY CONDITIONS',
           'DAMAGED TREE', 'MISSED COLLECTION', 'MISSED COLLECTION (ALL MATERIALS)', 'RODENT', 'SEWER',
           'ILLEGAL DUMPING', 'SIDEWALK CONDITION', 'OVERGROWN TREE/BRANCHES', 'GRAFFITI',
           'NEW TREE REQUEST', 'SNOW OR ICE', 'SNOW', 'DEAD/DYING TREE', 'ROOT/SEWER/SIDEWALK CONDITION',
           'SANITATION CONDITION', 'RESIDENTIAL DISPOSAL COMPLAINT', 'COMMERCIAL DISPOSAL COMPLAINT',
           'DEAD ANIMAL', 'CURB CONDITION', 'STREET SWEEPING COMPLAINT', 'STREET SIGN - DAMAGED',
           'STREET SIGN - MISSING', 'STREET SIGN - DANGLING', 'ELECTRONICS WASTE APPOINTMENT',
           'ILLEGAL TREE DAMAGE', 'WATER CONSERVATION', 'HIGHWAY CONDITION', 'WATER MAINTENANCE',
           'LITTER BASKET REQUEST', 'LITTER BASKET COMPLAINT', 'LITTER BASKET / REQUEST',
           'OVERFLOWING LITTER BASKETS', 'SEWER MAINTENANCE', 'STANDING WATER', 'LOT CONDITION',
           'DUMPSTER COMPLAINT', 'WOOD PILE REMAINING', 'VACANT LOT', 'OBSTRUCTION', 'STORM',
           'BROKEN PARKING METER', 'ILLEGAL POSTING', 'SANITATION WORKER OR VEHICLE COMPLAINT',
           'UNSANITARY PIGEON CONDITION', 'BUS STOP SHELTER COMPLAINT'}
ORDER = {'NON-EMERGENCY POLICE MATTER', 'DRUG ACTIVITY', 'ENCAMPMENT', 'HOMELESS PERSON ASSISTANCE',
         'HOMELESS STREET CONDITION', 'ILLEGAL FIREWORKS', 'PANHANDLING', 'DRINKING',
         'URINATING IN PUBLIC', 'VENDOR ENFORCEMENT', 'TRAFFIC', 'ANIMAL-ABUSE',
         'BIKE/ROLLER/SKATE CHRONIC', 'DISORDERLY YOUTH', 'MASS GATHERING COMPLAINT',
         'POSTING ADVERTISEMENT'}
CATS = [  # key, label (order is the drawing order everywhere)
    ('building', 'Apartment and building conditions'),
    ('noise', 'Noise'),
    ('vehicles', 'Parking and vehicles'),
    ('order', 'Police and street order'),
    ('streets', 'Streets, sanitation and trees'),
    ('other', 'Everything else'),
]
CAT_IDX = {k: i for i, (k, _) in enumerate(CATS)}


def category(tkey):
    if tkey.startswith('NOISE'):
        return 'noise'
    for name, s in (('building', BUILDING), ('vehicles', VEHICLES), ('streets', STREETS), ('order', ORDER)):
        if tkey in s:
            return name
    return 'other'


def norm_addr(s):
    s = s.str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
    for p, r in ABBREV:
        s = s.str.replace(p, r, regex=True)
    return s


def load_types():
    frames = []
    for f in sorted(glob.glob(os.path.join(CACHE, 'types', '*.csv'))):
        d = pd.read_csv(f, dtype=str, keep_default_na=False)
        d['n'] = d.n.astype(np.int64)
        d['year'] = int(os.path.basename(f)[:4])
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d['raw'] = d.incident_address.str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
    d['addr'] = norm_addr(d.incident_address)
    d['zip'] = d.incident_zip.str.strip().str[:5]
    d['tkey'] = d.complaint_type.str.strip().str.upper()
    return d[['raw', 'addr', 'zip', 'tkey', 'complaint_type', 'year', 'n']]


def load_coords():
    frames = [pd.read_csv(f, dtype=str, keep_default_na=False)
              for f in sorted(glob.glob(os.path.join(CACHE, 'coords', '*.csv')))]
    c = pd.concat(frames, ignore_index=True)
    c = c[(c.lat != '') & (c.incident_address != '')]
    c['nl'] = c.nl.astype(np.int64)
    c['lat'] = c.lat.astype(float)
    c['lon'] = c.lon.astype(float)
    c['addr'] = norm_addr(c.incident_address)
    c['zip'] = c.incident_zip.str.strip().str[:5]
    # The geocoder occasionally places one address in two spots. Use the point
    # from the quarter with the most located complaints rather than an average,
    # which could land between the two.
    g = (c.sort_values('nl').drop_duplicates(['addr', 'zip'], keep='last')
         .set_index(['addr', 'zip'])[['lat', 'lon']])
    # Spread: how far apart the quarterly points for one address are, in meters.
    c['lat_min'] = c.lat
    c['lat_max'] = c.lat
    c['lon_min'] = c.lon
    c['lon_max'] = c.lon
    sp = c.groupby(['addr', 'zip']).agg(lat_min=('lat_min', 'min'), lat_max=('lat_max', 'max'),
                                        lon_min=('lon_min', 'min'), lon_max=('lon_max', 'max'))
    g['spread_m'] = np.hypot((sp.lat_max - sp.lat_min) * 111000, (sp.lon_max - sp.lon_min) * 84000)
    b = (c[c.borough.isin(['MANHATTAN', 'BRONX', 'BROOKLYN', 'QUEENS', 'STATEN ISLAND'])]
         .groupby(['addr', 'zip', 'borough']).nl.sum().reset_index()
         .sort_values('nl').drop_duplicates(['addr', 'zip'], keep='last')
         .set_index(['addr', 'zip']).borough)
    g['borough'] = b
    return g[['lat', 'lon', 'spread_m', 'borough']]


def steps():
    # Slider stops: every 0.01% up to 0.1%, every 0.1% up to 10%, then every 1% to 100%.
    s = ([round(i / 10000, 5) for i in range(1, 10)] + [round(i / 1000, 4) for i in range(1, 101)]
         + [round(i / 100, 4) for i in range(11, 101)])
    return s


def main():
    meta = json.load(open(os.path.join(CACHE, 'meta.json')))[0]
    d = load_types()
    # One label per complaint type, merging case variants under the most common spelling.
    lab = (d.groupby(['tkey', 'complaint_type']).n.sum().reset_index()
           .sort_values('n').drop_duplicates('tkey', keep='last').set_index('tkey').complaint_type)
    TOT = int(d.n.sum())
    checks = {'rows_in_feed': int(meta['n']), 'rows_summed': TOT, 'newest_record': meta['newest']}
    assert TOT == int(meta['n']), f'quarterly sums {TOT} != feed count {meta["n"]}'

    placed = d.addr.str.match(ADDR_RE)
    blank = int(d.loc[d.addr == '', 'n'].sum())
    named = int(d.loc[~placed & (d.addr != ''), 'n'].sum())
    unplaced = blank + named
    top_named = (d[~placed & (d.addr != '')].groupby(['addr', 'zip']).n.sum()
                 .sort_values(ascending=False).head(25))
    checks['named_entries'] = int(d[~placed & (d.addr != '')].groupby(['addr', 'zip']).ngroups)
    checks['top_named'] = [[a, z, int(n)] for (a, z), n in top_named.items()]
    da = d[placed]
    at = da.groupby(['addr', 'zip']).n.sum().reset_index()
    at = at.sort_values(['n', 'addr', 'zip'], ascending=[False, True, True]).reset_index(drop=True)
    at['rank'] = np.arange(1, len(at) + 1)
    N = len(at)
    cum = at.n.cumsum().to_numpy()
    counts = at.n.to_numpy()

    # Per-type and per-category cumulative counts along the address ranking.
    da = da.merge(at[['addr', 'zip', 'rank']], on=['addr', 'zip'])
    da['cat'] = da.tkey.map(category)
    type_tot = d.groupby('tkey').n.sum().sort_values(ascending=False)
    big = [t for t, v in type_tot.items() if v >= TYPE_MIN]
    ST = steps()
    ks = [int(round(N * p)) for p in ST]

    def cum_at(frame):
        s = frame.groupby('rank').n.sum()
        r = s.index.to_numpy()
        c = s.cumsum().to_numpy()
        idx = np.searchsorted(r, ks, side='right') - 1
        return [int(c[i]) if i >= 0 else 0 for i in idx]

    cat_cum = {k: cum_at(da[da.cat == k]) for k, _ in CATS}
    type_cum = {t: cum_at(da[da.tkey == t]) for t in big}
    cat_tot = d.assign(cat=d.tkey.map(category)).groupby('cat').n.sum()
    cat_blank = d[~placed].assign(cat=lambda x: x.tkey.map(category)).groupby('cat').n.sum()

    # The top slice and its details.
    K = int(round(N * TOP_SHARE))
    top = at.head(K).copy()
    coords = load_coords()
    top = top.join(coords, on=['addr', 'zip'])
    tt = (da[da['rank'] <= K].groupby(['rank', 'tkey']).n.sum().reset_index()
          .sort_values(['rank', 'n'], ascending=[True, False]))
    tt['pos'] = tt.groupby('rank').cumcount()
    ntypes = tt.groupby('rank').size()
    t3 = tt[tt.pos < 3]
    yrs = sorted(d.year.unique())
    yy = (da[da['rank'] <= K].groupby(['rank', 'year']).n.sum().unstack(fill_value=0)
          .reindex(columns=yrs, fill_value=0))
    cat_by_rank = (da[da['rank'] <= K].groupby(['rank', 'cat']).n.sum().unstack(fill_value=0))

    # Index the complaint types the points refer to.
    tlist = sorted(set(t3.tkey) | set(big), key=lambda t: -type_tot[t])
    tix = {t: i for i, t in enumerate(tlist)}

    pts = {'addr': [], 'zip': [], 'boro': [], 'lat': [], 'lon': [], 'n': [], 'cat': [], 'types': [],
           'years': [], 'ntypes': []}
    boro_code = {'MANHATTAN': 'M', 'BRONX': 'X', 'BROOKLYN': 'K', 'QUEENS': 'Q', 'STATEN ISLAND': 'R'}
    t3g = {r: list(zip(g.tkey, g.n)) for r, g in t3.groupby('rank')}
    missing_xy = 0
    for r in top.itertuples():
        if not (isinstance(r.lat, float) and math.isfinite(r.lat)):
            missing_xy += 1
            lat = lon = None
        else:
            lat, lon = int(round(r.lat * 1e5)), int(round(r.lon * 1e5))  # degrees x 100,000
        pts['addr'].append(r.addr)
        pts['zip'].append(r.zip)
        pts['boro'].append(boro_code.get(r.borough, ''))
        pts['lat'].append(lat)
        pts['lon'].append(lon)
        pts['n'].append(int(r.n))
        cb = cat_by_rank.loc[r.rank]
        pts['cat'].append(CAT_IDX[cb.idxmax()])
        pts['types'].append([v for tk, n in t3g[r.rank] for v in (tix[tk], int(n))])
        pts['years'].append([int(v) for v in yy.loc[r.rank]])
        pts['ntypes'].append(int(ntypes[r.rank]))
    checks['top_missing_coords'] = missing_xy
    spread = top.spread_m.dropna()
    checks['top_coord_spread_over_100m'] = int((spread > 100).sum())

    labels = [lab[t] for t in tlist]
    with open(os.path.join(DATA, 'points.json'), 'w') as f:
        json.dump({'ylabels': [int(y) for y in yrs], 'tlabels': labels, 'cats': [k for k, _ in CATS], **pts},
                  f, separators=(',', ':'))

    # Summary for the charts.
    summary = {
        'total': TOT, 'unplaced': unplaced, 'blank': blank, 'named': named, 'locations': N,
        'newest': meta['newest'],
        'first': '2020-01-01', 'top_k': K, 'top_share': TOP_SHARE,
        'cats': [{'key': k, 'label': l, 'total': int(cat_tot.get(k, 0)), 'unplaced': int(cat_blank.get(k, 0))}
                 for k, l in CATS],
        'steps': ST, 'k': ks, 'cum': [int(cum[k - 1]) for k in ks], 'min': [int(counts[k - 1]) for k in ks],
        'cat_cum': [cat_cum[k] for k, _ in CATS],
        'types': [{'label': lab[t], 'cat': CAT_IDX[category(t)], 'total': int(type_tot[t]),
                   'cum': type_cum[t]} for t in big],
        'median': float(np.median(counts)), 'one_complaint': int((counts == 1).sum()),
        'curve': {'k': [], 'cum': []},
    }
    # A thinned Lorenz curve for the small inset.
    kk = sorted(set([1] + [int(round(N * i / 1000)) for i in range(1, 1001)]))
    summary['curve'] = {'k': kk, 'cum': [int(cum[k - 1]) for k in kk]}
    with open(os.path.join(DATA, 'summary.json'), 'w') as f:
        json.dump(summary, f, separators=(',', ':'))

    # Download.
    out = pd.DataFrame({'rank': top['rank'], 'address': top.addr, 'zip': top.zip,
                        'borough': top.borough.fillna('').str.title(),
                        'latitude': top.lat.round(5), 'longitude': top.lon.round(5),
                        'complaints': top.n})
    for i in range(3):
        out[f'type_{i + 1}'] = [lab[t3g[r][i][0]] if len(t3g[r]) > i else '' for r in top['rank']]
        out[f'type_{i + 1}_complaints'] = [t3g[r][i][1] if len(t3g[r]) > i else '' for r in top['rank']]
    for y in yrs:
        out[f'complaints_{y}'] = yy[y].to_numpy()
    out.to_csv(os.path.join(DATA, 'top-5-percent-addresses.csv'), index=False)

    # Numbers the methodology page quotes.
    def share_at(p):
        k = int(round(N * p))
        return {'k': k, 'min': int(counts[k - 1]), 'cum': int(cum[k - 1]), 'share': cum[k - 1] / TOT}
    checks.update({
        'total': TOT, 'blank': blank, 'named': named, 'unplaced': unplaced, 'locations': N, 'top_k': K,
        'median': float(np.median(counts)), 'one_complaint': int((counts == 1).sum()),
        'at': {str(p): share_at(p) for p in (0.0001, 0.001, 0.01, 0.05, 0.10, 0.20, 0.50)},
        'top10_share': int(cum[9]) / TOT, 'top100_share': int(cum[99]) / TOT,
        'top5_without_top100': (cum[K - 1] - cum[99]) / (TOT - cum[99]),
        'types_total': int(len(type_tot)), 'types_big': len(big),
        'cat_share_top5': {k: cat_cum[k][ST.index(TOP_SHARE)] / cum[K - 1] for k, _ in CATS},
        'cat_share_rest': {k: (cat_tot.get(k, 0) - cat_blank.get(k, 0) - cat_cum[k][ST.index(TOP_SHARE)])
                           / (TOT - unplaced - cum[K - 1]) for k, _ in CATS},
        'abbrev_rewritten_complaints': int(d.loc[d.raw != d.addr, 'n'].sum()),
        'abbrev_rewritten_addresses': int(d.loc[d.raw != d.addr, 'raw'].nunique()),
        'points_bytes': os.path.getsize(os.path.join(DATA, 'points.json')),
    })
    with open(os.path.join(ROOT, 'build', 'checks.json'), 'w') as f:
        json.dump(checks, f, indent=1)
    print(json.dumps({k: checks[k] for k in ('total', 'blank', 'named', 'locations', 'top_k', 'top_missing_coords',
                                              'top_coord_spread_over_100m', 'points_bytes')}, indent=1))
    print(json.dumps(checks['at'], indent=1))


if __name__ == '__main__':
    main()
