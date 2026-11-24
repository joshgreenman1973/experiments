"""Collect iNaturalist bird sightings in New York City, by day.

Source: iNaturalist API v2, observations of birds (taxon 3, Aves) inside
iNaturalist's "New York City" place (674), "verifiable" quality only:
research grade plus needs-ID, which leaves out captive birds, records with
no photo or sound, and records with no date or place.
    https://api.inaturalist.org/v2/observations?taxon_id=3&place_id=674&verifiable=true&...

Per season we keep, for each day, how many sightings of each species were
reported (subspecies folded into their species) and how many sightings were
not identified down to a species. Species names and photos come from
https://api.inaturalist.org/v1/taxa/<ids>; we keep a photo only when its
license is a Creative Commons one or CC0, with its attribution.

Usage:
  python fetch_inat.py --all             # every season
  python fetch_inat.py --season 2026-fall
  python fetch_inat.py nightly           # refresh the last 30 days in season
"""
import argparse
import datetime as dt
import json
import sys
import time
import urllib.parse
from zoneinfo import ZoneInfo

from common import (SRC, FetchError, all_seasons, http_get, read_json,
                    season_key, write_json)

NY = ZoneInfo("America/New_York")
PLACE_NYC = 674
AVES = 3
PAUSE = 1.1  # iNaturalist asks API users to stay near one request a second
INAT = SRC / "inat"
TAXA = INAT / "taxa.json"
OPEN_LICENSES = {"cc0", "cc-by", "cc-by-nc", "cc-by-sa", "cc-by-nc-sa", "cc-by-nd", "cc-by-nc-nd"}


def ny_today():
    return dt.datetime.now(NY).date()


def fetch_obs(d1, d2):
    """Every verifiable bird observation in NYC observed d1..d2, as
    (observed_on, taxon_id, rank) tuples. Pages by id so nothing shifts."""
    out, id_above, total = [], 0, None
    fields = "(id:!t,observed_on:!t,taxon:(id:!t,rank:!t))"
    while True:
        q = {"taxon_id": AVES, "place_id": PLACE_NYC, "verifiable": "true",
             "d1": d1.isoformat(), "d2": d2.isoformat(), "per_page": 200,
             "order_by": "id", "order": "asc", "id_above": id_above, "fields": fields}
        url = "https://api.inaturalist.org/v2/observations?" + urllib.parse.urlencode(q)
        data = json.loads(http_get(url, accept="application/json"))
        time.sleep(PAUSE)
        if total is None:
            total = data.get("total_results", 0)
        rows = data.get("results") or []
        if not rows:
            break
        for r in rows:
            t = r.get("taxon") or {}
            out.append((r.get("observed_on"), t.get("id"), t.get("rank")))
        id_above = rows[-1]["id"]
    if total and len(out) < total * 0.98:
        raise FetchError(f"iNaturalist: got {len(out)} of {total} observations for {d1}..{d2}")
    return out


def load_taxa(ids):
    taxa = read_json(TAXA, {})
    need = sorted({i for i in ids if i and str(i) not in taxa})
    for k in range(0, len(need), 30):
        chunk = need[k:k + 30]
        url = "https://api.inaturalist.org/v1/taxa/" + ",".join(map(str, chunk)) + "?per_page=30"
        data = json.loads(http_get(url, accept="application/json"))
        time.sleep(PAUSE)
        for t in data.get("results") or []:
            ph = t.get("default_photo") or {}
            lic = (ph.get("license_code") or "").lower()
            taxa[str(t["id"])] = {
                "name": t.get("name"),
                "common": t.get("preferred_common_name"),
                "rank": t.get("rank"),
                "anc": t.get("ancestor_ids") or [],
                "photo": {"url": ph.get("square_url"), "by": ph.get("attribution")} if lic in OPEN_LICENSES and ph.get("square_url") else None,
                "n": t.get("observations_count"),
            }
        missing = [i for i in chunk if str(i) not in taxa]
        if missing:
            raise FetchError(f"iNaturalist taxa lookup missed {missing}")
    write_json(TAXA, dict(sorted(taxa.items(), key=lambda kv: int(kv[0]))))
    return taxa


INFRA = {"subspecies", "variety", "form", "infrahybrid"}


def species_of(tid, taxa):
    """Species id for a taxon at species rank or below, else None."""
    t = taxa.get(str(tid))
    if not t:
        return None
    if t["rank"] == "species":
        return tid
    if t["rank"] in INFRA and t["anc"]:
        # ancestor_ids may or may not end with the taxon itself
        anc = [a for a in t["anc"] if a != tid]
        parent = anc[-1] if anc else None
        pt = taxa.get(str(parent))
        if pt is None or pt["rank"] == "species":
            return parent  # unknown rank yet: checked again after lookup
    return None


def summarize(obs, taxa):
    days = {}
    for day, tid, rank in obs:
        if not day:
            continue
        d = days.setdefault(day, {"sp": {}, "other": 0, "n": 0})
        d["n"] += 1
        sp = species_of(tid, taxa)
        if sp is None:
            d["other"] += 1
        else:
            d["sp"][sp] = d["sp"].get(sp, 0) + 1
    return {k: {"n": v["n"], "other": v["other"],
                "sp": sorted(([int(s), c] for s, c in v["sp"].items()), key=lambda x: (-x[1], x[0]))}
            for k, v in sorted(days.items())}


def fetch_season(year, name, start, end, since=None):
    key = season_key(year, name)
    path = INAT / f"{key}.json"
    old = read_json(path)
    today = ny_today()
    if old and old.get("complete") and since is None:
        print(f"{key}: already complete")
        return old
    if since and not old:
        since = None  # nothing stored yet: take the whole season
    d1 = max(start, since) if since else start
    d2 = min(end, today)
    obs = fetch_obs(d1, d2)
    taxa = load_taxa({o[1] for o in obs})
    # subspecies map to species we may not have looked up yet
    load_taxa({species_of(o[1], taxa) for o in obs if species_of(o[1], taxa)})
    taxa = read_json(TAXA, {})
    for o in obs:  # second pass: every parent is now known
        sp = species_of(o[1], taxa)
        if sp is not None and taxa.get(str(sp), {}).get("rank") != "species":
            raise FetchError(f"taxon {o[1]} folded into non-species {sp}")
    days = summarize(obs, taxa)
    merged = dict(old["days"]) if (old and since) else {}
    for k in list(merged):
        if k >= d1.isoformat():
            del merged[k]
    merged.update(days)
    if not merged:
        raise FetchError(f"{key}: no iNaturalist observations at all")
    out = {"season": key, "days": dict(sorted(merged.items())),
           "complete": today > end + dt.timedelta(days=45),
           "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    write_json(path, out)
    print(f"{key}: {sum(v['n'] for v in merged.values()):,} sightings over {len(merged)} days")
    return out


def nightly():
    today = ny_today()
    for year, name, start, end in all_seasons(today):
        # keep refreshing for 45 days after a season ends: uploads and IDs lag
        if start <= today <= end + dt.timedelta(days=45):
            fetch_season(year, name, start, end, since=today - dt.timedelta(days=30))
            return
    print(f"{today}: no season to refresh")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="season", choices=["season", "nightly"])
    ap.add_argument("--season")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.what == "nightly":
        return nightly()
    seasons = all_seasons(ny_today())
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
