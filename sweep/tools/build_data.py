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

    # Signs only mark part of a block (one sign = a dot). Redraw each side along the street's own
    # centerline, corner to corner, pushed out to the side of the street the signs are on.
    out_faces, pts, stats = blockify(out_faces, pts, names)
    print("block geometry:", stats)

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


CL_CACHE = os.path.join(os.path.dirname(__file__), "cache", "centerline.json")
CL_API = "https://data.cityofnewyork.us/resource/inkn-q76z.json"


def fetch_centerline():
    """NYC Street Centerline (CSCL), inkn-q76z: one row per street segment with its geometry."""
    import urllib.request, urllib.parse
    out, off = [], 0
    while True:
        q = urllib.parse.urlencode({"$select": "the_geom,full_street_name,boroughcode,streetwidth,rw_type,objectid",
                                    "$order": "objectid", "$limit": 50000, "$offset": off})
        for attempt in range(5):
            try:
                req = urllib.request.Request(f"{CL_API}?{q}", headers={"User-Agent": "Sweep-build/1.0"})
                page = json.load(urllib.request.urlopen(req, timeout=180))
                break
            except Exception as e:
                print("  centerline retry", attempt, e); import time; time.sleep(5 * (attempt + 1))
        else:
            sys.exit("centerline download failed")
        out += page; off += len(page)
        print(f"  centerline {off}")
        if len(page) < 50000:
            break
    if len(out) < 100000:
        sys.exit(f"centerline came back with only {len(out)} rows; refusing to continue")
    os.makedirs(os.path.dirname(CL_CACHE), exist_ok=True)
    json.dump(out, open(CL_CACHE, "w"))
    return out


SUFFIX = {"STREET": "ST", "AVENUE": "AVE", "PLACE": "PL", "ROAD": "RD", "BOULEVARD": "BLVD", "PARKWAY": "PKWY",
          "DRIVE": "DR", "COURT": "CT", "LANE": "LN", "TERRACE": "TER", "HIGHWAY": "HWY", "SQUARE": "SQ",
          "EXPRESSWAY": "EXPY", "TURNPIKE": "TPKE", "WEST": "W", "EAST": "E", "NORTH": "N", "SOUTH": "S",
          "SAINT": "ST", "FORT": "FT", "MOUNT": "MT", "PLAZA": "PLZ", "CIRCLE": "CIR", "WALK": "WALK", "LOOP": "LOOP",
          "AVE": "AVE", "STR": "ST", "BL": "BLVD", "PKY": "PKWY", "CRESCENT": "CRES", "GARDENS": "GDNS", "HEIGHTS": "HTS"}


def canon(name):
    words = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper()).split()
    out = []
    for w in words:
        w = re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", w)
        out.append(SUFFIX.get(w, w))
    return " ".join(out)


BORO = {"MANHATTAN": "1", "BRONX": "2", "BROOKLYN": "3", "QUEENS": "4", "STATEN ISLAND": "5"}


