#!/usr/bin/env python3
"""Walk/bike streets for the PATH corridor in New Jersey, from OpenStreetMap.

The city's Centerline file stops at the city line, so PATH's seven New Jersey
stations would have no streets to walk on: you could ride the train but not
leave the platform. This fetches the walkable network for Newark, Harrison,
Jersey City and Hoboken so PATH has somewhere to arrive.

Scope is deliberately the PATH corridor and nothing more. This is not a
general New Jersey street graph, and the taxi mode does not use it — see
METHODOLOGY.md on why driving stays inside New York City.

Output: cache/nj_edges.json — [lat1, lon1, lat2, lon2, walk, bike] per segment,
merged by build_streets.py into the same node space as the Centerline data.
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")

# Newark and Harrison in the west, Hoboken in the east. Clipped at -74.02 so we
# stop at the Hudson and never overlap the Centerline data in Manhattan.
BBOX = (40.69, -74.20, 40.79, -74.02)
OVERPASS = "https://overpass.kumi.systems/api/interpreter"

# OSM highway classes a person can walk on. Motorways, trunk roads and their
# links are excluded: no pedestrians on the New Jersey Turnpike.
WALKABLE = {
    "footway", "path", "pedestrian", "steps", "living_street", "residential",
    "tertiary", "tertiary_link", "secondary", "secondary_link", "primary",
    "primary_link", "unclassified", "service", "track", "cycleway", "road",
    "corridor",
}
NO_BIKE = {"steps", "corridor"}  # stairs: a bike must be carried


def log(m):
    print(m, flush=True)


def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def fetch():
    path = os.path.join(CACHE, "nj_osm.json")
    if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
        log(f"  cached nj_osm.json ({os.path.getsize(path)/1e6:.1f} MB)")
        return json.load(open(path))
    os.makedirs(CACHE, exist_ok=True)
    s, w, n, e = BBOX
    q = (
        f'[out:json][timeout:600];'
        f'way["highway"]["area"!~"yes"]({s},{w},{n},{e});'
        f'out geom;'
    )
    log("  querying Overpass (this takes a minute) ...")
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(OVERPASS, data=data,
                                 headers={"User-Agent": "45-minute-city/1.0"})
    with urllib.request.urlopen(req, timeout=900) as r:
        raw = r.read()
    open(path, "wb").write(raw)
    log(f"  fetched nj_osm.json ({len(raw)/1e6:.1f} MB)")
    return json.loads(raw)


def main():
    log("Fetching New Jersey streets for the PATH corridor")
    d = fetch()
    els = d.get("elements", [])
    log(f"  {len(els):,} ways returned")

    edges = []
    kept = skipped = 0
    kinds = {}
    for el in els:
        t = el.get("tags", {}) or {}
        hw = t.get("highway")
        if hw not in WALKABLE:
            skipped += 1
            continue
        # Honour explicit access tags rather than guessing.
        if t.get("foot") in ("no", "private") or t.get("access") in ("no", "private"):
            skipped += 1
            continue
        walk = 1
        bike = 0 if (hw in NO_BIKE or t.get("bicycle") in ("no", "private")) else 1
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        kinds[hw] = kinds.get(hw, 0) + 1
        kept += 1
        for i in range(len(geom) - 1):
            a, b = geom[i], geom[i + 1]
            # Clip at the Hudson so we never duplicate Centerline geometry.
            if a["lon"] > -74.02 or b["lon"] > -74.02:
                continue
            dd = hav(a["lat"], a["lon"], b["lat"], b["lon"])
            if dd < 0.5:
                continue
            edges.append([round(a["lat"], 6), round(a["lon"], 6),
                          round(b["lat"], 6), round(b["lon"], 6), walk, bike])

    log(f"  kept {kept:,} ways ({skipped:,} skipped), {len(edges):,} segments")
    log("  top highway classes: " +
        ", ".join(f"{k}={v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:8]))

    out = os.path.join(CACHE, "nj_edges.json")
    json.dump(edges, open(out, "w"), separators=(",", ":"))
    log(f"  wrote {out} ({os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
