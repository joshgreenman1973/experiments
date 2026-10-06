#!/usr/bin/env python3
"""
Build the bus tracker's static GTFS products from the MTA's six bus feeds.

Outputs (paths relative to nyc-bus-tracker/):
  data/routes/routes.geojson         one LineString per route (the route's longest
                                     shape), simplified to ~5 m, for the live map
  data/routes/route-table.json       every scheduled route: names, agency, color,
                                     kind (local/limited/sbs/express), group
  data/gtfs/scheduled-service.json   scheduled buses in service per route per clock
                                     hour, stored as day "patterns" plus a
                                     date -> pattern map; past dates are kept

Standard library only, so it runs on a stock GitHub Ubuntu runner.

Usage:
  python3 nyc-bus-tracker/scripts/build_gtfs.py [--work-dir DIR] [--skip-download]
                                                [--out-dir DIR] [--today YYYY-MM-DD]

  --work-dir       where the feed zips are downloaded (default: $GTFS_WORK_DIR, else
                   a temporary directory that is deleted afterwards)
  --skip-download  reuse zips already in --work-dir (for local testing)
  --out-dir        the nyc-bus-tracker/data directory (default: next to this script)
  --today          override "today" (America/New_York) for the history merge

Exits 1 on any download failure, truncated feed or failed sanity check.
"""

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile

