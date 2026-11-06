#!/usr/bin/env python3
"""Build data for "Where you can sit down" (nyc-where-to-sit), version 2.

Run:  python3 build_data.py          (uses raw/ files; add --fetch to re-download)

Inputs (NYC Open Data, all fetched with the Socrata API):
  esmy-s8q5  DOT Seating Locations (CityBench benches and leaning bars)
  rvih-nhyn  DCP Privately Owned Public Spaces (POPS)
  5dck-9m6g  DOT Pedestrian Plazas
  t4f2-8md7  DOT Bus Stop Shelters
  enfh-gkve  NYC Parks Properties (polygons)
  raw/nta2020_clipped.geojson  2020 Neighborhood Tabulation Areas, shoreline-clipped,
             with 2020 Census population (carried over from the v1 build)

Outputs (data/):
  walk.png        one RGBA raster, ~60 m cells, Web Mercator-regular rows.
                  R = minutes x10 to the nearest street seat (DOT bench, POPS with
                      required seating or DOT plaza; leaning bars excluded)
                  G = minutes x10 to the nearest backed DOT bench
                  B = minutes x10 to the nearest seat of any kind we can place
                      (street seats + bus shelters + edge of a park likely to have benches)
                  A = 255 on land, 0 on water. Values cap at 254 (25.4 minutes).
  walk_meta.json  raster bounds and encoding
  seats.json      points for the map and finder, plus all summary figures
  ntas.geojson    simplified NTA polygons with per-neighborhood figures
  parks.geojson   simplified park polygons used in the "any seat" layer
  *.csv           flat downloads
"""
import json
import math
import time
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import shapely
from PIL import Image
from scipy.spatial import cKDTree
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "data")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

SOURCES = {
    "seating_esmy.json": "https://data.cityofnewyork.us/resource/esmy-s8q5.json?$limit=50000",
    "pops_rvih.json": "https://data.cityofnewyork.us/resource/rvih-nhyn.json?$limit=50000",
    "plazas_5dck.json": "https://data.cityofnewyork.us/resource/5dck-9m6g.json?$limit=50000",
    "shelters_t4f2.json": "https://data.cityofnewyork.us/resource/t4f2-8md7.json?$limit=50000",
    "parks_enfh.json": "https://data.cityofnewyork.us/resource/enfh-gkve.json?$limit=50000"
                       "&$select=gispropnum,signname,typecategory,acres,borough,multipolygon",
}
FETCHED = "2026-11-06"

# Walking model: straight-line distance x 1.25 (street-grid detour) at 3 mph = 25 min per straight-line mile.
ROUTE = 1.25
MIN_PER_MILE = 20.0
MIN_PER_M = ROUTE * MIN_PER_MILE / 1609.344

# Park types where benches are near-certain. Gardens (often locked), nature areas, strips,
# parkways, undeveloped land, cemeteries, lots and operations sites are left out.
PARK_TYPES_WITH_SEATS = {
    "Neighborhood Park", "Playground", "Jointly Operated Playground", "Community Park",
    "Flagship Park", "Triangle/Plaza", "Mall", "Waterfront Facility", "Historic House Park",
    "Recreational Field/Courts",
}

LAT0 = 40.70
KX = 111320.0 * math.cos(math.radians(LAT0))
KY = 110540.0


def fetch():
    for fn, url in SOURCES.items():
        print("fetching", fn)
        urllib.request.urlretrieve(url, os.path.join(RAW, fn))


def load(fn):
    with open(os.path.join(RAW, fn)) as f:
        return json.load(f)


def xy(lon, lat):
    return (np.asarray(lon) + 74.0) * KX, (np.asarray(lat) - LAT0) * KY


def merc_y(lat):
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def inv_merc_y(y):
    return np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)


