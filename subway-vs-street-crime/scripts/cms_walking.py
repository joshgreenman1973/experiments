"""Walking inputs from NYC DOT's 2024 Citywide Mobility Survey microdata.

Trip table wgnh-qwsg, day table naav-ygga (NYC Open Data). Weights are the
citywide weights; per the 2024 user guide the day weights sum to adult
residents on an average day and trip weights sum to their trips that day.
Trip records are *unlinked*: a subway trip is split into walk-access,
subway and walk-egress legs, each a record with its own mode_type
(1 = walk). That lets us measure walk-only trips (the original Method 1)
and walk legs to and from transit separately.

Usage: python3 -I cms_walking.py OUTDIR   (writes cms_walking.json)
"""
import json, sys, time, urllib.parse, urllib.request, pathlib, statistics

TRIP = "https://data.cityofnewyork.us/resource/wgnh-qwsg.json"
DAY = "https://data.cityofnewyork.us/resource/naav-ygga.json"


def get(url, params):
    u = url + "?" + urllib.parse.urlencode(params)
    for a in range(8):
        try:
            with urllib.request.urlopen(u, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(5 * (a + 1)); continue
            raise
    raise RuntimeError(u)


def page(url, select):
    out, off = [], 0
    while True:
        rows = get(url, {"$select": select, "$limit": 50000, "$offset": off, "$order": ":id"})
        out += rows
        if len(rows) < 50000:
            return out
        off += 50000


days = page(DAY, "travel_dow,day_weight_citywide")
trips = page(TRIP, "travel_dow,n_legs,leg_num,mode_type,duration_minutes,"
                   "transit_quality_flag,trip_weight_citywide")
if not days or not trips:
    raise SystemExit("FAIL: empty survey pull")

f = lambda x: float(x) if x not in (None, "") else None
WEEKEND = {"6", "7"}  # travel_dow: 1 = Monday ... 7 = Sunday


def summarize(keep):
    dw = sum(f(d["day_weight_citywide"]) for d in days if keep(d["travel_dow"]))
    ts = [t for t in trips if keep(t["travel_dow"])]
    w = lambda t: f(t["trip_weight_citywide"]) or 0.0
    linked = [t for t in ts if t["n_legs"] == "1" or t["leg_num"] == "1"]
    walk_only = [t for t in ts if t["n_legs"] == "1" and t["mode_type"] == "1"]
    walk_legs = [t for t in ts if t["n_legs"] != "1" and t["mode_type"] == "1"]

    def minutes(group):
        # Synthetic access/egress legs carry no duration; give them the
        # weighted mean of the timed legs in the same group.
        timed = [(w(t), f(t["duration_minutes"])) for t in group if f(t["duration_minutes"]) is not None]
        mean = sum(a * b for a, b in timed) / sum(a for a, _ in timed)
        tot = sum(w(t) * (f(t["duration_minutes"]) if f(t["duration_minutes"]) is not None else mean) for t in group)
        med = statistics.median(b for _, b in timed)
        return mean, med, tot

    wo_mean, wo_med, wo_tot = minutes(walk_only)
    wl_mean, wl_med, wl_tot = minutes(walk_legs)
    return {
        "adult_days_weighted": dw,
        "linked_trips_per_adult_day": sum(map(w, linked)) / dw,
        "walk_only_share_of_linked_trips": sum(map(w, walk_only)) / sum(map(w, linked)),
        "walk_only_trips_per_adult_day": sum(map(w, walk_only)) / dw,
        "walk_only_mean_minutes": wo_mean, "walk_only_median_minutes": wo_med,
        "walk_only_minutes_per_adult_day": wo_tot / dw,
        "transit_walk_legs_per_adult_day": sum(map(w, walk_legs)) / dw,
        "transit_walk_leg_mean_minutes": wl_mean, "transit_walk_leg_median_minutes": wl_med,
        "transit_walk_minutes_per_adult_day": wl_tot / dw,
        "n_trip_records": len(ts),
    }


out = {
    "source": "NYC DOT Citywide Mobility Survey 2024 (wgnh-qwsg trips, naav-ygga days), citywide weights",
    "pulled": time.strftime("%Y-%m-%d"),
    "all_days": summarize(lambda d: True),
    "weekday": summarize(lambda d: d not in WEEKEND),
    "weekend": summarize(lambda d: d in WEEKEND),
}
pathlib.Path(sys.argv[1], "cms_walking.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
