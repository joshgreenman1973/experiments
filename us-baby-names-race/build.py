import sys, json, os
src, out = sys.argv[1], sys.argv[2]
import re
yrs = sorted(int(m.group(1)) for f in os.listdir(src) if (m := re.match(r'yob(\d{4})\.txt$', f)))
Y0, Y1, TOP = yrs[0], yrs[-1], 50
assert yrs == list(range(Y0, Y1 + 1)), 'missing years'
data = {'F': {}, 'M': {}}   # sex -> name -> {year: (rank, count)}
totals = {'F': {}, 'M': {}}
tail = {'F': {}, 'M': {}}
for y in range(Y0, Y1+1):
    rows = {'F': [], 'M': []}
    with open(os.path.join(src, f'yob{y}.txt')) as f:
        for line in f:
            n, s, c = line.strip().split(',')
            rows[s].append((n, int(c)))
    for s in 'FM':
        r = sorted(rows[s], key=lambda t: (-t[1], t[0]))
        totals[s][y] = sum(c for _, c in r)
        tail[s][y] = (round(100*sum(c for _, c in r[:TOP])/totals[s][y], 2), len(r))
        for i, (n, c) in enumerate(r[:1000]):
            data[s].setdefault(n, {})[y] = (i+1, c)
res = {'years': [Y0, Y1], 'top': TOP, 'sexes': {}}
for s, key in (('M', 'boys'), ('F', 'girls')):
    names = [n for n, d in data[s].items() if any(v[0] <= TOP for v in d.values())]
    recs = []
    for n in names:
        d = data[s][n]
        ranks = [d[y][0] if y in d else 0 for y in range(Y0, Y1+1)]   # 0 = outside top 1000
        per = [round(d[y][1] / totals[s][y] * 1000, 2) if y in d else 0 for y in range(Y0, Y1+1)]
        first = min(y for y in d if d[y][0] <= TOP)
        best = min(d[y][0] for y in d)
        bestyr = min(y for y in d if d[y][0] == best)
        recs.append({'n': n, 'r': ranks, 'p': per, 'first': first, 'best': best, 'bestYr': bestyr,
                     'yrsTop': sum(1 for y in d if d[y][0] <= TOP)})
    recs.sort(key=lambda r: (r['first'], r['best']))
    res['sexes'][key] = {'names': recs, 'births': [totals[s][y] for y in range(Y0, Y1+1)], 'top50pct': [tail[s][y][0] for y in range(Y0, Y1+1)], 'distinct': [tail[s][y][1] for y in range(Y0, Y1+1)]}
json.dump(res, open(out, 'w'), separators=(',', ':'))
for key in ('boys', 'girls'):
    recs = res['sexes'][key]['names']
    t0 = {r['n'] for r in recs if 0 < r['r'][0] <= TOP}
    t1 = {r['n'] for r in recs if 0 < r['r'][-1] <= TOP}
    always = [r['n'] for r in recs if r['yrsTop'] == Y1-Y0+1]
    print(key, 'ever top50:', len(recs), '| 1880 top50 still top50 in 2024:', len(t0 & t1), sorted(t0 & t1), '| every year:', len(always), always)
    one = [r['n'] for r in sorted(recs, key=lambda r: r['best']) if r['best'] == 1]
    print('  ever #1:', one)
