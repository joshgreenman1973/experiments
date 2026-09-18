#!/usr/bin/env python3
"""Outlier measures for every indicator, computed once at build time.

Each measure answers a different question, and they disagree on purpose. An
indicator can be the year's biggest percentage move and still be unremarkable
against its own ten-year record; another can barely move and still be the
worst reading the city has ever published. The site lets a reader sort by any
of them, so all of them ship.

Direction: the city labels most indicators Up or Down for the direction it
wants. Every change here is also stored signed so that positive means "moved
the way the city says it should," which is the only way to compare a falling
response time against a rising completion rate.
"""
import math, statistics


def _rel(a, b):
    """Relative change from a to b, or None when it would not mean anything."""
    if a is None or b is None or a == 0:
        return None
    return (b - a) / abs(a)


def suspect(vals, years, is_pct):
    """Published figures that cannot be what the label says they are.

    Two kinds turn up in this dataset. A percentage filed as 184112. And a
    single year in a series filed at the raw scale when every other year is
    filed in thousands. Neither is corrected here -- the series is published
    as the city published it -- but both are labelled, because an unflagged
    one wrecks every ranking it touches.

    A percentage above 100 is NOT flagged. Plenty of these indicators measure
    performance against a target -- pruning goal completed, revenue as percent
    of target -- and clearing the target is the whole point.
    """
    pairs = [(y, v) for y, v in zip(years, vals) if v is not None]
    if not pairs:
        return None
    out = {}
    if is_pct:
        for y, v in pairs:
            if v < -100 or v > 1000:
                out[str(y)] = "impossible as a percentage"
    if len(pairs) >= 4:
        mags = sorted((abs(v) for _, v in pairs), reverse=True)
        rest = mags[1:]
        med = statistics.median(rest) if rest else 0
        second = rest[0] if rest else 0
        top = mags[0]
        if med > 0 and top >= 50 * med and top >= 20 * max(second, 1e-9):
            for y, v in pairs:
                if abs(v) == top:
                    out.setdefault(str(y), "orders of magnitude above every other year")
    return out or None


