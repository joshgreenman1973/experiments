# Procedural Muppet-style puppets for Blender/bpy 5.2 (Cycles).
# Coordinates: character faces -Y (toward camera), +Z up, metres. Head centre ~ origin of head frame.
import math
import bpy
import numpy as np
from mathutils import Vector, Matrix
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree


# ----------------------------------------------------------------------------- colours / materials
_PI = math.pi


def hex_lin(h, mult=1.0):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [(v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return (min(1, lin[0] * mult), min(1, lin[1] * mult), min(1, lin[2] * mult), 1.0)


def _new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    return m, nt, p


def mat_fleece(name, color, sheen=1.0, rough=0.9, bump=0.6, fiber_scale=520.0, tint_var=0.12, sss=0.04):
    """Antron-fleece look: matte, strong sheen at grazing angles, fine fibre bump, slight blotchiness."""
    m, nt, p = _new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    blotch = N.new('ShaderNodeTexNoise'); blotch.inputs['Scale'].default_value = 18.0
    blotch.inputs['Detail'].default_value = 3.0
    L.new(tc.outputs['Object'], blotch.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 1.0 - tint_var
    mr.inputs['To Max'].default_value = 1.0 + tint_var
    L.new(blotch.outputs['Fac'], mr.inputs['Value'])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    mix.inputs['A'].default_value = color
    L.new(mr.outputs['Result'], mix.inputs['B'])
    L.new(mix.outputs['Result'], p.inputs['Base Color'])
    fib = N.new('ShaderNodeTexNoise'); fib.inputs['Scale'].default_value = fiber_scale
    fib.inputs['Detail'].default_value = 2.0; fib.inputs['Roughness'].default_value = 0.7
    L.new(tc.outputs['Object'], fib.inputs['Vector'])
    vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = fiber_scale * 0.35
    L.new(tc.outputs['Object'], vor.inputs['Vector'])
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'
    L.new(fib.outputs['Fac'], add.inputs[0]); L.new(vor.outputs['Distance'], add.inputs[1])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump
    bp.inputs['Distance'].default_value = 0.0008
    L.new(add.outputs['Value'], bp.inputs['Height'])
    L.new(bp.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = rough
    p.inputs['Specular IOR Level'].default_value = 0.25
    p.inputs['Sheen Weight'].default_value = sheen
    p.inputs['Sheen Roughness'].default_value = 0.35
    p.inputs['Sheen Tint'].default_value = tuple(min(1.0, c * 1.6 + 0.12) for c in color[:3]) + (1.0,)
    p.inputs['Subsurface Weight'].default_value = sss
    p.inputs['Subsurface Radius'].default_value = (0.01, 0.005, 0.004)
    return m


def mat_plain(name, color, rough=0.5, coat=0.0, spec=0.5, sheen=0.0, metallic=0.0):
    m, nt, p = _new_mat(name)
    p.inputs['Base Color'].default_value = color
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = 0.08
    p.inputs['Specular IOR Level'].default_value = spec
    p.inputs['Sheen Weight'].default_value = sheen
    p.inputs['Metallic'].default_value = metallic
    return m


def mat_hair(name, color, rough=0.42, rand=0.12):
    m, nt, p = _new_mat(name)
    N, L = nt.nodes, nt.links
    h = N.new('ShaderNodeBsdfHairPrincipled')
    h.parametrization = 'COLOR'
    for k, v in (('Color', color), ('Roughness', rough), ('Radial Roughness', 0.55), ('Coat', 0.15),
                 ('Random Color', rand), ('Random Roughness', 0.15)):
        if k in h.inputs:
            h.inputs[k].default_value = v
    out = N['Material Output']
    L.new(h.outputs['BSDF'], out.inputs['Surface'])
    return m


def mat_robe(name, base_hex='#060607', shirt_hex='#ecebe6', tie_hex=None, v_depth=0.16, v_half=0.075,
             tie_w=0.022, collar=True, v_shape='V', pattern=None, shirt_pattern=None, tie_pattern=None,
             pin=None, lapel=None, fabric=None, placket=None, buttons=None, pockets=None):
    """Garment with a V (or round 'U') opening showing a shirt (and optional tie), via object-space masks.

    The defaults give the black judicial robe. Optional extras, all off by default:
      v_shape 'V' | 'U'
      pattern / shirt_pattern / tie_pattern = dict(kind='dots'|'check'|'stripes'|'diag', hex, s=spacing m, r, strength)
      lapel = hex band along the V edge; pin = dict(hex, x, z, r); placket = hex line down the front;
      buttons = dict(hex, z0, dz, n, r); pockets = dict(hex, cx, cz, w, h, t); fabric 'knit'|'denim'|'cotton'|'suit'."""
    m, nt, p = _new_mat(name)
    N, L = nt.nodes, nt.links
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])

    def math(op, a, b=None, val=None):
        n = N.new('ShaderNodeMath'); n.operation = op
        for i, s in enumerate((a, b)):
            if s is None:
                continue
            if isinstance(s, (int, float)):
                n.inputs[i].default_value = s
            else:
                L.new(s, n.inputs[i])
        return n.outputs[0]

    def ramp(src, lo, hi):
        n = N.new('ShaderNodeMapRange'); n.clamp = True
        n.inputs['From Min'].default_value = lo; n.inputs['From Max'].default_value = hi
        n.inputs['To Min'].default_value = 0.0; n.inputs['To Max'].default_value = 1.0
        L.new(src, n.inputs['Value'])
        return n.outputs['Result']

    def mixc(factor, a, b, blend='MIX'):
        """RGBA mix; a, b are colour tuples or sockets."""
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = blend
        if isinstance(factor, (int, float)):
            mx.inputs['Factor'].default_value = factor
        else:
            L.new(factor, mx.inputs['Factor'])
        for key, v in (('A', a), ('B', b)):
            if isinstance(v, tuple):
                mx.inputs[key].default_value = v
            else:
                L.new(v, mx.inputs[key])
        return mx.outputs['Result']

    x, y, z = sep.outputs['X'], sep.outputs['Y'], sep.outputs['Z']
    ax = math('ABSOLUTE', x)
    if v_shape == 'U':
        # round neckline: half-width = v_half * sqrt(u (2 - u)); u = 0 at the bottom of the scoop, 1 at the neck base
        u = ramp(z, -v_depth, 0.0)
        vw = math('MULTIPLY', math('SQRT', math('MULTIPLY', u, math('SUBTRACT', 2.0, u))), v_half)
    else:
        # V half-width grows linearly from 0 at z=-v_depth to v_half at z=0 (neck base)
        vw = math('MULTIPLY', math('ADD', z, v_depth), v_half / v_depth)
    in_v = ramp(math('SUBTRACT', vw, ax), -0.002, 0.002)
    front = ramp(math('MULTIPLY', y, -1.0), 0.01, 0.04)
    shirt = math('MULTIPLY', in_v, front)

    # ---- optional patterns: projected on the front (x, z) and side (y, z) planes, blended by the surface normal
    nsep = []

    def planar(fn):
        if not nsep:
            s_ = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Normal'], s_.inputs[0]); nsep.append(s_)
        mf, ms = fn(x, z), fn(y, z)
        wf = math('ABSOLUTE', nsep[0].outputs['Y']); ws = math('ABSOLUTE', nsep[0].outputs['X'])
        num = math('ADD', math('MULTIPLY', mf, wf), math('MULTIPLY', ms, ws))
        return math('DIVIDE', num, math('ADD', math('ADD', wf, ws), 1e-4))

    def fract(s):
        return math('FRACT', s)

    def pat_mask(pat):
        k, sp = pat['kind'], pat['s']
        if k == 'dots':
            r = pat.get('r', 0.22)  # radius in cell units

            def fn(a, b):
                a1, b1 = math('DIVIDE', a, sp), math('DIVIDE', b, sp)
                off = math('MULTIPLY', math('MODULO', math('FLOOR', b1), 2.0), 0.5)
                fa = math('SUBTRACT', fract(math('ADD', a1, off)), 0.5)
                fb = math('SUBTRACT', fract(b1), 0.5)
                d = math('SQRT', math('ADD', math('MULTIPLY', fa, fa), math('MULTIPLY', fb, fb)))
                return ramp(d, r * 1.15, r * 0.85)
            return planar(fn)
        if k == 'check':
            def fn(a, b):
                ma = math('LESS_THAN', fract(math('DIVIDE', a, sp)), 0.5)
                mb = math('LESS_THAN', fract(math('DIVIDE', b, sp)), 0.5)
                return math('MULTIPLY', math('ADD', ma, mb), 0.5)
            return planar(fn)
        if k == 'stripes':
            def fn(a, b):
                return math('LESS_THAN', fract(math('DIVIDE', a, sp)), 0.5)
            return planar(fn)
        if k == 'diag':  # tie stripes (front only)
            return math('LESS_THAN', fract(math('DIVIDE', math('ADD', x, z), sp)), 0.5)
        raise ValueError(k)

    def patterned(hex_, pat):
        base = hex_lin(hex_)
        if not pat:
            return base
        return mixc(math('MULTIPLY', pat_mask(pat), float(pat.get('strength', 1.0))), base, hex_lin(pat['hex']))

    mix1 = N.new('ShaderNodeMix'); mix1.data_type = 'RGBA'
    L.new(shirt, mix1.inputs['Factor'])
    for key, v in (('A', patterned(base_hex, pattern)), ('B', patterned(shirt_hex, shirt_pattern))):
        if isinstance(v, tuple):
            mix1.inputs[key].default_value = v
        else:
            L.new(v, mix1.inputs[key])
    col_out = mix1.outputs['Result']
    if lapel:
        e = math('SUBTRACT', ax, vw)  # distance outside the V edge
        lm = math('MULTIPLY', math('MULTIPLY', ramp(e, 0.0, 0.003), ramp(e, 0.027, 0.024)), front)
        lm = math('MULTIPLY', lm, ramp(z, -v_depth - 0.03, -v_depth + 0.01))
        col_out = mixc(lm, col_out, hex_lin(lapel))
    if tie_hex:
        # tie narrows into a knot near the collar
        tw = math('ADD', math('MULTIPLY', math('ADD', z, 0.0), -0.04), tie_w * 0.75)
        in_tie = ramp(math('SUBTRACT', tw, ax), -0.0015, 0.0015)
        tie_mask = math('MULTIPLY', in_tie, shirt)
        mix2 = N.new('ShaderNodeMix'); mix2.data_type = 'RGBA'
        L.new(tie_mask, mix2.inputs['Factor'])
        L.new(col_out, mix2.inputs['A'])
        tcol = patterned(tie_hex, tie_pattern)
        if isinstance(tcol, tuple):
            mix2.inputs['B'].default_value = tcol
        else:
            L.new(tcol, mix2.inputs['B'])
        col_out = mix2.outputs['Result']
    outside = math('MULTIPLY', math('SUBTRACT', 1.0, in_v), front)  # garment front, outside the opening
    if placket:
        line = ramp(math('SUBTRACT', 0.0026, ax), -0.0007, 0.0007)
        col_out = mixc(math('MULTIPLY', line, outside), col_out, hex_lin(placket))
    if buttons:
        bz0, bdz, bn = buttons.get('z0', -0.2), buttons.get('dz', 0.075), buttons.get('n', 4)
        br = buttons.get('r', 0.0062)
        zz = math('DIVIDE', math('SUBTRACT', bz0, z), bdz)  # 0 at the first button, 1 at the next, ...
        cz = math('MULTIPLY', math('SUBTRACT', fract(math('ADD', zz, 0.5)), 0.5), bdz)
        d = math('SQRT', math('ADD', math('MULTIPLY', x, x), math('MULTIPLY', cz, cz)))
        rng_ = math('MULTIPLY', math('LESS_THAN', zz, bn - 0.5), math('GREATER_THAN', zz, -0.5))
        bm = math('MULTIPLY', math('MULTIPLY', ramp(d, br * 1.25, br * 0.8), rng_), outside)
        col_out = mixc(bm, col_out, hex_lin(buttons.get('hex', '#e8e4da')))
    if pockets:
        cx, cz_, pw, ph, pt = (pockets.get(k, d_) for k, d_ in (('cx', 0.09), ('cz', -0.16), ('w', 0.07),
                                                                  ('h', 0.08), ('t', 0.0035)))
        dx = math('ABSOLUTE', math('SUBTRACT', ax, cx))
        dz = math('ABSOLUTE', math('SUBTRACT', z, cz_))

        def rect(hw, hh):
            return math('MULTIPLY', ramp(math('SUBTRACT', hw, dx), -0.0007, 0.0007),
                        ramp(math('SUBTRACT', hh, dz), -0.0007, 0.0007))
        edge = math('MULTIPLY', rect(pw / 2 + pt, ph / 2 + pt), math('SUBTRACT', 1.0, rect(pw / 2, ph / 2)))
        col_out = mixc(math('MULTIPLY', edge, outside), col_out, hex_lin(pockets.get('hex', '#35527f')))
    if pin:
        px, pz, pr = pin.get('x', 0.085), pin.get('z', -0.095), pin.get('r', 0.0075)
        d = math('SQRT', math('ADD', math('MULTIPLY', math('SUBTRACT', x, px), math('SUBTRACT', x, px)),
                              math('MULTIPLY', math('SUBTRACT', z, pz), math('SUBTRACT', z, pz))))
        col_out = mixc(math('MULTIPLY', ramp(d, pr * 1.2, pr * 0.85), front), col_out, hex_lin(pin.get('hex', '#d9b550')))

    # ---- fabric: soft folds + fine fibre bump; per-fabric extras
    folds = N.new('ShaderNodeTexWave'); folds.wave_type = 'BANDS'; folds.bands_direction = 'X'
    folds.inputs['Scale'].default_value = 5.0; folds.inputs['Distortion'].default_value = 9.0
    folds.inputs['Detail'].default_value = 1.5
    L.new(tc.outputs['Object'], folds.inputs['Vector'])
    fib = N.new('ShaderNodeTexNoise'); fib.inputs['Scale'].default_value = 700
    L.new(tc.outputs['Object'], fib.inputs['Vector'])
    h = math('ADD', math('MULTIPLY', folds.outputs['Fac'], 0.6), fib.outputs['Fac'])
    bump_s, rough, sheen, spec = 0.3, 0.78, 0.12, 0.12
    sheen_tint = (0.2, 0.2, 0.22, 1.0)
    if fabric:
        if fabric == 'knit':
            def rib(a, b):
                s_ = math('SINE', math('MULTIPLY', a, 2 * _PI / 0.0072))
                return math('ADD', math('MULTIPLY', s_, 0.5), 0.5)
            h = math('ADD', h, math('MULTIPLY', planar(rib), 1.1))
            bump_s, rough, sheen, spec = 0.7, 0.93, 0.5, 0.06
        elif fabric == 'denim':
            def twill(a, b):
                return fract(math('DIVIDE', math('ADD', a, b), 0.0034))
            h = math('ADD', h, math('MULTIPLY', planar(twill), 0.9))
            bump_s, rough, sheen, spec = 0.5, 0.82, 0.2, 0.08
        elif fabric == 'cotton':
            bump_s, rough, sheen, spec = 0.22, 0.72, 0.18, 0.1
        elif fabric == 'suit':
            bump_s, rough, sheen, spec = 0.25, 0.68, 0.14, 0.14
        if fabric in ('knit', 'denim', 'suit'):  # heathered yarn: slow blotchy tint
            hn = N.new('ShaderNodeTexNoise'); hn.inputs['Scale'].default_value = 140 if fabric != 'suit' else 40
            hn.inputs['Detail'].default_value = 4.0
            L.new(tc.outputs['Object'], hn.inputs['Vector'])
            mr = N.new('ShaderNodeMapRange')
            mr.inputs['To Min'].default_value = 0.86 if fabric != 'suit' else 0.94
            mr.inputs['To Max'].default_value = 1.08 if fabric != 'suit' else 1.04
            L.new(hn.outputs['Fac'], mr.inputs['Value'])
            gray = N.new('ShaderNodeCombineColor')
            for k_ in ('Red', 'Green', 'Blue'):
                L.new(mr.outputs['Result'], gray.inputs[k_])
            col_out = mixc(1.0, col_out, gray.outputs['Color'], 'MULTIPLY')
        sc3 = hex_lin(base_hex)
        sheen_tint = tuple(min(1.0, c * 1.5 + 0.1) for c in sc3[:3]) + (1.0,)
    L.new(col_out, p.inputs['Base Color'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump_s
    bp.inputs['Distance'].default_value = 0.01
    L.new(h, bp.inputs['Height']); L.new(bp.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Roughness'].default_value = rough
    p.inputs['Sheen Weight'].default_value = sheen
    p.inputs['Sheen Roughness'].default_value = 0.3
    p.inputs['Sheen Tint'].default_value = sheen_tint
    p.inputs['Specular IOR Level'].default_value = spec
    return m


# ----------------------------------------------------------------------------- mesh helpers
def superellipse_ring(rx, ry, cy, nseg, n=2.3):
    phi = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    c, s = np.cos(phi), np.sin(phi)
    x = rx * np.sign(c) * np.abs(c) ** (2.0 / n)
    y = cy + ry * np.sign(s) * np.abs(s) ** (2.0 / n)
    return x, y


def loft(rings, nseg, n_exp=2.3, zfun=None):
    """rings: list of (z, rx, ry, cy, mat). rx==0 at ends -> pole. Returns verts (V,3), faces, face mats."""
    verts, faces, fmats, ring_idx = [], [], [], []
    for (z, rx, ry, cy, mat) in rings:
        if rx <= 1e-6:
            ring_idx.append([len(verts)])
            verts.append((0.0, cy, z))
        else:
            x, y = superellipse_ring(rx, ry, cy, nseg, n_exp)
            ring_idx.append(list(range(len(verts), len(verts) + nseg)))
            verts.extend(zip(x, y, np.full(nseg, z)))
    for k in range(len(rings) - 1):
        a, b = ring_idx[k], ring_idx[k + 1]
        mat = rings[k + 1][4]
        if len(a) == 1:
            for j in range(nseg):
                faces.append((a[0], b[(j + 1) % nseg], b[j])); fmats.append(mat)
        elif len(b) == 1:
            for j in range(nseg):
                faces.append((a[j], a[(j + 1) % nseg], b[0])); fmats.append(mat)
        else:
            for j in range(nseg):
                faces.append((a[j], a[(j + 1) % nseg], b[(j + 1) % nseg], b[j])); fmats.append(mat)
    V = np.array(verts, dtype=np.float64)
    if zfun is not None:
        V[:, 2] += zfun(V)
    return V, faces, fmats


def mesh_obj(name, V, faces, fmats, mats, smooth=True, parent=None, location=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], faces)
    me.validate()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', np.array(fmats, dtype=np.int32))
    me.polygons.foreach_set('use_smooth', np.full(len(me.polygons), smooth, dtype=bool))
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.location = location
    if parent is not None:
        ob.parent = parent
    return ob


def tri_data(V, faces, face_ok=None):
    tris = []
    for i, f in enumerate(faces):
        if face_ok is not None and not face_ok[i]:
            continue
        if len(f) == 3:
            tris.append(f)
        else:
            tris.append((f[0], f[1], f[2])); tris.append((f[0], f[2], f[3]))
    T = np.array(tris)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(n, axis=1)
    return T, a, b, c, area


def sample_surface(V, faces, count, rng, mask=None, outward_center=None, face_ok=None):
    T, a, b, c, area = tri_data(V, faces, face_ok)
    cen = (a + b + c) / 3
    w = area.copy()
    if mask is not None:
        w *= mask(cen)
    w /= w.sum()
    idx = rng.choice(len(T), size=count, p=w)
    r1, r2 = rng.random(count), rng.random(count)
    sq = np.sqrt(r1)
    P = (1 - sq)[:, None] * a[idx] + (sq * (1 - r2))[:, None] * b[idx] + (sq * r2)[:, None] * c[idx]
    n = np.cross(b[idx] - a[idx], c[idx] - a[idx])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    if outward_center is not None:
        flip = np.einsum('ij,ij->i', n, P - outward_center) < 0
        n[flip] *= -1
    return P, n


def uv_sphere(name, r, mats, segs=48, rings=24, scale=(1, 1, 1), parent=None, loc=(0, 0, 0), rot=None,
              keep=None):
    """Ellipsoid mesh; keep(V)->bool mask of vertices to keep (for caps)."""
    rr = []
    for k in range(rings + 1):
        th = math.pi * k / rings
        rr.append((r * math.cos(th) * scale[2], r * math.sin(th) * scale[0], r * math.sin(th) * scale[1], 0.0, 0))
    V, F, M = loft(rr, segs, 2.0)
    if keep is not None:
        km = keep(V)
        newidx = -np.ones(len(V), dtype=int)
        newidx[km] = np.arange(km.sum())
        F2, M2 = [], []
        for f, m in zip(F, M):
            if all(km[i] for i in f):
                F2.append(tuple(int(newidx[i]) for i in f)); M2.append(m)
        V, F, M = V[km], F2, M2
    ob = mesh_obj(name, V, F, M, mats, parent=parent, location=loc)
    if rot is not None:
        ob.rotation_euler = rot
    return ob


def tube(name, pts, radii, mats, nseg=32, parent=None, caps=True):
    """Swept tube along a polyline (smoothly resampled)."""
    pts = np.asarray(pts, float); radii = np.asarray(radii, float)
    t = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    tt = np.linspace(0, t[-1], 40)
    fx = [PchipInterpolator(t, pts[:, i]) for i in range(3)]
    Pp = np.stack([f(tt) for f in fx], 1)
    R = np.interp(tt, t, radii)
    T = np.gradient(Pp, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    up = np.array([0, 0, 1.0])
    verts, faces = [], []
    ref = np.cross(T[0], up if abs(T[0] @ up) < 0.9 else np.array([1.0, 0, 0]))
    ref /= np.linalg.norm(ref)
    phi = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    for i in range(len(Pp)):
        ref = ref - (ref @ T[i]) * T[i]; ref /= np.linalg.norm(ref)
        b = np.cross(T[i], ref)
        ring = Pp[i] + R[i] * (np.cos(phi)[:, None] * ref + np.sin(phi)[:, None] * b)
        verts.extend(ring)
    for i in range(len(Pp) - 1):
        for j in range(nseg):
            a0, a1 = i * nseg + j, i * nseg + (j + 1) % nseg
            faces.append((a0, a1, a1 + nseg, a0 + nseg))
    if caps:
        c0 = len(verts); verts.append(Pp[0] - T[0] * R[0] * 0.3)
        c1 = len(verts); verts.append(Pp[-1] + T[-1] * R[-1] * 0.3)
        last = (len(Pp) - 1) * nseg
        for j in range(nseg):
            faces.append((c0, (j + 1) % nseg, j))
            faces.append((c1, last + j, last + (j + 1) % nseg))
    V = np.array(verts)
    return mesh_obj(name, V, faces, [0] * len(faces), mats, parent=parent)


def curves_obj(name, P, radii, mat, parent=None):
    """P: (N, K, 3) strand points; radii: (N, K)."""
    N, K, _ = P.shape
    cv = bpy.data.hair_curves.new(name)
    cv.add_curves([K] * N)
    cv.position_data.foreach_set('vector', P.astype(np.float32).ravel())
    if 'radius' not in cv.attributes:
        cv.attributes.new('radius', 'FLOAT', 'POINT')
    cv.attributes['radius'].data.foreach_set('value', radii.astype(np.float32).ravel())
    cv.materials.append(mat)
    ob = bpy.data.objects.new(name, cv)
    bpy.context.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


# ----------------------------------------------------------------------------- hair growth
class Collider:
    """Union of ellipsoids (centre, radii); push points outside with margin."""

    def __init__(self, ells):
        self.ells = [(np.array(c, float), np.array(r, float)) for c, r in ells]

    def push(self, P, margin):
        for c, r in self.ells:
            rr = r + margin
            d = (P - c) / rr
            f = np.sqrt((d ** 2).sum(-1))
            inside = f < 1.0
            if inside.any():
                P[inside] = c + (P[inside] - c) / f[inside, None]
        return P


class FaceGuard:
    """Keep strands out of a box in front of the face by pushing them sideways."""

    def __init__(self, xf, yf, zlo, zhi):
        self.xf, self.yf, self.zlo, self.zhi = xf, yf, zlo, zhi

    def push(self, P, margin):
        m = (P[:, 1] < self.yf) & (np.abs(P[:, 0]) < self.xf) & (P[:, 2] > self.zlo) & (P[:, 2] < self.zhi)
        if m.any():
            P[m, 0] = np.where(P[m, 0] >= 0, 1, -1) * self.xf
        return P


class Multi:
    def __init__(self, *cs):
        self.cs = cs

    def push(self, P, margin):
        for c in self.cs:
            P = c.push(P, margin)
        return P


def grow(roots, normals, length, npts, comb_fn, collider, rng, lift=0.6, gravity=0.0, curl=0.0,
         stiff=0.75, margin=0.004, jitter=0.15):
    """Grow strands from roots. comb_fn(P, n)->unit tangent combing direction."""
    n = len(roots)
    L = length if np.ndim(length) else np.full(n, length)
    seg = (L / (npts - 1))[:, None]
    P = np.zeros((n, npts, 3))
    P[:, 0] = roots
    comb = comb_fn(roots, normals)
    d = normals * lift + comb * (1 - lift)
    d += rng.normal(0, jitter, d.shape)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    phase = rng.random(n) * 6.28
    for i in range(1, npts):
        t = i / (npts - 1)
        target = comb_fn(P[:, i - 1], normals) + np.array([0, 0, -gravity * t * 2.0])
        if curl:
            side = np.cross(d, np.array([0, 0, 1.0]))
            side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
            target += side * (curl * np.sin(phase + i * 1.3))[:, None]
        d = stiff * d + (1 - stiff) * target
        d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-12
        P[:, i] = P[:, i - 1] + d * seg
        if collider is not None:
            P[:, i] = collider.push(P[:, i], margin * (0.6 + 0.8 * t))
    return P


def children_from_guides(G, groots, croots, rng, clump=0.6, spread_noise=0.002):
    """Interpolate child strands from nearest guides (with clumping toward the tip)."""
    tree = cKDTree(groots)
    _, gi = tree.query(croots, k=1)
    K = G.shape[1]
    t = np.linspace(0, 1, K)[None, :, None]
    off = (croots - groots[gi])[:, None, :]
    C = G[gi] - groots[gi][:, None, :] + croots[:, None, :]
    C = C - off * clump * t
    C += rng.normal(0, spread_noise, C.shape) * t
    return C


# ----------------------------------------------------------------------------- the puppet
DEFAULT = dict(
    skin='#e8a98a', nose_mult=0.92, lip_r=0.009,
    H=0.20, zc=0.07, Wc=0.128, Dc=0.135, W=0.138, D=0.135, zk=0.005, zm=-0.04, Wm=0.122, Dm=0.122,
    cy_top=0.008, cy_mouth=-0.006, Wj=0.108, Dj=0.108, zb=-0.128, chin_fwd=0.014, jaw_pow=0.7,
    smile=0.008, n_exp=2.05, hinge_y=0.06,
    sculpt=dict(brow=0.012, cheek=0.012, jowl=0.0, chin=0.006, temple=0.006),
    fuzz=dict(count=110000, len=0.0028, hex=None),
    eye_r=0.034, eye_x=0.043, eye_z=0.058, eye_sink=0.5, pupil=0.42, lid=0.36, lid_tilt=0.0, low_lid=0.0,
    lid_hex=None, eye_conv=1.2,
    nose=dict(w=0.032, h=0.03, l=0.04, z=0.012, droop=0.18, sink=0.55),
    ears=dict(size=0.04, z=0.02, show=True),
    brows=dict(hex='#6b6b6b', z=0.103, len=0.058, thick=1.4, angle=0.0, arch=0.007, x=0.046, fur=0.02),
    hair=dict(style='side_part', hex='#9a9a9a', part=0.035, length=0.035, density=1.0),
    body=dict(robe='#060607', shirt='#ecebe6', tie='#2a2f4a', w=0.2, d=0.13, shoulder=0.195, collar=True),
    neck_r=0.06,
    glasses=None,  # e.g. dict(hex='#2a2a2a', r=1.18, wire=0.0022) to put frames on a puppet
    # --- optional extras (all off by default; the Supreme Court puppets don't use them)
    beard=None,      # dict(hex, hex2, frac, chin, density, len, chin_len, cheek_z, mw, beard, mustache, shadow, shadow_hex)
    lipstick=None,   # dict(hex) colours the lip rim of the mouth
    iris=None,       # dict(hex, r) coloured iris cap under the pupil
    necklace=None,   # dict(hex, drop, star)
)


def merged(spec):
    out = {}
    for k, v in DEFAULT.items():
        if isinstance(v, dict):
            out[k] = dict(v, **spec.get(k, {}))
        else:
            out[k] = spec.get(k, v)
    return out


def head_rings(s, part):
    """Ring profiles for the upper head ('upper') or lower jaw ('jaw'); materials 0=skin 1=mouth."""
    lip = s['lip_r']
    zm = s['zm']
    lipm = 2 if s.get('lipstick') else 0  # material index of the lip rim (2 = lipstick)
    if part == 'upper':
        rings = []
        H, zc = s['H'], s['zc']
        for a in np.linspace(0, math.pi / 2, 14):
            rings.append((zc + (H - zc) * math.cos(a), s['Wc'] * math.sin(a), s['Dc'] * math.sin(a),
                          s['cy_top'] * math.cos(a), 0))
        # below cranium equator: cheeks -> mouth edge (pchip through control points)
        zs = np.array([zc, s['zk'], zm + lip])
        rxs = np.array([s['Wc'], s['W'], s['Wm']])
        rys = np.array([s['Dc'], s['D'], s['Dm']])
        cys = np.array([0.0, 0.0, s['cy_mouth']])
        fx, fy, fc = (PchipInterpolator(-zs, v) for v in (rxs, rys, cys))
        for z in np.linspace(zc, zm + lip, 10)[1:]:
            rings.append((z, float(fx(-z)), float(fy(-z)), float(fc(-z)), 0))
        # lip bevel curling under
        for a in np.linspace(0, math.pi / 2, 6)[1:]:
            rings.append((zm + lip - lip * math.sin(a), s['Wm'] - lip + lip * math.cos(a),
                          s['Dm'] - lip + lip * math.cos(a), s['cy_mouth'], lipm))
        # mouth roof
        for f in np.linspace(1, 0, 7)[1:]:
            rings.append((zm, (s['Wm'] - lip) * f, (s['Dm'] - lip) * f, s['cy_mouth'], 1))
        return rings
    rings = []
    for f in np.linspace(0, 1, 7):
        rings.append((zm, (s['Wm'] - lip) * f, (s['Dm'] - lip) * f, s['cy_mouth'], 1))
    for a in np.linspace(0, math.pi / 2, 6)[1:]:
        rings.append((zm - lip + lip * math.cos(a), s['Wm'] - lip + lip * math.sin(a),
                      s['Dm'] - lip + lip * math.sin(a), s['cy_mouth'], lipm))
    zj0, zb = zm - lip, s['zb']
    for a in np.linspace(0, math.pi / 2, 16)[1:]:
        sn, c = math.cos(a), math.sin(a)  # sn: 1 at mouth -> 0 at bottom
        rx = s['Wm'] + (s['Wj'] - s['Wm']) * min(1, c * 3)
        rings.append((zj0 - (zj0 - zb) * c, rx * sn ** s['jaw_pow'] if sn > 1e-6 else 0.0,
                      s['Dj'] * sn if sn > 1e-6 else 0.0, s['cy_mouth'] - s['chin_fwd'] * c, 0))
    return rings


def front_y(rings, x, z, n_exp):
    """Approximate front surface y of a lofted shape at (x, z)."""
    zs = np.array([r[0] for r in rings])
    i = int(np.argmin(np.abs(zs - z)))
    zz, rx, ry, cy, _ = rings[i]
    u = min(abs(x) / max(rx, 1e-6), 0.999)
    return cy - ry * (1 - u ** n_exp) ** (1.0 / n_exp)


def ring_interp(rings, z, n_use=23):
    """(rx, ry, cy) of the upper-head loft at height z, by linear interpolation of the cranium/cheek rings."""
    zs = np.array([r[0] for r in rings[:n_use]])[::-1]
    return tuple(float(np.interp(z, zs, np.array([r[k] for r in rings[:n_use]])[::-1])) for k in (1, 2, 3))


def skin_shadow(mat, color, strength, attr='beard'):
    """Darken a skin material by a per-vertex mesh attribute (beard shadow / stubble under the fur)."""
    nt = mat.node_tree
    pb = nt.nodes['Principled BSDF']
    src_sock = pb.inputs['Base Color'].links[0].from_socket
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = attr
    sc_ = nt.nodes.new('ShaderNodeMath'); sc_.operation = 'MULTIPLY'; sc_.inputs[1].default_value = strength
    nt.links.new(at.outputs['Fac'], sc_.inputs[0])
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    nt.links.new(sc_.outputs[0], mx.inputs['Factor'])
    nt.links.new(src_sock, mx.inputs['A'])
    mx.inputs['B'].default_value = color
    nt.links.new(mx.outputs['Result'], pb.inputs['Base Color'])


def set_vertex_attr(ob, name, values):
    me = ob.data
    if len(values) != len(me.vertices):
        return
    a = me.attributes.new(name, 'FLOAT', 'POINT')
    a.data.foreach_set('value', np.asarray(values, np.float32))


def beard_weights(s, bd):
    """Smooth 0..1 masks (functions of head-frame points) for the jaw beard, upper-head cheek beard and mustache."""
    zm, lip = s['zm'], s['lip_r']
    cheek_z = bd.get('cheek_z', zm + 0.045)
    mw = bd.get('mw', 0.05)
    mh = bd.get('must_h', 0.027)
    full = bd.get('beard', True)
    must = bd.get('mustache', True)

    def jaw(C):
        x, y, z = C[:, 0], C[:, 1], C[:, 2]
        if not full:
            return np.zeros(len(C))
        return np.clip(((zm - lip - bd.get('lip_gap', 0.003)) - z) / 0.006, 0, 1) * np.clip((0.05 - y) / 0.03, 0, 1)

    def cheek(C):
        x, y, z = C[:, 0], C[:, 1], C[:, 2]
        if not full:
            return np.zeros(len(C))
        zline = cheek_z + (bd.get('sideburn_z', 0.03) - cheek_z) * np.clip((np.abs(x) - 0.05) / 0.07, 0, 1)
        return (np.clip((zline - z) / 0.012, 0, 1) * np.clip((z - (zm + lip * 0.6)) / 0.004, 0, 1)
                * np.clip((0.045 - y) / 0.03, 0, 1))

    def mustache(C):
        x, y, z = C[:, 0], C[:, 1], C[:, 2]
        if not must:
            return np.zeros(len(C))
        return (np.clip((mw - np.abs(x)) / 0.008, 0, 1) * np.clip((zm + mh - z) / 0.006, 0, 1)
                * np.clip((z - (zm + lip * 0.5)) / 0.004, 0, 1) * np.clip((0.0 - y) / 0.03, 0, 1))
    return jaw, cheek, mustache


def build_beard(name, s, Vu, Fu, Mu, Vj, Fj, Mj, head, jaw, hinge, seed):
    """Short fur on the lower face: chin/jaw strands ride the jaw mesh, cheeks and mustache the upper head."""
    bd = s['beard']
    rng = np.random.default_rng(seed + 77)
    zm = s['zm']
    m1 = mat_hair(name + '_beard', hex_lin(bd.get('hex', '#1c1511')), rough=0.5, rand=0.1)
    m2 = mat_hair(name + '_beard2', hex_lin(bd['hex2']), rough=0.5, rand=0.1) if bd.get('hex2') else None
    dens = bd.get('density', 1.0)
    Lc = bd.get('len', 0.011)
    Lchin = bd.get('chin_len', Lc * 1.5)
    w_jaw, w_cheek, w_must = beard_weights(s, bd)

    def gray_p(z):
        return bd.get('frac', 0.0) + bd.get('chin', 0.0) * np.clip(((zm - 0.025) - z) / 0.07, 0, 1)

    def comb_down(P, n):
        v = np.stack([np.sign(P[:, 0]) * 0.18 * np.clip(np.abs(P[:, 0]) / 0.08, 0, 1), np.full(len(P), -0.12),
                      np.full(len(P), -1.0)], 1)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def comb_must(P, n):
        v = np.stack([np.sign(P[:, 0]) * 0.55, np.full(len(P), -0.35), np.full(len(P), -0.8)], 1)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def emit(tag, R, Nn, comb, lengths, par, off, lift):
        n = len(R)
        G = grow(R, Nn, lengths, 4, comb, None, rng, lift=lift, gravity=0.0, stiff=0.55, margin=0.0, jitter=0.22)
        G = G - off
        rad = np.tile(np.linspace(bd.get('r0', 0.00085), 0.0003, 4), (n, 1))
        if m2 is not None:
            gray = rng.random(n) < gray_p(R[:, 2])
            parts = ((~gray, m1, ''), (gray, m2, '2'))
        else:
            parts = ((np.ones(n, bool), m1, ''),)
        for sel, mat, suf in parts:
            if sel.any():
                curves_obj(f'{name}_{tag}{suf}', G[sel], rad[sel], mat, parent=par)

    center_u = np.array([0, 0, s['zc']])
    if bd.get('beard', True):
        okj = np.array(Mj) == 0
        R, Nn = sample_surface(Vj, Fj, int(40000 * dens), rng, w_jaw, np.array([0, 0, zm - 0.05]), face_ok=okj)
        z = R[:, 2]
        chin = np.clip(((zm - 0.03) - z) / 0.05, 0, 1) * np.clip((0.06 - np.abs(R[:, 0])) / 0.04, 0, 1)
        emit('beardj', R, Nn, comb_down, Lc + (Lchin - Lc) * chin, jaw, hinge, 0.45)
        oku = np.array(Mu) == 0
        R, Nn = sample_surface(Vu, Fu, int(30000 * dens), rng, w_cheek, center_u, face_ok=oku)
        emit('beardc', R, Nn, comb_down, np.full(len(R), Lc * 0.9), head, np.zeros(3), 0.45)
    if bd.get('mustache', True):
        oku = np.array(Mu) == 0
        R, Nn = sample_surface(Vu, Fu, int(bd.get('must_count', 12000) * dens), rng, w_must, center_u, face_ok=oku)
        emit('must', R, Nn, comb_must, np.full(len(R), bd.get('must_len', Lc * 1.5)) * rng.uniform(0.8, 1.2, len(R)),
             head, np.zeros(3), 0.4)


def build_necklace(name, s, br, neck_base, root):
    """Thin chain hanging on the chest (with a small star), following the front of the body rings."""
    nk = s['necklace']
    zs = np.array([r[0] for r in br[1:-1]])[::-1]

    def front(x, z):
        rx, ry, cy = (float(np.interp(z, zs, np.array([r[k] for r in br[1:-1]])[::-1])) for k in (1, 2, 3))
        u = min(abs(x) / max(rx, 1e-6), 0.999)
        return cy - ry * (1 - u ** 2.25) ** (1 / 2.25)
    drop = nk.get('drop', 0.1)
    pts = []
    for t in np.linspace(-1, 1, 19):
        x = 0.062 * t
        z = neck_base + 0.004 - drop * (1 - t * t) ** 1.0
        pts.append((x, front(x, z) - 0.0035, z))
    gold = mat_plain(name + '_chain', hex_lin(nk.get('hex', '#d9b550')), rough=0.22, metallic=1.0)
    tube(name + '_chain', pts, np.full(len(pts), 0.0011), [gold], nseg=8, parent=root, caps=False)
    if nk.get('star', True):
        cx, cz = 0.0, neck_base + 0.004 - drop
        cy = front(0.0, cz) - 0.006
        V = [(cx, cy, cz)]
        for k in range(10):
            a = math.pi / 2 + k * math.pi / 5
            r = 0.0105 if k % 2 == 0 else 0.0045
            V.append((cx + r * math.cos(a), cy - 0.0004, cz + r * math.sin(a)))
        Fs = [(0, 1 + k, 1 + (k + 1) % 10) for k in range(10)]
        mesh_obj(name + '_star', np.array(V), Fs, [0] * len(Fs), [gold], parent=root)


def emit_hair(name, C, rad, hs, hm, head, rng, pg=None):
    """Hair curves object(s). hs['mix'] = dict(hex2, frac, temple) splits strands into two colours (salt and pepper)."""
    mix = hs.get('mix')
    if not mix:
        return [curves_obj(name + '_hair', C, rad, hm, parent=head)]
    if pg is None:
        pg = mix.get('frac', 0.3) + mix.get('temple', 0.0) * np.clip(np.abs(C[:, 0, 0]) / 0.1, 0, 1)
    gray = rng.random(len(C)) < pg
    hm2 = mat_hair(name + '_hair2', hex_lin(mix['hex2']), rough=hs.get('rough', 0.42), rand=hs.get('rand', 0.12))
    out = []
    for sel, mat, nm in ((~gray, hm, '_hair'), (gray, hm2, '_hair2')):
        if sel.any():
            out.append(curves_obj(name + nm, C[sel], rad[sel], mat, parent=head))
    return out


def build_puppet(name, spec, root_loc=(0, 0, 0), root_rot_z=0.0, body_h=0.55, seed=1, hair_scale=1.0):
    """Returns dict(root, jaw, head, hinge_angle_fn). Head centre sits at root + (0,0,body_h)."""
    s = merged(spec)
    rng = np.random.default_rng(seed)
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.location = root_loc
    root.rotation_euler = (0, 0, root_rot_z)
    head = bpy.data.objects.new(name + '_head', None)
    bpy.context.collection.objects.link(head)
    head.parent = root
    head.location = (0, 0, body_h)

    skin = mat_fleece(name + '_skin', hex_lin(s['skin']))
    mouth = mat_fleece(name + '_mouth', hex_lin('#2a0508'), sheen=0.3)
    nose_m = mat_fleece(name + '_nose', hex_lin(s['skin'], s['nose_mult']))
    lid_m = mat_fleece(name + '_lid', hex_lin(s['lid_hex'] or s['skin'], 0.93 if not s['lid_hex'] else 1.0))
    eye_m = mat_plain(name + '_eyew', hex_lin('#f1efe8'), rough=0.33, coat=0.3, spec=0.4)
    pup_m = mat_plain(name + '_pupil', (0.004, 0.004, 0.004, 1), rough=0.12, coat=1.0)
    tongue_m = mat_fleece(name + '_tongue', hex_lin('#9c2b35'), sheen=0.5)
    lip_m = None
    if s.get('lipstick'):
        ls = s['lipstick']
        lip_m = mat_fleece(name + '_lip', hex_lin(ls['hex']), sheen=0.5, rough=0.55)
        lip_m.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = ls.get('gloss', 0.25)
    bd_ = s.get('beard')
    if bd_ and bd_.get('shadow', 0.5) > 0:
        skin_shadow(skin, hex_lin(bd_.get('shadow_hex', bd_.get('hex', '#1c1511'))), bd_.get('shadow', 0.5))
    skin_mats = [skin, mouth] + ([lip_m] if lip_m else [])

    smile, Wm, zm = s['smile'], s['Wm'], s['zm']

    def zfun(V):  # mouth-line smile curve shared by upper head and jaw
        return smile * (V[:, 0] / Wm) ** 2 * np.exp(-((V[:, 2] - zm) / 0.03) ** 2) * (V[:, 1] < 0.03)

    sc_ = s['sculpt']

    def sculpt(V):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        front = np.clip(-y / 0.05, 0, 1)
        dy = np.zeros(len(V)); dx = np.zeros(len(V))
        dy -= sc_['brow'] * np.exp(-((z - (s['eye_z'] + 0.042)) / 0.016) ** 2) * np.exp(-(x / 0.075) ** 2) * front
        ck = np.exp(-((z - (s['eye_z'] - 0.045)) / 0.028) ** 2) * np.exp(-((np.abs(x) - 0.075) / 0.035) ** 2)
        dy -= sc_['cheek'] * ck * front
        dx += np.sign(x) * sc_['cheek'] * 0.5 * ck
        jw = np.exp(-((z - (s['zm'] - 0.035)) / 0.03) ** 2) * np.exp(-((np.abs(x) - 0.08) / 0.04) ** 2)
        dx += np.sign(x) * sc_['jowl'] * jw
        dy -= sc_['chin'] * np.exp(-((z - (s['zb'] + 0.035)) / 0.025) ** 2) * np.exp(-(x / 0.04) ** 2) * front
        tp = np.exp(-((z - (s['eye_z'] + 0.03)) / 0.03) ** 2) * (np.abs(x) > 0.09)
        dx -= np.sign(x) * sc_['temple'] * tp
        V[:, 0] += dx; V[:, 1] += dy
        return V

    up_r = head_rings(s, 'upper')
    Vu, Fu, Mu = loft(up_r, 96, s['n_exp'], zfun)
    Vu = sculpt(Vu)

    def surf(x, z):
        x = np.atleast_1d(np.asarray(x, float)); z = np.atleast_1d(np.asarray(z, float))
        y = np.array([front_y(up_r, xi, zi, s['n_exp']) for xi, zi in zip(x, z)])
        return sculpt(np.stack([x, y, z], 1))
    upper = mesh_obj(name + '_upper', Vu, Fu, Mu, skin_mats, parent=head)

    jaw_r = head_rings(s, 'jaw')
    Vj, Fj, Mj = loft(jaw_r, 96, s['n_exp'], zfun)
    Vj = sculpt(Vj)
    hinge = np.array([0.0, s['hinge_y'], zm])
    jaw = mesh_obj(name + '_jaw', Vj - hinge, Fj, Mj, skin_mats, parent=head, location=tuple(hinge))
    if bd_ and bd_.get('shadow', 0.5) > 0:
        wj_, wc_, wm_ = beard_weights(s, bd_)
        set_vertex_attr(upper, 'beard', np.maximum(wc_(Vu), wm_(Vu)))
        set_vertex_attr(jaw, 'beard', wj_(Vj))

    # mouth cavity (dark) so an open mouth has depth
    uv_sphere(name + '_cavity', 1.0, [mouth], scale=(s['Wm'] * 0.86, s['Dm'] * 0.84, 0.07), parent=head,
              loc=(0, s['cy_mouth'] + 0.01, zm))
    # tongue rides on the jaw
    uv_sphere(name + '_tongue', 1.0, [tongue_m], scale=(Wm * 0.48, s['Dm'] * 0.55, 0.012), parent=jaw,
              loc=(0, s['cy_mouth'] - s['Dm'] * 0.25 - hinge[1], 0.004))

    # eyes
    for sx in (-1, 1):
        ex, ez = sx * s['eye_x'], s['eye_z']
        c = surf(ex, ez)[0] + np.array([0, s['eye_r'] * s['eye_sink'], 0])
        uv_sphere(f'{name}_eye{sx}', s['eye_r'], [eye_m], parent=head, loc=tuple(c))
        gaze = np.array([-ex * s['eye_conv'] * 0.0, -1.0, 0.02])
        gaze = gaze + np.array([-sx * 0.04 * s['eye_conv'], 0, 0])
        gaze /= np.linalg.norm(gaze)
        pc = c + gaze * s['eye_r'] * 0.93
        pr = s['eye_r'] * s['pupil']
        pup = uv_sphere(f'{name}_pupil{sx}', 1.0, [pup_m], scale=(pr, pr, s['eye_r'] * 0.12), parent=head,
                        loc=tuple(pc))
        pup.rotation_mode = 'QUATERNION'
        pup.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(gaze))
        if s.get('iris'):  # coloured iris: a spherical cap on the eyeball under the pupil
            ir = s['iris']
            iris_m = mat_plain(name + '_iris', hex_lin(ir['hex']), rough=0.3, coat=0.5, spec=0.4)
            R_ = s['eye_r'] * 1.004
            cap = math.asin(min(0.95, ir.get('r', 0.68)))
            ic = uv_sphere(f'{name}_iris{sx}', R_, [iris_m], segs=64, rings=64, parent=head, loc=tuple(c),
                           keep=lambda V, R_=R_, cap=cap: V[:, 2] >= R_ * math.cos(cap) - 1e-9)
            ic.rotation_mode = 'QUATERNION'
            ic.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(gaze))
        # upper lid: sphere cap above a tilted plane
        lr = s['eye_r'] * 1.07
        lid, tilt = s['lid'], s['lid_tilt'] * sx
        h0 = lr * (1 - 2 * lid)
        nrm = np.array([math.sin(tilt), 0.0, math.cos(tilt)])
        nrm = nrm / np.linalg.norm(nrm)
        uv_sphere(f'{name}_lid{sx}', lr, [lid_m], segs=48, rings=32, parent=head, loc=tuple(c),
                  keep=lambda V, n=nrm, h=h0: (V @ n) >= h - 1e-9)
        if s['low_lid'] > 0:
            h1 = lr * (1 - 2 * s['low_lid'])
            uv_sphere(f'{name}_llid{sx}', lr * 1.01, [lid_m], segs=48, rings=32, parent=head, loc=tuple(c),
                      keep=lambda V, h=h1: (-V[:, 2]) >= h - 1e-9)

    # optional glasses: rims in front of each eye, bridge over the nose, temples back to the ears.
    # keys: hex, metal, r (rim size), wire (thickness), n (rim shape: 2 = ellipse, ~4 = rounded rectangle),
    #       trans (0..1 frame translucency), up = z of the lens centres to wear them pushed up on top of the head,
    #       off (gap between the frames and the hair when pushed up)
    gl = s.get('glasses')
    if gl:
        fr_m = mat_plain(name + '_frames', hex_lin(gl.get('hex', '#2b2b2b')), rough=0.25, coat=0.5,
                         metallic=gl.get('metal', 0.0))
        if gl.get('trans'):
            pf = fr_m.node_tree.nodes['Principled BSDF']
            pf.inputs['Transmission Weight'].default_value = gl['trans']
            pf.inputs['Roughness'].default_value = 0.12
            pf.inputs['IOR'].default_value = 1.35
        lens_m, ntl, pl = _new_mat(name + '_lens')
        pl.inputs['Transmission Weight'].default_value = 1.0
        pl.inputs['Roughness'].default_value = 0.02
        pl.inputs['IOR'].default_value = 1.2
        pl.inputs['Thin Wall'].default_value = True
        rr = s['eye_r'] * gl.get('r', 1.18)
        wire = gl.get('wire', 0.0022)
        nexp = float(gl.get('n', 2.0))
        ang = np.linspace(0, 2 * np.pi, 49)
        if nexp == 2.0:
            ux, uz = np.cos(ang), np.sin(ang)
        else:
            ux = np.sign(np.cos(ang)) * np.abs(np.cos(ang)) ** (2 / nexp)
            uz = np.sign(np.sin(ang)) * np.abs(np.sin(ang)) ** (2 / nexp)
        up = gl.get('up')
        cents = []
        if up is None:
            for sx in (-1, 1):
                c = surf(sx * s['eye_x'], s['eye_z'])[0] + np.array([0, s['eye_r'] * s['eye_sink'], 0])
                c = c + np.array([0, -s['eye_r'] * 1.08, 0])
                cents.append(c)
                ring = np.stack([c[0] + rr * ux * 1.08, np.full_like(ang, c[1]), c[2] + rr * uz * 0.86], 1)
                tube(f'{name}_rim{sx}', ring, np.full(len(ring), wire), [fr_m], nseg=10, parent=head, caps=False)
                lv = [c + np.array([rr * 1.08 * ux[j], 0.0005, rr * 0.86 * uz[j]]) for j in range(48)]
                lv = np.array([c + np.array([0, 0.0005, 0])] + lv)
                lf = [(0, 1 + j, 1 + (j + 1) % 48) for j in range(48)]
                mesh_obj(f'{name}_lens{sx}', lv, lf, [0] * len(lf), [lens_m], parent=head)
                ear_pt = np.array([sx * (s['W'] + 0.004), 0.03, s['eye_z'] - 0.005])
                t0 = c + np.array([sx * rr * 1.08, 0, rr * 0.2])
                tube(f'{name}_temple{sx}', [t0, t0 + np.array([sx * 0.006, 0.02, 0]), ear_pt],
                     [wire, wire, wire], [fr_m], nseg=10, parent=head)
            a_, b_ = cents[0] + np.array([rr * 1.08, 0, rr * 0.25]), cents[1] + np.array([-rr * 1.08, 0, rr * 0.25])
            mid = (a_ + b_) / 2 + np.array([0, -0.004, 0.006])
            tube(f'{name}_bridge', [a_, mid, b_], [wire, wire, wire], [fr_m], nseg=10, parent=head)
        else:
            # pushed up: the frames lie on the dome of the head, following its curvature
            zu = float(up)
            off = gl.get('off', 0.03)
            phi = math.atan2((surf(0.0, zu + 0.01)[0][1] - surf(0.0, zu)[0][1]) / 0.01, 1.0)

            def dome(u, v, w=0.0):
                zz = zu + v * math.cos(phi)
                yc = surf(u, zz)[0][1]
                yz = (surf(u, zz + 0.004)[0][1] - surf(u, zz - 0.004)[0][1]) / 0.008
                n_ = np.array([0.0, -1.0, yz]); n_ /= np.linalg.norm(n_)
                return np.array([u, yc, zz]) + n_ * (off + w)
            gap = gl.get('gap', 1.0)
            for sx in (-1, 1):
                u0 = sx * s['eye_x'] * gap
                ring = np.array([dome(u0 + rr * 1.08 * ux[j], rr * 0.86 * uz[j]) for j in range(49)])
                tube(f'{name}_rim{sx}', ring, np.full(len(ring), wire), [fr_m], nseg=10, parent=head, caps=False)
                lv = np.array([dome(u0, 0.0, 0.0005)] + [dome(u0 + rr * 1.08 * ux[j], rr * 0.86 * uz[j], 0.0005)
                                                        for j in range(48)])
                lf = [(0, 1 + j, 1 + (j + 1) % 48) for j in range(48)]
                mesh_obj(f'{name}_lens{sx}', lv, lf, [0] * len(lf), [lens_m], parent=head)
                # temple arm: from the outer rim edge around the side of the head
                p0 = dome(u0 + sx * rr * 1.08, rr * 0.2)
                rx_, ry_, cy_ = ring_interp(up_r, p0[2] - 0.004)
                psi0 = math.asin(min(0.98, abs(p0[0]) / (rx_ + off)))
                pts = [p0]
                for k, psi in enumerate((psi0 + (math.pi / 2 - psi0) * 0.55, math.pi / 2 + 0.1, math.pi / 2 + 0.55)):
                    pts.append(np.array([sx * (rx_ + off) * math.sin(psi), cy_ - (ry_ + off) * math.cos(psi),
                                         p0[2] - 0.004 * (k + 1)]))
                tube(f'{name}_temple{sx}', pts, [wire] * len(pts), [fr_m], nseg=10, parent=head)
            a_, b_ = dome(-s['eye_x'] * gap + rr * 1.08, rr * 0.25), dome(s['eye_x'] * gap - rr * 1.08, rr * 0.25)
            mid = dome(0.0, rr * 0.25 + 0.004, 0.003)
            tube(f'{name}_bridge', [a_, mid, b_], [wire, wire, wire], [fr_m], nseg=10, parent=head)

    # nose
    nz = s['nose']
    fy = surf(0.0, nz['z'])[0][1]
    nose = uv_sphere(name + '_nose', 1.0, [nose_m], scale=(nz['w'], nz['l'], nz['h']), parent=head,
                     loc=(0, fy - nz['l'] * (1 - nz['sink']), nz['z']))
    nose.rotation_euler = (nz['droop'], 0, 0)

    # ears
    ez = s['ears']
    if ez['show']:
        for sx in (-1, 1):
            zz = ez['z']
            xx = sx * (float(PchipInterpolator(-np.array([s['zc'], s['zk'], zm]),
                                               np.array([s['Wc'], s['W'], s['Wm']]))(-zz)) - 0.006)
            e = uv_sphere(f'{name}_ear{sx}', 1.0, [skin], scale=(ez['size'] * 0.28, ez['size'] * 0.62,
                                                                  ez['size']), parent=head, loc=(xx, 0.035, zz))
            e.rotation_euler = (0, 0, -sx * 0.45)

    # neck + body
    b = s['body']
    # optional garment extras (patterns, V/U neckline, lapel pin, ...): see mat_robe
    robe_kw = {k: b[k] for k in ('v_shape', 'v_depth', 'v_half', 'pattern', 'shirt_pattern', 'tie_pattern', 'pin',
                                 'lapel', 'fabric', 'placket', 'buttons', 'pockets') if k in b}
    body_m = mat_robe(name + '_robe', b['robe'], b['shirt'], b.get('tie'), **robe_kw)
    nb = 0.0
    zn = -body_h + 0.0  # body rings expressed in root frame; neck base at z = body_h + zb + 0.01
    neck_base = body_h + s['zb'] + 0.035
    br = []
    sh = b['shoulder']
    prof = [(0.0, 0.0, 0.0), (0.0, s['neck_r'] * 1.3, s['neck_r'] * 1.25), (-0.02, sh * 0.5, b['d'] * 0.75),
            (-0.05, sh * 0.78, b['d'] * 0.88), (-0.09, sh * 0.95, b['d'] * 0.97), (-0.14, sh, b['d']),
            (-0.3, b['w'] * 0.98, b['d'] * 1.03), (-b.get('len', 0.6), b['w'] * 0.96, b['d'] * 1.05)]
    for dz, rx, ry in prof:
        br.append((neck_base + dz, rx, ry, 0.012, 0))
    br.append((neck_base - b.get('len', 0.6), 0.0, 0.0, 0.012, 0))
    Vb, Fb, Mb = loft(br, 96, 2.25)
    body = mesh_obj(name + '_body', Vb, Fb, Mb, [body_m], parent=root)
    # object-space mask in mat_robe expects z=0 at neck base: shift mesh so origin is at neck base
    body.data.transform(Matrix.Translation((0, 0, -neck_base)))
    body.location = (0, 0, neck_base)
    sleeve_m = mat_robe(name + '_sleeve', b['robe'], b['shirt'], None, v_half=0.0,
                        **{k: b[k] for k in ('pattern', 'fabric') if k in b})
    # arms in robe sleeves, forearms resting forward (on the bench / lectern), fleece mitten hands
    rest_z = neck_base + b.get('rest_dz', -0.36)
    for sx in (-1, 1):
        sh_p = (sx * sh * 0.82, 0.01, neck_base - 0.075)
        el_p = (sx * sh * 1.02, -0.01, neck_base - 0.3)
        wr_p = (sx * b.get('hand_x', 0.13), -b.get('reach', 0.26), rest_z + 0.03)
        mid_p = (sx * sh * 0.96, -0.08, rest_z + 0.025)
        tube(f'{name}_arm{sx}', [sh_p, el_p, mid_p, wr_p], [0.058, 0.062, 0.058, 0.05], [sleeve_m], parent=root)
        hnd = uv_sphere(f'{name}_hand{sx}', 1.0, [skin], scale=(0.045, 0.062, 0.024), parent=root,
                        loc=(wr_p[0] - sx * 0.01, wr_p[1] - 0.05, rest_z + 0.018))
        hnd.rotation_euler = (0, 0, sx * 0.35)
    # neck column (skin) hidden mostly by collar
    nr = []
    for z in np.linspace(neck_base + 0.002, body_h + s['zb'] + 0.06, 5):
        nr.append((z, s['neck_r'], s['neck_r'] * 0.95, 0.01, 0))
    Vn, Fn, Mn = loft([(nr[0][0], 0, 0, 0.01, 0)] + nr + [(nr[-1][0], 0, 0, 0.01, 0)], 48, 2.0)
    mesh_obj(name + '_neck', Vn, Fn, Mn, [skin], parent=root)
    if b.get('collar', True):
        chex = b.get('collar_hex', b['shirt'])
        if 'collar_pattern' in b or 'collar_fabric' in b:
            col_m = mat_robe(name + '_collar', chex, chex, None, v_half=0.0, pattern=b.get('collar_pattern'),
                             fabric=b.get('collar_fabric', 'cotton'))
        else:
            col_m = mat_plain(name + '_collar', hex_lin(chex), rough=0.75, sheen=0.3)
        cr = []
        for z, rr in ((neck_base - 0.004, 1.32), (neck_base + 0.02, 1.18), (neck_base + 0.036, 1.12)):
            cr.append((z, s['neck_r'] * rr, s['neck_r'] * rr * 0.97, 0.008, 0))
        Vc, Fc, Mc = loft(cr, 64, 2.0)
        # open the collar at the front a little (drop faces near front centre)
        keepf = [i for i, f in enumerate(Fc) if not (np.all(np.abs(Vc[list(f), 0]) < 0.012)
                                                    and np.all(Vc[list(f), 1] < 0))]
        mesh_obj(name + '_collar', Vc, [Fc[i] for i in keepf], [0] * len(keepf), [col_m], parent=root)

    # brows
    bw = s['brows']
    brow_m = mat_hair(name + '_browhair', hex_lin(bw['hex']), rough=0.65)
    allP = []
    for sx in (-1, 1):
        n_s = int(420 * bw['thick'])
        t = rng.random(n_s)
        bx = sx * (bw['x'] - bw['len'] / 2 + bw['len'] * t)
        u = (t - 0.5) * 2
        bz = bw['z'] + bw['arch'] * (1 - u ** 2) + sx * 0 + bw['angle'] * (t - 0.5) * bw['len'] \
            + rng.normal(0, 0.0035 * bw['thick'], n_s)
        R = surf(bx, bz) - np.array([0, 0.0015, 0])
        d = np.stack([np.full(n_s, sx * 0.85), np.full(n_s, -0.25), np.full(n_s, 0.35)], 1)
        d += rng.normal(0, 0.25, d.shape)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        K = 4
        P = R[:, None, :] + d[:, None, :] * (np.linspace(0, 1, K)[None, :, None] * bw['fur'])
        P[:, :, 1] -= np.linspace(0, 1, K)[None, :] * 0.003
        allP.append(P)
    P = np.concatenate(allP)
    curves_obj(name + '_brows', P + np.array([0, 0, 0]), np.tile(np.linspace(0.0011, 0.0004, P.shape[1]),
                                                                 (len(P), 1)), brow_m, parent=head)

    # fleece fuzz: very short fibres over skin so silhouettes and grazing light read as fabric
    fz = s['fuzz']
    if fz['count'] > 0:
        fuzz_m = mat_hair(name + '_fuzz', hex_lin(fz['hex'] or s['skin'], 1.05), rough=0.5, rand=0.08)
        for part_name, V_, F_, M_, par, off in (('u', Vu, Fu, Mu, head, np.zeros(3)),
                                               ('j', Vj, Fj, Mj, jaw, hinge)):
            ok = np.array(M_) == 0
            n_f = int(fz['count'] * (1.0 if part_name == 'u' else 0.45) * hair_scale)
            R, Nn = sample_surface(V_, F_, n_f, rng, outward_center=np.array([0, 0, s['zc'] if part_name == 'u' else s['zm'] - 0.05]), face_ok=ok)
            d = Nn + rng.normal(0, 0.55, Nn.shape)
            d /= np.linalg.norm(d, axis=1, keepdims=True)
            K = 3
            Lf = fz['len'] * rng.uniform(0.6, 1.3, n_f)
            Pz = R[:, None, :] + d[:, None, :] * (np.linspace(0, 1, K)[None, :, None] * Lf[:, None, None])
            Pz -= off
            curves_obj(f'{name}_fuzz{part_name}', Pz, np.tile(np.array([0.00016, 0.00011, 0.00005]), (n_f, 1)),
                       fuzz_m, parent=par)

    # hair
    build_hair(name, s, Vu, Fu, up_r, head, rng, hair_scale)
    if bd_:
        build_beard(name, s, Vu, Fu, Mu, Vj, Fj, Mj, head, jaw, hinge, seed)
    if s.get('necklace'):
        build_necklace(name, s, br, neck_base, root)

    objs = [root]
    stack = [root]
    while stack:
        o = stack.pop()
        for ch in o.children:
            objs.append(ch); stack.append(ch)
    return dict(root=root, head=head, jaw=jaw, spec=s, objs=objs)


def build_hair(name, s, Vu, Fu, up_r, head, rng, hair_scale=1.0):
    hs = s['hair']
    style = hs['style']
    if style == 'none':
        return
    hm = mat_hair(name + '_hair', hex_lin(hs['hex']), rough=hs.get('rough', 0.42), rand=hs.get('rand', 0.12))
    H, zm, zc = s['H'], s['zm'], s['zc']
    coll = Collider([((0, s['cy_top'] * 0.5, zc), (s['Wc'] * 1.0, s['Dc'] * 1.0, (H - zc) * 1.0)),
                     ((0, 0, s['zk']), (s['W'] * 0.98, s['D'] * 0.98, 0.07)),
                     ((0, 0.012, s['zb'] - 0.33), (s['body']['shoulder'] * 1.05, s['body']['d'] * 1.08, 0.3))])
    center = np.array([0, 0, zc])

    def hairline(C, front_z, side_z, back_z, side_x_cut=None, temple=0.0):
        x, y, z = C[:, 0], C[:, 1], C[:, 2]
        ang = np.arctan2(y, x)  # front is ang=-pi/2
        fb = (np.sin(ang) + 1) / 2  # 0 at front, 1 at back
        sideness = np.abs(np.cos(ang))
        zline = (front_z * (1 - fb) + back_z * fb) * (1 - sideness) + side_z * sideness
        if temple:  # receding temples: raise the hairline at the front corners
            th = np.arctan2(np.abs(x), -y)
            zline = zline + temple * np.exp(-((th - 0.95) / 0.4) ** 2)
        m = (z > zline).astype(float)
        if side_x_cut is not None:  # keep ears clear
            m *= ~((np.abs(x) > side_x_cut[0]) & (z < side_x_cut[1]) & (y < 0.07) & (y > -0.03))
        return m

    part = hs.get('part', 0.0)

    if style in ('side_part', 'short', 'buzz'):
        L = hs.get('length', 0.035)
        front_z = hs.get('front_z', s['H'] * 0.62)
        mask = lambda C: hairline(C, front_z, hs.get('side_z', s['eye_z'] - 0.005), hs.get('back_z', zm),
                                  side_x_cut=(s['Wc'] * 0.8, s['eye_z'] + 0.005))
        n_g = 900
        groots, gn = sample_surface(Vu, Fu, n_g, rng, mask, center)

        def comb(P, n):
            x, y, z = P[:, 0], P[:, 1], P[:, 2]
            top = np.clip((z - (s['eye_z'] + 0.02)) / (H - s['eye_z']), 0, 1)
            lat = np.tanh((x - part) / 0.01)
            v = np.stack([lat * (0.4 + 0.6 * top), 0.55 + 0.2 * (1 - top), -0.5 * (1 - top) - 0.05], 1)
            if style == 'buzz':
                v = np.stack([lat * 0.3, np.full(len(x), 0.6), -0.4 * np.ones(len(x))], 1)
            v -= (np.einsum('ij,ij->i', v, n))[:, None] * n * 0.6
            return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

        K = 7
        G = grow(groots, gn, L, K, comb, coll, rng, lift=hs.get('lift', 0.55), gravity=0.05, stiff=0.6,
                 margin=0.002, jitter=0.18)
        nc = int(hs.get('count', 60000) * hs['density'] * hair_scale)
        croots, cn = sample_surface(Vu, Fu, nc, rng, mask, center)
        C = children_from_guides(G, groots, croots, rng, clump=0.35, spread_noise=0.0012)
        rad = np.tile(np.linspace(hs.get('r0', 0.00055), 0.00025, K), (nc, 1))
        curves_obj(name + '_hair', C, rad, hm, parent=head)
        return

    if style == 'cut':
        # short cuts: tousled, neat or swept up and back. keys: length (top), side_len, front_z, side_z, back_z,
        # temple (receding), part, sweep (0..1 back), up (0..1 lift at the front), side, tousle, clump, lift, jitter
        L_top = hs.get('length', 0.05)
        L_side = hs.get('side_len', L_top * 0.55)
        front_z = hs.get('front_z', H * 0.62)
        mask = lambda C: hairline(C, front_z, hs.get('side_z', s['eye_z']), hs.get('back_z', zm),
                                  side_x_cut=(s['Wc'] * 0.8, s['eye_z'] + 0.005), temple=hs.get('temple', 0.0))
        n_g = 1300
        groots, gn = sample_surface(Vu, Fu, n_g, rng, mask, center)
        up, sweep, sidek = hs.get('up', 0.0), hs.get('sweep', 0.5), hs.get('side', 0.4)
        tous = rng.normal(0, 1, (n_g, 3)) * hs.get('tousle', 0.0)

        def comb(P, n):
            x, y, z = P[:, 0], P[:, 1], P[:, 2]
            top = np.clip((z - (s['eye_z'] + 0.015)) / (H - s['eye_z'] - 0.015), 0, 1)
            fr = np.clip(-y / 0.09, 0, 1)
            lat = np.tanh((x - part) / 0.012)
            v = np.stack([lat * sidek * (0.3 + 0.7 * top),
                          (0.3 + 0.7 * sweep) * (0.35 + 0.65 * top) + 0.2 * (1 - top),
                          up * fr * top - 0.55 * (1 - top) - 0.05], 1)
            v = v + tous * (0.4 + 0.6 * top)[:, None]
            v -= np.einsum('ij,ij->i', v, n)[:, None] * n * hs.get('flat', 0.5)
            return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

        topf = np.clip((groots[:, 2] - s['eye_z']) / (H - s['eye_z']), 0, 1)
        frf = np.clip(-groots[:, 1] / 0.09, 0, 1)
        Lg = L_side + (L_top - L_side) * topf * (0.55 + 0.45 * frf)
        K = 8
        G = grow(groots, gn, Lg, K, comb, coll, rng, lift=hs.get('lift', 0.55), gravity=hs.get('gravity', 0.05),
                 stiff=hs.get('stiff', 0.6), margin=0.002, jitter=hs.get('jitter', 0.18))
        nc = int(hs.get('count', 70000) * hs['density'] * hair_scale)
        croots, cn = sample_surface(Vu, Fu, nc, rng, mask, center)
        C = children_from_guides(G, groots, croots, rng, clump=hs.get('clump', 0.4), spread_noise=0.0012)
        rad = np.tile(np.linspace(hs.get('r0', 0.00058), 0.00025, K), (nc, 1))
        emit_hair(name, C, rad, hs, hm, head, rng)
        return

    guard = FaceGuard(s['Wm'] * 0.88, -0.03, s['zb'] - 0.02, s['eye_z'] + 0.012)
    coll_f = Multi(coll, guard)

    if style == 'curls':
        # long curls / waves: guide strands fall like 'long'; each lock is a bundle of helical strands.
        # keys: length, volume, spread, locks, per_lock, curl_r, turns, lock_r, part, front_z, mix
        L = hs.get('length', 0.3)
        front_z = hs.get('front_z', H * 0.6)
        mask = lambda C: hairline(C, front_z, hs.get('side_z', s['eye_z'] + 0.01), hs.get('back_z', zm - 0.01))
        n_g = 1600
        groots, gn = sample_surface(Vu, Fu, n_g, rng, mask, center)

        def comb(P, n):
            x, y, z = P[:, 0], P[:, 1], P[:, 2]
            lat = np.tanh((x - part) / 0.012)
            top = np.clip((z - s['eye_z']) / (H - s['eye_z']), 0, 1)
            frontish = np.clip(-y / 0.08, 0, 1)
            fr = hs.get('fringe', 0.0)
            back = (1.0 - fr) * frontish * np.clip(top * 2.5, 0, 1)
            v = np.stack([lat * (0.7 * top + 0.25) * (0.6 + 0.4 * frontish) * (1 - 0.5 * back),
                          0.3 * top + 1.6 * back + 0.1,
                          (-0.2 - 1.1 * (1 - top) - fr * frontish * top) * (1 - back) + 0.55 * back], 1)
            return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

        K = 26
        Ls = L * (0.7 + 0.3 * np.clip((groots[:, 1] + 0.1) / 0.2, 0, 1))
        G = grow(groots, gn, Ls, K, comb, coll_f, rng, lift=hs.get('lift', 0.12), gravity=hs.get('gravity', 0.6),
                 stiff=0.72, margin=hs.get('volume', 0.02), jitter=0.08)
        sp = hs.get('spread', 0.0)
        tt = np.linspace(0, 1, K)
        if sp:  # push the mass outward from the head's axis, more toward the tips: a fuller silhouette
            xy = G[:, :, :2] - np.array([0.0, 0.0])
            xy /= np.linalg.norm(xy, axis=2, keepdims=True) + 1e-9
            G[:, :, :2] += xy * sp * (tt[None, :, None] ** 1.3) * np.clip((-G[:, :, 2] + H) / 0.2, 0.2, 1.0)[..., None]
            G[:, 1:] = coll_f.push(G[:, 1:].reshape(-1, 3), 0.004).reshape(n_g, K - 1, 3)
        n_lock, per = hs.get('locks', 650), hs.get('per_lock', 56)
        lroots, ln = sample_surface(Vu, Fu, n_lock, rng, mask, center)
        LC = children_from_guides(G, groots, lroots, rng, clump=0.0, spread_noise=0.0)
        T = np.gradient(LC, axis=1)
        T /= np.linalg.norm(T, axis=2, keepdims=True) + 1e-9
        ref = np.array([1.0, 0.3, 0.0]); ref /= np.linalg.norm(ref)
        N1 = np.cross(T, ref); N1 /= np.linalg.norm(N1, axis=2, keepdims=True) + 1e-9
        N2 = np.cross(T, N1)
        amp = hs.get('curl_r', 0.014) * np.clip(tt / 0.18, 0, 1)
        turns = hs.get('turns', 4.0) * rng.uniform(0.8, 1.25, n_lock)
        phase = rng.random(n_lock) * 2 * np.pi
        hand = rng.choice([-1.0, 1.0], n_lock)
        Phi = 2 * np.pi * turns[:, None] * tt[None, :] * hand[:, None] + phase[:, None]
        base = LC + amp[None, :, None] * (np.cos(Phi)[..., None] * N1 + np.sin(Phi)[..., None] * N2)
        lock_of = np.repeat(np.arange(n_lock), per)
        nc = len(lock_of)
        dl = rng.random(nc) * 2 * np.pi
        rho = np.sqrt(rng.random(nc)) * hs.get('lock_r', 0.006)
        ramp_t = np.clip(tt / 0.12, 0, 1)[None, :, None]
        C = base[lock_of] + rho[:, None, None] * (np.cos(dl)[:, None, None] * N1[lock_of]
                                                 + np.sin(dl)[:, None, None] * N2[lock_of]) * ramp_t
        C += rng.normal(0, 0.0007, C.shape) * ramp_t
        C[:, 1:] = coll_f.push(C[:, 1:].reshape(-1, 3), 0.003).reshape(nc, K - 1, 3)
        rad = np.tile(np.linspace(hs.get('r0', 0.00085), 0.00045, K), (nc, 1))
        pg = None
        if hs.get('mix'):
            bias = rng.random(n_lock)[lock_of]
            pg = np.clip(bias * 2 * hs['mix'].get('frac', 0.5), 0, 1)
        emit_hair(name, C, rad, hs, hm, head, rng, pg)
        return

    if style in ('bob', 'long'):
        L = hs.get('length', 0.17 if style == 'bob' else 0.30)
        front_z = hs.get('front_z', s['H'] * 0.6)
        mask = lambda C: hairline(C, front_z, hs.get('side_z', s['eye_z'] + 0.01), hs.get('back_z', zm - 0.01))
        n_g = 2000
        groots, gn = sample_surface(Vu, Fu, n_g, rng, mask, center)

        def comb(P, n):
            x, y, z = P[:, 0], P[:, 1], P[:, 2]
            lat = np.tanh((x - part) / 0.012)
            top = np.clip((z - s['eye_z']) / (H - s['eye_z']), 0, 1)
            frontish = np.clip(-y / 0.08, 0, 1)
            fr = hs.get('fringe', 0.0)
            # sweep away from the part and back on top; fall down along the sides lower on the head
            back = (1.0 - fr) * frontish * np.clip(top * 2.5, 0, 1)  # front hair pulled up and back off the face
            v = np.stack([lat * (0.7 * top + 0.25) * (0.6 + 0.4 * frontish) * (1 - 0.5 * back),
                          0.3 * top + 1.6 * back + 0.1,
                          (-0.2 - 1.1 * (1 - top) - fr * frontish * top) * (1 - back) + 0.55 * back], 1)
            return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

        K = 18
        Ls = L * (0.7 + 0.3 * np.clip((groots[:, 1] + 0.1) / 0.2, 0, 1))
        G = grow(groots, gn, Ls, K, comb, coll_f, rng, lift=hs.get('lift', 0.12), gravity=hs.get('gravity', 0.6),
                 curl=hs.get('curl', 0.0), stiff=0.72, margin=hs.get('volume', 0.012), jitter=0.08)
        nc = int(hs.get('count', 90000) * hs['density'] * hair_scale)
        croots, cn = sample_surface(Vu, Fu, nc, rng, mask, center)
        C = children_from_guides(G, groots, croots, rng, clump=0.25, spread_noise=0.0035)
        C[:, 1:] = coll_f.push(C[:, 1:].reshape(-1, 3), 0.004).reshape(nc, K - 1, 3)
        rad = np.tile(np.linspace(hs.get('r0', 0.00075), 0.0004, K), (nc, 1))
        curves_obj(name + '_hair', C, rad, hm, parent=head)
        return

    if style == 'locs':
        # short base fur on scalp + thick locs falling back over shoulders
        front_z = hs.get('front_z', s['H'] * 0.6)
        mask = lambda C: hairline(C, front_z, s['eye_z'] + 0.01, zm - 0.01)
        base_r, base_n = sample_surface(Vu, Fu, 40000, rng, mask, center)

        def comb_back(P, n):
            v = np.stack([np.zeros(len(P)), np.ones(len(P)) * 0.7, -np.ones(len(P)) * 0.4], 1)
            return v / np.linalg.norm(v, axis=1, keepdims=True)

        B = grow(base_r, base_n, 0.012, 4, comb_back, coll, rng, lift=0.3, stiff=0.5, margin=0.001)
        curves_obj(name + '_hairbase', B, np.tile(np.linspace(0.0006, 0.0003, 4), (len(B), 1)), hm, parent=head)
        nl = hs.get('locs', 170)
        lroots, ln = sample_surface(Vu, Fu, nl, rng, mask, center)

        def comb(P, n):
            x, z = P[:, 0], P[:, 2]
            top = np.clip((z - s['eye_z']) / (H - s['eye_z']), 0, 1)
            v = np.stack([np.tanh(x / 0.02) * (0.5 + 0.4 * top), np.full(len(P), 0.6) * (0.4 + top),
                          -0.3 - 1.0 * (1 - top)], 1)
            return v / np.linalg.norm(v, axis=1, keepdims=True)

        K = 22
        G = grow(lroots, ln, hs.get('length', 0.26) * rng.uniform(0.8, 1.1, nl), K, comb, coll_f, rng, lift=0.3,
                 gravity=0.7, curl=0.06, stiff=0.75, margin=0.011, jitter=0.08)
        rad = np.tile(np.linspace(hs.get('r0', 0.0068), 0.0055, K), (nl, 1))
        loc_m = mat_fleece(name + '_locmat', hex_lin(hs['hex']), sheen=0.35, rough=0.9, bump=0.5, fiber_scale=300)
        curves_obj(name + '_locs', G, rad, loc_m, parent=head)
        return
