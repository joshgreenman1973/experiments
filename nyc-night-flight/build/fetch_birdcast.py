"""Collect BirdCast's radar migration estimates for the five boroughs.

Source: the BirdCast Migration Dashboard (Cornell Lab of Ornithology,
Colorado State University, UMass Amherst), one page per county per night:
    https://dashboard.birdcast.org/region/<county code>?night=<YYYY-MM-DD>
Each page carries its numbers inside the HTML (window.__NUXT__). We read
two things from it:
  - migrationLiveDataFromApi.nightSeries: birds in flight every 10 minutes
    that night, with flight direction, speed and altitude
  - migrationHistDataFromApi.season: running totals of birds that crossed
    the county, night by night, for that season and for BirdCast's
    historical average

Usage:
  python fetch_birdcast.py totals --all          # season totals, every season
  python fetch_birdcast.py curves --season 2026-fall
  python fetch_birdcast.py nightly               # what the daily job runs
"""
import argparse
import datetime as dt
import sys
import time
from zoneinfo import ZoneInfo

from common import (BOROUGHS, SRC, FetchError, all_seasons, daterange, http_get,
                    read_json, season_key, write_json)
from nuxt_parse import parse_nuxt

NY = ZoneInfo("America/New_York")
PAUSE = 1.5  # seconds between page requests; be gentle with BirdCast
STALE_AFTER_DAYS = 3

TOTALS = SRC / "birdcast" / "totals"
CURVES = SRC / "birdcast" / "curves"


def page(code, night):
    url = f"https://dashboard.birdcast.org/region/{code}?night={night.isoformat()}"
    html = http_get(url, accept="text/html")
    data = parse_nuxt(html)
    region = (data.get("fetch") or {}).get("Region:0")
    if not region:
        raise FetchError(f"{url}: no Region data in page")
    got = (region.get("region") or {}).get("code")
    if got != code:
        raise FetchError(f"{url}: page is for {got!r}, not {code}")
    time.sleep(PAUSE)
    return region


def cum_series(series):
    return [[s["dateTime"][:10], s.get("totalBirds")] for s in (series or [])]


def season_totals_from(region):
    hist = region.get("migrationHistDataFromApi") or {}
    season = hist.get("season") or {}
    return {
        "cum": cum_series(season.get("currentSeasonSeries")),
        "hist_cum": cum_series(season.get("annualAvgSeries")),
    }


def night_from(region, night):
    live = region.get("migrationLiveDataFromApi") or {}
    series = live.get("nightSeries") or []
    rows = []
    for p in series:
        t = (p.get("localTime") or "")[11:16]
        def r(v, nd=0):
            return None if v is None else round(v, nd) if nd else round(v)
        rows.append([t, p.get("numAloft"), r(p.get("avgDirection")), r(p.get("avgSpeed"), 1),
                     r(p.get("meanHeight")), r(p.get("maxHeight"))])
    return {
        "total": live.get("cumulativeBirds") if series else None,
        "high": bool(live.get("isHigh")),
        "s": rows,
        "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def ny_today():
    return dt.datetime.now(NY).date()


def find_season(key):
    for year, name, start, end in all_seasons(ny_today()):
        if season_key(year, name) == key:
            return year, name, start, end
    raise SystemExit(f"unknown season {key}")


def fetch_totals(year, name, start, end, force=False):
    key = season_key(year, name)
    path = TOTALS / f"{key}.json"
    old = read_json(path)
    last_night = min(end, ny_today() - dt.timedelta(days=1))
    if old and not force and old.get("complete"):
        print(f"{key}: totals already complete")
        return old
    out = {"season": key, "start": start.isoformat(), "end": end.isoformat(),
           "through": last_night.isoformat(), "boroughs": {}}
    for code, borough in BOROUGHS:
        region = page(code, last_night)
        tot = season_totals_from(region)
        if not tot["cum"]:
            raise FetchError(f"{key} {borough}: BirdCast returned no season totals")
        out["boroughs"][code] = tot
        print(f"{key} {borough}: {len(tot['cum'])} nights, season total {tot['cum'][-1][1]:,.0f}")
    out["complete"] = ny_today() > end + dt.timedelta(days=3)
    out["fetched"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    write_json(path, out)
    return out


def fetch_curves(year, name, start, end, since=None, refresh_days=2):
    """Ten-minute series for each night of a season. Skips nights already
    stored unless they were fetched within refresh_days of the night itself
    (BirdCast can fill in a night the next morning)."""
    key = season_key(year, name)
    path = CURVES / f"{key}.json"
    store = read_json(path, {})
    last_night = min(end, ny_today() - dt.timedelta(days=1))
    first = max(start, since) if since else start
    fetched = 0
    newest_region = None
    for night in daterange(first, last_night):
        nk = night.isoformat()
        for code, borough in BOROUGHS:
            have = store.get(nk, {}).get(code)
            if have:
                f = dt.datetime.fromisoformat(have["fetched"]).astimezone(NY).date()
                if (f - night).days > refresh_days or have["s"]:
                    continue
            region = page(code, night)
            store.setdefault(nk, {})[code] = night_from(region, night)
            fetched += 1
            if night == last_night:
                newest_region = newest_region or {}
                newest_region[code] = region
        if fetched and fetched % 25 == 0:
            write_json(path, store)  # save as we go on long backfills
            print(f"{key}: through {nk}, {fetched} pages")
    write_json(path, dict(sorted(store.items())))
    print(f"{key}: {fetched} new pages, {len(store)} nights stored")
    return store, newest_region


def nightly():
    """Daily job: in season, add last night for every borough and refresh
    the season's running totals. Off season, do nothing. Fails loudly when
    the newest stored night is too old."""
    today = ny_today()
    current = None
    for year, name, start, end in all_seasons(today):
        if start <= today <= end + dt.timedelta(days=3):
            current = (year, name, start, end)
    if not current:
        print(f"{today}: outside BirdCast's live seasons; nothing to fetch")
        return
    year, name, start, end = current
    since = max(start, today - dt.timedelta(days=4))
    store, newest = fetch_curves(year, name, start, end, since=since)
    fetch_totals(year, name, start, end, force=True)

    nights_with_data = [n for n, b in store.items() if any(v.get("s") for v in b.values())]
    newest_night = max(nights_with_data) if nights_with_data else None
    expected = min(end, today - dt.timedelta(days=1))
    if newest_night is None or (expected - dt.date.fromisoformat(newest_night)).days >= STALE_AFTER_DAYS:
        raise SystemExit(f"STALE: newest BirdCast night with data is {newest_night}, expected {expected}")
    print(f"newest night with data: {newest_night}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["totals", "curves", "nightly"])
    ap.add_argument("--season")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.what == "nightly":
        return nightly()
    seasons = all_seasons(ny_today()) if a.all else [find_season(a.season)]
    for s in seasons:
        if a.what == "totals":
            fetch_totals(*s, force=a.force)
        else:
            fetch_curves(*s)


if __name__ == "__main__":
    try:
        main()
    except FetchError as e:
        print(f"FETCH FAILED: {e}", file=sys.stderr)
        sys.exit(1)