def series_stats(vals, years, direction, is_pct):
    """vals is year-aligned with nulls. Returns a dict, or None if too sparse."""
    pairs = [(y, v) for y, v in zip(years, vals) if v is not None]
    if len(pairs) < 2:
        return None
    ys = [y for y, _ in pairs]
    vs = [v for _, v in pairs]
    last_y, last = pairs[-1]
    prev_y, prev = pairs[-2]
    first_y, first = pairs[0]

    d1 = _rel(prev, last)
    dA = _rel(first, last)
    p1 = last - prev
    pA = last - first

    out = {
        "ly": last_y, "lv": round(last, 4),
        "py": prev_y, "pv": round(prev, 4),
        "fy": first_y, "fv": round(first, 4),
        "n": len(vs),
    }
    if d1 is not None:
        out["d1"] = round(d1, 6)
    if dA is not None:
        out["dA"] = round(dA, 6)
    out["p1"] = round(p1, 4)
    out["pA"] = round(pA, 4)

    # Where the latest reading sits against the indicator's own history.
    prior = vs[:-1]
    if len(prior) >= 4:
        mu = statistics.fmean(prior)
        sd = statistics.pstdev(prior)
        if sd > 0:
            out["z"] = round((last - mu) / sd, 3)
        out["hi"] = round(max(prior), 4)
        out["lo"] = round(min(prior), 4)
        if last > max(prior):
            out["rec"] = 1          # highest reading on record
        elif last < min(prior):
            out["rec"] = -1         # lowest reading on record

    # A base near zero turns an ordinary move into a four-figure percentage.
    # Flag it rather than hide it: the change is arithmetically right and the
    # reader can decide, but it should never top a list by accident.
    med = statistics.median([abs(v) for v in vs]) or 0
    if abs(prev) < max(1.0, 0.05 * med):
        out["lowbase"] = 1
    # A one-year move of 100 per cent or more. Occasionally real, far more
    # often a redefinition, a recount or a restated scale.
    if d1 is not None and abs(d1) >= 1.0:
        out["bigstep"] = 1

    # How much this indicator swings, full stop. Series that sit at zero most
    # years produce meaningless ratios, so they are left out.
    if len(vs) >= 4 and sum(1 for v in vs if v != 0) >= len(vs) / 2:
        mu_all = statistics.fmean(vs)
        if mu_all != 0:
            out["cv"] = round(statistics.pstdev(vs) / abs(mu_all), 4)

    # Consecutive years moving the same way, ending at the latest reading.
    st = 0
    for i in range(len(vs) - 1, 0, -1):
        if ys[i] != ys[i - 1] + 1:
            break
        step = vs[i] - vs[i - 1]
        if step == 0:
            break
        s = 1 if step > 0 else -1
        if st == 0 or (st > 0) == (s > 0):
            st += s
        else:
            break
    if abs(st) >= 2:
        out["st"] = st

    # The largest single-year step in the whole series. A step above 100 per
    # cent almost always means the indicator was redefined, recounted or
    # restated, not that the thing being measured doubled.
    floor = max(1.0, 0.05 * max(abs(v) for v in vs))
    steps = [abs(_rel(vs[i - 1], vs[i]))
             for i in range(1, len(vs))
             if ys[i] == ys[i - 1] + 1 and abs(vs[i - 1]) >= floor and _rel(vs[i - 1], vs[i]) is not None]
    if steps:
        out["br"] = round(max(steps), 4)

    # Two ways of reading a whole series rather than its two endpoints.
    #
    # cagr  compounds the first-to-last change over the years between them, so
    #       a 60 per cent rise over nine years reads as the 5.4 per cent a year
    #       it actually is. Undefined when either end is zero or the series
    #       crosses zero, and those are left without a figure rather than
    #       forced into one.
    # tr    is the least-squares slope through every published year, divided by
    #       the mean, so it is a per-year rate too -- but one that uses all ten
    #       readings instead of the two at the ends. When cagr and tr disagree,
    #       the endpoints are doing the work.
    yrs_between = last_y - first_y
    if yrs_between > 0 and all(v > 0 for v in vs):
        out["cagr"] = round((last / first) ** (1.0 / yrs_between) - 1, 6)
    if len(vs) >= 4:
        mx = statistics.fmean(ys)
        my = statistics.fmean(vs)
        denom = sum((y - mx) ** 2 for y in ys)
        if denom and my != 0:
            slope = sum((y - mx) * (v - my) for y, v in pairs) / denom
            out["tr"] = round(slope / abs(my), 6)
            # how well a straight line actually describes it, 0 to 1
            ss_tot = sum((v - my) ** 2 for v in vs)
            if ss_tot > 0:
                pred = [my + slope * (y - mx) for y in ys]
                ss_res = sum((v - p) ** 2 for v, p in zip(vs, pred))
                out["r2"] = round(max(0.0, 1 - ss_res / ss_tot), 3)

    # Direction-aware versions: positive means "toward what the city wants".
    if direction:
        if d1 is not None:
            out["g1"] = round(d1 * direction, 6)
        if dA is not None:
            out["gA"] = round(dA * direction, 6)
        out["gp1"] = round(p1 * direction, 4)
        if "z" in out:
            out["gz"] = round(out["z"] * direction, 3)
        if "rec" in out:
            out["grec"] = out["rec"] * direction
        if "st" in out:
            out["gst"] = out["st"] * direction
        if "cagr" in out:
            out["gcagr"] = round(out["cagr"] * direction, 6)
        if "tr" in out:
            out["gtr"] = round(out["tr"] * direction, 6)
    return out


def verdict(g1, flat=0.01):
    if g1 is None:
        return 0
    if abs(g1) < flat:
        return 0
    return 1 if g1 > 0 else -1
