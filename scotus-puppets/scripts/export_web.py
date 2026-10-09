# Export the virtual cameras as browser-ready images: one baked background (plate + bodies + shadows) per camera
# and one sprite sheet per camera holding every head pose, plus a layout file the player reads.
# Usage: python export_web.py ASSETS META.json OUTDIR --advocates key1,key2,... [--motion]
#   --motion (Supreme Court pages): bodies are left out of the baked background and shipped as sprites, so the player can
#   make them breathe; adds each puppet's eyes-closed head (heads[5]) where ASSETS has it, the wall clock's position,
#   the gallery audience (ASSETS/gallery/) and the mouse (ASSETS/mouse.json). The page enables each behaviour with page.motion.
import argparse, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import layers as L

ap = argparse.ArgumentParser()
ap.add_argument('assets'); ap.add_argument('meta'); ap.add_argument('out')
ap.add_argument('--advocates', required=True)
ap.add_argument('--bench', default=None, help='comma-separated keys in wide-shot order (default: the Supreme Court bench)')
ap.add_argument('--bench-shift', type=int, default=70, help='pixels to push the bench close-ups down (0 for the interview)')
ap.add_argument('--motion', action='store_true', help='sprite bodies, blink heads, clock, gallery and mouse for the Supreme Court player')
ap.add_argument('--jpeg-quality', type=int, default=86)
ap.add_argument('--webp-quality', type=int, default=88)
a = ap.parse_args()
advocates = [x for x in a.advocates.split(',') if x]
if a.bench:
    BENCH_ORDER = [x for x in a.bench.split(',') if x]
else:
    from characters import BENCH_ORDER
L.configure(a.assets, json.load(open(a.meta)))
GALLERY_DIR = os.path.join(a.assets, 'gallery')
GALLERY = None
if a.motion and os.path.exists(os.path.join(GALLERY_DIR, 'gallery.json')):
    GALLERY = json.load(open(os.path.join(GALLERY_DIR, 'gallery.json')))
if a.motion:
    VC = L.build_vcams(BENCH_ORDER, advocates, bench_shift=a.bench_shift, blink=True, bodies=False,
                       advocate_plate=os.path.join(GALLERY_DIR, GALLERY['plate']) if GALLERY else None)
else:
    VC = L.build_vcams(BENCH_ORDER, advocates, bench_shift=a.bench_shift)
os.makedirs(os.path.join(a.out, 'img'), exist_ok=True)
WIDE_FAMILY = {'wide', 'bench_left', 'bench_right', 'bench_center'}


def unpremul(pm):
    """premultiplied float RGBA -> straight uint8 RGBA"""
    al = pm[..., 3:4]
    rgb = np.where(al > 0, pm[..., :3] * 255.0 / np.maximum(al, 1e-6), 0)
    return np.clip(np.concatenate([rgb, al], -1) + 0.5, 0, 255).astype(np.uint8)


def pack(sprites, max_w=2048, gap=2):
    """Shelf-pack [(id, array)] -> atlas array and {id: [x, y, w, h]}"""
    order = sorted(sprites, key=lambda s: -s[1].shape[0])
    x = y = shelf_h = 0
    pos, width = {}, 0
    for sid, im in order:
        h, w = im.shape[:2]
        if x + w > max_w:
            x, y, shelf_h = 0, y + shelf_h + gap, 0
        pos[sid] = [x, y, w, h]
        x += w + gap
        shelf_h = max(shelf_h, h)
        width = max(width, x)
    atlas = np.zeros((y + shelf_h, width, 4), np.uint8)
    for sid, im in sprites:
        px, py, w, h = pos[sid]
        atlas[py:py + h, px:px + w] = im
    return atlas, pos


