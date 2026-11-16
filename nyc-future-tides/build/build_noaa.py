"""NOAA sea-level rise layers, 0 to 10 feet above today's high tide, for the slider.

Inputs (in ~/.vital-city/flood-dl/):
  noaa/x/NY_Metro_slr_final_dist.gdb  NOAA Office for Coastal Management, Sea Level Rise Viewer data,
        https://coast.noaa.gov/htdata/Inundation/SLR/SLRdata/NY/NY_Metro_slr_data_dist.zip
        Layers NY_M_slr_{0..10}ft: land and water connected to the ocean that sits below
        mean higher high water (MHHW, 1983-2001 tidal epoch) plus N feet.
        Layers NY_M_low_{0..10}ft: low spots below that level with no connection to the water.
  boro_land_gthc-hcne.geojson  Borough Boundaries, shoreline clipped (DCP, NYC Open Data gthc-hcne)
  pluto/p_*.csv                PLUTO 26v2 (same files as build_lots.py)
Outputs:
  data/noaa.json               area, homes and lots at each foot, citywide and by borough
  data/noaa_lots/<boro>.json   BBL -> first foot (0-10) at which the lot center is under water
  ~/.vital-city/flood-dl/noaa_layers.geojsonl  (for build_noaa_tiles)
Counting rule is the same as build_lots.py: a lot counts when its PLUTO center point is inside.
"""
import glob, json, os, subprocess
import pandas as pd, geopandas as gpd
from shapely.validation import make_valid

D = os.path.expanduser('~/.vital-city/flood-dl/')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data')
GDB = D + 'noaa/x/NY_Metro_slr_final_dist.gdb'
FEET = list(range(11))
LAND = make_valid(gpd.read_file(D + 'boro_land_gthc-hcne.geojson').to_crs(2263).geometry.union_all())
BORO = gpd.read_file(D + 'boro_land_gthc-hcne.geojson').to_crs(2263)
print('land sq mi', round(LAND.area / 27878400, 1))

lots = pd.concat([pd.read_csv(f, dtype={'bbl': str}) for f in sorted(glob.glob(D + 'pluto/p_*.csv'))])
lots['bbl'] = lots['bbl'].str.split('.').str[0]
lots = lots.drop_duplicates('bbl').reset_index(drop=True).dropna(subset=['xcoord', 'ycoord']).reset_index(drop=True)
lots['unitsres'] = lots['unitsres'].fillna(0).astype(int)
g = gpd.GeoDataFrame(lots, geometry=gpd.points_from_xy(lots.xcoord, lots.ycoord), crs=2263)
print('lots with coords', len(g), 'units', int(g.unitsres.sum()))

def hits(geom):
    poly = gpd.GeoDataFrame(geometry=[geom], crs=2263)
    return g.index.isin(gpd.sjoin(g[['geometry']], poly, predicate='within', how='inner').index)

res = {'feet': FEET, 'units_total': int(g.unitsres.sum()), 'land_sqmi': round(LAND.area / 27878400, 1),
       'sqmi': [], 'units': [], 'lots': [], 'low_units': [], 'low_sqmi': [], 'by_boro': {}}
tmp = D + 'noaa_layers.geojsonl'
first = pd.Series(-1, index=g.index)
with open(tmp, 'w') as fh:
    for ft in FEET:
        con = make_valid(make_valid(gpd.read_file(GDB, layer=f'NY_M_slr_{ft}ft').to_crs(2263).geometry.union_all()).intersection(LAND))
        low = make_valid(make_valid(gpd.read_file(GDB, layer=f'NY_M_low_{ft}ft').to_crs(2263).geometry.union_all()).intersection(LAND))
        low = make_valid(low.difference(con))
        h, hl = hits(con), hits(low)
        first[(first < 0) & h] = ft
        g[f'f{ft}'] = h
        res['sqmi'].append(round(con.area / 27878400, 2)); res['low_sqmi'].append(round(low.area / 27878400, 2))
        res['units'].append(int(g.unitsres[h].sum())); res['lots'].append(int(h.sum()))
        res['low_units'].append(int(g.unitsres[hl & ~h].sum()))
        print(ft, 'ft', res['sqmi'][-1], 'sq mi', res['units'][-1], 'homes', res['lots'][-1], 'lots; low-lying', res['low_units'][-1], flush=True)
        s = gpd.GeoSeries([make_valid(con.simplify(6, preserve_topology=True))], crs=2263).to_crs(4326).explode(index_parts=False)
        for part in s:
            if part.geom_type in ('Polygon', 'MultiPolygon'):
                fh.write(json.dumps({'type': 'Feature', 'properties': {'f': ft},
                                     'geometry': json.loads(gpd.GeoSeries([part]).to_json())['features'][0]['geometry']}) + '\n')

# Nesting check: a lot under water at N feet should stay under at N+1
bad = sum(int((g[f'f{a}'] & ~g[f'f{a+1}']).sum()) for a in FEET[:-1])
print('non-nesting lot hits', bad)
res['non_nesting_lot_hits'] = bad
for b, s in g.groupby('borough'):
    res['by_boro'][b] = [int(s.unitsres[s[f'f{ft}']].sum()) for ft in FEET]
json.dump(res, open(os.path.join(OUT, 'noaa.json'), 'w'), separators=(',', ':'))

os.makedirs(os.path.join(OUT, 'noaa_lots'), exist_ok=True)
g['first'] = first
t = g[g['first'] >= 0]
for b, s in t.groupby(t.bbl.str[0]):
    json.dump({r.bbl: int(r.first) for r in s.itertuples()}, open(os.path.join(OUT, 'noaa_lots', f'{b}.json'), 'w'), separators=(',', ':'))
print('lots under water at some level', len(t))

out = os.path.join(OUT, 'noaa.pmtiles')
subprocess.run(['tippecanoe', '-q', '-o', out, '--force', '-l', 'noaa', '-Z9', '-z14', '--simplification=3',
                '--no-tiny-polygon-reduction', '--detect-shared-borders', '-P', tmp], check=True)
print(os.path.getsize(out) / 1e6, 'MB')
