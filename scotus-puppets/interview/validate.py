# Sanity checks on W/page/data.json and the player script.
import base64, json, os, re, subprocess, sys
W = os.environ.get('W') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'interview')
d = json.load(open(f'{W}/page/data.json'))
P, tl, segs = d['page'], d['tl'], d['segments']
ok = True
def check(c, msg):
    global ok
    print(('ok   ' if c else 'FAIL ') + msg); ok &= bool(c)
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{W}/audio_edit.mp3'], capture_output=True, text=True).stdout)
total = segs[-1][1] + segs[-1][2]
check(abs(tl['duration'] - total) < 0.15 and abs(dur - total) < 0.15, f"duration {tl['duration']} vs segments {total:.3f} vs audio_edit.mp3 {dur:.3f}")
check(tl['nframes'] == int(tl['duration'] * tl['fps']) or abs(tl['nframes'] - tl['duration'] * tl['fps']) < 2, f"nframes {tl['nframes']}")
check(len(base64.b64decode(tl['openv'])) == tl['nframes'], 'openv length == nframes')
check(tl['keys'] == ['smith', 'gelinas', 'greenman', 'lawler', 'katz', 'zagare', 'facciola'], 'keys in seating order')
check(set(tl['labels']) == set(tl['keys']), 'labels for every key')
t = tl['turns']
check(all(a < b for a, b, _ in t) and all(t[i][1] <= t[i + 1][0] + 1e-9 for i in range(len(t) - 1)), f'{len(t)} turns: positive length, no overlap')
check(0 <= t[0][0] < 1 and t[-1][1] <= tl['duration'] + 1e-6, f"turns span {t[0][0]}..{t[-1][1]}")
c = tl['captions']
check(all(a < b for a, b, _, _ in c) and all(c[i][0] <= c[i + 1][0] and c[i][1] <= c[i + 1][0] + 1e-9 for i in range(len(c) - 1)), f'{len(c)} captions in order, no overlap')
check(all(len(x[3]) > 0 for x in c) and max(len(x[3]) for x in c) <= 115, f"caption lengths max {max(len(x[3]) for x in c)}")
s = tl['shots']
check(s[0][0] == 0 and abs(s[-1][1] - tl['duration']) < 1e-6 and all(abs(s[i][1] - s[i + 1][0]) < 1e-6 for i in range(len(s) - 1)), f'{len(s)} shots contiguous')
check(min(b - a for a, b, _ in s) >= 1.2 - 1e-6, f'min shot {min(b - a for a, b, _ in s):.2f}s')
cams = {x[2] for x in s}
check(cams <= set(tl['keys']) | {'wide', 'bench_left', 'bench_right', 'bench_center'}, f'shot names {sorted(cams)}')
check(all(segs[i][0].startswith('audio/') and os.path.exists(f"{W}/page/{segs[i][0]}") for i in range(len(segs))) and all(abs(segs[i][1] + segs[i][2] - segs[i + 1][1]) < 0.1 for i in range(len(segs) - 1)), f'{len(segs)} audio segments contiguous')
check(tl['cuts'] == [x[1] for x in segs[1:]], 'cuts == segment starts')
check(P['bench'] == tl['keys'] and P['advocates'] == [] and set(P['tags']) == set(tl['keys']), 'bench/advocates/tags')
ch = P['chapters']
check(len(ch) >= 15 and all(ch[i][0] < ch[i + 1][0] for i in range(len(ch) - 1)) and ch[-1][0] < total, f'{len(ch)} chapters')
check(abs(sum(m[1] for m in P['mic']) * 60 - sum(b - a for a, b, _ in t)) < 25, 'mic minutes add up to turn time')
# the player script must parse
html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web', 'player.html'), encoding='utf-8').read()
js = re.search(r'<script>(.*)</script>', html, re.S).group(1)
open(f'{W}/tmp/player_script.js', 'w').write(js)
r = subprocess.run(['node', '--check', f'{W}/tmp/player_script.js'], capture_output=True, text=True)
check(r.returncode == 0, 'node --check player.html script ' + r.stderr[:300])
if os.path.exists(f'{W}/page/index.html'):
    h = open(f'{W}/page/index.html', encoding='utf-8').read()
    js2 = re.search(r'<script>(.*)</script>', h, re.S).group(1)
    open(f'{W}/tmp/index_script.js', 'w').write(js2)
    check(subprocess.run(['node', '--check', f'{W}/tmp/index_script.js']).returncode == 0, 'node --check page/index.html script')
    check(not re.search(r'__[A-Z_]+__', h), 'no unsubstituted __PLACEHOLDER__')
print('ALL OK' if ok else 'PROBLEMS')
sys.exit(0 if ok else 1)
