# Build the edited audio, cut list, player timeline and page data for the Lawler breakfast interview.
#   python build.py [--table]      (--table: print turn times only and stop)
# Inputs : W/tmp/align_raw.json (from align.py), W/audio.mp3, W/whisper.json, W/transcript.txt, W/chapters.json
# Outputs: W/audio_edit.mp3, W/cuts.json, W/cuts_report.md, W/tl_web.json, W/page_data.json, W/alignment.json,
#          W/page/data.json, W/page/audio/sNN.mp3   (+ W/page/index.html via finish_page.py when layout.json exists)
import base64, json, math, os, random, re, subprocess, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt

W = os.environ.get('W') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'interview')
SR, FPS, LEAD = 16000, 24, 0.045
MIN_CUT = float(os.environ.get('MIN_CUT', 10.0))   # unpublished speech at least this long is removed
SPLICE = 0.4                                        # pause left at each splice, seconds
XF = int(0.012 * SR)                                # 12 ms crossfade at every splice
KEYS = ['smith', 'gelinas', 'greenman', 'lawler', 'katz', 'zagare', 'facciola']   # seating, left to right
KIDX = {k: i for i, k in enumerate(KEYS)}
LABEL = {'lawler': 'REP. LAWLER', 'smith': 'BEN SMITH', 'gelinas': 'NICOLE GELINAS', 'greenman': 'JOSH GREENMAN',
         'katz': 'ALYSSA KATZ', 'zagare': 'LIENA ŽAGARE', 'facciola': 'TIMMY FACCIOLA'}
DISPLAY = {'lawler': 'Mike Lawler', 'smith': 'Ben Smith', 'gelinas': 'Nicole Gelinas', 'greenman': 'Josh Greenman',
           'katz': 'Alyssa Katz', 'zagare': 'Liena Žagare', 'facciola': 'Timmy Facciola'}
JOURNALISTS = [k for k in KEYS if k != 'lawler']

R = json.load(open(f'{W}/tmp/align_raw.json'))
turns, tw, ww = R['turns'], R['twords'], R['wwords']
match = {int(k): v for k, v in R['match'].items()}
fuzzy = set(R['fuzzy'])
n = len(tw)
if not os.path.exists(f'{W}/tmp/audio_f32.npy'):      # decode once: original audio, 16 kHz mono float
    os.makedirs(f'{W}/tmp', exist_ok=True)
    np.save(f'{W}/tmp/audio_f32.npy', np.frombuffer(subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', f'{W}/audio.mp3', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
        capture_output=True, check=True).stdout, dtype=np.float32))
x = np.load(f'{W}/tmp/audio_f32.npy')                  # original audio, 16 kHz mono float


def tfmt(t):
    t = max(0, t); return f'{int(t // 60)}:{t % 60:05.2f}'


# ====================================================================== 1. word times in the original recording
ts, te = [None] * n, [None] * n
for a, b in match.items():
    ts[a] = ww[b]['s']
    te[a] = min(ww[b]['e'], ww[b]['s'] + max(0.3, 0.09 * len(ww[b]['n']) + 0.2))   # Whisper stretches words into pauses
i = 0
while i < n:                                            # interpolate unmatched transcript words between matched neighbours
    if ts[i] is None:
        j = i
        while j < n and ts[j] is None:
            j += 1
        L = te[i - 1] if i > 0 else ww[0]['s']
        Rt = max(ts[j] if j < n else ww[-1]['e'], L)
        wts = [len(tw[k]['n']) + 1 for k in range(i, j)]
        c = L
        for k, wt in zip(range(i, j), wts):
            d = (Rt - L) * wt / sum(wts)
            ts[k], te[k] = c, c + d
            c += d
        i = j
    else:
        i += 1
for k in range(1, n):
    ts[k] = max(ts[k], ts[k - 1]); te[k] = max(te[k], ts[k])

# raw (display) words per paragraph, with times
tok_of = {}
for k, t in enumerate(tw):
    tok_of.setdefault((t['turn'], t['para'], t['w']), []).append(k)
