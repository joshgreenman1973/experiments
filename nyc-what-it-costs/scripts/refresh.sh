#!/bin/sh
# Monthly refresh: pull, rebuild, verify. Stops at the first failure.
set -e
cd "$(dirname "$0")/.."
python3 scripts/fetch_bls.py
python3 scripts/fetch_other.py
python3 scripts/extract_weights.py
python3 scripts/build.py
python3 scripts/verify.py
