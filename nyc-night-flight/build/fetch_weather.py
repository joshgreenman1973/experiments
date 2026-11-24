"""Overnight wind and rain over New York City, from Open-Meteo.

Source: Open-Meteo's historical weather API (ERA5 and ECMWF IFS reanalysis),
hourly 10-meter wind and precipitation at Central Park (40.78, -73.97):
    https://archive-api.open-meteo.com/v1/archive
Open-Meteo data are CC BY 4.0. For each night we keep the hours from 7 p.m.
to 6 a.m. local time.

Usage:
  python fetch_weather.py --all
  python fetch_weather.py nightly
"""
import argparse
import datetime as dt
import json
import sys
import time
import urllib.parse
from zoneinfo import ZoneInfo

from common import SRC, FetchError, all_seasons, http_get, read_json, season_key, write_json

NY = ZoneInfo("America/New_York")
LAT, LON = 40.78, -73.97
WX = SRC / "weather"


def fetch_hours(d1, d2):
    q = {"latitude": LAT, "longitude": LON, "start_date": d1.isoformat(), "end_date": d2.isoformat(),
         "hourly": "wind_speed_10m,wind_direction_10m,precipitation",
         "timezone": "America/New_York", "wind_speed_unit": "mph"}
    data = json.loads(http_get("https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(q)))
    time.sleep(1)
    h = data.get("hourly") or {}
    rows = list(zip(h.get("time", []), h.get("wind_speed_10m", []), h.get("wind_direction_10m", []), h.get("precipitation", [])))
    if not rows:
        raise FetchError(f"Open-Meteo returned no hours for {d1}..{d2}")
    return rows


def nights(rows, start, end):
    """Group hours into nights: hours 19-23 of date D and 0-6 of D+1 belong to night D."""
    by = {}
    for t, spd, dirn, rain in rows:
        if spd is None:
            continue
        stamp = dt.datetime.fromisoformat(t)
        hr = stamp.hour
        if hr >= 19:
            night = stamp.date()
        elif hr <= 6:
            night = stamp.date() - dt.timedelta(days=1)
        else:
            continue
        if start <= night <= end:
            by.setdefault(night.isoformat(), []).append([stamp.strftime("%H"), round(spd, 1), dirn, rain])
    return {k: v for k, v in sorted(by.items()) if len(v) >= 10}


def fetch_season(year, name, start, end, force=False):
    key = season_key(year, name)
    path = WX / f"{key}.json"
    old = read_json(path)
    today = dt.datetime.now(NY).date()
    if old and old.get("complete") and not force:
        print(f"{key}: weather already complete")
        return
    last = min(end + dt.timedelta(days=1), today - dt.timedelta(days=1))
    rows = fetch_hours(start, last)
    out = {"season": key, "where": "Central Park (40.78, -73.97)",
           "nights": nights(rows, start, end),
           "complete": today > end + dt.timedelta(days=10),
           "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if not out["nights"]:
        raise FetchError(f"{key}: no complete nights of weather")
    write_json(path, out)
    print(f"{key}: {len(out['nights'])} nights of wind")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="season", choices=["season", "nightly"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--season")
    a = ap.parse_args()
    today = dt.datetime.now(NY).date()
    seasons = all_seasons(today)
    if a.what == "nightly":
        seasons = [s for s in seasons if s[2] <= today <= s[3] + dt.timedelta(days=10)]
        for s in seasons:
            fetch_season(*s, force=True)
        return
    if not a.all:
        seasons = [s for s in seasons if season_key(s[0], s[1]) == a.season]
    for s in seasons:
        fetch_season(*s)


if __name__ == "__main__":
    try:
        main()
    except FetchError as e:
        print(f"FETCH FAILED: {e}", file=sys.stderr)
        sys.exit(1)
