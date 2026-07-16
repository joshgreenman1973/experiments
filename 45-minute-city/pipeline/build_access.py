#!/usr/bin/env python3
"""Build the accessibility layer: which subway stations are ADA-accessible, and
how long a wheelchair-accessible vehicle (WAV) actually takes to arrive.

Station accessibility comes from the MTA's own station list. WAV waits are
measured, not assumed: the TLC high-volume FHV file (Uber/Lyft) records a
request timestamp, a WAV-request flag and a pickup timestamp for every ride in
the city, so the wait is the median request-to-pickup gap over every accessible
vehicle actually requested in the month, per time-of-day band. The standard
(non-WAV) wait is computed alongside for contrast.

Sources:
  stations  https://data.ny.gov/resource/39hk-dx4f.json (MTA Subway Stations)
  fhv trips https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet
"""
import json
import os
import sys
import urllib.request
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "out")

MONTH = "2026-03"  # matches the taxi calibration month
STATIONS_URL = "https://data.ny.gov/resource/39hk-dx4f.json?$select=gtfs_stop_id,stop_name,ada,ada_northbound,ada_southbound&$limit=600"
FHV_URL = f"https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{MONTH}.parquet"

BANDS = [
    ("weekday_am_peak", 7, 10, "weekday"),
    ("weekday_midday", 10, 16, "weekday"),
    ("weekday_pm_peak", 16, 19, "weekday"),
    ("weekday_evening", 19, 23, "weekday"),
    ("weekday_late", 23, 29, "weekday"),
    ("saturday_midday", 10, 18, "saturday"),
    ("sunday_midday", 10, 18, "sunday"),
]


def log(m):
    print(m, flush=True)


def fetch(url, name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        log(f"  cached  {name} ({os.path.getsize(path)/1e6:.1f} MB)")
        return path
    log(f"  fetching {name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "45-minute-city/1.0"})
    with urllib.request.urlopen(req, timeout=1800) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 22)
            if not chunk:
                break
            f.write(chunk)
    log(f"  fetched  {name} ({os.path.getsize(path)/1e6:.1f} MB)")
    return path


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- ADA stations
    log("MTA station accessibility")
    path = fetch(STATIONS_URL, "mta_stations.json")
    rows = json.load(open(path))
    ada = {}
    for r in rows:
        gid = (r.get("gtfs_stop_id") or "").strip()
        if not gid:
            continue
        try:
            flag = int(r.get("ada") or 0)
        except ValueError:
            flag = 0
        # 0 = not accessible, 1 = fully accessible, 2 = partially (one direction)
        ada[gid] = flag
    n_full = sum(1 for v in ada.values() if v == 1)
    n_part = sum(1 for v in ada.values() if v == 2)
    log(f"  {len(ada)} stations: {n_full} fully accessible, {n_part} partially, "
        f"{len(ada)-n_full-n_part} not")

    # ---- WAV waits from the high-volume FHV file
    log("FHV trip records (this file is large)")
    import numpy as np
    import pyarrow.parquet as pq

    fp = fetch(FHV_URL, f"fhvhv_{MONTH}.parquet")
    tab = pq.read_table(fp, columns=["request_datetime", "pickup_datetime", "wav_request_flag"])
    log(f"  {tab.num_rows:,} FHV trips in {MONTH}")

    req = tab["request_datetime"].to_numpy()
    pick = tab["pickup_datetime"].to_numpy()
    wav = np.array(tab["wav_request_flag"].to_pylist()) == "Y"

    wait = (pick - req) / np.timedelta64(1, "s")
    ok = (wait >= 0) & (wait <= 3600) & ~np.isnat(pick) & ~np.isnat(req)

    # local clock -> service day + shifted hour, matching the other pipelines
    req_local = req.astype("datetime64[s]")
    hours = (req_local.astype("datetime64[h]") - req_local.astype("datetime64[D]")).astype(int)
    svc = (req_local - np.timedelta64(5, "h")).astype("datetime64[D]")
    dow = (svc.astype("datetime64[D]").view("int64") + 4) % 7  # 1970-01-01 was a Thursday
    shifted = np.where(hours >= 5, hours, hours + 24)
    daykind = np.where(dow <= 4, 0, np.where(dow == 5, 1, 2))  # 0 wk, 1 sat, 2 sun
    DK = {"weekday": 0, "saturday": 1, "sunday": 2}

    out_bands = {}
    log("  Median request-to-pickup wait (minutes):")
    log(f"  {'band':20s} {'WAV':>8s} {'n WAV':>9s} {'standard':>9s} {'n std':>11s}")
    for name, lo, hi, dkind in BANDS:
        in_band = ok & (daykind == DK[dkind]) & (shifted >= lo) & (shifted < hi)
        w = wait[in_band & wav]
        s = wait[in_band & ~wav]
        if len(w) < 100:
            log(f"  {name:20s} INSUFFICIENT ({len(w)})")
            continue
        out_bands[name] = {
            "wav_wait_secs": int(np.median(w)),
            "wav_p75_secs": int(np.percentile(w, 75)),
            "wav_n": int(len(w)),
            "standard_wait_secs": int(np.median(s)),
            "standard_n": int(len(s)),
        }
        log(f"  {name:20s} {np.median(w)/60:7.1f} {len(w):9,} {np.median(s)/60:8.1f} {len(s):11,}")

    result = {
        "month": MONTH,
        "stations": {gid: flag for gid, flag in ada.items() if flag > 0},
        "counts": {"fully_accessible": n_full, "partially_accessible": n_part, "total": len(ada)},
        "wav": out_bands,
        "note": (
            "Station flags from the MTA's station list (1 fully accessible, 2 one "
            "direction only; treated as accessible with the caveat documented). "
            "WAV waits are median request-to-pickup gaps over every "
            "wheelchair-accessible-vehicle request in the month's TLC "
            "high-volume FHV records. Access-A-Ride is absent because it books "
            "by 5pm the previous day and so cannot appear in a turn-up-and-go map."
        ),
    }
    p = os.path.join(OUT, "access.json")
    json.dump(result, open(p, "w"), separators=(",", ":"))
    log(f"wrote {p} ({os.path.getsize(p)/1e3:.1f} KB)")


if __name__ == "__main__":
    sys.exit(main())
