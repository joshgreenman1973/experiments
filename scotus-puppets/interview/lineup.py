# Lineup of the seven puppets (like scripts/lineup.py). Usage: OUT=dir [SAMPLES=32 RX=420 RY=480] python lineup.py [-- names...]
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); sys.path.insert(0, HERE)
import bpy
import puppet as P
from proto import reset, area, camera
from cast import CAST, ORDER
names = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ORDER
out = os.environ['OUT']
os.makedirs(out, exist_ok=True)
for n in names:
    sc = reset()
    sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.42, 0.34, 1)
    pp = P.build_puppet(n, dict(CAST[n]), body_h=0.55, seed=1000 + ORDER.index(n))
    pp['jaw'].rotation_euler = (float(os.environ.get('JAW', 0.02)), 0, 0)
    wall = P.mat_fleece('wall', P.hex_lin('#d9c4a0'), sheen=0.2)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.9, 0.6)); pl = bpy.context.object
    pl.scale = (3, 2, 1); pl.rotation_euler = (math.pi / 2, 0, 0); pl.data.materials.append(wall)
    area('key', (-0.9, -1.3, 1.6), (0, 0, 0.55), 170, 1.4)
    area('fill', (1.2, -1.2, 0.7), (0, 0, 0.55), 60, 1.6, (0.95, 0.95, 1.0))
    area('rim', (0.7, 1.0, 1.4), (0, 0, 0.6), 90, 0.6)
    camera((0, -1.75, 0.6), (0, 0, 0.47), lens=70, dof=1.75, fstop=4)
    sc.render.resolution_x = int(os.environ.get('RX', 420)); sc.render.resolution_y = int(os.environ.get('RY', 480))
    sc.render.filepath = f'{out}/{n}.png'
    t = time.time(); bpy.ops.render.render(write_still=True); print('done', n, round(time.time() - t, 1), flush=True)
