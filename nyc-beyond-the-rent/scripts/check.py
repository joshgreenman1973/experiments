#!/usr/bin/env python3
"""Compare a freshly built data/dashboard.json with the published one before it ships.

Stops (exit 1) if the new build went backward or came back thinner: an earlier
latest month, fewer peer utilities, shorter series, missing research files or an
empty headline number. A source that failed quietly should never reach the page.

Usage: check.py OLD.json [NEW.json]. Prints changed=true|false, and writes it to
$GITHUB_OUTPUT when run in Actions. "Changed" ignores the build and fetch dates.
"""
import json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
old = json.load(open(sys.argv[1]))
new = json.load(open(sys.argv[2] if len(sys.argv) > 2 else ROOT / "data/dashboard.json"))
bad = []


def at(d, path):
    for k in path.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


# Latest dates may stay put (heating oil is weekly only from October to March) but never move back.
for p in ["elec.latest.month", "gas.latest.month", "gas.latest.stack_month",
          "oil.latest.date", "oil.latest.spot_month", "oil.latest.margin_month"]:
    o, n = at(old, p), at(new, p)
    if not n:
        bad.append(f"{p} is missing")
    elif o and n < o:
        bad.append(f"{p} went back from {o} to {n}")

# Headline numbers must exist.
for p in ["elec.latest.coned_t12", "elec.latest.us_t12", "elec.latest.nys_t12", "elec.latest.coned_t12bill",
          "gas.latest.ny_t12", "gas.latest.us_t12", "oil.latest.nyc", "elec.split_latest"]:
    if at(new, p) in (None, {}, []):
        bad.append(f"{p} is empty")

# Series and lists may grow but not shrink.
def size(x):
    if isinstance(x, dict):
        return sum(size(v) for v in x.values()) if x and all(isinstance(v, (dict, list)) for v in x.values()) else len(x)
    return len(x) if isinstance(x, list) else 0

for p in ["elec.coned", "elec.other", "elec.nys", "elec.us", "elec.lbmp", "elec.henry_hub", "elec.split",
          "gas.eia", "gas.bls_therm", "oil.weekly", "oil.spot", "cpi"]:
    o, n = size(at(old, p)), size(at(new, p))
    if n < o:
        bad.append(f"{p} shrank from {o} to {n} points")

o, n = len(at(old, "elec.peers") or []), len(at(new, "elec.peers") or [])
if n < 0.9 * o:
    bad.append(f"peer utilities fell from {o} to {n}")
for p in ["water.rates", "coned_research.rate_cases"]:
    if not at(new, p):
        bad.append(f"{p} is missing")

if bad:
    print("Refusing to publish this build:\n  " + "\n  ".join(bad))
    sys.exit(1)

strip = lambda d: {k: v for k, v in d.items() if k not in ("built", "bls_fetched")}
changed = strip(old) != strip(new)
print(f"checks passed; changed={'true' if changed else 'false'}")
for p in ["elec.latest.month", "gas.latest.month", "oil.latest.date"]:
    print(f"  {p}: {at(old, p)} -> {at(new, p)}")
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"changed={'true' if changed else 'false'}\n")
