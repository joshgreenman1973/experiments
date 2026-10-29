"""Count New York City public high schools by size, 1994-95 to 2025-26.

Universe: NYSED public (non-charter) schools in New York City enrolling any students in grades 9-12,
excluding District 75 and District 79 (codes 3075/3079), the pre-2004 alternative high school
superintendency (NYSED district 77) and its successors, and transfer high schools on DOE lists.
Size = total enrollment, all grades (so a 6-12 school counts its middle schoolers).
A school is "still phasing in" if it has no 12th graders and first appears in the files within the past four years.
"""
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
d = pd.read_csv(ROOT / 'data/nyc_enrollment_long.csv', dtype={'beds': str})
d['hs'] = d[['g9', 'g10', 'g11', 'g12']].sum(1)
# drop elementary and middle schools carrying a stray ninth grader: grades 9-12 must be at least a quarter of enrollment
d = d[(d.school_type == 'PUBLIC') & (d.beds.str[:2] != '30') & (d.hs > 0) & (d.hs >= 0.25 * d.total)].copy()
d['dist'] = d.beds.str[2:4].astype(int)
d['boro_num'] = d.dbn.str[2] + d.dbn.str[-3:]

transfer = set(json.load(open(ROOT / 'data/transfer_dbns.json')))
alt_boro_num = set(d.loc[d.dist == 77, 'boro_num'])
d['transfer'] = d.dbn.isin(transfer) | (d.boro_num.isin(alt_boro_num) & (d.spring <= 2010))
# Comparison series: transfer schools left in after the 2003-04 recode (closest match to Chalkbeat's chart)
alt = d[d.dist != 77].groupby('spring').agg(schools=('dbn', 'size'), under_250=('total', lambda x: int((x < 250).sum())),
                                            transfer_schools=('transfer', 'sum'))
alt.to_csv(ROOT / 'data/hs_counts_incl_transfer.csv')
d = d[(d.dist != 77) & ~d.transfer]

# Track schools across the 2003-04 recode (district 78/77 -> geographic districts) by borough + school number
first = d.groupby('boro_num').spring.min()
d['first_year'] = d.boro_num.map(first)
d['phasing_in'] = (d.g12 == 0) & (d.spring - d.first_year < 4) & (d.first_year > 1995)

def label(s): return f"{s-1}-{str(s)[2:]}"
rows = []
for s, g in d.groupby('spring'):
    r = {'spring': int(s), 'school_year': label(s), 'schools': len(g), 'students': int(g.total.sum()),
         'median_size': int(g.total.median())}
    for cut in [250, 300, 350]:
        m = g.total < cut
        r[f'under_{cut}'] = int(m.sum())
        r[f'under_{cut}_mature'] = int((m & ~g.phasing_in).sum())
        r[f'under_{cut}_students'] = int(g.loc[m, 'total'].sum())
    r['phasing_in'] = int(g.phasing_in.sum())
    rows.append(r)
counts = pd.DataFrame(rows)
counts.to_csv(ROOT / 'data/hs_counts_by_size.csv', index=False)
d.to_csv(ROOT / 'data/hs_universe.csv', index=False)
pd.set_option('display.width', 250)
print(counts.to_string(index=False))
