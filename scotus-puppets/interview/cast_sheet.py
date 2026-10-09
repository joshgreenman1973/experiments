# Labelled cast sheet from the lineup tiles. Usage: python cast_sheet.py LINEUP_DIR OUT.png
import sys, os
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cast import CAST, ORDER
d, out = sys.argv[1], sys.argv[2]
ims = [Image.open(f'{d}/{n}.png').convert('RGB') for n in ORDER]
w, h = ims[0].size
cols = 4
rows = (len(ims) + cols - 1) // cols
lab = 62
T = Image.new('RGB', (w * cols, (h + lab) * rows), (36, 33, 31))
fb = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Bold.otf', 22)
fr = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Regular.otf', 16)
dr = ImageDraw.Draw(T)
for i, (n, im) in enumerate(zip(ORDER, ims)):
    x, y = (i % cols) * w, (i // cols) * (h + lab)
    T.paste(im, (x, y))
    dr.text((x + 12, y + h + 8), f'{i + 1}. {CAST[n]["display"]}', fill='white', font=fb)
    dr.text((x + 12, y + h + 36), CAST[n]['role'], fill=(200, 192, 180), font=fr)
T.save(out)
print(out, T.size)
