# Render the felt-mouse Easter egg for the wide shot: one transparent sprite per pose, cropped like the puppet layers.
# Usage: python render_mouse.py OUTDIR [pose ...]      (OUTDIR = the assets folder that holds wide/plate.png and meta.json)
# Writes OUTDIR/wide/mouse_<pose>.png, OUTDIR/mouse.json and, next to OUTDIR, mouse_check.png (poses over the plate).
# Env: S_LAYER samples (as render_assets.py, default 64), FORCE=1 to re-render existing sprites,
#      MOUSE_XY="x,y" world position on the counsel table, MOUSE_SIZE scale (default mouse.SIZE).
#
# mouse.json: {"cam": "wide", "res": [2560, 1440], "anchor": [x, y] (the feet point, wide-render pixels),
#              "crop": [x, y, w, h] (the one box every sprite is cropped to), "height_px": ear tips to feet,
#              "poses": {pose: {"file": "wide/mouse_<pose>.png" (relative to OUTDIR), "crop": [x, y, w, h],
#                               "bbox": [x, y, w, h] of the opaque mouse}}}
# All coordinates are in the 2560x1440 wide render. Blit a sprite at its crop x,y (scaled with the frame); the mouse
# stands on `anchor`. Every pose shares the same crop, so swapping poses never shifts the body.
#
# Same set, lights, camera, AgX view transform, exposure (0 EV for the wide shot) and samples as render_assets.py.
# Occlusion: every piece of set geometry is a holdout, exactly as for the puppet layers, EXCEPT the counsel table the
# mouse sits on. That table is a Cycles shadow catcher, so the sprite carries the real soft contact shadow of the
# scene's own area lights (and any bounce light), as semi-transparent dark pixels around the feet; the faint tail of
# the shadow is faded to nothing at the crop edges. Puppets and audience are hidden, as in the plate, and never built:
# build_world is called with puppet.build_puppet stubbed out (they are invisible in the wide plate, and building them
# costs ~4 GB and half a minute). FULL_WORLD=1 builds everything.
# A plate check re-renders the corner without the mouse and compares it with wide/plate.png, so a changed set, light or
# camera in court.py is reported instead of silently drifting.
import sys, os, json, time, math
sys.path.insert(0, os.path.dirname(__file__))

OUT = sys.argv[1]
FILT = sys.argv[2:]
WIDE_RES = (2560, 1440)
S_LAYER = int(os.environ.get('S_LAYER', 64))
FORCE = os.environ.get('FORCE') == '1'
TABLE = 'counsel_table-1'                  # the left counsel table, lower-left corner of the wide frame
MARGIN = 16                                # same margin as objs_bbox in render_assets.py
D = os.path.join(OUT, 'wide')
JSON = os.path.join(OUT, 'mouse.json')
CHECK = os.environ.get('CHECK') or os.path.join(os.path.dirname(os.path.abspath(OUT)), 'mouse_check.png')

import mouse as M

POSES = [p for p in M.POSES if not FILT or p in FILT]
todo = [p for p in POSES if FORCE or not os.path.exists(os.path.join(D, f'mouse_{p}.png'))]


