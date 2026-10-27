"""Build data/three-schools/three_schools.json for the "Three Brooklyn schools" box.

Sources (download first; paths are arguments so raw files stay outside the repo):
  1. DOE Galaxy budget summaries, FY2026 (as of June 25, 2026). Fetched with
     scripts/fetch_galaxy.py into data/three-schools/galaxy/ (the page only renders via a form post).
  2. DOE Demographic Snapshot 2021-22 to 2025-26, "School" sheet (2025-26 enrollment, disability and poverty shares).
  3. NYSED report card database SRC2025 (https://data.nysed.gov/files/essa/24-25/SRC2025.zip),
     table "Expenditures per Pupil", YEAR 2025 = 2024-25 actual spending.
  4. NYC School Funding Transparency Form 2022-23
     (https://infohub.nyced.org/docs/default-source/default-document-library/newyorkcityschooltransparency202223.zip),
     Parts B and C.

Usage:
  python3 scripts/build_three_schools.py SNAPSHOT.xlsx SRC2025_Group4.mdb NewYorkCitySchoolTransparency202223.xlsx
  (needs pandas; the .mdb is read with access-parser, e.g. `uv run --with access-parser --with pandas --with openpyxl`)
"""
import json, os, statistics, sys
import pandas as pd
from access_parser import AccessParser

sys.path.insert(0, os.path.dirname(__file__))
from galaxy_parse import parse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'data', 'three-schools')
SCHOOLS = [  # DBN, Galaxy code, NYSED BEDS code, form code
    ('13K307', 'K307', '331300010307', '13K307'),
    ('15K321', 'K321', '331500010321', '15K321'),
    ('75K369', 'K369', '307500013369', '97K369'),
]
# Galaxy sections -> the box's six groups
GROUPS = {
    'Teachers': ['Classroom Teacher', 'Elementary Cluster/Quota', 'Cluster/Quota Teacher', 'Q Rate',
                 'Homeroom Teacher - Alternate Assessment', 'Homeroom Teacher - Standard Assessment',
                 'Classroom Teacher - Alternate Assessment', 'Classroom Teacher - Standard Assessment'],
    'Related services, counselors and evaluators': ['Special Needs - Support Services', 'Guidance/Social Workers', 'SBST'],
    'Paraprofessionals': ['Paraprofessionals'],
    'Principal, assistant principals and office staff': ['Leadership', 'Coordinator/Supervisor/Dean', 'Secretary',
                                                        'School Aides and Other Support Staff', 'Family Workers'],
    'Coaches, substitutes, extra hours and departed staff': ['Professional/Curriculum Development', 'Per Diem',
                                                             'Per Session', 'Per Session - After/Before School',
                                                             'Per Session - Professional Development',
                                                             'Per Session - Miscellaneous', 'Sixth period coverage',
                                                             'People Working Partial Year'],
    'Supplies, contracts and other non-personnel': ['OTPS', 'Setasides'],
}
SEC2GRP = {s: g for g, ss in GROUPS.items() for s in ss}

snap_path, mdb_path, form_path = sys.argv[1:4]
snap = pd.read_excel(snap_path, sheet_name='School')
snap = snap[snap['Year'] == '2025-26'].set_index('DBN')

db = AccessParser(mdb_path)
tb = db.parse_table('Expenditures per Pupil')
cols = list(tb.keys())
ess = [{c: tb[c][i] for c in cols} for i in range(len(tb[cols[0]]))]
ess = [r for r in ess if r['YEAR'] == 2025 and r['PER_FED_STATE_LOCAL_EXP']]
by_beds = {r['ENTITY_CD']: r for r in ess}
# Comparison sets: District 75 (codes 3075...) and schools in the 32 geographic districts (borough digits 1-5)
d75 = [r['PER_FED_STATE_LOCAL_EXP'] for r in ess if r['ENTITY_CD'].startswith('3075')]
geo = [r['PER_FED_STATE_LOCAL_EXP'] for r in ess
       if len(r['ENTITY_CD']) == 12 and r['ENTITY_CD'][0] == '3' and r['ENTITY_CD'][1] in '12345'
       and r['ENTITY_CD'][2:4].isdigit() and 1 <= int(r['ENTITY_CD'][2:4]) <= 32 and r['ENTITY_CD'][8:] != '0000']

