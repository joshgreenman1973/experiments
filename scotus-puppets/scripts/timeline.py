# Build the per-frame performance + edit decision list from the Oyez transcript and the argument audio.
# Usage: python timeline.py TRANSCRIPT.json AUDIO.mp3 OUT.npz OUT.json
import sys, json, subprocess, math, re
import numpy as np
from scipy.signal import butter, sosfiltfilt
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from characters import CHARS, BENCH_ORDER, ADVOCATES, CASE

FPS = 24
SR = 16000
LEAD = 0.045  # mouth shapes lead the audio slightly (reads as in-sync)

tr_path, audio_path, out_npz, out_json = sys.argv[1:5]
d = json.load(open(tr_path))
secs = d['transcript']['sections']
name2key = {v['oyez']: k for k, v in CHARS.items()}
KEYS = BENCH_ORDER + ADVOCATES
KIDX = {k: i for i, k in enumerate(KEYS)}

# ---------------------------------------------------------------- audio envelope
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', audio_path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                     capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
dur = len(x) / SR
sos = butter(4, [180, 3400], btype='band', fs=SR, output='sos')
xb = sosfiltfilt(sos, x)
nF = int(math.floor(dur * FPS))
win = int(0.035 * SR)
c = np.cumsum(np.r_[0, xb ** 2])
centers = ((np.arange(nF) / FPS + LEAD) * SR).astype(int)
lo = np.clip(centers - win // 2, 0, len(xb)); hi = np.clip(centers + win // 2, 0, len(xb))
rms = np.sqrt((c[hi] - c[lo]) / np.maximum(hi - lo, 1))
db = 20 * np.log10(rms + 1e-7)

# ---------------------------------------------------------------- turns
turns = []
for si, s in enumerate(secs):
    for t in s['turns']:
        k = name2key.get((t.get('speaker') or {}).get('name'))
        turns.append(dict(sec=si, start=t['start'], stop=t['stop'], who=k, blocks=t['text_blocks']))
section_adv = []
for si, s in enumerate(secs):
    tot = {}
    for t in turns:
        if t['sec'] == si and t['who'] in ADVOCATES:
            tot[t['who']] = tot.get(t['who'], 0) + t['stop'] - t['start']
    section_adv.append((s['start'], max(tot, key=tot.get)))

speaker = np.full(nF, -1, dtype=np.int16)
mouth = np.zeros(nF, dtype=np.int8)
openv = np.zeros(nF, dtype=np.float32)
for t in turns:
    f0, f1 = int(t['start'] * FPS), min(nF, int(math.ceil(t['stop'] * FPS)))
    if t['who'] is None or f1 <= f0:
        continue
    speaker[f0:f1] = KIDX[t['who']]
    seg = db[f0:f1]
    floor = np.percentile(seg, 12)
    peak = np.percentile(seg, 97)
    o = np.clip((seg - floor - 5.0) / max(8.0, peak - floor - 5.0), 0, 1) ** 0.85
    sm = np.zeros_like(o)
    prev = 0.0
    for i, v in enumerate(o):  # fast attack, quick-but-not-instant release
        prev = v if v > prev else max(v, prev * 0.5)
        sm[i] = prev
    openv[f0:f1] = sm
    mouth[f0:f1] = np.clip(np.floor(sm * 4.6), 0, 4).astype(np.int8)

# ---------------------------------------------------------------- head motion (per character, per frame)
rng = np.random.default_rng(11)
tt = np.arange(nF) / FPS
nK = len(KEYS)
tilt = np.zeros((nK, nF), np.float32)   # degrees
bob = np.zeros((nK, nF), np.float32)    # fraction of head height (positive = up)
sway = np.zeros((nK, nF), np.float32)   # fraction of head height (positive = right)


def lp(sig, sec):
    a = math.exp(-1.0 / (sec * FPS))
    out = np.empty_like(sig); acc = 0.0
    for i, v in enumerate(sig):
        acc = a * acc + (1 - a) * v; out[i] = acc
    return out


for k in range(nK):
    ph = rng.random(6) * 6.28
    speaking = (speaker == k).astype(np.float32)
    act = lp(speaking, 0.6)
    o = np.where(speaker == k, openv, 0)
    o_lp = lp(o, 0.25)
    idle = 0.7 * np.sin(2 * np.pi * 0.07 * tt + ph[0]) + 0.5 * np.sin(2 * np.pi * 0.13 * tt + ph[1])
    talk = 1.6 * np.sin(2 * np.pi * 0.31 * tt + ph[2]) + 1.0 * np.sin(2 * np.pi * 0.67 * tt + ph[3])
    tilt[k] = idle + act * talk + act * 3.0 * (o_lp - 0.3)
    bob[k] = 0.012 * np.sin(2 * np.pi * 0.21 * tt + ph[4]) + 0.06 * o * speaking + act * 0.02 * o_lp
    sway[k] = 0.01 * np.sin(2 * np.pi * 0.09 * tt + ph[5]) + act * 0.025 * np.sin(2 * np.pi * 0.27 * tt + ph[2])
    # listeners: occasional slow nods
    for t0 in np.sort(rng.uniform(0, dur, int(dur / 40))):
        m = (tt > t0) & (tt < t0 + 1.2)
        bob[k][m] -= 0.02 * np.sin(np.pi * (tt[m] - t0) / 1.2) * (1 - speaking[m])

# ---------------------------------------------------------------- edit decision list
LEFT = BENCH_ORDER[:5]
RIGHT = BENCH_ORDER[4:]


def half_for(who):
    i = BENCH_ORDER.index(who)
    return 'bench_left' if i < 4 else ('bench_right' if i > 4 else 'bench_center')


def adv_at(tsec):
    a = section_adv[0][1]
    for st, k in section_adv:
        if tsec >= st - 0.01:
            a = k
    return a


shots = []  # (start, end, shot)


def add(s, e, shot):
    if e - s <= 0:
        return
    shots.append([s, e, shot])


cut_cycle = ['wide', 'bench_left', 'bench_right', 'wide', 'bench_right', 'bench_left']
cc = 0
for i, t in enumerate(turns):
    s, e, who = t['start'], t['stop'], t['who']
    if i == 0:
        add(0, e, 'wide'); continue
    if who in ADVOCATES:
        cur = s
        first = rng.uniform(7.5, 11.0)
        while e - cur > first + 9.0:
            add(cur, cur + first, who)
            cut = cut_cycle[cc % len(cut_cycle)]; cc += 1
            cl = rng.uniform(3.5, 6.0)
            add(cur + first, cur + first + cl, cut)
            cur += first + cl
            first = rng.uniform(10.0, 19.0)
        add(cur, e, who)
    elif who in BENCH_ORDER:
        if e - s >= 2.2:
            if e - s > 16:
                m = s + (e - s) * 0.45
                add(s, m, who); add(m, m + 3.0, adv_at(m)); add(m + 3.0, e, who)
            else:
                add(s, e, who)
        else:
            add(s, e, half_for(who))
    else:
        add(s, e, 'wide')
# last shot runs to the end of the audio, then an end card is appended by the compositor
shots[-1][1] = dur

# merge identical neighbours and swallow very short shots
merged = []
for sh in shots:
    if merged and merged[-1][2] == sh[2]:
        merged[-1][1] = sh[1]
    elif merged and sh[1] - sh[0] < 1.0:
        merged[-1][1] = sh[1]
    else:
        merged.append(list(sh))
shots = merged
shot_names = sorted(set(s[2] for s in shots))
shot_f = np.zeros(nF, dtype=np.int16)
for s, e, nm in shots:
    shot_f[int(s * FPS):int(math.ceil(e * FPS))] = shot_names.index(nm)
adv_f = np.array([KIDX[adv_at(t)] for t in tt[::FPS]], dtype=np.int16).repeat(FPS)[:nF]
if len(adv_f) < nF:
    adv_f = np.r_[adv_f, np.full(nF - len(adv_f), adv_f[-1])]

# ---------------------------------------------------------------- captions
LABEL = {'roberts': 'CHIEF JUSTICE ROBERTS'}
for k, a in CASE['advocates'].items():
    LABEL[k] = a.get('caption_label') or a['display'].upper()
for k in BENCH_ORDER:
    if k not in LABEL:
        LABEL[k] = 'JUSTICE ' + CHARS[k]['display'].split()[-1].upper().replace(',', '')
LABEL['alito'] = 'JUSTICE ALITO'


def chunk_text(text, maxc=96):
    words = text.split()
    out, cur = [], ''
    for w in words:
        if len(cur) + len(w) + 1 > maxc and cur:
            out.append(cur); cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        out.append(cur)
    # avoid a tiny orphan chunk
    if len(out) > 1 and len(out[-1]) < 25:
        last = out.pop()
        out[-1] = out[-1] + ' ' + last
    return out


caps = []
for t in turns:
    for b in t['blocks']:
        txt = re.sub(r'\s+', ' ', b['text']).strip()
        if not txt:
            continue
        parts = chunk_text(txt)
        tot = sum(len(p) for p in parts)
        cur = b['start']
        for p in parts:
            dd = (b['stop'] - b['start']) * len(p) / tot
            caps.append(dict(start=round(cur, 3), end=round(cur + dd, 3), who=t['who'], label=LABEL.get(t['who'], ''),
                             text=p))
            cur += dd

np.savez_compressed(out_npz, speaker=speaker, mouth=mouth, openv=openv, tilt=tilt, bob=bob, sway=sway,
                    shot=shot_f, adv=adv_f)
json.dump(dict(fps=FPS, nframes=nF, duration=dur, keys=KEYS, shot_names=shot_names, shots=shots, captions=caps,
               sections=section_adv, labels=LABEL), open(out_json, 'w'), indent=0)
from collections import Counter
cnt = Counter()
for s, e, nm in shots:
    cnt[nm] += e - s
print('frames', nF, 'shots', len(shots), 'captions', len(caps))
print({k: round(v / 60, 1) for k, v in cnt.most_common()})
print('mouth hist', np.bincount(mouth[speaker >= 0], minlength=5) / (speaker >= 0).sum())
