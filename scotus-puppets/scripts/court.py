# Supreme Court courtroom set, cast placement, lights and cameras (bpy 5.2).
import math, os
import bpy
import numpy as np
from mathutils import Vector
import puppet as P
from characters import CHARS, BENCH_ORDER, ADVOCATES

HERE = os.path.dirname(__file__)
BENCH_TOP = 1.2          # world z of bench top
ARC_R = 11.0             # bench arc radius, centred near the lectern
SEAT_DTHETA = 0.082      # ~0.9 m between seats
LECTERN = Vector((0, -3.1, 0))
ADV_POS = Vector((0, -3.55, 0))
LECTERN_TOP = 1.16


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
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.009, 0.007, 1)
    return sc


# ----------------------------------------------------------------------------- materials
def mat_wood(name, dark='#2e120b', light='#5c2716', gloss=0.25):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 9.0)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'
    wv.inputs['Scale'].default_value = 3.0; wv.inputs['Distortion'].default_value = 7.0
    wv.inputs['Detail'].default_value = 3.0; wv.inputs['Detail Scale'].default_value = 1.6
    L.new(mp.outputs['Vector'], wv.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = P.hex_lin(dark); cr.color_ramp.elements[1].color = P.hex_lin(light)
    L.new(wv.outputs['Fac'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.38
    p.inputs['Coat Weight'].default_value = gloss
    p.inputs['Coat Roughness'].default_value = 0.12
    return m


def mat_marble(name, base='#e7dfcc', vein='#b9ad97'):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.8
    nz.inputs['Detail'].default_value = 8.0; nz.inputs['Distortion'].default_value = 2.5
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.45; cr.color_ramp.elements[0].color = P.hex_lin(base)
    cr.color_ramp.elements[1].position = 0.62; cr.color_ramp.elements[1].color = P.hex_lin(vein)
    L.new(nz.outputs['Fac'], cr.inputs['Fac'])
    L.new(cr.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.22
    p.inputs['Subsurface Weight'].default_value = 0.1
    return m


def mat_velvet(name, hexc='#5c0a10'):
    m, nt, p = P._new_mat(name)
    p.inputs['Base Color'].default_value = P.hex_lin(hexc)
    p.inputs['Roughness'].default_value = 0.85
    p.inputs['Sheen Weight'].default_value = 1.0
    p.inputs['Sheen Roughness'].default_value = 0.3
    p.inputs['Sheen Tint'].default_value = P.hex_lin('#d0505a')
    p.inputs['Specular IOR Level'].default_value = 0.2
    return m


def mat_leather(name, hexc='#070505'):
    m, nt, p = P._new_mat(name)
    N, L = nt.nodes, nt.links
    p.inputs['Base Color'].default_value = P.hex_lin(hexc)
    p.inputs['Roughness'].default_value = 0.6
    p.inputs['Specular IOR Level'].default_value = 0.25
    p.inputs['Coat Weight'].default_value = 0.08
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 300
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.15
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], p.inputs['Normal'])
    return m


def mat_emit(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = color; e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m


# ----------------------------------------------------------------------------- geometry helpers
def box(name, size, loc, mats, rot_z=0.0, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name
    o.scale = size; o.rotation_euler = (0, 0, rot_z)
    for m in mats:
        o.data.materials.append(m)
    if bevel:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        md = o.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = 3
    return o


def cylinder(name, r, h, loc, mats, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, vertices=verts)
    o = bpy.context.object; o.name = name
    for m in mats:
        o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o


def seat_frame(i):
    """World position (root), facing rotation (toward the lectern) and arc angle for bench seat i."""
    th = (i - 4) * SEAT_DTHETA
    pos = Vector(arc_point(th, 0.55, BENCH_TOP - 0.08))
    d = Vector((LECTERN.x - pos.x, LECTERN.y - pos.y, 0)).normalized()
    return pos, math.atan2(d.x, -d.y), th


def arc_point(th, r_off, z):
    c = Vector((0, -ARC_R, 0))
    r = ARC_R + r_off
    return (r * math.sin(th), c.y + r * math.cos(th), z)


def build_bench(wood, wood_dark, top_m):
    """Sweep a moulded cross-section along the bench arc. Returns the bench object (an occluder)."""
    prof = [(0.0, 0.0), (0.0, 0.12), (0.03, 0.14), (0.03, 0.2), (0.0, 0.22), (0.0, 1.02), (0.035, 1.05),
            (0.035, 1.11), (0.06, 1.13), (0.06, BENCH_TOP), (-0.8, BENCH_TOP), (-0.8, 0.0)]
    ths = np.linspace(-4.75 * SEAT_DTHETA, 4.75 * SEAT_DTHETA, 220)
    V, F = [], []
    n = len(prof)
    for th in ths:
        for d, z in prof:
            V.append(arc_point(th, -d, z))
    for i in range(len(ths) - 1):
        for j in range(n - 1):
            a = i * n + j
            F.append((a, a + n, a + n + 1, a + 1))
    # end caps
    F.append(tuple(range(n))[::-1]); F.append(tuple(range((len(ths) - 1) * n, len(ths) * n)))
    mats = [wood, top_m]
    fm = []
    for i in range(len(ths) - 1):
        for j in range(n - 1):
            fm.append(1 if j == n - 3 else 0)
    fm += [0, 0]
    bench = P.mesh_obj('bench', np.array(V), F, fm, mats, smooth=False)
    # raised panels / pilasters between seats
    parts = [bench]
    for k in range(10):
        th = (k - 4.5) * SEAT_DTHETA
        x, y, _ = arc_point(th, -0.035, 0)
        pil = box(f'pilaster{k}', (0.12, 0.08, 0.86), (x, y, 0.6), [wood_dark], rot_z=-th, bevel=0.01)
        parts.append(pil)
    for k in range(9):
        th = (k - 4) * SEAT_DTHETA
        x, y, _ = arc_point(th, -0.015, 0)
        pn = box(f'panel{k}', (0.62, 0.04, 0.62), (x, y, 0.62), [wood], rot_z=-th, bevel=0.012)
        parts.append(pn)
    return parts


def build_chair(name, loc, rot_z, height, leather):
    rings = []
    hw, hd = 0.36, 0.12
    for z, f in ((0.0, 0.0), (0.0, 0.92), (0.02, 1.0), (height - 0.12, 1.0), (height - 0.03, 0.9),
                 (height, 0.6), (height + 0.005, 0.0)):
        rings.append((z, hw * f, hd * f, 0.0, 0))
    V, F, M = P.loft(rings, 48, 4.0)
    o = P.mesh_obj(name, V, F, M, [leather], location=loc)
    o.rotation_euler = (0, 0, rot_z)
    md = o.modifiers.new('bv', 'BEVEL'); md.width = 0.01
    return o


def build_drapes(velvet, y=2.6, width=19.0, height=9.0):
    xs = np.linspace(-width / 2, width / 2, 900)
    zs = np.linspace(0, height, 30)
    rng = np.random.default_rng(3)
    ph = np.cumsum(rng.normal(0, 0.12, len(xs)))
    V, F = [], []
    for z in zs:
        amp = 0.09 + 0.03 * np.sin(z * 0.7)
        dy = amp * np.sin(xs * 2 * np.pi / 0.42 + ph * 0.25 + z * 0.05)
        for x, d in zip(xs, dy):
            V.append((x, y + d, z))
    nx = len(xs)
    for i in range(len(zs) - 1):
        for j in range(nx - 1):
            a = i * nx + j
            F.append((a, a + 1, a + nx + 1, a + nx))
    return P.mesh_obj('drapes', np.array(V), F, [0] * len(F), [velvet])


def build_column(name, x, y, marble, h=9.0, r=0.34):
    phi = np.linspace(0, 2 * np.pi, 96, endpoint=False)
    rr = r * (1 - 0.05 * np.abs(np.sin(12 * phi)))
    V, F = [], []
    zs = np.linspace(0.5, h - 0.6, 12)
    for z in zs:
        taper = 1 - 0.08 * (z / h)
        for p_, r_ in zip(phi, rr):
            V.append((x + r_ * taper * math.cos(p_), y + r_ * taper * math.sin(p_), z))
    n = len(phi)
    for i in range(len(zs) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            F.append((a, b, b + n, a + n))
    o = P.mesh_obj(name, np.array(V), F, [0] * len(F), [marble])
    box(name + '_base', (r * 2.7, r * 2.7, 0.3), (x, y, 0.15), [marble], bevel=0.03)
    cylinder(name + '_torus', r * 1.12, 0.22, (x, y, 0.4), [marble])
    box(name + '_cap', (r * 2.6, r * 2.6, 0.22), (x, y, h - 0.4), [marble], bevel=0.04)
    cylinder(name + '_echinus', r * 1.05, 0.25, (x, y, h - 0.62), [marble])
    return o


def clock_face_image(path):
    from PIL import Image, ImageDraw, ImageFont
    S = 1024
    im = Image.new('RGB', (S, S), (238, 232, 214))
    d = ImageDraw.Draw(im)
    c = S / 2
    fp = next((p for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
                           '/System/Library/Fonts/Supplemental/Times New Roman.ttf') if os.path.exists(p)), None)
    f = ImageFont.truetype(fp, 92) if fp else ImageFont.load_default(92)
    numer = ['XII', 'I', 'II', 'III', 'IIII', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']
    for k in range(60):
        a = k / 60 * 2 * math.pi
        r0 = 470 if k % 5 else 440
        d.line([(c + r0 * math.sin(a), c - r0 * math.cos(a)), (c + 495 * math.sin(a), c - 495 * math.cos(a))],
               fill=(30, 25, 20), width=10 if k % 5 == 0 else 4)
    for k, t in enumerate(numer):
        a = k / 12 * 2 * math.pi
        x, y = c + 360 * math.sin(a), c - 360 * math.cos(a)
        d.text((x, y), t, fill=(25, 20, 15), font=f, anchor='mm')
    for frac, ln, wd in ((10 / 12, 230, 26), (0.0, 330, 14)):  # 10:00
        a = frac * 2 * math.pi
        d.line([(c, c), (c + ln * math.sin(a), c - ln * math.cos(a))], fill=(15, 12, 10), width=wd)
    d.ellipse([c - 22, c - 22, c + 22, c + 22], fill=(15, 12, 10))
    im.save(path)


def build_clock(y, z, gold):
    path = os.path.join(os.environ.get('WORK') or os.path.join(HERE, '..', 'work'), 'clockface.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        clock_face_image(path)
    m, nt, p = P._new_mat('clockface')
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(path)
    nt.links.new(tex.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.3
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=0.42, fill_type='NGON', location=(0, y - 0.06, z),
                                      rotation=(math.pi / 2, 0, 0))
    face = bpy.context.object; face.name = 'clockface'
    face.data.materials.append(m)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.uv.cylinder_project(); bpy.ops.object.mode_set(mode='OBJECT')
    # planar UVs: map x,z to u,v
    me = face.data
    uv = me.uv_layers.active.data
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = (0.5 + v.x / 0.84, 0.5 + v.y / 0.84)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.46, minor_radius=0.06, location=(0, y - 0.05, z),
                                     rotation=(math.pi / 2, 0, 0))
    rim = bpy.context.object; rim.name = 'clockrim'; rim.data.materials.append(gold)
    bpy.ops.object.shade_smooth()
    return [face, rim]


def build_lectern(wood, wood_dark):
    parts = []
    x0, y0 = LECTERN.x, LECTERN.y
    parts.append(box('lectern_body', (0.66, 0.46, LECTERN_TOP - 0.06), (x0, y0, (LECTERN_TOP - 0.06) / 2),
                     [wood], bevel=0.02))
    top_m = mat_wood('lectern_top_wood', '#2a0f08', '#4f1f12', gloss=0.0)
    top_m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7
    top_m.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = 0.2
    top = box('lectern_top', (0.76, 0.56, 0.06), (x0, y0, LECTERN_TOP - 0.02), [top_m], bevel=0.015)
    top.rotation_euler = (-0.12, 0, 0)
    parts.append(top)
    parts.append(box('lectern_base', (0.8, 0.6, 0.08), (x0, y0, 0.04), [wood_dark], bevel=0.02))
    # the famous lights: white (two minutes left) and red (time up), on the bench side of the lectern top
    lw = mat_emit('light_white', (1, 0.95, 0.85, 1), 2.0)
    lr = mat_emit('light_red', (0.35, 0.02, 0.02, 1), 0.6)
    for xo, m in ((-0.12, lw), (0.12, lr)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=(x0 + xo, y0 + 0.25, LECTERN_TOP + 0.03))
        o = bpy.context.object; o.data.materials.append(m); bpy.ops.object.shade_smooth()
        parts.append(o)
    # papers / binder on the lectern
    paper = P.mat_plain('paper', P.hex_lin('#f3f0e6'), rough=0.8)
    pp = box('lectern_papers', (0.34, 0.26, 0.012), (x0 + 0.02, y0 - 0.02, LECTERN_TOP + 0.02), [paper])
    pp.rotation_euler = (-0.12, 0, 0.05)
    parts.append(pp)
    return parts


def build_gallery(wood, rng, n_people=26):
    """Counsel tables, the bar, pews and a generic audience behind the advocate (seen from the bench)."""
    objs, people = [], []
    for sx in (-1, 1):
        objs.append(box(f'counsel_table{sx}', (2.0, 0.9, 0.06), (sx * 2.1, -4.6, 0.76), [wood], bevel=0.01))
        objs.append(box(f'counsel_legs{sx}', (1.9, 0.8, 0.7), (sx * 2.1, -4.6, 0.37), [wood]))
    objs.append(box('bar_rail', (12.0, 0.12, 0.95), (0, -6.0, 0.47), [wood], bevel=0.02))
    for r in range(6):
        y = -7.0 - r * 1.05
        for sx in (-1, 1):
            objs.append(box(f'pew{r}{sx}', (4.6, 0.12, 1.0), (sx * 3.0, y - 0.35, 0.5), [wood], bevel=0.02))
    skins = ['#e8b39b', '#c8916c', '#8a5a3e', '#f0c4ab', '#d9a07c', '#5e3b2a', '#e2ab8c']
    hairs = ['#2b1e17', '#4a3528', '#7d7a75', '#3d2a20', '#7a5c3e', '#151210', '#5c5853', '#1c1410']
    suits = ['#1c1f2a', '#2a2a2e', '#3a2f2a', '#1a2430', '#33302e', '#4a1f26']
    styles = ['side_part', 'side_part', 'bob', 'long', 'side_part', 'bob']
    k = 0
    for r in range(4):
        y = -7.0 - r * 1.05
        for sx in (-1, 1):
            for c in range(3 if r < 3 else 2):
                if rng.random() < 0.18:
                    continue
                x = sx * (1.4 + c * 1.25 + rng.uniform(-0.2, 0.2))
                st = styles[rng.integers(len(styles))]
                spec = dict(skin=skins[rng.integers(len(skins))],
                            W=rng.uniform(0.13, 0.15), H=rng.uniform(0.19, 0.21),
                            hair=dict(style=st, hex=hairs[rng.integers(len(hairs))], part=rng.choice([-0.03, 0.03]),
                                      length={'bob': 0.11, 'long': 0.2}.get(st, 0.04), front_z=0.13,
                                      count=40000),
                            fuzz=dict(count=0),
                            brows=dict(thick=0.6),
                            body=dict(robe=suits[rng.integers(len(suits))], tie=None, rest_dz=-0.5, reach=0.1))
                pp = P.build_puppet(f'aud{k}', spec, root_loc=(x, y, 0.5), root_rot_z=math.pi, body_h=0.55,
                                    seed=100 + k, hair_scale=1.0)
                people.append(pp)
                k += 1
    return objs, people


def add_area(name, loc, target, energy, size, color=(1.0, 0.9, 0.78), size_y=None):
    l = bpy.data.lights.new(name, 'AREA'); l.energy = energy
    if size_y:
        l.shape = 'RECTANGLE'; l.size = size; l.size_y = size_y
    else:
        l.size = size
    l.color = color
    o = bpy.data.objects.new(name, l); bpy.context.collection.objects.link(o); o.location = loc
    d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def build_world(with_gallery=True, gallery_seed=11):
    """Build everything. Returns dict with object groups and cast."""
    wood = mat_wood('mahogany')
    wood_dark = mat_wood('mahogany_dark', '#220d08', '#45190e')
    top_m = P.mat_plain('benchtop', P.hex_lin('#1a0c08'), rough=0.3, coat=0.4)
    velvet = mat_velvet('velvet')
    marble = mat_marble('marble')
    leather = mat_leather('leather')
    gold = P.mat_plain('gold', P.hex_lin('#c9a24a'), rough=0.25, metallic=1.0)
    carpet = P.mat_fleece('carpet', P.hex_lin('#3a0a0e'), sheen=0.4, bump=0.3, fiber_scale=200)
    floor_m = mat_marble('floor', '#c9bfa9', '#9c917c')

    G = dict(bench=[], lectern=[], set=[], chairs=[], gallery=[], people=[])
    G['bench'] = build_bench(wood, wood_dark, top_m)
    # raised platform behind the bench and steps
    G['set'].append(box('dais', (11.0, 3.0, 0.4), (0, 1.7, 0.2), [wood_dark]))
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.object; fl.name = 'floor'
    fl.data.materials.append(carpet); G['set'].append(fl)
    G['set'].append(build_drapes(velvet))
    for x in (-8.2, -5.0, 5.0, 8.2):
        G['set'].append(build_column(f'col{x}', x, 2.15, marble))
    # side colonnades (seen in reverse/wide shots)
    for sx in (-1, 1):
        for y in (-2.0, -6.0, -10.0):
            G['set'].append(build_column(f'scol{sx}{y}', sx * 9.5, y, marble))
    G['set'].append(box('frieze', (20.0, 0.6, 1.6), (0, 2.1, 9.6), [marble]))
    G['set'] += build_clock(2.42, 3.55, gold)
    G['lectern'] = build_lectern(wood, wood_dark)
    # chairs
    rng = np.random.default_rng(5)
    for i, n in enumerate(BENCH_ORDER):
        pos, rz, th = seat_frame(i)
        h = 1.55 if n != 'roberts' else 1.7
        h += rng.uniform(-0.06, 0.06)
        cl = Vector(arc_point(th, 0.95, 0))
        cl.z = BENCH_TOP - 0.55
        G['chairs'].append(build_chair(f'chair_{n}', cl, -th, h, leather))
    # back wall of the gallery
    G['set'].append(box('backwall', (22.0, 0.3, 9.0), (0, -16.0, 4.5), [velvet]))
    if with_gallery:
        objs, people = build_gallery(wood, np.random.default_rng(gallery_seed))
        G['gallery'] = objs; G['people'] = people

    cast = {}
    for i, n in enumerate(BENCH_ORDER):
        pos, rz, th = seat_frame(i)
        cast[n] = P.build_puppet(n, CHARS[n], root_loc=tuple(pos), root_rot_z=rz, body_h=0.55,
                                 seed=1000 + i)
    for n in ADVOCATES:
        spec = dict(CHARS[n])
        spec['body'] = dict(spec.get('body', {}), len=1.15, rest_dz=-0.36, reach=0.24)
        cast[n] = P.build_puppet(n, spec, root_loc=(ADV_POS.x, ADV_POS.y, LECTERN_TOP - 0.08),
                                 root_rot_z=math.pi, body_h=0.55, seed=2000 + len(n))

    # lights: warm overhead soft boxes, gallery-side fill, rims from behind the bench
    L = []
    L.append(add_area('key_bench', (0, -3.0, 6.5), (0, 0.6, 1.6), 2600, 6.0, size_y=3.0))
    L.append(add_area('fill_gallery', (0, -7.0, 3.6), (0, 0.4, 1.7), 900, 8.0, (0.95, 0.9, 0.85), size_y=2.0))
    L.append(add_area('rim_bench', (0, 2.2, 4.2), (0, 0.4, 1.7), 900, 9.0, (1.0, 0.85, 0.7), size_y=0.8))
    L.append(add_area('drape_wash', (0, -1.5, 7.5), (0, 2.6, 3.5), 600, 12.0, (1.0, 0.82, 0.65), size_y=2.0))
    L.append(add_area('key_lectern', (1.5, -1.6, 4.2), (0, -3.5, 1.6), 900, 3.0))
    L.append(add_area('gallery_wash', (0, -9.0, 7.0), (0, -9.0, 0.5), 1600, 12.0, (1.0, 0.88, 0.75), size_y=8))
    G['lights'] = L
    return G, cast


# ----------------------------------------------------------------------------- cameras
def make_camera(name, loc, target, lens, focus=None, fstop=2.8, sensor=36.0):
    c = bpy.data.cameras.new(name); c.lens = lens; c.sensor_width = sensor
    o = bpy.data.objects.new(name, c); bpy.context.collection.objects.link(o); o.location = loc
    d = Vector(target) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if focus:
        c.dof.use_dof = True; c.dof.focus_distance = focus; c.dof.aperture_fstop = fstop
    return o


def head_world(pp):
    return pp['head'].matrix_world.translation.copy()


def cameras(cast):
    bpy.context.view_layer.update()
    cams = {}
    roberts_head = head_world(cast['roberts'])
    cams['wide'] = make_camera('cam_wide', (1.5, -10.6, 2.55), (0.15, 0.3, 1.6), 44, focus=10.8, fstop=8)
    for i, n in enumerate(BENCH_ORDER):
        h = head_world(cast[n])
        to_l = (Vector((LECTERN.x, LECTERN.y, h.z)) - h).normalized()
        loc = h + to_l * 2.6 + Vector((0, 0, -0.08))
        tgt = h + Vector((0, 0, -0.11))
        cams[n] = make_camera(f'cam_{n}', loc, tgt, 70, focus=(loc - h).length, fstop=2.2)
    for n in ADVOCATES:
        h = head_world(cast[n])
        loc = h + Vector((0.3, 2.9, 0.18))
        tgt = h + Vector((0, 0, -0.1))
        cams[n] = make_camera(f'cam_{n}', loc, tgt, 64, focus=(loc - h).length, fstop=2.2)
    return cams
