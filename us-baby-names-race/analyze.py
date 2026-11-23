"""Comebacks, departures, arrivals and all-time totals for the national data.

  python3 analyze.py <folder of yobYYYY.txt> analysis.json

A name's "stretches" in a list (top 50 or top 100) are runs of consecutive years
in which it ranked at or above the cutoff. Ranks are by count within sex and year,
ties broken alphabetically (same as build.py).
"""
import sys, os, re, json, collections

src, out = sys.argv[1], sys.argv[2]
yrs = sorted(int(m.group(1)) for f in os.listdir(src) if (m := re.match(r'yob(\d{4})\.txt$', f)))
Y0, Y1 = yrs[0], yrs[-1]
SURGE_FROM = 1920  # arrival speed only for names first reaching the list after this year
NOWHERE = 1000     # "from nowhere" = ranked below 1,000th or not listed

rank = {'F': collections.defaultdict(dict), 'M': collections.defaultdict(dict)}
tot = {'F': collections.Counter(), 'M': collections.Counter()}
for y in yrs:
    rows = {'F': [], 'M': []}
    for line in open(os.path.join(src, f'yob{y}.txt')):
        n, s, c = line.strip().split(',')
        rows[s].append((n, int(c))); tot[s][n] += int(c)
    for s in 'FM':
        for i, (n, c) in enumerate(sorted(rows[s], key=lambda t: (-t[1], t[0]))):
            rank[s][n][y] = i + 1


def stretches(d, K):
    out, a = [], None
    for y in yrs:
        inn = d.get(y, 10**9) <= K
        if inn and a is None: a = y
        if not inn and a is not None: out.append([a, y - 1]); a = None
    if a is not None: out.append([a, Y1])
    return out


res = {'years': [Y0, Y1], 'lists': {}, 'totals': {}}
for K in (50, 100):
    res['lists'][K] = {}
    for s, lab in (('F', 'girls'), ('M', 'boys')):
        cats = collections.Counter(); nst = collections.Counter()
        away, surge, once, repeat = [], [], [], []
        never = []
        for n, d in rank[s].items():
            r = stretches(d, K)
            if not r: continue
            k, now_in = len(r), r[-1][1] == Y1
            nst[k] += 1
            if k == 1 and r[0] == [Y0, Y1]: c = 'never_left'; never.append((-sum(d.get(y, 0) and 1 for y in yrs), min(d.values()), n))
            elif k == 1 and now_in: c = 'one_in'
            elif k == 1: c = 'one_gone'
            elif now_in: c = 'back_in'
            else: c = 'back_gone'
            cats[c] += 1
            for (a1, b1), (a2, b2) in zip(r, r[1:]):
                away.append({'n': n, 'years': a2 - b1 - 1, 'left': b1, 'back': a2})
            if k >= 3: repeat.append({'n': n, 'stretches': r})
            if k == 1 and r[0][0] == r[0][1] and r[0][0] < Y1: once.append({'n': n, 'year': r[0][0], 'rank': d[r[0][0]]})
            f = r[0][0]
            if f > SURGE_FROM:
                y = f - 1
                while y >= Y0 and d.get(y, 10**9) <= NOWHERE: y -= 1
                if y >= SURGE_FROM:
                    surge.append({'n': n, 'years': f - y, 'from': y, 'fromRank': d.get(y), 'to': f, 'toRank': d[f]})
        away.sort(key=lambda a: (-a['years'], a['n']))
        surge.sort(key=lambda a: (a['years'], a['to'], a['n']))
        once.sort(key=lambda a: a['year'])
        repeat.sort(key=lambda a: (-len(a['stretches']), a['n']))
        res['lists'][K][lab] = {
            'ever': sum(cats.values()),
            'firstAfterStart': sum(1 for n, d in rank[s].items() if (r := stretches(d, K)) and r[0][0] > Y0),
            'cats': dict(cats),
            'stretches': {str(k): v for k, v in sorted(nst.items())},
            'cameBack': sum(v for k, v in nst.items() if k >= 2),
            'cameBack2': sum(v for k, v in nst.items() if k >= 3),
            'neverLeft': sorted(n for *_, n in never),
            'away': away[:12], 'surge': surge[:12], 'once': once, 'repeat': repeat[:8],
        }

both = tot['F'] + tot['M']
res['grand'] = sum(both.values())
res['grandBySex'] = {'girls': sum(tot['F'].values()), 'boys': sum(tot['M'].values())}
res['totals']['both'] = [{'n': n, 't': c, 'girls': tot['F'][n], 'boys': tot['M'][n]} for n, c in both.most_common(10)]
res['totals']['girls'] = [{'n': n, 't': c} for n, c in tot['F'].most_common(10)]
res['totals']['boys'] = [{'n': n, 't': c} for n, c in tot['M'].most_common(10)]
json.dump(res, open(out, 'w'), separators=(',', ':'))

for K in (50, 100):
    for lab in ('girls', 'boys'):
        x = res['lists'][K][lab]
        print(K, lab, 'ever', x['ever'], 'after start', x['firstAfterStart'], x['cats'], 'back', x['cameBack'], 'back2+', x['cameBack2'])
        print('   away', [(a['n'], a['years'], a['left'], a['back']) for a in x['away'][:6]])
        print('   surge', [(a['n'], a['years'], a['from'], a['fromRank'], a['to'], a['toRank']) for a in x['surge'][:8]])
        print('   once', len(x['once']), [(a['n'], a['year']) for a in x['once']][:20])
        print('   repeat', [(a['n'], len(a['stretches']), a['stretches'][0][0], a['stretches'][-1][1]) for a in x['repeat'][:5]])
print('grand', res['grand'], res['grandBySex'])
