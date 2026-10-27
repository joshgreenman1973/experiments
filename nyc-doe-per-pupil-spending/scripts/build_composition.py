"""Build data/composition.json: what per-pupil spending is made of (Section 8 and the three-school box).

Inputs (paths as arguments; raw Census files stay outside the repo):
  1. Census 2024 district file elsec24.xlsx
     (https://www2.census.gov/programs-surveys/school-finances/tables/2024/secondary-education-finance/elsec24.xlsx)
  2. Census 2024 summary tables elsec24_sumtables.xlsx (Table 18 NYC row, Table 8 U.S. row)
  3. data/three-schools/nysed_2024_25.json (from scripts/parse_nysed_transparency.py)

Census per pupil = (TCURELSC - V91 - V92) / V33, which reproduces Table 18. Its instruction line is
TCURINST - V91 - V92 (Table 18 subtracts payments to private and charter schools from instruction);
support services split into E17 pupil support, E07 instructional staff, E08 general administration,
E09 school administration, V40 operation and maintenance, V45 student transportation, V90 business/central/other
(V85 is zero for NYC); other current spending is E11 food services (V60, V65 are zero for NYC).

Usage: python3 scripts/build_composition.py elsec24.xlsx elsec24_sumtables.xlsx
"""
import json, os, sys
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dist_path, sum_path = sys.argv[1:3]

d = pd.read_excel(dist_path, dtype={'NCESID': str})
r = d[d.NCESID == '3620580'].iloc[0]
n = r.V33
pp = lambda v: v * 1000 / n
census_nyc = {
    'Instruction': pp(r.TCURINST - r.V91 - r.V92),
    'Pupil support': pp(r.E17),
    'Instructional staff support': pp(r.E07),
    'General administration': pp(r.E08),
    'School administration': pp(r.E09),
    'Building operation and maintenance': pp(r.V40),
    'Student transportation': pp(r.V45),
    'Business, central and other support': pp(r.V90 + r.V85),
    'Food services and other': pp(r.TCUROTH),
}
total = pp(r.TCURELSC - r.V91 - r.V92)
assert abs(sum(census_nyc.values()) - total) < 0.01

t18 = pd.read_excel(sum_path, sheet_name='18', header=None)
row = t18[t18[2].astype(str).str.strip() == 'New York City'].iloc[0]
t18v = dict(zip(['total', 'salaries', 'benefits', 'instr', 'instr_sal', 'instr_ben', 'support', 'pupil', 'instr_staff', 'gen_admin', 'sch_admin'],
                [float(row[i]) for i in range(5, 16)]))
assert abs(t18v['total'] - total) < 0.01 and abs(t18v['instr'] - census_nyc['Instruction']) < 0.01
t8 = pd.read_excel(sum_path, sheet_name='8', header=None)
us = t8[t8[0].astype(str).str.contains('United States')].iloc[0]
usv = dict(zip(['total', 'salaries', 'benefits', 'instr', 'instr_sal', 'instr_ben', 'support', 'pupil', 'instr_staff', 'gen_admin', 'sch_admin'],
               [float(us[i]) for i in range(2, 13)]))
census_us = {
    'Instruction': usv['instr'], 'Pupil support': usv['pupil'], 'Instructional staff support': usv['instr_staff'],
    'General administration': usv['gen_admin'], 'School administration': usv['sch_admin'],
    'Other support services (operation, transportation, business and central)':
        usv['support'] - usv['pupil'] - usv['instr_staff'] - usv['gen_admin'] - usv['sch_admin'],
    'Food services and other': usv['total'] - usv['instr'] - usv['support'],
}

# NYSED 2024-25 districtwide and three schools, grouped the same way in Section 8 and the box.
GROUPS = [('Instruction', [1, 3]), ('Pupil support', [2]), ('School administration', [5]),
          ('Transportation', [7]), ('Building operation and maintenance', [6]), ('Food services', [9]),
          ('Central administration and other districtwide costs', [4, 8, 12])]
ny = json.load(open(os.path.join(HERE, 'data', 'three-schools', 'nysed_2024_25.json')))
nysed = {}
for k in ['NYC districtwide', '13K307', '15K321', '75K369']:
    g = ny[k]['groups']
    nysed[k] = {'total': ny[k]['per_pupil_total'], 'groups': [
        {'name': name, **{o: sum(g[str(i)][o] for i in rows) for o in ('salaries', 'benefits', 'other')}}
        for name, rows in GROUPS]}
    assert abs(sum(x['salaries'] + x['benefits'] + x['other'] for x in nysed[k]['groups']) - nysed[k]['total']) < 0.2

out = {'census_fy2024': {'nyc_total': total, 'nyc': census_nyc, 'nyc_table18': t18v,
                         'us_total': usv['total'], 'us': census_us, 'us_table8': usv},
       'nysed_2024_25': nysed, 'nysed_groups': GROUPS}
json.dump(out, open(os.path.join(HERE, 'data', 'composition.json'), 'w'), indent=1)

print('Census NYC', round(total), {k: round(v) for k, v in census_nyc.items()})
print('Census instruction salaries/benefits/other', round(t18v['instr_sal']), round(t18v['instr_ben']),
      round(t18v['instr'] - t18v['instr_sal'] - t18v['instr_ben']))
print('Census US', round(usv['total']), {k: round(v) for k, v in census_us.items()})
for k, v in nysed.items():
    print(k, round(v['total']), [[round(x['salaries']), round(x['benefits']), round(x['other'])] for x in v['groups']])
