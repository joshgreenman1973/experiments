# Assemble a browser-player page for one argument: audio cut at silences, page data, index.html.
# Expects OUTDIR to already hold layout.json + img/ from export_web.py.
# Usage: python build_page.py CASE_CFG.json TRANSCRIPT.json AUDIO.mp3 TIMELINE_WEB.json OUTDIR [--outcome OUTCOME.json]
import argparse, html, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))

ap = argparse.ArgumentParser()
ap.add_argument('cfg'); ap.add_argument('transcript'); ap.add_argument('audio'); ap.add_argument('tlweb'); ap.add_argument('out')
ap.add_argument('--outcome', help='JSON with outcome, decided (YYYY-MM-DD), source')
ap.add_argument('--notes', help='verified decision notes from verify_notes.py')
ap.add_argument('--credit', default='Made by Josh Greenman with Claude.')
a = ap.parse_args()
os.environ['SCOTUS_CASE'] = os.path.abspath(a.cfg)
from characters import CHARS, BENCH_ORDER, ADVOCATES

cfg = json.load(open(a.cfg))
tr = json.load(open(a.transcript))
tl = json.load(open(a.tlweb))
web = cfg.get('web', {})
os.makedirs(os.path.join(a.out, 'audio'), exist_ok=True)


def fmt(sec):
    sec = int(sec)
    h, m, x = sec // 3600, sec // 60 % 60, sec % 60
    return f'{h}:{m:02d}:{x:02d}' if h else f'{m}:{x:02d}'


# ---------------------------------------------------------------- audio segments (stream copy, cut in silences)
bounds = [0.0] + tl['cuts'] + [None]
segments = []
for i in range(len(bounds) - 1):
    p = f'audio/s{i:02d}.mp3'
    span = ['-t', str(bounds[i + 1] - bounds[i])] if bounds[i + 1] else []
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(bounds[i]), '-i', a.audio] + span +
                   ['-c', 'copy', '-map', '0:a', os.path.join(a.out, p)], check=True)
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                              os.path.join(a.out, p)], capture_output=True, text=True, check=True).stdout)
    segments.append([p, round(bounds[i], 3), round(d, 3)])

# ---------------------------------------------------------------- who spoke
turns = [t for s in tr['transcript']['sections'] for t in s['turns'] if t.get('speaker')]
name2key = {v['oyez']: k for k, v in CHARS.items()}
stats = {}
for t in turns:
    k = name2key.get(t['speaker']['name'])
    if not k:
        continue
    s = stats.setdefault(k, dict(first=t['start'], secs=0.0))
    s['secs'] += t['stop'] - t['start']


def label(k):
    if k in ADVOCATES:
        return CHARS[k]['display']
    last = CHARS[k]['oyez'].replace(', Jr.', '').split()[-1]
    return ('Chief Justice ' if k == 'roberts' else 'Justice ') + last


mic = [[label(k), round(s['secs'] / 60, 1), round(s['first'], 1)] + ([True] if k in ADVOCATES else [])
       for k, s in sorted(stats.items(), key=lambda kv: -kv[1]['secs'])]

# ---------------------------------------------------------------- chapters and section cards
def role_short(r):
    return re.split(r',\s*supporting', r or '', maxsplit=1)[0].strip()


cards, chapters, seen = [], [[round(turns[0]['start'], 1), 'The Chief Justice calls the case']], set()
for i, (st, k) in enumerate(tl['sections']):
    rb = k in seen
    seen.add(k)
    role = role_short(CHARS[k].get('role', ''))
    if cfg.get('sections') and i < len(cfg['sections']):
        cards.append([8.0 if i == 0 else st + 0.5, cfg['sections'][i]['title'], cfg['sections'][i].get('sub', '')])
    else:
        cards.append([8.0 if i == 0 else st + 0.5, ('REBUTTAL' if rb else 'ARGUMENT') + (' ' + role.upper() if role and not rb else ''),
                      CHARS[k]['display']])
    first = next((t['start'] for t in turns if t['start'] >= st - 0.01 and name2key.get(t['speaker']['name']) == k), st)
    chapters.append([round(first, 1), ('Rebuttal: ' if rb else 'Argument ' + (role + ': ' if role else 'of ')) + CHARS[k]['display']])
