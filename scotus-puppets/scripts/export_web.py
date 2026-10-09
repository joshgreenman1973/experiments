# Export the virtual cameras as browser-ready images: one baked background (plate + bodies + shadows) per camera
# and one sprite sheet per camera holding every head pose, plus a layout file the player reads.
# Usage: python export_web.py ASSETS META.json OUTDIR --advocates key1,key2,...
import argparse, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import layers as L
from characters import BENCH_ORDER

ap = argparse.ArgumentParser()
ap.add_argument('assets'); ap.add_argument('meta'); ap.add_argument('out')
ap.add_argument('--advocates', required=True)
ap.add_argument('--jpeg-quality', type=int, default=86)
ap.add_argument('--webp-quality', type=int, default=88)
a = ap.parse_args()
advocates = [x for x in a.advocates.split(',') if x]
L.configure(a.assets, json.load(open(a.meta)))
VC = L.build_vcams(BENCH_ORDER, advocates)
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
        if name in WIDE_FAMILY and n in advocates:
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
    apath = f'img/a_{name}.webp'
    Image.fromarray(atlas).save(os.path.join(a.out, apath), 'WEBP', quality=a.webp_quality, method=5)
    layout['vcams'][name] = dict(base=bpath, atlas=apath, chars=chars, wide=name in WIDE_FAMILY)
    total += os.path.getsize(os.path.join(a.out, bpath)) + os.path.getsize(os.path.join(a.out, apath))
json.dump(layout, open(os.path.join(a.out, 'layout.json'), 'w'), separators=(',', ':'))
print(f'{len(VC)} cameras, {total / 1e6:.1f} MB of images -> {a.out}')
