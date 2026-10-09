import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import bpy
import court as C
from characters import ADVOCATES
sc = C.scene_setup(int(os.environ.get('SAMPLES', 24)))
t = time.time()
G, cast = C.build_world(with_gallery=True)
cams = C.cameras(cast)
print('built', round(time.time() - t, 1), flush=True)
out = os.environ['OUT']
for name in os.environ.get('CAMS', 'wide,roberts,thomas,' + ADVOCATES[0]).split(','):
    hide_gal = name == 'wide'
    for o in G['gallery']:
        o.hide_render = hide_gal
    for pp in G['people']:
        for o in pp['objs']:
            o.hide_render = hide_gal
    # one advocate at the lectern: the one whose own shot this is, otherwise the first advocate
    for adv in ADVOCATES:
        show = (name == adv) or (name not in ADVOCATES and adv == ADVOCATES[0])
        for o in cast[adv]['objs']:
            o.hide_render = not show
    sc.camera = cams[name]
    sc.render.resolution_x, sc.render.resolution_y = (1280, 720)
    sc.render.filepath = f'{out}/{name}.png'
    t = time.time(); bpy.ops.render.render(write_still=True); print('done', name, round(time.time() - t, 1), flush=True)
