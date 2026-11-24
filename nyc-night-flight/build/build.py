"""Turn the raw pulls in data/src into the files the page reads.

  data/index.json            seasons, per-borough season totals, biggest nights
  data/season/<key>.json     nightly totals, historical average, wind, sightings
  data/curves/<key>.json     ten-minute flight detail (seasons that have it)

Nightly BirdCast totals are differences of BirdCast's running season totals.
The historical average is the same difference taken on BirdCast's
"annualAvgSeries". Sightings are matched to the morning after each night:
night D (evening of D into the morning of D+1) pairs with sightings dated D+1.
"""
import datetime as dt
import math

from common import BOROUGHS, OUT, SRC, all_seasons, daterange, read_json, season_key, write_json

SEASON_LABEL = {"spring": "Spring", "fall": "Fall"}
NEW_AFTER_DAYS = 14  # don't call anything a new arrival in a season's first two weeks


def diffs(cum, dates):
    by = {d: v for d, v in cum}
    out, prev = [], 0.0
    for d in dates:
        v = by.get(d)
        if v is None:
            out.append(None)
            continue
        out.append(max(0, round(v - prev)))
        prev = v
    return out


def fill_times(rows):
    """BirdCast marks a missed radar scan with an empty time and no values.
    Give it the time it should have had (10 minutes after the row before,
    or before the row after) so the page can show a gap there."""
    rows = [list(r) for r in rows]
    def shift(t, mins):
        h, m = map(int, t.split(":"))
        x = (h * 60 + m + mins) % 1440
        return f"{x // 60:02d}:{x % 60:02d}"
    for i, r in enumerate(rows):
        if r[0]:
            continue
        if i and rows[i - 1][0]:
            r[0] = shift(rows[i - 1][0], 10)
        else:
            nxt = next((j for j in range(i + 1, len(rows)) if rows[j][0]), None)
            if nxt is not None:
                r[0] = shift(rows[nxt][0], -10 * (nxt - i))
    return rows


def wind_summary(hours):
    if not hours:
        return None
    u = v = 0.0
    spd_sum = rain = 0.0
    for _, spd, dirn, r in hours:
        rad = math.radians(dirn)
        u += -spd * math.sin(rad)
        v += -spd * math.cos(rad)
        spd_sum += spd
        rain += r or 0
    n = len(hours)
    frm = (math.degrees(math.atan2(-u / n, -v / n)) + 360) % 360
    return {"from": round(frm), "mph": round(spd_sum / n, 1),
            "steady": round(math.hypot(u / n, v / n) / (spd_sum / n), 2) if spd_sum else 0,
            "rain": round(rain, 1)}