def body_sprite(layer):
    """the body layer cut to the frame: (straight RGBA uint8, x, y) or None"""
    img, x, y = layer.img, layer.x, layer.y
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(L.W, x + w), min(L.H, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    return unpremul(img[y0 - y:y1 - y, x0 - x:x1 - x]), x0, y0


def save_atlas(sprites, path):
    atlas, pos = pack(sprites)
    Image.fromarray(atlas).save(os.path.join(a.out, path), 'WEBP', quality=a.webp_quality, method=5)
    return pos, os.path.getsize(os.path.join(a.out, path))


layout = dict(W=L.W, H=L.H, vcams={})
total = 0
for name, v in VC.items():
    base = np.clip(v.base + 0.5, 0, 255).astype(np.uint8)
    bpath = f'img/b_{name}.jpg'
    Image.fromarray(base).save(os.path.join(a.out, bpath), quality=a.jpeg_quality, optimize=True, progressive=True)
    sprites, chars = [], {}
    for n, c in v.chars.items():
        info = dict(hx=c['hx'], hy=c['hy'], px=round(c['pivot'][0], 2), py=round(c['pivot'][1], 2),
                    unit=round(c['unit'], 3), heads={})
        for k, pm in sorted(c['heads'].items()):
            sprites.append(((n, 'h', k), unpremul(pm)))
        if a.motion:
            bs = body_sprite(c['body'])
            if bs:
                sprites.append(((n, 'b', 0), bs[0]))
                info['body_xy'] = [bs[1], bs[2]]
        elif name in WIDE_FAMILY and n in advocates:
            sprites.append(((n, 'b', 0), unpremul(c['body'].img)))
            info['body_xy'] = [c['body'].x, c['body'].y]
        chars[n] = info
    atlas, pos = pack(sprites)
    for (n, kind, k), r in pos.items():
        if kind == 'h':
            chars[n]['heads'][k] = r
        else:
            chars[n]['body'] = r
    for n in chars:  # heads as a list indexed by mouth state; missing states fall back to state 0
        hs = chars[n]['heads']
        chars[n]['heads'] = [hs.get(k, hs[min(hs)]) for k in range(5)]
        if 5 in hs:   # eyes closed, jaw shut: the player's blink
            chars[n]['heads'].append(hs[5])
    apath = f'img/a_{name}.webp'
    Image.fromarray(atlas).save(os.path.join(a.out, apath), 'WEBP', quality=a.webp_quality, method=5)
    layout['vcams'][name] = dict(base=bpath, atlas=apath, chars=chars, wide=name in WIDE_FAMILY)
    if a.motion:
        vc = layout['vcams'][name]
        if GALLERY and name in advocates:
            vc['watchers'] = True
        if name in WIDE_FAMILY:
            vc['xf'] = [v.rect[0], v.rect[1], v.scale, v.shift_y]   # wide-render pixel -> this camera: ((x - xf0) * xf2, (y - xf1) * xf2 + xf3)
            ck = L.meta['wide'].get('clock')
            if ck:   # where the wall clock sits in this camera, for the live hands
                cx, cy = v.to_vc(ck[0], ck[1])
                if 0 <= cx <= L.W and 0 <= cy <= L.H:
                    vc['clock'] = [round(cx, 2), round(cy, 2), round(ck[2] * v.scale, 2)]
    total += os.path.getsize(os.path.join(a.out, bpath)) + os.path.getsize(os.path.join(a.out, apath))
if a.motion and GALLERY:
    # the audience behind the advocate: one shared atlas (identical for every case, so a theater page stores it once)
    sprites = []
    for i, pe in enumerate(GALLERY['people']):
        sprites.append((i, L.load_rgba(os.path.join(GALLERY_DIR, pe['file']))))
    pos, size = save_atlas(sprites, 'img/g_gallery.webp')
    total += size
    layout['gallery'] = dict(atlas='img/g_gallery.webp',
                             people=[dict(rect=pos[i], xy=pe['crop'][:2], pivot=pe['pivot']) for i, pe in enumerate(GALLERY['people'])])
MOUSE_JSON = os.path.join(a.assets, 'mouse.json')
if a.motion and os.path.exists(MOUSE_JSON):
    # the mouse, in wide-render pixels (scripts/render_mouse.py): {"anchor": [feet x, feet y], "poses": {pose: {"file": "wide/mouse_<pose>.png",
    # "crop": [x, y, w, h]}}}; a pose may carry its own "anchor"
    mj = json.load(open(MOUSE_JSON))
    sprites, info = [], {}
    for pose, m in (mj.get('poses') or {}).items():
        pth = os.path.join(a.assets, m.get('file') or f'wide/mouse_{pose}.png')
        anchor = m.get('anchor') or mj.get('anchor')
        if not os.path.exists(pth) or not anchor:
            continue
        sprites.append((pose, L.load_rgba(pth)))
        info[pose] = dict(xy=m['crop'][:2], anchor=anchor)
    if sprites:
        pos, size = save_atlas(sprites, 'img/g_mouse.webp')
        total += size
        layout['mouse'] = dict(atlas='img/g_mouse.webp', poses={p: dict(info[p], rect=pos[p]) for p in info})
        for name, vc in layout['vcams'].items():   # which wide-family cameras can see it
            if name in WIDE_FAMILY:
                x0, y0, sc, sy = vc['xf']
                ref = info.get('listen') or next(iter(info.values()))
                fx, fy = (ref['anchor'][0] - x0) * sc, (ref['anchor'][1] - y0) * sc + sy
                vc['mouse'] = bool(0 <= fx <= L.W and 0 <= fy <= L.H)
json.dump(layout, open(os.path.join(a.out, 'layout.json'), 'w'), separators=(',', ':'))
print(f'{len(VC)} cameras, {total / 1e6:.1f} MB of images -> {a.out}')
