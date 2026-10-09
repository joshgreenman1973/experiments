import sys
from PIL import Image, ImageDraw, ImageFont
d, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
names = sys.argv[4:]
ims = [Image.open(f'{d}/{n}.png').convert('RGB') for n in names]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
T = Image.new('RGB', (w * cols, h * rows), (30, 30, 30))
f = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Bold.otf', 22)
for i, (n, im) in enumerate(zip(names, ims)):
    x, y = (i % cols) * w, (i // cols) * h
    T.paste(im, (x, y)); ImageDraw.Draw(T).text((x + 10, y + 8), n, fill='white', font=f)
T.save(out)
