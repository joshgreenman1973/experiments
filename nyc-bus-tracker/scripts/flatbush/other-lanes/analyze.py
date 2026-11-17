#!/usr/bin/env python3
"""Before/after bus speeds on project corridors, with same-route control segments (difference-in-differences).

Inputs: projects.py, corridors.json (build_corridors.py), segments.csv + segments.geojson (build_segments.py),
        mta/<ROUTE>.csv (this folder, then ../mta; downloaded by mta_seg.py).
Output: results.json

Rules (see README.md):
- weekday rows only; all-day = hour_of_day 7..18; peak = hour_of_day 7,8,9 and 16,17,18; PM = 16,17,18
- speed = sum(road_distance * trips) / sum(average_travel_time * trips / 60)
- corridor segments: project routes, overlap share >= 0.50 with the project corridor (direction-aware)
- control segments: the routes that contribute corridor segments; segments with overlap < 0.10 with every
  project corridor and every other 2023+ DOT bus lane
- after months: up to 12 full months starting the month after opening, through Oct 2026
- before month for after month A: A-12; if that is in/after the construction month (or the opening month when
  construction start is unknown), A-24; if that is before Jan 2023, the pair is dropped
- matching within a month pair (same route and direction): a segment in the after month is matched to a segment in
  the before month whose start and end stops are each within 150 m (this survives stop-ID renumbering); if timepoints
  were re-cut, a chain of up to 3 consecutive segments on one side may match a chain on the other with the same start
  and end. A match counts only if road distance (trip-weighted, per month) differs by no more than 3% (path check).
"""
import csv, json, os, collections, math
import numpy as np
from projects import PROJECTS
from geo import Corridor, to_xy, COMPASS
from build_segments import route_files

HERE = os.path.dirname(os.path.abspath(__file__))
KEEP = 0.50
CTRL_MAX = 0.10
DIAG_MIN = 0.25
PATH_TOL = 0.03
SAME_STOP_M = 150.0
WINDOWS = {'all': set(range(7, 19)), 'peak': {7, 8, 9, 16, 17, 18}, 'pm': {16, 17, 18}}
FIRST, LAST = (2023, 1), (2026, 10)
EXPRESS_PREFIX = ('X', 'BXM', 'QM', 'BM', 'SIM')


