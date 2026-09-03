"""Merges the adversarial audit outputs into factcheck.json.
Findings are keyed by the exact pair of source URLs the checker fetched, never
by position: pairings renumber whenever one is added or a comparison swapped."""
import json, collections, sys
src = json.load(open('pairings-src.json'))['items']
byn = {i+1: it for i, it in enumerate(src)}
rows = []
for b in (1, 2, 3, 4):
    try: batch = json.load(open(f'audit-out-{b}.json'))
    except FileNotFoundError:
        print(f'  audit-out-{b}.json missing', file=sys.stderr); continue
    for r in batch:
        it = byn.get(r['n'])
        if not it: continue
        r['checked_nyc_url'] = it['nyc_url']
        r['checked_match_url'] = it['match_url']
        r['round'] = 'audit'
        rows.append(r)
fc = json.load(open('factcheck.json'))
prior = [r for r in fc['items'] if r.get('round') != 'audit']
fc['items'] = prior + rows
pairs = {(i['nyc_url'], i['match_url']) for i in src}
live = [r for r in rows if (r['checked_nyc_url'], r['checked_match_url']) in pairs]
c = collections.Counter(r['verdict'] for r in live)
covered = len({(r['checked_nyc_url'], r['checked_match_url']) for r in live})
json.dump(fc, open('factcheck.json','w'), indent=1)
print(f'audit rows: {len(rows)}, covering {covered} of {len(src)} pairings')
print(dict(c))
for r in sorted(live, key=lambda x: x['n']):
    if r['verdict'] != 'CONFIRMED':
        print(f"  {r['n']:>3} {r['verdict']:<24} {r['finding'][:150]}")
        if r.get('conflict'): print(f"      conflict: {r['conflict'][:190]}")
