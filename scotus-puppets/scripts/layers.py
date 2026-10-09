# Shared 2D layer machinery: load rendered puppet layers, place them in virtual cameras, bake static bases.
# Used by compose.py (MP4) and export_web.py (browser player).
import math, os
import numpy as np
import cv2

W, H = 1280, 720
ASSETS = None   # set by configure()
meta = None


def configure(assets, meta_dict):
    global ASSETS, meta
    ASSETS, meta = assets, meta_dict


# ------------------------------------------------------------------ image helpers
def load_rgba(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.shape[2] == 3:
        im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)


def premul(im):
    a = im[..., 3:4].astype(np.float32) / 255.0
    out = im.astype(np.float32)
    out[..., :3] *= a
    return out  # float32 premultiplied RGBA


def blend(dst, src_pm, x, y):
    """dst float32 HxWx3; src_pm float32 premultiplied RGBA placed at integer (x, y)."""
    h, w = src_pm.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src_pm[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] * (1.0 / 255.0)
    d = dst[y0:y1, x0:x1]
    d *= (1.0 - a)
    d += s[..., :3]


class Layer:
    """A premultiplied RGBA sprite placed in virtual-camera coordinates."""

    def __init__(self, img_pm, x, y):
        self.img, self.x, self.y = img_pm, x, y


