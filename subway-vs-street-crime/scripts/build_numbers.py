"""Every number on the page, computed in one place.

Inputs (all in ../data, pulled by the other scripts):
  complaints_by_premise.json  NYPD complaints by year/offense/premise/jurisdiction
  cms_walking.json            2024 Citywide Mobility Survey walking inputs
  multipliers.json            precinct multipliers
Hard-coded inputs below carry their source in a comment.

Run: python3 -I scripts/build_numbers.py   -> prints a report, writes data/model.json
"""
import json, math, pathlib

D = pathlib.Path(__file__).resolve().parent.parent / "data"
rows = json.load(open(D / "complaints_by_premise.json"))["rows"]
cms = json.load(open(D / "cms_walking.json"))["all_days"]
mult = json.load(open(D / "multipliers.json"))

# ---------- crime definitions ----------
VIOLENT = {"MURDER & NON-NEGL. MANSLAUGHTER", "RAPE", "ROBBERY", "FELONY ASSAULT"}
PROPERTY = {"BURGLARY", "GRAND LARCENY", "GRAND LARCENY OF MOTOR VEHICLE"}
MISD_ASSAULT = "ASSAULT 3 & RELATED OFFENSES"
TRANSIT = "N.Y. TRANSIT POLICE"  # reproduces Vital City's 2023 subway count (1,120) exactly
PUBLIC = {  # street and other public outdoor places; reproduces 16,079 to within 20
    "STREET", "PARK/PLAYGROUND", "PARKING LOT/GARAGE (PUBLIC)", "PARKING LOT/GARAGE (PRIVATE)",
    "HIGHWAY/PARKWAY", "OPEN AREAS (OPEN LOTS)", "BUS STOP", "BRIDGE", "MARINA/PIER",
}


def count(year, offenses, where):
    return sum(r["n"] for r in rows if r["year"] == year and r["ofns"] in offenses and where(r))


def crimes(year):
    sub = lambda r: r["juris"] == TRANSIT
    pub = lambda r: r["juris"] != TRANSIT and r["prem"] in PUBLIC
    v = (count(year, VIOLENT, sub), count(year, VIOLENT, pub))
    m = (count(year, {MISD_ASSAULT}, sub), count(year, {MISD_ASSAULT}, pub))
    i = (count(year, VIOLENT | PROPERTY, sub), count(year, VIOLENT | PROPERTY, pub))
    return {"violent": v, "violent_plus": (v[0] + m[0], v[1] + m[1]), "misd_assault": m, "all": i,
            "violent_citywide": count(year, VIOLENT, lambda r: True),
            "misd_citywide": count(year, {MISD_ASSAULT}, lambda r: True),
            "index_citywide": count(year, VIOLENT | PROPERTY, lambda r: True),
            "subway_robbery": count(year, {"ROBBERY"}, sub), "subway_fel_assault": count(year, {"FELONY ASSAULT"}, sub),
            "public_robbery": count(year, {"ROBBERY"}, pub), "public_fel_assault": count(year, {"FELONY ASSAULT"}, pub)}


# ---------- subway exposure ----------
# MTA Daily Ridership and Traffic (data.ny.gov sayj-mze2), mode = Subway, summed by year
PAID = {2023: 1_150_217_108, 2025: 1_282_466_281}
# MTA NYCT Subway Fare Evasion (data.ny.gov 6kj3-ijvb), mean of the four quarterly rates
EVASION = {2023: (0.111 + 0.123 + 0.140 + 0.133) / 4, 2025: (0.098 + 0.099 + 0.110 + 0.101) / 4}
MIN_PER_TRIP = 40  # 30 on the train + 10 on platforms and stairs (Vital City); CMS 2024 measures ~42


def subway_hours(year):
    trips = PAID[year] / (1 - EVASION[year])
    return trips, trips * MIN_PER_TRIP / 60


# ---------- street exposure ----------
RESIDENTS = {2023: 8_300_000, 2025: 8_585_000}  # 2023: Vital City; 2025: DCP, Census Vintage 2025 (July 1)
COMMUTERS = 1_000_000  # Vital City's "over 1 million" daily commuters (not refreshed)
TOURISTS = 200_000     # Vital City; not refreshed
# Original Method 1 inputs (2023 version of the page)
ORIG_TRIPS_PER_DAY = (2.5 * 5 + 2.3 * 2) / 7
ORIG_WALK_SHARE = 0.41
ORIG_WALK_MIN = 20


