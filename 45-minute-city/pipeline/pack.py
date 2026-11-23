#!/usr/bin/env python3
"""Pack the transit graph into compact binary for the browser.

Emits:
  out/core.json    stops, routes, stop->street-node links, band list, meta
  out/bands.bin    all time bands' ride edges + headways, concatenated
  out/bands.json   byte offsets into bands.bin
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SHIPPED = [
    "core.json", "bands.bin", "bands.json", "street_nodes.bin", "street_edges.bin",
    "car_nodes.bin", "car_edges.bin", "car_calibration.json", "car_calibration2.json",
    "car_zones.bin", "car_link.bin", "access.json",
]


def main():
    T = json.load(open(os.path.join(OUT, "transit.json")))
    stop_nodes = json.load(open(os.path.join(OUT, "stop_nodes.json")))
    detour = json.load(open(os.path.join(OUT, "detour.json")))
    street_meta = json.load(open(os.path.join(OUT, "street_meta.json")))

    stops, routes = T["stops"], T["routes"]
    assert len(stops) < 65535, "stop index no longer fits in uint16"
    assert len(routes) < 65535, "route index no longer fits in uint16"

    blob = bytearray()
    index = {}
    for band in T["bands"]:
        bid = band["id"]
        ride = T["ride"][bid]
        hw = T["headway"][bid]
        r_off = len(blob)
        for a, b, r, d, secs, n in ride:
            blob += struct.pack("<HHHBH", a, b, r, d, min(65535, secs))
        h_off = len(blob)
        for s, r, d, secs, n in hw:
            blob += struct.pack("<HHBH", s, r, d, min(65535, secs))
        index[bid] = {
            "ride_offset": r_off, "ride_count": len(ride),
            "headway_offset": h_off, "headway_count": len(hw),
        }

    open(os.path.join(OUT, "bands.bin"), "wb").write(blob)
    json.dump(index, open(os.path.join(OUT, "bands.json"), "w"), separators=(",", ":"))

    core = {
        "meta": {
            **T["meta"],
            "streets": street_meta,
            "detour_measured": detour,
        },
        "bands": T["bands"],
        # [name, lat, lon, kind, street_node, gtfs_id-for-subway-else-0]
        "stops": [
            [s[1], s[2], s[3], s[4], stop_nodes[i][0],
             s[0].split(":", 1)[1] if s[4] == 0 else 0]
            for i, s in enumerate(stops)
        ],
        "routes": routes,
        "format": {
            "ride": "uint16 a, uint16 b, uint16 route, uint8 dir, uint16 seconds  (9 bytes)",
            "headway": "uint16 stop, uint16 route, uint8 dir, uint16 seconds  (7 bytes)",
        },
    }
    json.dump(core, open(os.path.join(OUT, "core.json"), "w"), separators=(",", ":"))

    # Every file the browser loads. car_zones.bin and car_link.bin are indexed
    # by car-network node, so a stale copy of either silently attaches traffic
    # factors and race times to the wrong streets: copy all twelve together.
    missing = [f for f in SHIPPED if not os.path.exists(os.path.join(OUT, f))]
    if missing:
        print(f"  MISSING from out/: {', '.join(missing)} -- run the step that builds each")
    for f in SHIPPED:
        p = os.path.join(OUT, f)
        if os.path.exists(p):
            print(f"  {f:22s} {os.path.getsize(p)/1e6:6.2f} MB")
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in SHIPPED
                if os.path.exists(os.path.join(OUT, f)))
    print(f"  {'TOTAL':22s} {total/1e6:6.2f} MB")
    print("  then: cp pipeline/out/{" + ",".join(SHIPPED) + "} data/")


if __name__ == "__main__":
    sys.exit(main())
