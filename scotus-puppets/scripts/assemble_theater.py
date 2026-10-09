# Fold a slate's case pages into one "screening room" page: one player, a grid of cases with screenshots.
# Usage: python assemble_theater.py SLATE.json WORKROOT OUTDIR [--kbps 16] [--seg 1800] [--mp3]
#   Reads WORKROOT/cases/<docket>/{page/data.json,page/layout.json,page/img,audio.mp3,tl_web.json,outcome.json}
#   and WORKROOT/thumbs/<docket>.jpg. Images shared between cases (the justices) are stored once.
#   Audio is re-encoded small (AAC, ~16 kbps speech) so every argument fits under the 256 MB page limit;
#   --mp3 makes MP3 segments instead (for testing in browsers without AAC).
import argparse, datetime, hashlib, html, json, os, re, shutil, subprocess

ap = argparse.ArgumentParser()
ap.add_argument('slate'); ap.add_argument('work'); ap.add_argument('out')
ap.add_argument('--kbps', type=int, default=16); ap.add_argument('--seg', type=float, default=1800); ap.add_argument('--mp3', action='store_true')
a = ap.parse_args()
slate = json.load(open(a.slate))
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(a.out, 'img'), exist_ok=True)
os.makedirs(os.path.join(a.out, 'thumbs'), exist_ok=True)
stored = {}


def store(src):
    h = hashlib.sha1(open(src, 'rb').read()).hexdigest()[:14]
    rel = f'img/{h}{os.path.splitext(src)[1]}'
    if rel not in stored:
        shutil.copyfile(src, os.path.join(a.out, rel))
        stored[rel] = os.path.getsize(src)
    return rel


def fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime('%B ') + str(d.day) + d.strftime(', %Y')


cases, total_audio = [], 0
for c in slate['cases']:
    d = c['docket']
    C = os.path.join(a.work, 'cases', d)
    page = os.path.join(C, 'page')
    data = json.load(open(os.path.join(page, 'data.json')))
    lay = json.load(open(os.path.join(page, 'layout.json')))
    for v in lay['vcams'].values():
        v['base'] = store(os.path.join(page, v['base']))
        v['atlas'] = store(os.path.join(page, v['atlas']))
    # audio: fewer, longer pieces cut at the quiet points the timeline already found
    tl = json.load(open(os.path.join(C, 'tl_web.json')))
    dur = tl['duration']
    cuts, target = [], a.seg
    while target < dur - a.seg * 0.4:
        best = min(tl['cuts'], key=lambda x: abs(x - target)) if tl['cuts'] else target
        if not cuts or best > cuts[-1] + 60:
            cuts.append(best)
        target += a.seg
    bounds = [0.0] + cuts + [None]
    cdir = os.path.join(a.out, 'c', d)
    os.makedirs(cdir, exist_ok=True)
    segs = []
    for i in range(len(bounds) - 1):
        ext = 'mp3' if a.mp3 else 'm4a'
        rel = f'c/{d}/a{i:02d}.{ext}'
        span = ['-t', str(bounds[i + 1] - bounds[i])] if bounds[i + 1] else []
        codec = ['-c:a', 'libmp3lame', '-b:a', '24k', '-ar', '16000'] if a.mp3 else \
                ['-c:a', 'aac', '-b:a', f'{a.kbps}k', '-ar', '16000', '-movflags', '+faststart']
        dst = os.path.join(a.out, rel)
        if not os.path.exists(dst):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(bounds[i]), '-i', os.path.join(C, 'audio.mp3')] + span +
                           ['-vn', '-ac', '1'] + codec + [dst], check=True)
        sd = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', dst],
                                  capture_output=True, text=True, check=True).stdout)
        segs.append([rel, round(bounds[i], 3), round(sd, 3)])
        total_audio += os.path.getsize(dst)
    data['segments'] = segs
    json.dump(data, open(os.path.join(cdir, 'data.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    json.dump(lay, open(os.path.join(cdir, 'layout.json'), 'w'), separators=(',', ':'))
    thumb = os.path.join(a.work, 'thumbs', f'{d}.jpg')
    if os.path.exists(thumb):
        shutil.copyfile(thumb, os.path.join(a.out, 'thumbs', f'{d}.jpg'))
    o = json.load(open(os.path.join(C, 'outcome.json'))) if os.path.exists(os.path.join(C, 'outcome.json')) else {}
    P = data['page']
    cases.append(dict(docket=d, name=c['name'], topic=c['topic'], argued=P['argued'], argued_short=P['argued'].replace(', 20', ', 20'),
                      length=segs[-1][1] + segs[-1][2], vote=o.get('vote', ''),
                      outcome_short=((('Decided ' + fmt_date(o['decided']) + '. ') if o.get('decided') else '') + o.get('outcome', '')),
                      thumb=f'thumbs/{d}.jpg', data=f'c/{d}/data.json', layout=f'c/{d}/layout.json'))

E = lambda s: html.escape(str(s), quote=True)
total_len = sum(c['length'] for c in cases)
extra = slate.get('extra', [])
notes_html = ('<p><strong>How these are made.</strong> The audio is the Court\'s own recording of each argument, unedited, via Oyez, whose '
              'transcripts mark who is speaking when. The justices are 3D caricatures; the lawyers are stand-in puppets in felt colors, '
              'not likenesses. Mouths move with the loudness of each speaker\'s syllables. Audio here is compressed to fit all '
              f'{len(cases)} arguments on one page.</p>'
              '<p><strong>From the decision.</strong> During each argument, notes quote the Court\'s slip opinion (majority, '
              'concurrences and dissents) at the moment a justice asks about the issue the passage addresses. Every quotation was '
              'checked word for word against the opinion text.</p>'
              + ''.join(f'<p><strong>Also:</strong> <a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a>. {E(n)}</p>' for t, u, n in extra) +
              '<p>Audio and transcript timing from <a href="https://www.oyez.org" target="_blank" rel="noopener">Oyez</a>, licensed CC BY-NC 4.0. '
              'Opinions: Supreme Court of the United States, via CourtListener. Made by Josh Greenman with Claude.</p>')
hours = int(total_len // 3600)
catalog = dict(title=slate.get('index_title', slate['label'] + ' in Puppets'),
               eyebrow=f"Supreme Court of the United States · {slate['label']}",
               dek=f"{len(cases)} of the term's biggest arguments, complete and unedited ({hours} hours in all), performed by puppets of the "
                   "justices over the Court's own audio, with what the decision said layered in.",
               gridnote='Pick an argument to play it above.', notes_html=notes_html, cases=cases)
json.dump(catalog, open(os.path.join(a.out, 'catalog.json'), 'w'), ensure_ascii=False)
tpl = open(os.path.join(here, '..', 'web', 'player.html')).read()
for k, v in {'__TITLE__': catalog['title'], '__EYEBROW__': catalog['eyebrow'], '__CASE_NAME__': catalog['title'], '__DEK__': catalog['dek']}.items():
    tpl = tpl.replace(k, html.escape(v, quote=False))
open(os.path.join(a.out, 'index.html'), 'w').write(tpl)
size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(a.out) for f in fs)
nfiles = sum(len(fs) for _, fs in [(dp, fs) for dp, _, fs in os.walk(a.out)])
print(f'{len(cases)} cases, {nfiles} files, {size / 1e6:.0f} MB (audio {total_audio / 1e6:.0f} MB, images {sum(stored.values()) / 1e6:.1f} MB in {len(stored)} files)')
