"""Neighbourhood Tabulation Areas built by dissolving NYC Planning's shoreline-clipped 2010 census tracts.
Usage: python nta_from_tracts.py nyct2010.shp OUT.geojson"""
import sys, geopandas as gpd
t = gpd.read_file(sys.argv[1])
n = t.dissolve(by=["NTACode", "NTAName", "BoroName"], as_index=False)[["NTACode", "NTAName", "BoroName", "geometry"]]
n.to_crs(4326).to_file(sys.argv[2], driver="GeoJSON")
print(len(n), n.NTAName.head().tolist())
