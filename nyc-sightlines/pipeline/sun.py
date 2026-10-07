"""Where can you watch the sun rise or set? One answer per season.

For a set of dates, follow the sun's path near the horizon at 13 apparent altitudes from 0.3 to 6 degrees
(dense near the horizon, where a street canyon can catch it for only a minute or two). For every cell,
compute the horizon angle of the surface model toward the sun at each of those moments; the sun is in
view if it sits above that horizon. Each cell keeps the lowest altitude at which it catches the sun:
level 3 = at or below 1.2 degrees (within ~8 minutes of sunset or sunrise), 2 = at or below 2.5 degrees
(~16 minutes), 1 = at or below 6 degrees (~35 minutes), 0 = never in that last (first) stretch.

Horizon angles use the upper-convex-hull sweep (Dozier & Frew 1990) along parallel lines: every cell is
visited once per direction, and the horizon for each cell is the tangent from its eye point to the
hull of the surface ahead of it. Earth curvature is ignored here (under 0.1 degree within the grid).

Usage: python sun.py GRID_DIR OUT_DIR    -> OUT_DIR/sun_states.json, OUT_DIR/sun_<state>_<rise|set>.npy
"""
import sys, os, json, datetime as dt
import numpy as np, numba as nb
from zoneinfo import ZoneInfo
from astral import Observer
from astral.sun import elevation, azimuth, sunrise as astral_sunrise, sunset as astral_sunset
import grid

NY = ZoneInfo("America/New_York")
OBS = Observer(latitude=40.754, longitude=-73.984)
GRID_CONV = 0.66            # true north = UTM grid north + 0.66 degrees here
PATH = [0.3, 0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]   # apparent altitudes sampled
LEVEL_ALT = [6.0, 2.5, 1.2]  # upper altitude for levels 1, 2, 3 (also the points the page draws)
def level_of(alt):
    return 3 if alt <= 1.2 else (2 if alt <= 2.5 else 1)
GRID_BEARING = 299.0        # Manhattan cross streets, true bearing (measured from the street centrelines)


def crossing(day, alt, rising):
    """Local time on `day` when the sun's apparent centre passes `alt` degrees, by bisection."""
    lo = dt.datetime(day.year, day.month, day.day, 3 if rising else 12, tzinfo=NY)
    hi = lo + dt.timedelta(hours=9)
    f = lambda t: elevation(OBS, t, with_refraction=True) - alt
    flo = f(lo)
    for _ in range(40):
        mid = lo + (hi - lo) / 2
        if (f(mid) > 0) == (flo > 0):
            lo, flo = mid, f(mid)
        else:
            hi = mid
    return lo + (hi - lo) / 2


def event(day, rising):
    out = {"date": day.isoformat(), "levels": [], "path": []}
    for a in LEVEL_ALT:
        t = crossing(day, a, rising)
        out["levels"].append({"alt": a, "time": t.strftime("%H:%M"), "az": round(azimuth(OBS, t), 2)})
    for a in PATH:
        t = crossing(day, a, rising)
        out["path"].append({"alt": a, "time": t.strftime("%H:%M:%S"), "az": round(azimuth(OBS, t), 3)})
    # Official sunrise / sunset: the standard definition (geometric centre 0.833 degrees below the horizon,
    # which already allows for refraction and the sun's radius), as astral computes it.
    t0 = (astral_sunrise if rising else astral_sunset)(OBS, day, tzinfo=NY)
    out["official"] = t0.strftime("%H:%M")
    out["official_az"] = round(azimuth(OBS, t0), 2)
    return out


def henge(month_from, month_to, target, rising):
    """The day whose sun at 0.5 degrees lines up best with the street grid."""
    best = None
    d = dt.date(2026, month_from, 1)
    end = dt.date(2026, month_to + 1, 1) if month_to < 12 else dt.date(2027, 1, 1)
    while d < end:
        a = azimuth(OBS, crossing(d, 0.5, rising))
        if best is None or abs(a - target) < best[0]:
            best = (abs(a - target), d)
        d += dt.timedelta(days=1)
    return best[1]