RAW = []       # per turn: list of paragraphs: list of dict(text, o0, o1)
for ti, t in enumerate(turns):
    paras = []
    for pi, p in enumerate(t['paras']):
        ws = []
        for wi, raw in enumerate(p.split()):
            ks = tok_of.get((ti, pi, wi))
            ws.append(dict(text=raw, o0=ts[ks[0]] if ks else None, o1=te[ks[-1]] if ks else None, tok=ks[0] if ks else None))
        prev = None
        for w in ws:
            if w['o0'] is None:
                w['o0'] = w['o1'] = prev if prev is not None else (RAW[-1][-1][-1]['o1'] if RAW else 0.0)
            prev = w['o1']
        paras.append(ws)
    RAW.append(paras)

# ====================================================================== 2. unpublished stretches and splice points
sm_win = int(0.02 * SR)
_c = np.cumsum(np.r_[0, x.astype(np.float64) ** 2])


def dbat(t, half=0.01):
    lo, hi = max(0, int((t - half) * SR)), min(len(x), int((t + half) * SR))
    return 10 * math.log10((_c[hi] - _c[lo]) / max(hi - lo, 1) + 1e-12)


def quietest(lo, hi, step=0.004):
    ts_ = np.arange(lo, hi + 1e-9, step)
    return float(ts_[int(np.argmin([dbat(t) for t in ts_]))])


def window_text(o0, o1, maxw=25):
    return ' '.join(w['raw'] for w in ww if o0 <= w['s'] < o1 and w['raw'])


matched_b = {b for b in match.values()}
first_a = min(match); last_a = max(match)
first_s = ts[first_a]; last_e = te[last_a]
cutlist = []     # dicts: kind, o0, o1 (original seconds of the REMOVED stretch), a_pt/b_pt = splice points (kept side)
# head: everything before the first published word
b_head = quietest(first_s - 0.06, first_s + 0.10)
cutlist.append(dict(kind='head', o0=0.0, o1=b_head))
# interior stretches of unpublished speech
pairs = sorted(match.items())
for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
    g0, g1 = ww[b0]['e'], ww[b1]['s']
    if g1 - g0 < MIN_CUT:
        continue
    nb = b1 - b0 - 1
    na = sum(1 for k in range(a0 + 1, a1) if not tw[k].get('skip'))
    if nb >= 10 and na <= 0.35 * (g1 - g0) * 2.2:
        a_pt = quietest(g0 + 0.02, g0 + 0.20); b_pt = quietest(g1 - 0.20, g1 - 0.02)
        cutlist.append(dict(kind='mid', o0=a_pt, o1=b_pt, g0=g0, g1=g1))
# tail: everything after the last published word, except a moment of natural decay
a_tail = quietest(last_e + 0.55, last_e + 0.85)
cutlist.append(dict(kind='tail', o0=a_tail, o1=len(x) / SR))
for c in cutlist:
    c['dur'] = c['o1'] - c['o0']
    c['text'] = window_text(c['o0'], c['o1'])
    print(f"cut {c['kind']}: {c['o0']:.2f}-{c['o1']:.2f} ({c['dur']:.1f}s)")

# free (speech-less) windows for room tone
_busy = sorted((w['s'] - 0.12, w['e'] + 0.12) for w in ww)


def room_tone(length, near, rad=60.0, seed=0):
    """a real stretch of the room's own background, the quietest word-free window of this length near `near`"""
    top = min(len(x) / SR, near + rad)
    free, cur = [], max(0.0, near - rad)
    for s, e in _busy:
        if e < near - rad or s > top:
            continue
        if s - cur >= length:
            free.append((cur, s))
        cur = max(cur, e)
    if top - cur >= length:
        free.append((cur, top))
    best, bd = None, 1e9
    for s, e in free:
        for t in np.arange(s, e - length, 0.05):
            seg = x[int(t * SR):int((t + length) * SR)]
            r = float(np.sqrt(np.mean(seg ** 2)))
            if r < bd and np.abs(seg).max() < 4 * r + 0.02:
                best, bd = t, r
    if best is None:
        return np.random.default_rng(seed).normal(0, 0.01, int(length * SR)).astype(np.float32)
    return x[int(best * SR):int((best + length) * SR)].copy()


# ====================================================================== 3. assemble the edited audio
kept = []   # original-time intervals kept, in order
cuts_sorted = sorted(cutlist, key=lambda c: c['o0'] if c['kind'] != 'head' else -1)
head = cuts_sorted[0]
kept_edges = [head['o1']]
for c in cuts_sorted[1:]:
    kept.append((kept_edges[-1], c['o0']))
    kept_edges.append(c['o1'])