last = turns[-1]
if 'submitted' in ' '.join(b['text'] for b in last['text_blocks']).lower():
    chapters.append([round(last['start'], 1), '“The case is submitted.”'])
if web.get('chapters'):
    chapters = web['chapters']

tags = {}
for k in BENCH_ORDER:
    nm = CHARS[k]['display'].replace('Chief Justice ', '').replace('Justice ', '')
    tags[k] = [nm, 'Chief Justice of the United States' if k == 'roberts' else 'Associate Justice']
for k in ADVOCATES:
    r = CHARS[k].get('role', '')
    tags[k] = [CHARS[k]['display'], r[:1].upper() + r[1:]]

outcome = json.load(open(a.outcome)) if a.outcome else {}
decided = outcome.get('decided') or ''
if re.match(r'\d{4}-\d{2}-\d{2}$', decided):
    import datetime
    dt = datetime.date.fromisoformat(decided)
    decided = dt.strftime('%B ') + str(dt.day) + dt.strftime(', %Y')
page = dict(
    case_name=cfg['case_name'], docket=cfg['docket'], argued=cfg['argued'], decided=decided or cfg.get('decided', '').replace('Decided ', ''),
    bug=f"{cfg['short_name']}  ·  No. {cfg['docket']}  ·  ARGUED {cfg['argued_short']}",
    question=cfg.get('question', ''), outcome=outcome.get('outcome') or cfg.get('outcome', ''), outcome_src=outcome.get('source', ''),
    stand_in_note=web.get('stand_in_note', ''), end_puppets=web.get('end_puppets', ''), oyez_url=cfg.get('oyez_url', 'https://www.oyez.org'),
    credit=a.credit, storage_key=web.get('storage_key', 'pos-' + cfg['docket']),
    bench=BENCH_ORDER, advocates=ADVOCATES, chapters=chapters, cards=cards, tags=tags, mic=mic,
    notes=json.load(open(a.notes))['notes'] if a.notes else [])
# Supreme Court pages turn on the player's optional motion (listeners, breathing, blinks, camera drift, gallery, mouse, live clock);
# each only does anything where the layout holds its sprites. clock_start: seconds after midnight when the argument began.
page['motion'] = dict(listeners=True, breathe=True, blink=True, drift=True, gallery=True, mouse=True, clock=True)
page['clock_start'] = web.get('clock_start', 36000)
json.dump(dict(page=page, tl=tl, segments=segments), open(os.path.join(a.out, 'data.json'), 'w'), separators=(',', ':'),
          ensure_ascii=False)

tpl = open(os.path.join(os.path.dirname(__file__), '..', 'web', 'player.html')).read()
total = segments[-1][1] + segments[-1][2]
for k, v in {'__TITLE__': web.get('title') or cfg['case_name'],
             '__EYEBROW__': f"Supreme Court of the United States · No. {cfg['docket']} · Argued {cfg['argued']}",
             '__CASE_NAME__': cfg['case_name'],
             '__DEK__': web.get('dek') or f"The complete oral argument, {fmt(total)} long, performed by puppets. Every word is the Court's own recording."}.items():
    tpl = tpl.replace(k, html.escape(v, quote=False))
open(os.path.join(a.out, 'index.html'), 'w').write(tpl)
size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(a.out) for f in fs)
nfiles = sum(len(fs) for _, _, fs in os.walk(a.out))
print(f"{a.out}: {len(segments)} audio segments, {fmt(total)}, {nfiles} files, {size / 1e6:.1f} MB")
