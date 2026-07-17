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

Bridge caveat: CSCL types car-only expressway decks (Verrazzano, Throgs Neck,
elevated BQE) as rw_type 3 alongside walkable crossings, and posted speed does
not separate them (the Verrazzano deck is posted 35). What does separate them,
verified against the data: every major crossing with pedestrian access has
DEDICATED path segments ("BROOKLYN BRIDGE PEDESTRIAN PATH", "GEORGE WASHINGTON
BRDG PED PATH", ...), so the same-named roadway deck is cars only. Small local
drawbridges (Gowanus, Newtown Creek, City Island, Broadway Bridge) carry their
sidewalks on the roadway segment and have no separate path — those stay.
Rule for rw_type 3: keep explicit ped/bike path segments; drop expressway and
parkway decks and the named major crossings whose walkways are separate
segments; keep the rest.
"""
import re

# Major crossings whose pedestrian/bike access is a separate CSCL segment
# (or that have no pedestrian access at all: Verrazzano, Throgs Neck,
# Whitestone, Alexander Hamilton, FDR/Harlem River drives).
BRIDGE_ROADWAY_EXCLUDE = re.compile(
    r"EXPY|PKWY|VERRAZ|THROGS NECK|WHITESTONE|ALEXANDER HAMILTON|HENRY HUDSON"
    r"|GEORGE WASHINGTON|ROBERT F KENNEDY|RFK|QUEENSBORO|ED KOCH|MANHATTAN BRG"
    r"|WILLIAMSBURG BRG|BROOKLYN BRG|KOSCIUSZKO|PULASKI|WASHINGTON BRG"
    r"|MACOMBS DAM|MADISON AVE?\s+BR|WILLIS AV|3 AV BRIDGE|145 ST BRIDGE"
    r"|FDR DR|HARLEM RIVER DR"
)
BRIDGE_PATH_KEEP = re.compile(r"PED|PATH|BIKE|WALK|OPAS")
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
    path = os.path.join(CACHE, "cscl_v2.json")
    if os.path.exists(path) and os.path.getsize(path) > 10_000_000:
        log(f"  cached cscl_v2.json ({os.path.getsize(path)/1e6:.1f} MB)")
        return json.load(open(path))
    os.makedirs(CACHE, exist_ok=True)
    rows, offset, limit = [], 0, 50000
    while True:
        q = {
            "$select": "the_geom,rw_type,posted_speed,physicalid,segmentlength,full_street_name",
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
    fast_bridges = 0
    for r in rows:
        g = r.get("the_geom")
        rw = r.get("rw_type")
        if not g or rw not in FETCH_TYPES:
            skipped += 1
            continue
        if rw == "3":
            # See module docstring: keep explicit ped/bike paths, drop car-only
            # decks and roadways whose walkway is a separate segment.
            name = (r.get("full_street_name") or "").upper()
            if not BRIDGE_PATH_KEEP.search(name):
                try:
                    mph = int(float(r.get("posted_speed") or 0))
                except ValueError:
                    mph = 0
                if mph > 35 or BRIDGE_ROADWAY_EXCLUDE.search(name):
                    fast_bridges += 1
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

    log(f"  nodes: {len(nodes):,}  edges: {len(edges):,}  (skipped {skipped}, "
        f"car-only bridge decks dropped: {fast_bridges})")

    # Merge the PATH corridor in New Jersey (OpenStreetMap), if built. Those
    # streets share this node space and weld at identical coordinates -- which
    # never happens across the Hudson, correctly: you cannot walk from Hoboken
    # to Manhattan. PATH links them in the transit graph instead.
    nj_path = os.path.join(CACHE, "nj_edges.json")
    if os.path.exists(nj_path):
        nj = json.load(open(nj_path))
        before = len(edges)
        for la1, lo1, la2, lo2, w, bk in nj:
            d = hav(la1, lo1, la2, lo2)
            if d < 0.5:
                continue
            a, b = nid(lo1, la1), nid(lo2, la2)
            if a == b:
                continue
            edges.append((a, b, d, w, bk))
        log(f"  + New Jersey (PATH corridor, OSM): {len(edges)-before:,} segments, "
            f"nodes now {len(nodes):,}")
    else:
        log("  (no nj_edges.json; run build_nj_streets.py for the PATH corridor)")

    # Drop stray-geometry islands, but KEEP every real landmass. Staten Island
    # is genuinely walk-disconnected from the rest of the city (the Verrazzano
    # has no pedestrian access), so "largest component only" would delete the
    # borough. Any component with at least 500 nodes is a place, not noise.
    MIN_COMPONENT = 500
    adj = defaultdict(list)
    for i, (a, b, d, w, bk) in enumerate(edges):
        adj[a].append(b)
        adj[b].append(a)
    seen = set()
    keep = set()
    comps = []
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
        comps.append(len(comp))
        if len(comp) >= MIN_COMPONENT:
            keep.update(comp)
    comps.sort(reverse=True)
    log(f"  components kept (>= {MIN_COMPONENT} nodes): "
        f"{[c for c in comps if c >= MIN_COMPONENT]}")
    log(f"  kept {len(keep):,} of {len(nodes):,} nodes ({len(keep)/len(nodes)*100:.1f}%)")

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
