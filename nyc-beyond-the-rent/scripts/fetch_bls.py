#!/usr/bin/env python3
"""Pull the BLS series behind Beyond the Rent from the BLS public API v2.

CPI-U (not seasonally adjusted) for the New York metro area, the Northeast region
and the U.S. city average, plus BLS average prices per kWh / therm / gallon.
Writes data/raw/bls.json: {"series": {id: {"YYYY-MM": value}}}.
Keyless tier: 25 series and 10 years per request, so the pull runs in windows.
"""
import json, os, sys, time, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/raw/bls.json"
WINDOWS = [(1997, 2006), (2007, 2016), (2017, 2026)]

AREAS = {"S12A": "New York metro", "0100": "Northeast", "0000": "U.S. city average"}
ITEMS = ["SA0", "SEHA", "SA0E", "SAH2", "SAH21", "SEHF", "SEHF01", "SEHF02",
         "SEHE", "SEHE01", "SEHG", "SEHG01", "SEHG02"]
AP = ["APUS12A72610", "APUS12A72620", "APU010072610", "APU010072620",
      "APU000072610", "APU000072620", "APU010072511", "APU000072511",
      # electricity per kWh in other large metros, for the city comparison
      "APUS11A72610", "APUS12B72610", "APUS35A72610", "APUS35E72610",
      "APUS35B72610", "APUS35C72610", "APUS35D72610", "APUS23A72610",
      "APUS24A72610", "APUS37A72610", "APUS49A72610", "APUS49B72610",
      "APUS49D72610", "APUS48A72610", "APUS23B72610", "APUS48B72610"]


def post(ids, y0, y1):
    body = {"seriesid": ids, "startyear": str(y0), "endyear": str(y1)}
    if os.environ.get("BLS_API_KEY"):
        body["registrationkey"] = os.environ["BLS_API_KEY"]
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def main():
    ids = [f"CUUR{a}{i}" for a in AREAS for i in ITEMS] + AP
    out = {i: {} for i in ids}
    for y0, y1 in WINDOWS:
        for k in range(0, len(ids), 25):
            d = post(ids[k:k + 25], y0, y1)
            if d.get("status") != "REQUEST_SUCCEEDED":
                sys.exit(f"BLS API refused: {d.get('message')}")
            for s in d["Results"]["series"]:
                for x in s["data"]:
                    if x["period"].startswith("M") and x["period"] != "M13":
                        try:
                            out[s["seriesID"]][f"{x['year']}-{x['period'][1:]}"] = float(x["value"])
                        except ValueError:
                            pass
            time.sleep(1)
    empty = [i for i, v in out.items() if not v]
    have = {i: dict(sorted(v.items())) for i, v in out.items() if v}
    if len(have) < len(ids) * 0.6:
        sys.exit(f"only {len(have)} of {len(ids)} series returned; not writing")
    OUT.write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "empty": empty, "series": have}))
    for i, v in have.items():
        ks = list(v)
        print(f"{i:16s} {ks[0]} -> {ks[-1]}  n={len(ks)}")
    print("EMPTY:", empty)


if __name__ == "__main__":
    main()
