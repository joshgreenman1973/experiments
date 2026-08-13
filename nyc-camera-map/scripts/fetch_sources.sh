#!/bin/sh
# Fetch the upstream inputs the build scripts read from raw/.
# Everything here is public and unauthenticated.
set -e
cd "$(dirname "$0")/.."
mkdir -p raw

echo "NYC DOT traffic camera feed"
curl -sfL --retry 3 -H 'User-Agent: Mozilla/5.0' \
  'https://webcams.nyctmc.org/api/cameras' -o raw/dot_traffic_cameras.json

echo "Borough boundaries"
curl -sfL --retry 3 \
  'https://data.cityofnewyork.us/resource/gthc-hcne.geojson?$limit=10' \
  -o raw/borough_boundaries.geojson

echo "Street centerline (122k segments, a few minutes)"
python3 scripts/fetch_centerline.py

echo "OpenStreetMap surveillance devices"
curl -sfL --retry 3 -X POST 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:170];
(
 node["man_made"="surveillance"](40.47,-74.30,40.93,-73.68);
 way["man_made"="surveillance"](40.47,-74.30,40.93,-73.68);
 node["highway"="speed_camera"](40.47,-74.30,40.93,-73.68);
);
out center tags;' -o raw/osm_surveillance.json

echo "Amnesty International Decode Surveillance NYC, 2021"
curl -sfL --retry 3 \
  'https://raw.githubusercontent.com/amnesty-crisis-evidence-lab/decode-surveillance-nyc/main/data/counts_per_intersections.csv' \
  -o raw/amnesty_counts_per_intersections.csv

echo "Camera tickets (fiscal 2026, grouped by location)"
python3 scripts/fetch_violations.py

echo "done"
