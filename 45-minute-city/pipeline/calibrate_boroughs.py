#!/usr/bin/env python3
"""Per-borough traffic calibration from the TLC high-volume FHV file.

The citywide alpha mixed crawling Manhattan with flowing eastern Queens; since
most trips are Manhattan trips, the single median made Manhattan too fast and
the edges of the city too slow. Uber/Lyft records cover all five boroughs
densely (22M trips a month), so the factor can be measured per borough:

    alpha(band, borough) = median over INTRA-borough trips of
                           observed trip_time / posted-speed routed time

Intra-borough trips isolate each borough's own streets. Cross-borough trips
fall back to the citywide median. Shared rides are excluded (their durations
include other passengers' detours).

Outputs car_calibration2.json and car_zones.bin (a borough class per car node).
"""
import json
import os
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "out")
MONTH = "2026-03"

BANDS = [
    ("weekday_am_peak", 7, 10, "weekday"),
    ("weekday_midday", 10, 16, "weekday"),
    ("weekday_pm_peak", 16, 19, "weekday"),
    ("weekday_evening", 19, 23, "weekday"),
    ("weekday_late", 23, 29, "weekday"),
    ("saturday_midday", 10, 18, "saturday"),
    ("sunday_midday", 10, 18, "sunday"),
]
BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]


def log(m):
    print(m, flush=True)


