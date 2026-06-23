# NY prediction markets tracker — methodology

## What this is

A consolidated view of every active prediction market touching New York City or New York State civic life — elections, government, policy, the economy, demographics, transit, crime and public health — refreshed every six hours via GitHub Actions. Sports, entertainment and daily weather markets are deliberately excluded.

The relevance filter is **structural, not a hand-kept roster of names**: a market qualifies when it pairs a New York place with a civic context, or matches any electoral-district pattern. That means new races, candidates and topics surface on their own, without anyone editing a keyword list when the news changes.

## Data sources

All three are public APIs, no authentication required.

| Source | Endpoint | Pagination | Pricing |
|---|---|---|---|
| Polymarket | `https://gamma-api.polymarket.com/markets?closed=false&active=true` | `limit=100` + `offset`, up to 60 pages | `outcomePrices` (decimal, JSON-encoded) |
| Kalshi | `https://api.elections.kalshi.com/trade-api/v2/events?status=open&with_nested_markets=true` | `cursor`, capped at 60 pages × 200 | `last_price_dollars` (decimal string) |
| Manifold | `https://api.manifold.markets/v0/search-markets?term=…` | per-keyword search × 22 queries | `probability` (decimal) |

Polymarket and Kalshi are real-money venues; their volumes are USD. Manifold is play-money — its volumes are mana ("M") and shouldn't be compared dollar-for-dollar.

Note on Polymarket pagination: the Gamma API now hard-caps every response at 100 items regardless of the requested `limit`. The fetcher pages by 100 via `offset` until the list is exhausted (a `422` past the end is treated as the stop signal). An earlier version asked for `limit=500`, received 100, saw `100 < 500` and stopped after the first page — which silently scanned only the top ~100 of ~2,100 open markets and was why most New York races never appeared.

## Filter logic — `matchesNY()` in `fetch.mjs`

A market is first dropped if its text or tags match any **hard exclusion** (sports, entertainment, weather). Otherwise it qualifies if it satisfies **any one** of the four tests below. The design goal is that the structural tests (geography + context, and districts) carry the load, so the tracker keeps finding New York markets as the cast of names changes.

### 1. Geography + context (the self-maintaining core)

A market qualifies when it contains **both** a New York place **and** a civic/governance word. This is what surfaces races and policy markets the tracker has never seen before.

- **Places:** New York, New York City, NYC, the five boroughs, Albany, Long Island, Hudson Valley, Westchester, Buffalo, Rochester, Syracuse, Yonkers, upstate New York.
- **Context:** any office (governor, mayor, comptroller, attorney general, public advocate, borough president, city council, state senate/assembly, district attorney, congress), any electoral word (primary, general election, nominee, candidate, ballot, proposition, referendum, redistricting, incumbent, special election, runoff, recall, impeach, term limit), or any policy word (budget, tax, rent, housing, zoning, homeless, migrant, immigration, minimum wage, school, education, healthcare, public health, population, census, economy, inflation, transit, subway, crime, police, eviction, pension, legislature, law, bill, and more).

Example: "Will New York tax QSBS gains?" matches on `New York + tax`; "New York Attorney General winner?" matches on `New York + attorney general`.

### 2. Electoral districts (`DISTRICT_RE`)

Any congressional, state legislative or city council district pattern qualifies on its own:

