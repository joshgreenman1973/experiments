"""Turn camera tickets into camera locations.

The city will not publish where its automated enforcement cameras are. But every
ticket a camera writes carries the corner it was written at, so the set of
distinct locations in the ticket data is the set of cameras that were running.

Department of Finance splits that location across two 20-character columns
(street_name, intersecting_street), so the first job is putting the string back
together, then splitting it into a travel direction and two street names, then
looking the pair up in the Centerline-derived intersection gazetteer.
"""
import json
import os
import re
import sys
from collections import defaultdict
from difflib import get_close_matches

sys.path.insert(0, os.path.dirname(__file__))
from streets import normalize, strip_direction, variants

RAW = os.path.join(os.path.dirname(__file__), '..', 'raw')
DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
COUNTY = {'NY': 'MN', 'MN': 'MN', 'BX': 'BX', 'BRONX': 'BX', 'K': 'BK', 'BK': 'BK',
          'KINGS': 'BK', 'Q': 'QN', 'QN': 'QN', 'QUEENS': 'QN', 'R': 'ST', 'ST': 'ST',
          'RICH': 'ST'}
BORO_NAME = {'MN': 'Manhattan', 'BX': 'Bronx', 'BK': 'Brooklyn',
             'QN': 'Queens', 'ST': 'Staten Island'}


def rejoin(a, b):
    """Reassemble a location split across two 20-character columns."""
    a = (a or '').rstrip('\n')
    b = (b or '')
    if len(a) >= 20:          # column filled to the brim: no character was lost
        return a + b
    return (a + ' ' + b).strip() if b else a


def parse(loc):
    """('WB N CONDUIT AVE @ 88TH ST') -> ('WB', 'N CONDUIT AVE', '88TH ST')"""
    s = re.sub(r'\s+', ' ', (loc or '').upper()).strip()
    s = s.replace('@', ' @ ')
    s = re.sub(r'\s+', ' ', s).strip()
    if '@' not in s:
        return None
    left, right = s.split('@', 1)
    d1, street = strip_direction(left)
    d2, cross = strip_direction(right)
    return (d1 or d2), street.strip(), cross.strip()


def main():
    index = json.load(open(os.path.join(RAW, 'intersection_index.json')))
    # secondary index ignoring borough, for rows with a bad county code
    noboro = defaultdict(list)
    names_by_boro = defaultdict(set)
    for k, v in index.items():
        a, b, boro = k.split('|')
        noboro[(a, b)].append(v)
        names_by_boro[boro].add(a)
        names_by_boro[boro].add(b)
    names_by_boro['*'] = set().union(*names_by_boro.values())
    # Sorted lists, not sets: difflib picks among equally close candidates in
    # iteration order, and set order varies between runs with hash seeding,
    # which would make the same inputs produce slightly different coordinates.
    names_by_boro = {k: sorted(v) for k, v in names_by_boro.items()}
    ctx = (index, noboro, names_by_boro)

    raw = json.load(open(os.path.join(RAW, 'violation_locations.json')))

    # kind -> location string -> merged record
    merged = defaultdict(dict)
    for key, rows in raw.items():
        kind, dataset = key.split('|')
        for r in rows:
            loc = rejoin(r.get('street_name'), r.get('intersecting_street'))
            p = parse(loc)
            if not p:
                continue
            direction, street, cross = p
            boro = COUNTY.get((r.get('violation_county') or '').upper().strip(), '')
            ident = (street, cross, direction, boro)
            rec = merged[kind].setdefault(ident, {
                'street': street, 'cross': cross, 'direction': direction,
                'boro': boro, 'tickets': 0, 'raw': loc,
                'first_seen': None, 'last_seen': None})
            rec['tickets'] += int(r.get('n', 0))
            for f, cmpf in (('first_seen', min), ('last_seen', max)):
                v = r.get(f)
                if v:
                    rec[f] = v if rec[f] is None else cmpf(rec[f], v)

    stats = {}
    out = {}
    for kind, recs in merged.items():
        located, missed = [], []
        for rec in recs.values():
            # "70 ST / 45 AVE" names two cross streets; the first will do.
            cross = rec['cross'].split('/')[0].strip() or rec['cross']
            a, b = normalize(rec['street']), normalize(cross)
            pt, how = lookup(ctx, a, b, rec['boro'])
            if pt:
                rec['lon'], rec['lat'] = pt[0], pt[1]
                rec['borough'] = BORO_NAME.get(rec['boro'], '')
                rec['match'] = how
                located.append(rec)
            else:
                missed.append(rec)
        stats[kind] = {
            'distinct_locations': len(recs),
            'located': len(located),
            'unlocated': len(missed),
            'tickets_total': sum(r['tickets'] for r in recs.values()),
            'tickets_located': sum(r['tickets'] for r in located),
        }
        out[kind] = located
        json.dump(sorted(missed, key=lambda r: -r['tickets']),
                  open(os.path.join(RAW, 'unlocated_%s.json' % kind), 'w'), indent=1)

    for kind, s in stats.items():
        rate = 100.0 * s['located'] / max(1, s['distinct_locations'])
        trate = 100.0 * s['tickets_located'] / max(1, s['tickets_total'])
        print('%-9s %5d locations, %5d located (%.1f%%), %.1f%% of tickets'
              % (kind, s['distinct_locations'], s['located'], rate, trate))

    json.dump(out, open(os.path.join(RAW, 'enforcement_located.json'), 'w'))
    json.dump(stats, open(os.path.join(DATA, 'enforcement_stats.json'), 'w'), indent=1)


def _try(ctx, sa, sb, boro):
    index, noboro, _ = ctx
    for va in sa:
        for vb in sb:
            k1, k2 = sorted([va, vb])
            hit = index.get('%s|%s|%s' % (k1, k2, boro))
            if hit:
                return hit
    for va in sa:
        for vb in sb:
            k1, k2 = sorted([va, vb])
            hits = noboro.get((k1, k2))
            if hits and len(hits) == 1:
                return hits[0]
    return None


def _expand(ctx, name, boro):
    """Candidate real street names for a possibly truncated or misspelt one."""
    names = ctx[2].get(boro) or ctx[2]['*']
    cands = list(variants(name))
    seen = set(cands)
    # The location field is capped at 40 characters, so the second street is
    # often cut off mid-word: "SPRINGFIELD BL", "MANHATTAN COLLE".
    extra = []
    if len(name) >= 5:
        extra += [n for n in names if n.startswith(name)]
    if len(cands) + len(extra) <= 40:
        extra += get_close_matches(name, names, n=3, cutoff=0.88)
    for n in extra:
        if n not in seen:
            seen.add(n)
            cands.append(n)
    return cands


def lookup(ctx, a, b, boro):
    """Find the corner where streets a and b meet, trying spelling variants."""
    if not a or not b:
        return None, None
    hit = _try(ctx, variants(a), variants(b), boro)
    if hit:
        return hit, 'exact'
    hit = _try(ctx, _expand(ctx, a, boro), _expand(ctx, b, boro), boro)
    if hit:
        return hit, 'fuzzy'
    return None, None


if __name__ == '__main__':
    main()
