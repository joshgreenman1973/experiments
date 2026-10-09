# Composite rendered puppet layers into the final video, driven by the timeline.
# Usage: python compose.py ASSETS TIMELINE_DIR OUT.mp4 START_FRAME END_FRAME [--endcard]
import sys, json, math, subprocess, os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from characters import CHARS, BENCH_ORDER, ADVOCATES, CASE

ASSETS, TL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
F0, F1 = int(sys.argv[4]), int(sys.argv[5])
ENDCARD = '--endcard' in sys.argv
FPS = 24
meta = json.load(open(os.environ.get('META') or os.path.join(ASSETS, 'meta.json')))
tl = json.load(open(os.path.join(TL, 'timeline.json')))
arr = np.load(os.path.join(TL, 'timeline.npz'))
KEYS = tl['keys']
KIDX = {k: i for i, k in enumerate(KEYS)}
SPEAKER, MOUTH, TILT, BOB, SWAY = arr['speaker'], arr['mouth'], arr['tilt'], arr['bob'], arr['sway']
SHOT, ADV = arr['shot'], arr['adv']
NF = tl['nframes']

INTER_DIRS = ['/usr/share/fonts/opentype/inter', os.path.expanduser('~/Library/Fonts'), '/Library/Fonts',
              os.path.join(os.path.dirname(__file__), '..', 'fonts')]
SANS_FALLBACK = {'Bold': '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                 'SemiBold': '/System/Library/Fonts/Supplemental/Arial Bold.ttf'}
SERIF = next((p for p in ('/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
                          '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
                          '/System/Library/Fonts/Supplemental/Georgia.ttf') if os.path.exists(p)), None)
GOLD = (214, 180, 106)


def font(style, size):
    """Inter (Linux package, or dropped into ~/Library/Fonts or ./fonts), else Arial on macOS, else PIL's default."""
    for d in INTER_DIRS:
        for ext in ('otf', 'ttf'):
            p = os.path.join(d, f'Inter-{style}.{ext}')
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    p = SANS_FALLBACK.get(style, '/System/Library/Fonts/Supplemental/Arial.ttf')
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default(size)


def serif(size):
    return ImageFont.truetype(SERIF, size) if SERIF else font('Regular', size)


import layers as L
from layers import premul, blend, W, H
L.configure(ASSETS, meta)


def vhead(v, dst, n, f, state, motion=1.0):
    k = KIDX[n]
    c = v.chars[n]
    v.warp_head(dst, n, state, math.radians(float(TILT[k, f]) * motion),
                float(SWAY[k, f]) * 0.35 * c['unit'] * motion, -float(BOB[k, f]) * 0.35 * c['unit'] * motion)


print('loading assets...', flush=True)
ONLY = os.environ.get('ONLY_VCS', '').split(',') if os.environ.get('ONLY_VCS') else None
VC = L.build_vcams(BENCH_ORDER, ADVOCATES, only=ONLY)
print('assets loaded', flush=True)

# ------------------------------------------------------------------ overlays
CAPS = tl['captions']
cap_starts = np.array([c['start'] for c in CAPS])
_cap_cache = {}


def text_w(draw, s, f):
    return draw.textlength(s, font=f)


def wrap(s, f, maxw, draw):
    words, lines, cur = s.split(), [], ''
    for w_ in words:
        t = (cur + ' ' + w_).strip()
        if text_w(draw, t, f) > maxw and cur:
            lines.append(cur); cur = w_
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def caption_img(i):
    if i in _cap_cache:
        return _cap_cache[i]
    c = CAPS[i]
    f = font('Medium', 25)
    fl = font('Bold', 14)
    tmp = Image.new('RGBA', (10, 10)); d = ImageDraw.Draw(tmp)
    lines = wrap(c['text'], f, 980, d)[:3]
    lh = 33
    tw = max(text_w(d, l, f) for l in lines)
    lab = c['label']
    lw = text_w(d, lab, fl) + len(lab) * 1.5
    bw = int(max(tw, lw) + 48)
    bh = int(lh * len(lines) + 24 + (21 if lab else 0))
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=10, fill=(8, 8, 10, 172))
    y = 11
    if lab:
        x = 24
        for ch in lab:
            d.text((x, y), ch, font=fl, fill=GOLD + (255,)); x += text_w(d, ch, fl) + 1.5
        y += 21
    for l in lines:
        d.text((24, y), l, font=f, fill=(250, 248, 242, 255)); y += lh
    pm = premul(np.array(im))
    if len(_cap_cache) > 64:
        _cap_cache.clear()
    _cap_cache[i] = pm
    return pm


