#!/usr/bin/env python3
"""Build a frequency-based multimodal transit graph for New York City from MTA GTFS.

Every ride time and every headway in the output is computed from published MTA
schedules. Nothing here is estimated, scaled or hand-tuned.

Outputs pipeline/out/transit.json:
  meta      - feed versions, build date, service dates used, row counts
  stops     - [id, name, lat, lon, kind]  kind 0=subway 1=bus
  routes    - [short_name, kind, color]
  bands     - time-of-day bands
  ride      - per band: [from_stop, to_stop, route, median_seconds, n_obs]
  headway   - per band: [stop, route, mean_headway_seconds, n_departures]

Ride time  = median over all scheduled trips in the band of
             (arrival at B - departure from A) for consecutive stops A,B.
Headway    = band duration / number of scheduled departures, per stop+route.
"""
import csv
import io
import json
import os
import statistics
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "out")

FEEDS = {
    "subway": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip",
    "bus_bx": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip",
    "bus_b": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip",
    "bus_m": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip",
    "bus_q": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip",
    "bus_si": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip",
    "bus_co": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip",
    # Staten Island Ferry, published by NYC DOT (not the MTA). Free, 24/7, and
    # the only transit link between Staten Island and Manhattan, so leaving it
    # out silently strands the borough.
    "siferry": "https://data.cityofnewyork.us/download/b57i-ri22/application%2Fzip",
    # NYC Ferry (Astoria, East River, South Brooklyn, Rockaway, Soundview,
    # Governors Island, St. George). A different operator again, published
    # through its own vendor feed.
    "nycferry": "https://nycferry.connexionz.net/rtt/public/utility/gtfs.aspx",
    # PATH -- Port Authority Trans-Hudson. Included where the commuter
    # railroads are not, because it behaves like a subway: see METHODOLOGY.md.
    "path": "https://data.trilliumtransit.com/gtfs/path-nj-us/path-nj-us.zip",
}

# stop/route kind: 0 rail (subway + Staten Island Railway), 1 bus, 2 ferry.
# Derived from GTFS route_type, not from the feed: NYC Ferry's own feed carries
# two route_type=3 shuttle BUS routes (the free Rockaway shuttles) alongside
# its boats, so a per-feed label would call those buses ferries.
FEED_KIND = {"subway": 0, "siferry": 2, "nycferry": 2, "path": 0}
ROUTE_TYPE_KIND = {
    "0": 1,   # tram/streetcar -> treat as surface
    "1": 0,   # subway
    "2": 0,   # rail (Staten Island Railway)
    "3": 1,   # bus
    "4": 2,   # ferry
    "5": 1, "6": 1, "7": 1,
}

# (name, start_sec, end_sec, day_kind). Times are GTFS seconds since noon-12h.
BANDS = [
    ("weekday_am_peak", 7 * 3600, 10 * 3600, "weekday"),
    ("weekday_midday", 10 * 3600, 16 * 3600, "weekday"),
    ("weekday_pm_peak", 16 * 3600, 19 * 3600, "weekday"),
    ("weekday_evening", 19 * 3600, 23 * 3600, "weekday"),
    ("weekday_late", 23 * 3600, 29 * 3600, "weekday"),  # 11pm-5am, GTFS wraps past 24h
    ("saturday_midday", 10 * 3600, 18 * 3600, "saturday"),
    ("sunday_midday", 10 * 3600, 18 * 3600, "sunday"),
]


def log(msg):
    print(msg, flush=True)


def fetch(name, url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name + ".zip")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        log(f"  cached  {name} ({os.path.getsize(path)/1e6:.1f} MB)")
        return path
    log(f"  fetching {name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "45-minute-city/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())
    log(f"  fetched  {name} ({os.path.getsize(path)/1e6:.1f} MB)")
    return path


def read_csv(zf, name):
    """Yield dict rows from a GTFS table, tolerating a BOM."""
    try:
        raw = zf.read(name)
    except KeyError:
        return []
    text = raw.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def gtfs_secs(t):
    """Parse GTFS HH:MM:SS, which may exceed 24h. Returns None if unparseable."""
    if not t:
        return None
    parts = t.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None


def pick_service_dates(zf):
    """Choose a representative weekday / saturday / sunday inside the feed's
    validity window. Dates carrying calendar_dates exceptions are holiday or
    diversion schedules — a rebuild the week before Christmas must not bake
    holiday headways into every weekday band — so exception dates are skipped
    unless nothing else is available."""
    cal = read_csv(zf, "calendar.txt")
    if not cal:
        return {}
    starts = [c["start_date"] for c in cal if c.get("start_date")]
    ends = [c["end_date"] for c in cal if c.get("end_date")]
    lo = max(min(starts), date.today().strftime("%Y%m%d"))
    hi = max(ends)

    exception_dates = {e["date"] for e in read_csv(zf, "calendar_dates.txt") if e.get("date")}

    def d(s):
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))

    lo_d, hi_d = d(lo), d(hi)
    if lo_d > hi_d:
        lo_d = d(min(starts))
    want = {"weekday": 2, "saturday": 5, "sunday": 6}  # Wed, Sat, Sun
    out = {}
    for kind, wd in want.items():
        fallback = None
        cur = lo_d
        while cur <= hi_d and cur <= lo_d + timedelta(days=60):
            if cur.weekday() == wd:
                s = cur.strftime("%Y%m%d")
                if s not in exception_dates:
                    out[kind] = s
                    break
                if fallback is None:
                    fallback = s
            cur += timedelta(days=1)
        if kind not in out and fallback:
            out[kind] = fallback
    return out


