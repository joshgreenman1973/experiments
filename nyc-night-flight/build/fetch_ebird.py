"""Collect eBird bird reports for New York City, by day.

Source: eBird API 2.0 (Cornell Lab of Ornithology). Needs a free API key in
the EBIRD_API_KEY environment variable. For each borough (county) and day:
    /v2/data/obs/<county>/historic/<y>/<m>/<d>?rank=mrec&detail=simple&cat=species
lists the species reported that day, one record per species. Species don't
add up across boroughs (the same species in two boroughs is one species), so
the citywide list is the union of the five borough lists.

eBird allows 500 requests an hour per key (bursts of 25 in 5 seconds), so:
  - one request per borough per day (5 a day)
  - each run spends at most CALL_BUDGET requests (default 450)
  - the daily job first refreshes recent days (uploads lag), then spends what
    is left filling in older seasons, newest first, so the full history
    arrives over a couple of weeks of runs
  - when eBird says the hour's quota is used up, the run saves and stops
    cleanly; with --patient it waits for the quota to come back instead

eBird's terms ask for attribution and restrict passing the data along in its
original form, so only a daily summary is stored: for each species, the
boroughs where it was reported. (Days fetched early on also carry checklist
counts from /v2/product/stats; the page does not use them.)

Usage:
  EBIRD_API_KEY=... python fetch_ebird.py nightly            # the daily job
  EBIRD_API_KEY=... python fetch_ebird.py backfill --patient [--seasons N]  # local, waits out the quota
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

import common
from common import BOROUGHS, SRC, FetchError, all_seasons, daterange, read_json, season_key, write_json

NY = ZoneInfo("America/New_York")
EB = SRC / "ebird"
TAXA = EB / "taxa.json"
MIN_GAP = 0.3          # seconds between requests: under the 25-in-5-seconds burst limit
CALL_BUDGET = int(os.environ.get("EBIRD_CALL_BUDGET", "450"))
RECENT_DAYS = 14       # refreshed every run in and just after a season
AFTER_SEASON = 45      # days after a season ends that recent days keep being refreshed


class QuotaUsed(Exception):
    pass


class Client:
    def __init__(self, patient=False):
        k = os.environ.get("EBIRD_API_KEY", "").strip()
        if not k:
            raise FetchError("EBIRD_API_KEY is not set")
        self.key, self.patient, self.calls, self.last = k, patient, 0, 0.0

    def get(self, path):
        if self.calls >= CALL_BUDGET and not self.patient:
            raise QuotaUsed(f"used this run's budget of {CALL_BUDGET} requests")
        url = "https://api.ebird.org/v2/" + path
        last, attempt = None, 0
        while attempt < 6:
            wait = self.last + MIN_GAP - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            self.calls += 1
            try:
                req = urllib.request.Request(url, headers={"X-eBirdApiToken": self.key, "User-Agent": common.UA})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last = e
                if e.code == 429:
                    hourly_gone = '"policy";r=0' in (e.headers.get("ratelimit") or "")
                    retry = int(e.headers.get("retry-after") or 5)
                    if hourly_gone:
                        if not self.patient:
                            raise QuotaUsed("eBird's hourly quota is used up")
                        print("eBird hourly quota used up; waiting 10 minutes", flush=True)
                        time.sleep(600)
                    else:
                        time.sleep(retry + 1)
                    continue  # throttling doesn't count as a failed attempt
                if e.code in (400, 401, 403, 404):
                    break
                attempt += 1
                time.sleep(5 * attempt)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
                attempt += 1
                time.sleep(5 * attempt)
        raise FetchError(f"eBird {path}: {last}")


def one_day(client, day):
    out, names = {"sp": {}}, {}
    for code, _ in BOROUGHS:
        recs = client.get(f"data/obs/{code}/historic/{day.year}/{day.month}/{day.day}"
                          "?rank=mrec&detail=simple&cat=species&maxResults=10000")
        for r in recs:
            sc = r["speciesCode"]
            out["sp"].setdefault(sc, []).append(code[-3:])
            names[sc] = [r.get("comName"), r.get("sciName")]
    return out, names


def season_days(start, end, today):
    last = min(end + dt.timedelta(days=1), today - dt.timedelta(days=1))  # +1: the morning after the last night
    return list(daterange(start, last))


def save(skey, store, start, end, today, fetched=None):
    days = season_days(start, end, today)
    have_all = all(d.isoformat() in store for d in days)
    out = {"season": skey, "days": dict(sorted(store.items())),
           "complete": have_all and today > end + dt.timedelta(days=AFTER_SEASON),
           "allDays": have_all}
    old = read_json(EB / f"{skey}.json") or {}
    out["fetched"] = fetched or old.get("fetched")
    write_json(EB / f"{skey}.json", out)


def run(client, recent=True, newest=None):
    today = dt.datetime.now(NY).date()
    taxa = read_json(TAXA, {})
    seasons = all_seasons(today)[::-1]  # newest first
    if newest:
        seasons = seasons[:newest]
    plan = []
    if recent:
        for year, name, start, end in seasons:
            if start <= today <= end + dt.timedelta(days=AFTER_SEASON):
                days = season_days(start, end, today)
                plan += [(year, name, start, end, d, True) for d in days[-RECENT_DAYS:]]
    for year, name, start, end in seasons:
        store = (read_json(EB / f"{season_key(year, name)}.json") or {}).get("days", {})
        plan += [(year, name, start, end, d, False) for d in season_days(start, end, today) if d.isoformat() not in store]

    stores, done, stopped, recent_ok = {}, 0, None, True
    try:
        for year, name, start, end, day, is_recent in plan:
            skey = season_key(year, name)
            if skey not in stores:
                stores[skey] = ((read_json(EB / f"{skey}.json") or {}).get("days", {}), start, end)
            store = stores[skey][0]
            if not is_recent and day.isoformat() in store:
                continue
            try:
                store[day.isoformat()], names = one_day(client, day)
            except QuotaUsed:
                if is_recent:
                    recent_ok = False
                raise
            taxa.update({k: v for k, v in names.items() if k not in taxa})
            done += 1
            if done % 10 == 0:
                for k, (st, s0, s1) in stores.items():
                    save(k, st, s0, s1, today)
                write_json(TAXA, dict(sorted(taxa.items())))
                print(f"{done} days fetched ({client.calls} requests), latest {skey} {day}", flush=True)
    except QuotaUsed as e:
        stopped = str(e)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for k, (st, s0, s1) in stores.items():
        save(k, st, s0, s1, today, fetched=stamp)
    write_json(TAXA, dict(sorted(taxa.items())))
    left = 0
    for year, name, start, end in seasons:
        st = (read_json(EB / f"{season_key(year, name)}.json") or {}).get("days", {})
        left += sum(1 for d in season_days(start, end, today) if d.isoformat() not in st)
    print(f"fetched {done} days with {client.calls} requests; {left} days still to fill"
          + (f"; stopped: {stopped}" if stopped else ""), flush=True)
    if not recent_ok:
        raise FetchError("eBird quota ran out before the recent days were refreshed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["nightly", "backfill"])
    ap.add_argument("--patient", action="store_true", help="wait out eBird's hourly quota instead of stopping")
    ap.add_argument("--seasons", type=int, help="only the newest N seasons")
    a = ap.parse_args()
    run(Client(patient=a.patient), recent=(a.what == "nightly"), newest=a.seasons)


if __name__ == "__main__":
    try:
        main()
    except FetchError as e:
        print(f"FETCH FAILED: {e}", file=sys.stderr)
        sys.exit(1)
