# Report card

A searchable explorer of New York City's Mayor's Management Report, FY2016–2026. It includes a direction-aware scoreboard, agency pages, indicator search, outlier measures, curated ratios, and retired indicators. Static HTML, CSS and JavaScript; no frontend framework.

## Sources and interpretation

- [Agency performance indicators](https://data.cityofnewyork.us/City-Government/Mayor-s-Management-Report-Agency-Performance-Indica/rbed-zzin): June year-to-date rows supply annual slots. Reporting periods can be fiscal, calendar or school year.
- [FY2026 MMR](https://www.nyc.gov/assets/operations/downloads/pdf/mmr2026/2026_mmr.pdf): matched annual values, printed historical values, desired directions, and numeric or directional targets.
- [MMR resources](https://data.cityofnewyork.us/resource/4qmi-txnk.json) and [PMMR resources](https://data.cityofnewyork.us/resource/nvzu-6t9y.json): final prior-year PMMR actuals supersede provisional MMR actuals. Plans are not treated as actuals.

Historical PDF values are used alongside FY2026 to avoid mixing publication vintages within the printed five-year span. Differing original Open Data values are retained in each record's `pdf.original` and displayed in the drawer. When a completed annual Open Data value becomes available, it takes priority over the PDF fallback. Source precedence is explicit; future upstream changes still need review.

Matching is primarily numerical, with name-based disambiguation and a constrained restatement pass. Five larger DOB revisions have a reviewed mapping, checked against both old and revised histories from PDF page 375. No match means “not extracted,” not “absent from the report.” PDF page links use the PDF index rather than printed numbering.

The [method page](methodology.html) explains scoring and limitations. [AUDIT.md](AUDIT.md) records fixes, evidence, and proposed next features, including a review of the ratios. The original prompt history was context, not an executable specification.

## Build

Requires Python 3 and `pypdf`; Node.js is used for frontend regression assertions. Generated JSON is committed; raw downloads under `build/raw/` are ignored.

```sh
python3 -m pip install pypdf
python3 build/fetch.py
python3 build/transform.py
python3 build/pdf2026.py             # use --refresh to download the PDF again
python3 build/transform.py
python3 build/ratios.py
python3 -m unittest discover -s tests -v
node tests/test_app.cjs
```

Run from this directory. The first transformation supplies the matching index (including on a clean bootstrap). If a generated PDF overlay exists, it may be used provisionally at that step; the second transformation uses the refreshed overlay. PDF matching restores original Open Data history before matching again, so rerunning the pipeline does not progressively match against its own revisions.

`fetch.py` downloads to temporary files and replaces a snapshot only when its row count matches the count obtained before download. `pdf2026.py` caches the PDF unless refreshed and caches extracted text by PDF checksum. `transform.py` records build time and source row count. It selects metadata using fiscal year and observation date, and retains desired direction by year.

## Validation and rules

- Equal values stay unchanged even with a zero threshold.
- Missing or flagged values, zero percentage baselines and documented definition breaks are not scored.
- Flagged observations are displayed but excluded from derived statistics.
- Streaks and biggest annual steps require consecutive years. Percentage-point rankings compare percentage units only.
- Ratio components require known matching period types and consecutive overlapping years. True shares are bounded by 0–100%; flow comparisons are not.
- Final resource actuals use the PMMR's `previous_fy_actual` and the previous fiscal year, not its current-year budget plans.
- Numeric targets, directional targets and extraction gaps remain distinct.

The tests cover real regressions and representative published records. They are not a certification of every PDF row's identity, every source definition, or every publication's accuracy. Numerical equality alone cannot establish semantic comparability.

## Local preview

```sh
python3 -m http.server 8765
```

Then open `http://localhost:8765/`. Comparison years, threshold and filters are encoded in the URL for reproducible links. Indicator drawers support keyboard focus containment and restoration.
