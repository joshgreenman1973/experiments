#!/usr/bin/env python3
"""Build data files for nyc-where-to-sit ("Where you can sit down").

Sources:
  1. NYC DOT Seating Locations (NYC Open Data `esmy-s8q5`), 5,776 records fetched 2026-11-06.
  2. NYC DCP Privately Owned Public Spaces (NYC Open Data `rvih-nhyn`), 392 records fetched 2026-11-06.
  3. NYC DOT Pedestrian Plazas (NYC Open Data `5dck-9m6g`), 90 records fetched 2026-11-06.
  4. NYC DCP 2020 Neighborhood Tabulation Areas (shoreline-clipped `nyc_nta_2020.geojson`)
     and 2020 Decennial Census population (`populations.json`).
"""
import json
import math
import os
import re
from collections import Counter, defaultdict

import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

RAW_DIR = "/Users/joshgreenman/Experiments/nyc-where-to-sit/raw"
DOT_SEATING_JSON = os.path.join(RAW_DIR, "dot_seating_esmy_s8q5.json")
POPS_JSON = os.path.join(RAW_DIR, "dcp_pops_rvih_nhyn.json")
PLAZAS_JSON = os.path.join(RAW_DIR, "dot_plazas_5dck_9m6g.json")

NTA_GEOJSON = "/Users/joshgreenman/Experiments/nyc-child-density/data/nyc_nta_2020.geojson"
POP_JSON = "/Users/joshgreenman/Experiments/nyc-rat-map/data/populations.json"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "data")
os.makedirs(OUT_DIR, exist_ok=True)


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def classify_subtype(raw_sub):
    s = (raw_sub or "").strip().upper()
    if s in ("BACKED 1.0", "BACKED 2.0", "WORLDS FAIR"):
        return "backed"
    if s in ("BACKLESS 1.0", "BACKLESS 2.0"):
        return "backless"
    if s == "LEANING BAR":
        return "leaning_bar"
    if s == "UNKNOWN BENCH":
        return "unknown_bench"
    return "untyped_recent"


