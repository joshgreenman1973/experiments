#!/usr/bin/env python3
"""Download the non-BLS raw files into data/raw/: EIA-861M (current-year utility file and
state totals), EIA price series (natural gas, heating oil), NYSERDA weekly heating oil
and the latest NYISO day-ahead zonal archives. Older EIA-861M and NYISO files are
already in data/raw and do not change.

A download that comes back as an error page or near-empty stops the script.
"""
import datetime as dt, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
UA = {"User-Agent": "Mozilla/5.0 (Beyond the Rent data refresh)"}
YEAR = dt.date.today().year


def get(url, dest, min_bytes=5000):
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()
    if len(data) < min_bytes or data[:15].lower().startswith(b"<!doctype html"):
        sys.exit(f"bad download ({len(data)} bytes) from {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print("ok", dest.relative_to(ROOT), len(data))


E = "https://www.eia.gov/electricity/data/eia861m"
# Final-year archives (kept out of git): fetched once if missing.
for y in range(2010, YEAR - 1):
    name = f"f826{y}.xls" if y <= 2016 else f"retail_sales_{y}.xlsx" if y <= 2020 else f"sales_ult_cust_{y}.xlsx"
    if not (RAW / "eia861m" / name).exists():
        get(f"{E}/archive/xls/{name}", RAW / "eia861m" / name)
y, m = 2010, 1
while (y, m) < (dt.date.today().year, dt.date.today().month - 2):
    k = f"{y}{m:02d}01"
    if not (RAW / "nyiso" / f"{k}.zip").exists():
        get(f"https://mis.nyiso.com/public/csv/damlbmp/{k}damlbmp_zone_csv.zip", RAW / f"nyiso/{k}.zip", 2000)
    m += 1
    if m > 12:
        y, m = y + 1, 1
get(f"{E}/xls/sales_revenue.xlsx", RAW / "sales_revenue.xlsx")
get(f"{E}/xls/sales_ult_cust_{YEAR}.xlsx", RAW / f"eia861m/sales_ult_cust_{YEAR}.xlsx")
# In January the prior year's file moves to the archive with its final numbers.
try:
    get(f"{E}/archive/xls/sales_ult_cust_{YEAR - 1}.xlsx", RAW / f"eia861m/sales_ult_cust_{YEAR - 1}.xlsx")
except Exception as ex:
    print("prior-year archive not available yet:", ex)

for s in ["N3010NY3m", "N3010US3m", "N3050NY3m", "RNGWHHDm", "N3010NJ3m"]:
    get(f"https://www.eia.gov/dnav/ng/hist_xls/{s}.xls", RAW / f"{s}.xls")
for s in ["W_EPD2F_PRS_SNY_DPGw", "W_EPD2F_PRS_NUS_DPGw", "W_EPD2F_PRS_R10_DPGw", "EER_EPD2F_PF4_Y35NY_DPGm"]:
    get(f"https://www.eia.gov/dnav/pet/hist_xls/{s}.xls", RAW / f"{s}.xls")
get("https://data.ny.gov/resource/rc94-5y2u.csv?$limit=50000", RAW / "nyserda_heating_oil.csv")

today = dt.date.today()
for back in range(3):
    m = today.month - back
    y = today.year
    while m < 1:
        m += 12
        y -= 1
    k = f"{y}{m:02d}01"
    get(f"https://mis.nyiso.com/public/csv/damlbmp/{k}damlbmp_zone_csv.zip", RAW / f"nyiso/{k}.zip", 2000)
