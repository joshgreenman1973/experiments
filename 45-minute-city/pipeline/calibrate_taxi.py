#!/usr/bin/env python3
"""Calibrate car travel times against real taxi trips.

Posted speed limits are a ceiling, not a description of traffic. To find how
far below them the city actually moves, we take a month of TLC yellow-cab trip
records — every row is a real ride with a metered duration — route the same
zone-to-zone journeys on the car graph at posted speeds, and measure the ratio

    alpha = observed duration / posted-speed routed duration

per time-of-day band. The app then divides every posted speed by that band's
median alpha. One number per band, measured from tens of thousands of trips,
with the spread reported alongside.

Sources:
  trips  https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet
  zones  https://data.cityofnewyork.us/api/geospatial/d3c5-ddgc (GeoJSON export)
"""
import heapq
import json
import math
import os
import struct
import sys
import urllib.request
from collections import defaultdict
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "out")

MONTH = "2026-03"  # most recent complete month at build time
TRIPS_URL = f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{MONTH}.parquet"
ZONES_URL = "https://data.cityofnewyork.us/resource/8meu-9t5y.json?$select=locationid,the_geom&$limit=300"

# Must match build_transit.py BANDS. day: 0=weekday 5=sat 6=sun on the SERVICE
# day (clock time shifted back 5h so 1am Saturday belongs to Friday service).
BANDS = [
    ("weekday_am_peak", 7, 10, "weekday"),
    ("weekday_midday", 10, 16, "weekday"),
    ("weekday_pm_peak", 16, 19, "weekday"),
    ("weekday_evening", 19, 23, "weekday"),
    ("weekday_late", 23, 29, "weekday"),
    ("saturday_midday", 10, 18, "saturday"),
    ("sunday_midday", 10, 18, "sunday"),
]
MAX_PER_BAND = 120000


def log(m):
    print(m, flush=True)


