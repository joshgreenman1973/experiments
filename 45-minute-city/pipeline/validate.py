#!/usr/bin/env python3
"""Sanity-check the built transit graph against physical reality.

The old build multiplied bus times by 2.5x to make them look right. If this
build is honest, implied speeds should be plausible with no correction at all.
"""
import json
import math
import os
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "out", "transit.json")))

stops = D["stops"]
routes = D["routes"]


def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[2]), math.radians(b[2])
    dp = p2 - p1
    dl = math.radians(b[3] - a[3])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]


print("=" * 64)
print("IMPLIED SPEEDS (straight-line distance / scheduled time)")
print("Straight-line understates true track/street distance, so these are")
print("lower bounds on real speed.")
print("=" * 64)

for band in ["weekday_am_peak", "weekday_midday", "weekday_late"]:
    print(f"\n--- {band}")
    speeds = defaultdict(list)
    for a, b, r, dr, secs, n in D["ride"][band]:
        d = hav(stops[a], stops[b])
        if d < 50 or secs <= 0:
            continue
        kind = "subway" if stops[a][4] == 0 else "bus"
        speeds[kind].append(d / secs * 2.23694)  # m/s -> mph
    for kind, v in sorted(speeds.items()):
        print(f"  {kind:7s} n={len(v):6,}  p10={pct(v,.1):5.1f}  median={statistics.median(v):5.1f}  "
              f"p90={pct(v,.9):5.1f}  max={max(v):5.1f} mph")

print("\n" + "=" * 64)
print("PLAUSIBILITY CHECKS")
print("=" * 64)
band = "weekday_am_peak"
speeds = {"subway": [], "bus": []}
for a, b, r, dr, secs, n in D["ride"][band]:
    d = hav(stops[a], stops[b])
    if d < 50 or secs <= 0:
        continue
    speeds["subway" if stops[a][4] == 0 else "bus"].append(d / secs * 2.23694)

bus_med = statistics.median(speeds["bus"])
sub_med = statistics.median(speeds["subway"])
# NYC DOT reports average bus speeds around 7-8 mph citywide.
print(f"  bus median {bus_med:.1f} mph      {'PLAUSIBLE (NYC buses avg ~7-8 mph)' if 4 <= bus_med <= 12 else 'IMPLAUSIBLE'}")
print(f"  subway median {sub_med:.1f} mph   {'PLAUSIBLE (subway avg ~17 mph incl. stops)' if 10 <= sub_med <= 30 else 'IMPLAUSIBLE'}")
fast_bus = sum(1 for s in speeds["bus"] if s > 45)
print(f"  bus segments over 45 mph: {fast_bus} ({fast_bus/len(speeds['bus'])*100:.2f}%)")

print("\n" + "=" * 64)
print("HEADWAYS — named routes, weekday AM peak (should match timetables)")
print("=" * 64)
hw = defaultdict(list)
for s, r, dr, secs, n in D["headway"]["weekday_am_peak"]:
    hw[routes[r][0]].append(secs / 60)
for name in ["6", "L", "7", "A", "G", "M14+", "B41", "Bx12+", "Q58", "S79+", "M104"]:
    if name in hw:
        v = hw[name]
        print(f"  {name:6s} median headway {statistics.median(v):5.1f} min   (n={len(v)} stops)")

print("\n  Late-night vs peak on the 6 train:")
for band in ["weekday_am_peak", "weekday_late"]:
    v = [secs / 60 for s, r, dr, secs, n in D["headway"][band] if routes[r][0] == "6"]
    if v:
        print(f"    {band:18s} {statistics.median(v):5.1f} min")