def active_services(zf, yyyymmdd):
    """service_ids running on a given date, honoring calendar_dates exceptions."""
    if not yyyymmdd:
        return set()
    d = date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    dow = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][d.weekday()]
    active = set()
    for c in read_csv(zf, "calendar.txt"):
        if c.get(dow) == "1" and c["start_date"] <= yyyymmdd <= c["end_date"]:
            active.add(c["service_id"])
    for e in read_csv(zf, "calendar_dates.txt"):
        if e.get("date") != yyyymmdd:
            continue
        if e.get("exception_type") == "1":
            active.add(e["service_id"])
        elif e.get("exception_type") == "2":
            active.discard(e["service_id"])
    return active


def process_feed(name, path, kind, acc):
    """Accumulate stops, routes, ride observations and departures from one feed."""
    log(f"\n-- {name}")
    zf = zipfile.ZipFile(path)

    dates = pick_service_dates(zf)
    log(f"   service dates: {dates}")
    services = {k: active_services(zf, v) for k, v in dates.items()}
    for k, v in services.items():
        log(f"   {k}: {len(v)} service_ids")

    # stops
    is_subway = kind == 0
    stops = {}
    for s in read_csv(zf, "stops.txt"):
        if s.get("location_type") not in ("", "0", None):
            continue  # skip stations/entrances; we key on the platform's parent below
        try:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        except (ValueError, KeyError):
            continue
        # For subway, collapse N/S platforms onto the parent station.
        sid = s.get("parent_station") or s["stop_id"] if is_subway else s["stop_id"]
        key = f"{name}:{sid}"
        if key not in stops:
            stops[key] = (s["stop_name"].strip(), lat, lon)
    # subway parent stations live as location_type=1 rows; grab their coords/names
    if is_subway:
        for s in read_csv(zf, "stops.txt"):
            if s.get("location_type") == "1":
                key = f"{name}:{s['stop_id']}"
                try:
                    stops[key] = (s["stop_name"].strip(), float(s["stop_lat"]), float(s["stop_lon"]))
                except (ValueError, KeyError):
                    pass
    acc["stops"].update(stops)
    log(f"   stops: {len(stops)}")

    # map platform stop_id -> canonical key (parent for subway)
    canon = {}
    for s in read_csv(zf, "stops.txt"):
        if s.get("location_type") in ("1", "2", "3", "4"):
            continue
        sid = s["stop_id"]
        target = (s.get("parent_station") or sid) if is_subway else sid
        canon[sid] = f"{name}:{target}"

    # routes — kind from route_type where the feed declares one
    routes = {}
    route_kind = {}
    for r in read_csv(zf, "routes.txt"):
        key = f"{name}:{r['route_id']}"
        short = (r.get("route_short_name") or r.get("route_long_name") or r["route_id"]).strip()
        rk = ROUTE_TYPE_KIND.get((r.get("route_type") or "").strip(), kind)
        route_kind[key] = rk
        routes[key] = (short, rk, (r.get("route_color") or "").strip())
    acc["routes"].update(routes)

    # trips
    trip_route = {}
    trip_service = {}
    trip_dir = {}
    for t in read_csv(zf, "trips.txt"):
        trip_route[t["trip_id"]] = f"{name}:{t['route_id']}"
        trip_service[t["trip_id"]] = t["service_id"]
        d = (t.get("direction_id") or "0").strip()
        trip_dir[t["trip_id"]] = 1 if d == "1" else 0

    # A stop's kind follows the routes serving it, so a Rockaway shuttle-bus
    # stop in the ferry feed is labelled a bus stop. Rail wins over bus wins
    # over ferry when a stop serves several.
    for tid, rkey in trip_route.items():
        pass  # stop kinds are filled in while reading stop_times below

    # stop_times, grouped by trip
    log("   reading stop_times ...")
    by_trip = defaultdict(list)
    n = 0
    for st in read_csv(zf, "stop_times.txt"):
        tid = st["trip_id"]
        if tid not in trip_route:
            continue
        arr = gtfs_secs(st.get("arrival_time"))
        dep = gtfs_secs(st.get("departure_time"))
        if arr is None and dep is None:
            continue
        arr = arr if arr is not None else dep
        dep = dep if dep is not None else arr
        try:
            seq = int(st["stop_sequence"])
        except (ValueError, KeyError):
            continue
        sid = canon.get(st["stop_id"])
        if not sid:
            continue
        rk = route_kind.get(trip_route[tid], kind)
        prev = acc["stop_kind"].get(sid)
        acc["stop_kind"][sid] = rk if prev is None else min(prev, rk)
        by_trip[tid].append((seq, sid, arr, dep))
        n += 1
    log(f"   stop_times rows: {n:,} across {len(by_trip):,} trips")

    for band_name, lo, hi, day_kind in BANDS:
        svc = services.get(day_kind, set())
        if not svc:
            continue
        rides = acc["ride"][band_name]
        deps = acc["dep"][band_name]
        # A band past 24h (late night) must also catch trips encoded with
        # small after-midnight times: the MTA writes a 1:30am weekday trip as
        # 01:30:00 on the same service day, not 25:30:00. Without the +24h
        # alias, roughly half of overnight service is invisible and late-night
        # headways double.
        def in_band(t):
            return lo <= t < hi or lo <= t + 86400 < hi

        for tid, seq in by_trip.items():
            if trip_service.get(tid) not in svc:
                continue
            route = trip_route[tid]
            direction = trip_dir[tid]
            seq.sort()
            for i in range(len(seq) - 1):
                _, a_sid, _, a_dep = seq[i]
                _, b_sid, b_arr, b_dep = seq[i + 1]
                if a_sid == b_sid:
                    continue
                if not in_band(a_dep):
                    continue
                # Cost to the NEXT departure, not the next arrival: using
                # arrival drops the dwell at every intermediate stop, which
                # compounds to minutes on long rides with scheduled holds.
                # The final stop of a trip has dep == arr, so nothing is
                # overcounted at the end of a journey.
                dt = b_dep - a_dep
                if dt <= 0 or dt > 3600:
                    continue  # drop nonsense / layovers
                rides[(a_sid, b_sid, route, direction)].append(dt)
            # Departures for headway, keyed by direction. A rider going one way
            # only benefits from trips heading that way, so merging directions
            # would halve every headway at a two-directional stop.
            for _, sid, _, dep in seq[:-1]:  # last stop is arrival-only
                if in_band(dep):
                    deps[(sid, route, direction)] += 1
    zf.close()


