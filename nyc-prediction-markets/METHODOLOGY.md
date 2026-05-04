# NY prediction markets tracker — methodology

## What this is

A consolidated view of every active prediction market touching New York City or New York State politics and policy, refreshed every six hours via GitHub Actions.

## Data sources

All three are public APIs, no authentication required.

| Source | Endpoint | Pagination | Pricing |
|---|---|---|---|
| Polymarket | `https://gamma-api.polymarket.com/markets?closed=false` | `limit` + `offset`, capped at 20 pages × 500 | `outcomePrices` (decimal, JSON-encoded) |
| Kalshi | `https://api.elections.kalshi.com/trade-api/v2/events?status=open&with_nested_markets=true` | `cursor`, capped at 60 pages × 200 | `last_price_dollars` (decimal string) |
| Manifold | `https://api.manifold.markets/v0/search-markets?term=…` | per-keyword search × 22 queries | `probability` (decimal) |

Polymarket and Kalshi are real-money venues; their volumes are USD. Manifold is play-money — its volumes are mana ("M") and shouldn't be compared dollar-for-dollar.

## Filter logic — `matchesNY()` in `fetch.mjs`

A market qualifies if its title, subtitle, event title, or category text matches one of three buckets, **and** does not match any sports/entertainment/weather exclusion.

### Strong keywords (any match qualifies)

People: Mamdani, Hochul, Cuomo, Letitia James, Tish James, Jumaane Williams, Brad Lander, Zellnor Myrie, Scott Stringer, Ritchie Torres, Dan Goldman, Jessica Ramos, Curtis Sliwa, Sliwa, Stefanik, Gillibrand, Schumer, Ocasio-Cortez, AOC.

Places / offices: New York City, NYC, New York State, NY governor, NY-Gov, NY Senate, Albany, Bronx, Brooklyn, Queens DA, Manhattan DA.

Topics: MTA, NYPD, Rikers, congestion pricing, City Hall, rent stabilization.

### Ambiguous tokens (require co-occurring NY context)

To avoid false positives like Amy Adams / John Adams / LeBron James / Knicks games:

| Token | Required context |
|---|---|
| Adams | "mayor", "Eric Adams", "City Hall" |
| Lander | "comptroller", "mayor", "Brad Lander" |
| Stringer | "comptroller", "Scott Stringer" |
| James | "Letitia", "Tish", "attorney general" |
| Williams | "Jumaane", "public advocate" |

Note: "James" deliberately excludes "New York" from its context — otherwise every NBA game involving LeBron + a New York team would qualify.

### Hard exclusions

A market is rejected outright if its text matches any of:

Knicks, Yankees, Mets, Giants, Jets, Rangers, Nets, Islanders, Liberty, Red Bulls, NYCFC, New York City FC, NY/NYC Marathon, MLS Cup, MLB, NBA, NHL, NFL, UFC, WNBA, NCAA, Champions League, Premier League, Bundesliga, La Liga, Super Bowl, World Series, Stanley Cup, Final Four, Eurovision, Oscars, Grammys, Emmys, box office, temperature, rainfall, snowfall, "inches of rain/snow".

Kalshi event tickers starting with `KXNFL`, `KXNBA`, `KXNHL`, `KXMLB`, `KXSOCCER`, `KXMVE…`, `KXUFC`, `KXTENNIS`, `KXGOLF`, `KXOSCAR`, `KXGRAMM`, `KXEMMY` are skipped before keyword matching.

### Tag-based catch-all

Polymarket events sometimes have a parent event title like "New York City Mayoral Election 2025" — those qualify even if the per-market question doesn't mention NYC by name. Same for Kalshi `category` and Manifold `groupSlugs` containing "new york".

## Schema (`data/markets.json`)

```jsonc
{
  "updated_at": "2026-05-04T18:00:00Z",
  "source_counts": { "polymarket": 35, "kalshi": 146, "manifold": 134 },
  "markets": [
    {
      "source": "polymarket" | "kalshi" | "manifold",
      "id": "platform-native id",
      "question": "Will Mamdani freeze NYC rents before 2027?",
      "url": "https://polymarket.com/event/...",
      "yes_price": 0.27,            // decimal probability for the Yes contract
      "volume_usd": 253802,         // null for Manifold (play-money)
      "volume_mana": null,          // populated only for Manifold
      "liquidity_usd": null,
      "open_interest_usd": null,
      "close_date": "2027-01-01T00:00:00Z",
      "matched_keywords": ["Mamdani"],
      "price_24h_ago": 0.24,        // null until two snapshots exist
      "price_change_24h": 0.03
    }
  ]
}
```

Each run also writes a snapshot to `data/history/YYYY-MM-DD-HH.json`. The 24h-change column is computed by joining the current run against the most recent snapshot at least ~23 hours older.

## Limitations

- **No authentication = no markets behind logins.** Kalshi has some markets only visible to logged-in users; we see only what the public API returns.
- **Pagination caps.** We stop at 10,000 Polymarket markets, 12,000 Kalshi events, and 22 Manifold keyword searches × 100 results each. In practice this captures the entire active universe with room to spare, but extreme-tail markets could be missed.
- **Manifold play-money.** Manifold prices reflect crowd belief but no real money is at stake; treat them as forecast aggregators, not market prices.
- **Volume is lifetime, not recent.** Polymarket and Kalshi report total contract volume since launch. A "$10M" market may have done all of that volume months ago.
- **Keyword false negatives.** Markets that talk about NY policy without naming any of the listed people, places, offices, or topics will slip through. The keyword list is in `fetch.mjs` (`STRONG_KEYWORDS`, `AMBIGUOUS`, `MANIFOLD_QUERIES`) and is the single thing to edit when something is missed.
- **Multi-outcome markets.** For events like "NYC Mayor 2025 winner" with N candidates, every candidate's contract appears as its own row. This is intentional — it's the only way to see how each contract is priced — but it means one event can dominate the table.

## Update cadence

Cron `0 */6 * * *` — runs at 00:00, 06:00, 12:00, 18:00 UTC. Each run takes ~30s. The Action commits to `data/markets.json` and a timestamped file in `data/history/` only when something changed.
