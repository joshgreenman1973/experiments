# Methodology

The full list of figures with their source URLs and verbatim quotes is published at `methodology.html` (built from `data/facts.json`). This file explains the rules behind it.

## Sourcing rule

Every number on the page had to come from a web page or PDF fetched during research on Sept. 6, 2026, with a verbatim quote copied from that page and stored beside the number. Figures that could not be fetched were dropped rather than estimated. Where the fetched source was secondary (a news report of an agency figure, a think-tank report citing city data, an encyclopedia list), the source line on the page says so and the confidence note on the methodology page explains it.

Research was done with Anthropic's Claude Code under the author's direction, using six parallel research passes (population, economy, Lower Manhattan, security and health, daily life, plus follow-ups). The raw output of each pass is in `research/`.

## Choosing "then" and "now"

"Then" is the figure closest to September 2001 that the source publishes. For census measures that is the 2000 census; for the Housing and Vacancy Survey it is 2002; for stop-and-frisk it is 2002, the first year recorded. The label under each number states the year.

"Now" is the most recent figure published as of early September 2026. Monthly series (jobs) use the latest month, flagged preliminary where the Bureau of Labor Statistics flags it. Annual series use 2025. Survey series use the latest survey year.

## Calculations

- Percent change is (now - then) / then, computed by the page script from the values shown. Where the ratio is 3 or more it is shown as a multiple.
- Percentage-point differences are shown for shares and rates.
- Dollar figures are nominal, in dollars of their own year, and the page marks them "nominal". No inflation adjustment is applied.
- Derived figures: the 2000 count of children under 18 is the sum of eight age cells from Census Summary File 1; the 2000 share of adults with a bachelor's degree sums eight degree cells from Summary File 3; the 2000 work-from-home share divides the 'worked at home' cell by all workers 16 and over; the 2025 airport total sums the three airports' published figures so it covers the same airports as 2001.
- The Asian, white, Black and Hispanic shares are computed from the census counts and totals in the API responses.

## Like-for-like check

Every pair was checked on Sept. 6, 2026 for a matching definition, universe and source series. Where the two ends came from different products (a decennial census count and an American Community Survey estimate; an executive budget proposal and an adopted budget; a Downtown Alliance figure drawn from a broker's report and a later one from Cushman & Wakefield), the label or the methodology page says so.

## Known limitations

- The 2000 and 2020 census race categories are close but not identical because of changes to the 2020 questionnaire.
- Rent is median contract rent (excluding utilities) in both the 2002 and 2023 Housing and Vacancy Survey findings.
- Lower Manhattan employment spans a 2018 change in how government jobs are counted.
- The NYPD's 2000 headcount peak comes from secondary sources that agree with each other (40,285 and 40,280) and with the City Comptroller's description of a required peak of 40,710.
- The count of buildings 1,000 feet or taller relies on a maintained encyclopedia list; the tall-buildings council's database could not be fetched.
- The fiscal 2002 budget figure is the April 2001 executive proposal, the last budget document before the attacks, rather than the total adopted in June 2001.
- Federal homeland security grants compare two awards (fiscal 2004 and fiscal 2024) to the same New York urban area. Fiscal 2025 is disputed between FEMA's published allocation and the state's account of what was issued, and fiscal 2026 is so far only a target allocation, so neither is used as the headline figure.
