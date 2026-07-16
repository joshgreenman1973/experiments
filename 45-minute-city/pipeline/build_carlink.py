#!/usr/bin/env python3
"""Map every car-graph node to its nearest walk-graph node.

The "train vs cab" view needs both times at the same place: taxi times live on
the car graph, transit times on the walk graph. This link lets the app read a
transit time for any car node. Emits car_link.bin (uint32 walk node per car
node; 0xFFFFFFFF if nothing within ~2.5 km).
"""
import os
import struct
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def load_nodes(name):
    nb = open(os.path.join(OUT, name), "rb").read()
    n = len(nb) // 8
    lat, lon = [0.0] * n, [0.0] * n
    for i in range(n):
        a, b = struct.unpack_from("<ii", nb, i * 8)
        lat[i], lon[i] = a / 1e6, b / 1e6
    return lat, lon, n


def main():
    wlat, wlon, wn = load_nodes("street_nodes.bin")
    clat, clon, cn = load_nodes("car_nodes.bin")
    print(f"walk nodes {wn:,}, car nodes {cn:,}", flush=True)

    CELL = 0.004
    grid = defaultdict(list)
    for i in range(wn):
        grid[(int(wlat[i] / CELL), int(wlon[i] / CELL))].append(i)

    out = bytearray()
    missing = 0
    for i in range(cn):
        la, lo = clat[i], clon[i]
        ci, cj = int(la / CELL), int(lo / CELL)
        best, bd = -1, 1e18
        for r in range(6):
            hit = False
            for gi in range(ci - r, ci + r + 1):
                for gj in range(cj - r, cj + r + 1):
                    if r > 0 and abs(gi - ci) != r and abs(gj - cj) != r:
                        continue
                    for k in grid.get((gi, gj), ()):
                        dx = (wlat[k] - la) * 111320
                        dy = (wlon[k] - lo) * 84500
                        d = dx * dx + dy * dy
                        if d < bd:
                            bd, best = d, k
                        hit = True
            if hit and r >= 1:
                break
        if best < 0:
            missing += 1
            best = 0xFFFFFFFF
        out += struct.pack("<I", best & 0xFFFFFFFF)

    open(os.path.join(OUT, "car_link.bin"), "wb").write(out)
    print(f"wrote car_link.bin ({len(out)/1e6:.2f} MB), unlinked: {missing}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
