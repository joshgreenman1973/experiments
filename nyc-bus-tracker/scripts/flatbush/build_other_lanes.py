#!/usr/bin/env python3
"""Build data/spotlight/other-lanes.json for the "Other bus lane projects" section.

Input: other-lanes/results.json (from other-lanes/run.sh). Numbers are copied from it unchanged,
rounded for display. Names, labels and the short notes per project are written here by hand
from the flags in results.json.
Usage: build_other_lanes.py RESULTS_JSON OUT_JSON
"""
import json, sys

src, out = sys.argv[1], sys.argv[2]
R = {p['id']: p for p in json.load(open(src))}

SHOW = {
    # id: (display name, opened label, city claim, short note)
    1: ('Northern Boulevard, Broadway to 114th Street', 'Aug. 2023', '',
        'Construction start unknown, so only January to July of each year are compared. Afternoon rush fell {pm}%.'),
    2: ('Gun Hill Road, Bainbridge Avenue to Bartow Avenue', 'Oct. 2023', '',
        'Construction began May 2023, leaving only January to April to compare.'),
    3: ('Third Avenue, 59th to 96th streets', 'Dec. 2023', 'City: up to 14% faster.',
        'Measured from 67th Street north only. Afternoon rush rose {pm}%.'),
    4: ('Livingston Street, Boerum Place to Flatbush Avenue', 'Jan. 2024', '',
        'B45 and B67 only; the B41’s MTA segments here run mostly off Livingston.'),
    5: ('University Avenue, north section', 'Dec. 2023', '',
        'Bx3 only, with a small comparison set.'),
    6: ('Pelham Parkway, Boston Road to Stillwell Avenue', 'Dec. 2023', '',
        'One 1.2-mile Bx12 local segment, westbound. Slower in all {n} months compared.'),
    7: ('Second Avenue, 59th Street to Houston Street', 'Dec. 2024', '',
        'Congestion pricing began Jan. 5, 2025, a month after the lanes opened, and this stretch is inside the zone.'),
    8: ('96th Street, crosstown', 'Nov. 2024', '',
        'Small comparison set; faster in {pos} of {n} months compared.'),
    9: ('Third Avenue, 96th to 128th streets', 'Aug. 2025', '',
        'Faster in {pos} of {n} months compared.'),
    10: ('Hillside Avenue, 139th Street to Springfield Boulevard', 'Sept. 2025', 'City: up to 28% faster.',
         'Opened during the Queens bus network redesign, which changed stops on these routes. Afternoon rush rose {pm}%.'),
    12: ('Madison Avenue, 23rd to 42nd streets', 'July 2026', '',
         'Three months of data so far. Most of these buses are express routes.'),
}
NUM = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
sp = lambda n: NUM[n] if n < 10 else str(n)

projects = []
for i, (name, opened, claim, note) in SHOW.items():
    p = R[i]
    dm = p['did_month_pairs']
    routes = [r.replace('BX', 'Bx') for r in sorted(p['controlRoutes'], key=lambda r: (len(r), r))]
    if i == 12:
        routes = ['M1', 'M2', 'M3', 'and express routes']
    pm = p.get('pm_peak_change_pct')
    projects.append({
        'id': i, 'name': name, 'borough': p['borough'], 'opened': p['opened'], 'openedLabel': opened,
        'routes': routes, 'months': p['nAfterMonths'],
        'before_mph': p['before_mph'], 'after_mph': p['after_mph'],
        'change_pct': round(p['change_pct'], 1),
        'control_change_mph': round(p['control_change_mph'], 2) + 0.0,
        'diff_in_diff_mph': round(p['diff_in_diff_mph'], 2) + 0.0,
        'monthsFaster': dm['positive'],
        'cityClaim': claim,
        'flags': [note.format(pm=f'{abs(pm):.1f}' if pm is not None else '', n=sp(dm['n']), pos=sp(dm['positive']))],
    })
projects.sort(key=lambda p: p['opened'])

did = {p['id']: p['diff_in_diff_mph'] for p in projects}
up = [p for p in projects if p['diff_in_diff_mph'] > 0.05]
print('net change > 0.05 mph:', len(up), 'of', len(projects))
print({p['name']: p['diff_in_diff_mph'] for p in projects})

REL_FEB = 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-announces-city-will-restart-construction-of-four-h'
REL_JUN = 'https://www.nyc.gov/mayors-office/news/2026/06/mayor-mamdani-announces-new-and-upgraded-bus-lanes-and-widened-b'

copy = (
    f'The city finished bus lanes or busways on at least 15 other streets from 2023 through September 2026. '
    f'The MTA&rsquo;s monthly segment speeds can measure {len(projects)} of them. For each, the table compares buses on the '
    f'treated street in the months after it opened with the same months before construction, then subtracts the change '
    f'for the same routes on streets that got nothing new. The result is the net change. '
    f'By that measure, {sp(len(up))} of the {len(projects)} got faster, most by between {min(p["diff_in_diff_mph"] for p in up if p["id"] not in (10, 12)):.2f} '
    f'and {max(p["diff_in_diff_mph"] for p in up if p["id"] not in (10, 12)):.2f} mph. Hillside Avenue in Queens gained the most, '
    f'{did[10]:.2f} mph, but it opened during the Queens bus network redesign. Madison Avenue gained {did[12]:.2f} mph in its '
    f'first three months. Gun Hill Road and Livingston Street changed little, and buses on Pelham Parkway got slower.'
)
note = (
    'MTA Bus Route Segment Speeds, weekdays 7 a.m. to 7 p.m., weighted by trips. A route segment counts if at least half '
    'its length runs on the project. Each month after opening, up to 12 and through October 2026, is paired with the same '
    'month a year earlier, or two years earlier if that month fell during construction. These are whole-month MTA figures, '
    'a different source from the Flatbush GPS readings above. Four projects can&rsquo;t be measured this way because the '
    'MTA&rsquo;s segments through them are too long: Flatbush Avenue from Livingston to State streets (2025), Lexington '
    'Avenue from 52nd to 60th streets, Broadway in Queens and the Tremont Avenue busway (all 2026). City claims are from '
    f'mayoral press releases in <a href="{REL_FEB}" target="_blank" rel="noopener">February</a> and '
    f'<a href="{REL_JUN}" target="_blank" rel="noopener">June</a> 2026. A before-and-after comparison also picks up '
    'anything else that changed on the same street, such as signal timing or enforcement. '
    '<a href="data/spotlight/other-lanes-results.json">Full results</a>, with monthly series and every caveat.'
)
json.dump({'copy': copy, 'note': note, 'projects': projects}, open(out, 'w'), indent=1, ensure_ascii=False)
print(copy)