def name_tag(n):
    ch = CHARS[n]
    name = ch['display']
    role = ch.get('role', 'Associate Justice' if n != 'roberts' else 'Chief Justice of the United States')
    if n == 'roberts':
        name = 'John G. Roberts, Jr.'
    elif n in BENCH_ORDER:
        name = name.replace('Justice ', '')
    f1, f2 = font('Bold', 30), font('Regular', 19)
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    w_ = int(max(text_w(tmp, name, f1), text_w(tmp, role, f2)) + 56)
    im = Image.new('RGBA', (w_, 92), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w_, 92], fill=(10, 10, 12, 190))
    d.rectangle([0, 0, 6, 92], fill=GOLD + (255,))
    d.text((26, 12), name, font=f1, fill=(255, 255, 255, 255))
    d.text((26, 54), role, font=f2, fill=(222, 214, 196, 255))
    return premul(np.array(im))


TAGS = {n: name_tag(n) for n in BENCH_ORDER + ADVOCATES}


def bug_img():
    f = font('SemiBold', 15)
    s1 = f"{CASE['short_name']}  ·  No. {CASE['docket']}  ·  ARGUED {CASE['argued_short']}"
    s2 = 'PUPPETS ARE CARICATURES  ·  AUDIO IS THE REAL ARGUMENT'
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    w_ = int(max(text_w(tmp, s1, f), text_w(tmp, s2, font('Regular', 12))) + 28)
    im = Image.new('RGBA', (w_, 50), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w_ - 1, 49], radius=6, fill=(0, 0, 0, 110))
    d.text((14, 7), s1, font=f, fill=(255, 255, 255, 230))
    d.text((14, 29), s2, font=font('Regular', 12), fill=(230, 214, 170, 230))
    return premul(np.array(im))


BUG = bug_img()


def title_img():
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    grad = np.zeros((H, W, 4), np.uint8)
    yy = np.linspace(0, 1, H)[:, None]
    grad[..., 3] = (np.clip(1.0 - np.abs(yy - 0.42) * 1.6, 0, 1) * 200).astype(np.uint8)
    im = Image.fromarray(grad, 'RGBA')
    d = ImageDraw.Draw(im)
    f1 = serif(64)
    f2 = font('Medium', 24)
    f3 = font('Regular', 20)
    def ctext(y, s, f, fill):
        d.text((W / 2, y), s, font=f, fill=fill, anchor='mm')
    ctext(196, 'THE SUPREME COURT OF THE UNITED STATES', font('SemiBold', 18), GOLD + (255,))
    ctext(262, CASE['case_name'], f1, (255, 255, 255, 255))
    ctext(326, f"Oral argument  ·  {CASE['argued']}  ·  No. {CASE['docket']}", f2, (240, 236, 226, 255))
    ctext(372, 'Performed by puppets. Every word is the actual courtroom audio.', f3, (225, 215, 190, 255))
    return premul(np.array(im))


TITLE = title_img()

SECTIONS = tl['sections']
CHAPTER_TEXT = []
for i, (st, adv) in enumerate(SECTIONS):
    if i < len(CASE.get('sections', [])):
        sec = CASE['sections'][i]
        CHAPTER_TEXT.append((8.0 if i == 0 else st + 0.5, sec['title'], sec.get('sub', '')))


def chapter_img(a, b):
    f1, f2 = font('Bold', 22), font('Regular', 18)
    tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    w_ = int(max(text_w(tmp, a, f1) + len(a) * 1.2, text_w(tmp, b, f2)) + 60)
    im = Image.new('RGBA', (w_, 78), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w_ - 1, 77], radius=8, fill=(10, 10, 12, 200))
    d.line([(30, 44), (w_ - 30, 44)], fill=GOLD + (200,), width=1)
    x = 30
    for ch in a:
        d.text((x, 12), ch, font=f1, fill=(255, 255, 255, 255)); x += text_w(d, ch, f1) + 1.2
    d.text((w_ / 2, 60), b, font=f2, fill=(230, 220, 196, 255), anchor='mm')
    return premul(np.array(im))


CHAPTERS = [(t, chapter_img(a, b)) for t, a, b in CHAPTER_TEXT]
CLIP = os.environ.get('CLIP')  # 'F0,F1,label' -> excerpt card + fades at the clip's own ends
if CLIP:
    c0, c1, clabel = CLIP.split(',', 2)
    c0, c1 = int(c0), int(c1)
    CHAPTERS.append((c0 / FPS + 0.3, chapter_img(CASE['case_name'].upper().replace(' V. ', ' v. ') + '  ·  EXCERPT', clabel)))