# pieces: (tone) + kept + (tone + kept)* + (tone)
out = np.zeros(0, np.float32)
pmap = []   # (o0, o1, e0) audio pieces


def append(seg):
    global out
    if len(out) == 0:
        out = seg.astype(np.float32); return 0
    f = np.linspace(0, 1, XF, dtype=np.float32)
    out[-XF:] = out[-XF:] * (1 - f) + seg[:XF] * f
    pos = len(out) - XF
    out = np.concatenate([out, seg[XF:]])
    return pos


tone_head = room_tone(SPLICE + 0.05, head['o1'], rad=120)
append(tone_head)
splices = []   # (edited time of splice, original o0, o1)
for idx, (k0, k1) in enumerate(kept):
    pos = append(x[int(k0 * SR):int(k1 * SR)])
    pmap.append((k0, k1, pos / SR))
    if idx < len(kept) - 1:                     # interior splice: top up the natural pause with room tone
        c = cuts_sorted[idx + 1]
        have = (c['o0'] - c['g0']) + (c['g1'] - c['o1'])      # quiet edges already kept on both sides
        splices.append((len(out) / SR, c['o0'], c['o1']))
        append(room_tone(max(0.05, SPLICE - have), c['o0'], seed=idx))
tail_tone = room_tone(0.5, kept[-1][1])
append(tail_tone)
# fade the very end
fe = int(0.08 * SR)
out[-fe:] *= np.linspace(1, 0, fe, dtype=np.float32)
gain = 0.95 / max(1.0, float(np.abs(out).max()))
out = out * gain
dur_samples = len(out)
print('edited length', dur_samples / SR, 'gain', gain)


def emap(t):
    """original time -> edited time"""
    if t <= pmap[0][0]:
        return pmap[0][2]
    for k, (o0, o1, e0) in enumerate(pmap):
        if t <= o1:
            return e0 + (t - o0)
        if k + 1 < len(pmap) and t < pmap[k + 1][0]:
            return e0 + (o1 - o0) if t - o1 < pmap[k + 1][0] - t else pmap[k + 1][2]
    o0, o1, e0 = pmap[-1]
    return e0 + (o1 - o0)


p = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'libmp3lame',
                    '-b:a', '40k', f'{W}/audio_edit.mp3'], input=out.tobytes(), capture_output=True)
assert p.returncode == 0, p.stderr
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f'{W}/audio_edit.mp3', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                     capture_output=True, check=True).stdout
y = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
dur = len(y) / SR
probe = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{W}/audio_edit.mp3'],
                             capture_output=True, text=True, check=True).stdout)
print('decoded duration', dur, 'ffprobe', probe)

# ====================================================================== 4. word, turn and chapter times in the edited audio
for paras in RAW:
    for ws in paras:
        for w in ws:
            w['e0'], w['e1'] = emap(w['o0']), emap(w['o1'])
TURN = []
for ti, t in enumerate(turns):
    real = [w for ws in RAW[ti] for w in ws if w['tok'] is not None and not tw[w['tok']].get('skip')]
    f, l = real[0], real[-1]
    TURN.append(dict(i=ti, who=t['who'], first=f['e0'], last=l['e1'], text=t['paras'][0]))
for i, t in enumerate(TURN):                            # turn start just before its first word; stop shortly after its last
    prev_stop = TURN[i - 1]['stop'] if i else 0.0
    t['start'] = max(prev_stop, t['first'] - 0.05)
    nxt = TURN[i + 1]['first'] - 0.05 if i + 1 < len(TURN) else dur
    t['stop'] = max(t['start'] + 0.1, min(t['last'] + 0.2, max(nxt, t['last'])))
if '--table' in sys.argv:
    for t in TURN:
        print(f"{t['i']:3d} {tfmt(t['start'])} {t['stop'] - t['start']:6.1f}s {t['who']:9s} {t['text'][:110]}")
    sys.exit()

