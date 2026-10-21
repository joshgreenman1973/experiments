# What New York Costs

Prices in New York City and its metro area since the start of the year, compared
with the same months of the year before. Government sources throughout, except
Zillow's asking-rent index (labeled private) and Citi Bike's own posted price.

A draft tool, in two pages: `index.html` (prices) and `pay.html`, Keeping Up in
New York (pay and rent burden). Replaces the NYC Price Watch (`../nyc-price-watch`) and the price
side of the earlier NYC Affordability Index draft (`../vc-affordability-index`). See
`methodology.html` for the rules and why each source was chosen.

## Refresh

    sh scripts/refresh.sh

Pulls BLS (API v2, no key needed at this volume), EIA, FHFA and Zillow, rebuilds
`data/dashboard.json`, then runs `scripts/verify.py`, which fails if the category
contributions stop adding up to the all-items change, a headline number is
missing, a series is stale, or the page scripts do not parse. Do not publish on
a failed verify.

City-set prices live in `data/administered.json`. Add a step only when the
agency's own page confirms a change, with the URL and a quoted line.

## Yearly sources for the pay page

- `python3 scripts/fetch_oews.py <YY>`: BLS OEWS May wages for the metro area (spring).
- `python3 scripts/fetch_acs.py`: Census ACS 1-year rent burden for New York City
  (September/October). Needs CENSUS_API_KEY (Keychain on Josh's Mac).
- `data/burden_static.json`: Housing and Vacancy Survey figures and the five
  reference measures, entered by hand from each publisher's own report.
- Then `python3 scripts/build_pay.py && python3 scripts/verify.py`.

The old draft at vitalcity-nyc.github.io/nyc-affordability-index forwards here.

## Calendar

- BLS New York-area CPI: about mid-month for the prior month. Main monthly run
  goes after it.
- EIA gasoline: weekly (Mondays). EIA 861M (Con Edison): end of month, about
  10 weeks behind. FHFA: quarterly. Zillow: mid-month.
- January: the build needs BLS's December relative-importance table for the
  year just ended (posted with the January CPI in February). `extract_weights.py`
  downloads it and stops if it is not out yet.
- Rent Guidelines Board votes in June; MTA fare changes come with board votes;
  Water Board rates change July 1.

## Known gaps

- No October 2025 BLS data (shutdown); October 2026 twelve-month changes will not exist.
- ACS 2025 1-year (median contract rent, NYC) is scheduled for Oct. 29, 2026.
  Update the note in `data/administered.json` -> `rent_rules.acs`.
