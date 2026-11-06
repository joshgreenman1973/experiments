#!/usr/bin/env python3
"""Compare a freshly built data/dashboard.json with the published one before it ships.

Stops (exit 1) if the new build went backward or came back thinner: an earlier
latest month, fewer peer utilities, shorter series, missing research files or an
empty headline number. Also stops on gaps inside monthly series, electricity
windows that end in different months, a broken or unordered utility ranking,
stored ratios or changes that do not match their inputs, and a failed gas
weighting check. A source that failed quietly should never reach the page.

Warns (does not stop) when the hand-collected research files are more than a year
old, and appends every historical value that changed since the published build to
data/revisions.log, so source revisions can be told apart from mistakes.

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

# Monthly series may not develop new holes. Some gaps are real and already published
# (EIA withheld 1996 New York gas months; BLS published no October 2025 CPI during the
# federal shutdown), so only holes absent from the published build stop it.
def months(d):
    return sorted(k for k in d if len(k) == 7 and k[4] == "-")


def nxt(k):
    y, m = int(k[:4]), int(k[5:])
    return f"{y + (m == 12)}-{1 if m == 12 else m + 1:02d}"


for p in ["elec.coned.price", "elec.coned.t12", "elec.other.t12", "elec.nys.t12", "elec.us.t12",
          "elec.lbmp.J", "elec.henry_hub", "gas.eia.ny", "gas.eia.us", "gas.eia_vol.ny", "gas.eia_t12.ny",
          "gas.stack.res", "oil.spot", "cpi.nyc_all", "cpi.nyc_rent"]:
    def holes_in(d):
        ks = months(d or {})
        out, have = [], set(ks)
        k = ks[0] if ks else None
        while ks and k < ks[-1]:
            k = nxt(k)
            if k not in have:
                out.append(k)
        return ks, out
    ks, holes = holes_in(at(new, p))
    if not ks:
        bad.append(f"{p} is empty")
        continue
    known = set(holes_in(at(old, p))[1]) if at(old, p) else set()
    holes = [h for h in holes if h not in known and not (at(old, p) and h < min(months(at(old, p)) or [h]))]
    if holes and at(old, p):
        bad.append(f"{p} has missing months: {', '.join(holes[:6])}{' …' if len(holes) > 6 else ''}")

# Comparison windows must line up.
el = at(new, "elec.latest") or {}
for k in ["nys_month", "us_month"]:
    if el.get(k) and el.get(k) != el.get("month"):
        bad.append(f"electricity windows differ: Con Edison {el.get('month')}, {k} {el.get(k)}")
if at(new, "elec.split_latest.month") != el.get("month"):
    bad.append(f"wholesale benchmark ends {at(new, 'elec.split_latest.month')}, retail {el.get('month')}")
for p in ["elec.coned.t12", "elec.us.t12"]:
    if el.get("month") not in (at(new, p) or {}):
        bad.append(f"{p} has no value for the headline month {el.get('month')}")

# Ranking: Con Edison present, list in descending price order.
peers = at(new, "elec.peers") or []
if not any(x["name"].startswith("Consolidated Edison") for x in peers):
    bad.append("Con Edison is missing from the utility ranking")
if any(a["price"] < b["price"] for a, b in zip(peers, peers[1:])):
    bad.append("utility ranking is not in descending price order")


# Arithmetic identities between stored values (tolerance covers 4-decimal storage).
def close(a, b, tol=0.002):
    return a is not None and b is not None and abs(a - b) <= tol * max(1, abs(b))


ident = [("coned_us_ratio", el.get("coned_t12", 0) / el["us_t12"] if el.get("us_t12") else None),
         ("coned_t12_yoy", (el["coned_t12"] / el["coned_t12_yago"] - 1) * 100 if el.get("coned_t12_yago") else None),
         ("coned_t12bill_yoy", (el["coned_t12bill"] / el["coned_t12bill_yago"] - 1) * 100 if el.get("coned_t12bill_yago") else None)]
for k, want in ident:
    if want is not None and not close(el.get(k), want):
        bad.append(f"elec.latest.{k} = {el.get(k)} but its inputs give {want:.4f}")
sl = at(new, "elec.split_latest") or {}
if sl.get("gap") is not None and not close(sl["gap"], sl["retail"] - sl["energy"]):
    bad.append("split_latest.gap does not equal retail minus energy")
if (at(new, f"elec.coned.t12.{el.get('month')}") is not None
        and not close(at(new, f"elec.coned.t12.{el.get('month')}"), el.get("coned_t12"), 0.001)):
    bad.append("headline Con Edison price does not match its own series")
gl = at(new, "gas.latest") or {}
if gl.get("ny_t12_yago") and not close(gl.get("ny_t12_yoy"), (gl["ny_t12"] / gl["ny_t12_yago"] - 1) * 100):
    bad.append("gas.latest.ny_t12_yoy does not match its inputs")
wc = at(new, "gas.weight_check") or {}
if not wc:
    bad.append("gas weighting check is missing")
elif max(abs(v["diff_pct"]) for v in wc.values()) > 3:
    bad.append("weighted gas prices are more than 3% off EIA's annual figures")

warn = []
import datetime as _dt
for p in ["coned_research.generated", "water.meta.compiled"]:
    g = at(new, p)
    if isinstance(g, str) and len(g) >= 10:
        age = (_dt.date.today() - _dt.date.fromisoformat(g[:10])).days
        if age > 365:
            warn.append(f"{p.split('.')[0]} research was last compiled {g[:10]} ({age} days ago); check for new orders and rates")
for w in warn:
    print("warning:", w)

if bad:
    print("Refusing to publish this build:\n  " + "\n  ".join(bad))
    sys.exit(1)

# Revisions: historical values present in both builds that changed.
rev = []
for p in ["elec.coned.t12", "elec.coned.price", "elec.us.t12", "elec.other.t12", "gas.eia.ny", "gas.eia.us",
          "gas.eia_vol.ny", "oil.spot", "cpi.nyc_all", "cpi.nyc_rent"]:
    o, n = at(old, p) or {}, at(new, p) or {}
    for k in sorted(set(o) & set(n)):
        if o[k] is not None and n[k] is not None and abs(o[k] - n[k]) > 0.005 * max(1, abs(o[k])):
            rev.append(f"{p} {k}: {o[k]} -> {n[k]}")
op = {x["name"]: x["price"] for x in at(old, "elec.peers") or []}
if at(old, "elec.peers_window") == at(new, "elec.peers_window"):
    for x in peers:
        if x["name"] in op and abs(op[x["name"]] - x["price"]) > 0.05:
            rev.append(f"peer price {x['name']}: {op[x['name']]} -> {x['price']}")
if rev:
    print(f"{len(rev)} historical values revised since the published build (logged):")
    for line in rev[:15]:
        print("  " + line)
    with open(ROOT / "data/revisions.log", "a") as f:
        f.write(f"## build {new.get('built')} vs {old.get('built')}\n" + "\n".join(rev) + "\n")

strip = lambda d: {k: v for k, v in d.items() if k not in ("built", "bls_fetched")}
changed = strip(old) != strip(new)
print(f"checks passed; changed={'true' if changed else 'false'}")
for p in ["elec.latest.month", "gas.latest.month", "oil.latest.date"]:
    print(f"  {p}: {at(old, p)} -> {at(new, p)}")
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"changed={'true' if changed else 'false'}\n")
