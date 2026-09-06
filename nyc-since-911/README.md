# 25 ways New York City has changed since 9/11

An infographic comparing New York City in September 2001 with the latest published figures, for the 25th anniversary of the attacks. Twenty-five paired measures across people, work and money, Lower Manhattan, security and the toll, and daily life, plus a timeline of the World Trade Center site.

Live: https://joshgreenman1973.github.io/experiments/nyc-since-911/

## Files

- `index.html` is built. Do not edit it by hand.
- `build/template.html` holds the page markup, styles and rendering script.
- `data/facts.json` is the source of truth: every figure, its label, its source URL and the verbatim quote from that page.
- `build/build.mjs` inlines the data into the template and writes `index.html` and `methodology.html`. Run `node build/build.mjs` after editing the data or the template. It refuses to build unless there are exactly 25 items.
- `research/*.json` are the raw research files, one per theme, with every candidate figure fetched during research, including those not used.
- `METHODOLOGY.md` explains sourcing rules and calculations.

## Design

Deliberately its own system rather than the house style: white ground, black rules, Barlow Condensed numerals, and the blue and orange of the New York City flag standing for 2001 and the latest figure.
