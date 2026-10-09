# Composite checks from rendered layers. Usage: python check.py ASSETS META.json OUTDIR
#   wide_check.png     full-res wide: plate + every person's body and resting head
#   closeups_check.png contact sheet of the seven close-ups (plate + body + head)
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cast import ORDER, CAST
assets, meta_p, out = sys.argv[1:4]
meta = json.load(open(meta_p))


def comp(cam, n_list, head=0, subject=None):
    pl = Image.open(f'{assets}/{cam}/plate.png').convert('RGBA')
    for n in n_list:
        m = meta[cam][n]
        x0, y0 = m['crop'][:2]
        for kind in ('body', f'head{head}'):
            p = f'{assets}/{cam}/{n}_{kind}.png'
            if os.path.exists(p):
                im = Image.open(p).convert('RGBA')
                pl.alpha_composite(im, (x0, y0))
    return pl.convert('RGB')


if os.path.exists(f'{assets}/wide/plate.png'):
    comp('wide', ORDER).save(f'{out}/wide_check.png')
    print('wide_check.png')
thumbs = []
for n in ORDER:
    if os.path.exists(f'{assets}/{n}/plate.png') and os.path.exists(f'{assets}/{n}/{n}_body.png'):
        thumbs.append((n, comp(n, [n], head=2).resize((640, 360), Image.LANCZOS)))
if thumbs:
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    T = Image.new('RGB', (640 * cols, 360 * rows), (30, 30, 30))
    f = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Bold.otf', 20)
    for i, (n, im) in enumerate(thumbs):
        T.paste(im, ((i % cols) * 640, (i // cols) * 360))
        ImageDraw.Draw(T).text(((i % cols) * 640 + 10, (i // cols) * 360 + 8), CAST[n]['display'], fill='white', font=f)
    T.save(f'{out}/closeups_check.png')
    print('closeups_check.png')
