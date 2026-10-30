# Beyond the Rent

What New York City households pay for electricity, gas heat, heating oil and water and sewer service, how those prices have moved against the rest of New York State and the nation, and what drives them. Official sources only.

Live: https://joshgreenman1973.github.io/experiments/nyc-beyond-the-rent/

## Refresh

    sh scripts/refresh.sh

Downloads BLS (API), EIA (EIA-861M, natural gas and heating oil series), NYSERDA (data.ny.gov rc94-5y2u) and NYISO (day-ahead zonal archives) into `data/raw/` (not in git; the first run rebuilds the archive, about 60 MB), then writes `data/dashboard.json`. The page builds its prose from that file.

Hand-collected records, each value with URL and verbatim quote:
- `research/water.json`: NYC Water Board rates FY1988-FY2027, typical bills, reasons, rental payment, assistance
- `research/coned.json`: PSC rate cases, Con Edison taxes, city-side utility revenue, dated events

Update those by hand when the Water Board adopts a new rate (June) or the PSC issues a rate order.

## Data timing
- EIA-861M utility data: about two months behind
- BLS: New York-area electricity and gas indexes and average prices end December 2024 (BLS cut them); rent and all items continue monthly
- NYSERDA heating oil: weekly October-March, monthly otherwise
- NYISO: daily

See `methodology.html` for every definition and calculation.
