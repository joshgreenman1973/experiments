#!/usr/bin/env python3
"""Snapshot the city's agency file (t3jq-9nkf) into data/governance.json.

This is the only published source for what an office reports to. The build reads
the snapshot rather than the API so the page can be rebuilt offline and so a
change in the city's file shows up as a reviewable diff rather than silently.

Two things it refuses to do:

  * write a short read, so an empty or truncated fetch fails loudly instead of
    quietly emptying the chart;
  * write at all when the content is unchanged. The dataset restamps itself
    without changing a row - it did exactly that on 2026-08-06, a week after the
    previous snapshot, with all 306 rows and all 132 reporting lines identical.
    Comparing timestamps produces phantom updates; compare the content.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://data.cityofnewyork.us/resource/t3jq-9nkf.json?$limit=1000&$order=:id"
MIN_ROWS = 250
OUT = Path(__file__).parent / "data" / "governance.json"


def signature(rows):
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


with urllib.request.urlopen(URL, timeout=60) as r:
    rows = json.load(r)

if len(rows) < MIN_ROWS:
    sys.exit(f"FAIL: t3jq-9nkf returned {len(rows)} rows, expected at least {MIN_ROWS}. "
             "Not writing the snapshot.")

lines = sum(1 for x in rows if x.get("reports_to"))
new = json.dumps(rows, indent=1, ensure_ascii=False)

if OUT.exists() and signature(json.loads(OUT.read_text())) == signature(rows):
    print(f"unchanged: {len(rows)} organizations, {lines} with a published reporting line. "
          "Nothing written.")
    sys.exit(0)

OUT.write_text(new)
print(f"UPDATED {OUT.name}: {len(rows)} organizations, {lines} with a published reporting line")
