"""Per-pupil spending vs. school size for New York City high schools, 2024-25 (and 2023-24 as a check).

Spending: NYSED report card database SRC2025, table "Expenditures per Pupil" (federal + state/local, per pupil).
Need: NYSED 2024-25 enrollment by subgroup. Model: log(spending per pupil) on log(enrollment) and need shares.
"""
import json, pathlib
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

ROOT = pathlib.Path(__file__).resolve().parents[1]
u = pd.read_csv(ROOT / 'data/hs_universe.csv', dtype={'beds': str})
e = pd.read_csv(ROOT / 'raw/src/Expenditures_per_Pupil_2025.csv', dtype=str)
e['beds'] = e.ENTITY_CD.str.zfill(12)
for c in ['PUPIL_COUNT_TOT', 'PER_FED_STATE_LOCAL_EXP', 'FED_STATE_LOCAL_EXP', 'PER_FEDERAL_EXP']:
    e[c] = pd.to_numeric(e[c], errors='coerce')
need = pd.read_csv(ROOT / 'raw/need_2024_25_filled.csv', dtype={'beds': str})  # suppressed counts filled; not published

m = u[u.spring == 2025].merge(e[e.YEAR == '2025'], on='beds').merge(need, on='beds', how='left')
m['enr'] = m.PUPIL_COUNT_TOT
# Suppressed subgroup counts are filled in build_need.py from the complement; none should remain missing.
assert m[['swd', 'ell', 'ed']].notna().all().all(), m.loc[m[['swd', 'ell', 'ed']].isna().any(axis=1), 'dbn'].tolist()
print('suppressed counts filled from complement:', {k: int(m[f'{k}_filled'].sum()) for k in ['swd', 'ell', 'ed']},
      'students:', {k: int(m.loc[m[f'{k}_filled'] == 1, k].sum()) for k in ['swd', 'ell', 'ed']})
for k in ['swd', 'ell', 'ed']:
    m[f'p_{k}'] = m[k] / m.enr
m['has_ms'] = (m[['g6', 'g7', 'g8']].sum(1) > 0).astype(int)
m['pp'] = m.PER_FED_STATE_LOCAL_EXP
m['lpp'] = np.log(m.pp)
m['lenr'] = np.log(m.enr)

fit = smf.ols('lpp ~ lenr + p_swd + p_ell + p_ed + has_ms', data=m).fit(cov_type='HC1')
print(fit.summary().tables[1])
b = fit.params['lenr']
print(f'elasticity {b:.3f}: halving size raises per-pupil spending by {100*(2**-b-1):.1f}%')

# Binned version so the shape is not forced by the log form
bins = [0, 250, 300, 350, 500, 1000, 10000]
labels = ['Under 250', '250-299', '300-349', '350-499', '500-999', '1,000+']
m['size_bin'] = pd.cut(m.enr, bins, right=False, labels=labels)
fb = smf.ols('lpp ~ C(size_bin, Treatment(reference="500-999")) + p_swd + p_ell + p_ed + has_ms', data=m).fit(cov_type='HC1')
adj, ci = {}, {}
fb_ci = fb.conf_int(0.05)
for lab in labels:
    key = f'C(size_bin, Treatment(reference="500-999"))[T.{lab}]'
    adj[lab] = 0.0 if lab == '500-999' else float(fb.params[key])
    ci[lab] = (0.0, 0.0) if lab == '500-999' else tuple(float(v) for v in fb_ci.loc[key])
# Dollar figures exponentiate predicted log spending (a typical, geometric-mean prediction). Duan smearing factor for reference:
smear = float(np.mean(np.exp(fb.resid)))
print(f'smearing factor {smear:.5f}')

# Need-adjusted premium: predicted spending at actual size minus predicted at 500 students, same students
REF = 500
m['pred_ref'] = np.exp(fit.predict(m.assign(lenr=np.log(REF))))
m['pred_own'] = np.exp(fit.predict(m))
out = {'n_schools': int(len(m)), 'elasticity': b, 'elasticity_se': float(fit.bse['lenr']), 'r2': fit.rsquared,
       'coef': {k: float(v) for k, v in fit.params.items()}, 'bins': []}
