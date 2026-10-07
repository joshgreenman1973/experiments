"""Shared grid definition: a 3 m raster in UTM zone 18N covering the five boroughs."""
import numpy as np

CRS = "EPSG:32618"
RES = 3.0
X0, X1 = 562_800.0, 610_200.0
Y0, Y1 = 4_482_900.0, 4_530_300.0
W = int(round((X1 - X0) / RES))  # columns
H = int(round((Y1 - Y0) / RES))  # rows; row 0 is the north edge

EYE = 1.6  # metres, eye height of a person standing on the ground


def transform():
    from affine import Affine
    return Affine(RES, 0, X0, 0, -RES, Y1)


def to_rc(x, y):
    """UTM metres -> fractional (row, col) with cell centres at integer + 0.5."""
    return (Y1 - np.asarray(y)) / RES, (np.asarray(x) - X0) / RES


def to_xy(r, c):
    return X0 + np.asarray(c) * RES, Y1 - np.asarray(r) * RES
