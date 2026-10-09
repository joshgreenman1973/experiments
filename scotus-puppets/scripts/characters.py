# Character specs: rough caricatures of the Roberts Court (OT2023) and the two Rahimi advocates.
# Bench order from the gallery's point of view, left -> right (seniority seating).
BENCH_ORDER = ['barrett', 'gorsuch', 'sotomayor', 'thomas', 'roberts', 'alito', 'kagan', 'kavanaugh', 'jackson']

MAN = dict(shirt='#ecebe6')
WOMAN_COLLAR = dict(shirt='#efeee9', tie=None)

CHARS = {
    'roberts': dict(
        display='Chief Justice John G. Roberts, Jr.', oyez='John G. Roberts, Jr.',
        skin='#e7b09a', nose_mult=0.9, H=0.2, W=0.142, Wc=0.13, Wm=0.124, zb=-0.13, chin_fwd=0.01,
        sculpt=dict(brow=0.01, cheek=0.016, jowl=0.006, chin=0.004),
        eye_x=0.044, lid=0.38, smile=0.012,
        nose=dict(w=0.03, h=0.03, l=0.04, z=0.015, droop=0.15),
        brows=dict(hex='#8f8274', thick=1.2, angle=-0.05, arch=0.006),
        hair=dict(style='side_part', hex='#a9a59e', part=0.04, length=0.034, front_z=0.13, rand=0.15),
        body=dict(tie='#20263d')),
    'thomas': dict(
        display='Justice Clarence Thomas', oyez='Clarence Thomas',
        skin='#4a2c1f', nose_mult=0.92, H=0.2, W=0.152, Wc=0.136, Wm=0.134, Wj=0.12, zb=-0.135, chin_fwd=0.008,
        sculpt=dict(brow=0.014, cheek=0.014, jowl=0.012, chin=0.003),
        eye_x=0.046, lid=0.42, low_lid=0.12, smile=0.004, lid_hex='#432719',
        nose=dict(w=0.044, h=0.03, l=0.036, z=0.012, droop=0.12),
        brows=dict(hex='#3a3433', thick=1.3, angle=0.02, arch=0.004),
        hair=dict(style='buzz', hex='#8e8a86', length=0.006, front_z=0.155, side_z=0.04, count=70000, lift=0.15,
                  r0=0.0005, rand=0.35),
        glasses=dict(hex='#1c1816', metal=0.0, r=1.2, wire=0.0026, n=3.0),  # dark, fairly heavy rectangular frames
        body=dict(tie='#3b1f24')),
    'alito': dict(
        display='Justice Samuel A. Alito, Jr.', oyez='Samuel A. Alito, Jr.',
        skin='#dfa88a', nose_mult=0.9, H=0.212, W=0.136, Wc=0.126, Wm=0.12, Wj=0.104, zb=-0.14, chin_fwd=0.012,
        sculpt=dict(brow=0.016, cheek=0.01, jowl=0.004, chin=0.006),
        eye_x=0.043, lid=0.44, lid_tilt=-0.12, smile=0.002,
        nose=dict(w=0.03, h=0.034, l=0.046, z=0.012, droop=0.22),
        brows=dict(hex='#2f2925', thick=2.4, angle=0.06, arch=0.004, fur=0.024),
        hair=dict(style='side_part', hex='#6c6762', part=0.04, length=0.03, front_z=0.135, rand=0.3),
        body=dict(tie='#3c2b28')),
    'sotomayor': dict(
        display='Justice Sonia Sotomayor', oyez='Sonia Sotomayor',
        skin='#bf8762', nose_mult=0.92, H=0.198, W=0.142, Wc=0.13, Wm=0.126, zb=-0.13,
        sculpt=dict(brow=0.008, cheek=0.016, chin=0.004),
        eye_x=0.044, lid=0.34, smile=0.014,
        nose=dict(w=0.034, h=0.03, l=0.036, z=0.012, droop=0.16),
        ears=dict(show=False),
        brows=dict(hex='#3a2a22', thick=1.2, arch=0.008),
        hair=dict(style='bob', hex='#24160f', part=-0.03, length=0.12, front_z=0.13, volume=0.016, gravity=0.5,
                  curl=0.12, fringe=0.6, rand=0.25),
        body=dict(**WOMAN_COLLAR)),
    'kagan': dict(
        display='Justice Elena Kagan', oyez='Elena Kagan',
        skin='#ecbca4', nose_mult=0.92, H=0.198, W=0.148, Wc=0.134, Wm=0.13, Wj=0.116, zb=-0.13,
        sculpt=dict(brow=0.006, cheek=0.02, chin=0.002, jowl=0.004),
        eye_x=0.045, lid=0.36, smile=0.012,
        nose=dict(w=0.033, h=0.028, l=0.034, z=0.014, droop=0.14),
        ears=dict(show=False),
        brows=dict(hex='#6b5a4e', thick=1.1, arch=0.006),
        hair=dict(style='bob', hex='#4f4239', part=0.035, length=0.09, front_z=0.135, volume=0.012, gravity=0.55, fringe=0.3, rand=0.25),
        body=dict(**WOMAN_COLLAR)),
    'gorsuch': dict(
        display='Justice Neil Gorsuch', oyez='Neil Gorsuch',
        skin='#e7b296', nose_mult=0.92, H=0.215, W=0.13, Wc=0.124, Wm=0.116, Wj=0.1, zb=-0.142, chin_fwd=0.016,
        sculpt=dict(brow=0.016, cheek=0.006, chin=0.008, temple=0.008),
        eye_x=0.042, lid=0.36, lid_tilt=-0.08, smile=0.008,
        nose=dict(w=0.028, h=0.032, l=0.046, z=0.012, droop=0.2),
        brows=dict(hex='#4e443d', thick=1.5, arch=0.006, angle=0.03),
        hair=dict(style='side_part', hex='#b9b7b2', part=0.03, length=0.045, front_z=0.14, lift=0.62, rand=0.12),
        body=dict(tie='#2b3346')),
    'kavanaugh': dict(
        display='Justice Brett M. Kavanaugh', oyez='Brett M. Kavanaugh',
        skin='#e9ad92', nose_mult=0.88, H=0.2, W=0.148, Wc=0.134, Wm=0.13, Wj=0.118, zb=-0.13,
        sculpt=dict(brow=0.01, cheek=0.016, chin=0.004, jowl=0.004),
        eye_x=0.045, lid=0.4, smile=0.012,
        nose=dict(w=0.034, h=0.03, l=0.038, z=0.013, droop=0.16),
        brows=dict(hex='#3b2e27', thick=1.5, arch=0.005),
        hair=dict(style='side_part', hex='#3d2f26', part=0.04, length=0.03, front_z=0.135, rand=0.22),
        body=dict(tie='#3a2333')),
    'barrett': dict(
        display='Justice Amy Coney Barrett', oyez='Amy Coney Barrett',
        skin='#f0c3ab', nose_mult=0.93, H=0.205, W=0.13, Wc=0.124, Wm=0.116, Wj=0.1, zb=-0.135, chin_fwd=0.012,
        sculpt=dict(brow=0.006, cheek=0.012, chin=0.006),
        eye_x=0.042, lid=0.32, smile=0.01,
        nose=dict(w=0.026, h=0.026, l=0.034, z=0.014, droop=0.14),
        ears=dict(show=False),
        brows=dict(hex='#3b2a20', thick=1.1, arch=0.008),
        hair=dict(style='long', hex='#2c1d15', part=-0.035, length=0.27, front_z=0.135, volume=0.012, fringe=0.0),
        body=dict(**WOMAN_COLLAR)),
    'jackson': dict(
        display='Justice Ketanji Brown Jackson', oyez='Ketanji Brown Jackson',
        skin='#6b4230', nose_mult=0.92, H=0.2, W=0.142, Wc=0.13, Wm=0.126, zb=-0.13,
        sculpt=dict(brow=0.008, cheek=0.018, chin=0.004),
        eye_x=0.044, lid=0.32, smile=0.016, lid_hex='#5f3a29',
        nose=dict(w=0.038, h=0.028, l=0.034, z=0.012, droop=0.14),
        ears=dict(show=False),
        brows=dict(hex='#1f1612', thick=1.2, arch=0.008),
        hair=dict(style='locs', hex='#170f0b', length=0.3, locs=190, front_z=0.14, rand=0.15),
        glasses=dict(hex='#5a3550', metal=0.35, r=1.15, wire=0.0018, n=2.6),  # plum, slightly cat-eye frames
        body=dict(**WOMAN_COLLAR)),
}

# ---------------------------------------------------------------- per-case settings (advocates, glasses, bench)
import json as _json, os as _os
CASE_PATH = _os.environ.get('SCOTUS_CASE') or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'case.json')
CASE = _json.load(open(CASE_PATH))

# A different Court (an older term) can override the seating and add or replace justices in case.json:
#   "bench_order": [...gallery left -> right...], "justices": {"breyer": {...spec with display/oyez...}}
if CASE.get('bench_order'):
    BENCH_ORDER = list(CASE['bench_order'])
for _k, _spec in CASE.get('justices', {}).items():
    CHARS[_k] = _spec

ADVOCATES = list(CASE['advocates'])
for _k, _a in CASE['advocates'].items():
    _spec = dict(_a.get('spec', {}))
    _spec.update(display=_a['display'], oyez=_a['oyez'], role=_a.get('role', ''))
    CHARS[_k] = _spec

# Glasses: Thomas (dark rectangular) and Jackson (plum) wear them (set above). Add a pair for anyone else in case.json, e.g.
# "glasses": {"thomas": {"hex": "#3a3a3a", "metal": 0.0}}
for _k, _g in CASE.get('glasses', {}).items():
    CHARS[_k]['glasses'] = _g
