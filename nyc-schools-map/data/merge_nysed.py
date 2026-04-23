#!/usr/bin/env python3
"""Merge NYSED enrollment (2019-20 through 2024-25) into schools.json."""
import json, re, sys
from access_parser import AccessParser

NYSED_FILES = [
    '/tmp/nysed/ENROLL2022_20221114.accdb',
    '/tmp/nysed/ENROLL2025_20251217.accdb',
]

SCHOOL_YEAR_LABEL = {
    2020: '2019-20', 2021: '2020-21', 2022: '2021-22',
    2023: '2022-23', 2024: '2023-24', 2025: '2024-25',
}

BORO = {'M':'31','X':'32','K':'33','Q':'34','R':'35'}

def dbn_to_beds(dbn):
    m = re.match(r'^(\d{2})([MXKQR])(\d+)$', dbn or '')
    if not m: return None
    d, b, s = m.groups()
    return f"{BORO[b]}{d}00010{s.zfill(3)[-3:]}"

def norm_name(n):
    n = (n or '').upper().strip()
    n = re.sub(r'\s+(CHARTER SCHOOL|CHARTER|SCHOOL)$', '', n).strip()
    n = re.sub(r'[^A-Z0-9 ]+', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def load_all():
    by_beds, by_name = {}, {}
    for path in NYSED_FILES:
        t = AccessParser(path).parse_table('BEDS Day Enrollment')
        for i in range(len(t['ENTITY_CD'])):
            cd = t['ENTITY_CD'][i]
            yr = t['YEAR'][i]
            if not cd or len(cd) != 12: continue
            try: yi = int(yr.rstrip('.'))
            except: continue
            k12 = t['K12'][i] or 0
            pk = (t['PKFULL'][i] or 0) + (t['PKHALF'][i] or 0)
            total = k12 + pk
            by_beds.setdefault(cd, {})[yi] = total
            nm = norm_name(t['ENTITY_NAME'][i])
            if nm:
                by_name.setdefault(nm, {})[yi] = total
    return by_beds, by_name

def main():
    by_beds, by_name = load_all()
    path = 'nyc-schools-map/public/data/schools.json'
    schools = json.load(open(path))
    stats = {'dbn': 0, 'name': 0, 'none': 0, 'private_skipped': 0}
    for s in schools:
        if s.get('sector') == 'private':
            stats['private_skipped'] += 1
            continue
        trend = None
        dbn = s.get('dbn', '')
        beds = dbn_to_beds(dbn)
        if beds and beds in by_beds:
            trend = by_beds[beds]
            stats['dbn'] += 1
        elif s.get('sector') == 'charter':
            nm = norm_name(s.get('name', ''))
            if nm in by_name:
                trend = by_name[nm]
                stats['name'] += 1
        if not trend:
            stats['none'] += 1
            continue
        years = sorted(trend.keys())
        s['trend'] = [[SCHOOL_YEAR_LABEL[y], trend[y]] for y in years if y in SCHOOL_YEAR_LABEL]
        latest_year = years[-1]
        if s.get('demo') is None:
            s['demo'] = {}
        s['demo']['year_enrollment'] = SCHOOL_YEAR_LABEL[latest_year]
        s['demo']['enrollment_latest'] = trend[latest_year]
    json.dump(schools, open(path, 'w'))
    print(stats)

if __name__ == '__main__':
    main()
