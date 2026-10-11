# Mouth openness for the puppets' jaws, from the audio envelope. Shared by scripts/timeline.py (court) and interview/build.py.
#
# The old rule mapped loudness to jaw position, frame by frame. In a reverberant room the tail of one syllable fills the gap before
# the next, so the loudness barely dips and the jaw opened once per two or three syllables and sat at its widest. This module
# finds the syllables instead and gives each one a full open-close cycle:
#
#   1. a fine envelope (25 ms RMS of the 180-3400 Hz band every 5 ms, smoothed over 30 ms) is searched for peaks at least 110 ms
#      apart that stand at least 3 dB above the valleys beside them: one peak per syllable (about 1.0 peaks per syllable of text);
#   2. the silence gate is the old one (above the turn's own quiet level and the recording's silence level, for 125 ms, with the
#      quiet-speaker cap), widened by 4 frames so a weak syllable between two strong ones keeps its peak, and no frame within 8 dB
#      of the recording's silence level ever opens;
#   3. each syllable opens on its peak and closes to state 0 (or 1) at the valley before the next, so every syllable is a cycle;
#   4. how wide it opens (states 2 to 4) comes from where the syllable's peak stands among the turn's syllables (half by rank, half
#      by level), so only the loudest, stressed ones reach state 4 (about a tenth of the open frames);
#   5. the mouth leads the sound by 45 ms as before, and the jaw still releases at 0.45 per frame after a peak.
import re

import numpy as np
from scipy.ndimage import binary_dilation, uniform_filter1d
from scipy.signal import butter, find_peaks, sosfiltfilt

BAND = (180, 3400)          # Hz, speech band
FINE_HOP = 0.005            # s between fine-envelope points
FINE_WIN = 0.025            # s RMS window of the fine envelope
FRAME_WIN = 0.035           # s RMS window of the frame-rate envelope (as before)
SMOOTH = 0.030              # s smoothing of the fine envelope before peak picking
MIN_GAP = 0.110             # s between syllable peaks
PROMINENCE = 3.0            # dB a syllable peak must stand above its valleys
SUB_PROMINENCE = 1.5        # dB: in a stretch longer than LONG_GAP with no peak (a long vowel, or syllables run together by reverb) look for fainter ones
LONG_GAP = 0.40             # s
VALLEY = 0.05               # openness at the valley between syllables (state 0)
L_MIN, L_MAX, L_GAMMA = 0.50, 0.97, 0.6     # openness at a syllable's peak runs from L_MIN (state 2) to L_MAX (state 4)
BRIDGE = 4                  # frames the silence gate's speech runs are widened by
AMP_MIN = 9.0               # dB over the recording's silence level the faintest syllable peak may have (a quiet speaker's)
SILENT = (8.0, 12.0)        # dB over the recording's silence level below which the mouth never opens: 12 for a loud speaker,
                            # down to 8 for one whose own loud end is near the room's level (0.4 of it, in between)
RELEASE = 0.45              # jaw decay per frame after a peak


def band_energy(x, sr=16000):
    """Cumulative energy (with a leading 0) of x band-passed to the speech band; x is float64 audio. Frees nothing: del x after."""
    xb = sosfiltfilt(butter(4, list(BAND), btype='band', fs=sr, output='sos'), x)
    c = np.empty(len(xb) + 1)
    c[0] = 0.0
    np.cumsum(xb ** 2, out=c[1:])
    return c