def states():
    D = dt.date
    S = [
        {"key": "dec", "label": "Dec 21", "months": [12], "rise": D(2026, 12, 21), "set": D(2026, 12, 21)},
        {"key": "jan", "label": "Jan 20 · Nov 21", "months": [1, 11], "rise": D(2026, 1, 20), "set": D(2026, 1, 20)},
        {"key": "feb", "label": "Feb 19 · Oct 23", "months": [2, 10], "rise": D(2026, 2, 19), "set": D(2026, 2, 19)},
        {"key": "mar", "label": "Mar 20 · Sep 23", "months": [3, 9], "rise": D(2026, 3, 20), "set": D(2026, 3, 20)},
        {"key": "apr", "label": "Apr 20 · Aug 23", "months": [4, 8], "rise": D(2026, 4, 20), "set": D(2026, 4, 20)},
        {"key": "may", "label": "May 21 · Jul 23", "months": [5, 7], "rise": D(2026, 5, 21), "set": D(2026, 5, 21)},
        {"key": "jun", "label": "Jun 21", "months": [6], "rise": D(2026, 6, 21), "set": D(2026, 6, 21)},
    ]
    # Map the published "full sun" evening (May 29, 2026): the sun lines up with the grid while it is still
    # clear of the New Jersey horizon. (Aligning exactly at 0.5 degrees would pick May 28.)
    hs = dt.date(2026, 5, 29)
    hs2 = henge(7, 7, GRID_BEARING, rising=False)         # and again in July
    hr = henge(11, 12, GRID_BEARING - 180, rising=True)   # sunrise up the cross streets, early December
    hr2 = henge(1, 1, GRID_BEARING - 180, rising=True)    # and again in January
    # Labels use the published dates (American Museum of Natural History, as reported for 2026); the layer
    # itself is computed for the evening (or morning) the sun lines up best with the measured grid bearing.
    S.append({"key": "henge", "label": "Manhattanhenge", "months": [], "rise": hr, "set": hs,
              "rise_label": "Nov 29–30 · mid-January (map: Nov 29)", "set_label": "May 28–29 · Jul 11–12 (map: May 29)",
              "computed_for": {"sunrise": hr.isoformat(), "sunset": hs.isoformat(), "sunrise_july_twin": hr2.isoformat(), "sunset_july_twin": hs2.isoformat()}})
    for s in S:
        s["sunrise"] = event(s.pop("rise"), True)
        s["sunset"] = event(s.pop("set"), False)
    return S


@nb.njit(parallel=True, cache=True)
def sweep(dsm, ground, target, az_grid_deg, eye, res, alt_deg, out_vis):
    """out_vis[r, c] = 1 where the horizon toward az is below alt (sun at alt is in view)."""
    H, W = dsm.shape
    th = np.radians(az_grid_deg)
    dc, dr = np.sin(th), -np.cos(th)           # one cell step toward the sun
    tan_alt = np.tan(np.radians(alt_deg))
    if abs(dc) >= abs(dr):
        major_c = True
        slope = dr / dc                         # rows per +1 column along the line
        sgn = 1 if dc > 0 else -1
        n_major, n_minor = W, H
    else:
        major_c = False
        slope = dc / dr                         # columns per +1 row along the line
        sgn = 1 if dr > 0 else -1
        n_major, n_minor = H, W
    step = np.sqrt(1.0 + slope * slope) * res  # metres per step along the line
    span = int(np.ceil(abs(slope) * n_major)) + 1
    lo = -span if slope > 0 else 0
    hi = n_minor + (span if slope < 0 else 0)
    for off in nb.prange(lo, hi + 1):
        hx = np.empty(n_major, np.float64)    # hull: distance along line (m), surface height
        hz = np.empty(n_major, np.float64)
        top = 0
        # walk from the sun side toward the far side; the sun side is the far end of the major axis when sgn > 0
        for k in range(n_major):
            m = n_major - 1 - k if sgn > 0 else k        # major index
            prog = (n_major - 1 - m) if sgn > 0 else m   # cells travelled away from the sun-side edge
            minor_f = off + slope * m
            mi = int(np.floor(minor_f + 0.5))
            if mi < 0 or mi >= n_minor:
                continue
            r = mi if major_c else m
            c = m if major_c else mi
            t = -prog * step                    # position along the line; ahead (toward the sun) is larger
            e = ground[r, c] + eye
            # horizon from this eye: tangent to the hull of everything ahead
            if target[r, c] == 0:
                pass
            elif top > 0:
                a, b = 0, top - 1               # hull indices 0..top-1, top-1 nearest
                # slopes are unimodal over the hull; binary search for the peak
                while a < b:
                    mid = (a + b) // 2
                    s1 = (hz[mid] - e) / (hx[mid] - t)
                    s2 = (hz[mid + 1] - e) / (hx[mid + 1] - t)
                    if s1 >= s2:
                        b = mid
                    else:
                        a = mid + 1
                best = (hz[a] - e) / (hx[a] - t)
                if best < tan_alt:
                    out_vis[r, c] = 1
            else:
                out_vis[r, c] = 1
            # add this cell's surface to the hull (it is the new nearest point)
            z = dsm[r, c]
            while top >= 2:
                # drop the current nearest hull point if it lies on or below the chord from the new point
                x1, z1 = hx[top - 1], hz[top - 1]
                x2, z2 = hx[top - 2], hz[top - 2]
                if (z1 - z) * (x2 - t) <= (z2 - z) * (x1 - t):
                    top -= 1
                else:
                    break
            hx[top] = t
            hz[top] = z
            top += 1
    return 0