def build_season(year, name, start, end, taxa):
    key = season_key(year, name)
    tot = read_json(SRC / "birdcast" / "totals" / f"{key}.json")
    if not tot:
        return None
    dates = [d.isoformat() for d in daterange(start, end)]
    birdcast = {}
    for code, _ in BOROUGHS:
        b = tot["boroughs"][code]
        birdcast[code] = {"night": diffs(b["cum"], dates), "avg": diffs(b["hist_cum"], dates)}
    through = tot.get("through")
    last = dates.index(through) + 1 if through in dates else len(dates)
    for code in birdcast:  # nights after "through" are not measured yet
        birdcast[code]["night"] = birdcast[code]["night"][:last] + [None] * (len(dates) - last)

    wx = (read_json(SRC / "weather" / f"{key}.json") or {}).get("nights", {})
    wind = [wind_summary(wx.get(d)) for d in dates]
    wind_hours = [[[h[0], h[1], h[2]] for h in wx.get(d, [])] for d in dates]

    inat = (read_json(SRC / "inat" / f"{key}.json") or {}).get("days", {})
    eb_file = read_json(SRC / "ebird" / f"{key}.json") or {}
    eb = eb_file.get("days", {})
    eb_names = read_json(SRC / "ebird" / "taxa.json", {})
    by_sci = {(v.get("name") or "").lower(): v for v in taxa.values()}
    seen, morning, used, used_eb = set(), [], set(), set()
    for i, d in enumerate(dates):
        nxt = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
        day, ebd = inat.get(nxt), eb.get(nxt)
        if not day and not ebd:
            morning.append(None)
            continue
        m = {"date": nxt}
        if day:
            new = [s for s, _ in day["sp"] if s not in seen]
            seen.update(s for s, _ in day["sp"])
            used.update(s for s, _ in day["sp"])
            m.update({"n": day["n"], "other": day["other"], "sp": day["sp"],
                      "new": new if i >= NEW_AFTER_DAYS else []})
        if ebd:
            sp = sorted(ebd["sp"].items(), key=lambda kv: (-len(kv[1]), kv[0]))
            used_eb.update(sc for sc, _ in sp)
            m["eb"] = {"sp": [[sc, ",".join(sorted(b))] for sc, b in sp]}
        morning.append(m)
    sp_taxa = {}
    for s in sorted(used):
        t = taxa.get(str(s)) or {}
        sp_taxa[s] = [t.get("common") or t.get("name"), t.get("name"),
                      (t.get("photo") or {}).get("url"), (t.get("photo") or {}).get("by")]
    eb_taxa = {}
    for sc in sorted(used_eb):
        com, sci = eb_names.get(sc, [sc, None])
        t = by_sci.get((sci or "").lower()) or {}
        eb_taxa[sc] = [com, sci, (t.get("photo") or {}).get("url"), (t.get("photo") or {}).get("by")]

    curves = read_json(SRC / "birdcast" / "curves" / f"{key}.json") or {}
    has_curves = sorted(d for d, b in curves.items() if any(v.get("s") for v in b.values()))
    if curves:
        slim = {d: {c: {"t": v["total"], "s": fill_times(v["s"])} for c, v in b.items() if v.get("s")}
                for d, b in sorted(curves.items())}
        write_json(OUT / "curves" / f"{key}.json", {k: v for k, v in slim.items() if v})

    season = {"key": key, "label": f"{SEASON_LABEL[name]} {year}", "start": start.isoformat(),
              "end": end.isoformat(), "through": through, "dates": dates,
              "birdcast": birdcast, "wind": wind, "windHours": wind_hours,
              "morning": morning, "taxa": sp_taxa, "ebTaxa": eb_taxa,
              "ebComplete": bool(eb_file.get("allDays")), "curveNights": has_curves}
    write_json(OUT / "season" / f"{key}.json", season)

    # summary for the index
    totals = {c: sum(x for x in birdcast[c]["night"] if x) for c in birdcast}
    avg_totals = {c: sum(x for x in birdcast[c]["avg"][:last] if x) for c in birdcast}
    combined = [sum((birdcast[c]["night"][i] or 0) for c in birdcast) for i in range(len(dates))]
    top = sorted(range(len(dates)), key=lambda i: -combined[i])[:5]
    return {"key": key, "label": season["label"], "start": season["start"], "end": season["end"],
            "through": through, "complete": bool(tot.get("complete")),
            "totals": totals, "avgTotals": avg_totals,
            "top": [{"night": dates[i], "by": {c: birdcast[c]["night"][i] for c in birdcast}} for i in top],
            "sightings": sum(v["n"] for v in inat.values()),
            "species": len({sp for v in inat.values() for sp, _ in v["sp"]}),
            "ebComplete": bool(eb_file.get("allDays")),
            "ebSpecies": len({sc for k, v in eb.items() if start.isoformat() <= k <= end.isoformat() for sc in v["sp"]}),
            "hasCurves": bool(has_curves)}


def main():
    taxa = read_json(SRC / "inat" / "taxa.json", {})
    seasons = []
    for s in all_seasons():
        r = build_season(*s, taxa)
        if r:
            seasons.append(r)
    if not seasons:
        raise SystemExit("no seasons built")
    newest = {}
    for k in ("birdcast/totals", "inat", "ebird", "weather"):
        stamps = [(read_json(p) or {}).get("fetched") for p in (SRC / k).glob("*.json")]
        newest[k.split("/")[0]] = max([s for s in stamps if s] or [None])
    write_json(OUT / "index.json", {
        "boroughs": [{"code": c, "name": n} for c, n in BOROUGHS],
        "seasons": seasons[::-1],
        "fetched": newest,
        # cache key for the page's data requests; not shown to readers
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }, indent=1)
    print(f"built {len(seasons)} seasons")


if __name__ == "__main__":
    main()
