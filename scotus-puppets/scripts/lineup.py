import sys, os, math, time
sys.path.insert(0, os.path.dirname(__file__))
import bpy
import puppet as P
from characters import CHARS
from proto import reset, area, camera
names = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else list(CHARS)
out = os.environ.get('OUT')
for n in names:
    sc = reset()
    spec = dict(CHARS[n])
    if os.environ.get('GL'):
        spec['glasses'] = dict(hex='#2b2b2b')
    pp = P.build_puppet(n, spec, body_h=0.55, seed=hash(n) % 1000)
    pp['jaw'].rotation_euler = (float(os.environ.get('JAW', 0.02)), 0, 0)
    drape = P.mat_fleece('drape', P.hex_lin('#5e0d12'), sheen=0.8)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.9, 0.6)); pl = bpy.context.object
    pl.scale = (3, 2, 1); pl.rotation_euler = (math.pi / 2, 0, 0); pl.data.materials.append(drape)
    area('key', (-0.9, -1.3, 1.6), (0, 0, 0.55), 150, 1.2)
    area('fill', (1.2, -1.2, 0.7), (0, 0, 0.55), 40, 1.5, (0.9, 0.93, 1.0))
    area('rim', (0.7, 1.0, 1.4), (0, 0, 0.6), 110, 0.6)
    camera((0, -1.75, 0.6), (0, 0, 0.47), lens=70, dof=1.75, fstop=4)
    sc.render.resolution_x = int(os.environ.get('RX', 420)); sc.render.resolution_y = int(os.environ.get('RY', 480))
    sc.render.filepath = f'{out}/{n}.png'
    t = time.time(); bpy.ops.render.render(write_still=True); print('done', n, round(time.time() - t, 1), flush=True)
