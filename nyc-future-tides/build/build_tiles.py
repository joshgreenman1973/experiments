"""Turn the 15 city flood layers into one PMTiles file for the map.
Simplified at 6 ft in state plane (the source DEM is 10 ft), reprojected to WGS84."""
import json, os, subprocess
import geopandas as gpd
from shapely.validation import make_valid
# The city's layers run past the city line into New Jersey; clip to the five boroughs (water areas included, DCP wh2p-dxnf)
NYC_CLIP = make_valid(gpd.read_file(os.path.expanduser('~/.vital-city/flood-dl/boro_water.geojson')).to_crs(2263).geometry.union_all())
D = os.path.expanduser('~/.vital-city/flood-dl/')
HERE = os.path.dirname(os.path.abspath(__file__))
DEC = [2030, 2050, 2080, 2100, 2150]
SRC = [('ht', D+'ht/future_high_tide_sea_level_rise.gdb', 'future_high_tide_{}'),
       ('fp100', D+'fp/future_floodplain_sea_level_rise.gdb', 'future_floodplains_100yr_{}'),
       ('fp500', D+'fp/future_floodplain_sea_level_rise.gdb', 'future_floodplains_500yr_{}')]
tmp = os.path.expanduser('~/.vital-city/flood-dl/layers.geojsonl')
with open(tmp, 'w') as f:
    for kind, path, pat in SRC:
        for d in DEC:
            g = gpd.read_file(path, layer=pat.format(d)).to_crs(2263)
            geom = make_valid(g.geometry.union_all()).intersection(NYC_CLIP).simplify(6, preserve_topology=True)
            geom = make_valid(geom)
            s = gpd.GeoSeries([geom], crs=2263).to_crs(4326).explode(index_parts=False)
            for part in s:
                if part.geom_type not in ('Polygon', 'MultiPolygon'):
                    continue
                f.write(json.dumps({'type': 'Feature', 'properties': {'k': kind, 'd': d},
                                    'geometry': json.loads(gpd.GeoSeries([part]).to_json())['features'][0]['geometry']}) + '\n')
            print(kind, d, flush=True)
out = os.path.join(HERE, '..', 'data', 'flood.pmtiles')
subprocess.run(['tippecanoe', '-q', '-o', out, '--force', '-l', 'flood', '-Z9', '-z14', '--simplification=3',
                '--no-tiny-polygon-reduction', '--detect-shared-borders', '-P', tmp], check=True)
print(os.path.getsize(out) / 1e6, 'MB')