for lab in labels:
    g = m[m.size_bin == lab]
    out['bins'].append({'bin': lab, 'schools': int(len(g)), 'students': int(g.enr.sum()),
        'median_pp': float(g.pp.median()), 'mean_pp_weighted': float(g.FED_STATE_LOCAL_EXP.sum() / g.enr.sum()),
        'need_adjusted_vs_500_999_pct': 100 * (np.exp(adj[lab]) - 1),
        'ci95_low_pct': 100 * (np.exp(ci[lab][0]) - 1), 'ci95_high_pct': 100 * (np.exp(ci[lab][1]) - 1),
        'swd': float(g.swd.sum() / g.enr.sum()), 'ell': float(g.ell.sum() / g.enr.sum()), 'ed': float(g.ed.sum() / g.enr.sum())})
for cut in [250, 300, 350]:
    g = m[m.enr < cut]
    prem = ((g.pred_own - g.pred_ref) * g.enr).sum()
    actual_gap = ((g.pp - g.pred_ref) * g.enr).sum()
    out[f'premium_under_{cut}'] = {'schools': int(len(g)), 'students': int(g.enr.sum()),
        'modeled_premium_dollars': float(prem), 'actual_minus_ref_dollars': float(actual_gap),
        'modeled_premium_per_pupil': float(prem / g.enr.sum())}
    print(cut, len(g), int(g.enr.sum()), f'${prem/1e6:.0f}M modeled, ${actual_gap/1e6:.0f}M actual vs ref')
pd.set_option('display.width', 200)
print(pd.DataFrame(out['bins']).round(3).to_string(index=False))
json.dump(out, open(ROOT / 'data/cost_model_2024_25.json', 'w'), indent=1)

# 2023-24 check with the same model
m4 = u[u.spring == 2024].merge(e[e.YEAR == '2024'], on='beds')
m4 = m4.merge(need, on='beds', how='left')  # 2024-25 need counts as a proxy: not a fully independent check
print('2023-24 check: schools without 2024-25 need counts', int(m4[['swd', 'ell', 'ed']].isna().any(axis=1).sum()))
m4 = m4.dropna(subset=['swd', 'ell', 'ed'])
for k in ['swd', 'ell', 'ed']:
    m4[f'p_{k}'] = (m4[k] / m4.PUPIL_COUNT_TOT).clip(upper=1)
m4['has_ms'] = (m4[['g6', 'g7', 'g8']].sum(1) > 0).astype(int)
m4['lpp'] = np.log(m4.PER_FED_STATE_LOCAL_EXP); m4['lenr'] = np.log(m4.PUPIL_COUNT_TOT)
f4 = smf.ols('lpp ~ lenr + p_swd + p_ell + p_ed + has_ms', data=m4).fit(cov_type='HC1')
print('2023-24 elasticity', round(f4.params['lenr'], 3), 'se', round(f4.bse['lenr'], 3))

# Binned premium: actual size bin vs. the 500-999 bin, same students (needs no log-linear shape)
m['pred_bin_ref'] = np.exp(fb.predict(m.assign(size_bin=pd.Categorical(['500-999'] * len(m), categories=labels))))
m['pred_bin_own'] = np.exp(fb.predict(m))
for cut in [250, 300, 350]:
    g = m[m.enr < cut]
    prem = ((g.pred_bin_own - g.pred_bin_ref) * g.enr).sum()
    out[f'premium_under_{cut}']['binned_premium_dollars'] = float(prem)
    out[f'premium_under_{cut}']['binned_premium_per_pupil'] = float(prem / g.enr.sum())
    print('binned', cut, f'${prem/1e6:.0f}M, ${prem/g.enr.sum():,.0f} per pupil')
out['bin_model_r2'] = fb.rsquared
out['bin_model_smearing_factor'] = smear
json.dump(out, open(ROOT / 'data/cost_model_2024_25.json', 'w'), indent=1)
# Keep the state's suppression in the published school-level file: blank any count or share filled from the complement
pub = m.copy()
for k in ['swd', 'ell', 'ed']:
    pub.loc[pub[f'{k}_filled'] == 1, [k, f'p_{k}']] = np.nan
    pub = pub.rename(columns={f'{k}_filled': f'{k}_suppressed'})
pub.to_csv(ROOT / 'data/hs_spending_2024_25.csv', index=False)
