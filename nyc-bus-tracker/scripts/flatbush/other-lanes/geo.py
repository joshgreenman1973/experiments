"""Small geometry helpers: local metric projection, densify, direction-aware corridor overlap."""
import math
import numpy as np

R = 6371000.0
LAT0 = math.radians(40.75)
KX = R * math.cos(LAT0) * math.pi / 180.0
KY = R * math.pi / 180.0
COMPASS = {'NB': (0, 1), 'SB': (0, -1), 'EB': (1, 0), 'WB': (-1, 0)}


def to_xy(lat, lon):
    return np.column_stack([np.asarray(lon, float) * KX, np.asarray(lat, float) * KY])


def to_ll(xy):
    xy = np.asarray(xy)
    return xy[:, 1] / KY, xy[:, 0] / KX


def cumlen(P):
    d = np.hypot(*np.diff(P, axis=0).T)
    return np.concatenate([[0.0], np.cumsum(d)])


def densify(P, step=10.0):
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        L = math.hypot(*(b - a))
        n = max(1, int(math.ceil(L / step)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return np.array(out)


def project_point(P, C, p):
    """All projections of point p onto polyline P (cum C). Returns arrays (dist, along)."""
    A, B = P[:-1], P[1:]
    AB = B - A
    L2 = (AB ** 2).sum(1)
    L2[L2 == 0] = 1e-9
    t = np.clip(((p - A) * AB).sum(1) / L2, 0, 1)
    Q = A + AB * t[:, None]
    d = np.hypot(*(Q - p).T)
    along = C[:-1] + t * np.sqrt(L2)
    return d, along


def candidates(P, C, p, tol):
    """Local-minimum projections within tol metres (one per contiguous run)."""
    d, along = project_point(P, C, p)
    ok = d < tol
    out = []
    i = 0
    n = len(d)
    while i < n:
        if ok[i]:
            j = i
            while j + 1 < n and ok[j + 1]:
                j += 1
            k = i + int(np.argmin(d[i:j + 1]))
            out.append((float(along[k]), float(d[k])))
            i = j + 1
        else:
            i += 1
    return out


def slice_line(P, C, a, b):
    """Sub-polyline of P between along-distances a<b."""
    def at(s):
        i = int(np.searchsorted(C, s, side='right') - 1)
        i = min(max(i, 0), len(P) - 2)
        seg = C[i + 1] - C[i]
        t = 0 if seg == 0 else (s - C[i]) / seg
        return P[i] + (P[i + 1] - P[i]) * t, i
    pa, ia = at(a)
    pb, ib = at(b)
    pts = [pa] + [P[k] for k in range(ia + 1, ib + 1)] + [pb]
    return np.array(pts)


class Corridor:
    """Set of directed line features. Each feature: (xy array, direction in NB/SB/EB/WB or '' for both)."""

    def __init__(self, feats, buf=60.0, cell=100.0, oriented=False):
        """oriented=True: each feature's own drawing order is its travel direction (used for coverage checks)."""
        self.oriented = oriented
        self.buf = buf
        self.cell = cell
        A, B, D = [], [], []
        for P, d in feats:
            for a, b in zip(P[:-1], P[1:]):
                if math.hypot(*(b - a)) < 0.01:
                    continue
                A.append(a); B.append(b); D.append(d)
        self.A = np.array(A); self.B = np.array(B); self.D = D
        self.grid = {}
        for i, (a, b) in enumerate(zip(self.A, self.B)):
            x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
            for gx in range(int((x0 - buf) // cell), int((x1 + buf) // cell) + 1):
                for gy in range(int((y0 - buf) // cell), int((y1 + buf) // cell) + 1):
                    self.grid.setdefault((gx, gy), []).append(i)

    def covers(self, m, v):
        """Is midpoint m (travelling along unit vector v) within buf of a parallel, same-direction feature?"""
        key = (int(m[0] // self.cell), int(m[1] // self.cell))
        for i in self.grid.get(key, ()):
            a, b = self.A[i], self.B[i]
            ab = b - a
            L = math.hypot(*ab)
            u = ab / L
            t = min(max(np.dot(m - a, u), 0), L)
            q = a + u * t
            if math.hypot(*(m - q)) > self.buf:
                continue
            if abs(np.dot(u, v)) < 0.7:          # not running along this street
                continue
            if self.oriented and np.dot(u, v) <= 0:
                continue
            d = self.D[i]
            if d and np.dot(v, COMPASS[d]) <= 0:  # wrong way for a one-direction lane
                continue
            return True
        return False

    def overlap(self, P, step=10.0):
        """Share of polyline P's length that runs inside the corridor, direction-aware."""
        Q = densify(P, step)
        tot = inside = 0.0
        for a, b in zip(Q[:-1], Q[1:]):
            L = math.hypot(*(b - a))
            if L == 0:
                continue
            tot += L
            if self.covers((a + b) / 2, (b - a) / L):
                inside += L
        return (inside / tot if tot else 0.0), tot
