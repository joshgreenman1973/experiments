# Indicator file schema

Every measure lives in `data/indicators/<id>.json`. The page build reads only these files,
`data/peers.json` and `data/registry.json`. Nothing on the page is typed by hand: every number is
read from these files when the page is built.

The edition is **New York in 2025**: use calendar 2025 (or the latest complete year if 2025 is not
out yet, labeled honestly). History matters: the build compares the latest year with the average of
the five years before it, and measures "typical year-to-year swing" over the ten years before that,
so get annual values back to at least 2010 wherever the source allows (2005 or earlier is better).

```json
{
  "id": "unemployment_rate",              // must match data/registry.json
  "status": "ok",                          // "ok" | "partial" | "missing"
  "status_reason": null,                   // required if not "ok": what failed and why, plainly
  "name": "Unemployment rate",
  "definition": "Share of the labor force without a job and looking for one, annual average, not seasonally adjusted.",
  "units": "percent",                      // "people" | "percent" | "dollars" | "years" | "per 100,000" | "minutes" | "count" | ...
  "format": "pct1",                        // how to print: "int" | "pct1" | "pct0" | "usd0" | "dec1" | "dec2" | "rate1"
  "better": "down",                        // "up" | "down" | "none" (none = no direction, e.g. population)
  "frequency": "annual",                   // the frequency of "series" below (always annual for the series)
  "series": [                              // New York City citywide, oldest first, ANNUAL values
    {"period": "2015", "value": 5.7, "moe": null}
  ],
  "latest_period": "2025",
  "latest_extra": {                        // optional: a more recent partial-year or monthly reading
    "period": "September 2026", "value": 5.2, "note": "monthly, not seasonally adjusted"
  },
  "source": {
    "name": "Bureau of Labor Statistics, Local Area Unemployment Statistics, series LAUCT365100000000003",
    "url": "https://data.bls.gov/timeseries/LAUCT365100000000003",   // a page a reader can open
    "endpoint": "https://api.bls.gov/publicAPI/v1/timeseries/data/LAUCT365100000000003",  // what the fetcher hit
    "fetched": "2026-11-16"
  },
  "peers": {                               // or null if no same-definition comparison exists
    "period": "2025",
    "geography": "city",                   // "city" | "county" | "metro" | "school district" | "continuum of care"
    "note": "Peers measured for the principal county, not the city, because ...",   // or null
    "source": {"name": "...", "url": "...", "endpoint": "...", "fetched": "2026-11-16"},
    "values": [ {"city": "Los Angeles", "value": 6.1, "moe": null, "geo_name": "Los Angeles city, California"} ]
  },
  "peer_series": null,                     // optional: {"Los Angeles": [{"period","value"}], ...} for the 4 named peers
  "breakdowns": [                          // optional, any number of groups
    {"by": "borough", "period": "2025", "source_url": "...",
     "values": [{"name": "Bronx", "value": 7.9, "moe": null}]}
  ],
  "method": "Plain-language description of exactly what was computed, with formulas, filters and exclusions.",
  "caveats": ["Plain-language caveat 1", "..."]
}
```

Rules:
- Never invent or estimate a value. If a number cannot be fetched from the source, leave it out and
  say so in `status_reason` / `caveats`. A file with `"status":"missing"` and an honest reason is
  far better than a guess.
- `moe` = the published 90% margin of error (ACS) or null.
- City names in `peers.values[].city` must match `name` in `data/peers.json` exactly.
- New York City itself should also appear in `peers.values` (as "New York") so it can be ranked.
- Each fetcher script must raise (exit non-zero) on an empty or failed download, never write empty data.
- Raw downloads are cached under `data/raw/<group>/` so the build can be rerun offline.
