#!/usr/bin/env python3
"""Yearly (May) all-occupations wages for the New York-Newark-Jersey City metro
area (MSA 35620) from BLS Occupational Employment and Wage Statistics.
Reads BLS's metro-area files (oesm<YY>ma.zip), keeps only the one row, and
writes data/oews.json. Run once a year after BLS's spring release."""
import io, json, pathlib, sys, urllib.request, zipfile
import openpyxl

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (research; josh.greenman@gmail.com)"}
OUT = ROOT / "data/oews.json"


def year_row(yy):
    url = f"https://www.bls.gov/oes/special-requests/oesm{yy}ma.zip"
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    # The metro file is MSA_M<YYYY>_dl.xlsx; skip Excel lock files ("~$...") BLS left in some archives.
    name = next(n for n in z.namelist() if n.rsplit("/", 1)[-1].upper().startswith("MSA_M"))
    raw = z.read(name)
    if raw[:2] == b"PK":  # a real .xlsx
        ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True).worksheets[0]
        rows = ws.iter_rows(values_only=True)
    else:  # older years ship old-format Excel, sometimes under an .xlsx name
        import pandas as pd
        df = pd.read_excel(io.BytesIO(raw), sheet_name=0, header=None, dtype=str)
        rows = iter(df.itertuples(index=False, name=None))
    hdr = [str(h).strip().upper() for h in next(rows)]
    ix = {h: i for i, h in enumerate(hdr)}
    for r in rows:
        if str(r[ix["AREA"]]).strip() == "35620" and str(r[ix["OCC_CODE"]]).strip() == "00-0000":
            g = lambda k: r[ix[k]]
            return {"year": 2000 + int(yy), "median_hourly": float(g("H_MEDIAN")), "mean_hourly": float(g("H_MEAN")),
                    "median_annual": float(g("A_MEDIAN")), "employment": int(float(g("TOT_EMP"))), "file": url}
    sys.exit(f"MSA 35620 all-occupations row not found in {url}")


def main():
    years = sys.argv[1:] or ["19", "20", "21", "22", "23", "24", "25"]
    old = json.loads(OUT.read_text())["years"] if OUT.exists() else {}
    for yy in years:
        r = year_row(yy)
        old[str(r["year"])] = r
        print(r["year"], r["median_hourly"], r["mean_hourly"])
    OUT.write_text(json.dumps({"source": "BLS Occupational Employment and Wage Statistics, May estimates, New York-Newark-Jersey City, NY-NJ-PA metropolitan area, all occupations",
                               "url": "https://www.bls.gov/oes/tables.htm", "years": dict(sorted(old.items()))}, indent=1))


if __name__ == "__main__":
    main()
