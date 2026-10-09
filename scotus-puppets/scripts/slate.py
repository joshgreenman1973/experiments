# Build configs for a slate of arguments from one term: one advocate registry (stand-in puppets) and a
# per-case config that characters.py / timeline.py / build_page.py read.
# Usage: python slate.py SLATE.json WORKROOT
#   SLATE.json: {"term": "2025", "cases": [{"docket": ..., "short": "TRUMP v. SLAUGHTER", "topic": "..."}, ...],
#                "outcomes": "path/to/outcomes.json", "advocate_overrides": {"Oyez Name": {...spec...}}}
#   WORKROOT/cases/<docket>/ must hold transcript.json, case.json (Oyez record) and audio.mp3 (scripts/fetch_slate.sh).
# Writes WORKROOT/slate_case.json (every advocate, for rendering) and WORKROOT/cases/<docket>/cfg.json.
import collections, datetime, hashlib, html, json, os, re, sys

slate_path, root = sys.argv[1], sys.argv[2]
slate = json.load(open(slate_path))
JUSTICES = {'John G. Roberts, Jr.', 'Clarence Thomas', 'Samuel A. Alito, Jr.', 'Sonia Sotomayor', 'Elena Kagan', 'Neil Gorsuch',
            'Brett M. Kavanaugh', 'Amy Coney Barrett', 'Ketanji Brown Jackson'}
outcomes = {o['docket'].strip(): o for o in json.load(open(slate['outcomes']))} if slate.get('outcomes') else {}

# ---------------------------------------------------------------- stand-in puppets
# The advocates' looks can't be verified from here, so they are "Anything Muppet" stand-ins: felt in non-human colors
# (no guess at anyone's race), with dress and hair following how the justices addressed them (Mr. / Ms.).
FELT = ['#7f8fc9', '#86a989', '#a48cc6', '#5d9fa3', '#6f8fb6', '#86c0aa', '#9a80b2', '#99a86e', '#7aa2d4', '#78b5a6',
        '#b08aa8', '#8a9bb0']
HAIR = ['#2a1e17', '#3d2c22', '#5a4434', '#7a5f48', '#9b9790', '#b9b5ad', '#1d1714', '#6e6a66']
SUIT = ['#15161c', '#1c2230', '#23252b', '#2a2a2e', '#1a2430', '#242028']
TIE = ['#7a1f24', '#2b3a5e', '#3b5b3a', '#5a2d5e', '#8a6a2a', '#2f4f5f', '#6a2a2a', '#40406a']


def rng_for(name):
    h = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    def pick(seq, salt=0):
        return seq[(h >> (salt * 7)) % len(seq)]
    def uni(lo, hi, salt=0):
        return round(lo + (hi - lo) * (((h >> (salt * 11 + 3)) % 1000) / 999), 4)
    return pick, uni


def stand_in_spec(name, presentation, felt):
    pick, uni = rng_for(name)
    hair_hex = pick(HAIR, 1)
    spec = dict(
        skin=felt, nose_mult=0.86, H=uni(0.195, 0.212, 1), W=uni(0.128, 0.15, 2), Wc=uni(0.122, 0.136, 3),
        Wm=uni(0.114, 0.13, 4), zb=uni(-0.142, -0.128, 5), chin_fwd=uni(0.008, 0.016, 6),
        sculpt=dict(brow=uni(0.006, 0.014, 7), cheek=uni(0.008, 0.018, 8), chin=uni(0.003, 0.008, 9)),
        eye_x=uni(0.041, 0.046, 10), lid=uni(0.3, 0.42, 11), smile=uni(0.004, 0.014, 12),
        nose=dict(w=uni(0.026, 0.04, 13), h=uni(0.026, 0.034, 14), l=uni(0.032, 0.046, 15), z=0.013, droop=uni(0.12, 0.22, 16)),
        brows=dict(hex=hair_hex, thick=uni(0.9, 1.6, 17), arch=uni(0.004, 0.008, 18)),
        crop_closeup=True)
    if presentation == 'Ms.':
        style = pick(['bob', 'long', 'bob'], 2)
        spec['ears'] = dict(show=False)
        spec['hair'] = dict(style=style, hex=hair_hex, part=pick([-0.035, 0.03], 3),
                            length=uni(0.1, 0.13, 19) if style == 'bob' else uni(0.17, 0.23, 19), front_z=0.135,
                            volume=0.012, fringe=0.0 if style == 'long' else 0.3)
        spec['body'] = dict(robe=pick(SUIT, 4), shirt='#efeee9', tie=None)
    else:
        spec['hair'] = dict(style='side_part', hex=hair_hex, part=pick([-0.035, 0.035, 0.04], 3),
                            length=uni(0.026, 0.04, 19), front_z=uni(0.13, 0.15, 20))
        spec['body'] = dict(robe=pick(SUIT, 4), shirt='#ecebe6', tie=pick(TIE, 5))
    return spec


