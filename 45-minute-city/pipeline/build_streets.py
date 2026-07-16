#!/usr/bin/env python3
"""Build a routable pedestrian/bicycle street graph for New York City from the
Department of City Planning's Centerline (CSCL) dataset.

This replaces the old build's invented GRID_FACTOR = 1.4 detour constant.
Walking and biking are routed on the actual street network instead.

Source: NYC Open Data, "Centerline" (inkn-q76z)
        https://data.cityofnewyork.us/resource/inkn-q76z.json

rw_type codes (DCP):
  1 Street        2 Highway      3 Bridge       4 Tunnel     5 Boardwalk
  6 Path/Trail    7 Step Street  8 Driveway     9 Ramp      10 Alley
 11 Unknown      12 Non-physical 13 U-turn      14 Ferry route

Walk: streets, bridges, boardwalks, paths, step streets, alleys.
Bike: same minus step streets (stairs) — bikes must be carried.
Both exclude highways, ramps, ferry routes, non-physical segments and driveways.
"""
import json
import math
import os
import struct
import sys
import urllib.parse
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "out")
BASE = "https://data.cityofnewyork.us/resource/inkn-q76z.json"

WALK_TYPES = {"1", "3", "5", "6", "7", "10"}
BIKE_TYPES = {"1", "3", "5", "6", "10"}  # no step streets
FETCH_TYPES = WALK_TYPES | BIKE_TYPES

SNAP = 1e5  # ~1m grid for welding segment endpoints into shared nodes


def log(m):
    print(m, flush=True)


def fetch_all():
    path = os.path.join(CACHE, "cscl.json")
    if os.path.exists(path) and os.path.getsize(path) > 10_000_000:
        log(f"  cached cscl.json ({os.path.getsize(path)/1e6:.1f} MB)")
        return json.load(open(path))
    os.makedirs(CACHE, exist_ok=True)
    rows, offset, limit = [], 0, 50000
    while True:
        q = {
            "$select": "the_geom,rw_type,physicalid,segmentlength,full_street_name",
            "$where": "rw_type in('" + "','".join(sorted(FETCH_TYPES)) + "') AND status='2'",
            "$limit": str(limit),
            "$offset": str(offset),
        }
        url = BASE + "?" + urllib.parse.urlencode(q)
        log(f"  fetching offset {offset} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "45-minute-city/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    json.dump(rows, open(path, "w"))
    log(f"  fetched {len(rows):,} segments -> {os.path.getsize(path)/1e6:.1f} MB")
    return rows


def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def main():
    os.makedirs(OUT, exist_ok=True)
    log("Fetching NYC Centerline")
    rows = fetch_all()
    log(f"  {len(rows):,} segments")

    node_id = {}
    nodes = []

    def nid(lon, lat):
        k = (round(lon * SNAP), round(lat * SNAP))
        i = node_id.get(k)
        if i is None:
            i = len(nodes)
            node_id[k] = i
            nodes.append((lat, lon))
        return i

    edges = []  # (a, b, meters, walk, bike)
    skipped = 0
    for r in rows:
        g = r.get("the_geom")
        rw = r.get("rw_type")
        if not g or rw not in FETCH_TYPES:
            skipped += 1
            continue
        walk = 1 if rw in WALK_TYPES else 0
        bike = 1 if rw in BIKE_TYPES else 0
        if not (walk or bike):
            continue
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for line in lines:
            for i in range(len(line) - 1):
                lon1, lat1 = line[i][0], line[i][1]
                lon2, lat2 = line[i + 1][0], line[i + 1][1]
                d = hav(lat1, lon1, lat2, lon2)
                if d < 0.5:
                    continue
                a, b = nid(lon1, lat1), nid(lon2, lat2)
                if a == b:
                    continue
                edges.append((a, b, d, walk, bike))

    log(f"  nodes: {len(nodes):,}  edges: {len(edges):,}  (skipped {skipped})")

    # Drop everything not connected to the largest component: islands of stray
    # geometry would otherwise make some origins unroutable.
    adj = defaultdict(list)
    for i, (a, b, d, w, bk) in enumerate(edges):
        adj[a].append(b)
        adj[b].append(a)
    seen = set()
    best = []
    for start in range(len(nodes)):
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            n = stack.pop()
            comp.append(n)
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        if len(comp) > len(best):
            best = comp
    keep = set(best)
    log(f"  largest connected component: {len(keep):,} nodes ({len(keep)/len(nodes)*100:.1f}%)")

    remap = {}
    out_nodes = []
    for n in sorted(keep):
        remap[n] = len(out_nodes)
        out_nodes.append(nodes[n])
    out_edges = [
        (remap[a], remap[b], d, w, bk)
        for (a, b, d, w, bk) in edges
        if a in keep and b in keep
    ]
    log(f"  kept edges: {len(out_edges):,}")

    # ---- binary payload: compact enough to ship to a browser
    # nodes.bin : int32 lat*1e6, int32 lon*1e6
    nb = bytearray()
    for lat, lon in out_nodes:
        nb += struct.pack("<ii", int(round(lat * 1e6)), int(round(lon * 1e6)))
    p = os.path.join(OUT, "street_nodes.bin")
    open(p, "wb").write(nb)
    log(f"  wrote {p} ({len(nb)/1e6:.2f} MB)")

    # edges.bin : uint32 a, uint32 b, uint16 decimeters (capped), uint8 flags
    eb = bytearray()
    for a, b, d, w, bk in out_edges:
        dm = min(65535, int(round(d * 10)))
        eb += struct.pack("<IIHB", a, b, dm, (w << 0) | (bk << 1))
    p = os.path.join(OUT, "street_edges.bin")
    open(p, "wb").write(eb)
    log(f"  wrote {p} ({len(eb)/1e6:.2f} MB)")

    meta = {
        "source": "NYC Open Data Centerline (inkn-q76z)",
        "nodes": len(out_nodes),
        "edges": len(out_edges),
        "walk_types": sorted(WALK_TYPES),
        "bike_types": sorted(BIKE_TYPES),
        "node_format": "int32 lat*1e6, int32 lon*1e6",
        "edge_format": "uint32 a, uint32 b, uint16 decimeters, uint8 flags(bit0=walk,bit1=bike)",
    }
    json.dump(meta, open(os.path.join(OUT, "street_meta.json"), "w"), indent=2)
    log(json.dumps(meta, indent=2))


if __name__ == "__main__":
    sys.exit(main())
