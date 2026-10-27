"""Parse NYSED 2024-25 school Financial Transparency Reports (data.nysed.gov/expenditures.php?year=2025&instid=ID).

Saved pages live in data/three-schools/nysed/<instid>.html. Column 1 is NYC districtwide, column 2 the school.
Writes data/three-schools/nysed_2024_25.json.
"""
import html, json, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, 'data', 'three-schools', 'nysed')
IDS = {'800000045541': '13K307', '800000045158': '15K321', '800000043560': '75K369'}
cell = lambda c: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()
num = lambda v: float(v.replace('$', '').replace(',', '').replace('%', ''))
out = {}
for inst, dbn in IDS.items():
    s = open(os.path.join(D, inst + '.html'), encoding='utf-8').read()
    head = [cell(c) for c in re.findall(r'<th[^>]*scope=.column.[^>]*>(.*?)</th>', s, flags=re.S)]
    assert head[1].startswith("NYC Chancellor"), head
    tab = re.findall(r'<table.*?</table>', s, flags=re.S)[0]
    groups, total = {}, None
    for r in re.findall(r'<tr.*?</tr>', tab, flags=re.S):
        c = [cell(x) for x in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', r, flags=re.S)]
        m = re.match(r'^(\d+)\.(\d) (Salaries|Employee Benefits|All Other)$', c[0])
        if m:
            g = int(m.group(1)); groups.setdefault(g, {})[m.group(3)] = (num(c[1]), num(c[2]))
        m = re.match(r'^(\d+)\. (.+)$', c[0])
        if m and not c[0].startswith('13.'):
            groups.setdefault(int(m.group(1)), {})['name'] = m.group(2).split(' (')[0]
        if c[0].startswith('13. Total'):
            total = (num(c[1]), num(c[2]))
    enr = int(re.search(r'P-12 ENROLLMENT</div>\s*<div[^>]*><h4>([\d,]+)</h4>', s).group(1).replace(',', ''))
    for i, side in ((0, 'district'), (1, 'school')):
        rows = {g: {'name': v['name'], 'salaries': v['Salaries'][i], 'benefits': v['Employee Benefits'][i],
                    'other': v['All Other'][i]} for g, v in sorted(groups.items())}
        chk = sum(x['salaries'] + x['benefits'] + x['other'] for x in rows.values())
        assert abs(chk - total[i]) < 0.2, (dbn, side, chk, total[i])
        rec = {'per_pupil_total': total[i], 'groups': rows,
               'salaries': sum(x['salaries'] for x in rows.values()),
               'benefits': sum(x['benefits'] for x in rows.values()),
               'other': sum(x['other'] for x in rows.values())}
        if side == 'school':
            rec['enrollment'] = enr; rec['url'] = f'https://data.nysed.gov/expenditures.php?year=2025&instid={inst}'
            out[dbn] = rec
        else:
            out['NYC districtwide'] = rec
json.dump(out, open(os.path.join(HERE, 'data', 'three-schools', 'nysed_2024_25.json'), 'w'), indent=1)
for k, v in out.items():
    print(k, round(v['per_pupil_total']), 'sal', round(v['salaries']), 'ben', round(v['benefits']), 'oth', round(v['other']))
    for g, x in v['groups'].items():
        print('    %2d %-55s %8.0f' % (g, x['name'][:55], x['salaries'] + x['benefits'] + x['other']))
