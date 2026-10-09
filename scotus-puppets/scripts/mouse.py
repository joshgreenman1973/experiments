# A tiny felt mouse for the wide shot (Easter egg): builds one pose of the mouse in bpy 5.2.
# Same materials as the puppets (fleece with sheen, hair-BSDF fuzz fibres, hair-BSDF whiskers), built procedurally.
#
# Frame: the mouse faces -Y at rest (like the puppets), +Z up, metres, origin on the ground between the hind feet.
# Every part is plain numpy vertices in that frame, parented to one root empty, so fuzz can be grown straight from the
# meshes and a pose is just a different set of numbers (head turn, ear angles, paw targets, eyes, mouth, tail).
#   build_mouse(pose, loc, cam_loc, key_loc) -> dict(root, objs)
# `pose['view']` is relative to the camera: 0 faces the camera, positive turns the mouse toward image right
# (toward the bench, from the left counsel table).
import math
import numpy as np
import bpy
from mathutils import Vector
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree
import puppet as P

POSES = ('listen', 'look', 'laugh', 'groom')
SIZE = 0.86            # overall scale of the design below (design is ~0.23 m with ears; this makes ~0.2 m)

FUR = '#6e5c4e'        # gray-brown fleece
BELLY = '#b9a894'
EAR_IN = '#ee7f93'
NOSE = '#e4788c'
PAW = '#c8958f'
TAIL = '#d9a29d'

# ----------------------------------------------------------------------------- poses
# head: yaw/pitch/roll in degrees relative to the body (pitch + is nose up, roll + drops the +x side)
# ears: yaw swings the ear's front face outward, tilt + raises it / - lays it back, splay rolls its top outward
# arm: paw target ('body'|'head', xyz) for the +x arm (mirrored for -x), plus elbow out/down offsets
CLASP = dict(frame='body', paw=(0.013, -0.062, 0.074), out=0.016, down=0.010)
BELLY_ARMS = dict(frame='body', paw=(0.026, -0.066, 0.050), out=0.020, down=0.006)
WASH = dict(frame='head', paw=(0.013, -0.058, -0.016), out=0.012, down=0.012)
POSE = {
    'listen': dict(view=52, lean=2, head=dict(yaw=22, pitch=27, roll=-8, dz=0.0),
                   ears=dict(yaw=10, tilt=2, splay=9), eyes='open', mouth=0.0, arm=CLASP, tail_lift=0.4),
    'look':   dict(view=52, lean=2, head=dict(yaw=-52, pitch=6, roll=7, dz=0.0),
                   ears=dict(yaw=22, tilt=6, splay=12), eyes='open', mouth=0.0, arm=CLASP, tail_lift=0.4),
    'laugh':  dict(view=20, lean=8, head=dict(yaw=-10, pitch=34, roll=6, dz=0.004),
                   ears=dict(yaw=50, tilt=-14, splay=16), eyes='happy', mouth=1.0, arm=BELLY_ARMS, tail_lift=1.0),
    'groom':  dict(view=24, lean=-5, head=dict(yaw=-4, pitch=-8, roll=0, dz=-0.003),
                   ears=dict(yaw=32, tilt=-4, splay=10), eyes='content', mouth=0.0, arm=WASH, tail_lift=0.2),
}


# ----------------------------------------------------------------------------- small geometry kit
def Rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def frame_from(ey, up=(0, 0, 1.0)):
    """Rotation whose y axis is ey (x = ey x z-ish, z = up-ish)."""
    ey = unit(ey)
    ex = np.cross(ey, up)
    if np.linalg.norm(ex) < 1e-6:
        ex = np.cross(ey, (1.0, 0, 0))
    ex = unit(ex)
    ez = np.cross(ex, ey)
    return np.stack([ex, ey, ez], 1)


def ellipsoid(c, r, R=None, nu=36, nv=20):
    rings = [(r[2] * math.cos(math.pi * k / nv), r[0] * math.sin(math.pi * k / nv),
              r[1] * math.sin(math.pi * k / nv), 0.0, 0) for k in range(nv + 1)]
    V, F, _ = P.loft(rings, nu, 2.0)
    if R is not None:
        V = V @ np.asarray(R).T
    return V + np.asarray(c, float), F