# ------------------------------------------------------------------ virtual cameras
class VCam:
    def __init__(self, name, src, rect, shift_y=0, plate_path=None):
        """rect = (x, y, w, h) in source pixels; output is W x H. shift_y moves the shot down (adds headroom).
        plate_path: use this empty-room plate instead of ASSETS/src/plate.png."""
        self.name, self.src = name, src
        self.rect = rect
        self.shift_y = shift_y
        self.scale = W / rect[2]
        self.chars = {}
        plate = load_rgba(plate_path or os.path.join(ASSETS, src, 'plate.png'))[..., :3]
        x, y, w, h = rect
        crop = plate[y:y + h, x:x + w]
        self.plate = cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA if self.scale < 1 else cv2.INTER_CUBIC
                                ).astype(np.float32)
        if shift_y:
            # extend the (blurred, vertical) drapes/columns/chair upward by repeating the top rows
            top = np.repeat(self.plate[:1], shift_y, axis=0)
            top = cv2.GaussianBlur(top, (0, 0), 3) if shift_y > 4 else top
            self.plate = np.vstack([top, self.plate[:H - shift_y]])

    def to_vc(self, px, py):
        return (px - self.rect[0]) * self.scale, (py - self.rect[1]) * self.scale + self.shift_y

    def add_char(self, n, heads=range(5)):
        m = meta[self.src][n]
        cx0, cy0, cx1, cy1 = m['crop']
        try:
            body = load_rgba(os.path.join(ASSETS, self.src, f'{n}_body.png'))
        except FileNotFoundError:
            return
        hs = {}
        for k in heads:
            p = os.path.join(ASSETS, self.src, f'{n}_head{k}.png')
            if os.path.exists(p):
                hs[k] = load_rgba(p)
        if not hs:
            return
        # common trim box across head states, then scale into VC space
        def place(im, pad=0):
            al = im[..., 3]
            ys, xs = np.nonzero(al > 0)
            if len(xs) == 0:
                return None
            return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

        bb = [place(h) for h in hs.values()]
        bb = [b for b in bb if b]
        hx0, hy0 = min(b[0] for b in bb), min(b[1] for b in bb)
        hx1, hy1 = max(b[2] for b in bb), max(b[3] for b in bb)
        pad = int(0.12 * max(hx1 - hx0, hy1 - hy0)) + 4
        s = self.scale

        def scaled(im, x0, y0, x1, y1, pad):
            sub = im[y0:y1, x0:x1]
            sub = cv2.copyMakeBorder(sub, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
            pm = premul(sub)
            if abs(s - 1) > 1e-3:
                pm = cv2.resize(pm, (max(1, round(pm.shape[1] * s)), max(1, round(pm.shape[0] * s))),
                                interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
            vx, vy = self.to_vc(cx0 + x0 - pad, cy0 + y0 - pad)
            return pm, int(round(vx)), int(round(vy))

        heads_pm = {}
        for k, im in hs.items():
            pm, vx, vy = scaled(im, hx0, hy0, hx1, hy1, pad)
            heads_pm[k] = pm
        b = place(body)
        body_pm, bx, by = scaled(body, *b, 2)
        piv = self.to_vc(*m['pivot'])
        hc = self.to_vc(*m['head'])
        unit = math.hypot(hc[0] - piv[0], hc[1] - piv[1]) / 0.13  # px per metre of head
        # soft drop shadow (static) from body + resting head
        sil = np.zeros((H, W), np.float32)
        for pm, x, y in ((body_pm, bx, by), (heads_pm[min(heads_pm)], vx, vy)):
            h_, w_ = pm.shape[:2]
            x0, y0 = max(0, x), max(0, y); x1, y1 = min(W, x + w_), min(H, y + h_)
            if x1 > x0 and y1 > y0:
                sil[y0:y1, x0:x1] = np.maximum(sil[y0:y1, x0:x1], pm[y0 - y:y1 - y, x0 - x:x1 - x, 3] / 255.0)
        self.chars[n] = dict(body=Layer(body_pm, bx, by), heads=heads_pm, hx=vx, hy=vy,
                             pivot=(piv[0] - vx, piv[1] - vy), unit=unit, sil=sil)

    def bake(self, shadow=True, exclude=(), bodies=True):
        """Plate + soft shadows (+ bodies). bodies=False leaves the bodies out, for pages that draw them as sprites."""
        base = self.plate.copy()
        if shadow:
            sh = np.zeros((H, W), np.float32)
            for n, c in self.chars.items():
                if n in exclude:
                    continue
                sig = max(2.0, 0.035 * c['unit'] * 0.35 * 2)
                off = int(round(0.02 * c['unit'])), int(round(0.012 * c['unit']))
                s = cv2.GaussianBlur(c['sil'], (0, 0), sig)
                M = np.float32([[1, 0, off[0]], [0, 1, off[1]]])
                s = cv2.warpAffine(s, M, (W, H))
                sh = np.maximum(sh, s)
            base *= (1 - 0.42 * sh)[..., None]
        for n, c in self.chars.items():
            if n in exclude or not bodies:
                continue
            blend(base, c['body'].img, c['body'].x, c['body'].y)
        self.base = base

    def warp_head(self, dst, n, state, th, dx, dy):
        c = self.chars[n]
        im = c['heads'].get(state, c['heads'][min(c['heads'])])
        lx, ly = c['pivot']
        cs, sn = math.cos(th), math.sin(th)
        # output = R (p - L) + L + D
        M = np.float32([[cs, -sn, lx - cs * lx + sn * ly + dx], [sn, cs, ly - sn * lx - cs * ly + dy]])
        out = cv2.warpAffine(im, M, (im.shape[1], im.shape[0]), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        blend(dst, out, c['hx'], c['hy'])


def wide_rect(names, margin_frac=0.18):
    """16:9 rect in wide-source pixels around the given justices' heads."""
    m = meta['wide']
    xs = [m[n]['head'][0] for n in names]
    ys = [m[n]['head'][1] for n in names]
    x0, x1 = min(xs), max(xs)
    w = (x1 - x0) * (1 + 2 * margin_frac) + 260
    h = w * 9 / 16
    cx, cy = (x0 + x1) / 2, sum(ys) / len(ys) + h * 0.12
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    sw, shh = meta['wide']['res']
    x = min(max(0, x), sw - int(w)); y = min(max(0, y), shh - int(h))
    return (x, y, int(round(w)), int(round(h)))




def build_vcams(bench_order, advocates, only=None, log=print, bench_shift=70, blink=False, bodies=True, advocate_plate=None):
    """All virtual cameras: a close-up per justice/advocate and four views cut from the wide master.
    bench_shift: pixels the bench close-ups are moved down (headroom added by extending the plate upward);
    the Supreme Court close-ups are framed tight and use 70, the breakfast interview is framed properly and uses 0.
    blink: also load each puppet's eyes-closed head layer (state 5) where it exists.
    bodies=False: bake without the bodies (the page draws them as sprites so they can breathe).
    advocate_plate: shared empty-room plate for the advocate close-ups."""
    VC = {}
    heads = range(6) if blink else range(5)
    for n in bench_order + advocates:
        if only and n not in only:
            continue
        v = VCam(n, n, (0, 0, W, H), shift_y=bench_shift if n in bench_order else 0,
                 plate_path=advocate_plate if n in advocates else None)
        v.add_char(n, heads=heads)
        v.bake(shadow=True, bodies=bodies)
        VC[n] = v
    sw, shh = meta['wide']['res']
    for name, rect in (('wide', (0, 0, sw, shh)), ('bench_left', wide_rect(bench_order[:5])),
                       ('bench_right', wide_rect(bench_order[4:])), ('bench_center', wide_rect(bench_order[2:7]))):
        v = VCam(name, 'wide', rect)
        for n in bench_order:
            v.add_char(n, heads=heads)
        for n in advocates:
            v.add_char(n, heads=[0, 5] if blink else [0])
        v.bake(shadow=True, exclude=advocates, bodies=bodies)
        VC[name] = v
    return VC
