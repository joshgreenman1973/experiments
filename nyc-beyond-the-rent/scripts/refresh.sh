#!/bin/sh
# Refresh every federal and state series, then rebuild data/dashboard.json.
# The hand-collected files in research/ (water rates, rate cases, taxes) are edited by hand.
set -e
cd "$(dirname "$0")/.."
python3 scripts/fetch_bls.py
python3 scripts/fetch_other.py
python3 scripts/parse_eia861m.py
python3 scripts/parse_nyiso.py
python3 scripts/build.py
