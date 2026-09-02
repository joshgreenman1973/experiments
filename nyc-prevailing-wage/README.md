# Paid on public work

Weekly certified payrolls filed with the New York State Department of Labor for
public construction in New York City, set against the city comptroller's
prevailing wage schedule trade by trade, with the state's public work
contractor registry alongside.

Live: https://joshgreenman1973.github.io/experiments/nyc-prevailing-wage/

## Sources

1. Certified Payroll Registration: Seven Year Window, data.ny.gov `w2zp-sf2x`
   (state Department of Labor). Holds 2026 only as of September 2026.
2. New York City Comptroller construction worker prevailing wage schedules,
   July 2025 to June 2026 and July 2026 to June 2027 (PDFs in `data/source/`).
3. Contractor Registry Certificate, data.ny.gov `i4jv-zkey`.
4. Non-Responsible Entities: Beginning 2019, data.ny.gov `jhxt-dfv6`.

## Rebuild

```
python3 fetch.py     # pulls the city-area payroll rows; fails if the portal returns nothing
python3 build.py     # parses the schedules, matches trades, writes data/*.json
```

The registry and non-responsible list are pulled by hand into `data/source/`
(the curl lines are in the methodology). The trade crosswalk lives in
`build.py` and is written out as `data/crosswalk.json`.

See `methodology.html` for the filters, the comparison test and what a
"below" result does not mean.
