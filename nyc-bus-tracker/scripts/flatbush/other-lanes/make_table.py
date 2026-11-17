#!/usr/bin/env python3
"""results.json -> table.md (the results table pasted into README.md)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'results.json')))


def f(x, d=3, sign=True):
    if x is None:
        return '—'
    return f'{x:+.{d}f}' if sign else f'{x:.{d}f}'


lines = ['| # | Project | Opened | Before → after mph | Change | Peak change | Control change | Diff-in-diff | Month pairs (after) | Corridor covered |',
         '|---|---|---|---|---|---|---|---|---|---|']
for r in R:
    op = 'June 2026' if r['id'] == 14 else r['opened']
    if r['before_mph'] is None:
        lines.append(f"| {r['id']} | {r['name']} | {op} | not measurable | — | — | — | — | 0 | 0% |")
        continue
    dm = r.get('did_month_pairs') or {}
    lines.append(f"| {r['id']} | {r['name']} | {op} | {r['before_mph']:.3f} → {r['after_mph']:.3f} | {f(r['change_mph'])} mph ({f(r['change_pct'], 2)}%) "
                 f"| {f(r['peak_change_pct'], 2)}% | {f(r['control_change_mph'])} mph ({f(r['control_change_pct'], 2)}%) "
                 f"| {f(r['diff_in_diff_mph'])} mph ({f(r['diff_in_diff_pct_pts'], 2)} pts); {dm.get('positive')}/{dm.get('n')} pairs positive "
                 f"| {r['nAfterMonths']} ({r['afterMonths'][0]} to {r['afterMonths'][-1]}) | {round(100 * r['corridorCoveredShare'])}% |")
open(os.path.join(HERE, 'table.md'), 'w').write('\n'.join(lines) + '\n')
