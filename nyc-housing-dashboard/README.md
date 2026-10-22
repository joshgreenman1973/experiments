# Who builds New York

Every New York City Council district and community district, measured by the net homes it added since 2010, the income-restricted homes the city financed since 2014, and the city's draft 2030 housing targets. A New York version of A City That Works' Chicago housing dashboard.

- `scripts/fetch.py` downloads the inputs into `data/raw/` (not committed). Needs `CENSUS_API_KEY` in the environment or the macOS Keychain.
- `scripts/build.py` writes `data/dashboard.json`, the district shapes and `data/hpd_buildings.csv`, and stops if a check fails.
- `research/` holds the targets read from the draft report and the Council member list.
- `docs/how-i-built-this.html` explains every source, calculation and judgment call.

Refresh when City Planning releases a new Housing Database version (quarterly) or the final targets come out.
