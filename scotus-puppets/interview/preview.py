# Low-res preview of the breakfast set with all puppets in place.
# Usage: OUT=dir [SAMPLES=24] [CAMS=wide,lawler] [RES=960x540] python preview.py
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); sys.path.insert(0, HERE)
import bpy
import breakfast as B
from cast import ORDER

sc = B.scene_setup(int(os.environ.get('SAMPLES', 24)))
t = time.time()
work = os.environ.get('WORK', os.path.join(HERE, '..', 'work'))
os.makedirs(work, exist_ok=True)
G, cast, set_objs = B.build_world(work, with_food=os.environ.get('FOOD', '1') == '1')
cams, yaw = B.cameras(cast)
print('built', round(time.time() - t, 1), flush=True)
out = os.environ['OUT']
os.makedirs(out, exist_ok=True)
rx, ry = (int(v) for v in os.environ.get('RES', '1280x720').split('x'))
for name in os.environ.get('CAMS', 'wide,lawler,smith').split(','):
    for n in ORDER:
        cast[n]['head'].rotation_euler = (0, 0, yaw.get((name, n), yaw.get(('wide', n), 0.0)) if name == 'wide' or name == n else yaw[('wide', n)])
    sc.camera = cams[name]
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.filepath = f'{out}/{name}.png'
    t = time.time(); bpy.ops.render.render(write_still=True); print('done', name, round(time.time() - t, 1), flush=True)