def fetch(url, name, binary=True):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        log(f"  cached  {name} ({os.path.getsize(path)/1e6:.1f} MB)")
        return path
    log(f"  fetching {name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "45-minute-city/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    log(f"  fetched  {name} ({os.path.getsize(path)/1e6:.1f} MB)")
    return path


def hav(la1, lo1, la2, lo2):
    R = 6371000.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = p2 - p1
    dl = math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def load_car_graph():
    nb = open(os.path.join(OUT, "car_nodes.bin"), "rb").read()
    n = len(nb) // 8
    lat, lon = [0.0] * n, [0.0] * n
    for i in range(n):
        a, b = struct.unpack_from("<ii", nb, i * 8)
        lat[i], lon[i] = a / 1e6, b / 1e6
    eb = open(os.path.join(OUT, "car_edges.bin"), "rb").read()
    m = len(eb) // 11
    adj = defaultdict(list)
    for i in range(m):
        a, b, dm, mph = struct.unpack_from("<IIHB", eb, i * 11)
        secs = (dm / 10.0) / (mph * 0.44704)  # seconds at posted speed
        adj[a].append((b, secs))
    return lat, lon, adj, n


def zone_centroids():
    path = fetch(ZONES_URL, "taxi_zones.json")
    rows = json.load(open(path))
    cent = {}
    for row in rows:
        try:
            zid = int(row["locationid"])
        except (KeyError, TypeError, ValueError):
            continue
        geom = row.get("the_geom")
        if not geom:
            continue
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        xs, ys = [], []
        for poly in polys:
            for x, y in poly[0]:
                xs.append(x)
                ys.append(y)
        if xs:
            cent[zid] = (sum(ys) / len(ys), sum(xs) / len(xs))
    log(f"  {len(cent)} zone centroids")
    return cent


def main():
    log("Loading car graph")
    lat, lon, adj, n = load_car_graph()
    log(f"  {n:,} nodes")

    log("Zone centroids")
    cent = zone_centroids()

    # snap centroids to car nodes via a coarse grid
    grid = defaultdict(list)
    CELL = 0.004
    for i in range(n):
        grid[(int(lat[i] / CELL), int(lon[i] / CELL))].append(i)

    def nearest(la, lo):
        ci, cj = int(la / CELL), int(lo / CELL)
        best, bd = -1, 1e18
        for r in range(6):
            hit = False
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    if r > 0 and abs(i - ci) != r and abs(j - cj) != r:
                        continue
                    for k in grid.get((i, j), ()):
                        d = hav(la, lo, lat[k], lon[k])
                        if d < bd:
                            bd, best = d, k
                        hit = True
            if hit and r >= 1:
                break
        return best

    zone_node = {z: nearest(la, lo) for z, (la, lo) in cent.items()}
    zone_node = {z: nd for z, nd in zone_node.items() if nd >= 0}

    log("Reading taxi trips")
    import pyarrow.parquet as pq

    tp = fetch(TRIPS_URL, f"yellow_{MONTH}.parquet")
    tab = pq.read_table(tp, columns=[
        "tpep_pickup_datetime", "tpep_dropoff_datetime",
        "PULocationID", "DOLocationID", "trip_distance",
    ])
    log(f"  {tab.num_rows:,} trips in {MONTH}")

    pu = tab["PULocationID"].to_pylist()
    do = tab["DOLocationID"].to_pylist()
    t0s = tab["tpep_pickup_datetime"].to_pylist()
    t1s = tab["tpep_dropoff_datetime"].to_pylist()
    dist_mi = tab["trip_distance"].to_pylist()

    # bucket trips into bands
    import random
    rng = random.Random(7)
    seen_counts = defaultdict(int)
    by_band = defaultdict(list)  # band -> (pu, do, observed_secs)
    for i in range(len(pu)):
        a, b = pu[i], do[i]
        if a == b or a not in zone_node or b not in zone_node:
            continue
        t0, t1 = t0s[i], t1s[i]
        if t0 is None or t1 is None:
            continue
        obs = (t1 - t0).total_seconds()
        if not (180 <= obs <= 7200):
            continue
        d = dist_mi[i]
        if not (0.8 <= d <= 35):
            continue
        mph = d / (obs / 3600)
        if not (1 <= mph <= 65):
            continue
        svc = t0 - timedelta(hours=5)
        wd = svc.weekday()
        day = "weekday" if wd <= 4 else ("saturday" if wd == 5 else "sunday")
        hr = t0.hour if t0.hour >= 5 else t0.hour + 24
        for name, lo_h, hi_h, dkind in BANDS:
            if dkind == day and lo_h <= hr < hi_h:
                # Reservoir sample so the cap draws uniformly from the whole
                # month. A first-N cap would fill from the first days of the
                # file (it is chronological) and bake week-one weather into
                # every band.
                bucket = by_band[name]
                seen_counts[name] += 1
                if len(bucket) < MAX_PER_BAND:
                    bucket.append((a, b, obs))
                else:
                    j = rng.randrange(seen_counts[name])
                    if j < MAX_PER_BAND:
                        bucket[j] = (a, b, obs)
                break
    for k, v in by_band.items():
        log(f"  {k:20s} {len(v):7,} usable trips")

    # one Dijkstra per pickup zone that actually appears
    needed = sorted({a for v in by_band.values() for a, _, _ in v})
    log(f"Routing from {len(needed)} pickup zones at posted speeds")
    zone_times = {}  # pickup zone -> {dropoff zone: secs}
    targets = {z: zone_node[z] for z in zone_node}
    for zi, z in enumerate(needed):
        src = zone_node[z]
        dist = {src: 0.0}
        pqh = [(0.0, src)]
        while pqh:
            d, u = heapq.heappop(pqh)
            if d > dist.get(u, 1e18):
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    heapq.heappush(pqh, (nd, v))
        zone_times[z] = {tz: dist.get(nd) for tz, nd in targets.items()}
        if (zi + 1) % 40 == 0:
            log(f"  {zi+1}/{len(needed)}")

    def pct(v, p):
        v = sorted(v)
        return v[min(len(v) - 1, int(len(v) * p))]

    result = {"month": MONTH, "bands": {}}
    log("\nBand calibration (alpha = observed / posted-speed routed):")
    for name, *_ in BANDS:
        alphas = []
        for a, b, obs in by_band.get(name, []):
            routed = zone_times.get(a, {}).get(b)
            # Floor of 5 routed minutes: centroids stand in for true endpoints,
            # and on short hops that understates the routed denominator
            # one-sidedly (a median absorbs noise, not bias). Longer trips
            # dilute the endpoint error.
            if routed is None or routed < 300:
                continue
            al = obs / routed
            if 0.3 <= al <= 8:
                alphas.append(al)
        if len(alphas) < 200:
            log(f"  {name:20s} INSUFFICIENT ({len(alphas)})")
            continue
        med = pct(alphas, 0.5)
        result["bands"][name] = {
            "alpha": round(med, 3),
            "p25": round(pct(alphas, 0.25), 3),
            "p75": round(pct(alphas, 0.75), 3),
            "n_trips": len(alphas),
            "effective_of_posted_pct": round(100 / med, 1),
        }
        log(f"  {name:20s} alpha={med:.2f}  IQR {pct(alphas,.25):.2f}-{pct(alphas,.75):.2f}  "
            f"n={len(alphas):,}  -> traffic runs at {100/med:.0f}% of posted")

    result["note"] = (
        "alpha divides posted speeds to give effective traffic speed per band. "
        "Median over real TLC yellow-cab trips vs the same zone-to-zone journey "
        "routed at posted speed limits. Zone centroids stand in for exact "
        "pickup/dropoff points; the median over tens of thousands of trips "
        "absorbs that noise."
    )
    json.dump(result, open(os.path.join(OUT, "car_calibration.json"), "w"), indent=2)
    log("\nwrote car_calibration.json")


if __name__ == "__main__":
    sys.exit(main())
