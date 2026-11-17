# Flatbush Avenue spotlight (flatbush.html)

Builds `data/spotlight/flatbush.json`, which holds every number on the page.

Run from one working folder that holds these scripts, in this order:

1. `git clone --filter=blob:none --no-checkout --single-branch --branch bus-data --depth=1 https://github.com/joshgreenman1973/experiments.git busdata`
   (a copy of the snapshot archive that downloads each day's files only when they are read)
2. `python3 extract.py 2026-11-09 2026-11-10 ...` pulls every bus position on Flatbush and in a few other corridor boxes, plus every position of the control routes, into `extracts/<date>.csv.gz`. About 45 seconds a day; 4 days run at once.
3. Download the MTA's Brooklyn GTFS (`https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip`) and unzip it to `gtfs/b/`. `corridor.py` uses shape `B410126`, the B41 to Kings Plaza.
4. `python3 corridor.py` writes `corridor_pairs.csv`: distance and time along Flatbush by date, hour, direction, stretch and route.
5. `python3 mta_seg.py B41` downloads MTA Bus Route Segment Speeds (data.ny.gov 58t6-89vi and kufs-yh3x), weekdays, to `mta/B41.csv`.
6. Copy `data/summary/days.json` from this project into the folder (it marks holidays and school-closed weekdays).
7. `python3 build_flatbush.py flatbush.json` prints the key figures and writes the page data. It also runs `control.py` (speed change on the B6, B35, B44 and B46 over the same weeks).

Periods are set at the top of `build_flatbush.py`: the last four weeks of construction (Oct. 13 to Nov. 6, 2026) and the first week of the lanes (Nov. 9 to 16, 2026). Update `AFT` and rerun steps 2, 4 and 7 to extend the after period.
