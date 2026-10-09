# Render plates and per-character body/head layers (with jaw states) for every camera.
# Usage: python render_assets.py OUTDIR [job-filter-substring ...]
# Extra passes for the browser player's motion (same OUTDIR; each skips files that exist):
#   BLINK=1    only the eyes-closed head layer {n}_head5.png per puppet and camera (lids over the eyes, jaw shut), cut with the
#              crop that the open-eye renders recorded in OUTDIR/meta.json, so it drops in exactly over heads 0..4.
#   GALLERY=1  the audience behind the advocate: OUTDIR/gallery/plate.png (the lectern background with nobody in the seats),
#              p00.png.. (one layer per visible person, back to front) and gallery.json. Shared by every case.
#              GALLERY_CAM=<advocate key> picks the camera (default: the first advocate in the case config).
import sys, os, json, time, math
sys.path.insert(0, os.path.dirname(__file__))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import court as C
from characters import BENCH_ORDER, ADVOCATES, CHARS

JAW = [0.015, 0.105, 0.195, 0.285, 0.375]
OUT = sys.argv[1]
FILT = sys.argv[2:]
BLINK = bool(os.environ.get('BLINK'))
GALLERY = bool(os.environ.get('GALLERY'))
if BLINK:   # lids that cover the eyes: the cap above the plane then reaches below the pupil
    for _n in list(CHARS):
        CHARS[_n] = dict(CHARS[_n], lid=max(CHARS[_n].get('lid', 0.36), 0.8))
WIDE_RES = (2560, 1440)
MCU_RES = (1280, 720)
S_PLATE, S_LAYER = int(os.environ.get('S_PLATE', 96)), int(os.environ.get('S_LAYER', 64))

sc = C.scene_setup(S_LAYER)
t0 = time.time()
G, cast = C.build_world(with_gallery=True)
cams = C.cameras(cast)
bpy.context.view_layer.update()
print('built', round(time.time() - t0, 1), flush=True)

set_objs = G['bench'] + G['lectern'] + G['set'] + G['chairs'] + G['gallery']
people_objs = [o for pp in G['people'] for o in pp['objs']]


def subtree(o):
    out, st = [o], [o]
    while st:
        x = st.pop()
        for c in x.children:
            out.append(c); st.append(c)
    return out


HEAD = {n: set(subtree(pp['head'])) for n, pp in cast.items()}
BODY = {n: [o for o in pp['objs'] if o not in HEAD[n]] for n, pp in cast.items()}


def reset_vis():
    for o in bpy.data.objects:
        if o.type in ('LIGHT', 'CAMERA'):
            continue
        o.hide_render = False
        o.visible_camera = True
        o.is_holdout = False


def hide(objs):
    for o in objs:
        o.hide_render = True


def holdout(objs):
    for o in objs:
        o.is_holdout = True


def proj(cam, res, co):
    v = world_to_camera_view(sc, cam, Vector(co))
    return v.x * res[0], (1 - v.y) * res[1], v.z


def char_bbox(cam, res, n, below):
    pp = cast[n]
    h = pp['head'].matrix_world.translation
    r = pp['root'].matrix_world.translation
    pts = []
    for dx in (-0.42, 0.42):
        for dy in (-0.45, 0.35):
            for z in (h.z + 0.32, below):
                pts.append((r.x + dx, r.y + dy, z))
    P = [proj(cam, res, p) for p in pts]
    x0 = max(0, int(min(p[0] for p in P)) - 12); x1 = min(res[0], int(max(p[0] for p in P)) + 12)
    y0 = max(0, int(min(p[1] for p in P)) - 12); y1 = min(res[1], int(max(p[1] for p in P)) + 12)
    return [x0, y0, x1, y1]


def render(path, cam, res, samples, transparent, crop=None):
    sc.camera = cams[cam]
    sc.view_settings.exposure = -0.35 if cam in ADVOCATES else 0.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.cycles.samples = samples
    sc.render.film_transparent = transparent
    if crop:
        x0, y0, x1, y1 = crop
        sc.render.use_border = True; sc.render.use_crop_to_border = True
        sc.render.border_min_x = x0 / res[0]; sc.render.border_max_x = x1 / res[0]
        sc.render.border_min_y = 1 - y1 / res[1]; sc.render.border_max_y = 1 - y0 / res[1]
    else:
        sc.render.use_border = False
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('done', os.path.relpath(path, OUT), round(time.time() - t, 1), flush=True)


meta_path = os.path.join(OUT, 'meta.json')
meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
# where the wall clock sits in the wide shot (centre and radius in pixels), so the player can draw live hands
_cf = bpy.data.objects.get('clockface')
if _cf is not None:
    _c = _cf.matrix_world.translation
    _p0 = proj(cams['wide'], WIDE_RES, _c)
    _p1 = proj(cams['wide'], WIDE_RES, _c + Vector((0.42 * 0.98, 0, 0)))
    meta.setdefault('wide', {})['clock'] = [round(_p0[0], 2), round(_p0[1], 2), round(abs(_p1[0] - _p0[0]), 2)]