@nb.njit(cache=True)
def brute(dsm, ground, r0, c0, az_grid_deg, eye, res, alt_deg):
    H, W = dsm.shape
    th = np.radians(az_grid_deg)
    dc, dr = np.sin(th), -np.cos(th)
    e = ground[r0, c0] + eye
    best = -1e9
    k = 1
    while True:
        r = r0 + 0.5 + dr * k * 0.25
        c = c0 + 0.5 + dc * k * 0.25
        ri, ci = int(np.floor(r)), int(np.floor(c))
        if ri < 0 or ci < 0 or ri >= H or ci >= W:
            break
        if ri != r0 or ci != c0:
            s = (dsm[ri, ci] - e) / (k * 0.25 * res)
            if s > best:
                best = s
        k += 1
    return best < np.tan(np.radians(alt_deg))


def main():
    G, OUT = sys.argv[1:3]
    os.makedirs(OUT, exist_ok=True)
    S = states()
    json.dump(S, open(f"{OUT}/sun_states.json", "w"), indent=1)
    if "--states-only" in sys.argv:
        return
    for s in S:
        print(s["key"], s["sunrise"]["date"], s["sunrise"]["levels"][2]["az"], s["sunset"]["date"], s["sunset"]["levels"][2]["az"], flush=True)
    dsm = np.load(f"{G}/dsm.npy")
    ground = np.load(f"{G}/ground.npy")
    cls = np.load(f"{G}/cls.npy"); boro = np.load(f"{G}/boro.npy")
    target = (((cls == 1) | (cls == 3)) & (boro >= 1) & (boro <= 5)).astype(np.uint8)   # open ground in the city
    del cls, boro
    rng = np.random.default_rng(3)
    for s in S:
        for ev in ("sunrise", "sunset"):
            lvl = np.zeros(dsm.shape, np.uint8)
            for j, P in enumerate(s[ev]["path"]):
                vis = np.zeros(dsm.shape, np.uint8)
                azg = P["az"] - GRID_CONV
                sweep(dsm, ground, target, azg, grid.EYE, grid.RES, P["alt"], vis)
                np.maximum(lvl, vis * np.uint8(level_of(P["alt"])), out=lvl)
                if j in (0, 6, 12):   # spot-check against brute force on random target cells
                    rr = rng.integers(2000, grid.H - 2000, 4000); cc = rng.integers(2000, grid.W - 2000, 4000)
                    keep = target[rr, cc] == 1; rr, cc = rr[keep][:250], cc[keep][:250]
                    agree = np.mean([brute(dsm, ground, int(a), int(b), azg, grid.EYE, grid.RES, P["alt"]) == bool(vis[a, b]) for a, b in zip(rr, cc)])
                    print(f"  {s['key']:6s} {ev:7s} alt {P['alt']:3.1f} az {P['az']:7.3f}  in view {vis[target == 1].mean()*100:5.1f}% of city open ground  brute-force agreement {agree*100:.1f}% (n={len(rr)})", flush=True)
            np.save(f"{OUT}/sun_{s['key']}_{ev}.npy", lvl * target)
            print(s["key"], ev, "levels", np.bincount(lvl[target == 1], minlength=4).tolist(), flush=True)


if __name__ == "__main__":
    main()