fb = pd.read_excel(form_path, sheet_name='Part B', header=6).set_index('Local School Code')
fc = pd.read_excel(form_path, sheet_name='Part C', header=6).set_index('Local School Code')

out = {'comparison_2024_25': {
    'district_school_median': statistics.median(geo), 'district_school_n': len(geo),
    'd75_median': statistics.median(d75), 'd75_n': len(d75)}, 'schools': []}
for dbn, gcode, beds, fcode in SCHOOLS:
    secs, sitetot, grand = parse(os.path.join(OUT, 'galaxy', f'{gcode}_FY2026.txt'))
    total = sum(s['total'][1] for s in secs)
    assert total == (grand[1] if grand else sum(sitetot.values())), gcode
    groups = {g: {'dollars': 0, 'positions': 0.0} for g in GROUPS}
    for s in secs:
        g = SEC2GRP[s['sec']]
        groups[g]['dollars'] += s['total'][1]
        groups[g]['positions'] += s['total'][0]
    sn = snap.loc[dbn]
    enr = int(sn['Total Enrollment'])
    e = by_beds[beds]
    b, c = fb.loc[fcode], fc.loc[fcode]
    form_enr = int(b['K-12 Enrollment'] + b['Pre-K\nEnrollment'] + b['Preschool Special Ed Enrollment'])
    rank_set = d75 if dbn.startswith('75') else geo
    out['schools'].append({
        'dbn': dbn, 'name': sn['School Name'],
        'enrollment_2025_26': enr,
        'pct_swd_2025_26': float(sn['% Students with Disabilities']),
        'pct_poverty_2025_26': float(sn['% Poverty']),
        'grades_3k_pk_2025_26': int(sn['Grade 3K'] + sn['Grade PK (Half Day & Full Day)']),
        'galaxy_fy2026': {
            'total': total, 'sites': len(sitetot), 'per_pupil': total / enr,
            'groups': {g: {**v, 'per_pupil': v['dollars'] / enr} for g, v in groups.items()}},
        'actual_2024_25': {
            'pupils': e['PUPIL_COUNT_TOT'], 'total': e['FED_STATE_LOCAL_EXP'],
            'per_pupil': e['PER_FED_STATE_LOCAL_EXP'], 'per_pupil_federal': e['PER_FEDERAL_EXP'],
            'per_pupil_state_local': e['PER_STATE_LOCAL_EXP'],
            'share_of_comparison_below': sum(x < e['PER_FED_STATE_LOCAL_EXP'] for x in rank_set) / len(rank_set)},
        'form_2022_23': {
            'enrollment': form_enr,
            'teacher_salaries': float(c['Classroom Teachers']), 'other_salaries': float(c['All Other Salaries']),
            'benefits': float(c['Employee Benefits']), 'other': float(c['All Other']),
            'school_total': float(c['Total Allocation by Object']), 'central': float(c['Central District Costs']),
            'total_with_central': float(c['Total School Allocation w/ Central District Costs']),
            'per_pupil': float(c['Total School Funding per Pupil']),
            'central_per_pupil': float(c['Central District Costs']) / form_enr},
    })
json.dump(out, open(os.path.join(OUT, 'three_schools.json'), 'w'), indent=1, default=float)
for s in out['schools']:
    g = s['galaxy_fy2026']; a = s['actual_2024_25']; f = s['form_2022_23']
    print(s['dbn'], s['enrollment_2025_26'], 'galaxy pp %.0f' % g['per_pupil'],
          {k[:12]: round(v['per_pupil']) for k, v in g['groups'].items()},
          'actual pp', a['per_pupil'], 'pct below %.2f' % a['share_of_comparison_below'],
          'form pp %.0f benefits/salaries %.3f' % (f['per_pupil'], f['benefits'] / (f['teacher_salaries'] + f['other_salaries'])))
print(out['comparison_2024_25'])
