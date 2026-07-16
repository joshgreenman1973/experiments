#!/usr/bin/env python3
"""Probe candidate MTA GTFS static feed URLs and report which actually resolve.

We do not guess: every URL that ends up in the build is one that returned 200
with a real ZIP payload here first.
"""
import urllib.request
import urllib.error

CANDIDATES = [
    # Current MTA S3-hosted static feeds
    ("subway", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"),
    ("bus_bronx", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip"),
    ("bus_brooklyn", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip"),
    ("bus_manhattan", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip"),
    ("bus_queens", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip"),
    ("bus_statenisland", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip"),
    ("bus_busco", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip"),
    # Legacy web.mta.info paths, in case the S3 ones have moved
    ("subway_legacy", "http://web.mta.info/developers/data/nyct/subway/google_transit.zip"),
    ("bus_bronx_legacy", "http://web.mta.info/developers/data/nyct/bus/google_transit_bronx.zip"),
    ("bus_brooklyn_legacy", "http://web.mta.info/developers/data/nyct/bus/google_transit_brooklyn.zip"),
    ("bus_manhattan_legacy", "http://web.mta.info/developers/data/nyct/bus/google_transit_manhattan.zip"),
    ("bus_queens_legacy", "http://web.mta.info/developers/data/nyct/bus/google_transit_queens.zip"),
    ("bus_si_legacy", "http://web.mta.info/developers/data/nyct/bus/google_transit_staten_island.zip"),
    ("busco_legacy", "http://web.mta.info/developers/data/busco/google_transit.zip"),
]

def probe(name, url):
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "45-minute-city/1.0 (data pipeline)")
    req.add_header("Range", "bytes=0-3")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            head = r.read(4)
            size = r.headers.get("Content-Range") or r.headers.get("Content-Length")
            is_zip = head[:2] == b"PK"
            print(f"  {'OK ' if is_zip else '??'} {name:24s} {r.status} zip={is_zip} size={size}")
            return is_zip
    except urllib.error.HTTPError as e:
        print(f"  XX {name:24s} HTTP {e.code}")
    except Exception as e:
        print(f"  XX {name:24s} {type(e).__name__}: {e}")
    return False

if __name__ == "__main__":
    print("Probing MTA GTFS static feeds\n")
    good = [(n, u) for n, u in CANDIDATES if probe(n, u)]
    print(f"\n{len(good)}/{len(CANDIDATES)} resolved:")
    for n, u in good:
        print(f"  {n}: {u}")