# Official MTA bus GTFS static feeds. The old web.mta.info/developers/data/... URLs
# now 301-redirect to these S3 objects (checked Oct 2026).
FEEDS = [
    ('bronx', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip'),
    ('brooklyn', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip'),
    ('manhattan', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip'),
    ('queens', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip'),
    ('staten_island', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip'),
    ('mta_bus_company', 'https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip'),
]
REQUIRED_FILES = ['routes.txt', 'trips.txt', 'stop_times.txt', 'shapes.txt']
MIN_ZIP_BYTES = 2_000_000      # every feed is 6-20 MB; anything tiny is an error page
MIN_TRIPS_PER_FEED = 5_000
MIN_STOP_TIME_ROWS = 300_000

SIMPLIFY_TOLERANCE_M = 5.0
COORD_DECIMALS = 5
SAMPLE_SECONDS = 300           # trips in progress are sampled every 5 minutes
SAMPLES_PER_DAY = 86400 // SAMPLE_SECONDS   # 288
SPILL_DAYS = 3                 # service-day arrays cover 72 h (stop times can pass 24:00)

MIN_ROUTES = 300
WEEKDAY_8AM_HARD = (2500, 5000)    # fail outside this
WEEKDAY_8AM_EXPECT = (3000, 4500)  # warn outside this

EXPRESS_RE = re.compile(r'^(BM|BXM|QM|SIM|X)\d', re.I)
LIMITED_RE = re.compile(r'\b(limited|ltd)\b', re.I)

METHOD = (
    "Scheduled buses in service, from the MTA's published bus GTFS timetables (all six "
    "feeds: Bronx, Brooklyn, Manhattan, Queens, Staten Island and MTA Bus Company). Each "
    "scheduled trip counts as in service from its first scheduled departure until its last "
    "scheduled arrival (first departure <= t < last arrival). For each calendar date and "
    "clock hour in New York time, the count of a route's trips in service is taken every "
    "five minutes (:00, :05 ... :55) and averaged over those 12 samples, rounded to 0.1. "
    "Which timetables run on a date comes from calendar.txt plus the exceptions in "
    "calendar_dates.txt, so holidays and school-day variants are reflected. Stop times past "
    "24:00 belong to the previous service day and are credited to the clock hour they "
    "actually fall in (25:30 on service day D counts at 1:30 on D+1); trips the MTA codes "
    "with small times on the next service day are counted on that day, so both overnight "
    "encodings add up. Time spent deadheading to or from the depot and layovers between "
    "trips are not counted, so this is a count of trips under way, a little below the "
    "number of buses the MTA puts on the street. Clock hours on the two daylight-saving "
    "nights (midnight to 3 a.m.) may be off by an hour. A route missing from a pattern has "
    "no scheduled trips on that day. Dates before the day a build ran are kept from earlier "
    "builds, so past dates reflect the timetable that was published at the time."
)


def log(msg=''):
    print(msg, flush=True)


def fail(msg):
    print(f'FATAL: {msg}', file=sys.stderr, flush=True)
    sys.exit(1)


# ─── time helpers ────────────────────────────────────────────────────────────

def ny_today():
    """Today's date in America/New_York (zoneinfo, with a rule-based fallback)."""
    now_utc = dt.datetime.now(dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return now_utc.astimezone(ZoneInfo('America/New_York')).date()
    except Exception:
        # US rule: EDT from 2nd Sunday of March 07:00 UTC to 1st Sunday of Nov 06:00 UTC.
        y = now_utc.year

        def nth_sunday(month, n):
            d = dt.date(y, month, 1)
            d += dt.timedelta(days=(6 - d.weekday()) % 7)
            return d + dt.timedelta(weeks=n - 1)
        start = dt.datetime.combine(nth_sunday(3, 2), dt.time(7), dt.timezone.utc)
        end = dt.datetime.combine(nth_sunday(11, 1), dt.time(6), dt.timezone.utc)
        offset = -4 if start <= now_utc < end else -5
        return (now_utc + dt.timedelta(hours=offset)).date()


def parse_gtfs_date(s):
    s = s.strip()
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def gtfs_seconds(s):
    """'25:30:00' -> 91800. Returns None for blank."""
    s = s.strip()
    if not s:
        return None
    h, m, sec = s.split(':')
    return int(h) * 3600 + int(m) * 60 + int(sec)


# ─── download ────────────────────────────────────────────────────────────────

def download(url, dest):
    last_err = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'nyc-bus-tracker-gtfs/1.0'})
            with urllib.request.urlopen(req, timeout=180) as res:
                if res.status != 200:
                    raise RuntimeError(f'HTTP {res.status}')
                expected = res.headers.get('Content-Length')
                last_modified = res.headers.get('Last-Modified')
                tmp = dest + '.part'
                with open(tmp, 'wb') as fh:
                    shutil.copyfileobj(res, fh, length=1 << 20)
            size = os.path.getsize(tmp)
            if expected is not None and int(expected) != size:
                raise RuntimeError(f'truncated: got {size} of {expected} bytes')
            os.replace(tmp, dest)
            return {'bytes': size, 'lastModified': last_modified}
        except Exception as e:  # noqa: BLE001 - retry anything, then fail loud
            last_err = e
            log(f'    attempt {attempt} failed: {e}')
            time.sleep(5 * attempt)
    fail(f'could not download {url}: {last_err}')


def check_zip(path, name):
    size = os.path.getsize(path)
    if size < MIN_ZIP_BYTES:
        fail(f'{name}: zip is only {size} bytes; looks truncated or an error page')
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        fail(f'{name}: not a valid zip ({e})')
    names = set(zf.namelist())
    missing = [f for f in REQUIRED_FILES if f not in names]
    if 'calendar.txt' not in names and 'calendar_dates.txt' not in names:
        missing.append('calendar.txt|calendar_dates.txt')
    if missing:
        fail(f'{name}: zip lacks {", ".join(missing)}')
    bad = zf.testzip()
    if bad is not None:
        fail(f'{name}: CRC error in {bad}; zip is corrupt or truncated')
    return zf


# ─── GTFS readers ────────────────────────────────────────────────────────────

def read_csv(zf, member):
    if member not in zf.namelist():
        return []
    with zf.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding='utf-8-sig', newline='')
        return [{k.strip(): (v or '').strip() for k, v in row.items() if k is not None}
                for row in csv.DictReader(text)]


def trip_spans(zf, name):
    """Stream stop_times.txt; return {trip_id: (first departure s, last arrival s)}."""
    lo, hi = {}, {}
    rows = 0
    with zf.open('stop_times.txt') as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
        header = [h.strip() for h in next(reader)]
        ti = header.index('trip_id')
        ai = header.index('arrival_time')
        di = header.index('departure_time')
        for row in reader:
            rows += 1
            dep = row[di] or row[ai]
            arr = row[ai] or row[di]
            if not dep:
                continue          # untimed intermediate stop
            d = gtfs_seconds(dep)
            a = gtfs_seconds(arr)
            t = row[ti]
            if t in lo:
                if d < lo[t]:
                    lo[t] = d
                if a > hi[t]:
                    hi[t] = a
            else:
                lo[t] = d
                hi[t] = a
    if rows < MIN_STOP_TIME_ROWS:
        fail(f'{name}: stop_times.txt has only {rows} rows; feed looks truncated')
    return {t: (lo[t], hi[t]) for t in lo}, rows


def active_services(calendar, calendar_dates):
    """{date: set(service_id)} from calendar.txt + calendar_dates.txt."""
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    act = {}
    for c in calendar:
        d = parse_gtfs_date(c['start_date'])
        end = parse_gtfs_date(c['end_date'])
        while d <= end:
            if c.get(days[d.weekday()]) == '1':
                act.setdefault(d, set()).add(c['service_id'])
            d += dt.timedelta(days=1)
    for x in calendar_dates:
        d = parse_gtfs_date(x['date'])
        if x['exception_type'] == '1':
            act.setdefault(d, set()).add(x['service_id'])
        elif x['exception_type'] == '2':
            act.setdefault(d, set()).discard(x['service_id'])
    return act


# ─── geometry ────────────────────────────────────────────────────────────────

M_PER_DEG_LAT = 110_540.0
M_PER_DEG_LON_NYC = 111_320.0 * math.cos(math.radians(40.7))


def line_length_m(coords):
    total = 0.0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        dx = (x2 - x1) * M_PER_DEG_LON_NYC
        dy = (y2 - y1) * M_PER_DEG_LAT
        total += math.hypot(dx, dy)
    return total


def simplify(coords, tol_m):
    """Iterative Douglas-Peucker in local metres (equirectangular at NYC latitude)."""
    n = len(coords)
    if n < 3:
        return coords
    pts = [(lon * M_PER_DEG_LON_NYC, lat * M_PER_DEG_LAT) for lon, lat in coords]
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tol_m * tol_m
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        best, best_k = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if seg2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
                qx, qy = ax + t * dx, ay + t * dy
                d2 = (px - qx) ** 2 + (py - qy) ** 2
            if d2 > best:
                best, best_k = d2, k
        if best > tol2:
            keep[best_k] = True
            stack.append((i, best_k))
            stack.append((best_k, j))
    out = []
    for c, k in zip(coords, keep):
        if k:
            r = [round(c[0], COORD_DECIMALS), round(c[1], COORD_DECIMALS)]
            if not out or out[-1] != r:
                out.append(r)
    return out


COVER_CELL_M = 25.0


def shape_cells(coords):
    """Set of 25 m grid cells a line passes through (densified every 10 m)."""
    cells = set()
    pts = [(lon * M_PER_DEG_LON_NYC, lat * M_PER_DEG_LAT) for lon, lat in coords]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 10))
        for i in range(n + 1):
            cells.add((int((x1 + (x2 - x1) * i / n) // COVER_CELL_M),
                       int((y1 + (y2 - y1) * i / n) // COVER_CELL_M)))
    return cells


def pick_shape(cands):
    """Pick the route's map line from {key: [coords, trips]}.

    Default is the longest shape. A different shape wins only when it lies along at
    least 5 points more of the route's trip-weighted path (within ~25-50 m) than the
    longest does; that catches routes whose longest shape is a rare depot or
    extension variant that skips the main line. Returns (coords, chose_longest).
    """
    lengths = {k: line_length_m(v[0]) for k, v in cands.items()}
    longest = max(lengths, key=lambda k: lengths[k])
    if len(cands) == 1:
        return cands[longest][0], True
    cells = {k: shape_cells(v[0]) for k, v in cands.items()}

    def coverage(k):
        near = set()
        for cx, cy in cells[k]:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near.add((cx + dx, cy + dy))
        num = den = 0
        for j, (_c, n) in cands.items():
            num += n * len(cells[j] & near)
            den += n * len(cells[j])
        return num / den if den else 0.0
    scores = {k: coverage(k) for k in cands}
    best = max(scores, key=lambda k: (scores[k], lengths[k]))
    if scores[best] - scores[longest] > 0.05:
        return cands[best][0], False
    return cands[longest][0], True


# ─── classification ──────────────────────────────────────────────────────────

def route_kind(rid, long_name, desc):
    if EXPRESS_RE.match(rid):
        return 'express'
    if rid.endswith('+'):
        return 'sbs'
    if LIMITED_RE.search(long_name) or LIMITED_RE.search(desc):
        return 'limited'
    return 'local'


def route_group(rid, kind):
    if kind == 'express':
        return 'X'
    u = rid.upper()
    if u.startswith('BX'):
        return 'Bx'
    for p in ('B', 'M', 'Q', 'S'):
        if u.startswith(p):
            return p
    return 'other'


# ─── schedule patterns ───────────────────────────────────────────────────────

def fmt_num(v):
    return str(int(v)) if v == int(v) else repr(v)


def pattern_id(pattern):
    """Content hash, computed on the printed form so a pattern read back from the
    file (ints like 3) hashes the same as a freshly built one (floats like 3.0)."""
    blob = ';'.join(f'{rid}:' + ','.join(fmt_num(v) for v in pattern[rid])
                    for rid in sorted(pattern))
    return hashlib.sha1(blob.encode()).hexdigest()


def write_schedule(path, doc):
    """Compact JSON, one route per line, so weekly diffs stay readable."""
    lines = ['{']
    lines.append(f' "generatedAt": {json.dumps(doc["generatedAt"])},')
    lines.append(f' "method": {json.dumps(doc["method"], ensure_ascii=False)},')
    lines.append(f' "source": {json.dumps(doc["source"], separators=(",", ":"))},')
    lines.append(' "patterns": {')
    pids = sorted(doc['patterns'])
    for pi, pid in enumerate(pids):
        pat = doc['patterns'][pid]
        lines.append(f'  {json.dumps(pid)}: {{')
        rids = sorted(pat)
        for ri, rid in enumerate(rids):
            arr = ','.join(fmt_num(v) for v in pat[rid])
            sep = ',' if ri < len(rids) - 1 else ''
            lines.append(f'   {json.dumps(rid)}: [{arr}]{sep}')
        lines.append('  }' + (',' if pi < len(pids) - 1 else ''))
    lines.append(' },')
    lines.append(' "dates": {')
    dates = sorted(doc['dates'])
    for di, d in enumerate(dates):
        sep = ',' if di < len(dates) - 1 else ''
        lines.append(f'  {json.dumps(d)}: {json.dumps(doc["dates"][d])}{sep}')
    lines.append(' }')
    lines.append('}')
    tmp = path + '.tmp'
    with open(tmp, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    with open(tmp) as fh:
        json.load(fh)      # round-trip check before replacing the live file
    os.replace(tmp, path)


# ─── main ────────────────────────────────────────────────────────────────────

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--work-dir', default=os.environ.get('GTFS_WORK_DIR'))
    ap.add_argument('--skip-download', action='store_true')
    ap.add_argument('--out-dir', default=os.path.join(here, '..', 'data'))
    ap.add_argument('--today')
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    cleanup = None
    if args.work_dir:
        work = os.path.abspath(args.work_dir)
        os.makedirs(work, exist_ok=True)
    else:
        if args.skip_download:
            fail('--skip-download needs --work-dir or GTFS_WORK_DIR')
        work = cleanup = tempfile.mkdtemp(prefix='bus-gtfs-')
    today = dt.date.fromisoformat(args.today) if args.today else ny_today()
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    log(f'GTFS build: today (New York) = {today}, work dir = {work}')

    # ── 1. download + validate ──
    sources = []
    zips = {}
    for name, url in FEEDS:
        path = os.path.join(work, os.path.basename(url))
        if args.skip_download:
            if not os.path.exists(path):
                fail(f'{name}: {path} missing and --skip-download set')
            meta = {'bytes': os.path.getsize(path), 'lastModified': None}
            log(f'  {name}: using {path}')
        else:
            log(f'  {name}: downloading {url}')
            meta = download(url, path)
            log(f'    {meta["bytes"]:,} bytes, Last-Modified {meta["lastModified"]}')
        zips[name] = check_zip(path, name)
        info = read_csv(zips[name], 'feed_info.txt')
        info = info[0] if info else {}
        sources.append({
            'feed': name, 'url': url, 'bytes': meta['bytes'],
            'lastModified': meta['lastModified'],
            'version': info.get('feed_version') or None,
            'start': info.get('feed_start_date') or None,
            'end': info.get('feed_end_date') or None,
        })

    # ── 2. parse feeds ──
    route_info = {}        # rid -> routes.txt row (first seen)
    route_trips = {}       # rid -> trip count
    shape_cands = {}       # rid -> {(feed, shape_id): [coords, trip count]}
    # service arrays: (feed, service_id) -> {rid: [counts per 5-min sample, 72 h]}
    n_samples = SAMPLES_PER_DAY * SPILL_DAYS
    svc_arrays = {}
    active = {}            # date -> set((feed, service_id))
    window_lo, window_hi = None, None
    max_end = 0

    for name, _url in FEEDS:
        zf = zips[name]
        t0 = time.time()
        routes = read_csv(zf, 'routes.txt')
        for r in routes:
            rid = r['route_id'].strip().upper()
            route_info.setdefault(rid, r)
        trips = read_csv(zf, 'trips.txt')
        if len(trips) < MIN_TRIPS_PER_FEED:
            fail(f'{name}: only {len(trips)} trips in trips.txt')
        spans, n_rows = trip_spans(zf, name)

        # shapes used by each route, with how many trips run on each
        route_shapes = {}
        for t in trips:
            if t.get('shape_id'):
                c = route_shapes.setdefault(t['route_id'].strip().upper(), {})
                c[t['shape_id']] = c.get(t['shape_id'], 0) + 1
        needed = set()
        for c in route_shapes.values():
            needed.update(c)
        shape_pts = {}
        with zf.open('shapes.txt') as raw:
            rd = csv.reader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
            hdr = [h.strip() for h in next(rd)]
            si, la, lo_, sq = (hdr.index('shape_id'), hdr.index('shape_pt_lat'),
                               hdr.index('shape_pt_lon'), hdr.index('shape_pt_sequence'))
            for row in rd:
                sid = row[si]
                if sid in needed:
                    shape_pts.setdefault(sid, []).append(
                        (int(row[sq]), float(row[lo_]), float(row[la])))
        shape_coords = {}
        for sid, pts in shape_pts.items():
            pts.sort()
            shape_coords[sid] = [(lon, lat) for _, lon, lat in pts]
        for rid, counts in route_shapes.items():
            for sid, n in counts.items():
                c = shape_coords.get(sid)
                if c and len(c) >= 2:
                    shape_cands.setdefault(rid, {})[(name, sid)] = [c, n]

        # schedule: difference arrays per (service, route)
        untimed = 0
        too_long = 0
        diffs = {}
        for t in trips:
            span = spans.get(t['trip_id'])
            if span is None:
                untimed += 1
                continue
            rid = t['route_id'].strip().upper()
            route_trips[rid] = route_trips.get(rid, 0) + 1
            start, end = span
            max_end = max(max_end, end)
            k0 = -(-start // SAMPLE_SECONDS)      # first sample with t >= start
            k1 = -(-end // SAMPLE_SECONDS)        # first sample with t >= end (exclusive)
            if k1 > n_samples:
                too_long += 1
                k1 = n_samples
            if k1 <= k0:
                continue                          # trip shorter than the gap between samples
            key = (name, t['service_id'])
            arr = diffs.setdefault(key, {}).setdefault(rid, [0] * (n_samples + 1))
            arr[k0] += 1
            arr[k1] -= 1
        for key, by_route in diffs.items():
            for rid, arr in by_route.items():
                run, out = 0, [0] * n_samples
                for k in range(n_samples):
                    run += arr[k]
                    out[k] = run
                by_route[rid] = out
            svc_arrays[key] = by_route
        if too_long:
            log(f'    warning: {too_long} trips run past {SPILL_DAYS * 24}:00 and were clipped')

        cal = read_csv(zf, 'calendar.txt')
        cds = read_csv(zf, 'calendar_dates.txt')
        for d, sids in active_services(cal, cds).items():
            active.setdefault(d, set()).update((name, s) for s in sids)
        src = next(s for s in sources if s['feed'] == name)
        if src['start'] and src['end']:
            lo_d, hi_d = parse_gtfs_date(src['start']), parse_gtfs_date(src['end'])
        else:
            ds = [d for d, s in active.items() if any(f == name for f, _ in s)]
            lo_d, hi_d = min(ds), max(ds)
        window_lo = lo_d if window_lo is None or lo_d < window_lo else window_lo
        window_hi = hi_d if window_hi is None or hi_d > window_hi else window_hi
        log(f'  {name}: {len(routes)} routes.txt rows, {len(trips):,} trips, '
            f'{n_rows:,} stop_times rows, {len(shape_coords):,} shapes, '
            f'{len(diffs)} services ({time.time() - t0:.1f}s)'
            + (f'; {untimed} trips without stop times' if untimed else ''))

    scheduled_ids = sorted(route_trips)
    if len(scheduled_ids) < MIN_ROUTES:
        fail(f'only {len(scheduled_ids)} routes have scheduled trips (need >= {MIN_ROUTES})')

    # ── 3. route-table.json ──
    table = {}
    for rid in scheduled_ids:
        r = route_info.get(rid)
        if r is None:
            fail(f'route {rid} has trips but no routes.txt row')
        long_name = re.sub(r'\s+', ' ', r.get('route_long_name', '')).strip()
        desc = re.sub(r'\s+', ' ', r.get('route_desc', '')).strip()
        kind = route_kind(rid, long_name, desc)
        color = r.get('route_color', '').strip()
        table[rid] = {
            'short': r.get('route_short_name', '').strip() or rid,
            'long': long_name,
            'desc': desc,
            'agency': r.get('agency_id', '').strip(),
            'color': f'#{color.upper()}' if color else '#4488FF',
            'kind': kind,
            'group': route_group(rid, kind),
        }
    unscheduled = {}
    for rid, r in sorted(route_info.items()):
        if rid in table:
            continue
        unscheduled[rid] = {
            'short': r.get('route_short_name', '').strip() or rid,
            'long': re.sub(r'\s+', ' ', r.get('route_long_name', '')).strip(),
            'agency': r.get('agency_id', '').strip(),
        }
    os.makedirs(os.path.join(out_dir, 'routes'), exist_ok=True)
    os.makedirs(os.path.join(out_dir, 'gtfs'), exist_ok=True)
    table_doc = {
        'generatedAt': generated_at,
        'generatedBy': 'nyc-bus-tracker/scripts/build_gtfs.py',
        'note': ('routes: every route with scheduled trips in the MTA bus GTFS feeds, keyed by '
                 'the uppercase GTFS route_id, which is the id the live BusTime feed uses '
                 '(e.g. "BX12+", "Q06"). kind: express if the id starts BM/BXM/QM/SIM/X plus '
                 'a digit; sbs if it ends in "+"; limited if the GTFS long name or description '
                 'says Limited or LTD; otherwise local. group: "X" for express, otherwise the '
                 'borough prefix (Bx, B, M, Q, S). unscheduledRoutes: ids listed in routes.txt '
                 'with no scheduled trips, almost all subway shuttle buses (B90, L92, T-series).'),
        'source': {'window': {'start': window_lo.isoformat(), 'end': window_hi.isoformat()},
                   'feeds': sources},
        'routes': table,
        'unscheduledRoutes': unscheduled,
    }
    with open(os.path.join(out_dir, 'routes', 'route-table.json'), 'w') as fh:
        json.dump(table_doc, fh, indent=1, ensure_ascii=False)
        fh.write('\n')

    # ── 4. routes.geojson ──
    features = []
    no_shape = []
    not_longest = []
    n_pts_raw = n_pts = 0
    for rid in scheduled_ids:
        if rid not in shape_cands:
            no_shape.append(rid)
            continue
        raw, chose_longest = pick_shape(shape_cands[rid])
        if not chose_longest:
            not_longest.append(rid)
        coords = simplify(raw, SIMPLIFY_TOLERANCE_M)
        n_pts_raw += len(raw)
        n_pts += len(coords)
        t = table[rid]
        features.append({
            'type': 'Feature',
            'properties': {'route': rid, 'routeId': rid, 'short': t['short'],
                           'color': t['color'], 'longName': t['long'], 'kind': t['kind']},
            'geometry': {'type': 'LineString', 'coordinates': coords},
        })
    if no_shape:
        log(f'  warning: no shape for {len(no_shape)} routes: {", ".join(no_shape)}')
    if not_longest:
        log(f'  used a shape other than the longest (better trip coverage) for: '
            f'{", ".join(not_longest)}')
    geo_path = os.path.join(out_dir, 'routes', 'routes.geojson')
    with open(geo_path, 'w') as fh:
        json.dump({'type': 'FeatureCollection', 'features': features}, fh,
                  separators=(',', ':'), ensure_ascii=False)
    geo_size = os.path.getsize(geo_path)
    log(f'routes.geojson: {len(features)} routes, {n_pts:,} points '
        f'(from {n_pts_raw:,} before simplifying), {geo_size / 1e6:.2f} MB')
    if len(features) < MIN_ROUTES:
        fail(f'routes.geojson has only {len(features)} features')
    if geo_size > 2_500_000:
        log('  warning: routes.geojson is over 2.5 MB')

    # ── 5. scheduled-service.json ──
    pattern_cache = {}
    new_patterns = {}
    new_dates = {}
    lookback = min(SPILL_DAYS, max(1, -(-max_end // 86400)))
    log(f'latest scheduled arrival is {max_end // 3600}:{max_end % 3600 // 60:02d} on its '
        f'service day; each date draws on {lookback} service day(s)')

    def service_pattern(d):
        keys = tuple(frozenset(active.get(d - dt.timedelta(days=back), ()))
                     for back in range(lookback))
        if keys in pattern_cache:
            return pattern_cache[keys]
        per_route = {}
        for back, sids in enumerate(keys):
            off = back * SAMPLES_PER_DAY
            for key in sids:
                for rid, arr in svc_arrays.get(key, {}).items():
                    seg = arr[off:off + SAMPLES_PER_DAY]
                    acc = per_route.get(rid)
                    per_route[rid] = seg if acc is None else [a + b for a, b in zip(acc, seg)]
        pat = {}
        for rid, acc in per_route.items():
            hours = [round(sum(acc[h * 12:(h + 1) * 12]) / 12, 1) for h in range(24)]
            if any(hours):
                pat[rid] = hours
        pid = pattern_id(pat)
        pattern_cache[keys] = (pid, pat)
        return pid, pat

    d = window_lo
    while d <= window_hi:
        pid, pat = service_pattern(d)
        new_patterns[pid] = pat
        new_dates[d.isoformat()] = pid
        d += dt.timedelta(days=1)

    sched_path = os.path.join(out_dir, 'gtfs', 'scheduled-service.json')
    old = None
    if os.path.exists(sched_path):
        try:
            old = json.load(open(sched_path))
        except Exception as e:
            fail(f'existing {sched_path} is not valid JSON ({e}); refusing to drop its history')
    dates_out, patterns_out = {}, {}
    today_s = today.isoformat()
    kept_past = added_past = kept_future = 0
    if old:
        old_patterns = old.get('patterns', {})
        old_full = {pid: pattern_id(p) for pid, p in old_patterns.items()}
        for ds, pid in old.get('dates', {}).items():
            if ds < today_s or ds not in new_dates:
                if pid not in old_patterns:
                    fail(f'existing file: date {ds} points at missing pattern {pid}')
                dates_out[ds] = old_full[pid]
                patterns_out[old_full[pid]] = old_patterns[pid]
                if ds < today_s:
                    kept_past += 1
                else:
                    kept_future += 1
    for ds, pid in new_dates.items():
        if ds >= today_s or ds not in dates_out:
            if ds < today_s:
                added_past += 1
            dates_out[ds] = pid
            patterns_out[pid] = new_patterns[pid]
    # drop patterns nothing references
    used = set(dates_out.values())
    patterns_out = {p: v for p, v in patterns_out.items() if p in used}
    # ids are content hashes; print the shortest prefix (>= 8 hex) that stays unique
    plen = 8
    while len({p[:plen] for p in patterns_out}) < len(patterns_out):
        plen += 2
    rename = {p: p[:plen] for p in patterns_out}
    sched_doc = {
        'generatedAt': generated_at,
        'method': METHOD,
        'source': {'window': {'start': window_lo.isoformat(), 'end': window_hi.isoformat()},
                   'feeds': [{k: s[k] for k in ('feed', 'version', 'start', 'end')}
                             for s in sources]},
        'patterns': {rename[p]: v for p, v in patterns_out.items()},
        'dates': {ds: rename[p] for ds, p in dates_out.items()},
    }
    write_schedule(sched_path, sched_doc)
    log(f'scheduled-service.json: {len(sched_doc["dates"])} dates '
        f'({sched_doc_min(sched_doc)} to {sched_doc_max(sched_doc)}), '
        f'{len(sched_doc["patterns"])} patterns, {os.path.getsize(sched_path) / 1e6:.2f} MB'
        + (f'; kept {kept_past} past dates and {kept_future} uncovered future dates from the '
           f'previous file, added {added_past} missing past dates' if old else ''))

    # ── 6. sanity checks ──
    by_kind, by_group = {}, {}
    for t in table.values():
        by_kind[t['kind']] = by_kind.get(t['kind'], 0) + 1
        by_group[t['group']] = by_group.get(t['group'], 0) + 1
    log(f'route-table.json: {len(table)} scheduled routes; by kind {dict(sorted(by_kind.items()))}; '
        f'by group {dict(sorted(by_group.items()))}; {len(unscheduled)} unscheduled ids')

    # representative weekday: the most common pattern among Tue-Thu dates from today on
    mid = [dd for dd in sorted(new_dates)
           if dt.date.fromisoformat(dd).weekday() in (1, 2, 3) and dd >= today_s]
    if not mid:
        mid = [dd for dd in sorted(new_dates) if dt.date.fromisoformat(dd).weekday() in (1, 2, 3)]
    counts = {}
    for dd in mid:
        counts[new_dates[dd]] = counts.get(new_dates[dd], 0) + 1
    wk_pid = max(counts, key=lambda p: counts[p])
    wk_dates = [x for x in mid if new_dates[x] == wk_pid]
    wk = new_patterns[wk_pid]
    totals = [round(sum(v[h] for v in wk.values())) for h in range(24)]
    log(f'typical weekday pattern {wk_pid[:plen]} ({len(wk_dates)} Tue-Thu dates, e.g. '
        f'{wk_dates[0]}): system scheduled trips in progress by hour')
    log('  ' + ' '.join(f'{h}h:{totals[h]}' for h in range(24)))
    log(f'  8am {totals[8]}, noon {totals[12]}, 6pm {totals[18]}, 10pm {totals[22]}')
    lo_b, hi_b = WEEKDAY_8AM_HARD
    if not lo_b <= totals[8] <= hi_b:
        fail(f'weekday 8am scheduled total {totals[8]} outside {lo_b}-{hi_b}')
    if not WEEKDAY_8AM_EXPECT[0] <= totals[8] <= WEEKDAY_8AM_EXPECT[1]:
        log(f'  warning: weekday 8am total {totals[8]} outside the expected '
            f'{WEEKDAY_8AM_EXPECT[0]}-{WEEKDAY_8AM_EXPECT[1]}')
    zero = sorted(r for r in table if r not in wk)
    log(f'  routes with no scheduled trips on that weekday ({len(zero)}): '
        + (', '.join(zero) if zero else 'none'))
    zero_day = sorted(r for r in table if r in wk and not any(wk[r][6:23]))
    if zero_day:
        log(f'  routes with weekday trips only outside 6am-11pm: {", ".join(zero_day)}')
    for rid in ('M15+', 'B6'):
        if rid in wk:
            log(f'  {rid} weekday: ' + ' '.join(fmt_num(v) for v in wk[rid]))

    if cleanup:
        shutil.rmtree(cleanup, ignore_errors=True)
    log('GTFS build done.')


def sched_doc_min(doc):
    return min(doc['dates']) if doc['dates'] else '-'


def sched_doc_max(doc):
    return max(doc['dates']) if doc['dates'] else '-'


if __name__ == '__main__':
    main()
