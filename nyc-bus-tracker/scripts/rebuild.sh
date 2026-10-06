#!/usr/bin/env bash
# Rebuild everything derived from the daily files, in dependency order.
# Called by the daily processor and the backfill workflow; safe to run by hand
# from the repo root or from nyc-bus-tracker/. Any step that fails stops the
# run, so a broken upstream never publishes half-updated files.
set -euo pipefail
cd "$(dirname "$0")/.."

node collector/rollup.js          # summaries, health, per-route history files
python3 scripts/build_events.py   # holidays, weather, outages, method changes
node scripts/export_csv.mjs       # CSV downloads + data dictionary