def main():
    seating_raw = json.load(open(DOT_SEATING_JSON))
    pops_raw = json.load(open(POPS_JSON))
    plazas_raw = json.load(open(PLAZAS_JSON))
    nta_fc = json.load(open(NTA_GEOJSON))
    pops_lookup = json.load(open(POP_JSON))["nta"]

    # Prepare NTA polygons (shoreline-clipped)
    ntas = {}
    for feat in nta_fc["features"]:
        props = feat["properties"]
        code = props["nta2020"]
        geom = shape(feat["geometry"])
        pop_entry = pops_lookup.get(code, {})
        # Area in sq miles (shape_area is in sq feet)
        area_sqmi = float(props.get("shape_area", 0)) / (5280.0 ** 2)
        ntas[code] = {
            "nta2020": code,
            "name": props["ntaname"],
            "boro": props["boroname"],
            "cdta": props.get("cdta2020", ""),
            "ntatype": str(props.get("ntatype", "0")),
            "pop2020": int(pop_entry.get("pop2020", 0)),
            "area_sqmi": round(area_sqmi, 3),
            "geom": geom,
            "prep": prep(geom),
            "dot_total": 0,
            "backed": 0,
            "backless": 0,
            "leaning_bar": 0,
            "untyped": 0,
            "bus_route_sites": 0,
            "pops_total": 0,
            "pops_seating": 0,
            "pops_24h": 0,
            "plazas": 0,
        }

    def find_nta(lat, lon):
        pt = Point(lon, lat)
        for code, n in ntas.items():
            if n["prep"].contains(pt):
                return code
        # Fallback: nearest NTA polygon within ~150m for shoreline edge points
        best_code = None
        best_d = 0.002
        for code, n in ntas.items():
            d = n["geom"].distance(pt)
            if d < best_d:
                best_d = d
                best_code = code
        return best_code

    # 1. Process DOT Seating Locations (esmy-s8q5)
    by_year = defaultdict(lambda: {"backed": 0, "backless": 0, "leaning_bar": 0, "unknown_bench": 0, "untyped_siteid_year": 0})
    dot_points = []
    subtype_counts = Counter()
    category_counts = Counter()

    for r in seating_raw:
        lat = float(r["latitude"])
        lon = float(r["longitude"])
        sub = (r.get("asset_subtype") or "").strip().upper()
        cat = classify_subtype(sub)
        subtype_counts[sub or "(BLANK)"] += 1
        category_counts[cat] += 1

        inst = (r.get("installation_date") or "").strip()
        yr = int(inst[:4]) if len(inst) >= 4 and inst[:4].isdigit() else None
        siteid = (r.get("siteid") or "").strip()
        siteid_yr = None
        m = re.match(r"^SEAT\.(20\d\d)\.", siteid)
        if m:
            siteid_yr = int(m.group(1))

        if yr and 2011 <= yr <= 2026:
            if cat in ("backed", "backless", "leaning_bar", "unknown_bench"):
                by_year[yr][cat] += 1
        elif siteid_yr and 2011 <= siteid_yr <= 2026:
            by_year[siteid_yr]["untyped_siteid_year"] += 1

        nta_code = find_nta(lat, lon)
        if nta_code and nta_code in ntas:
            n = ntas[nta_code]
            n["dot_total"] += 1
            if cat == "backed":
                n["backed"] += 1
            elif cat == "backless":
                n["backless"] += 1
            elif cat == "leaning_bar":
                n["leaning_bar"] += 1
            else:
                n["untyped"] += 1

        on_st = (r.get("on_street") or "").strip()
        fr_st = (r.get("from_street") or "").strip()
        to_st = (r.get("to_street") or "").strip()
        cross = f"{fr_st} to {to_st}".strip(" to") if (fr_st or to_st) else ""
        dot_points.append(
            {
                "id": siteid,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "cat": cat,
                "sub": sub or "Unclassified (2023–2026)",
                "yr": yr or siteid_yr,
                "dated": yr is not None,
                "boro": (r.get("boroname") or "").strip(),
                "street": on_st,
                "cross": cross,
                "addr": (r.get("nearest_add") or on_st).strip(),
                "nta": nta_code or "",
                "nta_name": (r.get("ntaname") or "").strip(),
            }
        )

    # 2. Process DCP Privately Owned Public Spaces (rvih-nhyn)
    pops_points = []
    pops_with_seating_count = 0
    pops_24h_count = 0
    pops_seating_24h_count = 0

    for r in pops_raw:
        lat_s = r.get("latitude")
        lon_s = r.get("longitude")
        if not lat_s or not lon_s:
            continue
        lat = float(lat_s)
        lon = float(lon_s)
        am = (r.get("amenities_required") or "").strip()
        hr = (r.get("hour_of_access_required") or "").strip()
        has_seat = any(k in am.lower() for k in ("seating", "table", "chair", "bench"))
        is_24h = "24 hours" in hr.lower()
        if has_seat:
            pops_with_seating_count += 1
        if is_24h:
            pops_24h_count += 1
        if has_seat and is_24h:
            pops_seating_24h_count += 1

        nta_code = find_nta(lat, lon)
        if nta_code and nta_code in ntas:
            n = ntas[nta_code]
            n["pops_total"] += 1
            if has_seat:
                n["pops_seating"] += 1
            if is_24h:
                n["pops_24h"] += 1

        pops_points.append(
            {
                "id": r.get("pops_number", ""),
                "name": (r.get("building_name") or r.get("building_address_with_zip") or "").strip(),
                "addr": (r.get("building_address_with_zip") or "").strip(),
                "boro": (r.get("borough_name") or "").strip(),
                "yr": int(float(r["year_completed"])) if (r.get("year_completed") or "").replace(".", "").isdigit() else None,
                "type": (r.get("public_space_type") or "").strip().split(";")[0],
                "has_seating": has_seat,
                "is_24h": is_24h,
                "hours": hr.split(";")[0] if hr else "Unknown",
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "nta": nta_code or "",
            }
        )

    # 3. Process DOT Pedestrian Plazas (5dck-9m6g)
    plaza_points = []
    B_MAP = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island", "M": "Manhattan", "X": "Bronx", "K": "Brooklyn", "Q": "Queens", "R": "Staten Island"}
    for idx, r in enumerate(plazas_raw):
        geom_raw = r.get("the_geom")
        if not geom_raw:
            continue
        g = shape(geom_raw)
        c = g.centroid
        lat, lon = c.y, c.x
        nta_code = find_nta(lat, lon)
        if nta_code and nta_code in ntas:
            ntas[nta_code]["plazas"] += 1
        bcode = str(r.get("borocode") or "").strip()
        plaza_points.append(
            {
                "id": f"PLAZA-{idx+1}",
                "name": (r.get("plazaname") or "").strip(),
                "street": f"{(r.get('onstreet') or '').strip()} ({(r.get('fromstreet') or '').strip()} to {(r.get('tostreet') or '').strip()})",
                "partner": (r.get("partner") or "").strip(),
                "boro": B_MAP.get(bcode, bcode),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "nta": nta_code or "",
            }
        )

    # 4. Compute grid walk-distance across residential NTAs
    # Build coordinate arrays for fast nearest-neighbor lookup:
    #   - true_seats: DOT benches (excluding leaning_bar) + POPS with seating + DOT plazas
    #   - backed_only: DOT backed benches only
    #   - dot_benches_no_bars: DOT benches excluding leaning bars
    true_seats_ll = (
        [(p["lat"], p["lon"]) for p in dot_points if p["cat"] != "leaning_bar"]
        + [(p["lat"], p["lon"]) for p in pops_points if p["has_seating"]]
        + [(p["lat"], p["lon"]) for p in plaza_points]
    )
    backed_ll = [(p["lat"], p["lon"]) for p in dot_points if p["cat"] == "backed"]
    all_dot_ll = [(p["lat"], p["lon"]) for p in dot_points]

    # Spatial bucket index (~0.01 deg ~ 0.7 mi cells) for fast nearest distance
    def build_grid_index(pts):
        grid = defaultdict(list)
        for lat, lon in pts:
            grid[(int(lat * 50), int(lon * 50))].append((lat, lon))
        return grid

    idx_true = build_grid_index(true_seats_ll)
    idx_backed = build_grid_index(backed_ll)

    def min_dist_miles(lat, lon, grid, fallback_pts):
        gx, gy = int(lat * 50), int(lon * 50)
        best = 999.0
        for r_ring in (1, 2, 4):
            cand = []
            for dx in range(-r_ring, r_ring + 1):
                for dy in range(-r_ring, r_ring + 1):
                    cand.extend(grid.get((gx + dx, gy + dy), ()))
            if cand:
                for p_lat, p_lon in cand:
                    d = haversine_miles(lat, lon, p_lat, p_lon)
                    if d < best:
                        best = d
                if best <= (r_ring * 0.8):
                    return best
        for p_lat, p_lon in fallback_pts:
            d = haversine_miles(lat, lon, p_lat, p_lon)
            if d < best:
                best = d
        return best

    # Sample a regular grid (~0.0025 deg ~ 250m spacing) across NYC land in residential NTAs
    # Walk distance = straight-line distance * 1.25 Manhattan-grid routing factor; walk time at 3.0 mph (20 min/mile)
    ROUTING_FACTOR = 1.25
    nta_list = []
    city_sample_dists_seat = []
    city_sample_dists_backed = []
    boro_stats = defaultdict(lambda: {"pop": 0, "area_sqmi": 0.0, "dot_total": 0, "backed": 0, "backless": 0, "leaning_bar": 0, "untyped": 0, "pops_seating": 0, "plazas": 0, "samples": 0, "beyond_quarter_mi_walk": 0, "beyond_half_mi_walk": 0})

    for code, n in sorted(ntas.items()):
        geom = n["geom"]
        minx, miny, maxx, maxy = geom.bounds
        step = 0.0028
        dists_seat = []
        dists_backed = []
        y = miny + step / 2
        while y < maxy:
            x = minx + step / 2
            while x < maxx:
                if n["prep"].contains(Point(x, y)):
                    d_s = min_dist_miles(y, x, idx_true, true_seats_ll) * ROUTING_FACTOR
                    d_b = min_dist_miles(y, x, idx_backed, backed_ll) * ROUTING_FACTOR
                    dists_seat.append(d_s)
                    dists_backed.append(d_b)
                x += step
            y += step

        if not dists_seat:
            c = geom.representative_point()
            dists_seat = [min_dist_miles(c.y, c.x, idx_true, true_seats_ll) * ROUTING_FACTOR]
            dists_backed = [min_dist_miles(c.y, c.x, idx_backed, backed_ll) * ROUTING_FACTOR]

        dists_seat.sort()
        dists_backed.sort()
        med_walk_mi = dists_seat[len(dists_seat) // 2]
        med_backed_mi = dists_backed[len(dists_backed) // 2]
        pct_beyond_5min = 100.0 * sum(1 for d in dists_seat if d > 0.25) / len(dists_seat)
        pct_beyond_10min = 100.0 * sum(1 for d in dists_seat if d > 0.50) / len(dists_seat)

        if n["ntatype"] == "0" and n["pop2020"] > 0:
            city_sample_dists_seat.extend(dists_seat)
            city_sample_dists_backed.extend(dists_backed)
            bs = boro_stats[n["boro"]]
            bs["pop"] += n["pop2020"]
            bs["area_sqmi"] += n["area_sqmi"]
            bs["dot_total"] += n["dot_total"]
            bs["backed"] += n["backed"]
            bs["backless"] += n["backless"]
            bs["leaning_bar"] += n["leaning_bar"]
            bs["untyped"] += n["untyped"]
            bs["pops_seating"] += n["pops_seating"]
            bs["plazas"] += n["plazas"]
            bs["samples"] += len(dists_seat)
            bs["beyond_quarter_mi_walk"] += sum(1 for d in dists_seat if d > 0.25)
            bs["beyond_half_mi_walk"] += sum(1 for d in dists_seat if d > 0.50)

        true_seat_count = (n["dot_total"] - n["leaning_bar"]) + n["pops_seating"] + n["plazas"]
        dot_bench_count = n["dot_total"] - n["leaning_bar"]
        pop = n["pop2020"]
        seats_per_10k_raw = (true_seat_count * 10000.0 / pop) if pop > 0 else 0.0
        benches_per_10k_raw = (dot_bench_count * 10000.0 / pop) if pop > 0 else 0.0
        backed_per_10k_raw = (n["backed"] * 10000.0 / pop) if pop > 0 else 0.0

        nta_rec = {
            "nta2020": code,
            "name": n["name"],
            "boro": n["boro"],
            "cdta": n["cdta"],
            "ntatype": n["ntatype"],
            "pop2020": pop,
            "area_sqmi": n["area_sqmi"],
            "dot_total": n["dot_total"],
            "dot_benches": dot_bench_count,
            "backed": n["backed"],
            "backless": n["backless"],
            "leaning_bar": n["leaning_bar"],
            "untyped": n["untyped"],
            "bus_route_sites": n["bus_route_sites"],
            "pops_total": n["pops_total"],
            "pops_seating": n["pops_seating"],
            "pops_24h": n["pops_24h"],
            "plazas": n["plazas"],
            "public_seat_sites": true_seat_count,
            "seats_per_10k": round(seats_per_10k_raw, 2),
            "seats_per_10k_raw": seats_per_10k_raw,
            "benches_per_10k": round(benches_per_10k_raw, 2),
            "backed_per_10k": round(backed_per_10k_raw, 2),
            "median_walk_miles": round(med_walk_mi, 2),
            "median_walk_mins": round(med_walk_mi * 20.0, 1),
            "median_backed_walk_miles": round(med_backed_mi, 2),
            "median_backed_walk_mins": round(med_backed_mi * 20.0, 1),
            "pct_land_beyond_5min_walk": round(pct_beyond_5min, 1),
            "pct_land_beyond_10min_walk": round(pct_beyond_10min, 1),
        }
        nta_list.append(nta_rec)

    # Update GeoJSON features with computed seating metrics and simplify geometry precision to 5 decimals
    def round_coords(coords):
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], 5), round(coords[1], 5)]
        return [round_coords(c) for c in coords]

    nta_by_code = {r["nta2020"]: r for r in nta_list}
    out_features = []
    for feat in nta_fc["features"]:
        code = feat["properties"]["nta2020"]
        rec = nta_by_code[code]
        out_features.append(
            {
                "type": "Feature",
                "properties": {k: v for k, v in rec.items() if k != "seats_per_10k_raw"},
                "geometry": {
                    "type": feat["geometry"]["type"],
                    "coordinates": round_coords(feat["geometry"]["coordinates"]),
                },
            }
        )

    with open(os.path.join(OUT_DIR, "nta_seating.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": out_features}, f, separators=(",", ":"), ensure_ascii=False)

    # Year-by-year table (2011 to 2026)
    annual_series = []
    for yr in range(2011, 2027):
        row = by_year[yr]
        subtyped_total = row["backed"] + row["backless"] + row["leaning_bar"]
        annual_series.append(
            {
                "year": yr,
                "backed": row["backed"],
                "backless": row["backless"],
                "leaning_bar": row["leaning_bar"],
                "unknown_bench": row["unknown_bench"],
                "untyped_siteid_year": row["untyped_siteid_year"],
                "dated_total": subtyped_total + row["unknown_bench"],
                "all_total": subtyped_total + row["unknown_bench"] + row["untyped_siteid_year"],
                "pct_backed_of_subtyped": round(100.0 * row["backed"] / subtyped_total, 1) if subtyped_total else None,
                "pct_backless_or_bar_of_subtyped": round(100.0 * (row["backless"] + row["leaning_bar"]) / subtyped_total, 1) if subtyped_total else None,
            }
        )

    # Borough table
    borough_rows = []
    for boro in ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]:
        bs = boro_stats[boro]
        true_seats = (bs["dot_total"] - bs["leaning_bar"]) + bs["pops_seating"] + bs["plazas"]
        borough_rows.append(
            {
                "boro": boro,
                "pop2020": bs["pop"],
                "area_sqmi": round(bs["area_sqmi"], 1),
                "dot_total": bs["dot_total"],
                "backed": bs["backed"],
                "backless": bs["backless"],
                "leaning_bar": bs["leaning_bar"],
                "untyped": bs["untyped"],
                "pops_seating": bs["pops_seating"],
                "plazas": bs["plazas"],
                "public_seat_sites": true_seats,
                "seats_per_10k": round(true_seats * 10000.0 / bs["pop"], 2) if bs["pop"] else 0,
                "backed_per_10k": round(bs["backed"] * 10000.0 / bs["pop"], 2) if bs["pop"] else 0,
                "pct_land_beyond_5min_walk": round(100.0 * bs["beyond_quarter_mi_walk"] / bs["samples"], 1) if bs["samples"] else 0,
                "pct_land_beyond_10min_walk": round(100.0 * bs["beyond_half_mi_walk"] / bs["samples"], 1) if bs["samples"] else 0,
            }
        )

    city_sample_dists_seat.sort()
    city_sample_dists_backed.sort()
    res_ntas = [r for r in nta_list if r["ntatype"] == "0" and r["pop2020"] >= 5000]
    res_ntas_sorted = sorted(res_ntas, key=lambda r: r["seats_per_10k_raw"])

    # Era comparison: 2012-2016 vs 2023-2026
    era1_backed = sum(r["backed"] for r in annual_series if 2012 <= r["year"] <= 2016)
    era1_backless = sum(r["backless"] for r in annual_series if 2012 <= r["year"] <= 2016)
    era1_bar = sum(r["leaning_bar"] for r in annual_series if 2012 <= r["year"] <= 2016)
    era1_tot = era1_backed + era1_backless + era1_bar

    era2_backed = sum(r["backed"] for r in annual_series if 2023 <= r["year"] <= 2026)
    era2_backless = sum(r["backless"] for r in annual_series if 2023 <= r["year"] <= 2026)
    era2_bar = sum(r["leaning_bar"] for r in annual_series if 2023 <= r["year"] <= 2026)
    era2_tot = era2_backed + era2_backless + era2_bar

    summary = {
        "fetched": "2026-11-06",
        "dot_total_sites": len(dot_points),
        "dot_subtyped_sites": sum(1 for p in dot_points if p["cat"] != "untyped_recent"),
        "dot_untyped_2023_2026_sites": sum(1 for p in dot_points if p["cat"] == "untyped_recent"),
        "dot_backed": category_counts["backed"],
        "dot_backless": category_counts["backless"],
        "dot_leaning_bar": category_counts["leaning_bar"],
        "dot_unknown_bench": category_counts["unknown_bench"],
        "era_2012_2016": {
            "backed": era1_backed,
            "backless": era1_backless,
            "leaning_bar": era1_bar,
            "total_subtyped": era1_tot,
            "pct_backed": round(100.0 * era1_backed / era1_tot, 1),
            "pct_backless_or_bar": round(100.0 * (era1_backless + era1_bar) / era1_tot, 1),
        },
        "era_2023_2026": {
            "backed": era2_backed,
            "backless": era2_backless,
            "leaning_bar": era2_bar,
            "total_subtyped": era2_tot,
            "pct_backed": round(100.0 * era2_backed / era2_tot, 1),
            "pct_backless_or_bar": round(100.0 * (era2_backless + era2_bar) / era2_tot, 1),
        },
        "pops_total": len(pops_points),
        "pops_with_seating": pops_with_seating_count,
        "pops_24h": pops_24h_count,
        "pops_seating_24h": pops_seating_24h_count,
        "pops_manhattan_share_pct": round(100.0 * sum(1 for p in pops_points if p["boro"] == "Manhattan") / len(pops_points), 1),
        "plazas_total": len(plaza_points),
        "true_public_seat_sites_total": (len(dot_points) - category_counts["leaning_bar"]) + pops_with_seating_count + len(plaza_points),
        "city_median_walk_miles": round(city_sample_dists_seat[len(city_sample_dists_seat) // 2], 2),
        "city_median_walk_mins": round(city_sample_dists_seat[len(city_sample_dists_seat) // 2] * 20.0, 1),
        "city_pct_land_beyond_5min_walk": round(100.0 * sum(1 for d in city_sample_dists_seat if d > 0.25) / len(city_sample_dists_seat), 1),
        "city_pct_land_beyond_10min_walk": round(100.0 * sum(1 for d in city_sample_dists_seat if d > 0.50) / len(city_sample_dists_seat), 1),
        "residential_ntas_zero_dot_seats": sum(1 for r in res_ntas if r["dot_benches"] == 0),
        "residential_ntas_under_2_per_10k": sum(1 for r in res_ntas if r["seats_per_10k_raw"] < 2.0),
    }

    payload = {
        "summary": summary,
        "annual": annual_series,
        "boroughs": borough_rows,
        "neighborhoods": [{k: v for k, v in r.items() if k != "seats_per_10k_raw"} for r in sorted(res_ntas, key=lambda r: -r["seats_per_10k_raw"])],
        "lowest_neighborhoods": [{k: v for k, v in r.items() if k != "seats_per_10k_raw"} for r in res_ntas_sorted[:15]],
        "highest_neighborhoods": [{k: v for k, v in r.items() if k != "seats_per_10k_raw"} for r in res_ntas_sorted[-15:][::-1]],
        "dot_seats": dot_points,
        "pops": pops_points,
        "plazas": plaza_points,
    }

    with open(os.path.join(OUT_DIR, "seating.json"), "w") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)

    # Write flat CSVs for download
    pd.DataFrame(annual_series).to_csv(os.path.join(OUT_DIR, "dot_installations_by_year.csv"), index=False)
    pd.DataFrame(borough_rows).to_csv(os.path.join(OUT_DIR, "seating_by_borough.csv"), index=False)
    pd.DataFrame([{k: v for k, v in r.items() if k != "seats_per_10k_raw"} for r in res_ntas]).to_csv(
        os.path.join(OUT_DIR, "seating_by_neighborhood_nta2020.csv"), index=False
    )

    print("Summary:", json.dumps(summary, indent=2))
    print("Boroughs:", json.dumps(borough_rows, indent=2))
    print("Bottom 8 residential NTAs (pop >= 5,000):")
    for r in res_ntas_sorted[:8]:
        print(" ", r["nta2020"], r["name"], f"({r['boro']}) pop={r['pop2020']}: {r['public_seat_sites']} sites ({r['seats_per_10k']}/10k), med walk={r['median_walk_mins']} min")
    print("Top 8 residential NTAs (pop >= 5,000):")
    for r in res_ntas_sorted[-8:][::-1]:
        print(" ", r["nta2020"], r["name"], f"({r['boro']}) pop={r['pop2020']}: {r['public_seat_sites']} sites ({r['seats_per_10k']}/10k), med walk={r['median_walk_mins']} min")


if __name__ == "__main__":
    main()
