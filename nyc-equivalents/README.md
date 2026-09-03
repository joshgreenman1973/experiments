# New York City equivalents

One New York City figure at a time, paired with the country, city, army, fleet or structure somewhere else in the world that comes in at about the same number. A world map pins where each equivalent lives; a ledger below draws each pair as two bars so the closeness of the match is visible.

- `index.html`: the graphic. Loads `data/world.json` and `data/pairings.json`.
- `methodology.html`: every pairing with both source URLs, the verbatim quote from each page, years, ratio, confidence and caveats, plus the blind fact-check.
- `build/research/*.json`: raw research output by realm, each row with URL and verbatim quote.
- `build/curate.py`: the curated list (sentence, place, pin, displays, methodology note) drawing numbers and quotes from the research files. Writes `build/pairings-src.json`.
- `build/assemble.mjs`: projects pins with the same Natural Earth I projection as the map, computes ratios and gaps, writes `data/pairings.json`.
- `build/methodology.mjs`: writes `methodology.html` from `pairings-src.json` and `build/factcheck.json`.
- `build/world.mjs`: projects Natural Earth 110m countries (world-atlas) to SVG paths in `data/world.json`.

Rebuild:

```
cd build && python3 curate.py && node assemble.mjs && node methodology.mjs
```

Loads `../house-style/house.css` from the Experiments repo.
