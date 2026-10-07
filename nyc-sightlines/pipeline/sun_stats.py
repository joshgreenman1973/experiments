"""Share of public ground that can watch the sun rise or set, by date and borough.
Usage: python sun_stats.py GRID_DIR SUN_DIR OUT_JSON"""
import sys, json, numpy as np
G, SUN, OUT = sys.argv[1:4]
BORO = {1: "Manhattan", 2: "Bronx", 3: "Brooklyn", 4: "Queens", 5: "Staten Island"}
pub = np.load(f"{G}/public.npy").astype(bool)
idx = np.flatnonzero(pub)
b = np.load(f"{G}/boro.npy").ravel()[idx]
out = []
for st in json.load(open(f"{SUN}/sun_states.json")):
    row = {"key": st["key"]}
    for ev in ("sunrise", "sunset"):
        lv = np.load(f"{SUN}/sun_{st['key']}_{ev}.npy").ravel()[idx]
        row[ev] = {"horizon": round(100 * float((lv == 3).mean()), 2), "any": round(100 * float((lv > 0).mean()), 2),
                   "by_boro": {n: round(100 * float((lv[b == k] == 3).mean()), 2) for k, n in BORO.items()}}
    out.append(row)
    print(row["key"], "rise", row["sunrise"]["horizon"], row["sunrise"]["any"], "| set", row["sunset"]["horizon"], row["sunset"]["any"], row["sunset"]["by_boro"])
json.dump(out, open(OUT, "w"), indent=1)
