"""Give piers to the borough people think they're in.

NYC Planning's boundaries follow the legal line, which in the East River runs along the old
Brooklyn and Queens shorelines, so piers built out past it (Brooklyn Bridge Park, for one) are in
Manhattan on paper. Any piece of Manhattan land that touches Brooklyn or Queens land is reassigned
to that borough. Marble Hill touches the Bronx and stays in Manhattan.
Usage: python fix_boro.py GRID_DIR
"""
import sys, numpy as np
from scipy import ndimage

G = sys.argv[1]
boro = np.load(f"{G}/boro.npy")
lab, n = ndimage.label(boro == 1, structure=np.ones((3, 3), bool))
sizes = np.bincount(lab.ravel())
main = int(np.argmax(sizes[1:]) + 1)                       # Manhattan island itself
touch = {}
for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
    a = lab[max(0, -dr):lab.shape[0] - max(0, dr), max(0, -dc):lab.shape[1] - max(0, dc)]
    b = boro[max(0, dr):, max(0, dc):][: a.shape[0], : a.shape[1]] if dc >= 0 else boro[dr:, :dc][: a.shape[0], : a.shape[1]]
    for la, bb in ((a, b),):
        m = (la > 0) & ((bb == 3) | (bb == 4))
        for l, k in zip(la[m], bb[m]):
            touch.setdefault(int(l), {}).setdefault(int(k), 0)
            touch[int(l)][int(k)] += 1
    # and the reverse direction
    a2 = boro[max(0, -dr):boro.shape[0] - max(0, dr), max(0, -dc):boro.shape[1] - max(0, dc)]
    b2 = lab[max(0, dr):, max(0, dc):][: a2.shape[0], : a2.shape[1]] if dc >= 0 else lab[dr:, :dc][: a2.shape[0], : a2.shape[1]]
    m = (b2 > 0) & ((a2 == 3) | (a2 == 4))
    for l, k in zip(b2[m], a2[m]):
        touch.setdefault(int(l), {}).setdefault(int(k), 0)
        touch[int(l)][int(k)] += 1
moved = 0
for l, ks in touch.items():
    if l == main:
        continue
    k = max(ks, key=ks.get)
    m = lab == l
    boro[m] = k
    moved += int(m.sum())
    print(f"component {l}: {int(m.sum())} cells -> borough {k}")
np.save(f"{G}/boro.npy", boro)
print("reassigned cells", moved, "km2", moved * 9 / 1e6)
