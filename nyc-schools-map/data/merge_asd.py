#!/usr/bin/env python3
"""Merge authoritative ASD Nest + ASD Horizon school lists into schools.json.

Nest list from NYU Steinhardt (DOE's official partner):
  https://steinhardt.nyu.edu/metrocenter/nest/nyc-public-schools-nest-program
Horizon list: no single public list exists; combining confirmed self-identified
schools with DOE resource pages. Not exhaustive.
"""
import json, re

# borough letter in DBN: M=Manhattan, X=Bronx, K=Brooklyn, Q=Queens, R=Staten Island
BORO_LETTER = {
    'Manhattan': 'M', 'Bronx': 'X', 'Brooklyn': 'K',
    'Queens': 'Q', 'Staten Island': 'R',
}

# NEST, by borough (NYU Steinhardt, ~88 schools)
NEST = {
    'Brooklyn': [
        'PS 26', 'PS 32', 'PS 84', 'PS 115', 'PS 121', 'PS 151', 'PS 155',
        'PS 222', 'PS 244', 'PS 255', 'PS 297', 'PS 316', 'PS 375', 'PS 682',
        'IS 278', 'MS 407', 'MS 442', 'MS 447', 'Seth Low',
        'Brooklyn Science', 'Cobble Hill', 'Ebbets Field',
        'Franklin D. Roosevelt', 'FDR', 'HSTAT', 'Juan Morel Campos',
        'Madiba Prep', 'Millennium Brooklyn', 'Nelson Mandela', 'Sunset',
    ],
    'Manhattan': [
        'PS 19', 'PS 36', 'PS 42', 'PS 75', 'PS 110', 'PS 112', 'PS 178',
        'PS 197', 'PS 206', 'PS/MS 206',
        'Lab Middle', 'Mott Hall School', 'University Neighborhood',
        'Esperanza Preparatory', 'Lab High', 'West Prep',
        'Urban Assembly for Media',
    ],
    'Queens': [
        'PS 36', 'PS 76', 'PS 88', 'PS 100', 'PS 153', 'PS 165', 'PS 186',
        'PS 207', 'PS 317', 'PS 354',
        'IS 125', 'IS 204', 'MS 219',
        'Channel View', 'East-West School of International',
        'Queens High School of Teaching', 'Queens School of Inquiry',
        'Academy for Careers in Television and Film',
    ],
    'Bronx': [
        'Bronx Little', 'PS 68', 'PS 97', 'PS 179', 'PS 182', 'PS 207',
        'PS 392', 'PS 396', 'PS 443',
        'MS 363', 'One World Middle',
        'Bronxdale', 'Bronx Engineering', 'High School for Teaching Professions',
        'Millennium Art Academy', 'Mott Hall', 'Samara Community',
    ],
    'Staten Island': [
        'PS 4', 'PS 9', 'PS 59', 'PS 60', 'PS 69',
        'IS 27', 'IS 72', 'IS 75',
        'Ralph McKee', 'Tottenville',
    ],
}

# HORIZON — partial, confirmed via school self-ID and Chalkbeat reporting
HORIZON = {
    'Manhattan': ['PS 133'],
    'Staten Island': ['PS 9', 'Naples Street'],
    'Bronx': ['IS 162', 'Millennium Art Academy'],
    'Queens': ['PS 91'],
    'Brooklyn': [],
}


def norm(s):
    s = (s or '').upper()
    s = s.replace('P.S.', 'PS').replace('I.S.', 'IS').replace('M.S.', 'MS')
    s = s.replace('J.H.S.', 'JHS').replace('H.S.', 'HS')
    s = re.sub(r'[^A-Z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # strip leading zeros from PS/IS/MS/JHS numbers: "PS 026" -> "PS 26"
    s = re.sub(r'\b(PS|IS|MS|JHS|HS)\s+0*(\d+)\b', r'\1 \2', s)
    return s


def name_matches(school_name, query):
    n = norm(school_name)
    q = norm(query)
    # PS 26 must match exact number, not PS 260 / PS 269 etc.
    m = re.match(r'^(PS|IS|MS|JHS)\s+(\d+)$', q)
    if m:
        prefix, num = m.group(1), m.group(2)
        # match any of PS/IS/MS/JHS before the number (JHS 278 == IS 278)
        return bool(re.search(rf'\b(PS|IS|MS|JHS)\s+{num}\b', n))
    # otherwise loose substring
    return q in n


def apply_program(schools, program_label, borough_map):
    by_boro = {}
    for s in schools:
        dbn = s.get('dbn', '')
        if len(dbn) < 3:
            continue
        letter = dbn[2]
        by_boro.setdefault(letter, []).append(s)

    matched = 0
    unmatched = []
    for borough, queries in borough_map.items():
        letter = BORO_LETTER[borough]
        pool = by_boro.get(letter, [])
        for q in queries:
            hits = [s for s in pool if s.get('sector') in ('public', 'charter')
                    and name_matches(s.get('name', ''), q)]
            if not hits:
                unmatched.append(f'{borough}: {q}')
                continue
            # take all that matched — PS 207 in Bronx may be one school, but
            # ambiguous names (e.g. "Mott Hall") might match several
            for s in hits:
                progs = s.setdefault('programs', [])
                if program_label not in progs:
                    progs.append(program_label)
                    matched += 1
    return matched, unmatched


def main():
    path = 'nyc-schools-map/public/data/schools.json'
    schools = json.load(open(path))

    # Strip existing narrative-extracted ASD tags — we replace with authoritative
    for s in schools:
        p = s.get('programs') or []
        s['programs'] = [t for t in p if t not in ('ASD Nest', 'ASD Horizon')]

    nest_n, nest_missed = apply_program(schools, 'ASD Nest', NEST)
    horz_n, horz_missed = apply_program(schools, 'ASD Horizon', HORIZON)

    # Count final tags
    final_nest = sum(1 for s in schools if 'ASD Nest' in (s.get('programs') or []))
    final_horz = sum(1 for s in schools if 'ASD Horizon' in (s.get('programs') or []))

    json.dump(schools, open(path, 'w'))

    print(f'Nest: tagged {final_nest} schools ({nest_n} additions)')
    print(f'Horizon: tagged {final_horz} schools ({horz_n} additions)')
    if nest_missed:
        print(f'\nNest unmatched ({len(nest_missed)}):')
        for m in nest_missed: print(' ', m)
    if horz_missed:
        print(f'\nHorizon unmatched ({len(horz_missed)}):')
        for m in horz_missed: print(' ', m)


if __name__ == '__main__':
    main()