def check_image(info):
    """Contact sheet: every pose over the plate (1280-frame size and 4x), plus the whole frame."""
    from PIL import Image, ImageDraw
    plate = Image.open(os.path.join(D, 'plate.png')).convert('RGB')
    ax, ay = info['anchor']
    comps = {}
    for p, v in info['poses'].items():
        im = plate.copy()
        sp = Image.open(os.path.join(OUT, v['file'])).convert('RGBA')
        im.paste(sp, (v['crop'][0], v['crop'][1]), sp)
        comps[p] = im
    names = [p for p in M.POSES if p in comps]
    if not names:
        return
    W = 1680
    x0 = max(0, min(int(ax - 200), 2560 - 400)); y0 = max(0, min(int(ay - 240), 1440 - 300))
    reg = (x0, y0, x0 + 400, y0 + 300)                 # 400 x 300 px of the 2560 render
    sheet = Image.new('RGB', (W, 720 + 2 * 600 + 4), (24, 22, 22))
    d = ImageDraw.Draw(sheet)
    sheet.paste(comps[names[0]].resize((1280, 720), Image.LANCZOS), (0, 0))
    d.rectangle([reg[0] / 2, reg[1] / 2, reg[2] / 2, reg[3] / 2], outline=(255, 255, 0))
    d.text((10, 8), f"1280x720 frame, {names[0]}; anchor {ax:.0f},{ay:.0f} (2560 px); yellow box = the zoom region", fill=(255, 255, 255))
    for i, p in enumerate(names):          # actual size in the 1280 frame
        z = comps[p].crop(reg).resize((200, 150), Image.LANCZOS)
        x, y = 1280 + (i % 2) * 200, (i // 2) * 150
        sheet.paste(z, (x, y))
        d.text((x + 4, y + 4), p, fill=(255, 255, 255))
    d.text((1284, 306), 'actual size in the 1280x720 frame', fill=(255, 255, 255))
    for i, p in enumerate(names):          # 4x of the 1280 frame
        z = comps[p].crop(reg).resize((800, 600), Image.LANCZOS)
        x, y = (i % 2) * 800, 720 + 4 + (i // 2) * 600
        sheet.paste(z, (x, y))
        d.text((x + 8, y + 6), f'{p}  (4x of the 1280 frame)', fill=(255, 255, 255))
    sheet.save(CHECK)
    print('check image', CHECK, flush=True)


if todo:
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    import court as C

    import puppet as PP

    def stub_puppet(name, spec, root_loc=(0, 0, 0), root_rot_z=0.0, body_h=0.55, **kw):
        root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root)
        root.location = root_loc
        head = bpy.data.objects.new(name + '_head', None); bpy.context.collection.objects.link(head)
        head.parent = root; head.location = (0, 0, body_h)
        return dict(root=root, head=head, jaw=head, objs=[root, head], spec=spec)

    if os.environ.get('FULL_WORLD') != '1':
        PP.build_puppet = stub_puppet
    sc = C.scene_setup(S_LAYER)
    t0 = time.time()
    G, cast = C.build_world(with_gallery=True)
    cams = C.cameras(cast)
    cam = cams['wide']
    sc.render.resolution_x, sc.render.resolution_y = WIDE_RES     # projections below depend on the aspect ratio
    bpy.context.view_layer.update()
    print('built', round(time.time() - t0, 1), flush=True)

    set_objs = G['bench'] + G['lectern'] + G['set'] + G['chairs'] + G['gallery']
    table = bpy.data.objects[TABLE]
    top_z = max((table.matrix_world @ Vector(c)).z for c in table.bound_box)
    xy = [float(v) for v in os.environ.get('MOUSE_XY', '-1.50,-4.85').split(',')]
    SPOT = (xy[0], xy[1], top_z)
    key = bpy.data.objects['key_bench']

    # puppets and audience are not in the plate: hide them (their shadows would not be in the plate either)
    for pp in list(cast.values()) + list(G['people']):
        for o in pp['objs']:
            o.hide_render = True
    for o in set_objs:
        o.is_holdout = o is not table
    table.is_shadow_catcher = True

    def proj(co):
        v = world_to_camera_view(sc, cam, Vector(co))
        return v.x * WIDE_RES[0], (1 - v.y) * WIDE_RES[1], v.z

    def objs_bbox(objs, margin=MARGIN, extra=()):
        """Pixel box around the world-space bounds of objs (clamped to the frame), as in render_assets.py."""
        xs, ys = [], []
        for o in objs:
            if o.type not in ('MESH', 'CURVES'):
                continue
            for c in o.bound_box:
                x, y, _ = proj(o.matrix_world @ Vector(c))
                xs.append(x); ys.append(y)
        for co in extra:
            x, y, _ = proj(co)
            xs.append(x); ys.append(y)
        return [max(0, int(min(xs)) - margin), max(0, int(min(ys)) - margin),
                min(WIDE_RES[0], int(max(xs)) + margin), min(WIDE_RES[1], int(max(ys)) + margin)]

    def render(path, crop, transparent=True):
        sc.camera = cam
        sc.view_settings.exposure = 0.0
        sc.render.resolution_x, sc.render.resolution_y = WIDE_RES
        sc.cycles.samples = S_LAYER
        sc.render.film_transparent = transparent
        x0, y0, x1, y1 = crop
        sc.render.use_border = True; sc.render.use_crop_to_border = True
        sc.render.border_min_x = x0 / WIDE_RES[0]; sc.render.border_max_x = x1 / WIDE_RES[0]
        sc.render.border_min_y = 1 - y1 / WIDE_RES[1]; sc.render.border_max_y = 1 - y0 / WIDE_RES[1]
        sc.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print('done', os.path.relpath(path, OUT), round(time.time() - t, 1), flush=True)

    def fade_edges(path, crop, band=22):
        """The soft shadow has a long faint tail: fade alpha to 0 over `band` px at crop edges that are not the frame edge."""
        from PIL import Image
        import numpy as np
        im = np.array(Image.open(path).convert('RGBA')).astype(np.float32)
        h, w = im.shape[:2]
        x0, y0, x1, y1 = crop
        ramp = lambda n, lo, hi: np.clip(np.minimum(np.arange(n) / band if lo else np.full(n, 9.0),
                                                    (n - 1 - np.arange(n)) / band if hi else np.full(n, 9.0)), 0, 1)
        fx = ramp(w, x0 > 0, x1 < WIDE_RES[0]); fy = ramp(h, y0 > 0, y1 < WIDE_RES[1])
        f = np.outer(fy, fx); f = f * f * (3 - 2 * f)
        im[..., 3] *= f
        Image.fromarray(np.clip(im + 0.5, 0, 255).astype(np.uint8), 'RGBA').save(path)

    os.makedirs(D, exist_ok=True)

    def verify_plate():
        """Render the corner without the mouse, no holdouts/catcher, and compare with wide/plate.png."""
        from PIL import Image
        import numpy as np
        ppath = os.path.join(D, 'plate.png')
        if not os.path.exists(ppath):
            print('plate check skipped (no wide/plate.png)', flush=True)
            return
        ax, ay, _ = proj(SPOT)
        crop = [max(0, int(ax - 200)), max(0, int(ay - 230)), min(WIDE_RES[0], int(ax + 200)), min(WIDE_RES[1], int(ay + 80))]
        for o in set_objs:
            o.is_holdout = False
        table.is_shadow_catcher = False
        tmp = os.path.join(D, '_platecheck.png')
        render(tmp, crop, transparent=False)
        a = np.array(Image.open(tmp).convert('RGB')).astype(float)
        b = np.array(Image.open(ppath).convert('RGB').crop(tuple(crop))).astype(float)
        os.remove(tmp)
        for o in set_objs:
            o.is_holdout = o is not table
        table.is_shadow_catcher = True
        diff = float(np.abs(a - b).mean())
        print(f'plate check: mean abs difference {diff:.2f}/255 ' +
              ('(ok)' if diff < 6 else 'WARNING: the set, lights or wide camera no longer match wide/plate.png'), flush=True)

    anchor = [round(v, 2) for v in proj(SPOT)[:2]]
    info = json.load(open(JSON)) if os.path.exists(JSON) else {}
    info.update(cam='wide', res=list(WIDE_RES), anchor=anchor, world=[round(v, 4) for v in SPOT])
    info.setdefault('poses', {})
    fp = 0.15       # shadow footprint around the feet, metres
    foot = [(SPOT[0] + dx, SPOT[1] + dy, SPOT[2]) for dx in (-fp, fp) for dy in (-fp, fp)]
    size = float(os.environ.get('MOUSE_SIZE', M.SIZE))
    verify_plate()

    # one crop box for every pose (union of the poses' boxes): sprites swap in place with no per-pose offsets, and the
    # parts the poses share (the body) come out pixel-identical, so swapping poses cannot flicker
    boxes = []
    for pose in M.POSES:
        m = M.build_mouse(pose, SPOT, cam.location, key.location, size=size)
        bpy.context.view_layer.update()
        boxes.append(objs_bbox(m['objs'], MARGIN, extra=foot))
        M.remove_mouse(m)
    crop = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    info['crop'] = [crop[0], crop[1], crop[2] - crop[0], crop[3] - crop[1]]
    stale = [p for p in POSES if p in info['poses'] and info['poses'][p]['crop'] != info['crop']]
    todo = [p for p in POSES if p in todo or p in stale]
    from PIL import Image
    import numpy as np
    for pose in todo:
        m = M.build_mouse(pose, SPOT, cam.location, key.location, size=size)
        bpy.context.view_layer.update()
        path = os.path.join(D, f'mouse_{pose}.png')
        render(path, crop)
        fade_edges(path, crop)
        al = np.array(Image.open(path).convert('RGBA'))[..., 3]
        ys, xs = np.where(al > 128)
        info['poses'][pose] = dict(file=f'wide/mouse_{pose}.png', crop=list(info['crop']),
                                   bbox=[crop[0] + int(xs.min()), crop[1] + int(ys.min()),
                                         int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)])
        info['height_px'] = max(info.get('height_px', 0), round(anchor[1] - info['poses'][pose]['bbox'][1], 1))
        json.dump(info, open(JSON, 'w'), indent=1)
        M.remove_mouse(m)
    print('ALL DONE', round(time.time() - t0, 1), flush=True)

info = json.load(open(JSON))
info['poses'] = {p: v for p, v in info['poses'].items() if os.path.exists(os.path.join(OUT, v['file']))}
check_image(info)
