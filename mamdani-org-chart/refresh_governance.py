#!/usr/bin/env python3
"""Snapshot the city's agency file (t3jq-9nkf) into data/governance.json.

This is the only published source for who an office reports to. The build reads
the snapshot rather than the API so the page can be rebuilt offline and so a
change in the city's file shows up as a reviewable diff rather than silently.

Fails loudly on a short read, per house rule: an empty fetch must never look
like a successful one.
"""
import json
import sys
import urllib.request
from pathlib import Path

URL = ("https://data.cityofnewyork.us/resource/t3jq-9nkf.json"
       "?$limit=1000&$order=:id")
MIN_ROWS = 250

with urllib.request.urlopen(URL, timeout=60) as r:
    rows = json.load(r)

if len(rows) < MIN_ROWS:
    sys.exit(f"FAIL: t3jq-9nkf returned {len(rows)} rows, expected at least {MIN_ROWS}. "
             "Not writing the snapshot.")

out = Path(__file__).parent / "data" / "governance.json"
out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
withline = sum(1 for x in rows if x.get("reports_to"))
print(f"wrote {out.name}: {len(rows)} organizations, {withline} with a published reporting line")
