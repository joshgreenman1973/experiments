"""How did complaints at the busiest addresses end, compared with everywhere else?

Reads build/cache/outcomes (from fetch_outcomes.py) and data/points.json, sorts
every resolution note into an outcome group by written rules, and compares the
top 0.01% and top 0.1% of addresses with all other complaints, both raw and
adjusted for complaint type (each type weighted as it appears at the top
addresses, using the rate for that type everywhere else).

Also measures, for the 22 addresses pulled record by record, how many
complaints were closed in batches (10 or more closed in the same second).

Writes data/outcomes.json and data/outcome-rules.csv (every closing note, its
group and its count, so the sorting can be checked), and prints a summary.

Usage: python3 scripts/analyze_outcomes.py
"""
import glob, json, os, re
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
OUT = os.path.join(ROOT, 'build', 'cache', 'outcomes')

# Rules run in order; the first match wins. "No violations were issued" has to
# hit "nothing found" before "violations were issued" can hit "action".
RULES = [
    ('duplicate', r'duplicate|earlier complaint|already (been )?(reported|filed|submitted)|previously filed|'
                  r'similar complaint|same (location|condition|issue)|under another service request'),
    ('no_access', r'unable to gain|not able to gain|could not gain|couldn.t gain|unable to complete|insufficient|'
                  r'can ?not be processed|could not be processed|unable to access|could not access|'
                  r'not able to (inspect|access)|no one (was )?(home|available)|did not provide'),
    ('nothing_found', r'no evidence|no violations? (were|was) (issued|found|observed)|did not violate|were gone|'
                      r'not necessary|no further action|could not find|couldn.t find|found no|no condition|'
                      r'not found|was found to be|temporary condition|no work is necessary|meets (its )?standards|'
                      r'valid permit|did not observe|didn.t observe|no action (is|was) (needed|necessary|required)|'
                      r'not observed|unfounded|no encampment|no longer (there|present)|gone on arrival|'
                      r'was not able to (find|locate)|could not locate|unable to (find|locate)|no violation|'
                      r'no criminal violation|did not find|not warranted'),
    ('corrected', r'(was|were|been|has been|had been) (corrected|restored|resolved)|condition was corrected|'
                  r'claimed the vehicle|vehicle was moved|has been moved|indicated that the condition'),
    ('unclear', r'keep the location under observation'),  # a promise to watch, not an outcome
    ('action', r'took action|summons|arrest|violations? (were|was|has been|have been) (issued|previously issued)|'
               r'notice of violation|found violations|repaired|corrected the (condition|problem)|'
               r'completed the request|completed the requested work|collected|cleaned|removed|towed|'
               r'hearing was scheduled|issued an? |ticket|fined|abated|fixed the|made repairs|work was completed|'
               r'the problem has been addressed|installed|replaced|restored service|took enforcement|'
               r'shut the|performed the work|addressed the issue|issue you reported was addressed|offered services'),
    ('referred', r'jurisdiction|referred|forwarded|transferred|has requested the'),
]
GROUPS = ['action', 'corrected', 'nothing_found', 'no_access', 'duplicate', 'referred', 'unclear', 'open']
LABELS = {'action': 'Agency took action or found a violation', 'corrected': 'Fixed by the time the agency checked',
          'nothing_found': 'Agency found nothing to act on', 'no_access': 'Agency could not get in or get details',
          'duplicate': 'Closed as a duplicate', 'referred': 'Referred elsewhere or not the agency\'s job',
          'unclear': 'Closed with no clear outcome', 'open': 'Still open'}
RX = [(g, re.compile(p, re.I)) for g, p in RULES]


def group(status, note):
    if status.strip().lower() != 'closed':
        return 'open'
    for g, rx in RX:
        if rx.search(note):
            return g
    return 'unclear'


def norm(s):
    s = s.str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
    for p, r in [(r' BLVD\b', ' BOULEVARD'), (r' AVE\b', ' AVENUE'), (r' ST$', ' STREET'),
                 (r' RD$', ' ROAD'), (r' PL$', ' PLACE'), (r' PKWY\b', ' PARKWAY')]:
        s = s.str.replace(p, r, regex=True)
    return s


def load(pattern):
    d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in sorted(glob.glob(pattern))],
                  ignore_index=True)
    d['n'] = d.n.astype(int)
    d['tkey'] = d.complaint_type.str.strip().str.upper()
    return d


def rates(frame):
    s = frame.groupby('g').n.sum().reindex(GROUPS, fill_value=0)
    return s / s.sum()