def envelopes(c, sr=16000, fps=24, lead=0.045):
    """(db, fine): db is the loudness at each video frame (35 ms RMS window centred `lead` seconds after the frame, as the old
    mouth rule used); fine is the loudness every 5 ms of audio time (25 ms RMS window), for finding syllables."""
    nS = len(c) - 1
    nF = int(np.floor(nS / sr * fps))
    win = int(FRAME_WIN * sr)
    ce = ((np.arange(nF) / fps + lead) * sr).astype(int)
    lo, hi = np.clip(ce - win // 2, 0, nS), np.clip(ce + win // 2, 0, nS)
    db = 20 * np.log10(np.sqrt((c[hi] - c[lo]) / np.maximum(hi - lo, 1)) + 1e-7)
    hop, w2 = int(FINE_HOP * sr), int(FINE_WIN * sr)
    cen = np.arange(0, nS, hop)
    l2, h2 = np.clip(cen - w2 // 2, 0, nS), np.clip(cen + w2 // 2, 0, nS)
    fine = 20 * np.log10(np.sqrt((c[h2] - c[l2]) / np.maximum(h2 - l2, 1)) + 1e-7)
    return db, fine


def _gate(seg, G):
    """frames of a turn that are real speech: the old silence gate"""
    floor, peak = np.percentile(seg, 12), np.percentile(seg, 97)
    thr = max(floor + 7.0, G + 13.0)                 # above the turn's own quiet level and the recording's silence level
    thr = max(G + 5.0, min(thr, peak - 16.0))        # a quiet speaker never rises far above the room: cap the gate under the loud end
    on = seg > thr
    j = 0
    while j < len(on):                                 # runs shorter than 3 frames (125 ms) are breaths and bumps
        if on[j]:
            k = j
            while k < len(on) and on[k]:
                k += 1
            if k - j < 3:
                on[j:k] = False
            j = k
        else:
            j += 1
    return on


def openness(db, fine, turns, fps=24, lead=0.045, debug=None):
    """Mouth openness 0..1 for every frame (float32); the player maps it to jaw states with floor(openness * 4.6).
    db, fine: from envelopes(). turns: iterable of (first frame, last frame + 1, speaker); frames outside every turn stay shut.
    debug: a dict that gets 'peaks' (audio time, opening) and 'valleys' (audio time) lists, for plotting."""
    nF = len(db)
    G = np.percentile(db, 8)                          # the recording's silence level
    fs = uniform_filter1d(fine, max(1, int(round(SMOOTH / FINE_HOP))))
    gap = int(round(MIN_GAP / FINE_HOP))
    jobs = []
    for f0, f1, who in turns:                        # pass 1: speech runs and syllable peaks of every turn
        f1 = min(nF, f1)
        if f1 <= f0:
            continue
        on = _gate(db[f0:f1], G)
        run = binary_dilation(on, iterations=BRIDGE) if BRIDGE else on
        i0 = int(f0 / fps / FINE_HOP)
        seg = fs[i0:int(f1 / fps / FINE_HOP) + 1]
        pk, _ = find_peaks(seg, distance=gap, prominence=PROMINENCE)
        tm = (pk + i0) * FINE_HOP                    # audio time of each peak
        fr = np.clip(np.round((tm - lead) * fps).astype(int), f0, f1 - 1) - f0
        keep = run[fr] & (seg[pk] - G >= AMP_MIN)
        pk = pk[keep]
        extra = []                                   # a long stretch with no peak (a long vowel, or syllables run together by reverb): look again, fainter
        for a, b in zip(np.concatenate([[0], pk]), np.concatenate([pk, [len(seg) - 1]])):
            lo_ = a + gap // 2 if a else a           # stay a half gap away from the peaks on either side
            hi_ = b - gap // 2 if b < len(seg) - 1 else b
            if (b - a) * FINE_HOP > LONG_GAP and hi_ - lo_ > gap:
                q, _ = find_peaks(seg[lo_:hi_], distance=gap, prominence=SUB_PROMINENCE)
                q = q + lo_
                qf = np.clip(np.round(((q + i0) * FINE_HOP - lead) * fps).astype(int), f0, f1 - 1) - f0
                extra.extend(q[run[qf] & (seg[q] - G >= AMP_MIN)])
        pk = np.sort(np.concatenate([pk, np.array(extra, dtype=int)])).astype(int)
        tm = (pk + i0) * FINE_HOP
        jobs.append(dict(f0=f0, f1=f1, who=who, run=run, i0=i0, seg=seg, pk=pk, tm=tm, amp=seg[pk]))
    pooled = {}
    for d in jobs:
        pooled.setdefault(d['who'], []).append(d['amp'])
    pooled = {w: np.concatenate(a) for w, a in pooled.items()}
    silent = {}                                      # per speaker: how far over the room's level a frame must be to open at all
    for w, a in pooled.items():
        silent[w] = float(np.clip(0.4 * (np.percentile(a, 90) - G), SILENT[0], SILENT[1])) if len(a) else SILENT[1]
    for d in jobs:                                   # drop syllables fainter than that
        k = d['amp'] - G >= silent[d['who']] + 1.0
        d['pk'], d['tm'], d['amp'] = d['pk'][k], d['tm'][k], d['amp'][k]
    pooled = {w: np.concatenate([d['amp'] for d in jobs if d['who'] == w] or [np.zeros(0)]) for w in pooled}
    openv = np.zeros(nF, np.float32)
    for d in jobs:                                   # pass 2: shape the jaw
        f0, f1, run, i0, seg, tm, amp = d['f0'], d['f1'], d['run'], d['i0'], d['seg'], d['tm'], d['amp']
        n = f1 - f0
        tgt = np.zeros(n)
        valley = np.zeros(n, bool)
        if len(amp):
            ref = amp if len(amp) >= 25 else pooled[d['who']]       # a short turn borrows the speaker's other syllables
            lo, hi = np.percentile(ref, 10), np.percentile(ref, 92)
            r_abs = np.clip((amp - lo) / max(3.0, hi - lo), 0, 1)
            r_rank = (np.argsort(np.argsort(amp)) + 0.5) / len(amp)
            level = L_MIN + (L_MAX - L_MIN) * (0.5 * r_abs + 0.5 * r_rank) ** L_GAMMA
        j = 0
        while j < n:
            if not run[j]:
                j += 1
                continue
            k = j
            while k < n and run[k]:
                k += 1
            t0, t1 = (f0 + j) / fps + lead, (f0 + k) / fps + lead      # audio-time span of this speech run
            a, b = np.searchsorted(tm, t0 - 0.02), np.searchsorted(tm, t1 + 0.02)
            if b > a:
                pts, lev = list(tm[a:b]), list(level[a:b])
            else:                                                       # a run with no clear syllable: one, at its loudest point
                ia, ib = max(0, int(t0 / FINE_HOP) - i0), min(len(seg), int(t1 / FINE_HOP) - i0)
                if ib <= ia:
                    j = k
                    continue
                pts, lev = [(ia + int(np.argmax(seg[ia:ib])) + i0) * FINE_HOP], [0.6]
            vt = [t0]                                                   # valleys: the run's start, the minimum between peaks, its end
            for p, q in zip(pts, pts[1:]):
                ia, ib = int(p / FINE_HOP) - i0, int(q / FINE_HOP) - i0
                vt.append((ia + int(np.argmin(seg[ia:ib + 1])) + i0) * FINE_HOP if ib > ia else (p + q) / 2)
            vt.append(t1)
            if debug is not None:
                debug.setdefault('peaks', []).extend(zip(pts, lev))
                debug.setdefault('valleys', []).extend(vt[1:-1])
            for s, (pt, L) in enumerate(zip(pts, lev)):
                vl, vr = vt[s], vt[s + 1]
                fa, fb = int(np.floor((vl - lead) * fps)) - f0, int(np.ceil((vr - lead) * fps)) - f0
                for f in range(max(j, fa), min(k, fb + 1)):
                    tau = (f0 + f) / fps + lead
                    u = (tau - vl) / max(1e-3, pt - vl) if tau <= pt else (vr - tau) / max(1e-3, vr - pt)
                    u = min(1.0, max(0.0, u))
                    tgt[f] = max(tgt[f], VALLEY + (L - VALLEY) * u * u * (3 - 2 * u))
                fp = int(np.clip(round((pt - lead) * fps) - f0, j, k - 1))
                tgt[fp] = max(tgt[fp], L)                               # the frame nearest the peak carries the full opening
            for vtime in vt[1:-1]:
                valley[int(np.clip(round((vtime - lead) * fps) - f0, j, k - 1))] = True
            j = k
        quiet = db[f0:f1] < G + silent[d['who']]
        prev = 0.0
        for q in range(n):                                              # instant attack, release at 0.45 per frame, shut at each valley
            v = tgt[q]
            if quiet[q]:
                v, prev = 0.0, 0.0
            if valley[q]:
                v, prev = min(v, VALLEY), min(prev, VALLEY)
            prev = v if v > prev else max(v, prev * RELEASE)
            openv[f0 + q] = prev
    return openv


def syllables(text):
    """Rough English syllable count of a text (vowel groups, with the usual silent-e and -ed corrections); digits count one each."""
    n = 0
    for word in text.split():
        w = re.sub(r'[^a-z]', '', word.lower())
        if not w:
            n += 1 if re.search(r'\d', word) else 0
            continue
        c = len(re.findall(r'[aeiouy]+', w))
        if w.endswith('e') and not w.endswith(('le', 'ee', 'ie', 'ye')) and c > 1:
            c -= 1
        elif w.endswith('es') and c > 1 and not w.endswith(('ses', 'zes', 'ces', 'ges', 'xes', 'ches', 'shes')):
            c -= 1
        elif w.endswith('ed') and c > 1 and not w.endswith(('ted', 'ded')):
            c -= 1
        n += max(1, c)
    return n
