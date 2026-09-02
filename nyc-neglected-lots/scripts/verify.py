"""Independent re-check: re-query each source count straight from the API and compare with
findings.json. Run after build_data.py. Exits non-zero on any mismatch beyond tolerance
(the live datasets move a little every day; the tolerance is 1% or 5 rows, whichever is larger)."""
import json, os, sys, urllib.request, urllib.parse, time
HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "..", "data", "findings.json")))
raw = F["counts"]["raw"]; W0 = F["window"][0]
SOC = "https://data.cityofnewyork.us/resource/"
def q(ds, params):
    url = SOC + ds + ".json?" + urllib.parse.urlencode(params)
    for t in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nyc-neglected-lots verify"}), timeout=300) as r:
                return json.load(r)
        except Exception as e:
            print("  retry", t, str(e)[:80]); time.sleep(5 * (2 ** t))
    raise SystemExit("gave up: " + url)
NEG = "('Dirty Condition','Illegal Dumping','Lot Condition','Graffiti','Derelict Vehicles','Rodent')"
checks = [
    ("vacant land lots (PLUTO landuse 11)", F["counts"]["vacant_lots"], lambda: int(q("64uk-42ks", {"$select": "count(*) as n", "$where": "landuse='11' AND latitude is not null"})[0]["n"])),
    ("311 neglect complaints in window", raw["c311"], lambda: int(q("erm2-nwe9", {"$select": "count(*) as n", "$where": f"created_date>='{W0}' AND complaint_type in {NEG}"})[0]["n"])),
    ("rodent initial inspections failed for rat activity", raw["rodent_initial"], lambda: int(q("p937-wjvj", {"$select": "count(*) as n", "$where": f"inspection_date>='{W0}' AND result like 'Failed for Rat Activity%' AND inspection_type='Initial'"})[0]["n"])),
    ("AEP active buildings with a BBL", raw["aep"], lambda: int(q("hcir-3275", {"$select": "count(distinct bbl) as n", "$where": "current_status='AEP Active' AND bbl is not null"})[0]["n"])),
    ("Underlying Conditions active with a BBL", raw["ucp"], lambda: int(q("xpbf-ithr", {"$select": "count(distinct bbl) as n", "$where": "current_status='Active' AND bbl is not null"})[0]["n"])),
    ("whole-building vacate orders in force with a BBL", raw["vacate"], lambda: int(q("tb8q-a3ar", {"$select": "count(distinct bbl) as n", "$where": "actual_rescind_date is null AND vacate_type='Entire Building' AND bbl is not null"})[0]["n"])),
    ("stalled sites on latest run", raw["stalled"], lambda: int(q("i296-73x5", {"$select": "count(*) as n", "$where": f"dobrundate='{raw['stalled_run']}T00:00:00.000'"})[0]["n"])),
    ("2025 tax lien final sale rows", raw["lien"], lambda: int(q("9rz4-mjek", {"$select": "count(*) as n", "$where": "month='2025-06-01T00:00:00.000' AND cycle='Final Sale'"})[0]["n"])),
    ("LotSmart distinct dated lot records", raw["lotsmart_requests"], lambda: int(q("r4c5-ndkx", {"$select": "count(distinct lotid) as n", "$where": "lotentrydate is not null"})[0]["n"])),
]
bad = 0
for name, built, fn in checks:
    live = fn(); tol = max(5, built * 0.01)
    ok = abs(live - built) <= tol
    print(f"{'OK ' if ok else 'BAD'} {name}: built {built:,} live {live:,}")
    bad += (not ok)
# internal consistency
L = json.load(open(os.path.join(HERE, "..", "data", "lots.json")))["lots"]
V = [r for r in L if r["k"] == "V"]
def chk(name, a, b):
    global bad
    ok = a == b; bad += (not ok); print(f"{'OK ' if ok else 'BAD'} {name}: {a:,} vs {b:,}")
chk("vacant lots in lots.json vs findings", len(V), F["counts"]["vacant_lots"])
chk("vacant with any signal", sum(1 for r in V if r["sc"] >= 1), F["counts"]["vacant_any_signal"])
chk("vacant 2+ agencies", sum(1 for r in V if r["sc"] >= 2), F["counts"]["vacant_2plus"])
chk("vacant 3+ agencies", sum(1 for r in V if r["sc"] >= 3), F["counts"]["vacant_3plus"])
chk("history lots", sum(1 for r in V if r.get("hist")), F["counts"]["hist_lots"])
chk("history lots with signal", sum(1 for r in V if r.get("hist") and r["sc"] >= 1), F["counts"]["hist_with_signal"])
chk("score equals length of agency list", sum(1 for r in L if r["sc"] != len(r["src"])), 0)
chk("every 311-scored lot carries 311 counts", sum(1 for r in L if ("311" in r["src"]) != bool(r.get("c311"))), 0)
chk("buildings count", sum(1 for r in L if r["k"] == "B"), F["counts"]["buildings"])
print("MISMATCHES:", bad)
sys.exit(1 if bad else 0)