def endcard_frame(k):
    im = Image.new('RGB', (W, H), (8, 7, 7))
    d = ImageDraw.Draw(im)
    def ctext(y, s, f, fill):
        d.text((W / 2, y), s, font=f, fill=fill, anchor='mm')
    ctext(150, CASE['case_name'], serif(52), (255, 255, 255))
    ctext(205, f"Argued {CASE['argued']}" + (f"  ·  {CASE['decided']}" if CASE.get('decided') else ''),
          font('Regular', 22), (220, 212, 196))
    lines = [
        ('Audio and transcript timing', 'Oyez (oyez.org), from the Supreme Court of the United States; CC BY-NC 4.0'),
        ('The puppets', 'Procedural 3D caricatures of the justices and counsel; any resemblance is rough by design'),
        ('What you heard', 'The complete, unedited argument audio; captions follow the Oyez transcript'),
    ]
    y = 300
    for a, b in lines:
        ctext(y, a.upper(), font('SemiBold', 16), GOLD); ctext(y + 30, b, font('Regular', 21), (236, 232, 222))
        y += 92
    arr_ = np.array(im).astype(np.float32)
    fade = min(1.0, k / 12.0)
    return arr_ * fade


# ------------------------------------------------------------------ main loop
def overlay(dst, pm, x, y, alpha=1.0):
    if alpha <= 0:
        return
    blend(dst, pm * alpha if alpha < 1 else pm, x, y)


def ramp(t, t0, t1, fade=0.35):
    if t < t0 or t > t1:
        return 0.0
    return min(1.0, (t - t0) / fade, (t1 - t) / fade)


# name-tag schedule: when the edit cuts to a close-up of someone not tagged in the last 150 s
SHOTS = tl['shots']
tag_events = []
last_tag = {}
for s, e, nm in SHOTS:
    if os.environ.get('CLIP') and e < int(os.environ['CLIP'].split(',')[0]) / FPS:
        continue
    if nm in TAGS and (s - last_tag.get(nm, -1e9) > 150) and e - s > 2.0:
        tag_events.append((s + 0.3, min(e, s + 4.6), nm)); last_tag[nm] = s

enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                        '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', os.environ.get('PRESET', 'veryfast'),
                        '-crf', os.environ.get('CRF', '21'), '-pix_fmt', 'yuv420p', '-g', '96',
                        '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
shot_names = tl['shot_names']
WIDE_FAMILY = {'wide', 'bench_left', 'bench_right', 'bench_center'}
import time
t_start = time.time()
for f in range(F0, F1):
    if f >= NF:
        frame = endcard_frame(f - NF)
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        continue
    t = f / FPS
    sn = shot_names[SHOT[f]]
    if sn not in VC:
        sn = 'wide'
    v = VC[sn]
    frame = v.base.copy()
    spk = SPEAKER[f]
    spk_key = KEYS[spk] if spk >= 0 else None
    if sn in WIDE_FAMILY:
        for n in BENCH_ORDER:
            if n in v.chars:
                vhead(v, frame, n, f, int(MOUTH[f]) if spk_key == n else 0, motion=1.0)
        adv = KEYS[ADV[f]]
        if adv in v.chars:
            c = v.chars[adv]
            blend(frame, c['body'].img, c['body'].x, c['body'].y)
            vhead(v, frame, adv, f, 0, motion=0.6)
    else:
        vhead(v, frame, sn, f, int(MOUTH[f]) if spk_key == sn else 0)
    # overlays
    overlay(frame, BUG, 22, 18, 1.0 if t > 8.0 else ramp(t, 7.0, 1e9, 1.0))
    if t < 8.0:
        overlay(frame, TITLE, 0, 0, max(0.0, min(1.0, (7.6 - t) / 1.1)))
    for ts, img in CHAPTERS:
        a = ramp(t, ts, ts + 4.5)
        if a > 0:
            overlay(frame, img, W - img.shape[1] - 22, 18, a)
    for ts, te, nm in tag_events:
        a = ramp(t, ts, te)
        if a > 0:
            overlay(frame, TAGS[nm], 0, 452, a)
    i = int(np.searchsorted(cap_starts, t, side='right')) - 1
    if i >= 0 and t < CAPS[i]['end'] + 0.25:
        img = caption_img(i)
        overlay(frame, img, (W - img.shape[1]) // 2, H - img.shape[0] - 26)
    if f < 12:
        frame *= f / 12.0
    if CLIP:
        k0, k1 = f - c0, c1 - 1 - f
        if k0 < 12:
            frame *= max(k0, 0) / 12.0
        if k1 < 18:
            frame *= max(k1, 0) / 18.0
    enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    if (f - F0) % 2400 == 0:
        el = time.time() - t_start
        print(f'frame {f} ({(f - F0) / max(el, 1e-6):.1f} fps)', flush=True)
enc.stdin.close()
enc.wait()
print('done', OUT, round(time.time() - t_start, 1), flush=True)