def adjusted(top, rest):
    # Expected outcome shares if each complaint at the top addresses had the
    # outcome mix of the same complaint type everywhere else.
    w = top.groupby('tkey').n.sum()
    r = rest.groupby(['tkey', 'g']).n.sum().unstack(fill_value=0).reindex(columns=GROUPS, fill_value=0)
    r = r.div(r.sum(axis=1), axis=0)
    w = w[w.index.isin(r.index)]
    return (r.loc[w.index].mul(w, axis=0).sum() / w.sum()).reindex(GROUPS)


def batches():
    # How complaints were closed at the 22 addresses pulled record by record.
    res = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'build', 'cache', 'records', '*.csv'))):
        d = pd.read_csv(f, dtype=str, keep_default_na=False)
        d = d[d.closed_date != '']
        c = pd.to_datetime(d.closed_date)
        t = pd.to_datetime(d.created_date)
        same = c.value_counts()
        name = os.path.basename(f)[:-4].rsplit('_', 1)[0].replace('_', ' ')
        res[name] = {'n_closed': int(len(c)),
                     'share_in_batches_10plus': round(float(same[same >= 10].sum() / len(c)), 4),
                     'largest_batch': int(same.max()),
                     'median_minutes_to_close': round(float(((c - t).dt.total_seconds() / 60).median()), 1),
                     'types': d.complaint_type.value_counts(normalize=True).round(3).head(2).to_dict()}
    return res