def save_meta():
    json.dump(meta, open(meta_path, 'w'), indent=1)


def job(name):
    if FILT and not any(f in name for f in FILT):
        return False
    return True


def objs_bbox(cam, res, objs, margin=16):
    """Pixel box around the world-space bounds of objs (clamped to the frame)."""
    xs, ys = [], []
    for o in objs:
        if o.type not in ('MESH', 'CURVES'):
            continue
        for c in o.bound_box:
            x, y, _ = proj(cam, res, o.matrix_world @ Vector(c))
            xs.append(x); ys.append(y)
    return [max(0, int(min(xs)) - margin), max(0, int(min(ys)) - margin),
            min(res[0], int(max(xs)) + margin), min(res[1], int(max(ys)) + margin)]


def layer_jobs(cam, res, n, others_holdout, below, crop_on, heads):
    """Body layer + head layers for character n seen from camera cam."""
    d = os.path.join(OUT, cam)
    os.makedirs(d, exist_ok=True)
    if crop_on:
        crop = char_bbox(cams[cam], res, n, below)
    elif CHARS.get(n, {}).get('crop_closeup'):
        # close-up rendered only where the puppet is (jaw fully open, hair included): ~3x fewer pixels to trace
        cast[n]['jaw'].rotation_euler = (JAW[-1], 0, 0)
        bpy.context.view_layer.update()
        crop = objs_bbox(cams[cam], res, cast[n]['objs'])
        cast[n]['jaw'].rotation_euler = (JAW[0], 0, 0)
        bpy.context.view_layer.update()
    else:
        crop = [0, 0, res[0], res[1]]
    pp = cast[n]
    neck = pp['head'].matrix_world @ Vector((0, 0, pp['spec']['zb'] + 0.02))
    hc = pp['head'].matrix_world.translation
    m = meta.setdefault(cam, {}).setdefault(n, {})
    m.update(crop=crop, pivot=proj(cams[cam], res, neck)[:2], head=proj(cams[cam], res, hc)[:2])
    save_meta()
    base = [o for o in bpy.data.objects if o.type not in ('LIGHT', 'CAMERA')]
    # body
    p = os.path.join(d, f'{n}_body.png')
    if job(f'{cam}/{n}_body') and not os.path.exists(p):
        reset_vis()
        hide([o for o in base if o not in set(pp['objs']) and o not in set(set_objs) and o not in others_holdout])
        holdout(set_objs); holdout(others_holdout)
        for o in HEAD[n]:
            o.visible_camera = False
        render(p, cam, res, S_LAYER, True, crop)
    for k in heads:
        p = os.path.join(d, f'{n}_head{k}.png')
        if not job(f'{cam}/{n}_head{k}') or os.path.exists(p):
            continue
        reset_vis()
        hide([o for o in base if o not in set(pp['objs']) and o not in set(set_objs) and o not in others_holdout])
        holdout(set_objs); holdout(others_holdout); holdout(BODY[n])
        pp['jaw'].rotation_euler = (JAW[k], 0, 0)
        render(p, cam, res, S_LAYER, True, crop)
    pp['jaw'].rotation_euler = (JAW[0], 0, 0)


def plate(cam, res, hidden):
    d = os.path.join(OUT, cam)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, 'plate.png')
    if job(f'{cam}/plate') and not os.path.exists(p):
        reset_vis()
        hide(hidden)
        for pp in cast.values():
            pp['jaw'].rotation_euler = (JAW[0], 0, 0)
        render(p, cam, res, S_PLATE, False)
    meta.setdefault(cam, {})['res'] = list(res)
    save_meta()


def run_blink():
    """eyes-closed head layer for every puppet on every camera (BLINK=1)"""
    base = [o for o in bpy.data.objects if o.type not in ('LIGHT', 'CAMERA')]

    def one(cam, res, n, others_holdout):
        p = os.path.join(OUT, cam, f'{n}_head5.png')
        m = meta.get(cam, {}).get(n)
        if not job(f'{cam}/{n}_head5') or os.path.exists(p):
            return
        if not m:
            print('no meta for', cam, n, '- render its open-eye layers first', flush=True)
            return
        pp = cast[n]
        reset_vis()
        hide([o for o in base if o not in set(pp['objs']) and o not in set(set_objs) and o not in others_holdout])
        holdout(set_objs); holdout(others_holdout); holdout(BODY[n])
        pp['jaw'].rotation_euler = (JAW[0], 0, 0)
        render(p, cam, res, S_LAYER, True, m['crop'])

    for n in BENCH_ORDER + ADVOCATES:
        one('wide', WIDE_RES, n, [])
    for i, n in enumerate(BENCH_ORDER):
        nb = []
        for j in (i - 1, i + 1):
            if 0 <= j < 9:
                nb += all_cast_objs[BENCH_ORDER[j]]
        one(n, MCU_RES, n, nb)
    for n in ADVOCATES:
        one(n, MCU_RES, n, [])


