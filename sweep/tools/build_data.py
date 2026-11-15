#!/usr/bin/env python3
"""Build the app's citywide street-cleaning data from NYC Open Data.

Source: NYC DOT Parking Regulation Locations and Signs (nfid-uabd), every
current sign whose description mentions the sanitation broom symbol.

Each sign belongs to a block face: borough + street + from street + to street +
side. We group signs into faces, parse the posted hours, and write

  ios/Sweep/Data/faces.json   names, rules and faces
  ios/Sweep/Data/points.bin   sign positions, little-endian int32 pairs
                              (latitude, longitude) in millionths of a degree

Usage: python3 tools/build_data.py [--refresh]
  --refresh  re-download the signs (otherwise uses tools/cache/signs.json)
"""
import json, os, re, struct, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache", "signs.json")
OUT = os.path.join(ROOT, "ios", "Sweep", "Data")
API = "https://data.cityofnewyork.us/resource/nfid-uabd.json"
COLS = "borough,on_street,from_street,to_street,side_of_street,sign_description,sign_x_coord,sign_y_coord,sign_design_voided_on_date,order_number"


def fetch():
    rows, off, page = [], 0, 50000
    while True:
        q = urllib.parse.urlencode({
            "$select": COLS,
            "$where": "record_type='Current' AND sign_description like '%BROOM%'",
            "$order": "order_number,sign_x_coord",
            "$limit": page, "$offset": off})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(API + "?" + q, timeout=120) as r:
                    batch = json.load(r)
                break
            except Exception as e:  # Socrata throttles anonymous traffic with 403s; retry
                print("retry", attempt, e, file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            sys.exit("download failed")
        rows += batch
        print(f"  {len(rows)} signs", file=sys.stderr)
        if len(batch) < page:
            break
        off += page
    if len(rows) < 150000:  # an empty or partial pull must fail loudly
        sys.exit(f"only {len(rows)} signs came back; expected about 195,000")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(rows, open(CACHE, "w"))
    return rows


# ---------- parsing the posted hours
DAYNAMES = {"SUNDAY": 0, "SUN": 0, "MONDAY": 1, "MODAY": 1, "MON": 1, "TUESDAY": 2, "TUES": 2, "TUE": 2,
            "WEDNESDAY": 3, "WED": 3, "THURSDAY": 4, "THURDAY": 4, "THURSDA": 4, "THURS": 4, "THU": 4,
            "FRIDAY": 5, "FRI": 5, "SATURDAY": 6, "SAT": 6}
DAYRX = "|".join(sorted(DAYNAMES, key=len, reverse=True))
T = r"(MIDNIGHT|NOON|\d{1,2}(?::\d\d)?\s*(?:AM|PM)?)"
TIMERX = re.compile(T + r"\s*(?:-|TO)+\s*" + T)


def clock(s):
    s = s.replace(" ", "")
    if s == "MIDNIGHT": return 0, "AM"
    if s == "NOON": return 12 * 60, "PM"
    m = re.match(r"(\d{1,2})(?::(\d\d))?(AM|PM)?$", s)
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    return (h % 12) * 60 + mi, ap


def parse(desc):
    """Return (days_mask, start_min, end_min, night, superseded) or None."""
    d = desc.upper()
    superseded = "SUPERSEDED BY" in d
    d = re.sub(r"\(?\s*SUPE?R?SEDE.*$", "", d)          # drop "(SUPERSEDES ..." notes
    d = re.sub(r"\bSUPESEDES.*$", "", d)
    d = d.replace("SYMB OLS", "SYMBOLS").replace("10A M", "10AM").replace("1 M ", "1PM ")
    d = re.sub(r"(\d) (AM|PM)\b", r"\1\2", d)
    d = re.sub(r"(AM|PM)(?=[A-Z])", r"\1 ", d)            # "1PM FRIW/" -> "1PM FRIW/"
    night = bool(re.search(r"MOON|NIGHT", d))
    tm = TIMERX.search(d)
    if not tm:
        return None
    (a, aap), (b, bap) = clock(tm.group(1)), clock(tm.group(2))
    if tm.group(2).strip() == "MIDNIGHT":
        b = 24 * 60
    elif bap == "PM" and b < 12 * 60:
        b += 12 * 60
    if tm.group(1).strip() not in ("MIDNIGHT", "NOON"):
        if aap == "PM" and a < 12 * 60:
            a += 12 * 60
        elif aap is None:  # "8:30-10AM": borrow the meridiem that gives a short window
            cands = [x for x in (a, a + 12 * 60) if 0 < b - x <= 6 * 60]
            if not cands:
                return None
            a = cands[-1]
    if not (0 < b - a <= 8 * 60):
        return None
    rest = d[:tm.start()] + " " + d[tm.end():]
    mask = 0
    for r0, r1 in re.findall(rf"\b({DAYRX})\s*-\s*({DAYRX})\b", rest):
        i, j = DAYNAMES[r0], DAYNAMES[r1]
        k = i
        while True:
            mask |= 1 << k
            if k == j: break
            k = (k + 1) % 7
    for w in re.findall(rf"\b({DAYRX})(?=\b|W/|<|-|&)", rest):
        mask |= 1 << DAYNAMES[w]
    if "EXCEPT SUNDAY" in d:
        mask = 0b1111110
    if mask == 0:
        return None
    return mask, a, b, night, superseded


def main():
    rows = fetch() if "--refresh" in sys.argv or not os.path.exists(CACHE) else json.load(open(CACHE))
    pulled = date.fromtimestamp(os.path.getmtime(CACHE)).isoformat()
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:2263", "EPSG:4326", always_xy=True)

    norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().upper())
    faces = defaultdict(lambda: {"pts": [], "rules": Counter(), "old": Counter()})
    unparsed = Counter()
    for r in rows:
        if r.get("sign_design_voided_on_date"):
            continue
        side = norm(r.get("side_of_street"))
        if side not in ("N", "S", "E", "W"):
            continue
        key = (norm(r.get("borough")), norm(r.get("on_street")), norm(r.get("from_street")), norm(r.get("to_street")), side)
        p = parse(r["sign_description"])
        if p is None:
            unparsed[r["sign_description"]] += 1
            continue
        f = faces[key]
        (f["old"] if p[4] else f["rules"])[p[:4]] += 1
        if r.get("sign_x_coord") and r.get("sign_y_coord"):
            lon, lat = tr.transform(float(r["sign_x_coord"]), float(r["sign_y_coord"]))
            f["pts"].append((lat, lon))

    names, nidx = [], {}
    def ni(s):
        if s not in nidx:
            nidx[s] = len(names); names.append(s)
        return nidx[s]
    rules, ridx = [], {}
    def ri(r):
        if r not in ridx:
            ridx[r] = len(rules); rules.append([r[0], r[1], r[2], 1 if r[3] else 0])
        return ridx[r]

    out_faces, pts, nopts = [], [], 0
    for key, f in faces.items():
        counts = f["rules"] or f["old"]  # a "superseded by" sign only counts if nothing newer is posted
        if not counts:
            continue
        if not f["pts"]:
            nopts += 1
            continue
        ranked = [r for r, _ in counts.most_common()]
        # order sign points along the block so the app can treat them as a line
        P = f["pts"]
        la0 = sum(p[0] for p in P) / len(P); lo0 = sum(p[1] for p in P) / len(P)
        xy = [((p[1] - lo0) * 0.7570, p[0] - la0) for p in P]  # cos(40.7 deg) scales longitude
        sxx = sum(x * x for x, _ in xy); syy = sum(y * y for _, y in xy); sxy = sum(x * y for x, y in xy)
        import math
        ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
        order = sorted(range(len(P)), key=lambda i: xy[i][0] * math.cos(ang) + xy[i][1] * math.sin(ang))
        line = []
        for i in order:
            if not line or abs(P[i][0] - line[-1][0]) + abs(P[i][1] - line[-1][1]) > 0.00002:
                line.append(P[i])
        boro, on, fr, to, side = key
        out_faces.append([ni(boro), ni(on), ni(fr), ni(to), side, [ri(r) for r in ranked], len(pts), len(line), sum(counts.values())])
        pts += line

    os.makedirs(OUT, exist_ok=True)
    json.dump({"source": "NYC DOT Parking Regulation Locations and Signs (nfid-uabd)", "pulled": pulled,
               "names": names, "rules": rules, "faces": out_faces}, open(os.path.join(OUT, "faces.json"), "w"), separators=(",", ":"))
    with open(os.path.join(OUT, "points.bin"), "wb") as fh:
        for la, lo in pts:
            fh.write(struct.pack("<ii", round(la * 1e6), round(lo * 1e6)))
    print(f"{len(rows)} signs -> {len(out_faces)} faces, {len(pts)} points, {len(rules)} distinct rules; "
          f"{nopts} faces had no mapped sign; {sum(unparsed.values())} signs unparsed ({len(unparsed)} texts)")
    for t, n in unparsed.most_common(15):
        print("  unparsed", n, t)
    multi = sum(1 for f in out_faces if len(f[5]) > 1)
    print(f"{multi} faces have more than one posted rule")


if __name__ == "__main__":
    main()