def main():
    city = load(os.path.join(OUT, 'city', '*.csv'))
    top = load(os.path.join(OUT, 'top', '*.csv'))
    P = json.load(open(os.path.join(ROOT, 'data', 'points.json')))
    rank = {(a, z): i + 1 for i, (a, z) in enumerate(zip(P['addr'][:1301], P['zip'][:1301]))}
    top['addr'] = norm(top.incident_address)
    top['zip'] = top.incident_zip.str.strip().str[:5]
    top['rank'] = [rank.get(k) for k in zip(top.addr, top.zip)]
    top = top[top['rank'].notna()].copy()
    top['rank'] = top['rank'].astype(int)

    notes = city.groupby(['status', 'resolution_description']).n.sum().reset_index()
    notes['g'] = [group(s, r) for s, r in zip(notes.status, notes.resolution_description)]
    notes['outcome'] = notes.g.map(LABELS)
    (notes.sort_values('n', ascending=False)[['outcome', 'status', 'resolution_description', 'n']]
     .rename(columns={'resolution_description': 'closing_note', 'n': 'complaints'})
     .to_csv(os.path.join(ROOT, 'data', 'outcome-rules.csv'), index=False))
    city['g'] = [group(s, r) for s, r in zip(city.status, city.resolution_description)]
    top['g'] = [group(s, r) for s, r in zip(top.status, top.resolution_description)]

    # Everything outside the top 0.1%, built by subtracting the top rows from the city totals.
    key = ['tkey', 'g']
    t_all = top.groupby(key).n.sum()
    rest = city.groupby(key).n.sum().sub(t_all, fill_value=0).clip(lower=0).reset_index()
    t001 = top[top['rank'] <= 130]
    t01 = top
    out = {'total_city': int(city.n.sum()), 'top_0.01_n': int(t001.n.sum()), 'top_0.1_n': int(t01.n.sum()),
           'points_top_0.01_n': int(sum(P['n'][:130])), 'points_top_0.1_n': int(sum(P['n'][:1301])),
           'labels': LABELS, 'groups': GROUPS}
    out['raw'] = {name: rates(f).round(4).to_dict() for name, f in
                  (('top_0.01', t001), ('top_0.1', t01), ('everyone_else', rest), ('city', city))}
    out['adjusted_expected'] = {'top_0.01': adjusted(t001, rest).round(4).to_dict(),
                                'top_0.1': adjusted(t01, rest).round(4).to_dict()}
    # Per complaint type, for the types that matter most at the top.
    per = []
    for t in t01.groupby('tkey').n.sum().sort_values(ascending=False).head(12).index:
        a, b, c = t001[t001.tkey == t], t01[t01.tkey == t], rest[rest.tkey == t]
        per.append({'type': t, 'n_top_0.01': int(a.n.sum()), 'n_top_0.1': int(b.n.sum()), 'n_else': int(c.n.sum()),
                    'top_0.01': rates(a).round(4).to_dict() if len(a) else None,
                    'top_0.1': rates(b).round(4).to_dict(), 'everyone_else': rates(c).round(4).to_dict()})
    out['by_type'] = per
    # A few addresses from the page.
    picks = {}
    for a, z in [('655 EAST 230 STREET', '10466'), ('672 EAST 231 STREET', '10466'), ('78-15 PARSONS BOULEVARD', '11366'),
                 ('82-68 164 STREET', '11432'), ('5-47 50 AVENUE', '11101'), ('191 UNION STREET', '11231'),
                 ('2176 TIEBOUT AVENUE', '10457'), ('18-11 129 STREET', '11356')]:
        f = top[(top.addr == a) & (top.zip == z)]
        picks[a] = {'n': int(f.n.sum()), 'rates': rates(f).round(4).to_dict()}
    out['addresses'] = picks
    # Per-address action rate for the top 130, against what its own type mix predicts.
    rest_r = rest.groupby(['tkey', 'g']).n.sum().unstack(fill_value=0).reindex(columns=GROUPS, fill_value=0)
    rest_r = rest_r.div(rest_r.sum(axis=1), axis=0)
    rows = []
    for r_, f in t001.groupby('rank'):
        obs = rates(f)['action']
        w = f.groupby('tkey').n.sum()
        w = w[w.index.isin(rest_r.index)]
        exp = float((rest_r.loc[w.index, 'action'] * w).sum() / w.sum())
        rows.append((r_, int(f.n.sum()), obs, exp))
    pa = pd.DataFrame(rows, columns=['rank', 'n', 'obs', 'exp'])
    out['top130_below_expected'] = int((pa.obs < pa.exp).sum())
    out['top130_below_half_expected'] = int((pa.obs < pa.exp / 2).sum())
    # Every one of the top 1,301 addresses: observed and expected action share,
    # plus the share closed as nothing found and as duplicates, by rank.
    per_addr = {'act': [], 'exp': [], 'nothing': [], 'dup': [], 'n': []}
    for r_, f in t01.groupby('rank'):
        rr = rates(f)
        w = f.groupby('tkey').n.sum()
        w = w[w.index.isin(rest_r.index)]
        per_addr['act'].append(round(float(rr['action']), 4))
        per_addr['exp'].append(round(float((rest_r.loc[w.index, 'action'] * w).sum() / w.sum()), 4))
        per_addr['nothing'].append(round(float(rr['nothing_found']), 4))
        per_addr['dup'].append(round(float(rr['duplicate']), 4))
        per_addr['n'].append(int(f.n.sum()))
    out['per_address'] = per_addr
    # Counts of addresses below their expected action share, from unrounded values.
    acts, exps = [], []
    for r_, f in t01.groupby('rank'):
        w = f.groupby('tkey').n.sum()
        w = w[w.index.isin(rest_r.index)]
        acts.append(float(rates(f)['action']))
        exps.append(float((rest_r.loc[w.index, 'action'] * w).sum() / w.sum()))
    out['below_expected'] = {k: {'below': sum(a < e for a, e in zip(acts[:n], exps[:n])),
                                 'below_half': sum(a < e / 2 for a, e in zip(acts[:n], exps[:n]))}
                             for k, n in (('top_0.01', 130), ('top_0.1', 1301))}
    out['closed_share'] = {k: round(1 - out['raw'][k]['open'], 4) for k in ('top_0.01', 'top_0.1', 'everyone_else')}
    out['unclear_city'] = round(float(out['raw']['city']['unclear']), 4)
    out['notes_per_quarter'] = int(city.groupby(['resolution_description']).ngroups / 1)
    out['batches'] = batches()
    json.dump(out, open(os.path.join(ROOT, 'data', 'outcomes.json'), 'w'), indent=1)

    pd.set_option('display.width', 250)
    print('city total', out['total_city'], '| top 0.01%', out['top_0.01_n'], 'vs points', out['points_top_0.01_n'],
          '| top 0.1%', out['top_0.1_n'], 'vs points', out['points_top_0.1_n'])
    print('unclear share of city', round(out['raw']['city']['unclear'], 4))
    tab = pd.DataFrame({k: pd.Series(v) for k, v in out['raw'].items()})
    tab['expected_0.01'] = pd.Series(out['adjusted_expected']['top_0.01'])
    tab['expected_0.1'] = pd.Series(out['adjusted_expected']['top_0.1'])
    print((tab * 100).round(1).to_string())
    for r in per:
        print(r['type'], r['n_top_0.01'], r['n_top_0.1'], r['n_else'],
              '| action 0.01/0.1/else', *[round((r[k] or {}).get('action', 0) * 100, 1) for k in ('top_0.01', 'top_0.1', 'everyone_else')],
              '| nothing', *[round((r[k] or {}).get('nothing_found', 0) * 100, 1) for k in ('top_0.01', 'top_0.1', 'everyone_else')],
              '| dup', *[round((r[k] or {}).get('duplicate', 0) * 100, 1) for k in ('top_0.01', 'top_0.1', 'everyone_else')])
    for a, v in picks.items():
        print(a, v['n'], {k: round(x * 100, 1) for k, x in v['rates'].items() if x > 0.005})
    print('top 130 addresses below their expected action rate:', out['top130_below_expected'],
          '; below half of it:', out['top130_below_half_expected'])


if __name__ == '__main__':
    main()
