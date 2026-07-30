#!/usr/bin/env python3
"""Pull family relationships between IMDb people from Wikidata.

IMDb's bulk files carry no kinship data at all, so the family view is stitched
from Wikidata: pairs of people who both hold an IMDb person ID (P345) and are
linked by father / mother / child / spouse / sibling.

Asking Wikidata for *every* such pair does not work -- the public endpoint caps
queries at 60 seconds and silently truncates the response mid-row. So instead we
drive the query from a batch of IMDb IDs at a time (a VALUES clause hits the
P345 index directly), which returns in well under a second per batch.

The seed list is the most-voted people in the local database, on the theory that
those are the ones anybody actually looks up. Raise it with --top if you want
deeper coverage.

Writes data/family.csv with columns nconst_a, nconst_b, relation_type -- the
shape app/queries.py::_family_source expects.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import queries  # noqa: E402

OUT = ROOT / "data" / "family.csv"
ENDPOINT = "https://query.wikidata.org/sparql"
# Wikidata asks for a descriptive user agent on the public endpoint.
USER_AGENT = "imdb-explorer/1.0 (local research tool; contact josh.greenman@gmail.com)"

BATCH = 300

QUERY = """
SELECT ?a ?b ?rel WHERE {
  VALUES ?a { %s }
  VALUES (?p ?rel) { (wdt:P22 "father") (wdt:P25 "mother") (wdt:P40 "child")
                     (wdt:P26 "spouse") (wdt:P3373 "sibling") }
  ?pa wdt:P345 ?a .
  ?pa ?p ?pb .
  ?pb wdt:P345 ?b .
}
"""


def seed_ids(top: int) -> list[str]:
    """Most-voted people in the local database."""
    rows = queries.conn().execute("""
        SELECT n.nconst
        FROM names n
        JOIN principals p ON p.nconst = n.nconst
        JOIN ratings r    ON r.tconst = p.tconst
        GROUP BY n.nconst
        ORDER BY SUM(r.numVotes) DESC
        LIMIT ?
    """, [top]).fetchall()
    return [r[0] for r in rows]


def ask(batch: list[str]) -> list[tuple[str, str, str]]:
    query = QUERY % " ".join('"%s"' % n for n in batch)
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(url, headers={
        "Accept": "text/csv", "User-Agent": USER_AGENT})

    for attempt in range(4):
        try:
            body = urllib.request.urlopen(req, timeout=120).read().decode()
            if not body.startswith("a,b,rel"):
                raise ValueError(f"unexpected response: {body[:120]!r}")
            # Wikidata sends CRLF and quotes its literals -- let csv handle both
            # rather than splitting by hand and inheriting a stray \r.
            out = []
            for row in csv.reader(body.splitlines()[1:]):
                if len(row) == 3 and row[0].startswith("nm") and row[1].startswith("nm"):
                    out.append((row[0].strip(), row[1].strip(), row[2].strip()))
            return out
        except (OSError, urllib.error.URLError, ValueError) as exc:
            wait = 5 * (attempt + 1)
            print(f"    retry {attempt + 1}/4 after {exc.__class__.__name__}; "
                  f"sleeping {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
    raise SystemExit("FATAL: Wikidata failed four times on the same batch. Aborting.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=60_000,
                    help="how many of the most-voted people to seed (default 60000)")
    args = ap.parse_args()

    ids = seed_ids(args.top)
    if not ids:
        raise SystemExit("FATAL: no people in the database. Build data/imdb.duckdb first.")
    print(f"Seeding from the {len(ids):,} most-voted people\n", flush=True)

    pairs: set[tuple[str, str, str]] = set()
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]
    t0 = time.time()
    for i, batch in enumerate(batches, 1):
        pairs.update(ask(batch))
        if i % 10 == 0 or i == len(batches):
            done = i / len(batches)
            eta = (time.time() - t0) / done * (1 - done)
            print(f"  batch {i}/{len(batches)}  {len(pairs):,} relationships  "
                  f"eta {eta / 60:.1f}m", flush=True)
        time.sleep(0.2)

    if not pairs:
        raise SystemExit("FATAL: Wikidata returned zero relationships. Not writing an empty file.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["nconst_a", "nconst_b", "relation_type"])
        for row in sorted(pairs):
            w.writerow(row)

    print(f"\nWrote {len(pairs):,} relationships to {OUT}")


if __name__ == "__main__":
    main()
