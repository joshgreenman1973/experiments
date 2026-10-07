import pandas as pd, glob
D = "data/nhgis/nhgis0004_csv/"
NYC = {"New York", "Kings", "Queens", "Bronx", "Richmond"}
OFFICIAL = {1910: 4766883, 1920: 5620048, 1930: 6930446, 1940: 7454995, 1950: 7891957, 1960: 7781984}
spec = {1910: ("ds40_1910_tract", "A65"), 1920: ("ds48_1920_tract", "BBQ002"), 1930: ("ds66_1930_tract", "BOC"),
        1940: ("ds81_1940_tractnyc", "BZO001"), 1950: ("ds82_1950_tract", "BZ8001"), 1960: ("ds92_1960_tract", "CA4001")}
for y, (f, col) in spec.items():
    df = pd.read_csv(glob.glob(D + f"*{f}.csv")[0], encoding="latin-1", low_memory=False, skiprows=[1])
    df = df[(df.STATE == "New York") & df.COUNTY.isin(NYC)]
    cols = [c for c in df.columns if c.startswith(col)] if len(col) == 3 else [col]
    tot = df[cols].sum(axis=1)
    print(y, len(df), "tracts", int(tot.sum()), "official", OFFICIAL[y], f"{tot.sum()/OFFICIAL[y]-1:+.3%}",
          df.groupby("COUNTY").size().to_dict())
