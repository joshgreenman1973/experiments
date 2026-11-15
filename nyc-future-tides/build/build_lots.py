"""Match every NYC tax lot to the city's future high-tide and floodplain layers.

Inputs (downloaded by fetch.sh into ~/.vital-city/flood-dl/):
  fp/future_floodplain_sea_level_rise.gdb   NYC Open Data 29fz-v4rp (MOCEJ, NPCC4 90th pct)
  ht/future_high_tide_sea_level_rise.gdb     NYC Open Data xbxf-ev5m
  pluto/p_*.csv                              PLUTO 64uk-42ks (lot centroids, units)
  nta.geojson                                2020 NTAs 9nt8-h7nd (DCP, shoreline clipped)
Outputs: data/summary.json, data/lots/<boro>.json (BBL lookup for the address search)
"""
import glob, json, os
import pandas as pd, geopandas as gpd
from shapely.validation import make_valid
# The city's layers run past the city line into New Jersey; clip to the five boroughs (water areas included, DCP wh2p-dxnf)
NYC_CLIP = make_valid(gpd.read_file(os.path.expanduser('~/.vital-city/flood-dl/boro_water.geojson')).to_crs(2263).geometry.union_all())

D = os.path.expanduser('~/.vital-city/flood-dl/')
OUT = os.path.join(os.path.dirname(__file__), '..', 'data')
DEC = [2030, 2050, 2080, 2100, 2150]
LAYERS = {('ht', d): (D+'ht/future_high_tide_sea_level_rise.gdb', f'future_high_tide_{d}') for d in DEC}
LAYERS.update({('fp100', d): (D+'fp/future_floodplain_sea_level_rise.gdb', f'future_floodplains_100yr_{d}') for d in DEC})
LAYERS.update({('fp500', d): (D+'fp/future_floodplain_sea_level_rise.gdb', f'future_floodplains_500yr_{d}') for d in DEC})

lots = pd.concat([pd.read_csv(f, dtype={'bbl': str}) for f in sorted(glob.glob(D+'pluto/p_*.csv'))])
lots['bbl'] = lots['bbl'].str.split('.').str[0]
lots = lots.drop_duplicates('bbl').reset_index(drop=True)
n_all = len(lots)
lots = lots.dropna(subset=['xcoord', 'ycoord'])
print('lots', n_all, 'with coords', len(lots))
for c in ['unitsres', 'unitstotal']:
    lots[c] = lots[c].fillna(0).astype(int)
g = gpd.GeoDataFrame(lots, geometry=gpd.points_from_xy(lots.xcoord, lots.ycoord), crs=2263)

areas = {}
for (kind, dec), (path, layer) in LAYERS.items():
    lay = gpd.read_file(path, layer=layer).to_crs(2263)
    geom = make_valid(lay.geometry.union_all()).intersection(NYC_CLIP)
    areas[f'{kind}_{dec}'] = round(geom.area / 27878400, 2)
    poly = gpd.GeoDataFrame(geometry=[geom], crs=2263)
    hit = gpd.sjoin(g[['geometry']], poly, predicate='within', how='inner').index
    g[f'{kind}_{dec}'] = g.index.isin(hit)
    print(kind, dec, areas[f'{kind}_{dec}'], 'sq mi', int(g[f'{kind}_{dec}'].sum()), 'lots')

def first(row, kind):
    for d in DEC:
        if row[f'{kind}_{d}']:
            return d
    return 0

for kind in ['ht', 'fp100', 'fp500']:
    cols = [f'{kind}_{d}' for d in DEC]
    arr = g[cols].values
    g[kind] = [next((DEC[i] for i, v in enumerate(r) if v), 0) for r in arr]

nta = gpd.read_file(D+'nta.geojson').to_crs(2263)[['nta2020', 'ntaname', 'boroname', 'ntatype', 'geometry']]
g = gpd.sjoin(g, nta, predicate='within', how='left').drop(columns='index_right')

# Sanity: layers should nest (a lot reached in 2050 stays reached later)
for kind in ['ht', 'fp100', 'fp500']:
    bad = 0
    for a, b in zip(DEC, DEC[1:]):
        bad += int((g[f'{kind}_{a}'] & ~g[f'{kind}_{b}']).sum())
    print('non-nesting lot hits', kind, bad)

summary = {'pluto_version': str(g['version'].iloc[0]), 'lots_total': int(n_all), 'lots_geocoded': int(len(g)),
           'units_total': int(g.unitsres.sum()), 'area_sqmi': areas, 'decades': DEC, 'by_decade': {}, 'by_boro': {}, 'nta': []}
for kind in ['ht', 'fp100', 'fp500']:
    summary['by_decade'][kind] = []
    for d in DEC:
        s = g[g[f'{kind}_{d}']]
        summary['by_decade'][kind].append({'decade': d, 'lots': int(len(s)), 'units': int(s.unitsres.sum()),
            'res_lots': int((s.unitsres > 0).sum())})
    summary['by_boro'][kind] = {}
    for b, s in g.groupby('borough'):
        summary['by_boro'][kind][b] = [int(s[s[f'{kind}_{d}']].unitsres.sum()) for d in DEC]

for (code, name, boro, typ), s in g.groupby(['nta2020', 'ntaname', 'boroname', 'ntatype']):
    row = {'nta': code, 'name': name, 'boro': boro, 'units': int(s.unitsres.sum()), 'lots': int(len(s))}
    for kind in ['ht', 'fp100']:
        row[kind] = [int(s[s[f'{kind}_{d}']].unitsres.sum()) for d in DEC]
        row[kind + '_lots'] = [int(s[f'{kind}_{d}'].sum()) for d in DEC]
    summary['nta'].append(row)

json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), separators=(',', ':'))

# BBL lookup for the address search: only lots touched by any layer.
# value = [first high-tide decade, first 100-yr decade, first 500-yr decade] as decade index+1 (0 = never)
os.makedirs(os.path.join(OUT, 'lots'), exist_ok=True)
idx = {d: i + 1 for i, d in enumerate(DEC)}; idx[0] = 0
touched = g[(g.ht > 0) | (g.fp100 > 0) | (g.fp500 > 0)]
for b, s in touched.groupby(touched.bbl.str[0]):
    m = {r.bbl: idx[r.ht] * 100 + idx[r.fp100] * 10 + idx[r.fp500] for r in s.itertuples()}
    json.dump(m, open(os.path.join(OUT, 'lots', f'{b}.json'), 'w'), separators=(',', ':'))
    print('boro', b, len(m))
print('touched lots', len(touched))
