"""Add clock times for the second date each sun map serves.

A map made for Feb 19 also serves Oct 23 (the sun follows nearly the same path), but the clock times differ,
not least because of daylight saving time. This adds, to each two-date state in sun_states.json, the sunrise and
sunset events for its second date, so the page can show the right times for the month the reader picks.
Usage: python sun_times.py SUN_DIR
"""
import sys, json, datetime as dt
from sun import event

SUN = sys.argv[1]
MIRROR = {"jan": (11, 21), "feb": (10, 23), "mar": (9, 23), "apr": (8, 23), "may": (7, 23)}
S = json.load(open(f"{SUN}/sun_states.json"))
for st in S:
    if st["key"] in MIRROR:
        m, d = MIRROR[st["key"]]
        day = dt.date(2026, m, d)
        st["alt"] = {"month": m, "sunrise": event(day, True), "sunset": event(day, False)}
        a, b = st["sunset"], st["alt"]["sunset"]
        print(st["key"], a["date"], a["official"], round(a["official_az"]), "|", b["date"], b["official"], round(b["official_az"]),
              "| rise", st["sunrise"]["official"], st["alt"]["sunrise"]["official"])
json.dump(S, open(f"{SUN}/sun_states.json", "w"), indent=1)
