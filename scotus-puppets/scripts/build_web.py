# Fill web/template.html into a page that streams the video as consecutive MP4 pieces.
# Usage: python build_web.py CASE.json TRANSCRIPT.json WEBDIR   (WEBDIR holds v/p00.mp4 ... and poster.jpg)
import glob, json, os, subprocess, sys

case_path, tr_path, webdir = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
case = json.load(open(case_path))
tr = json.load(open(tr_path))
web = case.get('web', {})

parts = []
for p in sorted(glob.glob(os.path.join(webdir, 'v', 'p*.mp4'))):
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                             capture_output=True, text=True, check=True).stdout)
    parts.append(['v/' + os.path.basename(p), round(d, 3)])
total = sum(d for _, d in parts)

turns = [t for s in tr['transcript']['sections'] for t in s['turns'] if t.get('speaker')]
adv_by_oyez = {a['oyez']: a for a in case['advocates'].values()}
stats = {}
for t in turns:
    n = t['speaker']['name']
    s = stats.setdefault(n, dict(first=t['start'], secs=0.0, last=t['speaker'].get('last_name') or n.split()[-1]))
    s['secs'] += t['stop'] - t['start']
mic = []
for n, s in sorted(stats.items(), key=lambda kv: -kv[1]['secs']):
    if n in adv_by_oyez:
        mic.append([adv_by_oyez[n]['display'], round(s['secs'] / 60, 1), round(s['first'], 1), True])
    else:
        label = 'Chief Justice ' + s['last'] if 'Roberts' in n else 'Justice ' + s['last']
        mic.append([label, round(s['secs'] / 60, 1), round(s['first'], 1)])

chapters = web.get('chapters')
if not chapters:  # fall back to section starts
    chapters = [[round(sec['start'], 1), (case.get('sections') or [{}] * 9)[i].get('title', f'Section {i + 1}').title()]
                for i, sec in enumerate(tr['transcript']['sections'])]


def fmt(sec):
    sec = int(sec)
    h, m, x = sec // 3600, sec // 60 % 60, sec % 60
    return f'{h}:{m:02d}:{x:02d}' if h else f'{m}:{x:02d}'


page = open(os.path.join(here, '..', 'web', 'template.html')).read()
outcome = case.get('outcome', '')
repl = {
    '__TITLE__': web.get('title') or case['case_name'],
    '__DOCKET__': case['docket'],
    '__ARGUED__': case['argued'],
    '__CASE_NAME__': case['case_name'],
    '__DEK__': web.get('dek', 'The complete oral argument, performed by puppets. Every word is the Court’s own recording.'),
    '__TOTAL__': fmt(total),
    '__TOTAL_S__': f'{total:.1f}',
    '__STAND_IN__': web.get('stand_in_note', ''),
    '__OUTCOME_P__': f'<p><strong>How it came out.</strong> {outcome}</p>' if outcome else '',
    '__OYEZ_URL__': case.get('oyez_url', 'https://www.oyez.org'),
    '__STORAGE_KEY__': web.get('storage_key', case['docket'] + '-pos'),
    '__PARTS__': json.dumps(parts),
    '__CHAPTERS__': json.dumps(chapters, ensure_ascii=False),
    '__MIC__': json.dumps(mic, ensure_ascii=False),
}
for k, v in repl.items():
    page = page.replace(k, v)
out = os.path.join(webdir, 'index.html')
open(out, 'w').write(page)
print(f'{out}: {len(parts)} parts, {fmt(total)}, {sum(os.path.getsize(os.path.join(webdir, p)) for p, _ in parts) / 1e6:.0f} MB')
