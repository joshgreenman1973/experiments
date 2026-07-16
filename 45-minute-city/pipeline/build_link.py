#!/usr/bin/env python3
"""Link transit stops to the street graph, and measure the real detour factor.

The old build assumed GRID_FACTOR = 1.4 — that walking anywhere takes 1.4x the
straight-line distance. Here we measure it: sample origin/destination pairs,
route them on the real NYC street network, and compare to straight-line.
The measured distribution is reported in the methodology instead of asserted.
"""
import heapq
import json
import math
import os
import random
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def log(m):
    print(m, flush=True)


def load_streets():
    nb = open(os.path.join(OUT, "street_nodes.bin"), "rb").read()
    n = len(nb) // 8
    lat = [0.0] * n
    lon = [0.0] * n
    for i in range(n):
        a, b = struct.unpack_from("<ii", nb, i * 8)
        lat[i] = a / 1e6
        lon[i] = b / 1e6
    eb = open(os.path.join(OUT, "street_edges.bin"), "rb").read()
    m = len(eb) // 11
    adj = defaultdict(list)
    for i in range(m):
        a, b, dm, fl = struct.unpack_from("<IIHB", eb, i * 11)
        d = dm / 10.0
        adj[a].append((b, d, fl))
        adj[b].append((a, d, fl))
    return lat, lon, adj, n


def hav(la1, lo1, la2, lo2):
    R = 6371000.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = p2 - p1
    dl = math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


class Grid:
    """Cheap spatial hash so we can snap without scipy."""

    CELL = 0.004  # ~400m

    def __init__(self, lat, lon):
        self.lat, self.lon = lat, lon
        self.g = defaultdict(list)
        for i in range(len(lat)):
            self.g[(int(lat[i] / self.CELL), int(lon[i] / self.CELL))].append(i)

    def nearest(self, la, lo, rings=4):
        ci, cj = int(la / self.CELL), int(lo / self.CELL)
        best, bd = -1, 1e18
        for r in range(rings):
            found = False
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    if r > 0 and abs(i - ci) != r and abs(j - cj) != r:
                        continue
                    for n in self.g.get((i, j), ()):
                        d = hav(la, lo, self.lat[n], self.lon[n])
                        if d < bd:
                            bd, best = d, n
                        found = True
            if found and r >= 1 and best >= 0:
                break
        return best, bd


def dijkstra(adj, src, mask, limit_m):
    dist = {src: 0.0}
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18) or d > limit_m:
            continue
        for v, w, fl in adj[u]:
            if not (fl & mask):
                continue
            nd = d + w
            if nd < dist.get(v, 1e18) and nd <= limit_m:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def main():
    log("Loading street graph")
    lat, lon, adj, n = load_streets()
    log(f"  {n:,} nodes")
    grid = Grid(lat, lon)

    log("Loading transit stops")
    T = json.load(open(os.path.join(OUT, "transit.json")))
    stops = T["stops"]

    log("Snapping stops to street nodes")
    snapped = []
    far = 0
    for s in stops:
        node, d = grid.nearest(s[2], s[3])
        snapped.append([node, round(d, 1)])
        if d > 200:
            far += 1
    dists = sorted(x[1] for x in snapped)
    log(f"  median snap distance {dists[len(dists)//2]:.1f} m, "
        f"p95 {dists[int(len(dists)*.95)]:.1f} m, >200m: {far}")
    json.dump(snapped, open(os.path.join(OUT, "stop_nodes.json"), "w"), separators=(",", ":"))

    # ---- measure the detour factor
    log("\nMeasuring street-network detour factor (walk mask)")
    random.seed(7)
    ratios = []
    srcs = random.sample(range(n), 60)
    for k, src in enumerate(srcs):
        dist = dijkstra(adj, src, 0b01, 2500)
        cand = [v for v, d in dist.items() if 400 <= d <= 2500]
        if not cand:
            continue
        for v in random.sample(cand, min(40, len(cand))):
            sl = hav(lat[src], lon[src], lat[v], lon[v])
            if sl < 150:
                continue
            ratios.append(dist[v] / sl)
    ratios.sort()

    def pc(p):
        return ratios[int(len(ratios) * p)]

    med = ratios[len(ratios) // 2]
    log(f"  n={len(ratios):,} routed pairs")
    log(f"  detour factor: p10={pc(.1):.2f}  median={med:.2f}  p90={pc(.9):.2f}")
    log(f"  old build asserted a flat 1.40")
    log(f"  -> measured median is {med:.2f}; the flat 1.40 was "
        f"{'an overestimate' if med < 1.4 else 'an underestimate'}")

    json.dump(
        {
            "n_pairs": len(ratios),
            "p10": round(pc(.1), 3),
            "median": round(med, 3),
            "p90": round(pc(.9), 3),
            "note": "Measured by routing random NYC origin/destination pairs on the "
                    "CSCL street network and dividing network distance by straight-line "
                    "distance. Reported for reference only: the app routes on the real "
                    "network and does not apply this factor.",
        },
        open(os.path.join(OUT, "detour.json"), "w"),
        indent=2,
    )


if __name__ == "__main__":
    sys.exit(main())