def street_hours(year):
    pop = RESIDENTS[year] + COMMUTERS + TOURISTS
    if year == 2023:
        trips, share, mins = ORIG_TRIPS_PER_DAY, ORIG_WALK_SHARE, ORIG_WALK_MIN
    else:  # 2024 Citywide Mobility Survey, adults, all days of the week
        trips, share, mins = (cms["linked_trips_per_adult_day"], cms["walk_only_share_of_linked_trips"],
                              cms["walk_only_mean_minutes"])
    m1 = pop * trips * share * mins / 60 * 365
    # Method 2: 45 min/day residents (every day), 30 min commuters (250 workdays), 120 min tourists
    m2_raw = RESIDENTS[year] * 45 / 60 * 365 + COMMUTERS * 30 / 60 * 250 + TOURISTS * 120 / 60 * 365
    m2 = m2_raw * 0.70
    # Method 3: 24 - 8 sleep - 8.5 work/school - 4.5 home awake - 0.7 transit = 2.3 h "other"
    other = 24 - 8.0 - 8.5 - 4.5 - 0.7
    m3_raw = pop * other * 0.60 * 365
    m3 = (m3_raw * 0.30, m3_raw * 0.45)
    central = (m1 + m2 + sum(m3) / 2) / 3
    return {"pop": pop, "m1_inputs": (trips, share, mins), "m1": m1, "m2_raw": m2_raw, "m2": m2,
            "m3_other": other, "m3_raw": m3_raw, "m3": m3, "central": central,
            "low": min(m1, m2, m3[0]), "high": max(m1, m2, m3[1])}


def risk(rate_per_hour, hours):
    return 1 - (1 - rate_per_hour) ** hours


out = {}
for y in (2023, 2025):
    c = crimes(y)
    trips, sh = subway_hours(y)
    st = street_hours(y)
    S = round(sh / 1e6)        # subway, millions of person-hours (rounded as shown on page)
    T = round(st["central"] / 1e7) * 10  # street, millions, rounded to nearest 10M
    rates = {}
    for k in ("violent", "violent_plus", "all"):
        s_rate, t_rate = c[k][0] / S, c[k][1] / T
        rates[k] = {"subway": s_rate, "street": t_rate, "ratio": t_rate / s_rate}
    v = rates["violent"]
    sens = {h: (c["violent"][1] / h) / v["subway"] for h in (1000, 1200, 1500, T, 2200, 3000)}
    breakeven = c["violent"][1] / v["subway"]  # millions of hours
    calc = {
        "subway_5h": risk(c["violent"][0] / (S * 1e6), 5 * 52),
        "street_10h": risk(c["violent"][1] / (T * 1e6), 10 * 52),
        "street_10h_mott": risk(c["violent"][1] / (T * 1e6) * mult["2025_violent"]["hoods"]["mott_haven"]["mult"], 10 * 52),
    }
    out[y] = {"crimes": c, "subway_trips": trips, "subway_hours_exact": sh, "S": S, "street": st, "T": T,
              "rates": rates, "sensitivity": sens, "breakeven_mh": breakeven,
              "breakeven_hrs_per_person_week": breakeven * 1e6 / 52 / st["pop"],
              "minutes_equiv": 60 / v["ratio"], "subway_share": c["violent"][0] / sum(c["violent"]),
              "calc": calc}

if __name__ == "__main__":
    for y, o in out.items():
        c, st = o["crimes"], o["street"]
        print(f"===== {y}")
        print(f" crimes subway/street  violent {c['violent']}  +misd {c['violent_plus']} (misd {c['misd_assault']})  index {c['all']}")
        print(f" citywide violent {c['violent_citywide']}  misd {c['misd_citywide']}  index {c['index_citywide']}")
        print(f" subway mix: robbery {c['subway_robbery']} fel.asslt {c['subway_fel_assault']}  "
              f"street mix: robbery {c['public_robbery']} fel.asslt {c['public_fel_assault']}")
        print(f" subway share of public violent {o['subway_share']:.4f}")
        print(f" subway trips {o['subway_trips']:,.0f} (evasion {EVASION[y]:.5f})  hours {o['subway_hours_exact']:,.0f} -> S={o['S']}M")
        print(f" pop {st['pop']:,}  M1 inputs {tuple(round(x, 4) for x in st['m1_inputs'])}")
        print(f" M1 {st['m1']:,.0f}  M2 raw {st['m2_raw']:,.0f} adj {st['m2']:,.0f}  M3 raw {st['m3_raw']:,.0f} -> {st['m3'][0]:,.0f}-{st['m3'][1]:,.0f}")
        print(f" central {st['central']:,.0f} -> T={o['T']}M  low {st['low']:,.0f} high {st['high']:,.0f}")
        for k, r in o["rates"].items():
            print(f"  {k:13s} subway {r['subway']:.4f}  street {r['street']:.4f}  ratio {r['ratio']:.3f}")
        print("  sensitivity", {h: round(x, 2) for h, x in o["sensitivity"].items()})
        print(f"  breakeven {o['breakeven_mh']:,.0f}M hrs = {o['breakeven_hrs_per_person_week']:.1f} hrs/person/week;"
              f" minutes-equivalent {o['minutes_equiv']:.2f}")
        print("  calc", {k: f"{v*100:.4f}% (1 in {round(1/v):,})" for k, v in o["calc"].items()})
    (D / "model.json").write_text(json.dumps({str(k): v for k, v in out.items()}, indent=1, default=list))