def main():
    import numpy as np
    import pyarrow.parquet as pq
    import urllib.request

    sys.path.insert(0, HERE)
    from calibrate_taxi import load_car_graph, zone_centroids, fetch, hav

    log("Car graph + zone centroids")
    lat, lon, adj, n = load_car_graph()
    cent = zone_centroids()

    # zone -> borough
    zb_path = os.path.join(CACHE, "taxi_zone_boroughs.json")
    if not os.path.exists(zb_path):
        url = ("https://data.cityofnewyork.us/resource/8meu-9t5y.json"
               "?$select=locationid,borough&$limit=300")
        req = urllib.request.Request(url, headers={"User-Agent": "45-minute-city/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            open(zb_path, "wb").write(r.read())
    zone_borough = {}
    for row in json.load(open(zb_path)):
        try:
            zone_borough[int(row["locationid"])] = row.get("borough", "")
        except (KeyError, ValueError):
            continue
    b_idx = {b: i for i, b in enumerate(BOROUGHS)}
    log(f"  {len(zone_borough)} zones with boroughs")

    # ---- snap car nodes to nearest zone centroid -> borough class per node
    log("Assigning car nodes to boroughs (nearest zone centroid)")
    grid = defaultdict(list)
    CELL = 0.01
    for z, (la, lo) in cent.items():
        grid[(int(la / CELL), int(lo / CELL))].append(z)

    def nearest_zone(la, lo):
        ci, cj = int(la / CELL), int(lo / CELL)
        best, bd = -1, 1e18
        for r in range(5):
            hit = False
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    if r > 0 and abs(i - ci) != r and abs(j - cj) != r:
                        continue
                    for z in grid.get((i, j), ()):
                        zla, zlo = cent[z]
                        d = (zla - la) ** 2 + (zlo - lo) ** 2
                        if d < bd:
                            bd, best = d, z
                        hit = True
            if hit and r >= 1:
                break
        return best

    node_class = bytearray(n)
    for i in range(n):
        z = nearest_zone(lat[i], lon[i])
        node_class[i] = b_idx.get(zone_borough.get(z, ""), 0)
    counts = defaultdict(int)
    for c in node_class:
        counts[BOROUGHS[c]] += 1
    log(f"  node classes: {dict(counts)}")
    open(os.path.join(OUT, "car_zones.bin"), "wb").write(bytes(node_class))

    # ---- routed posted-speed times between all zones (matrix)
    import heapq
    zone_node = {z: nearest_car_node(lat, lon, adj, *cent[z]) for z in cent}
    # reuse simple grid snap
    def snap_grid():
        g = defaultdict(list)
        for i in range(n):
            g[(int(lat[i] / 0.004), int(lon[i] / 0.004))].append(i)
        return g
    sg = snap_grid()

    def nearest_car(la, lo):
        ci, cj = int(la / 0.004), int(lo / 0.004)
        best, bd = -1, 1e18
        for r in range(6):
            hit = False
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    if r > 0 and abs(i - ci) != r and abs(j - cj) != r:
                        continue
                    for k in sg.get((i, j), ()):
                        d = hav(la, lo, lat[k], lon[k])
                        if d < bd:
                            bd, best = d, k
                        hit = True
            if hit and r >= 1:
                break
        return best

    zone_node = {z: nearest_car(la, lo) for z, (la, lo) in cent.items()}
    zids = sorted(zone_node)
    zpos = {z: i for i, z in enumerate(zids)}
    ZMAX = max(zids) + 1
    log(f"Routing {len(zids)} zones at posted speeds")
    Z = np.full((ZMAX, ZMAX), np.nan, dtype=np.float32)
    for k, z in enumerate(zids):
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
        for z2, nd2 in zone_node.items():
            t = dist.get(nd2)
            if t is not None:
                Z[z, z2] = t
        if (k + 1) % 50 == 0:
            log(f"  {k+1}/{len(zids)}")

    # ---- FHV trips, fully vectorized
    log("FHV trips")
    fp = fetch(f"https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{MONTH}.parquet",
               f"fhvhv_{MONTH}.parquet")
    tab = pq.read_table(fp, columns=[
        "request_datetime", "PULocationID", "DOLocationID",
        "trip_miles", "trip_time", "shared_request_flag",
    ])
    log(f"  {tab.num_rows:,} rows")
    import pyarrow.compute as pc
    pu = tab["PULocationID"].to_numpy().astype(np.int32)
    do = tab["DOLocationID"].to_numpy().astype(np.int32)
    miles = tab["trip_miles"].to_numpy()
    secs = tab["trip_time"].to_numpy().astype(np.float64)
    notshared = pc.equal(tab["shared_request_flag"], "N").to_numpy(zero_copy_only=False)
    req = tab["request_datetime"].to_numpy().astype("datetime64[s]")

    ok = (
        notshared
        & (pu > 0) & (pu < ZMAX) & (do > 0) & (do < ZMAX) & (pu != do)
        & (miles >= 0.8) & (miles <= 35)
        & (secs >= 180) & (secs <= 7200)
    )
    mph = np.where(secs > 0, miles / (secs / 3600), 0)
    ok &= (mph >= 1) & (mph <= 65)
    routed = Z[pu.clip(0, ZMAX - 1), do.clip(0, ZMAX - 1)]
    ok &= ~np.isnan(routed) & (routed >= 300)
    alpha = np.where(routed > 0, secs / routed, np.nan)
    ok &= (alpha >= 0.3) & (alpha <= 8)
    log(f"  usable trips: {ok.sum():,}")

    hours = (req.astype("datetime64[h]") - req.astype("datetime64[D]")).astype(int)
    svc = (req - np.timedelta64(5, "h")).astype("datetime64[D]")
    dow = (svc.view("int64") + 4) % 7
    shifted = np.where(hours >= 5, hours, hours + 24)
    daykind = np.where(dow <= 4, 0, np.where(dow == 5, 1, 2))
    DK = {"weekday": 0, "saturday": 1, "sunday": 2}

    zb_arr = np.zeros(ZMAX, dtype=np.int8)
    for z, b in zone_borough.items():
        if z < ZMAX:
            zb_arr[z] = b_idx.get(b, -1)
    pub = zb_arr[pu.clip(0, ZMAX - 1)]
    dob = zb_arr[do.clip(0, ZMAX - 1)]
    intra = ok & (pub == dob) & (pub >= 0)

    out = {"month": MONTH, "source": "TLC high-volume FHV (Uber/Lyft), non-shared trips",
           "boroughs": BOROUGHS, "bands": {}}
    log(f"\n  {'band':18s} citywide " + " ".join(f"{b[:9]:>9s}" for b in BOROUGHS))
    for name, lo_h, hi_h, dkind in BANDS:
        in_band = (daykind == DK[dkind]) & (shifted >= lo_h) & (shifted < hi_h)
        city = alpha[ok & in_band]
        entry = {"citywide": {"alpha": round(float(np.median(city)), 3), "n": int(len(city))},
                 "by_borough": {}}
        row = f"  {name:18s} {np.median(city):8.2f} "
        for bi, b in enumerate(BOROUGHS):
            v = alpha[intra & in_band & (pub == bi)]
            if len(v) >= 500:
                entry["by_borough"][b] = {
                    "alpha": round(float(np.median(v)), 3),
                    "p25": round(float(np.percentile(v, 25)), 3),
                    "p75": round(float(np.percentile(v, 75)), 3),
                    "n": int(len(v)),
                }
                row += f"{np.median(v):9.2f}"
            else:
                row += f"{'---':>9s}"
        out["bands"][name] = entry
        log(row)

    json.dump(out, open(os.path.join(OUT, "car_calibration2.json"), "w"), indent=1)
    log("\nwrote car_calibration2.json + car_zones.bin")


def nearest_car_node(lat, lon, adj, la, lo):
    return -1  # replaced above; kept for import shape


if __name__ == "__main__":
    sys.exit(main())
