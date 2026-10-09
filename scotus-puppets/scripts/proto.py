import sys, os, math, time
sys.path.insert(0, os.path.dirname(__file__))
import bpy, numpy as np
import puppet as P
from mathutils import Vector

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = int(os.environ.get('SAMPLES', 64))
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.015, 0.012, 1)
    return sc

def area(name, loc, target, energy, size, color=(1, 0.95, 0.88)):
    l = bpy.data.lights.new(name, 'AREA'); l.energy = energy; l.size = size; l.color = color
    o = bpy.data.objects.new(name, l); bpy.context.collection.objects.link(o); o.location = loc
    d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o

def camera(loc, target, lens=85, dof=None, fstop=2.8):
    c = bpy.data.cameras.new('cam'); c.lens = lens
    o = bpy.data.objects.new('cam', c); bpy.context.collection.objects.link(o); o.location = loc
    d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if dof:
        c.dof.use_dof = True; c.dof.focus_distance = dof; c.dof.aperture_fstop = fstop
    bpy.context.scene.camera = o
    return o

if __name__ == '__main__':
    import json
    sc = reset()
    spec = json.loads(os.environ.get('SPEC', '{}'))
    t = time.time()
    pp = P.build_puppet('pup', spec, root_loc=(0, 0, 0), body_h=0.55)
    print('build', time.time() - t)
    drape = P.mat_fleece('drape', P.hex_lin('#6e0f14'), sheen=0.8)
    import numpy as np
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.8, 0.6)); pl = bpy.context.object
    pl.scale = (3, 2, 1); pl.rotation_euler = (math.pi / 2, 0, 0); pl.data.materials.append(drape)
    area('key', (-0.9, -1.4, 1.5), (0, 0, 0.55), 160, 1.0)
    area('fill', (1.2, -1.2, 0.8), (0, 0, 0.55), 50, 1.5, (0.9, 0.93, 1.0))
    area('rim', (0.6, 1.0, 1.3), (0, 0, 0.6), 90, 0.6)
    camera((0, -1.75, 0.62), (0, 0, 0.5), lens=70, dof=1.75, fstop=4)
    sc.render.resolution_x = int(os.environ.get('RX', 640)); sc.render.resolution_y = int(os.environ.get('RY', 720))
    out = os.environ.get('OUT', '/tmp/x')
    for ang in [float(a) for a in os.environ.get('ANGLES', '0.02,0.42').split(',')]:
        pp['jaw'].rotation_euler = (ang, 0, 0)
        sc.render.filepath = f'{out}_{ang:.2f}.png'
        t = time.time(); bpy.ops.render.render(write_still=True); print('render', ang, time.time() - t)