def run_gallery():
    """the audience as separate layers over an empty lectern background (GALLERY=1)"""
    import cv2
    import numpy as np
    cam = os.environ.get('GALLERY_CAM') or ADVOCATES[0]
    d = os.path.join(OUT, 'gallery')
    os.makedirs(d, exist_ok=True)
    base = [o for o in bpy.data.objects if o.type not in ('LIGHT', 'CAMERA')]
    p = os.path.join(d, 'plate.png')
    if not os.path.exists(p):
        reset_vis()
        hide(adv_objs + just_objs + people_objs)
        for pp in cast.values():
            pp['jaw'].rotation_euler = (JAW[0], 0, 0)
        render(p, cam, MCU_RES, S_PLATE, False)
    cp = cams[cam].matrix_world.translation
    order = sorted(range(len(G['people'])), key=lambda i: -(G['people'][i]['head'].matrix_world.translation - cp).length)
    out, k = [], 0
    for i in order:   # far to near, so nearer people draw over farther ones
        pp = G['people'][i]
        h = proj(cams[cam], MCU_RES, pp['head'].matrix_world.translation)
        if not (0 <= h[0] <= MCU_RES[0] and 0 <= h[1] <= MCU_RES[1]):
            continue
        crop = objs_bbox(cams[cam], MCU_RES, pp['objs'], margin=24)
        lp = os.path.join(d, f'p{k:02d}.png')
        if not os.path.exists(lp):
            reset_vis()
            mine = set(pp['objs'])
            hide([o for o in base if o not in mine and o not in set(set_objs)])
            holdout(set_objs)
            render(lp, cam, MCU_RES, S_LAYER, True, crop)
        im = cv2.imread(lp, cv2.IMREAD_UNCHANGED)
        ys, xs = np.nonzero(im[..., 3] > 8) if im is not None and im.shape[2] == 4 else ([], [])
        if len(xs) < 150:   # hidden behind the pews
            os.remove(lp)
            continue
        # trim to what shows; pivot = bottom centre of the visible part (where the pew hides the person)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        cv2.imwrite(lp, im[y0:y1, x0:x1])
        out.append(dict(file=f'p{k:02d}.png', crop=[crop[0] + int(x0), crop[1] + int(y0), crop[0] + int(x1), crop[1] + int(y1)],
                        pivot=[crop[0] + (int(x0) + int(x1)) / 2, crop[1] + int(y1)]))
        k += 1
    json.dump(dict(cam=cam, res=list(MCU_RES), plate='plate.png', people=out), open(os.path.join(d, 'gallery.json'), 'w'), indent=1)
    print(len(out), 'people on', cam, flush=True)


all_cast_objs = {n: pp['objs'] for n, pp in cast.items()}
adv_objs = [o for n in ADVOCATES for o in cast[n]['objs']]
just_objs = [o for n in BENCH_ORDER for o in cast[n]['objs']]
if BLINK:
    run_blink()
    print('ALL DONE', round(time.time() - t0, 1), flush=True)
    sys.exit(0)
if GALLERY:
    run_gallery()
    print('ALL DONE', round(time.time() - t0, 1), flush=True)
    sys.exit(0)

# ---- wide (gallery camera): plate without any puppets
plate('wide', WIDE_RES, adv_objs + just_objs + people_objs)
for n in BENCH_ORDER:
    layer_jobs('wide', WIDE_RES, n, [], C.BENCH_TOP - 0.15, True, range(5))
for n in ADVOCATES:
    layer_jobs('wide', WIDE_RES, n, [], 0.0, True, [0])

# ---- justice close-ups: plate shows the neighbours; subject rendered as layers
for i, n in enumerate(BENCH_ORDER):
    plate(n, MCU_RES, list(all_cast_objs[n]) + adv_objs + people_objs)
    nb = []
    for j in (i - 1, i + 1):
        if 0 <= j < 9:
            nb += all_cast_objs[BENCH_ORDER[j]]
    layer_jobs(n, MCU_RES, n, nb, C.BENCH_TOP - 0.3, False, range(5))

# ---- advocate close-ups (camera from the bench): gallery behind
for n in ADVOCATES:
    plate(n, MCU_RES, adv_objs + just_objs)
    layer_jobs(n, MCU_RES, n, [], 0.0, False, range(5))
print('ALL DONE', round(time.time() - t0, 1), flush=True)