def rgeo(g, tol):
    """Simplify and round a geometry to 5 decimals for the browser."""
    gj = json.loads(shapely.to_geojson(g.simplify(tol, preserve_topology=True)))

    def rc(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 5), round(c[1], 5)]
        return [rc(x) for x in c]
    gj["coordinates"] = rc(gj["coordinates"])
    return gj


def classify(sub):
    s = (sub or "").strip().upper()
    if s in ("BACKED 1.0", "BACKED 2.0", "WORLDS FAIR"):
        return "backed"
    if s in ("BACKLESS 1.0", "BACKLESS 2.0"):
        return "backless"
    if s == "LEANING BAR":
        return "bar"
    if s == "UNKNOWN BENCH":
        return "unknown"
    return "unrecorded"


def main():
    if "--fetch" in sys.argv:
        fetch()

    seating = load("seating_esmy.json")
    pops = load("pops_rvih.json")
    plazas = load("plazas_5dck.json")
    shelters = load("shelters_t4f2.json")
    parks_raw = load("parks_enfh.json")
    nta_fc = load("nta2020_clipped.geojson")

    # ---------------- DOT seating ----------------
    dot = []
    sub_counts = Counter()
    for r in seating:
        lat, lon = float(r["latitude"]), float(r["longitude"])
        sub = (r.get("asset_subtype") or "").strip().upper()
        sub_counts[sub or "(blank)"] += 1
        m = re.match(r"^SEAT\.(\d{4})\.", r.get("siteid") or "")
        sid_yr = int(m.group(1)) if m else None
        inst = r.get("installation_date") or ""
        inst_yr = int(inst[:4]) if inst[:4].isdigit() else None
        # The site ID year matches the installation year (within one year) on 96% of records
        # that carry both, and it is present on records with no installation date, so it is
        # used as the installation year throughout. SEAT.1900.* placeholders are undated.
        yr = sid_yr if (sid_yr and 2011 <= sid_yr <= 2026) else (inst_yr if inst_yr and 2011 <= inst_yr <= 2026 else None)
        dot.append({
            "id": r.get("siteid"), "lat": round(lat, 5), "lon": round(lon, 5),
            "cat": classify(sub), "sub": sub, "yr": yr,
            "addr": (r.get("nearest_add") or r.get("on_street") or "").strip(),
            "on": (r.get("on_street") or "").strip(),
            "boro": (r.get("boroname") or "").strip(),
        })

    # Year-by-year
    years = list(range(2011, 2027))
    annual = {y: Counter() for y in years}
    undated = Counter()
    for p in dot:
        (annual[p["yr"]] if p["yr"] else undated)[p["cat"]] += 1
    annual_rows = []
    for y in years:
        c = annual[y]
        typed = c["backed"] + c["backless"] + c["bar"]
        annual_rows.append({
            "year": y, "backed": c["backed"], "backless": c["backless"], "leaning_bar": c["bar"],
            "unknown_bench": c["unknown"], "type_not_recorded": c["unrecorded"],
            "total": sum(c.values()),
            "pct_backed_of_typed": round(100 * c["backed"] / typed, 1) if typed else None,
        })

    def era(y0, y1):
        c = Counter()
        for y in range(y0, y1 + 1):
            c.update(annual[y])
        typed = c["backed"] + c["backless"] + c["bar"]
        return {
            "years": f"{y0}-{y1}", "backed": c["backed"], "backless": c["backless"], "leaning_bar": c["bar"],
            "unknown_bench": c["unknown"], "type_not_recorded": c["unrecorded"], "typed": typed,
            "total": sum(c.values()),
            "pct_backed_of_typed": round(100 * c["backed"] / typed, 1),
            "pct_no_back_of_typed": round(100 * (c["backless"] + c["bar"]) / typed, 1),
            # Upper bound: every unrecorded bench assumed backed
            "pct_backed_if_all_unrecorded_backed": round(100 * (c["backed"] + c["unrecorded"]) / (typed + c["unrecorded"]), 1),
        }

    era_early = era(2012, 2016)
    era_late = era(2023, 2026)

    # ---------------- POPS ----------------
    pops_pts = []
    for r in pops:
        if not r.get("latitude") or not r.get("longitude"):
            continue
        am = [a.strip() for a in (r.get("amenities_required") or "").split(";")]
        hrs = r.get("hour_of_access_required") or ""
        pops_pts.append({
            "id": r.get("pops_number"), "lat": round(float(r["latitude"]), 5), "lon": round(float(r["longitude"]), 5),
            "name": (r.get("building_name") or "").strip(), "addr": (r.get("building_address_with_zip") or "").strip(),
            "boro": (r.get("borough_name") or "").strip(),
            "seat": "Seating" in am, "tables": "Tables" in am,
            "h24": hrs.strip() == "24 Hours" or hrs.startswith("24 Hours"),
            "hours": hrs,
            "type": (r.get("public_space_type") or "").split(";")[0].strip(),
        })
    pops_seat = [p for p in pops_pts if p["seat"]]

    # ---------------- Plazas ----------------
    B = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}
    plaza_pts = []
    for r in plazas:
        g = shape(r["the_geom"])
        c = g.representative_point()
        plaza_pts.append({
            "lat": round(c.y, 5), "lon": round(c.x, 5), "name": (r.get("plazaname") or "").strip(),
            "on": (r.get("onstreet") or "").strip(), "partner": (r.get("partner") or "").strip(),
            "boro": B.get(str(r.get("borocode") or "")[:1], ""),
        })

    # ---------------- Bus shelters ----------------
    shelter_pts = []
    for r in shelters:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        shelter_pts.append({
            "id": r.get("shelter_id"), "lat": round(lat, 5), "lon": round(lon, 5),
            "on": (r.get("on_street") or "").title(), "x": (r.get("cross_stre") or "").title(),
            "boro": (r.get("boro_name") or "").title(),
        })

    # ---------------- Parks ----------------
    park_geoms, park_props = [], []
    park_type_counts = Counter()
    for r in parks_raw:
        t = r.get("typecategory")
        park_type_counts[t] += 1
        if t not in PARK_TYPES_WITH_SEATS or not r.get("multipolygon"):
            continue
        g = shapely.make_valid(shape(r["multipolygon"]))
        park_geoms.append(g)
        park_props.append({"name": r.get("signname") or "", "type": t, "acres": float(r.get("acres") or 0)})

    # ---------------- Raster ----------------
    lon0, lon1, lat0, lat1 = -74.2600, -73.6990, 40.4950, 40.9180
    cell = 60.0  # metres, approx, at the city's latitude
    nx = int(round((lon1 - lon0) * KX / cell))
    my0, my1 = merc_y(lat0), merc_y(lat1)
    ny_ = int(round((lat1 - lat0) * KY / cell))
    lons = lon0 + (np.arange(nx) + 0.5) * (lon1 - lon0) / nx
    mys = my1 - (np.arange(ny_) + 0.5) * (my1 - my0) / ny_  # top row first
    lats = inv_merc_y(mys)
    LON, LAT = np.meshgrid(lons, lats)
    flat_lon, flat_lat = LON.ravel(), LAT.ravel()
    print("raster", nx, "x", ny_)

    nta_geoms = [shapely.make_valid(shape(f["geometry"])) for f in nta_fc["features"]]
    t0 = time.time()
    all_pts = shapely.points(flat_lon, flat_lat)
    nta_tree = shapely.STRtree(nta_geoms)
    ci, gi = nta_tree.query(all_pts, predicate="intersects")
    cell_nta = np.full(len(flat_lon), -1)
    cell_nta[ci] = gi
    on_land = cell_nta >= 0
    print("land mask", round(time.time() - t0, 1), "s", int(on_land.sum()), "land cells")
    park_tree = shapely.STRtree(park_geoms)
    pi_, _ = park_tree.query(all_pts, predicate="intersects")
    in_park = np.zeros(len(flat_lon), bool)
    in_park[pi_] = True
    in_park &= on_land
    print("park mask", round(time.time() - t0, 1), "s", int(in_park.sum()), "park cells")

    gx, gy = xy(flat_lon, flat_lat)
    grid_xy = np.column_stack([gx, gy])
    land_idx = np.where(on_land)[0]

    def tree_of(pts):
        a = np.array([[p["lon"], p["lat"]] for p in pts])
        px, py = xy(a[:, 0], a[:, 1])
        return cKDTree(np.column_stack([px, py]))

    street = [p for p in dot if p["cat"] != "bar"] + pops_seat + plaza_pts
    backed = [p for p in dot if p["cat"] == "backed"]

    # Park edges sampled every ~25 m so distance-to-park is distance to the nearest edge
    edge_pts = []
    for g in park_geoms:
        for poly in getattr(g, "geoms", [g]):
            ring = poly.exterior
            length_m = ring.length * (KX + KY) / 2
            n = max(4, int(length_m / 25))
            for i in range(n):
                q = ring.interpolate(i / n, normalized=True)
                edge_pts.append({"lon": q.x, "lat": q.y})

    def minutes(pts, extra_zero=None):
        t = tree_of(pts)
        d, _ = t.query(grid_xy[land_idx], k=1, workers=-1)
        m = d * MIN_PER_M
        if extra_zero is not None:
            m[extra_zero[land_idx]] = 0
        out = np.full(grid_xy.shape[0], np.nan)
        out[land_idx] = m
        return out

    print("edge points", len(edge_pts))
    m_street = minutes(street)
    m_backed = minutes(backed)
    m_any = minutes(street + shelter_pts + edge_pts, extra_zero=in_park)

    # ---------------- Neighborhood figures ----------------
    # Only land outside park polygons counts as "where people are": park interiors are excluded
    # from every land-share figure.
    live = on_land & ~in_park

    def assign(pts):
        a = np.array([[p["lon"], p["lat"]] for p in pts])
        res = np.full(len(pts), -1)
        tree = shapely.STRtree(nta_geoms)
        pidx, gidx = tree.query(shapely.points(a[:, 0], a[:, 1]), predicate="intersects")
        res[pidx] = gidx
        # shoreline stragglers: nearest polygon within ~150 m
        miss = np.where(res < 0)[0]
        if len(miss):
            near = tree.query_nearest(shapely.points(a[miss, 0], a[miss, 1]), max_distance=0.002, all_matches=False)
            res[miss[near[0]]] = near[1]
        return res

    for arr in (dot, pops_seat, plaza_pts, shelter_pts):
        ix = assign(arr)
        for p, i in zip(arr, ix):
            p["_nta"] = int(i)

    nta_rows = []
    feats_out = []
    for i, f in enumerate(nta_fc["features"]):
        pr = f["properties"]
        sel = (cell_nta == i) & live
        if sel.sum() == 0:
            sel = (cell_nta == i) & on_land
        ms, mb, ma = m_street[sel], m_backed[sel], m_any[sel]
        cnt = Counter(p["cat"] for p in dot if p["_nta"] == i)
        row = {
            "nta2020": pr["nta2020"], "name": pr["name"], "boro": pr["boro"], "ntatype": pr["ntatype"],
            "pop2020": pr["pop2020"],
            "backed": cnt["backed"], "backless": cnt["backless"], "leaning_bar": cnt["bar"],
            "dot_type_not_recorded": cnt["unrecorded"] + cnt["unknown"],
            "pops_seating": sum(1 for p in pops_seat if p["_nta"] == i),
            "plazas": sum(1 for p in plaza_pts if p["_nta"] == i),
            "bus_shelters": sum(1 for p in shelter_pts if p["_nta"] == i),
            "cells": int(sel.sum()),
        }
        row["street_seats"] = row["backed"] + row["backless"] + row["dot_type_not_recorded"] + row["pops_seating"] + row["plazas"]
        row["street_seats_per_10k"] = round(row["street_seats"] * 1e4 / row["pop2020"], 2) if row["pop2020"] else None
        if len(ms):
            row.update({
                "median_min_street": round(float(np.median(ms)), 1),
                "median_min_backed": round(float(np.median(mb)), 1),
                "median_min_any": round(float(np.median(ma)), 1),
                "pct_over5_street": round(100 * float((ms > 5).mean()), 1),
                "pct_over5_backed": round(100 * float((mb > 5).mean()), 1),
                "pct_over5_any": round(100 * float((ma > 5).mean()), 1),
                "pct_over10_street": round(100 * float((ms > 10).mean()), 1),
                "pct_over10_any": round(100 * float((ma > 10).mean()), 1),
            })
        nta_rows.append(row)
        feats_out.append({"type": "Feature", "properties": {k: row.get(k) for k in (
            "nta2020", "name", "boro", "ntatype", "pop2020", "median_min_street", "median_min_backed",
            "median_min_any", "pct_over5_street", "pct_over5_any")}, "geometry": rgeo(shape(f["geometry"]), 0.00015)})

    res = [r for r in nta_rows if r["ntatype"] == "0" and r["pop2020"] >= 5000 and "median_min_street" in r]

    # Borough and city figures: share of lived-in land (outside parks, inside residential NTAs)
    res_idx = {i for i, r in enumerate(nta_rows) if r["ntatype"] == "0" and r["pop2020"] > 0}
    res_mask = live & np.isin(cell_nta, list(res_idx))
    boro_of = np.array([nta_rows[i]["boro"] if i >= 0 else "" for i in range(len(nta_rows))] + [""])
    cell_boro = np.where(cell_nta >= 0, boro_of[np.clip(cell_nta, 0, len(nta_rows) - 1)], "")

    def shares(mask):
        out = {}
        for key, m in (("street", m_street), ("backed", m_backed), ("any", m_any)):
            v = m[mask]
            out[f"median_min_{key}"] = round(float(np.median(v)), 1)
            out[f"pct_over5_{key}"] = round(100 * float((v > 5).mean()), 1)
            out[f"pct_over10_{key}"] = round(100 * float((v > 10).mean()), 1)
        return out

    boros = []
    for b in ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]:
        rows_b = [r for r in nta_rows if r["boro"] == b]
        rec = {"boro": b, "pop2020": sum(r["pop2020"] for r in rows_b if r["ntatype"] == "0"),
               "backed": sum(r["backed"] for r in rows_b), "backless": sum(r["backless"] for r in rows_b),
               "leaning_bar": sum(r["leaning_bar"] for r in rows_b),
               "dot_type_not_recorded": sum(r["dot_type_not_recorded"] for r in rows_b),
               "pops_seating": sum(r["pops_seating"] for r in rows_b), "plazas": sum(r["plazas"] for r in rows_b),
               "bus_shelters": sum(r["bus_shelters"] for r in rows_b)}
        rec.update(shares(res_mask & (cell_boro == b)))
        boros.append(rec)
    city = shares(res_mask)
    def enc(m):
        v = np.where(np.isnan(m), 0, np.clip(np.round(m * 10), 0, 254))
        return v.astype(np.uint8).reshape(ny_, nx)

    rgba = np.dstack([enc(m_street), enc(m_backed), enc(m_any),
                      np.where(res_mask, 255, np.where(on_land, 160, 0)).astype(np.uint8).reshape(ny_, nx)])
    Image.fromarray(rgba).save(os.path.join(OUT, "walk.png"), optimize=True)
    json.dump({
        "bounds": [lon0, lat0, lon1, lat1], "width": nx, "height": ny_, "cell_m": cell,
        "rows": "Web Mercator-regular, top row = north",
        "encoding": "value/10 = minutes, capped at 25.4; alpha 0 = water, 160 = parks and non-residential land, 255 = lived-in land (residential NTAs outside parks)",
        "channels": {"r": "street seats", "g": "backed DOT benches", "b": "any seat incl. bus shelters and parks"},
        "walk_model": "straight-line metres x 1.25 at 3 mph",
    }, open(os.path.join(OUT, "walk_meta.json"), "w"), indent=1)


    def strip(p):
        return {k: v for k, v in p.items() if not k.startswith("_")}

    summary = {
        "fetched": FETCHED,
        "dot_records": len(dot),
        "dot_subtypes": dict(sub_counts),
        "dot_by_cat": dict(Counter(p["cat"] for p in dot)),
        "dot_undated": dict(undated),
        "era_early": era_early, "era_late": era_late,
        "pops_total": len(pops_pts), "pops_seating": len(pops_seat),
        "pops_seating_24h": sum(1 for p in pops_seat if p["h24"]),
        "pops_seating_manhattan": sum(1 for p in pops_seat if p["boro"] == "Manhattan"),
        "plazas": len(plaza_pts), "bus_shelters": len(shelter_pts),
        "parks_used": len(park_geoms), "park_type_counts": dict(park_type_counts),
        "street_seat_sites": len(street),
        "city": city,
        "res_ntas": len(res),
    }

    payload = {
        "summary": summary,
        "annual": annual_rows,
        "boroughs": boros,
        "ntas": sorted(res, key=lambda r: -r["median_min_street"]),
        # compact point arrays: [lon, lat, ...]
        # type codes: B backed, L backless, R leaning bar, U unknown bench, X type not recorded
        "dot": [[p["lon"], p["lat"], {"backed": "B", "backless": "L", "bar": "R", "unknown": "U", "unrecorded": "X"}[p["cat"]], p["yr"] or 0, p["addr"], p["sub"]] for p in dot],
        "pops": [[p["lon"], p["lat"], p["name"] or p["addr"], p["addr"], 1 if p["h24"] else 0, p["type"]] for p in pops_seat],
        "plazas": [[p["lon"], p["lat"], p["name"], p["on"], p["partner"]] for p in plaza_pts],
        "shelters": [[p["lon"], p["lat"], p["on"], p["x"]] for p in shelter_pts],
    }
    with open(os.path.join(OUT, "seats.json"), "w") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)
    with open(os.path.join(OUT, "ntas.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats_out}, f, separators=(",", ":"), ensure_ascii=False)

    pk = []
    for g, pr in zip(park_geoms, park_props):
        if g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
            g = shapely.make_valid(g)
            polys = [x for x in getattr(g, "geoms", [g]) if x.geom_type in ("Polygon", "MultiPolygon")]
            if not polys:
                continue
            g = unary_union(polys)
        pk.append({"type": "Feature", "properties": pr, "geometry": rgeo(g, 0.00008)})
    with open(os.path.join(OUT, "parks.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": pk}, f, separators=(",", ":"), ensure_ascii=False)

    pd.DataFrame(annual_rows).to_csv(os.path.join(OUT, "dot_installations_by_year.csv"), index=False)
    pd.DataFrame(boros).to_csv(os.path.join(OUT, "seating_by_borough.csv"), index=False)
    pd.DataFrame(sorted(res, key=lambda r: r["nta2020"])).to_csv(os.path.join(OUT, "seating_by_neighborhood_nta2020.csv"), index=False)

    print(json.dumps(summary, indent=1))
    print(json.dumps(boros, indent=1))
    worst = sorted(res, key=lambda r: -r["median_min_any"])[:10]
    for r in worst:
        print(r["name"], r["boro"], r["median_min_street"], r["median_min_any"], r["pct_over5_any"])


if __name__ == "__main__":
    main()