def main():
    os.makedirs(OUT, exist_ok=True)
    acc = {
        "stops": {},
        "routes": {},
        "stop_kind": {},
        "ride": {b[0]: defaultdict(list) for b in BANDS},
        "dep": {b[0]: defaultdict(int) for b in BANDS},
    }

    log("Downloading feeds")
    paths = {n: fetch(n, u) for n, u in FEEDS.items()}

    for name, path in paths.items():
        process_feed(name, path, FEED_KIND.get(name, 1), acc)

    # ---- index and emit
    stop_keys = sorted(acc["stops"])
    stop_idx = {k: i for i, k in enumerate(stop_keys)}
    route_keys = sorted(acc["routes"])
    route_idx = {k: i for i, k in enumerate(route_keys)}

    out = {
        "meta": {
            "built": date.today().isoformat(),
            "sources": FEEDS,
            "note": "Ride times are medians of scheduled trips. Headways are band duration divided by scheduled departures.",
        },
        "bands": [{"id": b[0], "start": b[1], "end": b[2], "day": b[3]} for b in BANDS],
        "stops": [
            [stop_keys[i], acc["stops"][stop_keys[i]][0],
             round(acc["stops"][stop_keys[i]][1], 6), round(acc["stops"][stop_keys[i]][2], 6),
             acc["stop_kind"].get(stop_keys[i],
                                  FEED_KIND.get(stop_keys[i].split(":", 1)[0], 1))]
            for i in range(len(stop_keys))
        ],
        "routes": [[acc["routes"][k][0], acc["routes"][k][1], acc["routes"][k][2]] for k in route_keys],
        "ride": {},
        "headway": {},
    }

    for band_name, lo, hi, _ in BANDS:
        band_secs = hi - lo
        rides = acc["ride"][band_name]
        out["ride"][band_name] = [
            [stop_idx[a], stop_idx[b], route_idx[r], d, int(round(statistics.median(v))), len(v)]
            for (a, b, r, d), v in rides.items()
            if a in stop_idx and b in stop_idx and r in route_idx
        ]
        deps = acc["dep"][band_name]
        out["headway"][band_name] = [
            [stop_idx[s], route_idx[r], d, int(round(band_secs / n)), n]
            for (s, r, d), n in deps.items()
            if n > 0 and s in stop_idx and r in route_idx
        ]
        log(f"{band_name:20s} ride edges {len(out['ride'][band_name]):7,}   headway entries {len(out['headway'][band_name]):7,}")

    out["meta"]["counts"] = {
        "stops": len(out["stops"]),
        "routes": len(out["routes"]),
        "subway_stops": sum(1 for s in out["stops"] if s[4] == 0),
        "bus_stops": sum(1 for s in out["stops"] if s[4] == 1),
        "ferry_stops": sum(1 for s in out["stops"] if s[4] == 2),
    }

    path = os.path.join(OUT, "transit.json")
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    log(f"\nwrote {path} ({os.path.getsize(path)/1e6:.1f} MB)")
    log(json.dumps(out["meta"]["counts"], indent=2))


if __name__ == "__main__":
    sys.exit(main())
