"""Stack NYSED school enrollment files (1994-95 to 2025-26) for New York City into one long table.

Input: raw/enroll/T{spring year}.xlsx (NYSED IRS public school enrollment, All Students).
Output: data/nyc_enrollment_long.csv, one row per school per year.
"""
import re, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]

def norm(c):
    c = str(c).upper().strip()
    c = c.replace('PREK-12', 'PK12').replace('KINDERGARTEN', 'KG').replace('IDENTIFIER', 'ID')
    return re.sub(r'\s+', ' ', c)

frames = []
for f in sorted((ROOT / 'raw/enroll').glob('T*.xlsx')):
    spring = int(f.stem[1:])
    x = pd.ExcelFile(f)
    sheet = [s for s in x.sheet_names if 'info' not in s.lower()][0]
    df = pd.read_excel(x, sheet, dtype=str)
    df.columns = [norm(c) for c in df.columns]
    df = df[df['SUBGROUP NAME'].str.strip().str.lower() == 'all students']
    loc = df['STATE LOCATION ID'].str.strip().str.zfill(12)
    df = df[loc.str[:2].isin(['30', '31', '32', '33', '34', '35'])].copy()
    out = pd.DataFrame({
        'spring': spring,
        'beds': df['STATE LOCATION ID'].str.strip().str.zfill(12),
        'name': df['LOCATION NAME'].str.strip(),
        'school_type': df['SCHOOL TYPE'].str.strip().str.upper(),
    })
    num = lambda c: pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    out['total'] = num('PK12 TOTAL')
    for g in [6, 7, 8, 9, 10, 11, 12]:
        out[f'g{g}'] = num(f'GRADE {g}')
    out['ung_sec'] = num([c for c in df.columns if c.startswith('UNGRADED (SEC')][0])
    frames.append(out)
    print(spring, len(out))

long = pd.concat(frames, ignore_index=True)
boro = {'31': 'M', '32': 'X', '33': 'K', '34': 'Q', '35': 'R'}
long['dbn'] = long['beds'].map(lambda b: f"{b[2:4]}{boro.get(b[:2], '?')}{b[-3:]}")
long.to_csv(ROOT / 'data/nyc_enrollment_long.csv', index=False)
print(long.groupby('spring').size().to_string())
print(long['school_type'].value_counts())
