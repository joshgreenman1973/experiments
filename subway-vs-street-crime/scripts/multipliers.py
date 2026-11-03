"""Neighborhood street-risk multipliers: precinct violent index crimes per
resident divided by the citywide rate. Crimes from data/precinct_violent_YYYY.json
(NYPD complaints by addr_pct_cd, report-date year); residents from the 2020
census by precinct (jkeefe/census-by-precincts, P1_001N)."""
import csv, json, sys, pathlib
D = pathlib.Path(__file__).resolve().parent.parent / "data"
HOODS = {
 "mott_haven": ("Mott Haven", [40]), "hunts_point": ("Hunts Point", [41]),
 "morrisania": ("Morrisania / Crotona", [42]), "east_harlem": ("East Harlem", [23, 25]),
 "south_bronx": ("Highbridge / Fordham", [44, 46]), "jamaica": ("Jamaica, Queens", [103]),
 "brownsville": ("Brownsville", [73]), "central_harlem": ("Central Harlem", [28, 32]),
 "east_ny": ("East New York", [75]), "downtown_bk": ("Downtown Brooklyn", [84]),
 "bushwick": ("Bushwick", [83]), "bed_stuy": ("Bedford-Stuyvesant", [79, 81]),
 "wash_heights": ("Washington Heights", [33, 34]), "flatbush": ("Flatbush", [67, 70]),
 "crown_heights": ("Crown Heights", [71, 77]), "astoria": ("Astoria", [114]),
 "tribeca": ("Tribeca / Battery Park City", [1]), "sunset_park": ("Sunset Park", [72]),
 "riverdale": ("Riverdale", [50]), "williamsburg": ("Williamsburg / Greenpoint", [90, 94]),
 "park_slope": ("Park Slope", [78]), "staten_island": ("Staten Island", [120, 121, 122, 123]),
 "uws": ("Upper West Side", [20, 24]), "ues": ("Upper East Side", [19]),
 "forest_hills": ("Forest Hills", [112]), "bay_ridge": ("Bay Ridge", [68]),
 "bayside": ("Bayside", [111]),
 "midtown": ("Midtown", [14, 18]),
}
pop = {int(r["precinct"]): int(r["P1_001N"]) for r in csv.DictReader(open(D / "nyc_precinct_2020pop.csv"))}
out = {}
def load(name):
    return {int(r["addr_pct_cd"]): int(r["n"]) for r in json.load(open(D / name)) if r.get("addr_pct_cd")}


for y, kind, fname in ((2024, "violent", "precinct_violent_2024.json"),
                       (2025, "violent", "precinct_violent_2025.json"),
                       (2025, "index", "precinct_index_2025.json")):
    crimes = load(fname)
    y = f"{y}_{kind}"
    city = sum(crimes.values()) / sum(pop.values())
    out[y] = {"citywide_crimes": sum(crimes.values()), "citywide_pop": sum(pop.values()),
              "citywide_rate_per_1000": city * 1000, "hoods": {}}
    for k, (name, pcts) in HOODS.items():
        c = sum(crimes[p] for p in pcts); n = sum(pop[p] for p in pcts)
        out[y]["hoods"][k] = {"name": name, "precincts": pcts, "crimes": c, "pop": n,
                              "rate_per_1000": c / n * 1000, "mult": (c / n) / city}
(D / "multipliers.json").write_text(json.dumps(out, indent=1))
if __name__ == "__main__":
    for y in out:
        print(y, out[y]["citywide_crimes"], out[y]["citywide_pop"], round(out[y]["citywide_rate_per_1000"], 3))
    for k in HOODS:
        a, b, c = (out[y]["hoods"][k] for y in ("2024_violent", "2025_violent", "2025_index"))
        print(f"{k:15s} violent 2024 {a['mult']:.2f}  2025 {b['mult']:.2f}  index 2025 {c['mult']:.2f}")