def swept(pts, radii, nseg=20, n=48, ends=0.5):
    """Smooth tube along pts (PCHIP) with PCHIP radii and rounded ends."""
    pts = np.asarray(pts, float); radii = np.asarray(radii, float)
    t = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    tt = np.linspace(0, t[-1], n)
    Pp = np.stack([PchipInterpolator(t, pts[:, i])(tt) for i in range(3)], 1)
    R = PchipInterpolator(t, radii)(tt)
    T = np.gradient(Pp, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.cross(T[0], (0, 0, 1.0) if abs(T[0][2]) < 0.9 else (1.0, 0, 0))
    ref /= np.linalg.norm(ref)
    phi = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    V, F = [], []
    for i in range(n):
        ref = ref - (ref @ T[i]) * T[i]; ref /= np.linalg.norm(ref)
        b = np.cross(T[i], ref)
        V.extend(Pp[i] + R[i] * (np.cos(phi)[:, None] * ref + np.sin(phi)[:, None] * b))
    for i in range(n - 1):
        for j in range(nseg):
            a0, a1 = i * nseg + j, i * nseg + (j + 1) % nseg
            F.append((a0, a1, a1 + nseg, a0 + nseg))
    c0 = len(V); V.append(Pp[0] - T[0] * R[0] * ends)
    c1 = len(V); V.append(Pp[-1] + T[-1] * R[-1] * ends)
    last = (n - 1) * nseg
    for j in range(nseg):
        F.append((c0, (j + 1) % nseg, j))
        F.append((c1, last + j, last + (j + 1) % nseg))
    return np.array(V), F, Pp


def orient(V, F, ref_fn):
    """Flip faces whose normal points toward the reference (inside) so every part has outward normals."""
    out = []
    for f in F:
        p = V[list(f)]
        c = p.mean(0)
        n = np.cross(p[1] - p[0], p[2] - p[0]) if len(f) >= 3 else None
        if n is not None and np.dot(n, c - ref_fn(c)) < 0:
            f = tuple(f[::-1])
        out.append(tuple(int(i) for i in f))
    return out


def blob_ref(V):
    cen = V.mean(0)
    return lambda c: cen


def path_ref(Pp):
    tree = cKDTree(Pp)
    return lambda c: Pp[tree.query(c)[1]]


# ----------------------------------------------------------------------------- head: a lofted egg with a short muzzle
_HY = np.array([-0.0625, -0.0555, -0.0465, -0.0365, -0.0245, -0.0105, 0.004, 0.019, 0.031, 0.039, 0.0440])
_HR = np.array([0.0040, 0.0125, 0.0215, 0.0295, 0.0372, 0.0420, 0.0437, 0.0415, 0.0345, 0.0225, 0.0070])
_Rfun = PchipInterpolator(_HY, _HR)
_dRfun = _Rfun.derivative()
HEAD_SX, HEAD_SZ = 1.08, 0.97     # a little wider than tall: cheeks


def head_zc(y):
    return -0.0085 * np.clip(-y / 0.062, 0, 1) ** 1.5      # muzzle droops a touch


def head_surf(y, phi, inset=0.0):
    """Point on the head surface at axial position y and angle phi (0 = up, + toward +x), and its outward normal."""
    r = float(_Rfun(y)) - inset
    p = np.array([HEAD_SX * r * math.sin(phi), y, head_zc(y) + HEAD_SZ * r * math.cos(phi)])
    n = unit([math.sin(phi) / HEAD_SX, -float(_dRfun(y)) * 1.0, math.cos(phi) / HEAD_SZ])
    return p, n


MOUTH_HOLE = dict(y0=-0.0385, a=0.0150, b=1.05)    # elliptical window in (y, angle-from-up) on the muzzle underside


def head_mesh(nseg=64, ny=84, hole=False):
    ys = np.linspace(_HY[0], _HY[-1], ny)
    V = [(0.0, _HY[0] - 0.003, head_zc(_HY[0]))]
    for y in ys[1:-1]:
        for k in range(nseg):
            phi = 2 * math.pi * k / nseg
            V.append(tuple(head_surf(y, phi)[0]))
    V.append((0.0, _HY[-1] + 0.004, head_zc(_HY[-1])))
    F = []
    rings = ny - 2

    def cut(i, k):
        if not hole:
            return False
        y = 0.5 * (ys[1 + i] + ys[min(2 + i, ny - 1)])
        dphi = ((k + 0.5) / nseg * 2 * math.pi) - math.pi
        return ((y - MOUTH_HOLE['y0']) / MOUTH_HOLE['a']) ** 2 + (dphi / MOUTH_HOLE['b']) ** 2 < 1.0

    for k in range(nseg):
        F.append((0, 1 + (k + 1) % nseg, 1 + k))
    for i in range(rings - 1):
        for k in range(nseg):
            if cut(i, k):
                continue
            a, b = 1 + i * nseg + k, 1 + i * nseg + (k + 1) % nseg
            F.append((a, b, b + nseg, a + nseg))
    last = 1 + (rings - 1) * nseg
    for k in range(nseg):
        F.append((last + k, last + (k + 1) % nseg, len(V) - 1))
    return np.array(V), F


BODY_RINGS = [(0.0, 0.0, 0.0, 0.0), (0.004, 0.030, 0.036, 0.006), (0.014, 0.050, 0.056, 0.008),
              (0.032, 0.058, 0.062, 0.008), (0.055, 0.056, 0.058, 0.006), (0.075, 0.046, 0.048, 0.001),
              (0.095, 0.035, 0.036, -0.004), (0.110, 0.026, 0.026, -0.008), (0.120, 0.014, 0.014, -0.009),
              (0.126, 0.0, 0.0, -0.009)]
HEAD0 = np.array([0.0, -0.012, 0.139])     # head centre at rest
NECK = np.array([0.0, -0.004, 0.108])      # head pivot
HIP = np.array([0.0, 0.010, 0.030])        # pivot for leaning the whole upper body


# ----------------------------------------------------------------------------- the build
def mat_emit(name, strength=6.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (1, 1, 1, 1); e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m


def build_mouse(pose, loc, cam_loc, key_loc, size=SIZE, seed=11, fuzz_density=1.3e6):
    """Build `pose` standing at world `loc` (feet point), turned relative to the camera. Returns dict(root, objs)."""
    p = POSE[pose]
    rng = np.random.default_rng(seed)
    loc = Vector(loc)
    d = Vector(cam_loc) - loc
    yaw = math.atan2(d.x, -d.y) + math.radians(p['view'])
    root = bpy.data.objects.new('mouse_' + pose, None)
    bpy.context.collection.objects.link(root)
    root.location = loc; root.rotation_euler = (0, 0, yaw)
    Rw = Rz(yaw)

    # materials (the puppets' own recipes), shared between poses
    def M(name, make):
        return bpy.data.materials.get(name) or make()

    fur = M('mouse_fur', lambda: P.mat_fleece('mouse_fur', P.hex_lin(FUR), sheen=0.7, bump=0.55, fiber_scale=520.0, tint_var=0.10))
    belly = M('mouse_belly', lambda: P.mat_fleece('mouse_belly', P.hex_lin(BELLY), sheen=0.7, bump=0.5, fiber_scale=520.0, tint_var=0.08))
    ear_in = M('mouse_ear_in', lambda: P.mat_fleece('mouse_ear_in', P.hex_lin(EAR_IN), sheen=0.8, bump=0.4, fiber_scale=520.0))
    nose_m = M('mouse_nose', lambda: P.mat_fleece('mouse_nose', P.hex_lin(NOSE), sheen=0.5, rough=0.55, bump=0.3))
    paw_m = M('mouse_paw', lambda: P.mat_fleece('mouse_paw', P.hex_lin(PAW), sheen=0.7, bump=0.4, fiber_scale=520.0))
    tail_m = M('mouse_tail', lambda: P.mat_fleece('mouse_tail', P.hex_lin(TAIL), sheen=0.5, rough=0.7, bump=0.25, fiber_scale=300.0))
    bead = M('mouse_bead', lambda: P.mat_plain('mouse_bead', (0.003, 0.003, 0.003, 1), rough=0.1, coat=1.0))
    glint = M('mouse_glint', lambda: mat_emit('mouse_glint'))
    mouth_m = M('mouse_mouth', lambda: P.mat_fleece('mouse_mouth', P.hex_lin('#2b0709'), sheen=0.2))
    tongue_m = M('mouse_tongue', lambda: P.mat_fleece('mouse_tongue', P.hex_lin('#c9505f'), sheen=0.5))
    fz_fur = M('mouse_fuzz', lambda: P.mat_hair('mouse_fuzz', P.hex_lin(FUR, 1.05), rough=0.65, rand=0.1))
    fz_belly = M('mouse_fuzz_belly', lambda: P.mat_hair('mouse_fuzz_belly', P.hex_lin(BELLY, 1.0), rough=0.65, rand=0.1))
    fz_ear = M('mouse_fuzz_ear', lambda: P.mat_hair('mouse_fuzz_ear', P.hex_lin(EAR_IN, 1.2), rough=0.7, rand=0.1))
    whisk = M('mouse_whisker', lambda: P.mat_hair('mouse_whisker', P.hex_lin('#efe6da'), rough=0.3, rand=0.05))

    parts = []     # dict(name, V, F, mat, ref, fz=(fuzz mat, weight))

    def part(name, V, F, mat, ref=None, fz=None):
        V = np.asarray(V, float)
        parts.append(dict(name=name, V=V, F=F, mat=mat, ref=ref or blob_ref(V), fz=fz))
        return parts[-1]

    # --- transforms: head about the neck, then everything upper leans about the hip
    hd = p['head']
    Rh = Rz(math.radians(hd['yaw'])) @ Rx(-math.radians(hd['pitch'])) @ Ry(math.radians(hd['roll']))
    Rl = Rx(-math.radians(p['lean']))

    def lean(V):
        return (np.asarray(V, float) - HIP) @ Rl.T + HIP

    def H(V):       # head-local (centre at 0) -> mouse frame
        V = np.asarray(V, float)
        W = (V + HEAD0 + np.array([0, 0, hd['dz']]) - NECK) @ Rh.T + NECK
        return lean(W)

    # --- body, haunches, feet, belly bib
    from_rings = [(z, rx, ry, cy, 0) for z, rx, ry, cy in BODY_RINGS]
    V, F, _ = P.loft(from_rings, 44, 2.3)
    part('body', lean(V), F, fur, fz=(fz_fur, 1.0))
    for sx in (-1, 1):
        V, F = ellipsoid((sx * 0.041, 0.012, 0.030), (0.022, 0.038, 0.030), nu=32, nv=18)
        part(f'haunch{sx}', V, F, fur, fz=(fz_fur, 0.6))
        V, F = ellipsoid((sx * 0.033, -0.043, 0.0072), (0.0098, 0.021, 0.0072), Rz(-sx * 0.20), nu=24, nv=14)
        part(f'foot{sx}', V, F, paw_m)
    V, F = ellipsoid((0, -0.033, 0.054), (0.030, 0.024, 0.040), nu=32, nv=18)
    part('bib', lean(V), F, belly, fz=(fz_belly, 0.9))

    # --- head
    V, F = head_mesh(hole=p['mouth'] > 0.01)
    V = H(V)
    part('head', V, F, fur, fz=(fz_fur, 1.2))
    pn, _ = head_surf(-0.0625, 0)
    V, F = ellipsoid(pn + np.array([0, 0.0035, 0.0028]), (0.0108, 0.0098, 0.0088), nu=24, nv=14)
    part('nose', H(V), F, nose_m)

    # ears: thin round discs, felt outside / pink inside
    er = 0.0345
    for sx in (-1, 1):
        ep = p['ears']
        Re = Rz(sx * math.radians(ep['yaw'])) @ Rx(-math.radians(ep['tilt'])) @ Ry(sx * math.radians(ep['splay']))
        base = np.array([sx * 0.034, 0.016, 0.031])
        cen = base + Re @ np.array([sx * 0.002, 0, 0.62 * er])
        V, F = ellipsoid(cen, (er, 0.0040, er * 1.03), Re, nu=40, nv=22)
        part(f'ear{sx}', H(V), F, fur, fz=(fz_fur, 0.8))
        V, F = ellipsoid(cen + Re @ np.array([0, -0.0016, -0.002]), (er * 0.74, 0.0036, er * 0.76), Re, nu=36, nv=18)
        part(f'ear_in{sx}', H(V), F, ear_in, fz=(fz_ear, 0.6))

    # eyes: black beads (open) or short arcs (happy ^ or content u)
    r_eye = 0.0104
    Hw = unit(unit(np.array(key_loc) - np.array(loc)) + unit(np.array(cam_loc) - np.array(loc)))
    Hl = Rw.T @ Hw     # half-vector in the mouse frame: where a glossy bead shows its highlight
    glints = []
    for sx in (-1, 1):
        phi = sx * math.radians(50)
        ys = -0.0335
        ps, ns = head_surf(ys, phi)
        if p['eyes'] == 'open':
            c = ps - ns * 0.40 * r_eye
            V, F = ellipsoid(c, (r_eye,) * 3, nu=28, nv=16)
            part(f'eye{sx}', H(V), F, bead)
            hn = unit((Rl @ Rh).T @ Hl)       # half-vector in head-local axes (head may be rotated and leaned)
            gp = c + hn * r_eye * 0.93
            V, F = ellipsoid(gp, (0.0019,) * 3, nu=10, nv=6)
            glints.append(('glint%d' % sx, H(V), F))
        else:
            up = p['eyes'] == 'happy'
            pts = []
            for u in np.linspace(-1, 1, 9):
                q = ps + np.array([u * 0.0148, 0, (0.0075 * (1 - u * u)) * (1 if up else -1)])
                ph = math.atan2(q[0] / HEAD_SX, (q[2] - head_zc(q[1])) / HEAD_SZ)
                pq, nq = head_surf(q[1], ph)
                pts.append(pq + nq * 0.0026)
            V2, F2, Pp = swept(pts, [0.0028, 0.0031, 0.0033, 0.0034, 0.0034, 0.0034, 0.0033, 0.0031, 0.0028], nseg=10, n=24, ends=0.9)
            part(f'eye{sx}', H(V2), F2, bead, ref=path_ref(H(Pp)))

    # mouth: a window cut in the muzzle underside, a dark cavity behind it and a lower jaw hinged open with a tongue
    if p['mouth'] > 0.01:
        th = math.radians(46.0 * p['mouth'])
        yc = MOUTH_HOLE['y0']
        V, F = ellipsoid((0, yc - 0.001, head_zc(yc) - 0.0112), (0.0215, 0.0200, 0.0128), nu=32, nv=16)
        part('cavity', H(V), F, mouth_m)
        J = np.array([0.0, -0.003, -0.0305])
        Rj = Rx(th)
        for nm, c0, rr, mat, fzz in (('jaw', (0, -0.031, -0.0385), (0.0215, 0.0215, 0.0092), fur, (fz_fur, 0.8)),
                                     ('tongue', (0, -0.029, -0.0312), (0.0120, 0.0150, 0.0050), tongue_m, None)):
            cj = J + Rj @ (np.array(c0) - J)
            V, F = ellipsoid(cj, rr, Rj, nu=32, nv=16)
            part(nm, H(V), F, mat, fz=fzz)

    # whiskers: a fan of fine hair strands at each cheek
    wr, wrad, wn = [], [], 0
    for sx in (-1, 1):
        for el, az in ((17, 52), (-1, 66), (-19, 58)):
            root_pt = np.array([sx * 0.0135, -0.0475, head_zc(-0.0475) - 0.0060 + 0.0005 * el / 10.0])
            a, e = math.radians(az), math.radians(el)
            dvec = unit([sx * math.sin(a), -math.cos(a) * 0.9, math.tan(e) * 0.55])
            pts = []
            for k in range(6):
                s = k / 5.0
                pt = root_pt + dvec * (0.056 * s)
                pt = pt + np.array([0, 0, -0.012 * s * s])      # droop
                pts.append(pt)
            wr.append(H(np.array(pts))); wrad.append([0.00085, 0.00075, 0.00065, 0.00052, 0.00040, 0.00028])
    whisker_pts = np.array(wr); whisker_rad = np.array(wrad)

    # arms and paws
    arm = p['arm']
    for sx in (-1, 1):
        sh = lean(np.array([sx * 0.034, -0.012, 0.088]))
        tx, ty, tz = arm['paw']
        paw = np.array([sx * tx, ty, tz])
        paw = H(paw) if arm['frame'] == 'head' else lean(paw)
        paw = np.asarray(paw, float)
        el = (sh + paw) / 2 + np.array([sx * arm['out'], 0.004, -arm['down']])
        V, F, Pp = swept([sh, el, paw], [0.0130, 0.0102, 0.0090], nseg=18, n=30, ends=0.6)
        part(f'arm{sx}', V, F, fur, ref=path_ref(Pp), fz=(fz_fur, 0.5))
        f = unit(paw - el)
        R = frame_from(f)
        V, F = ellipsoid(paw + f * 0.0025, (0.0098, 0.0118, 0.0086), R, nu=24, nv=14)
        part(f'paw{sx}', V, F, paw_m)
        side = unit(np.cross(f, (0, 0, 1.0)))
        for k, o in enumerate((-1, 0, 1)):
            fp = paw + f * 0.0125 + side * (o * 0.0052) + np.array([0, 0, -0.0012 * abs(o)])
            V, F = ellipsoid(fp, (0.0033, 0.0046, 0.0031), R, nu=14, nv=8)
            part(f'fing{sx}{k}', V, F, paw_m)

    # tail: a thin pink S-curve out behind, on the side facing the camera
    c_local = Rw.T @ unit(np.array(cam_loc) - np.array(loc))
    s = -1.0 if c_local[0] < 0 else 1.0
    lf = p['tail_lift']
    tp = [(0, 0.050, 0.012), (s * 0.016, 0.082, 0.007), (s * 0.052, 0.103, 0.0045), (s * 0.092, 0.098, 0.011),
          (s * 0.118, 0.070, 0.026 + 0.012 * lf), (s * 0.120, 0.038, 0.050 + 0.040 * lf), (s * 0.100, 0.016, 0.074 + 0.050 * lf)]
    V, F, Pp = swept(tp, [0.0060, 0.0052, 0.0043, 0.0035, 0.0028, 0.0021, 0.0013], nseg=14, n=60, ends=0.7)
    part('tail', V, F, tail_m, ref=path_ref(Pp))

    # ---- emit objects
    k = size
    objs = []
    for pt in parts:
        V = pt['V'] * k
        F = orient(V, pt['F'], (lambda ref: (lambda c: ref(c / k) * k))(pt['ref']))
        ob = P.mesh_obj(f"{pose}_{pt['name']}", V, F, [0] * len(F), [pt['mat']], parent=root)
        objs.append(ob)
        if pt['fz'] is not None:
            m, wgt = pt['fz']
            T, a, b, c, area = P.tri_data(V, F)
            n = max(40, int(fuzz_density * wgt * area.sum()))
            R_, N_ = P.sample_surface(V, F, n, rng)
            cen = V.mean(0)
            if pt['name'].startswith('arm') or pt['name'] == 'tail':
                ref = (lambda rr: (lambda c: rr(c / k) * k))(pt['ref'])
                outv = R_ - np.array([ref(q) for q in R_])
            else:
                outv = R_ - cen
            N_ = np.where((np.einsum('ij,ij->i', N_, outv) < 0)[:, None], -N_, N_)
            dd = N_ + rng.normal(0, 0.55, N_.shape)
            dd /= np.linalg.norm(dd, axis=1, keepdims=True)
            Lf = 0.0036 * k * rng.uniform(0.75, 1.25, n)
            Pz = R_[:, None, :] + dd[:, None, :] * (np.array([0.0, 0.5, 1.0])[None, :, None] * Lf[:, None, None])
            rad = np.tile(np.array([0.00036, 0.00025, 0.0001]), (n, 1))
            objs.append(P.curves_obj(f"{pose}_{pt['name']}_fuzz", Pz, rad, m, parent=root))
    for nm, V, F in glints:
        V = V * k
        objs.append(P.mesh_obj(f'{pose}_{nm}', V, F, [0] * len(F), [glint], parent=root))
    objs.append(P.curves_obj(f'{pose}_whiskers', whisker_pts * k, whisker_rad * k, whisk, parent=root))
    return dict(root=root, objs=objs, yaw=yaw, size=size)


def remove_mouse(m):
    """Delete a mouse built by build_mouse (objects and their data)."""
    for ob in m['objs'] + [m['root']]:
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif hasattr(bpy.data, 'hair_curves') and isinstance(data, bpy.types.Curves):
                bpy.data.hair_curves.remove(data)
