#!/usr/bin/env python3
"""Build a directed drivable street graph for New York City from the CSCL
centerline file.

Unlike the walk/bike graph, car edges are DIRECTED (trafdir: FT with the
digitized direction, TF against it, TW both ways) and carry the posted speed.
Posted speeds are the ceiling; calibrate_taxi.py measures how far below them
real traffic runs, per time of day.

rw_type codes used for cars: 1 street, 2 highway, 3 bridge, 4 tunnel, 9 ramp.
Excluded: paths, boardwalks, step streets, alleys, driveways, ferry routes,
non-physical segments.

Outputs (own node space, separate from the walk/bike graph):
  out/car_nodes.bin  int32 lat*1e6, int32 lon*1e6
  out/car_edges.bin  uint32 from, uint32 to, uint16 decimeters, uint8 mph  (directed)
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

CAR_TYPES = {"1", "2", "3", "4", "9"}
SNAP = 1e5
DEFAULT_MPH = 25  # New York City default speed limit


def log(m):
    print(m, flush=True)


def fetch_all():
    path = os.path.join(CACHE, "cscl_car.json")
    if os.path.exists(path) and os.path.getsize(path) > 10_000_000:
        log(f"  cached cscl_car.json ({os.path.getsize(path)/1e6:.1f} MB)")
        return json.load(open(path))
    os.makedirs(CACHE, exist_ok=True)
    rows, offset, limit = [], 0, 50000
    while True:
        q = {
            "$select": "the_geom,rw_type,trafdir,posted_speed",
            "$where": "rw_type in('" + "','".join(sorted(CAR_TYPES)) + "') AND status='2'",
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
    log(f"  fetched {len(rows):,} segments")
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
    log("Fetching CSCL drivable segments")
    rows = fetch_all()

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

    edges = []  # directed (a, b, meters, mph)
    dir_counts = defaultdict(int)
    for r in rows:
        g = r.get("the_geom")
        if not g:
            continue
        td = (r.get("trafdir") or "").strip().upper()
        dir_counts[td] += 1
        if td not in ("FT", "TF", "TW"):
            continue  # NV and blank are non-vehicular
        try:
            mph = int(float(r.get("posted_speed") or 0))
        except ValueError:
            mph = 0
        if mph <= 0 or mph > 70:
            mph = DEFAULT_MPH
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
                if td in ("FT", "TW"):
                    edges.append((a, b, d, mph))
                if td in ("TF", "TW"):
                    edges.append((b, a, d, mph))

    log(f"  trafdir counts: {dict(dir_counts)}")
    log(f"  nodes: {len(nodes):,}  directed edges: {len(edges):,}")

    # Largest STRONGLY connected component would be ideal; for a street network
    # the practical equivalent is: keep the largest weakly connected component,
    # which removes stray islands. One-way stubs that trap a car are vanishingly
    # rare in CSCL and would only shave the isochrone's fringe.
    adj = defaultdict(list)
    for a, b, d, mph in edges:
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
    log(f"  largest component: {len(keep):,} nodes ({len(keep)/len(nodes)*100:.1f}%)")

    remap = {}
    out_nodes = []
    for n in sorted(keep):
        remap[n] = len(out_nodes)
        out_nodes.append(nodes[n])
    out_edges = [(remap[a], remap[b], d, mph) for a, b, d, mph in edges if a in keep and b in keep]

    nb = bytearray()
    for lat, lon in out_nodes:
        nb += struct.pack("<ii", int(round(lat * 1e6)), int(round(lon * 1e6)))
    open(os.path.join(OUT, "car_nodes.bin"), "wb").write(nb)

    eb = bytearray()
    for a, b, d, mph in out_edges:
        eb += struct.pack("<IIHB", a, b, min(65535, int(round(d * 10))), mph)
    open(os.path.join(OUT, "car_edges.bin"), "wb").write(eb)

    speeds = defaultdict(int)
    for _, _, _, mph in out_edges:
        speeds[mph] += 1
    meta = {
        "source": "NYC Open Data Centerline (inkn-q76z), rw_type 1/2/3/4/9, directed by trafdir",
        "nodes": len(out_nodes),
        "edges": len(out_edges),
        "posted_speed_histogram": dict(sorted(speeds.items())),
        "default_mph": DEFAULT_MPH,
        "edge_format": "uint32 from, uint32 to, uint16 decimeters, uint8 mph (directed)",
    }
    json.dump(meta, open(os.path.join(OUT, "car_meta.json"), "w"), indent=2)
    log(f"  wrote car_nodes.bin ({len(nb)/1e6:.2f} MB), car_edges.bin ({len(eb)/1e6:.2f} MB)")
    log(json.dumps(meta["posted_speed_histogram"], indent=2))


if __name__ == "__main__":
    sys.exit(main())