def ym_add(ym, k):
    i = ym[0] * 12 + (ym[1] - 1) + k
    return (i // 12, i % 12 + 1)


def ym_str(ym):
    return f'{ym[0]}-{ym[1]:02d}'


def ym_of(date):
    return (int(date[:4]), int(date[5:7]))


ALL_MONTHS = []
_m = FIRST
while _m <= LAST:
    ALL_MONTHS.append(_m)
    _m = ym_add(_m, 1)


def is_express(route):
    return route.startswith(EXPRESS_PREFIX)


def load_route(path):
    """agg[(route,dir,from,to)][ym][window] = [sum(rd*trips), sum(hours*trips), trips]"""
    agg = collections.defaultdict(lambda: collections.defaultdict(lambda: {w: [0.0, 0.0, 0] for w in WINDOWS}))
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if not r['next_timepoint_stop_id']:
                continue
            h = int(r['hour_of_day'])
            if h not in WINDOWS['all']:
                continue
            try:
                rd = float(r['road_distance']); tt = float(r['average_travel_time']); n = int(float(r['bus_trip_count']))
            except ValueError:
                continue
            if n <= 0 or tt <= 0:
                continue
            k = (r['route_id'], r['direction'], r['timepoint_stop_id'], r['next_timepoint_stop_id'])
            cell = agg[k][(int(r['year']), int(r['month']))]
            for w, hrs in WINDOWS.items():
                if h in hrs:
                    c = cell[w]
                    c[0] += rd * n; c[1] += tt * n / 60.0; c[2] += n
    return agg


def periods(p):
    opened = ym_of(p['opened'])
    cut = ym_of(p['constructionStart']) if p.get('constructionStart') else opened
    pairs, dropped = [], []
    for k in range(1, 13):
        A = ym_add(opened, k)
        if A > LAST:
            break
        B = ym_add(A, -12)
        shifted = False
        if B >= cut:
            B = ym_add(A, -24)
            shifted = True
        if B < FIRST or B >= cut:
            dropped.append(ym_str(A))
            continue
        pairs.append((A, B, shifted))
    return pairs, dropped


def dist_m(p, q):
    return math.hypot((p[1] - q[1]) * 84300.0, (p[0] - q[0]) * 111200.0)


def speed(acc):
    return acc[0] / acc[1] if acc[1] > 0 else None


class Matcher:
    def __init__(self, agg, info):
        self.agg = agg
        self.info = info  # key -> dict(a=(lat,lon), b=(lat,lon))

    def present(self, keys, ym):
        out = {}
        for k in keys:
            c = self.agg.get(k, {}).get(ym)
            if c and c['all'][2] > 0:
                out[k] = c['all'][0] / c['all'][2]  # trip-weighted road distance that month
        return out

    def chains(self, segs):
        """All chains of 1-3 consecutive segments: (start, end, total_rd, [keys])"""
        out = []
        ks = list(segs)
        for k in ks:
            out.append((self.info[k]['a'], self.info[k]['b'], segs[k], [k]))
        ext = [c for c in out]
        for _ in range(2):
            new = []
            for st, en, rd, kl in ext:
                for k in ks:
                    if k in kl:
                        continue
                    if dist_m(en, self.info[k]['a']) <= SAME_STOP_M:
                        new.append((st, self.info[k]['b'], rd + segs[k], kl + [k]))
            out += new
            ext = new
        return out

    def match(self, keys, A, B):
        """Returns (matched list of (keysA, keysB)), n_path_dropped, n_unmatched."""
        byrd = collections.defaultdict(list)
        for k in keys:
            byrd[(k[0], k[1])].append(k)
        matched, path_drop, unmatched = [], [], 0
        for grp, ks in byrd.items():
            sa, sb = self.present(ks, A), self.present(ks, B)
            if not sa and not sb:
                continue
            ca, cb = self.chains(sa), self.chains(sb)
            cand = []
            for i, (s1, e1, r1, k1) in enumerate(ca):
                for j, (s2, e2, r2, k2) in enumerate(cb):
                    if len(k1) > 1 and len(k2) > 1:
                        continue  # one side must be a single segment
                    d = dist_m(s1, s2) + dist_m(e1, e2)
                    if dist_m(s1, s2) <= SAME_STOP_M and dist_m(e1, e2) <= SAME_STOP_M:
                        rel = abs(r1 - r2) / r2
                        cand.append((len(k1) + len(k2), rel > PATH_TOL, d, rel, k1, k2, r1, r2))
            cand.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
            usedA, usedB = set(), set()
            for n, bad, d, rel, k1, k2, r1, r2 in cand:
                if usedA & set(k1) or usedB & set(k2):
                    continue
                usedA |= set(k1); usedB |= set(k2)
                if bad:
                    path_drop.append((k1, k2, r2, r1))
                else:
                    matched.append((k1, k2))
            unmatched += len(set(sa) - usedA) + len(set(sb) - usedB)
        return matched, path_drop, unmatched

    def compare(self, keys, pairs, windows=('all', 'peak', 'pm')):
        acc = {w: ([0.0, 0.0], [0.0, 0.0]) for w in windows}  # (before, after)
        used = collections.Counter(); drops = []; unmatched = 0; pairs_used = set()
        for A, B, _ in pairs:
            m, pd, um = self.match(keys, A, B)
            drops += [(ym_str(A), ym_str(B)) + x for x in pd]
            unmatched += um
            for kA, kB in m:
                for w in windows:
                    aw = [self.agg[k][A][w] for k in kA]; bw = [self.agg[k][B][w] for k in kB]
                    if sum(x[2] for x in aw) == 0 or sum(x[2] for x in bw) == 0:
                        continue
                    for x in aw:
                        acc[w][1][0] += x[0]; acc[w][1][1] += x[1]
                    for x in bw:
                        acc[w][0][0] += x[0]; acc[w][0][1] += x[1]
                for k in set(kA) | set(kB):
                    used[k] += 1
                pairs_used.add((A, B))
        out = {w: (speed(acc[w][0]), speed(acc[w][1])) for w in windows}
        return dict(speeds=out, used=used, drops=drops, unmatched=unmatched, pairs_used=sorted(pairs_used),
                    n_matches=sum(1 for _ in used))


def monthly(agg, segs, miles=False):
    out = []
    for ym in ALL_MONTHS:
        acc = [0.0, 0.0]; mi = 0.0
        for s in segs:
            c = agg.get(s, {}).get(ym)
            if c and c['all'][2]:
                acc[0] += c['all'][0]; acc[1] += c['all'][1]; mi += c['all'][0] / c['all'][2]
        if miles:
            out.append(round(mi, 2))
            continue
        v = speed(acc)
        out.append(round(v, 3) if v else None)
    return out


def r3(x):
    return None if x is None else round(x, 3)


def pct(b, a):
    return None if not b or not a else round(100 * (a / b - 1), 2)


def coverage(corridor_feats, seg_lines):
    """Share of corridor length (each direction drawn separately) that kept segments run along, same direction."""
    if not seg_lines:
        return 0.0
    C = Corridor(seg_lines, oriented=True)
    tot = cov = 0.0
    for f in corridor_feats:
        P = to_xy([c[1] for c in f['coords']], [c[0] for c in f['coords']])
        d = f['dir']
        if d:
            if np.dot(P[-1] - P[0], COMPASS[d]) < 0:
                P = P[::-1]
            sh, L = C.overlap(P)
        else:
            sh1, L = C.overlap(P)
            sh2, _ = C.overlap(P[::-1])
            sh = max(sh1, sh2)  # direction-free corridor (one-way street): either orientation
        tot += L; cov += sh * L
    return cov / tot if tot else 0.0


def main():
    seg_rows = list(csv.DictReader(open(os.path.join(HERE, 'segments.csv'))))
    gj = json.load(open(os.path.join(HERE, 'segments.geojson')))['features']
    key = lambda r: (r['route'], r['direction'], r['from_id'], r['to_id'])
    seg_geo = {key(row): f['geometry']['coordinates'] for row, f in zip(seg_rows, gj)}
    info = {key(r): dict(a=(float(r['from_lat']), float(r['from_lon'])), b=(float(r['to_lat']), float(r['to_lon'])))
            for r in seg_rows}
    cj = json.load(open(os.path.join(HERE, 'corridors.json')))
    pids = [str(p['id']) for p in PROJECTS]
    files = route_files()
    cache = {}

    def agg_for(routes):
        out = {}
        for rt in routes:
            if rt in files:
                if rt not in cache:
                    cache[rt] = load_route(files[rt])
                out.update(cache[rt])
        return out

    results = []
    for p in PROJECTS:
        pid = str(p['id'])
        flags = list(p.get('notes', []))
        routes = p['routes']
        miss = [r for r in routes if r not in files]
        if miss:
            flags.append('Route files not downloaded: ' + ', '.join(miss))
        agg = agg_for(routes)
        M = Matcher(agg, info)
        rows = [r for r in seg_rows if r['route'] in routes]
        kept = [r for r in rows if float(r[f'ov{pid}']) >= KEEP]
        kept_k = [key(r) for r in kept]
        pairs, dropped = periods(p)
        if dropped:
            flags.append('After months with no usable before month (the matching month one and two years earlier is '
                         'missing from the data or falls in construction): ' + ', '.join(dropped))
        shifted = [ym_str(B) for A, B, s in pairs if s]
        if shifted:
            flags.append('Before months taken two years earlier because one year earlier overlapped construction: ' + ', '.join(shifted))
        if not p.get('constructionStart'):
            flags.append('Construction start unknown: before months are limited to months before the opening month.')
        res = dict(id=p['id'], name=p['name'], borough=p['borough'], opened=p['opened'],
                   constructionStart=p.get('constructionStart'), routes=routes, cityClaim=p.get('cityClaim'))
        co = M.compare(kept_k, pairs) if kept else None
        used_routes = sorted({k[0] for k in co['used']}) if co else []
        ctrl_routes = used_routes or routes
        ctrl = [r for r in rows if r['route'] in ctrl_routes
                and max(float(r[f'ov{q}']) for q in pids) < CTRL_MAX and float(r['ov_other']) < CTRL_MAX]
        ctrl_k = [key(r) for r in ctrl]
        cc = M.compare(ctrl_k, pairs, ('all',)) if pairs else None

        used_lines = []
        for r in kept:
            if co and co['used'][key(r)]:
                c = seg_geo[key(r)]
                used_lines.append((to_xy([x[1] for x in c], [x[0] for x in c]), ''))
        res['corridorCoveredShare'] = round(coverage(cj['projects'][pid], used_lines), 3)
        res['segments'] = [dict(route=r['route'], direction=r['direction'], **{'from': r['from_name']}, to=r['to_name'],
                                miles=float(r['miles']), overlapShare=float(r[f'ov{pid}']),
                                dataMonths=f"{r['first_month']} to {r['last_month']}",
                                monthsUsed=(co['used'][key(r)] if co else 0)) for r in kept]
        usedpairs = co['pairs_used'] if co else []
        res['afterMonths'] = [ym_str(A) for A, B in usedpairs]
        res['beforeMonths'] = [ym_str(B) for A, B in usedpairs]
        res['nAfterMonths'] = len(usedpairs)
        sp = co['speeds'] if co else {}
        b, a = sp.get('all', (None, None))
        res['before_mph'] = r3(b); res['after_mph'] = r3(a)
        res['change_mph'] = r3(a - b) if a and b else None
        res['change_pct'] = pct(b, a)
        pb, pa = sp.get('peak', (None, None))
        res['peak_before'] = r3(pb); res['peak_after'] = r3(pa); res['peak_change_pct'] = pct(pb, pa)
        mb, ma = sp.get('pm', (None, None))
        res['pm_peak_before'] = r3(mb); res['pm_peak_after'] = r3(ma); res['pm_peak_change_pct'] = pct(mb, ma)
        cb, ca = cc['speeds']['all'] if cc else (None, None)
        res['control_before'] = r3(cb); res['control_after'] = r3(ca)
        res['control_change_mph'] = r3(ca - cb) if ca and cb else None
        res['control_change_pct'] = pct(cb, ca)
        res['controlRoutes'] = ctrl_routes
        res['controlSegmentsUsed'] = len([k for k in ctrl_k if cc and cc['used'][k]])
        res['controlMilesUsed'] = round(sum(float(r['miles']) for r in ctrl if cc and cc['used'][key(r)]), 2)
        if res['change_mph'] is not None and res['control_change_mph'] is not None:
            res['diff_in_diff_mph'] = r3(res['change_mph'] - res['control_change_mph'])
            res['diff_in_diff_pct_pts'] = round(res['change_pct'] - res['control_change_pct'], 2)
        else:
            res['diff_in_diff_mph'] = None; res['diff_in_diff_pct_pts'] = None

        # month-by-month spread: DiD computed separately for each matched month pair
        if co and usedpairs and cc:
            per = []
            for A_, B_, sh_ in pairs:
                if (A_, B_) not in usedpairs:
                    continue
                c1 = M.compare(kept_k, [(A_, B_, sh_)], ('all',))['speeds']['all']
                c2 = M.compare(ctrl_k, [(A_, B_, sh_)], ('all',))['speeds']['all']
                if all(c1) and all(c2):
                    per.append(dict(after=ym_str(A_), before=ym_str(B_), corridor_change_mph=r3(c1[1] - c1[0]),
                                    control_change_mph=r3(c2[1] - c2[0]), did_mph=r3((c1[1] - c1[0]) - (c2[1] - c2[0]))))
            res['byMonthPair'] = per
            d = [x['did_mph'] for x in per]
            if len(d) >= 2:
                mu = sum(d) / len(d)
                sd = math.sqrt(sum((x - mu) ** 2 for x in d) / (len(d) - 1))
                res['did_month_pairs'] = dict(n=len(d), positive=sum(1 for x in d if x > 0), min=min(d), max=max(d),
                                              mean=r3(mu), se=r3(sd / math.sqrt(len(d))))

        # sensitivity: local-route-only control when express routes are in the mix
        if any(is_express(r) for r in ctrl_routes) and any(not is_express(r) for r in ctrl_routes) and cc:
            loc = [k for k in ctrl_k if not is_express(k[0])]
            lc = M.compare(loc, pairs, ('all',))
            lb, la = lc['speeds']['all']
            exp_mi = sum(float(r['miles']) for r in ctrl if cc['used'][key(r)] and is_express(r['route']))
            if lb and la and res['change_mph'] is not None:
                flags.append(f"Control mix: {100*exp_mi/max(res['controlMilesUsed'],1e-9):.0f}% of control miles are express-route segments. "
                             f"Local-routes-only control: {lb:.3f} -> {la:.3f} mph ({la-lb:+.3f}), "
                             f"giving diff-in-diff {res['change_mph']-(la-lb):+.3f} mph.")
                res['control_local_only'] = dict(before=r3(lb), after=r3(la), change_mph=r3(la - lb),
                                                 diff_in_diff_mph=r3(res['change_mph'] - (la - lb)))

        # sensitivity: corridor measured on local routes only, when express routes also contribute
        if co and any(is_express(r) for r in used_routes) and any(not is_express(r) for r in used_routes):
            lk = [k for k in kept_k if not is_express(k[0])]
            lc2 = M.compare(lk, pairs, ('all',))
            lb2, la2 = lc2['speeds']['all']
            if lb2 and la2:
                flags.append(f"Local routes only on the corridor: {lb2:.3f} -> {la2:.3f} mph ({pct(lb2, la2):+.2f}%).")
                res['corridor_local_only'] = dict(before=r3(lb2), after=r3(la2), change_pct=pct(lb2, la2))

        if not kept:
            best = sorted(rows, key=lambda r: -float(r[f'ov{pid}']))
            best = [r for r in best if float(r[f'ov{pid}']) >= DIAG_MIN]
            top = sorted(rows, key=lambda r: -float(r[f'ov{pid}']))[:3]
            flags.insert(0, 'NOT MEASURABLE with MTA timepoint data: no segment of the project routes has >=50% of its length on the corridor. '
                         'Closest: ' + '; '.join(f"{r['route']} {r['direction']} {r['from_name']} -> {r['to_name']} "
                                                 f"({float(r['miles']):.2f} mi, {100*float(r[f'ov{pid}']):.0f}% on corridor)" for r in top))
            if best and pairs:
                dg = M.compare([key(r) for r in best], pairs, ('all',))
                db, da = dg['speeds']['all']
                res['diagnosticLowOverlap'] = dict(
                    note='NOT a corridor measurement: segments with 25-49% of their length on the corridor, same months and rules. '
                         'Any corridor effect is diluted by the off-corridor share.',
                    segments=[f"{r['route']} {r['direction']} {r['from_name']} -> {r['to_name']} ({100*float(r[f'ov{pid}']):.0f}%)" for r in best],
                    before_mph=r3(db), after_mph=r3(da), change_pct=pct(db, da),
                    control_change_mph=res['control_change_mph'],
                    months=[ym_str(A) for A, B in dg['pairs_used']])
        elif not usedpairs:
            flags.insert(0, 'NOT MEASURABLE: corridor segments exist but none could be matched across any before/after month pair.')
        if co:
            if co['drops']:
                ex = co['drops'][0]
                flags.append(f"Path check: {len(co['drops'])} segment-month matches dropped because road_distance changed >3% "
                             f"(e.g. {ex[2][0][0]} {ex[2][0][1]} {ex[0]} vs {ex[1]}: {ex[4]:.3f} -> {ex[5]:.3f} mi).")
            if co['unmatched']:
                flags.append(f"{co['unmatched']} segment-months on the corridor had no counterpart in the paired month "
                             f"(service pattern or timepoints changed) and were left out.")
        if cc and cc['drops']:
            flags.append(f"Control: {len(cc['drops'])} segment-month matches dropped by the path check.")
        if kept and res['corridorCoveredShare'] < 0.5:
            flags.append(f"Matched segments run along only {100*res['corridorCoveredShare']:.0f}% of the corridor's directional length.")
        if 0 < res['nAfterMonths'] < 6:
            flags.append(f"Only {res['nAfterMonths']} matched month pair(s).")
        res['flags'] = flags
        # monthly series use the segments that entered the before/after comparison, so chart levels track it
        corr_m = [k for k in kept_k if co and co['used'][k]] or kept_k
        ctrl_m = [k for k in ctrl_k if cc and cc['used'][k]] or ctrl_k
        res['monthly'] = {'months': [ym_str(m) for m in ALL_MONTHS],
                          'corridor': monthly(agg, corr_m) if kept else [None] * len(ALL_MONTHS),
                          'control': monthly(agg, ctrl_m),
                          'corridorSegmentMiles': monthly(agg, corr_m, miles=True) if kept else [0] * len(ALL_MONTHS),
                          'note': 'Weekday 7am-7pm trip-weighted mph over the corridor and control segments used in the '
                                  'before/after comparison; segments drop in and out as MTA re-cuts timepoints '
                                  '(corridorSegmentMiles = summed length of the corridor segments with data that month).'}
        results.append(res)
        print(f"{p['id']:>2} {p['name'][:42]:42} {res['before_mph']} -> {res['after_mph']} ({res['change_pct']}%) "
              f"ctrl {res['control_change_mph']} DiD {res['diff_in_diff_mph']} n={res['nAfterMonths']} "
              f"segs={sum(1 for s in res['segments'] if s['monthsUsed'])}/{len(kept)} cov={res['corridorCoveredShare']}")
    with open(os.path.join(HERE, 'results.json'), 'w') as fh:
        json.dump(results, fh, indent=1)


if __name__ == '__main__':
    main()