# ====================================================================== 5. mouth envelope (same method as scripts/timeline.py)
sos = butter(4, [180, 3400], btype='band', fs=SR, output='sos')
yb = sosfiltfilt(sos, y)
nF = int(math.floor(dur * FPS))
win = int(0.035 * SR)
c = np.cumsum(np.r_[0, yb ** 2])
centers = ((np.arange(nF) / FPS + LEAD) * SR).astype(int)
lo = np.clip(centers - win // 2, 0, len(yb)); hi = np.clip(centers + win // 2, 0, len(yb))
db = 20 * np.log10(np.sqrt((c[hi] - c[lo]) / np.maximum(hi - lo, 1)) + 1e-7)
GFLOOR = np.percentile(db, 8)   # silence level of the whole recording (same rule as scripts/timeline.py)
openv = np.zeros(nF, dtype=np.float32)
for t in TURN:
    f0, f1 = int(t['start'] * FPS), min(nF, int(math.ceil(t['stop'] * FPS)))
    if f1 <= f0:
        continue
    seg = db[f0:f1]
    floor, peak = np.percentile(seg, 12), np.percentile(seg, 97)
    # open only for real speech: above the turn's own quiet level and the recording's silence level, for at least 3 frames
    thr = max(floor + 7.0, GFLOOR + 13.0)
    thr = max(GFLOOR + 5.0, min(thr, peak - 16.0))   # quiet speakers: gate no more than 16 dB under the turn's loud end (same as timeline.py)
    on = seg > thr
    j = 0
    while j < len(on):
        if on[j]:
            k = j
            while k < len(on) and on[k]:
                k += 1
            if k - j < 3:
                on[j:k] = False
            j = k
        else:
            j += 1
    o = np.clip((seg - thr) / max(8.0, peak - thr), 0, 1) ** 0.85 * on
    sm = np.zeros_like(o); prev = 0.0
    for k, v in enumerate(o):                      # instant attack, release factor 0.45 per frame
        prev = v if v > prev else max(v, prev * 0.45)
        sm[k] = prev
    openv[f0:f1] = sm

# ====================================================================== 6. edit decision list
rng = random.Random(20261008)
SEAT = KIDX


def half_for(who):
    return 'bench_center' if who == 'lawler' else ('bench_left' if SEAT[who] <= 2 else 'bench_right')


# word boundaries in the edited audio (between consecutive spoken words) for cutting between words, never inside one
allw = [w for paras in RAW for ws in paras for w in ws if w['tok'] is not None and not tw[w['tok']].get('skip')]
bnd = []   # (gap start, gap end)
for a_, b_ in zip(allw, allw[1:]):
    bnd.append((a_['e1'], b_['e0'], bool(re.search(r'[.?!][”’"\')\]]*$', a_['text']))))
bt = np.array([(g0 + g1) / 2 for g0, g1, _ in bnd])
bgap = np.array([max(0.0, g1 - g0) for g0, g1, _ in bnd])
bsent = np.array([1.0 if s else 0.0 for _, _, s in bnd])


def dby(t, half=0.01):
    lo_, hi_ = max(0, int((t - half) * SR)), min(len(y), int((t + half) * SR))
    return 10 * math.log10(float(np.mean(y[lo_:hi_] ** 2)) + 1e-12) if hi_ > lo_ else -90


def snap(target, rad=1.4):
    """a cut time near target that falls between words, preferring real pauses and sentence ends, then the quietest instant"""
    m = np.where(np.abs(bt - target) <= rad)[0]
    if not len(m):
        return target
    score = bgap[m] + 0.25 * bsent[m] - 0.18 * np.abs(bt[m] - target)
    j = m[int(np.argmax(score))]
    g0, g1, _ = bnd[j]
    if g1 - g0 > 0.04:
        tt = np.arange(g0, g1 + 1e-9, 0.01)
        return float(tt[int(np.argmin([dby(t) for t in tt]))])
    return float(bt[j])


plan = []          # [time, shot]; each shot lasts until the next entry
last_q = {'who': None}


def reaction_target(i):
    """close-up of the journalist who asked the question that the speaker in turn i is answering"""
    j = i - 1
    while j >= 0:
        if TURN[j]['who'] in JOURNALISTS and TURN[j]['stop'] - TURN[j]['start'] >= 2.0:
            return TURN[j]['who']
        j -= 1
        if i - j > 6:
            break
    return None


CUT_MIN, CUT_MAX = 10.0, 20.0
prev_cut = None
for i, t in enumerate(TURN):
    s, e, who = t['start'], t['stop'], t['who']
    d = e - s
    if i == 0:
        plan.append([0.0, 'wide'])
        s0 = max(s, 8.4)                               # the title card sits over the first shot
        cur = s0
        plan.append([s0, who])
    elif d < 2.5:
        if d < 0.8 and plan[-1][1] in KEYS:           # a bare "yeah": stay on the person talking
            continue
        plan.append([s, rng.choice(['wide', half_for(who), half_for(who)])])
        continue
    else:
        plan.append([s, who]); cur = s
    # cutaways during a long turn
    nxt_len = rng.uniform(CUT_MIN, CUT_MAX)
    cur = plan[-1][0] if i else cur
    while e - cur > nxt_len + 6.0:
        at = cur + nxt_len
        opts = []
        if who == 'lawler':
            r = reaction_target(i)
            if r:
                opts += [r, r, r]
        else:
            opts += ['lawler', 'lawler']
        opts += ['wide', half_for(rng.choice([k for k in KEYS if k != who]))]
        if prev_cut in opts and len(opts) > 1:
            opts = [o for o in opts if o != prev_cut]
        shot = rng.choice(opts); prev_cut = shot
        cl = rng.uniform(3.0, 5.5)
        plan.append([at, shot])
        plan.append([at + cl, who])
        cur = at + cl
        nxt_len = rng.uniform(CUT_MIN, CUT_MAX)

# snap boundaries: turn starts cut just before the first word, cutaways between words
turn_cut = {round(t['start'], 3) for t in TURN}
snapped = []
for tm, sh in plan:
    if tm <= 0:
        snapped.append([0.0, sh]); continue
    if round(tm, 3) in turn_cut:
        snapped.append([tm, sh])
    else:
        snapped.append([snap(tm), sh])
snapped.sort(key=lambda p: p[0])
# minimum shot length 1.2 s: a shorter shot is absorbed by the shot before it (the first by the one after); merge identical neighbours
shots = []
for tm, sh in snapped:
    if shots and sh == shots[-1][1]:
        continue
    shots.append([tm, sh])
changed = True
while changed and len(shots) > 1:
    changed = False
    for k in range(len(shots)):
        end = shots[k + 1][0] if k + 1 < len(shots) else dur
        if end - shots[k][0] < 1.2:
            if k == 0:
                shots[1][0] = 0.0; del shots[0]
            else:
                del shots[k]
            merged = [shots[0]]
            for s_ in shots[1:]:
                if s_[1] != merged[-1][1]:
                    merged.append(s_)
            shots = merged
            changed = True
            break
fixed = shots
SHOTS = [[round(a, 3), round(b[0] if b else dur, 3), s] for (a, s), b in zip(fixed, fixed[1:] + [None])]
SHOTS[-1][1] = round(dur, 3)
_ws = np.array([(w['e0'], w['e1']) for w in allw])
inside = [round(a, 2) for a, _, _ in SHOTS[1:] if np.any((_ws[:, 0] + 0.03 < a) & (a < _ws[:, 1] - 0.03))]
print('shot boundaries inside a word (by Whisper timing):', len(inside), 'of', len(SHOTS) - 1, inside[:10])

# ====================================================================== 7. captions (published text, ~90 characters, timed from the aligned words)
def endp(text, chars):
    t_ = re.sub(r'[”’"\')\]]+$', '', text)
    return bool(t_) and t_[-1] in chars


def chunk_words(ws, maxc=90):
    chunks, cur, curlen = [], [], 0
    for w in ws:
        if cur and (curlen + len(w['text']) + 1 > maxc or w['e0'] - cur[-1]['e1'] > 1.5):
            k = len(cur)
            if curlen + len(w['text']) + 1 > maxc and w['e0'] - cur[-1]['e1'] <= 1.5:
                run = 0; best = None
                for q, cw in enumerate(cur):
                    run += len(cw['text']) + 1
                    if endp(cw['text'], '.?!') and run >= 30:
                        best = q + 1
                if best is None:
                    run = 0
                    for q, cw in enumerate(cur):
                        run += len(cw['text']) + 1
                        if endp(cw['text'], ',;:—–') and run >= 50:
                            best = q + 1
                k = best or len(cur)
            chunks.append(cur[:k]); cur = cur[k:]
            curlen = sum(len(cw['text']) + 1 for cw in cur)
        cur.append(w); curlen += len(w['text']) + 1
        if curlen >= 55 and endp(w['text'], '.?!'):         # prefer ending a caption at a sentence end
            chunks.append(cur); cur = []; curlen = 0
    if cur:
        chunks.append(cur)
    if len(chunks) > 1 and sum(len(c_['text']) + 1 for c_ in chunks[-1]) < 25 and chunks[-1][0]['e0'] - chunks[-2][-1]['e1'] <= 1.5:
        last = chunks.pop(); chunks[-1] += last
    return chunks


CAPS = []
for ti, t in enumerate(turns):
    for ws in RAW[ti]:
        bracket = all(re.match(r'^\[.*\]$', w['text']) for w in ws)
        who = -1 if bracket else KIDX[t['who']]
        for ch in chunk_words(ws):
            CAPS.append([ch[0]['e0'], ch[-1]['e1'], who, ' '.join(w['text'] for w in ch)])
CAPS.sort(key=lambda c: (c[0], c[1]))
for k, cp in enumerate(CAPS):
    nxt = CAPS[k + 1][0] if k + 1 < len(CAPS) else dur
    end = cp[1]
    end = nxt if nxt - end < 0.8 else end + 0.3
    cp[1] = max(min(end, nxt), min(nxt, cp[0] + 0.5))
    if cp[1] < cp[0] + 0.05:
        cp[1] = cp[0] + 0.05
CAPS = [[round(a, 3), round(b, 3), w_, tx] for a, b, w_, tx in CAPS]

# ====================================================================== 8. audio segment cut points (quietest moment near every 600 s)
SEG = float(os.environ.get('SEG', 600))
k_sm = int(FPS * 0.6)
db_sm = np.convolve(db, np.ones(k_sm) / k_sm, mode='same')
CUTS = []
target = SEG
while target < dur - SEG * 0.5:
    lo_, hi_ = int((target - 30) * FPS), int((target + 30) * FPS)
    CUTS.append(round((lo_ + int(np.argmin(db_sm[lo_:hi_]))) / FPS, 3))
    target = CUTS[-1] + SEG

TLW = dict(fps=FPS, nframes=nF, duration=round(dur, 3), keys=KEYS, labels=LABEL,
           turns=[[round(t['start'], 3), round(t['stop'], 3), KIDX[t['who']]] for t in TURN],
           openv=base64.b64encode(np.clip(np.round(openv * 255), 0, 255).astype(np.uint8).tobytes()).decode(),
           shots=SHOTS, captions=CAPS, sections=[[round(TURN[0]['start'], 3), 'lawler']], cuts=CUTS)
json.dump(TLW, open(f'{W}/tl_web.json', 'w'), separators=(',', ':'), ensure_ascii=False)

# ====================================================================== 9. cut list, alignment dump, report
cutmap = []
for c in cutlist:
    cutmap.append(dict(kind=c['kind'], orig_start=round(c['o0'], 3), orig_end=round(c['o1'], 3), duration=round(c['dur'], 3),
                       edit_time=round(emap(c['o0']) if c['kind'] != 'head' else 0.0, 3), words_heard=c['text']))
json.dump(dict(min_cut_seconds=MIN_CUT, splice_pause_seconds=SPLICE, removed=cutmap,
               kept=[dict(orig_start=round(o0, 3), orig_end=round(o1, 3), edit_start=round(e0, 3)) for o0, o1, e0 in pmap],
               edited_duration=round(dur, 3), original_duration=round(len(x) / SR, 3)),
          open(f'{W}/cuts.json', 'w'), indent=1, ensure_ascii=False)

aligned = [dict(turn=ti, speaker=turns[ti]['who'], paragraphs=[[dict(w=w['text'], t=round(w['e0'], 3), t_end=round(w['e1'], 3), orig=round(w['o0'], 3), matched=w['tok'] in match) for w in ws] for ws in RAW[ti]])
           for ti in range(len(turns))]
json.dump(aligned, open(f'{W}/alignment.json', 'w'), ensure_ascii=False)
nonskip = [k for k in range(n) if not tw[k].get('skip')]
stats = dict(transcript_tokens=len(nonskip), matched=sum(1 for k in nonskip if k in match), exact=sum(1 for k in nonskip if k in match and k not in fuzzy),
             fuzzy=sum(1 for k in nonskip if k in fuzzy), whisper_tokens=len(ww))
print(stats)
json.dump(dict(stats=stats), open(f'{W}/tmp/stats.json', 'w'))


# ====================================================================== 10. page data, audio segments, cuts report
PAGE = f'{W}/page'
os.makedirs(f'{PAGE}/audio', exist_ok=True)
dek = open(f'{W}/transcript.txt', encoding='utf-8').read().split('\n')[1].strip()
title = open(f'{W}/transcript.txt', encoding='utf-8').read().split('\n')[0].strip()
spec = json.load(open(f'{W}/chapters.json'))
chapters = [[round(TURN[i]['start'], 1), tx] for i, tx in spec]
assert chapters == sorted(chapters)
secs, first = {}, {}
for t in TURN:
    secs[t['who']] = secs.get(t['who'], 0.0) + t['stop'] - t['start']
    first.setdefault(t['who'], t['start'])
mic = [[DISPLAY[k], round(secs[k] / 60, 1), round(first[k], 1)] + ([True] if k == 'lawler' else []) for k in sorted(secs, key=lambda k: -secs[k])]
ROLE = {k: 'The New York Editorial Board' for k in KEYS}
ROLE['lawler'] = "Republican, New York's 17th District"
tags = {k: [DISPLAY[k], ROLE[k]] for k in KEYS}
page = dict(
    case_name=title, docket='', argued='October 8, 2026', decided='',
    bug='THE NEW YORK EDITORIAL BOARD \u00b7 REP. MIKE LAWLER \u00b7 OCT. 8, 2026',
    question=dek, question_label='The interview.', tag_at='center', outcome='', outcome_src='',
    stand_in_note='The puppets are caricatures of the participants, built from photographs.',
    end_puppets='', oyez_url='', credit='Made by Josh Greenman with Claude.', storage_key='pos-lawler-nyeb',
    bench=KEYS, advocates=[], chapters=chapters, cards=[], tags=tags, mic=mic, notes=[],
    kicker='THE NEW YORK EDITORIAL BOARD', subline='Breakfast interview \u00b7 October 8, 2026',
    tagline='Performed by puppets. Every word is the actual recording.',
    bug2='PUPPETS ARE CARICATURES \u00b7 AUDIO IS THE REAL INTERVIEW',
    setting='breakfast table', noun='interview',
    end_lines=[['RECORDING AND TRANSCRIPT', 'The New York Editorial Board, October 8, 2026'],
               ['THE PUPPETS', 'Caricatures of the participants, built from photographs']],
    about_html=("The audio is the New York Editorial Board's recording of its breakfast interview with Rep. Mike Lawler, trimmed to match the "
                "Board's published transcript, which also marks who is speaking when. Each puppet's mouth moves with the loudness of the "
                "speaker's syllables during that person's turn, and the participants are seated around the table."),
    credits_html="The recording and the transcript are the New York Editorial Board's.",
    mic_note="Minutes of speaking turns in the published transcript. Select a name to jump to that speaker's first words.")
json.dump(dict(page=page), open(f'{W}/page_data.json', 'w'), ensure_ascii=False, indent=1)

bounds = [0.0] + CUTS + [None]
segments = []
for i in range(len(bounds) - 1):
    pth = f'audio/s{i:02d}.mp3'
    span = ['-t', str(bounds[i + 1] - bounds[i])] if bounds[i + 1] else []
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(bounds[i]), '-i', f'{W}/audio_edit.mp3'] + span +
                   ['-c', 'copy', '-map', '0:a', f'{PAGE}/{pth}'], check=True)
    d_ = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{PAGE}/{pth}'],
                              capture_output=True, text=True, check=True).stdout)
    segments.append([pth, round(bounds[i], 3), round(d_, 3)])