def blockify(faces, pts, names):
    import math
    rows = json.load(open(CL_CACHE)) if os.path.exists(CL_CACHE) and "--refresh" not in sys.argv else fetch_centerline()
    LAT0, KX, KY = 40.7, 111320 * math.cos(math.radians(40.7)), 110574
    to_xy = lambda la, lo: ((lo + 74.0) * KX, (la - LAT0) * KY)
    to_ll = lambda x, y: (y / KY + LAT0, x / KX - 74.0)

    segs = []   # (boro, canon name, [xy...], width_m)
    for r in rows:
        g = r.get("the_geom")
        if not g:
            continue
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for ln in lines:
            if len(ln) >= 2:
                w = float(r.get("streetwidth") or 30) * 0.3048
                segs.append((r.get("boroughcode"), canon(r.get("full_street_name")), [to_xy(la, lo) for lo, la in ln], w))
    # grid index of segments by vertex cell, and a node table to walk along a street between corners
    CELL = 60.0
    grid = defaultdict(set)
    for i, (_, _, xy, _) in enumerate(segs):
        for (x0, y0), (x1, y1) in zip(xy, xy[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) // CELL) + 1)
            for k in range(n + 1):
                t = k / n
                grid[(int((x0 + t * (x1 - x0)) // CELL), int((y0 + t * (y1 - y0)) // CELL))].add(i)
    key = lambda p: (round(p[0] / 1.5), round(p[1] / 1.5))
    nodes = defaultdict(list)
    for i, (_, _, xy, _) in enumerate(segs):
        nodes[key(xy[0])].append(i); nodes[key(xy[-1])].append(i)

    def seg_dist(p, xy):
        best = 1e18
        for (x0, y0), (x1, y1) in zip(xy, xy[1:]):
            vx, vy = x1 - x0, y1 - y0; L = vx * vx + vy * vy
            t = 0 if L == 0 else max(0, min(1, ((p[0] - x0) * vx + (p[1] - y0) * vy) / L))
            best = min(best, math.hypot(p[0] - x0 - t * vx, p[1] - y0 - t * vy))
        return best

    def chain(i, name):
        """The run of same-name segments through segment i, stopping at corners (nodes where another street joins)."""
        line = list(segs[i][2]); used = {i}
        for end in (0, 1):
            for _ in range(12):
                node = key(line[-1] if end else line[0])
                others = [j for j in nodes[node] if j not in used]
                if len(nodes[node]) != 2 or len(others) != 1 or segs[others[0]][1] != name:
                    break
                j = others[0]; used.add(j)
                xy = segs[j][2]
                if key(xy[0]) != node:
                    xy = xy[::-1]
                line = line + xy[1:] if end else list(reversed(xy))[:-1] + line
        return line, max(segs[k][3] for k in used)

    def trim(line, cut):
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(line, line[1:]))
        cut = min(cut, L * 0.2)
        def at(d):
            acc = 0
            for a, b in zip(line, line[1:]):
                s = math.hypot(b[0] - a[0], b[1] - a[1])
                if acc + s >= d and s > 0:
                    t = (d - acc) / s; return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                acc += s
            return line[-1]
        out, acc = [at(cut)], 0
        for a, b in zip(line, line[1:]):
            acc += math.hypot(b[0] - a[0], b[1] - a[1])
            if cut < acc < L - cut:
                out.append(b)
        out.append(at(L - cut))
        # densify so the app's nearby-point search finds the middle of long blocks
        dense = [out[0]]
        for a, b in zip(out, out[1:]):
            s = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(s // 20) + (1 if s % 20 else 0))
            for k in range(1, n + 1):
                dense.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
        return dense

    def offset(line, d):
        out = []
        for k, p in enumerate(line):
            a = line[max(0, k - 1)]; b = line[min(len(line) - 1, k + 1)]
            vx, vy = b[0] - a[0], b[1] - a[1]; L = math.hypot(vx, vy) or 1
            out.append((p[0] - vy / L * d, p[1] + vx / L * d))   # positive d = to the left of travel
        return out

    compass = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    new_faces, new_pts = [], []
    stats = Counter()
    for f in faces:
        boro, on, side = names[f[0]], names[f[1]], f[4]
        old = pts[f[6]:f[6] + f[7]]
        P = [to_xy(la, lo) for la, lo in old]
        cx = sum(p[0] for p in P) / len(P); cy = sum(p[1] for p in P) / len(P)
        bc, cn = BORO.get(boro), canon(on)
        cand = set()
        gx, gy = int(cx // CELL), int(cy // CELL)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand |= grid.get((gx + dx, gy + dy), set())
        cand = [i for i in cand if segs[i][1] == cn and (segs[i][0] == bc or bc is None)]
        best = min(((sum(seg_dist(p, segs[i][2]) for p in P) / len(P), i) for i in cand), default=None)
        line = None
        if best and best[0] <= 25:
            ch, width = chain(best[1], cn)
            if max(seg_dist(p, ch) for p in P) <= 25 and len(ch) >= 2:
                # which side: where the signs actually stand, else the side letter
                vx, vy = ch[-1][0] - ch[0][0], ch[-1][1] - ch[0][1]
                lx, ly = -vy, vx
                signed = sum((p[0] - ch[0][0]) * lx + (p[1] - ch[0][1]) * ly for p in P) / len(P) / (math.hypot(lx, ly) or 1)
                if abs(signed) > 2:
                    left = signed > 0
                else:
                    c = compass[side]; left = (lx * c[0] + ly * c[1]) > 0
                d = max(3.0, min(12.0, width / 2 - 1.5))
                line = trim(offset(ch, d if left else -d), 7)
                stats["full block"] += 1
        if line is None:
            stats["kept sign points"] += 1
            if not cand:
                stats["  no same-name street nearby"] += 1
            line_ll = old
        else:
            line_ll = [to_ll(x, y) for x, y in line]
        nf = list(f); nf[6] = len(new_pts); nf[7] = len(line_ll)
        new_faces.append(nf); new_pts += line_ll
    stats["points"] = len(new_pts)
    return new_faces, new_pts, dict(stats)


if __name__ == "__main__":
    main()
