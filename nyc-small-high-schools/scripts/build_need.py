"""Student-need shares for New York City schools, 2024-25: students with disabilities, English language learners, economically disadvantaged."""
import pathlib
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]
out = None
for f, key, sub in [('students-with-disabilities', 'swd', 'students with disabilities'),
                    ('english-language-learners', 'ell', 'english language learner'),
                    ('economically-disadvantaged', 'ed', 'economically disadvantaged')]:
    x = pd.ExcelFile(ROOT / f'raw/enroll_sub/2024-25-{f}.xlsx')
    df = pd.read_excel(x, [s for s in x.sheet_names if 'info' not in s.lower()][0], dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    loc = df['state location identifier'].str.strip().str.zfill(12)
    df = df[loc.str[:2].isin(['31', '32', '33', '34', '35'])]
    df = df[df['subgroup name'].str.strip().str.lower() == sub]
    s = pd.DataFrame({'beds': df['state location identifier'].str.strip().str.zfill(12),
                      key: pd.to_numeric(df['prek-12 total'], errors='coerce')})
    out = s if out is None else out.merge(s, on='beds', how='outer')
out.to_csv(ROOT / 'data/need_2024_25.csv', index=False)
print(out.describe())