json.dump(dict(page=page, tl=TLW, segments=segments), open(f'{PAGE}/data.json', 'w'), separators=(',', ':'), ensure_ascii=False)
print('segments', segments)

# ---------------------------------------------------------------- cuts report for the editor
def span_txt(o0, o1):
    return f'{tfmt(o0)}\u2013{tfmt(o1)}'


def first_words(o0, o1, k=25):
    return ' '.join(w['raw'] for w in ww if o0 <= w['s'] < o1 and w['raw']).split()[:k]


NOTES = {
    'head': ("Pre-interview small talk and logistics: a chat about where someone lives, Lawler's arrival and introductions, "
             "coffee and food orders, breakfast arriving, light banter (someone is told \"no coaching\"), and Ben Smith's ground rules "
             "(\"we're recorded, no video. We just post the transcript ... It's all on the record\", he will moderate and may cut people off, "
             "the Israel portion can't run too long). Nothing in it is marked off the record. The interview proper starts at 2:49.8 "
             "with \"First of all, thanks for coming in.\" Whisper garbles names here (\"Lance Zagari\" is Liena \u017dagare)."),
    'tail': ("Post-interview chatter after Lawler's final \"Thank you.\": a further \"Thank you\" and a remark that something \"didn't get to heat at all\". "
             "Under the 10-second threshold, but it falls after the published transcript ends, so the audio stops about 0.7 s after the last published word."),
}
L = ['# Cuts report: Mike Lawler editorial-board interview', '',
     f'Recording: {tfmt(len(x) / SR)} ({len(x) / SR:.1f} s). Edited audio (`audio_edit.mp3`): {tfmt(dur)} ({dur:.1f} s). '
     f'Removed: {sum(c["dur"] for c in cutlist):.1f} s in {len(cutlist)} stretches.', '',
     f'Method: the published transcript was word-aligned to Whisper\'s timed words ({stats["matched"]} of {stats["transcript_tokens"]} transcript words matched, '
     f'{100 * stats["matched"] / stats["transcript_tokens"]:.1f}%). Any run of Whisper speech that the transcript lacks and that lasts {MIN_CUT:.0f} s or more is cut, '
     f'as is everything before the first and after the last published word. Each interior splice would keep a pause of about {SPLICE} s '
     '(natural quiet at both edges topped up with a stretch of the room\'s own background, 12 ms crossfades); at the start the audio opens with '
     f'{SPLICE} s of room tone before the first word. Machine-readable list with old-to-new times: `cuts.json`.', '',
     '## Removed', '']
