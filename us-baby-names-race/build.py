"""Build the data for The baby name horserace from Social Security baby name files.

  python3 build.py national <folder of yobYYYY.txt>  names.json
  python3 build.py states   <folder of XX.TXT>       states/

National files: name,sex,count (one file per year). State files: ST,sex,year,name,count
(one file per state). Both come from https://www.ssa.gov/oact/babynames/limits.html.
"""
import sys, os, re, json

TOP = 50


def build(rows, label):
    """rows: {year: {'F': [(name, count)], 'M': [...]}} -> output dict"""
    yrs = sorted(rows)
    Y0, Y1 = yrs[0], yrs[-1]
    assert yrs == list(range(Y0, Y1 + 1)), label + ': missing years'
    data = {'F': {}, 'M': {}}
    totals = {'F': {}, 'M': {}}
    tail = {'F': {}, 'M': {}}
    for y in yrs:
        for s in 'FM':
            r = sorted(rows[y][s], key=lambda t: (-t[1], t[0]))
            totals[s][y] = sum(c for _, c in r)
            tail[s][y] = (round(100 * sum(c for _, c in r[:TOP]) / totals[s][y], 2), len(r))
            for i, (n, c) in enumerate(r[:1000]):
                data[s].setdefault(n, {})[y] = (i + 1, c)
    res = {'years': [Y0, Y1], 'top': TOP, 'sexes': {}}
    for s, key in (('M', 'boys'), ('F', 'girls')):
        recs = []
        for n, d in data[s].items():
            if not any(v[0] <= TOP for v in d.values()):
                continue
            best = min(v[0] for v in d.values())
            recs.append({
                'n': n,
                'r': [d[y][0] if y in d else 0 for y in yrs],  # 0 = outside the top 1,000
                'p': [round(d[y][1] / totals[s][y] * 1000, 2) if y in d else 0 for y in yrs],  # per 1,000
                'first': min(y for y in d if d[y][0] <= TOP),
                'best': best,
                'bestYr': min(y for y in d if d[y][0] == best),
                'yrsTop': sum(1 for y in d if d[y][0] <= TOP),
            })
        recs.sort(key=lambda r: (r['first'], r['best']))
        res['sexes'][key] = {
            'names': recs,
            'births': [totals[s][y] for y in yrs],
            'top50pct': [tail[s][y][0] for y in yrs],
            'distinct': [tail[s][y][1] for y in yrs],
        }
    return res


def summary(res, label):
    Y0, Y1 = res['years']
    for key in ('boys', 'girls'):
        recs = res['sexes'][key]['names']
        t0 = {r['n'] for r in recs if 0 < r['r'][0] <= TOP}
        t1 = {r['n'] for r in recs if 0 < r['r'][-1] <= TOP}
        always = [r['n'] for r in recs if r['yrsTop'] == Y1 - Y0 + 1]
        print(f'{label} {key}: ever top 50 {len(recs)}; top 50 in both {Y0} and {Y1}: {len(t0 & t1)}; every year: {always}')


def national(src, out):
    rows = {}
    for f in os.listdir(src):
        m = re.match(r'yob(\d{4})\.txt$', f)
        if not m:
            continue
        y = int(m.group(1)); rows[y] = {'F': [], 'M': []}
        for line in open(os.path.join(src, f)):
            n, s, c = line.strip().split(',')
            rows[y][s].append((n, int(c)))
    res = build(rows, 'US')
    json.dump(res, open(out, 'w'), separators=(',', ':'))
    summary(res, 'US')


def states(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    done = []
    for f in sorted(os.listdir(src)):
        m = re.match(r'([A-Z]{2})\.TXT$', f)
        if not m:
            continue
        st = m.group(1); rows = {}
        for line in open(os.path.join(src, f)):
            a, s, y, n, c = line.strip().split(',')
            assert a == st
            rows.setdefault(int(y), {'F': [], 'M': []})[s].append((n, int(c)))
        res = build(rows, st)
        json.dump(res, open(os.path.join(outdir, st + '.json'), 'w'), separators=(',', ':'))
        done.append(st)
    print(len(done), 'states:', ' '.join(done))


if __name__ == '__main__':
    mode, src, out = sys.argv[1:4]
    {'national': national, 'states': states}[mode](src, out)