def stand_in_note(advs):
    """Advocates listed in the slate's advocate_overrides are modeled on photos; the rest are felt-colored stand-ins."""
    real = [v['caption_label'].title() for v in advs.values()
            if v['oyez'] in slate.get('advocate_overrides', {})]
    if not real:
        return 'The lawyers are stand-in puppets in felt colors, not likenesses; their names are on screen.'
    who = real[0] if len(real) == 1 else ', '.join(real[:-1]) + ' and ' + real[-1]
    if len(real) == len(advs):
        return f'The lawyers ({who}) are puppet caricatures modeled on photos.'
    return f"{who} {'is' if len(real) == 1 else 'are'} modeled on photos; the other lawyers are stand-in puppets in felt colors, not likenesses."


def key_for(name, taken):
    toks = [t for t in re.sub(r'[^A-Za-z\- ]', ' ', name.replace(', Jr.', '')).split() if len(t) > 1]
    k = toks[-1].lower().replace('-', '_')
    if k in taken and taken[k] != name:
        k = (toks[0] + '_' + toks[-1]).lower().replace('-', '_')
    taken[k] = name
    return k


def strip(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', h or ''))).strip()


# ---------------------------------------------------------------- gather advocates across the slate
adv = collections.OrderedDict()
case_info = {}
taken = {}
for c in slate['cases']:
    d = c['docket']
    D = os.path.join(root, 'cases', d)
    tr = json.load(open(os.path.join(D, 'transcript.json')))
    rec = json.load(open(os.path.join(D, 'case.json')))
    turns = [t for s in tr['transcript']['sections'] for t in s['turns'] if t.get('speaker')]
    bench_text = ' '.join(b['text'] for t in turns if t['speaker']['name'] in JUSTICES for b in t['text_blocks'])
    descs = {a['advocate']['name']: (a.get('advocate_description') or '').strip() for a in (rec.get('advocates') or []) if a.get('advocate')}
    names = []
    for t in turns:
        n = t['speaker']['name']
        if n in JUSTICES or n in names:
            continue
        names.append(n)
        a = adv.setdefault(n, dict(hon=collections.Counter(), cases={}))
        last = n.replace(', Jr.', '').split()[-1]
        for m in re.finditer(r'\b(Mr\.|Ms\.|Mrs\.|General)\s+' + re.escape(last) + r'\b', bench_text):
            a['hon'][m.group(1)] += 1
        a['cases'][d] = descs.get(n, '')
    title = tr.get('title', '')
    dt = datetime.datetime.strptime(title.split(' - ', 1)[1].strip(), '%B %d, %Y').date()
    case_info[d] = dict(name=rec.get('name') or c.get('name'), argued=dt, question=strip(rec.get('question')), advocates=names)

registry = {}
used_felt = collections.defaultdict(set)
for n, a in adv.items():
    k = key_for(n, taken)
    hon = a['hon'].most_common()
    honorific = hon[0][0] if hon else 'Mr.'
    presentation = 'Ms.' if a['hon']['Ms.'] + a['hon']['Mrs.'] > a['hon']['Mr.'] else 'Mr.'
    pick, _ = rng_for(n)
    felt = pick(FELT, 0)
    for _ in range(len(FELT)):  # different colors for advocates who share a case
        if not any(felt in used_felt[d] for d in a['cases']):
            break
        felt = FELT[(FELT.index(felt) + 1) % len(FELT)]
    for d in a['cases']:
        used_felt[d].add(felt)
    spec = stand_in_spec(n, presentation, felt)
    spec.update(slate.get('advocate_overrides', {}).get(n, {}))
    registry[k] = dict(oyez=n, display=n, honorific=honorific, caption_label=f"{honorific.upper()} {n.replace(', Jr.', '').split()[-1].upper()}",
                       presentation=presentation, cases=a['cases'], spec=spec)

base_case = dict(term=slate['term'], docket='slate', case_name='slate', short_name='', argued='', argued_short='',
                 sections=[], web={}, glasses={})
json.dump(dict(base_case, advocates={k: dict(oyez=r['oyez'], display=r['display'], role='', caption_label=r['caption_label'],
                                              spec=r['spec']) for k, r in registry.items()}),
          open(os.path.join(root, 'slate_case.json'), 'w'), indent=1)
json.dump(registry, open(os.path.join(root, 'advocates.json'), 'w'), indent=1)

oyez_key = {r['oyez']: k for k, r in registry.items()}
for c in slate['cases']:
    d = c['docket']
    ci = case_info[d]
    dt = ci['argued']
    advs = {}
    for n in ci['advocates']:
        k = oyez_key[n]
        r = registry[k]
        advs[k] = dict(oyez=n, display=r['display'], role=r['cases'][d], caption_label=r['caption_label'], spec=r['spec'])
    o = outcomes.get(d, {})
    real = [k for k, v in advs.items() if v['oyez'] in slate.get('advocate_overrides', {})]
    cfg = dict(term=slate['term'], docket=d, case_name=c.get('name') or ci['name'], short_name=c['short'],
               argued=dt.strftime('%B ') + str(dt.day) + dt.strftime(', %Y'),
               argued_short=dt.strftime('%b. ').upper().replace('MAY. ', 'MAY ').replace('JUN. ', 'JUNE ').replace('JUL. ', 'JULY ')
                            .replace('SEP. ', 'SEPT. ') + str(dt.day) + dt.strftime(', %Y'),
               question=ci['question'], oyez_url=f"https://www.oyez.org/cases/{slate['term']}/{d}",
               advocates=advs, sections=[], glasses={},
               web=dict(title=c.get('title') or ci['name'],
                        dek=c.get('dek', ''), storage_key='pos-' + d,
                        stand_in_note=stand_in_note(advs),
                        end_puppets='Procedural 3D caricatures of the justices' + ('' if len(real) == len(advs) else '; the lawyers are stand-ins, not likenesses'
                                     if not real else '; most of the lawyers are stand-ins, not likenesses')))
    json.dump(cfg, open(os.path.join(root, 'cases', d, 'cfg.json'), 'w'), indent=1, ensure_ascii=False)
    if o and o.get('confidence', 'confirmed') == 'confirmed':
        out = dict(outcome=o['outcome'], decided=o.get('decided'), source=(o.get('sources') or [''])[0])
        json.dump(out, open(os.path.join(root, 'cases', d, 'outcome.json'), 'w'), indent=1, ensure_ascii=False)

print(f"{len(registry)} advocates; {len(slate['cases'])} cases")
for k, r in registry.items():
    print(f"  {k:14s} {r['display']:26s} {r['caption_label']:20s} {r['spec']['skin']}  {r['spec']['hair']['style']:9s} {list(r['cases'])}")
