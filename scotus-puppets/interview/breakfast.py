# Editorial-board breakfast set: room, round table, chairs, breakfast props, cast placement, lights and cameras (bpy 5.2).
# Coordinates: metres, +Z up, the table centre is the origin, the wide camera sits on -Y (the open side of the panel),
# the windows are on the +Y wall. Seats are on a circle around the table, camera side open.
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); sys.path.insert(0, HERE)
import bpy
import numpy as np
from mathutils import Vector
import puppet as P
from cast import CAST, ORDER

TABLE_R = 1.2
TABLE_Z = 0.76          # table top
SEAT_R = 1.40           # puppet root radius (chest just outside the table edge)
STEP = 23.0             # degrees between seats
WALL_Y = 3.7
PHI = {k: (i - 3) * STEP for i, k in enumerate(ORDER)}   # degrees, negative = camera left
JAW = [0.015, 0.105, 0.195, 0.285, 0.375]

hexl = P.hex_lin


def polar(phi_deg, r):
    a = math.radians(phi_deg)
    return r * math.sin(a), r * math.cos(a)


# ----------------------------------------------------------------------------- scene / world
def scene_setup(samples=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.sample_clamp_indirect = 8.0
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Generated'], sp.inputs[0])
    cr = nt.nodes.new('ShaderNodeValToRGB')
    el = cr.color_ramp.elements
    el[0].position = 0.0; el[0].color = (0.30, 0.25, 0.20, 1)
    el[1].position = 1.0; el[1].color = (0.52, 0.70, 1.0, 1)
    e2 = el.new(0.47); e2.color = (0.62, 0.52, 0.42, 1)
    e3 = el.new(0.52); e3.color = (1.0, 0.90, 0.78, 1)
    e4 = el.new(0.68); e4.color = (0.80, 0.88, 1.0, 1)
    nt.links.new(sp.outputs['Z'], cr.inputs['Fac'])
    nt.links.new(cr.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.5
    return sc


# ----------------------------------------------------------------------------- materials
def plain(name, hexc, rough=0.5, coat=0.0, spec=0.5, sheen=0.0, metallic=0.0):
    return P.mat_plain(name, hexl(hexc), rough=rough, coat=coat, spec=spec, sheen=sheen, metallic=metallic)


def mat_noise(name, c1, c2, scale=20.0, rough=0.6, coat=0.0, bump=0.0, spec=0.4, sss=0.0, distort=0.0, detail=4.0):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale
    nz.inputs['Detail'].default_value = detail; nz.inputs['Distortion'].default_value = distort
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = hexl(c1); cr.color_ramp.elements[1].color = hexl(c2)
    L.new(nz.outputs['Fac'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = 0.1
    p.inputs['Specular IOR Level'].default_value = spec
    if sss:
        p.inputs['Subsurface Weight'].default_value = sss
        p.inputs['Subsurface Radius'].default_value = (0.01, 0.006, 0.004)
    if bump:
        bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.002
        L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], p.inputs['Normal'])
    return m


def mat_oak(name, dark='#7a4a26', light='#a8703d', rough=0.4, coat=0.2, scale=(1.0, 1.0, 9.0)):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = scale
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'
    wv.inputs['Scale'].default_value = 3.0; wv.inputs['Distortion'].default_value = 6.0
    wv.inputs['Detail'].default_value = 3.0; wv.inputs['Detail Scale'].default_value = 1.6
    L.new(mp.outputs['Vector'], wv.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = hexl(dark); cr.color_ramp.elements[1].color = hexl(light)
    L.new(wv.outputs['Fac'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = 0.15
    return m


def mat_floor(name):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    br = N.new('ShaderNodeTexBrick')
    br.offset = 0.5; br.offset_frequency = 2
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Color1'].default_value = hexl('#b8864f'); br.inputs['Color2'].default_value = hexl('#a67840')
    br.inputs['Mortar'].default_value = hexl('#5c3d22')
    br.inputs['Mortar Size'].default_value = 0.004; br.inputs['Brick Width'].default_value = 1.4
    br.inputs['Row Height'].default_value = 0.16
    br.inputs['Bias'].default_value = 0.0
    L.new(tc.outputs['Object'], br.inputs['Vector'])
    L.new(br.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.45
    p.inputs['Coat Weight'].default_value = 0.15
    return m


def mat_linen(name, hexc='#f3efe4'):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    p.inputs['Base Color'].default_value = hexl(hexc)
    p.inputs['Roughness'].default_value = 0.88
    p.inputs['Sheen Weight'].default_value = 0.6
    p.inputs['Sheen Roughness'].default_value = 0.4
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 1.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 6; nz2.inputs['Detail'].default_value = 3.0
    L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'
    L.new(nz.outputs['Fac'], add.inputs[0]); L.new(nz2.outputs['Fac'], add.inputs[1])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.35; bp.inputs['Distance'].default_value = 0.002
    L.new(add.outputs['Value'], bp.inputs['Height']); L.new(bp.outputs['Normal'], p.inputs['Normal'])
    return m


def mat_glass(name, tint=(1, 1, 1, 1), rough=0.0, ior=1.45):
    m, nt, p = P._new_mat(name)
    p.inputs['Base Color'].default_value = tint
    p.inputs['Transmission Weight'].default_value = 1.0
    p.inputs['Roughness'].default_value = rough
    p.inputs['IOR'].default_value = ior
    p.inputs['Thin Wall'].default_value = True
    return m


def mat_emit(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = color; e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m


def mat_bacon(name):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    # stripes across the strip width (local y): meat / fat / meat / fat / meat
    fr = N.new('ShaderNodeMath'); fr.operation = 'MULTIPLY'; fr.inputs[1].default_value = 1.0 / 0.0075
    L.new(sep.outputs['Y'], fr.inputs[0])
    fx = N.new('ShaderNodeMath'); fx.operation = 'FRACT'; L.new(fr.outputs[0], fx.inputs[0])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 60
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    ad = N.new('ShaderNodeMath'); ad.operation = 'ADD'; L.new(fx.outputs[0], ad.inputs[0])
    L.new(nz.outputs['Fac'], ad.inputs[1])
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.interpolation = 'LINEAR'
    el = cr.color_ramp.elements
    el[0].position = 0.42; el[0].color = hexl('#8e2a17')
    el[1].position = 0.6; el[1].color = hexl('#e9c99a')
    e2 = el.new(0.95); e2.color = hexl('#9a3a1c')
    L.new(ad.outputs[0], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.35
    p.inputs['Coat Weight'].default_value = 0.4
    return m


# ----------------------------------------------------------------------------- geometry helpers
def cube(name, size, loc, mat, parent=None, rot=(0, 0, 0), bevel=0.0, smooth=False):
    sx, sy, sz = size
    V = np.array([(x * sx / 2, y * sy / 2, z * sz / 2) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    F = [(4, 6, 7, 5), (0, 1, 3, 2), (2, 3, 7, 6), (0, 4, 5, 1), (1, 5, 7, 3), (0, 2, 6, 4)]
    ob = P.mesh_obj(name, V, F, [0] * 6, [mat], smooth=smooth, parent=parent, location=loc)
    ob.rotation_euler = rot
    if bevel:
        md = ob.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = 3
    return ob


def lathe(name, prof, mat, loc=(0, 0, 0), parent=None, segs=56, sxy=(1.0, 1.0), rot=(0, 0, 0), smooth=True):
    """Solid of revolution from [(r, z), ...]; r == 0 closes the profile at a pole."""
    rings = [(z, r, r, 0.0, 0) for (r, z) in prof]
    V, F, M = P.loft(rings, segs, 2.0)
    V = V * np.array([sxy[0], sxy[1], 1.0])
    ob = P.mesh_obj(name, V, F, M, [mat], smooth=smooth, parent=parent, location=loc)
    ob.rotation_euler = rot
    return ob


def sphere(name, r, mat, loc, scale=(1, 1, 1), parent=None, segs=20, rings=12, rot=None):
    return P.uv_sphere(name, r, [mat], segs=segs, rings=rings, scale=scale, parent=parent, loc=loc, rot=rot)


def group(name, loc, rot_z=0.0):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    e.location = loc
    e.rotation_euler = (0, 0, rot_z)
    return e


def torus(name, major, minor, mat, loc, parent=None, scale_z=1.0, rot=(0, 0, 0), maj_seg=40, min_seg=14):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=maj_seg,
                                     minor_segments=min_seg, location=(0, 0, 0))
    o = bpy.context.object; o.name = name
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    o.scale = (1, 1, scale_z)
    o.parent = parent; o.location = loc; o.rotation_euler = rot
    return o


# ----------------------------------------------------------------------------- tableware and food
class Mats:
    pass


def make_mats():
    M = Mats()
    M.oak = mat_oak('oak')
    M.oak_dark = mat_oak('oak_dark', '#5a3417', '#7e4d27')
    M.floor = mat_floor('floor')
    M.linen = mat_linen('linen')
    M.wall = P.mat_fleece('wall', hexl('#eadbc0'), sheen=0.15, rough=0.95, bump=0.15, fiber_scale=80, tint_var=0.05, sss=0.0)
    M.paint_white = plain('paint_white', '#f3eee4', rough=0.5, coat=0.1)
    M.ceramic = plain('ceramic', '#f6f3ec', rough=0.12, coat=0.6, spec=0.6)
    M.ceramic_blue = plain('ceramic_blue', '#4d73a8', rough=0.15, coat=0.5)
    M.steel = plain('steel', '#c8cbd0', rough=0.22, metallic=1.0)
    M.black = plain('black_plastic', '#17181a', rough=0.35, coat=0.3)
    M.glass = mat_glass('glass')
    M.glass_tint = mat_glass('glass_tint', (0.92, 0.97, 1.0, 1))
    M.water = plain('water', '#c9dff0', rough=0.05, coat=0.5, spec=0.6)
    M.coffee = plain('coffee', '#24140b', rough=0.08, coat=0.6, spec=0.6)
    M.oj = plain('oj', '#ff9a1a', rough=0.12, coat=0.4, spec=0.5)
    M.croissant = mat_noise('croissant', '#c47a2c', '#ecb35a', scale=11, rough=0.45, coat=0.25, bump=0.3, sss=0.05)
    M.croissant2 = mat_noise('croissant2', '#a05d1e', '#e29a43', scale=16, rough=0.45, coat=0.25, bump=0.3)
    M.bagel = mat_noise('bagel', '#b9783a', '#e6b172', scale=9, rough=0.55, coat=0.1, bump=0.25)
    M.muffin = mat_noise('muffin', '#a96a2c', '#dba25a', scale=18, rough=0.6, bump=0.3)
    M.wicker = mat_noise('wicker', '#8d5e2c', '#c79a58', scale=40, rough=0.7, bump=0.5, distort=2.0)
    M.bacon = mat_bacon('bacon')
    M.melon = plain('melon', '#f59a4f', rough=0.25, coat=0.5, spec=0.5)
    M.honeydew = plain('honeydew', '#c9e19a', rough=0.25, coat=0.5, spec=0.5)
    M.rind = plain('rind', '#cdbd86', rough=0.6)
    M.orange = plain('orange', '#ff8a12', rough=0.25, coat=0.6)
    M.strawberry = plain('strawberry', '#d1142a', rough=0.3, coat=0.5)
    M.leaf = plain('leaf', '#3f8a35', rough=0.5)
    M.blueberry = plain('blueberry', '#27407f', rough=0.3, coat=0.3)
    M.raspberry = plain('raspberry', '#c01c45', rough=0.35, coat=0.2)
    M.grape = plain('grape_g', '#a9c95c', rough=0.2, coat=0.6)
    M.grape_r = plain('grape_r', '#6c1f46', rough=0.2, coat=0.6)
    M.stem = plain('stem', '#5a4a2a', rough=0.7)
    M.butter = plain('butter', '#f6e083', rough=0.35, coat=0.1, sss=None) if False else plain('butter', '#f6e083', rough=0.35)
    M.jam = plain('jam', '#8c0f1c', rough=0.1, coat=0.6)
    M.jam2 = plain('jam2', '#c8581c', rough=0.1, coat=0.6)
    M.gold = plain('gold', '#d6b04c', rough=0.3, metallic=1.0)
    M.cream = plain('cream', '#f7f2e4', rough=0.3, coat=0.2)
    M.napkin = [plain(f'napkin{i}', c, rough=0.9, sheen=0.4) for i, c in enumerate(
        ('#c98b6c', '#8fa8c4', '#d8b86a', '#9cb59a', '#c98b6c', '#8fa8c4', '#d8b86a'))]
    M.notebook = [plain('nb0', '#223b6a', rough=0.5, coat=0.1), plain('nb1', '#8f2b2b', rough=0.5, coat=0.1),
                  plain('nb2', '#1d1d1f', rough=0.5, coat=0.1)]
    M.paper = plain('paper', '#f5f1e6', rough=0.8)
    M.cushion = [plain(f'cush{i}', c, rough=0.9, sheen=0.5) for i, c in enumerate(
        ('#b9a98a', '#8a9a7b', '#c7b79a', '#9aa5b3', '#b9a98a', '#8a9a7b', '#c7b79a'))]
    M.screen = plain('screen', '#0c1a2c', rough=0.05, coat=0.8, spec=0.8)
    M.red_led = mat_emit('red_led', (1.0, 0.05, 0.03, 1), 12.0)
    return M


def plate(name, r, mat, loc, parent=None, sxy=(1, 1), segs=56):
    prof = [(0, 0.0), (0.58 * r, 0.0), (0.8 * r, 0.006), (r, 0.017), (r, 0.021), (0.93 * r, 0.02), (0.6 * r, 0.007),
            (0, 0.007)]
    return lathe(name, prof, mat, loc, parent, segs, sxy)


def cup_saucer(name, M, parent, ang=0.0, handle_dir=1):
    parts = [plate(name + '_saucer', 0.072, M.ceramic, (0, 0, 0), parent, segs=40)]
    prof = [(0, 0.008), (0.024, 0.008), (0.03, 0.012), (0.041, 0.04), (0.046, 0.07), (0.0465, 0.0715), (0.0435, 0.0715),
            (0.039, 0.04), (0.0, 0.014)]
    parts.append(lathe(name + '_cup', prof, M.ceramic, (0, 0, 0), parent, segs=40))
    parts.append(lathe(name + '_coffee', [(0, 0.06), (0.0415, 0.06), (0, 0.0605)], M.coffee, (0, 0, 0), parent, segs=32))
    pts = [(handle_dir * 0.044, 0, 0.062), (handle_dir * 0.062, 0, 0.058), (handle_dir * 0.066, 0, 0.04),
           (handle_dir * 0.05, 0, 0.026)]
    parts.append(P.tube(name + '_handle', pts, [0.004, 0.0042, 0.004, 0.0035], [M.ceramic], nseg=8, parent=parent,
                        caps=True))
    return parts


def tumbler(name, M, parent, liquid, r=0.032, h=0.092):
    prof = [(0, 0.0), (r * 0.9, 0.0), (r * 0.95, 0.006), (r * 1.1, h), (r * 1.1 - 0.002, h), (r * 0.9, 0.012),
            (0, 0.01)]
    g = lathe(name + '_glass', prof, M.glass, (0, 0, 0), parent, segs=32)
    fill = lathe(name + '_liquid', [(0, 0.011), (r * 0.9 - 0.001, 0.012), (r * 1.02, h * 0.72), (0, h * 0.72)], liquid,
                 (0, 0, 0), parent, segs=32)
    return [g, fill]


def croissant(name, M, parent, loc, rot_z, scale=1.0, mat=None):
    """Crescent of overlapping flattened segments (a layered, golden croissant)."""
    n = 11
    arc = 2.5
    Rc = 0.062 * scale
    objs = []
    mat = mat or M.croissant
    for i in range(n):
        t = i / (n - 1)
        th = (t - 0.5) * arc
        thick = (0.011 + 0.026 * math.sin(math.pi * t) ** 0.8) * scale
        px, py = Rc * math.sin(th), Rc * (math.cos(th) - 1.0)
        o = sphere(f'{name}_s{i}', 1.0, mat, (loc[0], loc[1], loc[2]), scale=(0.0135 * scale, thick * 1.05, thick * 0.92),
                   parent=parent, segs=16, rings=10)
        # position the segment on the arc in the group frame
        c, s_ = math.cos(rot_z), math.sin(rot_z)
        o.location = (loc[0] + c * px - s_ * py, loc[1] + s_ * px + c * py, loc[2] + thick * 0.85)
        o.rotation_euler = (0, 0, rot_z - th)
        objs.append(o)
    return objs


def bagel(name, M, parent, loc, rot_z=0.0):
    t = torus(name, 0.045, 0.019, M.bagel, loc, parent, scale_z=0.8, rot=(0, 0, rot_z))
    return [t]


def strawberry(name, M, parent, loc):
    a = sphere(name, 1.0, M.strawberry, loc, scale=(0.0135, 0.0135, 0.0175), parent=parent, segs=14, rings=10)
    b = sphere(name + '_cap', 1.0, M.leaf, (loc[0], loc[1], loc[2] + 0.015), scale=(0.011, 0.011, 0.004), parent=parent,
               segs=10, rings=6)
    return [a, b]


def grapes(name, M, parent, loc, mat, rng, n=15):
    out = []
    pts = []
    for i in range(n):
        row = int((math.sqrt(8 * i + 1) - 1) / 2)
        col = i - row * (row + 1) // 2
        x = (col - row / 2) * 0.0185 + rng.normal(0, 0.0012)
        y = -row * 0.016 + rng.normal(0, 0.001)
        z = 0.009 + 0.002 * (n - i) / n
        pts.append((x, y, z))
        out.append(sphere(f'{name}_g{i}', 0.0098, mat, (loc[0] + x, loc[1] + y, loc[2] + z), parent=parent, segs=12, rings=8))
    out.append(P.tube(name + '_stem', [(loc[0], loc[1] + 0.012, loc[2] + 0.02), (loc[0], loc[1] + 0.025, loc[2] + 0.028)],
                      [0.0022, 0.0018], [M.stem], nseg=6, parent=parent))
    return out


def melon_slice(name, M, parent, loc, rot_z, mat, rind_mat, r=0.058):
    objs = []
    th = np.linspace(-0.95, 0.95, 9)
    pts = [(r * math.sin(a), r * (math.cos(a) - 1), 0.0) for a in th]
    flesh = P.tube(name, pts, [0.011] * len(pts), [mat], nseg=10, parent=parent)
    pts2 = [((r + 0.011) * math.sin(a), (r + 0.011) * (math.cos(a) - 1) , -0.002) for a in th]
    rind = P.tube(name + '_rind', pts2, [0.0042] * len(pts2), [rind_mat], nseg=8, parent=parent)
    for o in (flesh, rind):
        o.location = (loc[0], loc[1], loc[2] + 0.011); o.rotation_euler = (0, 0, rot_z)
        objs.append(o)
    return objs


def orange_segment(name, M, parent, loc, rot_z):
    th = np.linspace(-0.8, 0.8, 7)
    r = 0.026
    pts = [(r * math.sin(a), r * (math.cos(a) - 1), 0.0) for a in th]
    o = P.tube(name, pts, [0.0085, 0.0105, 0.0115, 0.012, 0.0115, 0.0105, 0.0085], [M.orange], nseg=8, parent=parent)
    o.location = (loc[0], loc[1], loc[2] + 0.009); o.rotation_euler = (0, 0, rot_z)
    return [o]


def bacon_strip(name, M, parent, loc, rot_z, rng, length=0.17, width=0.024):
    nx, ny = 28, 4
    xs = np.linspace(-length / 2, length / 2, nx)
    ys = np.linspace(-width / 2, width / 2, ny)
    ph = rng.random() * 6.28
    amp = rng.uniform(0.004, 0.007)
    V, F = [], []
    for x in xs:
        wob = 0.006 * math.sin(x * 38 + ph)
        for y in ys:
            V.append((x, y + wob, 0.0025 + amp * math.sin(x * 52 + ph * 1.3) * 0.5 + 0.003 * math.sin(x * 21 + y * 80)))
    for i in range(nx - 1):
        for j in range(ny - 1):
            a = i * ny + j
            F.append((a, a + ny, a + ny + 1, a + 1))
    o = P.mesh_obj(name, np.array(V), F, [0] * len(F), [M.bacon], smooth=True, parent=parent, location=loc)
    o.rotation_euler = (0, 0, rot_z)
    md = o.modifiers.new('sol', 'SOLIDIFY'); md.thickness = 0.004
    return [o]


def build_table(M, G):
    parent = group('table', (0, 0, 0))
    top = lathe('table_top', [(0, TABLE_Z - 0.06), (TABLE_R - 0.03, TABLE_Z - 0.06), (TABLE_R, TABLE_Z - 0.045),
                              (TABLE_R + 0.004, TABLE_Z - 0.02), (TABLE_R - 0.006, TABLE_Z), (0, TABLE_Z)], M.oak,
                (0, 0, 0), segs=96)
    apron = lathe('table_apron', [(0, 0.0), (1.02, 0.0)][:0] + [(1.0, TABLE_Z - 0.06), (1.0, TABLE_Z - 0.16),
                                                                  (0.98, TABLE_Z - 0.16)], M.oak_dark, (0, 0, 0), segs=96)
    ped = lathe('table_pedestal', [(0, 0.0), (0.42, 0.0), (0.42, 0.04), (0.12, 0.09), (0.1, TABLE_Z - 0.16),
                                   (0.0, TABLE_Z - 0.16)], M.oak_dark, (0, 0, 0), segs=48)
    cloth = lathe('tablecloth', [(0, TABLE_Z + 0.006), (0.9, TABLE_Z + 0.006), (0.985, TABLE_Z + 0.0055),
                                 (1.002, TABLE_Z + 0.0035), (1.0, TABLE_Z + 0.0005), (0, TABLE_Z + 0.0005)], M.linen,
                  (0, 0, 0), segs=128)
    # a soft hem band
    hem = lathe('cloth_hem', [(0.935, TABLE_Z + 0.0062), (0.945, TABLE_Z + 0.0066), (0.95, TABLE_Z + 0.0062)],
                plain('hem', '#d9d2c0', rough=0.9), (0, 0, 0), segs=128)
    G['set'] += [top, apron, ped, cloth, hem]


def place_settings(M, G, rng):
    for i, n in enumerate(ORDER):
        phi = PHI[n]
        z0 = TABLE_Z + 0.006
        g = group(f'place_{n}', (*polar(phi, 1.0), 0), -math.radians(phi))   # local frame: -Y points to the centre
        g.location = (*polar(phi, 1.0), 0)
        # local coords: x lateral (viewer-right of the sitter is -x), y radial (toward centre is -y)
        # napkin + plate with food
        nap = cube(f'nap_{n}', (0.2, 0.2, 0.004), (0, 0.03, z0 + 0.002), M.napkin[i], g, rot=(0, 0, 0.08 * (i % 3 - 1)))
        pl = plate(f'plate_{n}', 0.098, M.ceramic, (0, 0.03, z0 + 0.004), g)
        food = []
        kind = i % 4
        if kind == 0:
            food += croissant(f'cr_{n}', M, g, (0.0, 0.0, z0 + 0.011), 0.2 + 0.1 * i, 0.82)
        elif kind == 1:
            food += bagel(f'bg_{n}', M, g, (0.0, 0.03, z0 + 0.03), rng.uniform(0, 3))
            food.append(cube(f'bt_{n}', (0.03, 0.02, 0.012), (0.045, 0.0, z0 + 0.016), M.butter, g, bevel=0.002))
        elif kind == 2:
            food += croissant(f'cr_{n}', M, g, (0.0, 0.0, z0 + 0.011), -0.5, 0.78, M.croissant2)
            for k in range(3):
                food += strawberry(f'sb_{n}{k}', M, g, (0.05 - 0.03 * k, 0.045, z0 + 0.025))
        else:
            food += bagel(f'bg_{n}', M, g, (0.0, 0.03, z0 + 0.03), rng.uniform(0, 3))
            food += strawberry(f'sbx_{n}', M, g, (0.0, 0.0, z0 + 0.025))
        # coffee cup and saucer, off to the sitter's left of the plate (viewer's right = -x? use lateral sign)
        cs = group(f'cup_{n}', (0, 0, 0), 0.4 * (i - 3))
        cs.parent = g; cs.location = (-0.15, -0.14, z0)
        cup_saucer(f'cup_{n}', M, cs, handle_dir=1)
        # water glass
        wg = group(f'wglass_{n}', (0, 0, 0)); wg.parent = g; wg.location = (0.14, -0.15, z0)
        tumbler(f'wg_{n}', M, wg, M.water)
        # juice glass for some
        if i % 2 == 0:
            jg = group(f'jglass_{n}', (0, 0, 0)); jg.parent = g; jg.location = (0.2, -0.04, z0)
            tumbler(f'jg_{n}', M, jg, M.oj, r=0.029, h=0.1)
    # notebooks and pens at three journalists' places (beyond the left hand)
    for k, n in enumerate(('smith', 'greenman', 'katz')):
        g = bpy.data.objects[f'place_{n}']
        z0 = TABLE_Z + 0.006
        sgn = 1
        nb = group(f'nb_{n}', (0, 0, 0), 0.25 * (k - 1)); nb.parent = g; nb.location = (-0.285 * sgn, 0.02, z0)
        cube(f'nb_cover_{n}', (0.15, 0.205, 0.012), (0, 0, 0.006), M.notebook[k], nb, bevel=0.002)
        cube(f'nb_pages_{n}', (0.142, 0.198, 0.009), (0.004, 0, 0.007), M.paper, nb)
        pen = P.tube(f'pen_{n}', [(-0.04, 0.0, 0.0145), (0.05, 0.02, 0.0145)], [0.0042, 0.0042], [M.black], nseg=8,
                     parent=nb)
        cube(f'nb_band_{n}', (0.006, 0.206, 0.0135), (0.056, 0, 0.0066), M.black, nb)


def center_items(M, G, rng):
    z0 = TABLE_Z + 0.006
    root = group('centerpiece', (0, 0, 0))

    def at(name, x, y, rot=0.0):
        g = group(name, (x, y, 0), rot); return g

    # croissant basket
    g = at('basket', -0.32, 0.14, 0.4)
    lathe('basket_body', [(0, z0), (0.115, z0), (0.13, z0 + 0.03), (0.145, z0 + 0.075), (0.138, z0 + 0.077), (0.12, z0 + 0.04),
                          (0.0, z0 + 0.012)], M.wicker, (0, 0, 0), g, segs=48)
    lathe('basket_rim', [(0.138, z0 + 0.073), (0.147, z0 + 0.0755), (0.146, z0 + 0.081), (0.137, z0 + 0.079)], M.wicker,
          (0, 0, 0), g, segs=48)
    lathe('basket_cloth', [(0, z0 + 0.03), (0.12, z0 + 0.034), (0.14, z0 + 0.07), (0.0, z0 + 0.04)],
          plain('bcloth', '#f1e3d2', rough=0.9, sheen=0.4), (0, 0, 0), g, segs=40)
    for k, (x, y, rz, s_) in enumerate(((-0.035, -0.02, 0.5, 0.95), (0.04, -0.03, 2.6, 0.95), (0.0, 0.045, -1.4, 0.95),
                                        (0.0, 0.0, 1.2, 0.88))):
        cr = croissant(f'bcr{k}', M, g, (x, y, z0 + 0.045 + 0.018 * (k == 3)), rz, s_, M.croissant if k % 2 == 0 else M.croissant2)
    # fruit platter A (melon, berries, grapes, orange segments)
    g = at('fruitA', 0.34, 0.12, -0.4)
    plate('fruitA_plate', 0.2, plain('platter', '#fbfaf5', rough=0.12, coat=0.6), (0, 0, z0), g, sxy=(1.15, 0.85))
    for k in range(5):
        a = -0.9 + 0.45 * k
        melon_slice(f'mel{k}', M, g, (-0.12 + 0.06 * k, -0.045 + 0.02 * math.sin(k), z0 + 0.02), 0.2 * (k - 2),
                    M.melon if k % 2 == 0 else M.honeydew, M.rind, r=0.055)
    for k in range(7):
        orange_segment(f'osg{k}', M, g, (0.09 + 0.03 * math.cos(k), 0.04 + 0.025 * math.sin(k), z0 + 0.02 + 0.004 * (k % 2)),
                       k * 0.9)
    rr = np.random.default_rng(3)
    for k in range(10):
        x, y = rr.uniform(-0.1, 0.0), rr.uniform(0.0, 0.06)
        sphere(f'bb{k}', 0.0072, M.blueberry, (x - 0.02 + 0.015 * (k % 3), y + 0.02, z0 + 0.02 + 0.006 * (k % 2)), parent=g, segs=10, rings=7)
    for k in range(6):
        sphere(f'rb{k}', 0.0095, M.raspberry, (-0.05 + 0.017 * k, 0.065 - 0.01 * (k % 2), z0 + 0.026), parent=g, segs=10, rings=7)
    grapes('grapesA', M, g, (0.0, -0.01, z0 + 0.012), M.grape, rr, 14)
    # fruit platter B (berries, grapes, strawberries) near the camera side
    g = at('fruitB', 0.06, -0.4, 0.3)
    plate('fruitB_plate', 0.16, plain('platterB', '#fbfaf5', rough=0.12, coat=0.6), (0, 0, z0), g)
    for k in range(7):
        a = k * 0.9
        strawberry(f'sbB{k}', M, g, (0.06 * math.cos(a), 0.06 * math.sin(a), z0 + 0.03))
    grapes('grapesB', M, g, (0.0, 0.03, z0 + 0.012), M.grape_r, rr, 12)
    for k in range(9):
        sphere(f'bbB{k}', 0.0072, M.blueberry, (0.02 * math.cos(k * 1.4), -0.02 + 0.02 * math.sin(k * 1.4), z0 + 0.014 + 0.007 * (k % 2)),
               parent=g, segs=10, rings=7)
    # bacon plate
    g = at('baconplate', 0.0, 0.47, 0.0)
    plate('bacon_plate', 0.15, M.ceramic, (0, 0, z0), g, sxy=(1.25, 0.8))
    for k in range(6):
        bacon_strip(f'bacon{k}', M, g, (0.0 + 0.004 * k, -0.04 + 0.016 * k, z0 + 0.012 + 0.006 * (k % 3)), 0.15 * (k - 2.5) + 0.1,
                    rng)
    # bagel board with cream cheese, butter and jam
    g = at('bagelboard', 0.52, -0.1, 0.5)
    cube('board', (0.34, 0.22, 0.02), (0, 0, z0 + 0.01), M.oak, g, bevel=0.004)
    for k, (x, y) in enumerate(((-0.08, 0.02), (0.02, -0.04), (0.0, 0.055))):
        bagel(f'bgb{k}', M, g, (x, y, z0 + 0.042), k * 0.7)
    lathe('ramekin', [(0, z0 + 0.02), (0.03, z0 + 0.02), (0.034, z0 + 0.04), (0.031, z0 + 0.04), (0.0, z0 + 0.025)],
          M.ceramic, (0.11, -0.04, 0), g, segs=24)
    lathe('creamcheese', [(0, z0 + 0.038), (0.029, z0 + 0.036), (0.0, z0 + 0.046)], M.cream, (0.11, -0.04, 0), g, segs=24)
    g2 = at('butterdish', 0.67, 0.18, -0.3)
    cube('butter_dish', (0.1, 0.07, 0.01), (0, 0, z0 + 0.005), M.ceramic, g2, bevel=0.003)
    cube('butter', (0.07, 0.042, 0.03), (0, 0, z0 + 0.025), M.butter, g2, bevel=0.004)
    for k, (x, jm) in enumerate(((0.82, M.jam), (0.76, M.jam2))):
        gj = at(f'jar{k}', x - 0.06 * k, 0.04 - 0.1 * k, 0)
        lathe('jar_g', [(0, z0), (0.028, z0), (0.03, z0 + 0.008), (0.03, z0 + 0.052), (0.0, z0 + 0.052)], M.glass, (0, 0, 0), gj, segs=24)
        lathe('jar_j', [(0, z0 + 0.003), (0.0265, z0 + 0.004), (0.0275, z0 + 0.044), (0.0, z0 + 0.044)], jm, (0, 0, 0), gj, segs=24)
        lathe('jar_lid', [(0, z0 + 0.052), (0.0305, z0 + 0.052), (0.0305, z0 + 0.062), (0.0, z0 + 0.062)], M.gold, (0, 0, 0), gj, segs=24)
    # coffee carafe (stainless vacuum carafe with a black lid and handle), creamer and sugar
    g = at('carafe', -0.55, -0.05, 0.2)
    lathe('carafe_body', [(0, z0), (0.052, z0), (0.062, z0 + 0.012), (0.064, z0 + 0.04), (0.06, z0 + 0.19), (0.05, z0 + 0.225),
                          (0.036, z0 + 0.24), (0.0, z0 + 0.24)], M.steel, (0, 0, 0), g, segs=40)
    lathe('carafe_lid', [(0, z0 + 0.24), (0.042, z0 + 0.24), (0.04, z0 + 0.262), (0.02, z0 + 0.272), (0.0, z0 + 0.272)],
          M.black, (0, 0, 0), g, segs=32)
    P.tube('carafe_handle', [(0.056, 0.0, z0 + 0.2), (0.105, 0.0, z0 + 0.185), (0.108, 0.0, z0 + 0.1), (0.066, 0.0, z0 + 0.06)],
           [0.011, 0.011, 0.011, 0.011], [M.black], nseg=10, parent=g)
    g = at('creamer', -0.4, -0.25, 0.0)
    lathe('creamer', [(0, z0), (0.03, z0), (0.036, z0 + 0.02), (0.03, z0 + 0.07), (0.036, z0 + 0.085), (0.0, z0 + 0.085)],
          M.ceramic, (0, 0, 0), g, segs=32)
    g = at('sugar', -0.3, -0.33, 0.0)
    lathe('sugar', [(0, z0), (0.04, z0), (0.044, z0 + 0.03), (0.038, z0 + 0.055), (0.0, z0 + 0.055)], M.ceramic, (0, 0, 0), g, segs=32)
    lathe('sugar_lid', [(0, z0 + 0.055), (0.04, z0 + 0.055), (0.03, z0 + 0.07), (0.0, z0 + 0.076)], M.ceramic, (0, 0, 0), g, segs=32)
    # juice pitcher
    g = at('pitcher', 0.2, 0.34, 0.0)
    prof = [(0, z0), (0.05, z0), (0.056, z0 + 0.01), (0.062, z0 + 0.14), (0.058, z0 + 0.15), (0.05, z0 + 0.013), (0.0, z0 + 0.011)]
    lathe('pitcher_glass', prof, M.glass, (0, 0, 0), g, segs=40)
    lathe('pitcher_oj', [(0, z0 + 0.012), (0.049, z0 + 0.014), (0.058, z0 + 0.1), (0.0, z0 + 0.1)], M.oj, (0, 0, 0), g, segs=40)
    P.tube('pitcher_handle', [(0.06, 0.0, z0 + 0.13), (0.09, 0.0, z0 + 0.11), (0.092, 0.0, z0 + 0.05), (0.056, 0.0, z0 + 0.025)],
           [0.005] * 4, [M.glass_tint], nseg=8, parent=g)
    # phone and recorder near the centre (flat)
    g = at('phone', -0.08, -0.17, 0.6)
    cube('phone_body', (0.072, 0.152, 0.008), (0, 0, z0 + 0.004), M.black, g, bevel=0.003)
    cube('phone_screen', (0.066, 0.144, 0.0012), (0, 0, z0 + 0.0086), M.screen, g)
    g = at('recorder', 0.07, -0.07, -0.35)
    cube('rec_body', (0.048, 0.118, 0.018), (0, 0, z0 + 0.009), plain('rec', '#8f9298', rough=0.35, metallic=0.6), g, bevel=0.005)
    cube('rec_face', (0.036, 0.07, 0.002), (0, 0.01, z0 + 0.019), M.black, g)
    sphere('rec_led', 0.0035, M.red_led, (0.0, -0.04, z0 + 0.0185), parent=g, segs=10, rings=6)


# ----------------------------------------------------------------------------- room
def front_page_image(path, seed, title):
    from PIL import Image, ImageDraw, ImageFont
    rng = np.random.default_rng(seed)
    Wd, Ht = 640, 860
    im = Image.new('RGB', (Wd, Ht), (240, 234, 217))
    d = ImageDraw.Draw(im)
    fb = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
    fr = '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'
    f_m = ImageFont.truetype(fb, 56 if len(title) < 16 else 44)
    d.text((Wd / 2, 62), title, fill=(20, 18, 16), font=f_m, anchor='mm')
    d.line([(24, 108), (Wd - 24, 108)], fill=(20, 18, 16), width=4)
    d.line([(24, 114), (Wd - 24, 114)], fill=(20, 18, 16), width=1)
    f_h = ImageFont.truetype(fb, 46)
    heads = ['MAYORS, CHIEFS WEIGH IN', 'BUDGET DEAL REACHED', 'COUNCIL VOTES ON PLAN', 'VOTERS HEAD TO THE POLLS']
    h = heads[seed % len(heads)]
    d.text((Wd / 2, 160), h, fill=(15, 14, 12), font=f_h, anchor='mm')
    d.rectangle([34, 205, Wd - 34, 440], fill=(120, 124, 128))
    for k in range(6):
        x0 = rng.integers(40, Wd - 200); y0 = rng.integers(215, 330)
        d.rectangle([x0, y0, x0 + rng.integers(40, 160), y0 + rng.integers(40, 110)], fill=tuple(int(v) for v in rng.integers(70, 190, 3)))
    f_s = ImageFont.truetype(fr, 15)
    for c in range(3):
        x0 = 34 + c * ((Wd - 68) // 3 + 2)
        y = 460
        d.text((x0, y), 'A DEVELOPING STORY', fill=(30, 28, 25), font=ImageFont.truetype(fb, 15))
        y += 24
        while y < Ht - 40:
            w = int(((Wd - 68) // 3 - 14) * rng.uniform(0.7, 1.0))
            d.line([(x0, y), (x0 + w, y)], fill=(70, 68, 64), width=3)
            y += 12
            if rng.random() < 0.06:
                y += 12
    im.save(path)


def build_room(M, G, work):
    rng = np.random.default_rng(7)
    S = G['set']
    fl = bpy.data.objects.new('floor', None)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, -4, 0))
    fl = bpy.context.object; fl.name = 'floor'; fl.data.materials.append(M.floor); S.append(fl)
    # rug under the table
    rug = lathe('rug', [(0, 0.006), (1.95, 0.006), (2.0, 0.004), (2.0, 0.0), (0, 0.0)], plain('rug', '#7c8fa0', rough=0.95, sheen=0.4),
                (0, 0, 0), segs=96)
    rug2 = lathe('rug_inner', [(0, 0.0065), (1.62, 0.0065), (1.66, 0.006), (0, 0.006)],
                 plain('rug2', '#c9b690', rough=0.95, sheen=0.4), (0, 0, 0), segs=96)
    S += [rug, rug2]
    WT = 0.3
    # back wall with a window wall in the middle: piers beside the windows, wainscot below, header above
    wy = WALL_Y
    S.append(cube('wall_left', (3.4, WT, 3.6), (-4.9, wy, 1.8), M.wall))
    S.append(cube('wall_right', (3.4, WT, 3.6), (4.9, wy, 1.8), M.wall))
    S.append(cube('wall_sill', (6.4, WT, 0.9), (0, wy, 0.45), M.paint_white, bevel=0.01))
    S.append(cube('wall_header', (6.4, WT, 1.0), (0, wy, 3.1), M.wall))
    S.append(cube('sill_ledge', (6.4, 0.12, 0.04), (0, wy - 0.18, 0.92), M.paint_white, bevel=0.008))
    S.append(cube('baseboard', (14, 0.04, 0.14), (0, wy - 0.17, 0.07), M.paint_white, bevel=0.005))
    # mullions between the heads (spacing in wall units follows the perspective of the wide shot)
    for k in range(-4, 5):
        x = (k + 0.5) * 0.74
        if abs(x) < 3.2:
            S.append(cube(f'mullion{k}', (0.05, 0.08, 2.2), (x, wy - 0.12, 2.0), M.paint_white, bevel=0.004))
    S.append(cube('transom', (6.4, 0.08, 0.05), (0, wy - 0.12, 2.25), M.paint_white))
    # side walls and a ceiling-less room: left/right walls
    S.append(cube('side_left', (0.3, 14, 3.6), (-6.6, -2.5, 1.8), M.wall))
    S.append(cube('side_right', (0.3, 14, 3.6), (6.6, -2.5, 1.8), M.wall))
    # framed newspaper front pages on the wall piers
    titles = ['The Hudson Ledger', 'The Daily Chronicle', 'The City Gazette', 'The Morning Courier']
    for k, (x, z, sc_) in enumerate(((-4.2, 1.75, 1.0), (-5.35, 1.7, 0.9), (4.2, 1.75, 1.0), (5.35, 1.7, 0.9))):
        path = os.path.join(work, f'frontpage{k}.png')
        if not os.path.exists(path):
            front_page_image(path, k + 1, titles[k])
        fw, fh = 0.52 * sc_, 0.7 * sc_
        S.append(cube(f'frame{k}', (fw + 0.07, 0.04, fh + 0.07), (x, wy - 0.17, z), M.oak_dark, bevel=0.006))
        mm, nt, pp = P._new_mat(f'page{k}')
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path)
        nt.links.new(tex.outputs['Color'], pp.inputs['Base Color'])
        pp.inputs['Roughness'].default_value = 0.6
        pg = cube(f'page{k}', (fw, 0.01, fh), (x, wy - 0.2, z), mm)
        # project UVs: x -> u, z -> v
        me = pg.data
        uvl = me.uv_layers.new(name='uv')
        for poly in me.polygons:
            for li in poly.loop_indices:
                v = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (0.5 + v.x / fw, 0.5 + v.z / fh)
        S.append(pg)
    # the city outside: hazy emissive boxes at a distance (soft and out of focus)
    haze = np.array([0.93, 0.90, 0.86])
    palette = [(0.78, 0.69, 0.58), (0.70, 0.74, 0.80), (0.82, 0.62, 0.50), (0.66, 0.70, 0.76), (0.84, 0.80, 0.72),
               (0.60, 0.64, 0.70)]
    gm = mat_emit('cityground', (0.80, 0.78, 0.74, 1), 0.9)
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, wy + 200, -14.5))
    gp = bpy.context.object; gp.name = 'cityground'; gp.data.materials.append(gm); S.append(gp)
    for k in range(70):
        y = rng.uniform(22, 150)
        x = rng.uniform(-90, 90) * (y / 90 + 0.5)
        w, d_, h = rng.uniform(7, 22), rng.uniform(10, 20), rng.uniform(14, 95) * (1.0 if abs(x) > 8 else 0.7)
        fog = min(1.0, (y - 20) / 160) ** 0.8
        col = np.array(palette[rng.integers(len(palette))]) * (1 - fog) + haze * fog
        mm, nt, pp = P._new_mat(f'bld{k}')
        nt.nodes.remove(pp)
        tcn = nt.nodes.new('ShaderNodeTexCoord')
        ck = nt.nodes.new('ShaderNodeTexChecker'); ck.inputs['Scale'].default_value = 1.0
        mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.1, 1.1, 0.6)
        nt.links.new(tcn.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], ck.inputs['Vector'])
        ck.inputs['Color1'].default_value = (*col, 1.0); ck.inputs['Color2'].default_value = (*(col * 0.9), 1.0)
        em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 0.95
        nt.links.new(ck.outputs['Color'], em.inputs['Color'])
        nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
        S.append(cube(f'bld{k}', (w, d_, h), (x, wy + y, h / 2 - 15), mm))
    return S


# ----------------------------------------------------------------------------- chairs
def build_chair(name, phi, M, idx, G):
    g = group(f'chair_{name}', (*polar(phi, SEAT_R + 0.1), 0), -math.radians(phi))
    S = G['set']
    zs = 0.5
    S.append(cube(f'{name}_seat', (0.5, 0.5, 0.075), (0, 0.0, zs + 0.0375), M.cushion[idx], g, bevel=0.02))
    S.append(cube(f'{name}_seatframe', (0.52, 0.52, 0.04), (0, 0.0, zs - 0.02), M.oak, g, bevel=0.008))
    for sx in (-1, 1):
        for sy in (-1, 1):
            S.append(cube(f'{name}_leg{sx}{sy}', (0.045, 0.045, zs - 0.04), (sx * 0.225, sy * 0.225, (zs - 0.04) / 2), M.oak, g, bevel=0.01))
    # back: two posts, a top rail, and an upholstered panel (leaning back a little)
    yb = 0.235
    for sx in (-1, 1):
        S.append(cube(f'{name}_post{sx}', (0.045, 0.045, 0.62), (sx * 0.225, yb, zs + 0.31 + 0.02), M.oak, g, rot=(-0.08, 0, 0), bevel=0.01))
    S.append(cube(f'{name}_rail', (0.5, 0.05, 0.07), (0, yb + 0.045, zs + 0.64), M.oak, g, rot=(-0.08, 0, 0), bevel=0.012))
    S.append(cube(f'{name}_panel', (0.4, 0.045, 0.34), (0, yb + 0.02, zs + 0.36), M.cushion[idx], g, rot=(-0.08, 0, 0), bevel=0.016))
    return g


# ----------------------------------------------------------------------------- lights
def add_area(name, loc, target, energy, size, color=(1.0, 0.92, 0.8), size_y=None):
    l = bpy.data.lights.new(name, 'AREA'); l.energy = energy
    if size_y:
        l.shape = 'RECTANGLE'; l.size = size; l.size_y = size_y
    else:
        l.size = size
    l.color = color
    o = bpy.data.objects.new(name, l); bpy.context.collection.objects.link(o); o.location = loc
    d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def build_lights():
    L = []
    L.append(add_area('key', (-2.4, -4.6, 3.4), (0, 0.8, 1.15), 950, 3.0, (1.0, 0.94, 0.85), size_y=2.0))
    L.append(add_area('fill', (3.4, -4.2, 2.3), (0, 0.8, 1.1), 330, 3.0, (0.92, 0.95, 1.0), size_y=2.0))
    L.append(add_area('top', (0, -0.6, 3.5), (0, 0.4, 0.9), 320, 3.0, (1.0, 0.96, 0.9), size_y=3.0))
    L.append(add_area('wallwash', (0, -3.0, 3.0), (0, WALL_Y, 1.6), 160, 8.0, (1.0, 0.92, 0.8), size_y=1.5))
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 2.2; sun.angle = math.radians(4); sun.color = (1.0, 0.86, 0.68)
    so = bpy.data.objects.new('sun', sun); bpy.context.collection.objects.link(so)
    d = Vector((0.35, -0.8, -0.38)).normalized()
    so.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    L.append(so)
    return L


# ----------------------------------------------------------------------------- world
def root_z(spec):
    """Root height so that the hand sphere's underside sits on the table top."""
    s = P.merged(spec)
    b = s['body']
    neck_base = 0.55 + s['zb'] + 0.035
    return TABLE_Z - (neck_base + b.get('rest_dz', -0.36) + 0.018 - 0.024)


def build_world(work, with_food=True):
    M = make_mats()
    G = dict(set=[], chairs=[], lights=[])
    build_room(M, G, work)
    build_table(M, G)
    rng = np.random.default_rng(11)
    if with_food:
        place_settings(M, G, rng)
        center_items(M, G, rng)
    for i, n in enumerate(ORDER):
        build_chair(n, PHI[n], M, i, G)
    G['lights'] = build_lights()
    # the set = everything built so far that renders geometry
    set_objs = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVES')]
    cast = {}
    for i, n in enumerate(ORDER):
        spec = dict(CAST[n])
        body = dict(spec.get('body', {}))
        body.setdefault('reach', 0.285); body.setdefault('hand_x', 0.12)
        spec['body'] = body
        x, y = polar(PHI[n], SEAT_R)
        cast[n] = P.build_puppet(n, spec, root_loc=(x, y, root_z(spec)), root_rot_z=-math.radians(PHI[n]),
                                 body_h=0.55, seed=1000 + i)
    return G, cast, set_objs


# ----------------------------------------------------------------------------- cameras
def make_camera(name, loc, target, lens, focus=None, fstop=2.8, sensor=36.0, shift_y=0.0):
    c = bpy.data.cameras.new(name); c.lens = lens; c.sensor_width = sensor
    o = bpy.data.objects.new(name, c); bpy.context.collection.objects.link(o); o.location = loc
    d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    c.shift_y = shift_y
    if focus:
        c.dof.use_dof = True; c.dof.focus_distance = focus; c.dof.aperture_fstop = fstop
    return o


def head_world(pp):
    return pp['head'].matrix_world.translation.copy()


CLOSE_D = 4.1
CLOSE_LENS = 85


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def cameras(cast):
    """Wide shot from the open side, plus a close-up per person from across the table.
    Returns (cams, head_yaw): head_yaw[(cam, name)] = rotation of that person's head (about its z) for that camera."""
    bpy.context.view_layer.update()
    cams, yaw = {}, {}
    cams['wide'] = make_camera('cam_wide', (0.0, -5.5, 2.0), (0.0, 0.5, 1.05), 56, focus=6.6, fstop=5.6)
    wide_loc = cams['wide'].location
    for n in ORDER:
        pp = cast[n]
        h = head_world(pp)
        th_root = -math.radians(PHI[n])
        # wide: turn the head about 60 percent of the way toward the camera
        d = Vector((wide_loc.x - h.x, wide_loc.y - h.y, 0)).normalized()
        th_cam = math.atan2(d.x, -d.y)
        yaw[('wide', n)] = max(-0.8, min(0.8, 0.6 * wrap(th_cam - th_root)))
        # close-up: camera on the line between "straight across the table" and "the open side"
        f = Vector((math.sin(th_root), -math.cos(th_root), 0))
        w = 0.0 if n == 'lawler' else 0.5
        cd = (f * w + Vector((0, -1, 0)) * (1 - w)).normalized()
        loc = Vector((h.x, h.y, h.z + 0.03)) + cd * CLOSE_D
        tgt = Vector((h.x, h.y, h.z - 0.14))
        cams[n] = make_camera(f'cam_{n}', loc, tgt, CLOSE_LENS, focus=(loc - h).length, fstop=2.0)
        th_c = math.atan2(cd.x, -cd.y)
        yaw[(n, n)] = max(-0.95, min(0.95, wrap(th_c - th_root)))
    return cams, yaw
