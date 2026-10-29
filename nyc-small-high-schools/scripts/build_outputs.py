"""Write the CSVs the page reads, from the data/ files built by the other scripts."""
import json, pathlib
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'; OUT.mkdir(exist_ok=True)

c = pd.read_csv(ROOT / 'data/hs_counts_by_size.csv')
t = pd.read_csv(ROOT / 'data/hs_counts_incl_transfer.csv')
c = c.merge(t.rename(columns={'schools': 'schools_incl_transfer', 'under_250': 'under_250_incl_transfer'})[
    ['spring', 'schools_incl_transfer', 'under_250_incl_transfer', 'transfer_schools']], on='spring')
c['under_250_new'] = c.under_250 - c.under_250_mature
c[['school_year', 'spring', 'schools', 'students', 'median_size', 'under_250', 'under_300', 'under_350',
   'under_250_mature', 'under_250_new', 'under_300_mature', 'under_350_mature',
   'under_250_students', 'under_300_students', 'under_350_students',
   'schools_incl_transfer', 'under_250_incl_transfer', 'transfer_schools']].to_csv(OUT / 'counts.csv', index=False)

s = pd.read_csv(ROOT / 'data/hs_spending_2024_25.csv', dtype={'beds': str})
f = pd.read_csv(ROOT / 'data/hs_functions_2024_25.csv', dtype={'beds': str})
s = s.merge(f[['beds'] + [f'f{k}' for k in range(1, 13)] + ['total_pp']], on='beds', how='left')
s['instruction_pp'] = s.f1 + s.f3
s['pupil_support_pp'] = s.f2
s['school_admin_pp'] = s.f5
s['shared_pp'] = s[['f4', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12']].sum(1)
sch = s[['dbn', 'name', 'enr', 'pp', 'instruction_pp', 'pupil_support_pp', 'school_admin_pp', 'shared_pp',
         'p_swd', 'p_ell', 'p_ed', 'size_bin', 'pred_bin_ref']].copy()
sch['need_adjusted_premium_pp'] = (s.pred_bin_own - s.pred_bin_ref).round(0)
sch = sch.rename(columns={'enr': 'enrollment', 'pp': 'spending_per_pupil', 'pred_bin_ref': 'expected_at_500_999'})
for k in ['p_swd', 'p_ell', 'p_ed']: sch[k] = sch[k].round(3)
for k in ['instruction_pp', 'pupil_support_pp', 'school_admin_pp', 'shared_pp', 'expected_at_500_999']: sch[k] = sch[k].round(0)
sch.sort_values('enrollment').to_csv(OUT / 'schools_2024_25.csv', index=False)

m = json.load(open(ROOT / 'data/cost_model_2024_25.json'))
bins = pd.DataFrame(m['bins'])
fx = s.groupby('size_bin', observed=True).apply(lambda g: pd.Series({
    'instruction_pp': (g.instruction_pp * g.enr).sum() / g.enr.sum(),
    'pupil_support_pp': (g.pupil_support_pp * g.enr).sum() / g.enr.sum(),
    'school_admin_pp': (g.school_admin_pp * g.enr).sum() / g.enr.sum(),
    'shared_pp': (g.shared_pp * g.enr).sum() / g.enr.sum(),
    'reports_parsed': int(g.instruction_pp.notna().sum())})).reset_index().rename(columns={'size_bin': 'bin'})
bins = bins.merge(fx, on='bin')
bins['order'] = range(len(bins))
bins.round(3).to_csv(OUT / 'size_bins_2024_25.csv', index=False)

p = pd.DataFrame([{'cutoff': f'Under {k}', 'schools': v['schools'], 'students': v['students'],
                   'premium_dollars': round(v['binned_premium_dollars']), 'premium_per_pupil': round(v['binned_premium_per_pupil']),
                   'premium_dollars_log_model': round(v['modeled_premium_dollars'])}
                  for k, v in ((int(k.split('_')[-1]), v) for k, v in m.items() if k.startswith('premium_under_'))])
p.to_csv(OUT / 'premium_2024_25.csv', index=False)
print(c.tail(3).T); print(bins.T); print(p)
