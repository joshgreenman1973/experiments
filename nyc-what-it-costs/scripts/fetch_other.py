#!/usr/bin/env python3
"""Pull the non-BLS series: EIA (gasoline, heating oil, Con Edison electricity),
FHFA house prices and Zillow's observed rent index. Writes data/other_series.json.

Each series is stored as monthly (or quarterly) values keyed "YYYY-MM" ("YYYY-Qn"),
plus the source URL. A source that fails to download stops the script: an empty
or partial pull is never written over good data.
"""
import csv, io, json, pathlib, sys, urllib.request
from collections import defaultdict

import openpyxl
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
UA = {"User-Agent": "Mozilla/5.0 (research; josh.greenman@gmail.com)"}


def get(url, dest):
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=180).read()
    if len(data) < 2000:
        sys.exit(f"suspiciously small download from {url}")
    (RAW / dest).write_bytes(data)
    return RAW / dest


def eia_weekly(url, dest):
    f = get(url, dest)
    d = pd.read_excel(f, sheet_name="Data 1", header=None, skiprows=3)
    d.columns = ["d", "v"]
    d["d"] = pd.to_datetime(d["d"])
    d = d.dropna()
    monthly = {}
    for p, g in d.groupby(d.d.dt.to_period("M")):
        monthly[str(p)] = {"v": round(float(g.v.mean()), 4), "weeks": int(len(g))}
    last = d.iloc[-1]
    # Same week a year earlier: the reading 52 weeks (364 days) before the latest one.
    prior = d[d.d == last.d - pd.Timedelta(days=364)]
    lw = {"date": last.d.strftime("%Y-%m-%d"), "v": float(last.v)}
    if len(prior):
        lw["year_ago"] = {"date": prior.iloc[0].d.strftime("%Y-%m-%d"), "v": float(prior.iloc[0].v)}
    return monthly, lw


def coned():
    """EIA-861M: Consolidated Edison Co-NY (utility 4226), residential, full-service
    customers only (EIA withholds delivery-only rows monthly). Cents per kWh =
    revenue / sales."""
    out = {}
    files = [("https://www.eia.gov/electricity/data/eia861m/archive/xls/sales_ult_cust_2024.xlsx", "eia861m_2024.xlsx"),
             ("https://www.eia.gov/electricity/data/eia861m/archive/xls/sales_ult_cust_2025.xlsx", "eia861m_2025.xlsx"),
             ("https://www.eia.gov/electricity/data/eia861m/xls/sales_ult_cust_2026.xlsx", "eia861m_2026.xlsx")]
    for url, dest in files:
        f = get(url, dest)
        ws = openpyxl.load_workbook(f, read_only=True).worksheets[0]
        hdr_seen = False
        for r in ws.iter_rows(values_only=True):
            # Columns: Year, Month, Utility Number, Utility Name, State, Part, Service Type,
            # then RESIDENTIAL Revenue (thousand $), Sales (MWh), Customers.
            if r[2] == 4226 and r[4] == "NY" and isinstance(r[7], (int, float)) and r[8]:
                hdr_seen = True
                out[f"{int(r[0])}-{int(r[1]):02d}"] = {
                    "v": round(r[7] / r[8] * 100, 3), "rev_k": r[7], "mwh": r[8], "cust": r[9],
                    "service": r[6]}
        if not hdr_seen:
            sys.exit(f"Con Edison rows not found in {dest}; layout may have changed")
    return dict(sorted(out.items()))


def fhfa():
    f = get("https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv", "hpi_master.csv")
    out = defaultdict(dict)
    with open(f, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["place_id"] == "35614" and r["frequency"] == "quarterly":
                key = f"{r['yr']}-Q{r['period']}"
                out[f"{r['hpi_flavor']}|{r['index_nsa'] and 'nsa'}"][key] = float(r["index_nsa"]) if r["index_nsa"] else None
    po = out.get("purchase-only|nsa") or {}
    at = out.get("all-transactions|nsa") or {}
    if not po and not at:
        sys.exit("FHFA: metro division 35614 not found")
    return {"purchase_only_nsa": dict(sorted(po.items())), "all_transactions_nsa": dict(sorted(at.items()))}


def zori():
    f = get("https://files.zillowstatic.com/research/public_csvs/zori/City_zori_uc_sfrcondomfr_sm_month.csv", "zori_city.csv")
    with open(f, newline="") as fh:
        r = csv.reader(fh)
        h = next(r)
        for row in r:
            if row[2] == "New York" and row[5] == "NY" and row[3] == "city":
                return {c[:7]: round(float(v), 2) for c, v in zip(h[8:], row[8:]) if v}
    sys.exit("ZORI: New York city row not found")


def main():
    gas, gas_last = eia_weekly("https://www.eia.gov/dnav/pet/hist_xls/EMM_EPMR_PTE_Y35NY_DPGw.xls", "eia_gas_nyc.xls")
    oil, oil_last = eia_weekly("https://www.eia.gov/dnav/pet/hist_xls/W_EPD2F_PRS_SNY_DPGw.xls", "eia_heating_oil_ny.xls")
    out = {
        "gas_nyc": {"source": "EIA, New York City regular gasoline retail price, weekly (EMM_EPMR_PTE_Y35NY_DPG); monthly = average of the weeks",
                    "url": "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPMR_PTE_Y35NY_DPG&f=W",
                    "unit": "$/gal", "monthly": {k: v for k, v in gas.items() if k >= "2023-12"}, "last_week": gas_last},
        "heating_oil_ny": {"source": "EIA, New York State residential No. 2 heating oil, weekly, heating season only (W_EPD2F_PRS_SNY_DPG)",
                           "url": "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=W_EPD2F_PRS_SNY_DPG&f=W",
                           "unit": "$/gal", "monthly": {k: v for k, v in oil.items() if k >= "2023-10"}, "last_week": oil_last},
        "coned": {"source": "EIA-861M, Consolidated Edison Co-NY, residential revenue divided by residential sales, full-service customers",
                  "url": "https://www.eia.gov/electricity/data/eia861m/", "unit": "cents/kWh", "monthly": coned()},
        "fhfa": {"source": "FHFA House Price Index, New York-Jersey City-White Plains, NY-NJ metropolitan division (35614), not seasonally adjusted",
                 "url": "https://www.fhfa.gov/data/hpi/datasets", **fhfa()},
        "zori": {"source": "Zillow Observed Rent Index, New York city, all homes plus multifamily, smoothed (private source)",
                 "url": "https://www.zillow.com/research/data/", "unit": "$/month", "monthly": zori()},
    }
    (ROOT / "data/other_series.json").write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        m = v.get("monthly") or v.get("purchase_only_nsa")
        print(k, "latest", max(m), "n", len(m))


if __name__ == "__main__":
    main()