- Congressional, Polymarket style: `NY-12`, `NY12`, `NY 7`.
- Congressional, Kalshi style: `New York 21 House` (the spelled-out form requires an office/election word nearby so it doesn't fire on the cable channel "New York 1").
- Spelled-out districts: `State Senate District 12`, `Assembly District 36`, `City Council District 7`.

This is what brings in the down-ballot House primaries (NY-07, NY-12, NY-13, NY-21 and the rest) regardless of who the candidates are.

### 3. Strong keywords (any match qualifies, no geography needed)

A convenience layer for markets that are unmistakably New York but contain no New York place name — e.g. "Will AOC win the 2028 nomination?" People: Mamdani, Hochul, Cuomo, Letitia/Tish James, Jumaane Williams, Brad Lander, Zellnor Myrie, Scott Stringer, Ritchie Torres, Dan Goldman, Jessica Ramos, Curtis Sliwa, Stefanik, Gillibrand, Schumer, Ocasio-Cortez/AOC, Hakeem Jeffries, Jamaal Bowman, Antonio Delgado, Mark Levine. Phrases/agencies: New York City, New York State, NYC, NYS, NY governor, NY Senate, MTA, NYPD, FDNY, NYCHA, Rikers, congestion pricing, City Hall, rent stabilization, Rent Guidelines Board, and the five borough DA offices. This list is deliberately short — it is not where coverage comes from.

### 4. Ambiguous tokens (require co-occurring NY context)

To avoid false positives like Amy Adams / John Adams / LeBron James:

| Token | Required context |
|---|---|
| Adams | "mayor", "Eric Adams", "City Hall" |
| Lander | "comptroller", "mayor", "Brad Lander" |
| Stringer | "comptroller", "Scott Stringer" |
| James | "Letitia", "Tish", "attorney general" |
| Williams | "Jumaane", "public advocate" |

### Hard exclusions

A market is rejected outright, before any New York test runs, if its text or tags match any of:

Knicks, Yankees, Mets, Giants, Jets, Rangers, Nets, Islanders, Liberty, Red Bulls, Sabres, Buffalo Bills, NYCFC, New York City FC, Subway Series, NY/NYC Marathon, MLS Cup, MLB, NBA, NHL, NFL, UFC, PGA, WNBA, NCAA, Champions League, Premier League, Bundesliga, La Liga, Super Bowl, World Series, Stanley Cup, Final Four, playoffs, championship, Heisman, box office, Oscars, Grammys, Emmys, Tonys, Tony Award, Met Gala, Fashion Week, Broadway, Eurovision, Dancing with the Stars, DWTS, temperature, rainfall, snowfall, snowiest, Fahrenheit, Celsius, heat wave, blizzard, hurricane, "inches of rain/snow".

The list is kept specific on purpose — there is no bare "Bills" (that would swallow legislation) and no bare "degrees" or "hottest" (those collide with housing and economy markets).

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
      "category": "Mamdani",        // one of: Mamdani, Presidential, House / Congress, Elections, Policy & government, Other
      "price_24h_ago": 0.24,        // null until two snapshots exist
      "price_change_24h": 0.03
    }
  ]
}
```

Each run also writes a snapshot to `data/history/YYYY-MM-DD-HH.json`. The 24h-change column is computed by joining the current run against the most recent snapshot at least ~23 hours older.

## Limitations

- **No authentication = no markets behind logins.** Kalshi has some markets only visible to logged-in users; we see only what the public API returns.
- **Pagination caps.** We stop at 6,000 Polymarket markets (60 pages × 100, against ~2,100 currently open), 12,000 Kalshi events, and 22 Manifold keyword searches × 100 results each. In practice this captures the entire active universe with room to spare, but extreme-tail markets could be missed.
- **Manifold play-money.** Manifold prices reflect crowd belief but no real money is at stake; treat them as forecast aggregators, not market prices.
- **Volume is lifetime, not recent.** Polymarket and Kalshi report total contract volume since launch. A "$10M" market may have done all of that volume months ago.
- **Residual false negatives.** Because relevance is now structural (geography + context), most New York markets are caught automatically. The remaining gaps are markets that mention neither a New York place nor a strong keyword — e.g. a market that refers only to a candidate by name with no district, office or place. If something is missed, the levers in `fetch.mjs` are `GEO_KEYWORDS`, `CONTEXT_KEYWORDS`, `DISTRICT_RE`, `STRONG_KEYWORDS` and `MANIFOLD_QUERIES`.
- **False positives.** A national market that happens to name a New York place alongside a context word could qualify. Spot checks find these are rare and almost always genuinely New York; the volume filter on the page hides the low-stakes noise.
- **Multi-outcome markets.** For events like "NYC Mayor 2025 winner" with N candidates, every candidate's contract appears as its own row. This is intentional — it's the only way to see how each contract is priced — but it means one event can dominate the table.

## Category classification

Every market is assigned exactly one primary `category` for the dashboard's filter chips. The chips show live counts and narrow both the comparison strip and the table; counts reflect whatever other filters (source, volume, search) are active.

Classification is first-match-wins, so the order is the precedence — `categorize()` in `fetch.mjs`:

1. **Mamdani** — any market naming Mamdani (his mayoralty, policy pledges, even his 2028 presidential odds). The person bucket wins first so a click on "Mamdani" shows everything about him.
2. **Presidential** — national White House markets: 2028 nominations, "elected president", presidential runs (for everyone other than Mamdani, who is already caught above).
3. **House / Congress** — congressional district races, the single largest cluster (~460 rows, since every candidate in every district is its own contract). Split out of Elections so that chip stays usable: NY district shorthands (NY-12, "New York 21 House"), "congressional", and House primary/seat/district/general-election wording.
4. **Elections** — every *other* New York race: governor, state senate and assembly, US Senate, attorney general, comptroller, mayor, borough president, district attorney, city council, ballot measures (~74 rows).
5. **Policy & government** — congestion pricing, rent, the MTA, NYPD, crime, budget, taxes, housing, immigration, transit and the rest of the policy vocabulary.
6. **Other** — genuinely uncategorized civic markets (population and demographics, city efficiency savings, a Waymo launch, and so on).

The same classifier is mirrored in `index.html` as a fallback, so the chips still work on older history snapshots written before the `category` field existed. To retune the buckets, edit the regexes in both places (or just `fetch.mjs` and re-run).

## Cross-platform topic consolidation

When the same outcome trades on more than one platform — e.g. "Mamdani freezes NYC rent in 2026" runs on both Kalshi and Manifold — we want them side-by-side so price differences are obvious.

The `TOPIC_RULES` array in `fetch.mjs` is a list of `{ id, label, pattern }` rules. Each market's question is matched against the rules; the first match wins and tags the market with `topic_id` + `topic_label`. The dashboard groups markets by `topic_id` and surfaces any topic with 2+ distinct platforms in a "Same question, different platforms" comparison strip at the top of the page, sorted by spread (biggest disagreement first).

Topics are deliberately conservative: same outcome **and** same time window. "Mamdani freezes rent in 2026" and "Mamdani freezes rent before 2027" are distinct topics — they're betting on different things. Markets that don't match any rule have `topic_id: null` and don't appear in the comparison strip; they show up only in the main table.

Adding a new topic is a one-line append to `TOPIC_RULES`.

## Update cadence

Cron `0 */6 * * *` — runs at 00:00, 06:00, 12:00, 18:00 UTC. Each run takes ~30s. The Action commits to `data/markets.json` and a timestamped file in `data/history/` only when something changed.
