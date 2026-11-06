"""Student-need shares for New York City schools, 2024-25: students with disabilities, English language learners, economically disadvantaged.

The state suppresses small subgroup counts (shown as "-"). A suppressed count is not a zero. Where a subgroup count is
suppressed but its complement is published (English language learner / not English language learner; students with
disabilities / general education students), the model uses total enrollment minus the complement, and the school is
flagged. The filled counts go only to raw/ (not published); the published file keeps suppressed counts blank.
"""
import pathlib
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]
enr = pd.read_csv(ROOT / 'data/nyc_enrollment_long.csv', dtype={'beds': str})
total = enr[enr.spring == 2025].set_index('beds').total
out = None
for f, key, sub, comp in [('students-with-disabilities', 'swd', 'students with disabilities', 'general education students'),
                          ('english-language-learners', 'ell', 'english language learner', 'not english language learner'),
                          ('economically-disadvantaged', 'ed', 'economically disadvantaged', 'not economically disadvantaged')]:
    x = pd.ExcelFile(ROOT / f'raw/enroll_sub/2024-25-{f}.xlsx')
    df = pd.read_excel(x, [s for s in x.sheet_names if 'info' not in s.lower()][0], dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df['beds'] = df['state location identifier'].str.strip().str.zfill(12)
    df = df[df.beds.str[:2].isin(['31', '32', '33', '34', '35'])]
    df['n'] = pd.to_numeric(df['prek-12 total'], errors='coerce')
    name = df['subgroup name'].str.strip().str.lower()
    s = df[name == sub].set_index('beds').n.rename(key)
    c = df[name == comp].set_index('beds').n
    s = s.reindex(s.index.union(c.index))
    fill = s.isna() & s.index.to_series().map(c).notna() & s.index.to_series().map(total).notna()
    s[fill] = (s.index.to_series().map(total) - s.index.to_series().map(c))[fill].clip(lower=0)
    s = s.to_frame()
    s[f'{key}_filled'] = fill.astype(int)
    print(f'{key}: {int(fill.sum())} suppressed counts filled from the complement, {int(s[key].isna().sum())} still missing')
    s = s.reset_index().rename(columns={'index': 'beds'})
    out = s if out is None else out.merge(s, on='beds', how='outer')
out.to_csv(ROOT / 'raw/need_2024_25_filled.csv', index=False)
pub = out.copy()
for key in ['swd', 'ell', 'ed']:
    pub.loc[pub[f'{key}_filled'] == 1, key] = None
    pub = pub.rename(columns={f'{key}_filled': f'{key}_suppressed'})
pub.to_csv(ROOT / 'data/need_2024_25.csv', index=False)
print(out.describe())
