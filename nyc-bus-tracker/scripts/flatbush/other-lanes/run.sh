#!/bin/sh
# Rebuild everything in order. Downloads are slow (minutes per route); skip step 1 if mta/*.csv exist.
set -e
cd "$(dirname "$0")"
# 1. MTA Bus Route Segment Speeds (data.ny.gov 58t6-89vi + kufs-yh3x), weekdays, one CSV per route.
#    Routes already in ../mta are reused (B41 B45 B67 B103 M1 M2 M3 M4 M101 M102 M103 BX12 BX12+ BX36).
# python3 mta_seg.py Q66 QM2 QM20 QM32 BX28 BX38 M98 M15 M15+ M96 M106 BX3 Q1 Q2 Q3 Q17 Q36 Q43 Q76 Q77 Q82 QM68 \
#   X27 X28 X37 X38 SIM4C SIM33C BXM6 BXM7 BXM8 BXM9 BXM10 BXM18 QM63 QM64 Q70+
# 2. GTFS: ../gtfs/{b,m,bx} plus gtfs/{q,busco,si} from https://rrgtfsfeeds.s3.amazonaws.com/gtfs_{q,busco,si}.zip
python3 build_corridors.py     # -> corridors.json, corridors.geojson
python3 build_segments.py      # -> segments.csv, segments.geojson
python3 analyze.py             # -> results.json
python3 make_table.py         # -> table.md
