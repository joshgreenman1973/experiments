"""Parse 2024-25 NYSED Financial Transparency Reports for New York City high schools.

Each saved page (raw/fin2025/<instid>.html) has a districtwide column (NYC Chancellor's Office) and a school column.
Rows 1-12 are functions, each split into salaries, employee benefits and all other; row 13 is the total.
Writes data/hs_functions_2024_25.csv: per-pupil dollars by function for the school column.
"""
import csv, html, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
cell = lambda c: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()
num = lambda v: float(v.replace('$', '').replace(',', '').replace('%', '') or 0)
ids = {r['INSTITUTION_ID']: (r['beds'], r['dbn']) for r in csv.DictReader(open(ROOT / 'data/hs_2025_instids.csv'))}
rows, bad = [], []
for inst, (beds, dbn) in ids.items():
    f = ROOT / f'raw/fin2025/{inst}.html'
    if not f.exists():
        bad.append((dbn, 'missing')); continue
    s = f.read_text(encoding='utf-8', errors='replace')
    tabs = re.findall(r'<table.*?</table>', s, flags=re.S)
    if not tabs:
        bad.append((dbn, 'no table')); continue
    fn, total = {}, None
    for r in re.findall(r'<tr.*?</tr>', tabs[0], flags=re.S):
        c = [cell(x) for x in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', r, flags=re.S)]
        if len(c) < 3: continue
        m = re.match(r'^(\d+)\.(\d) (Salaries|Employee Benefits|All Other)$', c[0])
        if m:
            fn[int(m.group(1))] = fn.get(int(m.group(1)), 0) + num(c[2])
        if c[0].startswith('13. Total'):
            total = num(c[2])
    if total is None or abs(sum(fn.values()) - total) > 1:
        bad.append((dbn, 'sum mismatch')); continue
    em = re.search(r'P-12 ENROLLMENT</div>\s*<div[^>]*><h4>([\d,]+)</h4>', s)
    rec = {'beds': beds, 'dbn': dbn, 'instid': inst, 'enrollment': int(em.group(1).replace(',', '')) if em else '',
           'total_pp': total}
    for k in range(1, 13):
        rec[f'f{k}'] = fn.get(k, 0)
    rows.append(rec)
with open(ROOT / 'data/hs_functions_2024_25.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), 'parsed;', len(bad), 'problems', bad[:10])