for c in cutlist:
    ew = first_words(c['o0'], c['o1'])
    L += [f'### {span_txt(c["o0"], c["o1"])} ({c["dur"]:.1f} s) \u2013 {"before the interview" if c["kind"] == "head" else ("after the interview" if c["kind"] == "tail" else "mid-interview")}', '',
          f'- Original time: {c["o0"]:.2f} to {c["o1"]:.2f} s. In the edited audio this stretch sits at {tfmt(0 if c["kind"] == "head" else emap(c["o0"]))}'
          f'{" (the very start)" if c["kind"] == "head" else (" (the end)" if c["kind"] == "tail" else "")}.',
          f'- What Whisper heard (first {len(ew)} words): "{" ".join(ew)}"', f'- Editor\'s note: {NOTES.get(c["kind"], "")}', '']
if len(cutlist) == 2:
    L += ['No unpublished stretch of 10 seconds or more turned up inside the interview itself; the published transcript is a close, '
          'lightly edited record of everything said between those two points.', '']
# shorter unpublished runs left in
short = []
for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
    g0, g1 = ww[b0]['e'], ww[b1]['s']
    nb = b1 - b0 - 1
    if g0 < head['o1'] or g1 > a_tail:
        continue
    if nb >= 10 and g1 - g0 >= 4.0:
        short.append((g0, g1, a0, a1))
L += ['## Not in the transcript but kept (shorter than the threshold)', '',
      f'Runs of Whisper speech with no counterpart in the published text, 4 s or longer, left in the audio. To remove them too, rerun with `MIN_CUT=4 python build.py`.', '']
if not short:
    L += ['None.', '']
for g0, g1, a0, a1 in short:
    words = [w['raw'] for w in ww if g0 <= w['s'] < g1]
    xt = any('Crosstalk' in tw[k]['raw'] for k in range(a0 + 1, a1))
    L += [f'- Original {span_txt(g0, g1)} ({g1 - g0:.1f} s; edited {tfmt(emap(g0))}): "{" ".join(words[:25])}"' + (' (the transcript has a [Crosstalk] marker here)' if xt else '')]
open(f'{W}/cuts_report.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('wrote report')

if os.path.exists(f'{W}/finish_page.py'):
    subprocess.run([sys.executable, f'{W}/finish_page.py'], check=True)
