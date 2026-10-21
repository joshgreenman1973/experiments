#!/usr/bin/env python3
"""Pull every BLS series the dashboard uses, straight from the BLS public API v2.

Writes data/raw/bls.json: {series_id: {"title":..., "obs": {"YYYY-MM": value}}}.
No key needed for this volume (3 requests); set BLS_API_KEY to raise limits.
"""
import json, os, sys, time, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/raw/bls.json"
START, END = 2019, 2026  # 2019 for the yearly May wage comparison

NY = "CUURS12A"  # CPI-U, New York-Newark-Jersey City, NY-NJ-PA, not seasonally adjusted
CPI_ITEMS = ["SA0", "SA0L1E", "SAF", "SAF1", "SAF11", "SAF111", "SAF112", "SEFJ", "SAF113",
             "SAF114", "SAF115", "SAF116", "SEFV", "SAH", "SAH1", "SEHA", "SEHC01",
             "SAH3", "SAA", "SAT", "SAT1", "SETA01", "SETA02", "SETB01", "SA0E",
             "SAM", "SAR", "SAE", "SEEB", "SAG", "SAS", "SAC"]
OTHER = [
    "CUUR0000SA0", "CUUR0000SEHA", "CUUR0000SAF11",       # U.S. city average, for comparison
    "APUS12A74714",                                      # NY-area regular gasoline, $/gal
    "APU010072610", "APU010072620", "APU010072511",      # Northeast electricity, piped gas, fuel oil
    "CUUR0100SEHF01", "CUUR0100SEHF02",                  # Northeast CPI electricity, utility gas
    "APU0100702111", "APU0100703112", "APU0100706111", "APU0100FF1101",
    "APU0100711211", "APU0100712112", "APU0100712311", "APU0100704111",
    "SMU36935610500000003", "SMU36935610500000011",      # CES New York City, total private AHE, AWE
]

def post(ids, use_key=True):
    body = {"seriesid": ids, "startyear": str(START), "endyear": str(END)}
    if use_key and os.environ.get("BLS_API_KEY"):
        body["registrationkey"] = os.environ["BLS_API_KEY"]
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=120))
    # A key that has hit its daily quota fails outright; the keyless tier still answers.
    if use_key and "registrationkey" in body and d.get("status") != "REQUEST_SUCCEEDED":
        return post(ids, use_key=False)
    return d

def main():
    ids = [NY + i for i in CPI_ITEMS] + OTHER
    out, missing = {}, []
    for k in range(0, len(ids), 25):
        chunk = ids[k:k + 25]
        d = post(chunk)
        if d.get("status") != "REQUEST_SUCCEEDED":
            sys.exit(f"BLS API refused: {d.get('message')}")
        for s in d["Results"]["series"]:
            obs = {}
            for x in s["data"]:
                if x["period"].startswith("M") and x["period"] != "M13" and x["value"] not in ("-", ""):
                    try:
                        obs[f"{x['year']}-{x['period'][1:]}"] = float(x["value"])
                    except ValueError:
                        pass
            if obs:
                out[s["seriesID"]] = {"obs": dict(sorted(obs.items()))}
            else:
                missing.append(s["seriesID"])
        time.sleep(1)
    if missing:
        print("no data:", missing)
    # An empty pull is a failure, never a silent pass.
    if len(out) < len(ids) * 0.9:
        sys.exit(f"only {len(out)} of {len(ids)} series returned; not writing")
    OUT.write_text(json.dumps({"fetched": time.strftime("%Y-%m-%d"), "series": out}, indent=1))
    latest = max(max(v["obs"]) for v in out.values())
    print(f"ok {len(out)} series, latest month {latest}")

if __name__ == "__main__":
    main()
