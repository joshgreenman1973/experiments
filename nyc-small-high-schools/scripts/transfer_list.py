"""DBNs of transfer high schools, from DOE progress reports (2006-07 to 2012-13) and School Quality Reports (2014-15 to 2023-24)."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
T = ROOT / 'raw/transfer'
dbns = {}
for f in ['fzv4-jan3', 'dj4e-3xrn', 'cgz5-877h', 'ffnc-f3aa', 'mjux-q9d4']:
    for r in json.load(open(T / f'{f}.json')):
        if r.get('school_level_') == 'Transfer School' or r.get('progress_report_type') == 'HST':
            dbns.setdefault(r['dbn'].strip(), r.get('school', ''))
for f in ['ctq9-j8y9', 'f4zj-z3db', 'sqr']:
    for r in json.load(open(T / f'{f}.json')):
        dbns.setdefault(r['dbn'].strip(), r.get('school_name', ''))
json.dump(dict(sorted(dbns.items())), open(ROOT / 'data/transfer_dbns.json', 'w'), indent=1)
print(len(dbns))
