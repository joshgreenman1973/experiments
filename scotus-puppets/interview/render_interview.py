# Render plates and per-person body / head layers (five jaw states) for the breakfast set.
# Same file layout and meta.json format as scripts/render_assets.py, so layers.py and export_web.py work unchanged:
#   OUT/<cam>/plate.png, OUT/<cam>/<name>_body.png, OUT/<cam>/<name>_head{0..4}.png, OUT/meta.json
# Cameras: 'wide' (2560x1440, all seven people) and one close-up per person (1280x720, named after the person).
# Usage: python render_interview.py OUTDIR [job-filter-substring ...]
#   env: S_PLATE (48), S_LAYER (32), WORK (scratch dir for generated textures), THREADS (cycles threads, 0 = all),
#        META_OUT (meta.json path; default OUTDIR/meta.json), FOOD=0 to leave the food out, RES_SCALE (test passes)
# Jobs are named like 'wide/plate', 'wide/lawler_body', 'lawler/lawler_head3'; a filter keeps jobs containing it.
# A filter that matches nothing (e.g. __none__) renders nothing but still writes the complete meta.json (render-free pass).
import sys, os, json, time, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); sys.path.insert(0, HERE)
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import breakfast as B
from cast import ORDER

JAW = B.JAW  # = render_assets.JAW
OUT = sys.argv[1]
FILT = sys.argv[2:]
RS = float(os.environ.get('RES_SCALE', 1.0))  # < 1 for quick test passes
WIDE_RES = (int(2560 * RS), int(1440 * RS))
MCU_RES = (int(1280 * RS), int(720 * RS))
S_PLATE, S_LAYER = int(os.environ.get('S_PLATE', 48)), int(os.environ.get('S_LAYER', 32))
WORK = os.environ.get('WORK') or os.path.join(HERE, '..', 'work')
os.makedirs(WORK, exist_ok=True)

sc = B.scene_setup(S_LAYER)
if int(os.environ.get('THREADS', 0)):
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = int(os.environ['THREADS'])
t0 = time.time()
G, cast, set_objs = B.build_world(WORK, with_food=os.environ.get('FOOD', '1') == '1')
cams, YAW = B.cameras(cast)
bpy.context.view_layer.update()
print('built', round(time.time() - t0, 1), flush=True)

people_objs = {n: list(pp['objs']) for n, pp in cast.items()}
set_set = set(set_objs)


def subtree(o):
    out, st = [o], [o]
    while st:
        x = st.pop()
        for c in x.children:
            out.append(c); st.append(c)
    return out


HEAD = {n: set(subtree(pp['head'])) for n, pp in cast.items()}
BODY = {n: [o for o in pp['objs'] if o not in HEAD[n]] for n, pp in cast.items()}
RENDERABLE = [o for o in bpy.data.objects if o.type not in ('LIGHT', 'CAMERA')]


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


def set_pose(cam, subject=None, jaw=0):
    """Head yaw for this camera (the subject faces a close-up camera; everyone else keeps the wide-shot yaw) and jaw state."""
    for n, pp in cast.items():
        key = (cam, n) if (cam == 'wide' or n == subject) else ('wide', n)
        pp['head'].rotation_euler = (0.0, 0.0, YAW[key])
        pp['jaw'].rotation_euler = (JAW[jaw], 0, 0)
    bpy.context.view_layer.update()


def objs_bbox(cam, res, objs, margin=18):
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


def render(path, cam, res, samples, transparent, crop=None):
    sc.camera = cams[cam]
    sc.view_settings.exposure = 0.0
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


meta_path = os.environ.get('META_OUT') or os.path.join(OUT, 'meta.json')
try:
    meta = json.load(open(meta_path))
except (OSError, ValueError):
    meta = {}


def save_meta():
    json.dump(meta, open(meta_path, 'w'), indent=1)


def job(name):
    return not FILT or any(f in name for f in FILT)


def layer_jobs(cam, res, n, heads):
    """Body layer + head layers for person n seen from camera cam (others are holdouts, or in the plate)."""
    d = os.path.join(OUT, cam)
    os.makedirs(d, exist_ok=True)
    pp = cast[n]
    i = ORDER.index(n)
    # close-ups: only the neighbours two seats either way can overlap the frame; hide the rest
    if cam == 'wide':
        others = [m for m in ORDER if m != n]
        far = []
    else:
        others = [m for m in ORDER if m != n and abs(ORDER.index(m) - i) <= 2]
        far = [m for m in ORDER if m != n and abs(ORDER.index(m) - i) > 2]
    other_objs = [o for m in others for o in people_objs[m]]
    far_objs = [o for m in far for o in people_objs[m]]
    # crop: where the puppet is, with the jaw fully open and the camera's head yaw (meta must match the renders)
    set_pose(cam, n, jaw=len(JAW) - 1)
    crop = objs_bbox(cams[cam], res, pp['objs'])
    set_pose(cam, n, jaw=0)
    neck = pp['head'].matrix_world @ Vector((0, 0, pp['spec']['zb'] + 0.02))
    hc = pp['head'].matrix_world.translation
    m = meta.setdefault(cam, {}).setdefault(n, {})
    m.update(crop=crop, pivot=proj(cams[cam], res, neck)[:2], head=proj(cams[cam], res, hc)[:2])
    save_meta()
    own = set(pp['objs'])
    p = os.path.join(d, f'{n}_body.png')
    if job(f'{cam}/{n}_body') and not os.path.exists(p):
        reset_vis()
        hide(far_objs)
        hide([o for o in RENDERABLE if o not in own and o not in set_set and o not in set(other_objs)
              and o not in set(far_objs)])
        holdout(set_objs); holdout(other_objs)
        for o in HEAD[n]:
            o.visible_camera = False
        render(p, cam, res, S_LAYER, True, crop)
    for k in heads:
        p = os.path.join(d, f'{n}_head{k}.png')
        if not job(f'{cam}/{n}_head{k}') or os.path.exists(p):
            continue
        reset_vis()
        hide(far_objs)
        hide([o for o in RENDERABLE if o not in own and o not in set_set and o not in set(other_objs)
              and o not in set(far_objs)])
        holdout(set_objs); holdout(other_objs); holdout(BODY[n])
        set_pose(cam, n, jaw=k)
        render(p, cam, res, S_LAYER, True, crop)
    set_pose(cam, n, jaw=0)


def plate(cam, res, hidden):
    d = os.path.join(OUT, cam)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, 'plate.png')
    if job(f'{cam}/plate') and not os.path.exists(p):
        reset_vis()
        hide(hidden)
        render(p, cam, res, S_PLATE, False)
    meta.setdefault(cam, {})['res'] = list(res)
    save_meta()


all_people = [o for n in ORDER for o in people_objs[n]]

# ---- wide: plate without anybody, then every person's layers with all the others as holdouts
set_pose('wide')
plate('wide', WIDE_RES, all_people)
for n in ORDER:
    layer_jobs('wide', WIDE_RES, n, range(5))

# ---- close-ups: the plate shows the neighbours (and everybody else in range); the subject is rendered as layers
for n in ORDER:
    set_pose(n, n)
    plate(n, MCU_RES, people_objs[n])
    layer_jobs(n, MCU_RES, n, range(5))
print('ALL DONE', round(time.time() - t0, 1), flush=True)
