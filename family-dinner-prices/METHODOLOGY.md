# Family Dinner Prices — Methodology

A monthly tracker of **what a family of four pays for dinner** at everyday New York
City restaurants, plus a one-time citywide cross-section for context.

## The number we track

A real family-of-four dinner bill, with the bundle sized to how families
actually order at each kind of restaurant:

```
pizzerias : 1 large pizza
chinese   : 2 different shared dishes + 1 order of egg rolls
everywhere else (standard): 2 adult entrees + 2 kid portions (kids' menu where one exists)
+ 2 drinks ($2.50 each, standardized) ; then x (1 + 8.875% tax + 18% tip)
```

The published headline is the **median bill across the panel** (robust to a few
pricey institutions), shown with the average and the 25th–75th percentile range.
This is a dollar figure, not an index. Each restaurant's pinned dishes are
re-priced monthly by deterministic string match. Deterministic guards reject
desserts/drinks as an entree, require the kid item to be cheaper than the adult,
and enforce sane price ranges (adult $6–$32; a $25+ signature entree is flagged).

## The panel (84 restaurants, all five boroughs)

84 restaurants are active in the panel. A restaurant only counts in a given month
if all of its pinned dishes re-price cleanly, so the number actually priced is
usually a bit lower — **76 of 84 in the July 2026 check** (the other 8 missed and
were excluded from that month's number, not carried forward).

Restaurants whose menus are reliably readable online, balanced across boroughs.
Built in three passes:
1. **Discovery** — web-search scouts by borough/cuisine + a 200-restaurant
   candidate spreadsheet, screened to **valid sources only** (a restaurant's own
   site or direct ordering page; never delivery apps or Yelp/MenuPages directories).
2. **Scrapability test** — static fetch must find priced items (the same gate the
   monthly checker uses). About **1 in 5** candidates pass.
3. **Pinning + verification** — an AI pass picks one adult entree and one kid
   portion per restaurant; a second adversarial AI pass double-checks each pick
   (rejecting e.g. a whole specialty pizza miscast as a kid meal, a $1 "portion"
   scrape artifact, or any pair where the kid item isn't cheaper than the adult).
   Restaurants that can't form a valid pair are dropped.

## How we keep it honest

- **Direct prices only — never delivery.** Delivery-app menu prices run 15–25%
  above dine-in and move with platform commissions, not the kitchen. We exclude
  Grubhub/DoorDash/Uber Eats and Grubhub-owned MenuPages/Allmenus entirely.
- **Same-item, matched-model, no stale prices.** Each month we re-price the *same
  two pinned dishes* by deterministic string match (no AI at re-check time). A dish
  is only ever compared to its own past price. A restaurant counts that month only
  if BOTH dishes re-price cleanly; a miss is **excluded** (never carried forward as
  a frozen price), and the restaurant is **dropped** from the panel if it can't be
  re-priced for two consecutive checks or its page returns 404/closed. We never
  substitute a different dish. (EJ's Luncheonette was dropped at baseline — its
  pinned "thanksgiving turkey dinner" is seasonal and unverifiable in May.)
- **No composition distortion.** The headline month-over-month change is the median
  change at restaurants priced in *both* months (a matched sample), so dropping or
  adding a restaurant can't manufacture a fake jump in the bill.
- **Mis-read guard.** A dish that appears to move beyond ±100% is capped and
  flagged (almost always a scrape error), not allowed to whipsaw the bill.
- **Freshness signal.** We record each page's Last-Modified/ETag; a price that
  "holds" on a page unchanged since last month is flagged, so website staleness
  isn't read as price stability.
- **Price ceiling.** The panel targets entrees under $25; signature dishes above it
  (Katz's pastrami, a chicken parm) are flagged (●), not hidden.

## Selection bias (the honest caveat, also stated on the site)

We can only track restaurants that post a readable online menu — ~1 in 5 of those
we check. This tilts the panel toward more-digitized spots and **away from the
cash-only, menu-on-the-wall immigrant places that are often the most affordable**.
Read the series as a trend for the restaurants we *can* follow, not a census of the
cheapest dinner in the city. Closing the gap would require occasional on-the-ground
price checks, which this automated panel does not do.

## Benchmark

The official yardstick is the BLS "food away from home" CPI for the
New York–Newark–Jersey City metro: **+3.4% over the 12 months ending April 2026**
([BLS](https://www.bls.gov/regions/northeast/news-release/consumerpriceindex_newyork.htm)).
How our more-local panel diverges from it is itself the story.

## The one-time cross-section

The map is a dated **spring 2026** snapshot of 360+ restaurants (validated via the
Google Places API: open, 25+ reviews, located within 500 m). It is **not** re-checked
monthly — treat its prices as "around spring 2026."

## Cadence and revisions

Fixed monthly cadence, run automatically on the 1st of each month by the
`monthly-price-check` GitHub Action (which runs `check-panel.js` +
`build-panel-history.js` and commits the new snapshot). **Published months
are not silently revised.** Month-to-month moves are noisy at this panel size;
year-over-year will be the meaningful comparison once 12 months exist.

**Gap in the series.** The baseline is 2026-05-01. No check ran in June 2026, and
the second reading is dated **2026-07-15** — so the first interval spans two and a
half months, not one. The gap is real and is left visible rather than
back-filled: menu prices at a past date can't be recovered after the fact, and
inventing one would be exactly the carried-forward fiction this panel exists to
avoid. Monthly points resume 2026-08-01.

**Retired pipeline.** An earlier tracker (`check-prices.js` → `build-history.js` →
`price-history.js`, with snapshots in `data/snapshots/`) carried prices forward
when a re-check failed — 1,418 carried values against 26 real re-scrapes across
four months, which contradicts the same-item rule above. It was removed in July
2026 and is not part of this series; it remains in git history (through commit
`546cfd85`) for the record. The panel pipeline below is the only tracker.

## Files

| File | What it is |
|---|---|
| `data/panel.json` | The panel: per-restaurant pinned adult + kid dishes, beverage, baseline bill |
| `data/panel-snapshots/<date>.json` | One monthly re-check (re-priced dishes, bill, freshness) |
| `panel-history.js` | `PANEL_HISTORY` — dollar-bill series (avg/median/spread), by borough, panel, BLS |
| `data/restaurants.json` | The cross-section registry (360+, spring 2026) |
| `data/new-candidates.json`, `data/sheet-candidates.json` | Discovery candidate lists (audit trail) |
| `data/familybill-verified.json` | Adversarially-verified pin output (audit trail) |
| `scripts/scout-candidates.js` | Static-fetch scrapability + item extraction for candidates |
| `scripts/build-panel.js` | Assemble the family-bill panel from verified pins |
| `scripts/check-panel.js` | **Monthly:** re-price the two pinned dishes (deterministic) |
| `scripts/build-panel-history.js` | Rebuild `panel-history.js` (dollar-bill series) |

## Running a monthly update

```sh
node scripts/check-panel.js          # re-price pinned dishes -> new snapshot
node scripts/build-panel-history.js  # rebuild the dollar-bill series
# review the diff (missed / mis-read / freshness flags), then commit + push
```
