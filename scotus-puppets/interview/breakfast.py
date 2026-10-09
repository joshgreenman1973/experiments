# Editorial-board breakfast set: a dark walnut-panelled private room, long wooden table, bentwood chairs, breakfast
# food, cast placement, lights and cameras (bpy 5.2).
# Coordinates: metres, +Z up. The table centre is the origin; the wide camera sits on -Y (the open near side of the
# table); the back wall (with the sideboard) is on +Y. Lawler sits at the centre of the far long side facing the camera;
# Smith and Facciola sit at the two short ends; the rest fill the far side.
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts')); sys.path.insert(0, HERE)
import bpy
import numpy as np
from mathutils import Vector
import puppet as P
from cast import CAST, ORDER

TABLE_L, TABLE_W, TABLE_Z = 3.5, 1.1, 0.76     # long rectangular table, top height
WALL_Y = 2.85                                    # back wall
FRONT_Y = -7.6                                   # wall behind the camera
SIDE_X = 4.6                                     # side walls
CEIL_Z = 2.75
JAW = [0.015, 0.105, 0.195, 0.285, 0.375]        # = render_assets.JAW

hexl = P.hex_lin
FAR_Y = TABLE_W / 2 + 0.2                        # root y of the far-side sitters (chest just behind the table edge)
END_X = TABLE_L / 2 + 0.2
SEAT_X = {'gelinas': -1.16, 'greenman': -0.58, 'lawler': 0.0, 'katz': 0.58, 'zagare': 1.16}
# root position and rotation (about z; the puppet faces (sin t, -cos t)) of every seat
SEATS = {n: dict(x=SEAT_X[n], y=FAR_Y, rot=0.0) for n in SEAT_X}
SEATS['smith'] = dict(x=-END_X, y=0.12, rot=math.radians(90))      # left end, facing right
SEATS['facciola'] = dict(x=END_X, y=0.12, rot=math.radians(-90))   # right end, facing left


def facing(n):
    t = SEATS[n]['rot']
    return Vector((math.sin(t), -math.cos(t), 0.0))


# ----------------------------------------------------------------------------- scene / world
def scene_setup(samples=64):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.adaptive_min_samples = 8
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 4
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
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
    bg.inputs['Color'].default_value = (0.03, 0.02, 0.014, 1)
    bg.inputs['Strength'].default_value = 1.0
    return sc


# ----------------------------------------------------------------------------- materials


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


def mat_planks(name, c1, c2, axis='x', pitch=0.14, gap=0.012, rough=0.55, coat=0.12, grain='z'):
    """Vertical (or along-axis) plank panelling: per-plank tone variation, dark grooves, grain."""
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    u = sep.outputs['X' if axis == 'x' else 'Y']
    div = N.new('ShaderNodeMath'); div.operation = 'DIVIDE'; div.inputs[1].default_value = pitch
    L.new(u, div.inputs[0])
    fl = N.new('ShaderNodeMath'); fl.operation = 'FLOOR'; L.new(div.outputs[0], fl.inputs[0])
    wn = N.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'
    L.new(fl.outputs[0], wn.inputs['W'])
    fr = N.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(div.outputs[0], fr.inputs[0])
    gp = N.new('ShaderNodeMapRange'); gp.clamp = True
    gp.inputs['From Min'].default_value = gap / pitch; gp.inputs['From Max'].default_value = gap / pitch * 2.2
    L.new(fr.outputs[0], gp.inputs['Value'])
    # grain: stretched noise along the plank
    mp = N.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = {'z': (60.0, 60.0, 2.0), 'y': (60.0, 2.0, 60.0), 'x': (2.0, 60.0, 60.0)}[grain]
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    gr = N.new('ShaderNodeTexNoise'); gr.inputs['Scale'].default_value = 3.0; gr.inputs['Detail'].default_value = 5.0
    L.new(mp.outputs['Vector'], gr.inputs['Vector'])
    mix_t = N.new('ShaderNodeMath'); mix_t.operation = 'MULTIPLY'; mix_t.inputs[1].default_value = 0.6
    L.new(wn.outputs['Value'], mix_t.inputs[0])
    mix_g = N.new('ShaderNodeMath'); mix_g.operation = 'MULTIPLY'; mix_g.inputs[1].default_value = 0.4
    L.new(gr.outputs['Fac'], mix_g.inputs[0])
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'
    L.new(mix_t.outputs[0], add.inputs[0]); L.new(mix_g.outputs[0], add.inputs[1])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = hexl(c1); cr.color_ramp.elements[1].color = hexl(c2)
    L.new(add.outputs[0], cr.inputs['Fac'])
    dark = N.new('ShaderNodeMix'); dark.data_type = 'RGBA'; dark.inputs['B'].default_value = (0.004, 0.002, 0.001, 1)
    L.new(gp.outputs['Result'], dark.inputs['Factor'])
    dark.inputs['A'].default_value = (0.004, 0.002, 0.001, 1)
    L.new(cr.outputs['Color'], dark.inputs['B'])
    L.new(dark.outputs['Result'], p.inputs['Base Color'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.4; bp.inputs['Distance'].default_value = 0.004
    L.new(gp.outputs['Result'], bp.inputs['Height']); L.new(bp.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = 0.25
    return m


def mat_floor(name, c1='#4a2a17', c2='#3a2012'):
    """Worn dark wood floor: long planks, tone and wear variation."""
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    br = N.new('ShaderNodeTexBrick')
    br.offset = 0.5; br.offset_frequency = 2
    br.inputs['Color1'].default_value = hexl(c1); br.inputs['Color2'].default_value = hexl(c2)
    br.inputs['Mortar'].default_value = hexl('#1a0d06')
    br.inputs['Mortar Size'].default_value = 0.004; br.inputs['Brick Width'].default_value = 1.6
    br.inputs['Row Height'].default_value = 0.16
    L.new(tc.outputs['Object'], br.inputs['Vector'])
    wear = N.new('ShaderNodeTexNoise'); wear.inputs['Scale'].default_value = 5.0; wear.inputs['Detail'].default_value = 6.0
    L.new(tc.outputs['Object'], wear.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.65; mr.inputs['To Max'].default_value = 1.25
    L.new(wear.outputs['Fac'], mr.inputs['Value'])
    gray = N.new('ShaderNodeCombineColor')
    for k in ('Red', 'Green', 'Blue'):
        L.new(mr.outputs['Result'], gray.inputs[k])
    mul = N.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
    L.new(br.outputs['Color'], mul.inputs['A']); L.new(gray.outputs['Color'], mul.inputs['B'])
    L.new(mul.outputs['Result'], p.inputs['Base Color'])
    rg = N.new('ShaderNodeMapRange'); rg.inputs['To Min'].default_value = 0.35; rg.inputs['To Max'].default_value = 0.7
    L.new(wear.outputs['Fac'], rg.inputs['Value']); L.new(rg.outputs['Result'], p.inputs['Roughness'])
    p.inputs['Coat Weight'].default_value = 0.2
    p.inputs['Coat Roughness'].default_value = 0.2
    return m


def mat_stripe_napkin(name):
    """White napkin with two blue stripes parallel to its edges."""
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    ax = N.new('ShaderNodeMath'); ax.operation = 'ABSOLUTE'; L.new(sep.outputs['X'], ax.inputs[0])
    ay = N.new('ShaderNodeMath'); ay.operation = 'ABSOLUTE'; L.new(sep.outputs['Y'], ay.inputs[0])
    mx = N.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'; L.new(ax.outputs[0], mx.inputs[0]); L.new(ay.outputs[0], mx.inputs[1])
    masks = []
    for lo, hi in ((0.066, 0.074), (0.082, 0.088)):
        a = N.new('ShaderNodeMath'); a.operation = 'GREATER_THAN'; a.inputs[1].default_value = lo; L.new(mx.outputs[0], a.inputs[0])
        b = N.new('ShaderNodeMath'); b.operation = 'LESS_THAN'; b.inputs[1].default_value = hi; L.new(mx.outputs[0], b.inputs[0])
        c = N.new('ShaderNodeMath'); c.operation = 'MULTIPLY'; L.new(a.outputs[0], c.inputs[0]); L.new(b.outputs[0], c.inputs[1])
        masks.append(c)
    s = N.new('ShaderNodeMath'); s.operation = 'ADD'; L.new(masks[0].outputs[0], s.inputs[0]); L.new(masks[1].outputs[0], s.inputs[1])
    mxc = N.new('ShaderNodeMix'); mxc.data_type = 'RGBA'
    mxc.inputs['A'].default_value = hexl('#f6f4ee'); mxc.inputs['B'].default_value = hexl('#2f5aa8')
    L.new(s.outputs[0], mxc.inputs['Factor'])
    L.new(mxc.outputs['Result'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.9
    p.inputs['Sheen Weight'].default_value = 0.5
    return m


def mat_shade(name, hexc='#efe2c4', glow=3.5):
    """Cream lampshade that glows warmly from inside."""
    m, nt, p = P._new_mat(name)
    p.inputs['Base Color'].default_value = hexl(hexc)
    p.inputs['Roughness'].default_value = 0.8
    p.inputs['Emission Color'].default_value = hexl('#ffcf8a')
    p.inputs['Emission Strength'].default_value = glow
    return m


class Mats:
    pass


def make_mats():
    M = Mats()
    M.table = mat_oak('table_wood', '#6a3e1f', '#98602f', rough=0.5, coat=0.12)
    M.walnut = mat_oak('walnut', '#2a140a', '#4a2614', rough=0.42, coat=0.25)
    M.rustic = mat_oak('rustic', '#4a2814', '#7a4a26', rough=0.6, coat=0.05, scale=(1.0, 6.0, 1.0))
    M.floor = mat_floor('floor')
    M.panel_x = mat_planks('panel_x', '#3a1d0e', '#5a3118', axis='x')
    M.panel_y = mat_planks('panel_y', '#3a1d0e', '#5a3118', axis='y')
    M.ceiling = mat_planks('ceiling', '#2a140a', '#43230f', axis='x', pitch=0.18, coat=0.05, grain='y')
    M.ceiling_y = mat_planks('ceiling_y', '#2a140a', '#43230f', axis='y', pitch=0.18, coat=0.05, grain='x')
    M.ceramic = plain('ceramic', '#f6f3ec', rough=0.12, coat=0.6, spec=0.6)
    M.brass = plain('brass', '#c79a45', rough=0.28, metallic=1.0)
    M.silver = plain('silver', '#d6d8dc', rough=0.16, metallic=1.0)
    M.iron = mat_noise('iron', '#1b1c1e', '#34353a', scale=30, rough=0.55, bump=0.4, spec=0.3)
    M.iron.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.8
    M.mirror = plain('mirror', '#4c463d', rough=0.28, metallic=0.9)   # antiqued, dim warm reflections
    M.leather = plain('leather', '#0d0d0f', rough=0.42, coat=0.3)
    M.black = plain('black_plastic', '#17181a', rough=0.35, coat=0.3)
    M.shade = mat_shade('shade')
    M.glass = mat_glass('glass')
    M.glass_tint = mat_glass('glass_tint', (0.92, 0.97, 1.0, 1))
    M.water = plain('water', '#c9dff0', rough=0.05, coat=0.5, spec=0.6)
    M.coffee = plain('coffee', '#24140b', rough=0.08, coat=0.6, spec=0.6)
    M.oj = plain('oj', '#ff9a1a', rough=0.12, coat=0.4, spec=0.5)
    M.croissant = mat_noise('croissant', '#c47a2c', '#ecb35a', scale=11, rough=0.45, coat=0.25, bump=0.3, sss=0.05)
    M.croissant2 = mat_noise('croissant2', '#a05d1e', '#e29a43', scale=16, rough=0.45, coat=0.25, bump=0.3)
    M.bagel = mat_noise('bagel', '#b9783a', '#e6b172', scale=9, rough=0.55, coat=0.1, bump=0.25)
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
    M.butter = plain('butter', '#f6e083', rough=0.35)
    M.jam = plain('jam', '#8c0f1c', rough=0.1, coat=0.6)
    M.jam2 = plain('jam2', '#c8581c', rough=0.1, coat=0.6)
    M.cream = plain('cream', '#f7f2e4', rough=0.3, coat=0.2)
    M.napkin = mat_stripe_napkin('napkin')
    M.notebook = [plain('nb0', '#223b6a', rough=0.5, coat=0.1), plain('nb1', '#8f2b2b', rough=0.5, coat=0.1),
                  plain('nb2', '#1d1d1f', rough=0.5, coat=0.1)]
    M.paper = plain('paper', '#f5f1e6', rough=0.8)
    M.book = [plain(f'book{i}', c, rough=0.6, coat=0.1) for i, c in enumerate(
        ('#7c1d1a', '#5a1a14', '#8a3b1c', '#4a2a16', '#9a2e22', '#3a2415', '#6b2a1a', '#a24a24', '#2f3a2a'))]
    M.pages = plain('pages', '#e8dcc0', rough=0.9)
    M.petal = plain('petal', '#f7f1e4', rough=0.55, sheen=0.4)
    M.flame = mat_emit('flame', (1.0, 0.65, 0.2, 1), 25.0)
    M.bulb = mat_emit('bulb', (1.0, 0.72, 0.38, 1), 40.0)
    M.porthole = mat_emit('porthole', (1.0, 0.74, 0.28, 1), 14.0)
    M.screen = plain('screen', '#0c1a2c', rough=0.05, coat=0.8, spec=0.8)
    M.red_led = mat_emit('red_led', (1.0, 0.05, 0.03, 1), 12.0)
    M.recorder = plain('rec', '#8f9298', rough=0.35, metallic=0.6)
    return M


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


def lathe(name, prof, mat, loc=(0, 0, 0), parent=None, segs=56, sxy=(1.0, 1.0), rot=(0, 0, 0), smooth=True, pleats=None):
    """Solid of revolution from [(r, z), ...]; r == 0 closes the profile at a pole. pleats=(n, amp) folds the radius."""
    rings = [(z, r, r, 0.0, 0) for (r, z) in prof]
    V, F, M = P.loft(rings, segs, 2.0)
    if pleats:
        th = np.arctan2(V[:, 1], V[:, 0])
        k = 1.0 + pleats[1] * np.cos(pleats[0] * th)
        V = V.copy(); V[:, 0] *= k; V[:, 1] *= k
    V = V * np.array([sxy[0], sxy[1], 1.0])
    ob = P.mesh_obj(name, V, F, M, [mat], smooth=smooth, parent=parent, location=loc)
    ob.rotation_euler = rot
    return ob


# ----------------------------------------------------------------------------- tableware and food
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


def silver_pot(name, M, parent, scale=1.0, z0=0.0):
    """Classic silver coffee pot: bell body, domed lid, spout and a dark handle."""
    s_ = scale
    prof = [(0, z0), (0.055 * s_, z0), (0.072 * s_, z0 + 0.018 * s_), (0.07 * s_, z0 + 0.1 * s_),
            (0.052 * s_, z0 + 0.19 * s_), (0.044 * s_, z0 + 0.205 * s_), (0.0, z0 + 0.205 * s_)]
    lathe(name + '_body', prof, M.silver, (0, 0, 0), parent, segs=40)
    lathe(name + '_lid', [(0.0, z0 + 0.205 * s_), (0.046 * s_, z0 + 0.204 * s_), (0.036 * s_, z0 + 0.226 * s_),
                          (0.014 * s_, z0 + 0.238 * s_), (0.0, z0 + 0.24 * s_)], M.silver, (0, 0, 0), parent, segs=32)
    sphere(name + '_knob', 0.013 * s_, M.black, (0, 0, z0 + 0.248 * s_), parent=parent, segs=12, rings=8)
    P.tube(name + '_spout', [(0.05 * s_, 0, z0 + 0.04 * s_), (0.1 * s_, 0, z0 + 0.12 * s_), (0.135 * s_, 0, z0 + 0.19 * s_)],
           [0.02 * s_, 0.014 * s_, 0.008 * s_], [M.silver], nseg=10, parent=parent)
    P.tube(name + '_handle', [(-0.062 * s_, 0, z0 + 0.18 * s_), (-0.125 * s_, 0, z0 + 0.15 * s_),
                              (-0.128 * s_, 0, z0 + 0.07 * s_), (-0.068 * s_, 0, z0 + 0.035 * s_)],
           [0.011 * s_] * 4, [M.black], nseg=10, parent=parent)


def votive(name, M, parent, loc):
    g = group(name, loc); g.parent = parent; g.location = loc
    lathe(name + '_cup', [(0, 0.0), (0.026, 0.0), (0.03, 0.003), (0.034, 0.055), (0.0325, 0.056), (0.0, 0.004)], M.glass, (0, 0, 0), g, segs=24)
    sphere(name + '_flame', 1.0, M.flame, (0, 0, 0.034), scale=(0.005, 0.005, 0.011), parent=g, segs=10, rings=8)
    lathe(name + '_wax', [(0, 0.004), (0.0235, 0.005), (0.0245, 0.022), (0.0, 0.022)], M.cream, (0, 0, 0), g, segs=20)
    return g


def flowers(name, M, parent, loc, rng, scale=1.0):
    """Low white flower arrangement in a white bowl."""
    g = group(name, loc); g.parent = parent; g.location = loc
    lathe(name + '_bowl', [(0, 0.0), (0.05 * scale, 0.0), (0.075 * scale, 0.02 * scale), (0.09 * scale, 0.055 * scale),
                           (0.085 * scale, 0.056 * scale), (0.0, 0.03 * scale)], M.ceramic, (0, 0, 0), g, segs=32)
    for k in range(9):
        a = rng.uniform(0, 6.28); r = rng.uniform(0.0, 0.07) * scale
        sphere(f'{name}_leaf{k}', 1.0, M.leaf, (r * math.cos(a), r * math.sin(a), 0.06 * scale),
               scale=(0.03 * scale, 0.012 * scale, 0.006 * scale), parent=g, segs=10, rings=6, rot=(0, 0.3, a))
    for k in range(17):
        a = rng.uniform(0, 6.28); r = math.sqrt(rng.uniform(0, 1)) * 0.065 * scale
        sphere(f'{name}_f{k}', rng.uniform(0.015, 0.022) * scale, M.petal,
               (r * math.cos(a), r * math.sin(a), (0.065 + 0.03 * (1 - r / (0.07 * scale)) ** 0.5) * scale),
               scale=(1, 1, 0.8), parent=g, segs=12, rings=8)
    return g


def build_table(M, G):
    S = G['set']
    L_, W_, Z_ = TABLE_L, TABLE_W, TABLE_Z
    S.append(cube('table_top', (L_, W_, 0.06), (0, 0, Z_ - 0.03), M.table, bevel=0.018))
    S.append(cube('table_apron', (L_ - 0.3, W_ - 0.24, 0.1), (0, 0, Z_ - 0.11), M.walnut, bevel=0.006))
    for sx in (-1, 1):
        for sy in (-1, 1):
            S.append(cube(f'table_leg{sx}{sy}', (0.1, 0.1, Z_ - 0.06), (sx * (L_ / 2 - 0.22), sy * (W_ / 2 - 0.14), (Z_ - 0.06) / 2),
                          M.walnut, bevel=0.012))
    S.append(cube('table_stretcher', (L_ - 0.6, 0.05, 0.05), (0, 0, 0.2), M.walnut, bevel=0.008))


def place_settings(M, G, rng):
    """White plate, striped napkin, coffee cup, water and juice glasses at every seat (local frame: -y = toward the middle)."""
    z0 = TABLE_Z
    for i, n in enumerate(ORDER):
        st = SEATS[n]
        f = facing(n)
        ox, oy = st['x'] + f.x * 0.55, st['y'] + f.y * 0.55          # 0.2 m inside the table edge
        if n in ('smith', 'facciola'):
            ox, oy = st['x'] + f.x * 0.4, st['y']
        g = group(f'place_{n}', (ox, oy, 0), st['rot'])
        cube(f'nap_{n}', (0.2, 0.2, 0.004), (0, 0.03, z0 + 0.002), M.napkin, g, rot=(0, 0, 0.06 * (i % 3 - 1)))
        plate(f'plate_{n}', 0.098, M.ceramic, (0, 0.03, z0 + 0.004), g)
        kind = i % 4
        if kind == 0:
            croissant(f'cr_{n}', M, g, (0.0, 0.0, z0 + 0.011), 0.2 + 0.1 * i, 0.82)
        elif kind == 1:
            bagel(f'bg_{n}', M, g, (0.0, 0.03, z0 + 0.03), rng.uniform(0, 3))
            cube(f'bt_{n}', (0.03, 0.02, 0.012), (0.045, 0.0, z0 + 0.016), M.butter, g, bevel=0.002)
        elif kind == 2:
            croissant(f'cr_{n}', M, g, (0.0, 0.0, z0 + 0.011), -0.5, 0.78, M.croissant2)
            for k in range(3):
                strawberry(f'sb_{n}{k}', M, g, (0.05 - 0.03 * k, 0.045, z0 + 0.025))
        else:
            bagel(f'bg_{n}', M, g, (0.0, 0.03, z0 + 0.03), rng.uniform(0, 3))
            strawberry(f'sbx_{n}', M, g, (0.0, 0.0, z0 + 0.025))
        cs = group(f'cup_{n}', (0, 0, 0), 0.4 * (i - 3)); cs.parent = g; cs.location = (-0.17, -0.12, z0)
        cs.scale = (1.25, 1.25, 1.25)
        cup_saucer(f'cup_{n}', M, cs, handle_dir=1)
        wg = group(f'wglass_{n}', (0, 0, 0)); wg.parent = g; wg.location = (0.15, -0.13, z0)
        tumbler(f'wg_{n}', M, wg, M.water)
        if i % 2 == 0:
            jg = group(f'jglass_{n}', (0, 0, 0)); jg.parent = g; jg.location = (0.2, -0.02, z0)
            tumbler(f'jg_{n}', M, jg, M.oj, r=0.029, h=0.1)
    for k, n in enumerate(('smith', 'greenman', 'katz')):
        g = bpy.data.objects[f'place_{n}']
        nb = group(f'nb_{n}', (0, 0, 0), 0.25 * (k - 1)); nb.parent = g; nb.location = (-0.285, 0.02, z0)
        cube(f'nb_cover_{n}', (0.15, 0.205, 0.012), (0, 0, 0.006), M.notebook[k], nb, bevel=0.002)
        cube(f'nb_pages_{n}', (0.142, 0.198, 0.009), (0.004, 0, 0.007), M.paper, nb)
        P.tube(f'pen_{n}', [(-0.04, 0.0, 0.0145), (0.05, 0.02, 0.0145)], [0.0042, 0.0042], [M.black], nseg=8, parent=nb)
        cube(f'nb_band_{n}', (0.006, 0.206, 0.0135), (0.056, 0, 0.0066), M.black, nb)


def center_items(M, G, rng):
    """Shared breakfast down the middle of the long table (kept low, clear of every sitter's place)."""
    z0 = TABLE_Z

    def at(name, x, y, rot=0.0, s=1.0):
        g = group(name, (x, y, 0), rot); g.scale = (s, s, s); return g

    # croissant basket (bread basket with a napkin)
    g = at('basket', -0.78, -0.02, 0.4, 1.3)
    lathe('basket_body', [(0, z0), (0.115, z0), (0.13, z0 + 0.03), (0.145, z0 + 0.075), (0.138, z0 + 0.077), (0.12, z0 + 0.04),
                          (0.0, z0 + 0.012)], M.wicker, (0, 0, 0), g, segs=48)
    lathe('basket_rim', [(0.138, z0 + 0.073), (0.147, z0 + 0.0755), (0.146, z0 + 0.081), (0.137, z0 + 0.079)], M.wicker,
          (0, 0, 0), g, segs=48)
    lathe('basket_cloth', [(0, z0 + 0.03), (0.12, z0 + 0.034), (0.14, z0 + 0.07), (0.0, z0 + 0.04)],
          plain('bcloth', '#f4ece0', rough=0.9, sheen=0.4), (0, 0, 0), g, segs=40)
    for k, (x, y, rz, s_) in enumerate(((-0.035, -0.02, 0.5, 0.95), (0.04, -0.03, 2.6, 0.95), (0.0, 0.045, -1.4, 0.95),
                                        (0.0, 0.0, 1.2, 0.88))):
        croissant(f'bcr{k}', M, g, (x, y, z0 + 0.045 + 0.018 * (k == 3)), rz, s_, M.croissant if k % 2 == 0 else M.croissant2)
    # fruit platter A: melon, orange segments, berries, grapes
    rr = np.random.default_rng(3)
    g = at('fruitA', 0.8, 0.0, -0.4, 1.25)
    plate('fruitA_plate', 0.2, plain('platter', '#fbfaf5', rough=0.12, coat=0.6), (0, 0, z0), g, sxy=(1.15, 0.85))
    for k in range(5):
        melon_slice(f'mel{k}', M, g, (-0.12 + 0.06 * k, -0.045 + 0.02 * math.sin(k), z0 + 0.02), 0.2 * (k - 2),
                    M.melon if k % 2 == 0 else M.honeydew, M.rind, r=0.055)
    for k in range(7):
        orange_segment(f'osg{k}', M, g, (0.09 + 0.03 * math.cos(k), 0.04 + 0.025 * math.sin(k), z0 + 0.02 + 0.004 * (k % 2)), k * 0.9)
    for k in range(10):
        x, y = rr.uniform(-0.1, 0.0), rr.uniform(0.0, 0.06)
        sphere(f'bb{k}', 0.0072, M.blueberry, (x - 0.02 + 0.015 * (k % 3), y + 0.02, z0 + 0.02 + 0.006 * (k % 2)), parent=g, segs=10, rings=7)
    for k in range(6):
        sphere(f'rb{k}', 0.0095, M.raspberry, (-0.05 + 0.017 * k, 0.065 - 0.01 * (k % 2), z0 + 0.026), parent=g, segs=10, rings=7)
    grapes('grapesA', M, g, (0.0, -0.01, z0 + 0.012), M.grape, rr, 14)
    # fruit platter B (strawberries, grapes, blueberries), near side
    g = at('fruitB', -0.32, -0.34, 0.3, 1.2)
    plate('fruitB_plate', 0.16, plain('platterB', '#fbfaf5', rough=0.12, coat=0.6), (0, 0, z0), g)
    for k in range(7):
        a = k * 0.9
        strawberry(f'sbB{k}', M, g, (0.06 * math.cos(a), 0.06 * math.sin(a), z0 + 0.03))
    grapes('grapesB', M, g, (0.0, 0.03, z0 + 0.012), M.grape_r, rr, 12)
    for k in range(9):
        sphere(f'bbB{k}', 0.0072, M.blueberry, (0.02 * math.cos(k * 1.4), -0.02 + 0.02 * math.sin(k * 1.4), z0 + 0.014 + 0.007 * (k % 2)),
               parent=g, segs=10, rings=7)
    # plate of bacon
    g = at('baconplate', 0.02, -0.04, 0.05, 1.35)
    plate('bacon_plate', 0.15, M.ceramic, (0, 0, z0), g, sxy=(1.25, 0.8))
    for k in range(6):
        bacon_strip(f'bacon{k}', M, g, (0.0 + 0.004 * k, -0.04 + 0.016 * k, z0 + 0.012 + 0.006 * (k % 3)), 0.15 * (k - 2.5) + 0.1, rng)
    # bagels with cream cheese, butter and jam (small board)
    g = at('bagelboard', 0.5, -0.31, 0.2, 1.0)
    cube('board', (0.3, 0.2, 0.02), (0, 0, z0 + 0.01), M.table, g, bevel=0.004)
    for k, (x, y) in enumerate(((-0.07, 0.02), (0.03, -0.035))):
        bagel(f'bgb{k}', M, g, (x, y, z0 + 0.042), k * 0.7)
    lathe('ramekin', [(0, z0 + 0.02), (0.03, z0 + 0.02), (0.034, z0 + 0.04), (0.031, z0 + 0.04), (0.0, z0 + 0.025)],
          M.ceramic, (0.1, 0.04, 0), g, segs=24)
    lathe('creamcheese', [(0, z0 + 0.038), (0.029, z0 + 0.036), (0.0, z0 + 0.046)], M.cream, (0.1, 0.04, 0), g, segs=24)
    g2 = at('butterdish', 0.88, -0.3, -0.3)
    cube('butter_dish', (0.1, 0.07, 0.01), (0, 0, z0 + 0.005), M.ceramic, g2, bevel=0.003)
    cube('butter', (0.07, 0.042, 0.03), (0, 0, z0 + 0.025), M.butter, g2, bevel=0.004)
    for k, (x, jm) in enumerate(((1.0, M.jam), (0.96, M.jam2))):
        gj = at(f'jar{k}', x - 0.0, -0.18 - 0.1 * k, 0)
        lathe('jar_g', [(0, z0), (0.028, z0), (0.03, z0 + 0.008), (0.03, z0 + 0.052), (0.0, z0 + 0.052)], M.glass, (0, 0, 0), gj, segs=24)
        lathe('jar_j', [(0, z0 + 0.003), (0.0265, z0 + 0.004), (0.0275, z0 + 0.044), (0.0, z0 + 0.044)], jm, (0, 0, 0), gj, segs=24)
        lathe('jar_lid', [(0, z0 + 0.052), (0.0305, z0 + 0.052), (0.0305, z0 + 0.062), (0.0, z0 + 0.062)], M.brass, (0, 0, 0), gj, segs=24)
    # silver coffee pots, creamer and sugar
    g = at('pot1', -0.3, 0.08, 0.2); silver_pot('pot1', M, g, 1.15, z0)
    g = at('pot2', 0.34, 0.1, 3.0); silver_pot('pot2', M, g, 0.95, z0)
    g = at('creamer', -0.12, 0.04, 0.0)
    lathe('creamer', [(0, z0), (0.03, z0), (0.036, z0 + 0.02), (0.03, z0 + 0.07), (0.036, z0 + 0.085), (0.0, z0 + 0.085)], M.ceramic, (0, 0, 0), g, segs=32)
    g = at('sugar', 0.14, 0.02, 0.0)
    lathe('sugar', [(0, z0), (0.04, z0), (0.044, z0 + 0.03), (0.038, z0 + 0.055), (0.0, z0 + 0.055)], M.ceramic, (0, 0, 0), g, segs=32)
    lathe('sugar_lid', [(0, z0 + 0.055), (0.04, z0 + 0.055), (0.03, z0 + 0.07), (0.0, z0 + 0.076)], M.ceramic, (0, 0, 0), g, segs=32)
    # juice pitcher
    g = at('pitcher', 0.56, 0.1, 0.0)
    lathe('pitcher_glass', [(0, z0), (0.05, z0), (0.056, z0 + 0.01), (0.062, z0 + 0.14), (0.058, z0 + 0.15), (0.05, z0 + 0.013), (0.0, z0 + 0.011)],
          M.glass, (0, 0, 0), g, segs=40)
    lathe('pitcher_oj', [(0, z0 + 0.012), (0.049, z0 + 0.014), (0.058, z0 + 0.1), (0.0, z0 + 0.1)], M.oj, (0, 0, 0), g, segs=40)
    P.tube('pitcher_handle', [(0.06, 0.0, z0 + 0.13), (0.09, 0.0, z0 + 0.11), (0.092, 0.0, z0 + 0.05), (0.056, 0.0, z0 + 0.025)],
           [0.005] * 4, [M.glass_tint], nseg=8, parent=g)
    # low white flowers and candle votives along the middle
    flowers('flowers1', M, bpy.data.objects['table_top'], (-1.15, 0.04, z0 - (TABLE_Z - 0.03)), rr, 1.0)
    flowers('flowers2', M, bpy.data.objects['table_top'], (1.28, -0.02, z0 - (TABLE_Z - 0.03)), rr, 1.0)
    for k, (x, y) in enumerate(((-0.55, -0.2), (0.15, -0.22), (0.7, 0.0), (-1.45, -0.28), (1.45, -0.3))):
        votive(f'votive{k}', M, bpy.data.objects['table_top'], (x, y, z0 - (TABLE_Z - 0.03)))
    # phone and recorder near the centre (flat)
    g = at('phone', -0.1, -0.2, 0.6)
    cube('phone_body', (0.072, 0.152, 0.008), (0, 0, z0 + 0.004), M.black, g, bevel=0.003)
    cube('phone_screen', (0.066, 0.144, 0.0012), (0, 0, z0 + 0.0086), M.screen, g)
    g = at('recorder', 0.05, -0.17, -0.35)
    cube('rec_body', (0.048, 0.118, 0.018), (0, 0, z0 + 0.009), M.recorder, g, bevel=0.005)
    cube('rec_face', (0.036, 0.07, 0.002), (0, 0.01, z0 + 0.019), M.black, g)
    sphere('rec_led', 0.0035, M.red_led, (0.0, -0.04, z0 + 0.0185), parent=g, segs=10, rings=6)


def book_stack(name, M, loc, rng, n=5, parent=None):
    g = group(name, loc, rng.uniform(-0.25, 0.25))
    z = 0.0
    for k in range(n):
        w, d, h = rng.uniform(0.2, 0.27), rng.uniform(0.14, 0.19), rng.uniform(0.028, 0.05)
        c = M.book[rng.integers(len(M.book))]
        o = rng.uniform(-0.012, 0.012)
        cube(f'{name}_b{k}', (w, d, h), (o, rng.uniform(-0.01, 0.01), z + h / 2), c, g, rot=(0, 0, rng.uniform(-0.12, 0.12)), bevel=0.003)
        cube(f'{name}_p{k}', (w - 0.012, d + 0.004, h - 0.01), (o, 0.004, z + h / 2), M.pages, g)
        z += h
    return g


def gear(name, M, loc, rot_z=0.0, r=0.3, teeth=22):
    """Big cast-iron gear standing on its edge (axis toward the room)."""
    g = group(name, loc, rot_z)
    g.rotation_euler = (math.pi / 2, 0, rot_z)
    lathe(name + '_disc', [(0, -0.03), (r * 0.95, -0.03), (r * 0.95, 0.03), (0, 0.03)], M.iron, (0, 0, 0), g, segs=64)
    lathe(name + '_hub', [(0, -0.045), (r * 0.22, -0.045), (r * 0.22, 0.045), (0, 0.045)], M.iron, (0, 0, 0), g, segs=32)
    for k in range(teeth):
        a = 2 * math.pi * k / teeth
        cube(f'{name}_t{k}', (r * 0.14, r * 0.15, 0.06), (r * 1.02 * math.cos(a), r * 1.02 * math.sin(a), 0), M.iron, g,
             rot=(0, 0, a + math.pi / 2), bevel=0.004)
    for k in range(6):  # lighten the disc: dark spoke windows suggested by raised spokes
        a = 2 * math.pi * k / 6
        cube(f'{name}_s{k}', (r * 0.6, r * 0.09, 0.07), (r * 0.55 * math.cos(a), r * 0.55 * math.sin(a), 0), M.iron, g,
             rot=(0, 0, a), bevel=0.004)
    return g


def brass_lamp(name, M, loc, parent=None):
    g = group(name, loc)
    lathe(name + '_base', [(0, 0.0), (0.075, 0.0), (0.08, 0.012), (0.04, 0.04), (0.03, 0.09), (0.05, 0.13), (0.045, 0.2),
                           (0.012, 0.24), (0.012, 0.34), (0.0, 0.34)], M.brass, (0, 0, 0), g, segs=32)
    lathe(name + '_shade', [(0.0, 0.5), (0.1, 0.5), (0.165, 0.33), (0.158, 0.32), (0.095, 0.485), (0.0, 0.485)], M.shade,
          (0, 0, 0), g, segs=72, pleats=(36, 0.035), smooth=False)
    lathe(name + '_cap', [(0.0, 0.5), (0.1, 0.5), (0.1, 0.505), (0.0, 0.505)], M.brass, (0, 0, 0), g, segs=24)
    return g


def mirror(name, M, loc, w, h, parent=None):
    g = group(name, loc)
    cube(name + '_frame', (w + 0.07, 0.04, h + 0.07), (0, 0, 0), M.brass, g, bevel=0.03)
    cube(name + '_glass', (w, 0.012, h), (0, -0.022, 0), M.mirror, g, bevel=0.025)
    return g


def build_room(M, G, work):
    S = G['set']
    rng = np.random.default_rng(7)
    wy = WALL_Y
    # floor and ceiling
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, (wy + FRONT_Y) / 2, 0))
    fl = bpy.context.object; fl.name = 'floor'; fl.scale = (2 * SIDE_X, wy - FRONT_Y, 1); fl.data.materials.append(M.floor); S.append(fl)
    ce = cube('ceiling', (2 * SIDE_X, wy - FRONT_Y, 0.1), (0, (wy + FRONT_Y) / 2, CEIL_Z + 0.05), M.ceiling)
    S.append(ce)
    # walnut plank paneling on all four walls
    ln = wy - FRONT_Y
    S.append(cube('wall_back', (2 * SIDE_X, 0.2, CEIL_Z), (0, wy + 0.1, CEIL_Z / 2), M.panel_x))
    S.append(cube('wall_front', (2 * SIDE_X, 0.2, CEIL_Z), (0, FRONT_Y - 0.1, CEIL_Z / 2), M.panel_x))
    S.append(cube('wall_left', (0.2, ln, CEIL_Z), (-SIDE_X - 0.1, (wy + FRONT_Y) / 2, CEIL_Z / 2), M.panel_y))
    S.append(cube('wall_right', (0.2, ln, CEIL_Z), (SIDE_X + 0.1, (wy + FRONT_Y) / 2, CEIL_Z / 2), M.panel_y))
    S.append(cube('baseboard', (2 * SIDE_X, 0.04, 0.16), (0, wy - 0.02, 0.08), M.walnut, bevel=0.006))
    S.append(cube('crown', (2 * SIDE_X, 0.06, 0.08), (0, wy - 0.03, CEIL_Z - 0.04), M.walnut, bevel=0.006))
    # ceiling beams and rows of small exposed warm bulbs in brass fittings
    for k, y in enumerate((-1.6, 0.4, 2.2)):
        S.append(cube(f'beam{k}', (2 * SIDE_X, 0.14, 0.07), (0, y, CEIL_Z - 0.035), M.walnut, bevel=0.008))
        for i in range(-6, 7):
            x = i * 0.6
            S.append(cube(f'sock{k}_{i}', (0.03, 0.03, 0.035), (x, y, CEIL_Z - 0.085), M.brass))
            sp = sphere(f'bulb{k}_{i}', 0.019, M.bulb, (x, y, CEIL_Z - 0.12), segs=10, rings=6)
            sp.visible_shadow = False
            sp.visible_diffuse = False; sp.visible_glossy = False; sp.visible_transmission = False   # seen, but not a light
            S.append(sp)
    # long heavy rustic ledge / sideboard along the back wall
    ly = wy - 0.32
    S.append(cube('ledge_top', (8.0, 0.56, 0.09), (0, ly, 0.99), M.rustic, bevel=0.012))
    S.append(cube('ledge_body', (7.8, 0.5, 0.88), (0, ly, 0.44), M.walnut, bevel=0.01))
    for i, x in enumerate(np.linspace(-3.4, 3.4, 8)):
        S.append(cube(f'ledge_panel{i}', (0.8, 0.02, 0.7), (x, ly - 0.255, 0.45), M.rustic, bevel=0.01))
    # decor on the ledge: lamps in the gaps between heads, book stacks, the gear
    for i, x in enumerate((-2.55, -1.05, 1.05, 2.55)):
        brass_lamp(f'lamp{i}', M, (x, ly, 1.035))
    G['lamp_pos'] = [(x, ly, 1.035 + 0.42) for x in (-2.55, -1.05, 1.05, 2.55)]
    for i, (x, n_) in enumerate(((-1.8, 5), (-0.35, 4), (0.45, 6), (1.8, 4), (-3.3, 3))):
        book_stack(f'books{i}', M, (x, ly + 0.02, 1.035), rng, n_)
    gear('gear', M, (3.35, ly + 0.08, 1.035 + 0.3), 0.0)
    # vintage mirrors with rounded corners and brass edges on the paneling above
    for i, (x, w_, h_) in enumerate(((-2.0, 0.62, 0.9), (0.0, 0.7, 0.96), (2.0, 0.62, 0.9), (-3.4, 0.5, 0.7))):
        mirror(f'mirror{i}', M, (x, wy - 0.02, 1.95), w_, h_)
    # a round porthole window glowing warm yellow on the left wall
    ph = group('porthole', (-SIDE_X + 0.02, 1.2, 1.7))
    ph.rotation_euler = (0, 0, math.pi / 2)
    ring = torus('porthole_ring', 0.2, 0.03, M.brass, (0, 0, 0), ph, rot=(math.pi / 2, 0, 0))
    glow = lathe('porthole_glow', [(0, 0.0), (0.19, 0.0), (0.19, 0.012), (0, 0.012)], M.porthole, (0, 0.0, 0), ph, segs=48, rot=(math.pi / 2, 0, 0))
    S += [ring, glow]
    G['porthole_pos'] = (-SIDE_X + 0.25, 1.2, 1.7)
    return S


def build_chair(name, M, G, idx):
    """Bentwood cafe chair: black leather seat, dark bentwood legs, back loop and hoop."""
    st = SEATS[name]
    f = facing(name)
    pos = (st['x'] - f.x * 0.1, st['y'] - f.y * 0.1, 0)
    g = group(f'chair_{name}', pos, st['rot'])
    S = G['set']
    zs = 0.5
    S.append(lathe(f'{name}_seat', [(0, zs + 0.0), (0.205, zs + 0.0), (0.215, zs + 0.02), (0.205, zs + 0.045), (0.12, zs + 0.058), (0, zs + 0.06)],
                   M.leather, (0, 0, 0), g, segs=40))
    S.append(torus(f'{name}_seatring', 0.205, 0.016, M.walnut, (0, 0, zs - 0.005), g, maj_seg=40, min_seg=8))
    S.append(torus(f'{name}_stretch', 0.18, 0.011, M.walnut, (0, 0, 0.2), g, maj_seg=36, min_seg=8))
    for sx in (-1, 1):
        for sy in (-1, 1):
            top = (sx * 0.15, sy * 0.15, zs - 0.01)
            bot = (sx * 0.2, sy * 0.2, 0.0)
            if sy == 1:   # rear legs run up into the back
                pts = [bot, (sx * 0.19, 0.19, 0.25), top, (sx * 0.16, 0.2, 0.7), (sx * 0.13, 0.21, 0.95)]
                rad = [0.014, 0.014, 0.015, 0.014, 0.012]
            else:
                pts = [bot, (sx * 0.18, sy * 0.18, 0.25), top]
                rad = [0.013, 0.014, 0.015]
            S.append(P.tube(f'{name}_leg{sx}{sy}', pts, rad, [M.walnut], nseg=10, parent=g))
    # bentwood back: a loop across the top and a smaller hoop below it
    th = np.linspace(math.pi, 0, 17)
    loop = [(0.13 * math.cos(a), 0.215 + 0.02 * math.sin(a), 0.95 + 0.07 * math.sin(a)) for a in th]
    S.append(P.tube(f'{name}_loop', loop, [0.012] * len(loop), [M.walnut], nseg=10, parent=g, caps=True))
    hoop = [(0.15 * math.cos(a), 0.205, 0.72 + 0.055 * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 15)]
    S.append(P.tube(f'{name}_hoop', hoop, [0.011] * len(hoop), [M.walnut], nseg=10, parent=g))
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


def add_point(name, loc, energy, color, radius=0.05):
    l = bpy.data.lights.new(name, 'POINT'); l.energy = energy; l.color = color; l.shadow_soft_size = radius
    o = bpy.data.objects.new(name, l); bpy.context.collection.objects.link(o); o.location = loc
    return o


def build_lights(G):
    """Warm, dim and cozy: a soft key and fill from the camera side, bulbs and lamps overhead, the porthole glow."""
    WARM = (1.0, 0.80, 0.58)
    L = []
    L.append(add_area('key', (-2.6, -5.8, 2.5), (0, 0.5, 1.2), 520, 3.0, WARM, size_y=2.0))
    L.append(add_area('fill', (3.4, -5.2, 2.2), (0, 0.5, 1.1), 200, 3.0, (1.0, 0.86, 0.7), size_y=2.0))
    for k, x in enumerate((-0.9, 0.9)):
        L.append(add_area(f'top{k}', (x, 0.2, CEIL_Z - 0.2), (x, 0.4, 0.8), 260, 1.6, (1.0, 0.76, 0.5)))
    L.append(add_area('wallwash', (0, -1.0, CEIL_Z - 0.3), (0, wall_target(), 1.5), 180, 6.0, (1.0, 0.78, 0.52), size_y=1.0))
    for k, p in enumerate(G['lamp_pos']):
        L.append(add_point(f'lamp_light{k}', p, 60, (1.0, 0.72, 0.4), 0.08))
    L.append(add_point('porthole_light', G['porthole_pos'], 120, (1.0, 0.72, 0.3), 0.12))
    return L


def wall_target():
    return WALL_Y


# ----------------------------------------------------------------------------- world and cameras
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
        build_chair(n, M, G, i)
    G['lights'] = build_lights(G)
    set_objs = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVES')]    # everything built so far
    cast = {}
    for i, n in enumerate(ORDER):
        spec = dict(CAST[n])
        body = dict(spec.get('body', {}))
        body.setdefault('reach', 0.285); body.setdefault('hand_x', 0.12)
        body.setdefault('fuzz', dict(count=50000, arm=10000, len=0.0025))   # cloth fibres: lighter than the default
        spec['body'] = body
        st = SEATS[n]
        cast[n] = P.build_puppet(n, spec, root_loc=(st['x'], st['y'], root_z(spec)), root_rot_z=st['rot'],
                                 body_h=0.55, seed=1000 + i)
    return G, cast, set_objs


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


CLOSE_D = 4.1
CLOSE_LENS = 85


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def cameras(cast):
    """Wide shot from the open side, plus a close-up per person from across the table.
    Returns (cams, head_yaw): head_yaw[(cam, name)] = rotation of that person's head (about its z) for that camera."""
    bpy.context.view_layer.update()
    cams, yaw = {}, {}
    cams['wide'] = make_camera('cam_wide', (0.0, -6.0, 1.85), (0.0, 0.45, 1.18), 50, focus=6.8, fstop=5.6)
    wide_loc = cams['wide'].location
    for n in ORDER:
        h = head_world(cast[n])
        th_root = SEATS[n]['rot']
        d = Vector((wide_loc.x - h.x, wide_loc.y - h.y, 0)).normalized()
        th_cam = math.atan2(d.x, -d.y)
        yaw[('wide', n)] = max(-0.8, min(0.8, 0.6 * wrap(th_cam - th_root)))
        f = facing(n)
        w = 0.0 if n == 'lawler' else 0.5
        cd = (f * w + Vector((0, -1, 0)) * (1 - w)).normalized()
        loc = Vector((h.x, h.y, h.z + 0.24)) + cd * CLOSE_D   # a little above the table clutter, looking slightly down
        tgt = Vector((h.x, h.y, h.z - 0.15))
        cams[n] = make_camera(f'cam_{n}', loc, tgt, CLOSE_LENS, focus=(loc - h).length, fstop=2.0)
        th_c = math.atan2(cd.x, -cd.y)
        yaw[(n, n)] = max(-0.95, min(0.95, wrap(th_c - th_root)))
    return cams, yaw
