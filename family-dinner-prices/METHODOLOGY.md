# Family Dinner Prices — Methodology

A monthly **price index** for everyday New York City family restaurants, built the
way the Consumer Price Index is built: pin specific items and re-price the *same*
items over time. Plus a one-time citywide cross-section for context.

## 1. The tracked index (the product)

**53 restaurants** across all five boroughs whose menus are reliably readable
online, with **~520 pinned menu items** (about ten per restaurant). See
`data/panel.json`. (Panel grown by web-search discovery of new family
restaurants + scrapability testing; ~1 in 5 tested restaurants has a readable
static menu.)

### Construction

1. **Pinning** (`scripts/scout-trackable.js` → `scripts/build-panel.js`): for
   each restaurant we extract every clearly-named, clearly-priced item and store
   the **exact line text**, price, and any size descriptor. A restaurant joins
   the panel if the deterministic matcher can lock ≥4 of its items.
2. **Monthly re-check** (`scripts/check-panel.js`): re-fetch each menu and
   re-price every pinned line by string match — no AI, deterministic, free.
3. **Aggregation — Jevons index** (`scripts/build-panel-history.js`):
   - Each item's *price relative* = current price ÷ baseline price.
   - Each restaurant's monthly figure = **geometric mean** of its item relatives.
   - The headline index = geometric mean across restaurants, **= 100 at baseline**.
   - Geometric means are scale-free, so a $40 and a $100 restaurant count equally;
     the index is not dominated by the most expensive places (this is why we use
     Jevons, not an average of dollar totals).

### Index-quality rules

- **Matched-model only.** A dish is only ever compared to its own past price. No
  cross-restaurant bundle is imposed; each restaurant carries its own basket.
- **Cell-relative imputation.** If a pinned line is missing/unreadable in a given
  month, it is dropped for that month and the restaurant's change is computed from
  the items observed (i.e. the missing item inherits the restaurant's own mean
  change). We never substitute a different dish.
- **Winsorize-and-flag.** An item relative outside [0.5×, 2×] is clipped to the
  bound and flagged for review — large real moves stay in (bounded), mis-reads
  don't whipsaw the index, and nothing is silently deleted.
- **Freshness signal.** Each fetch records `Last-Modified` / `ETag`. A price that
  "holds" on a page unchanged since last month is flagged, so website staleness is
  not mistaken for genuine price stability — the central risk of any web-menu index.
- **Shrinkflation.** Each item's size descriptor is stored; when a price moves we
  surface the size for review (a same-price portion cut is real inflation the
  headline would otherwise miss). Detection is review-assisted, not fully automated.
- **Standardized drinks.** Soft drinks fixed at **$2.50** citywide; NYC sales tax
  (8.875%) applied consistently. The index tracks menu prices, not tip.
- **Dispersion.** We report the median, a 10% trimmed mean, and the 25th–75th
  percentile band of restaurant relatives, so readers see whether a move is broad.

### Staple watch (BEC-style core sub-index)

Where ≥4 restaurants carry the *identical* ubiquitous dish, we publish its plain
average dollar price over time (cleanest apples-to-apples). At 53 restaurants,
**five** qualify: fried rice (7), wonton soup (5), chicken over rice (4),
mozzarella sticks (4), spring roll (4). These thicken by **targeted recruitment**
(deliberately adding pizzerias for a slice index, halal carts for chicken over
rice, etc.) — the main growth lever, alongside more readable Brooklyn spots.

## 2. The one-time cross-section (context only)

The map: a one-time snapshot of **360+ restaurants** compiled in **spring 2026**,
validated against the Google Places API (exists, open, ≥25 reviews, within 500 m).
It is a dated landscape, **not re-checked monthly**. Closures fire only on a real
signal (Google permanently-closed, or HTTP 404/410); an unreadable menu is a
scrape failure, never a closure.

## Why only 31, and how to grow

A probe of the 316 cross-section restaurants with a menu URL found only ~64 expose
prices in **static HTML**; the rest are JavaScript-rendered, bot-blocked (403),
empty, or gone. Of those, 31 yield ≥4 reliably-lockable items. Readable menus
cluster on a few platforms (WordPress, Squarespace, Wix, and a family of `.shop`
builder sites) — the efficient path to grow N toward 50–100 (rec) is to recruit
new restaurants on those platforms, and to recruit by core staple to thicken the
sub-indices.

## Cadence and revisions

Fixed monthly cadence, run manually (no always-on automation). **Published index
points are not silently revised** — once a month is posted it stays; corrections
are noted. Month-to-month moves are noisy at this panel size; **year-over-year**
will be the meaningful comparison once 12 months exist.

## Files

| File | What it is |
|---|---|
| `data/panel.json` | The tracked panel: per-restaurant pinned baskets + baseline |
| `data/panel-snapshots/<date>.json` | One monthly re-check (per-item prices, relatives, freshness) |
| `data/trackable-scan.json` | Raw scout output across all readable menus (audit trail) |
| `panel-history.js` | `PANEL_HISTORY` — Jevons index, dispersion, core, panel; drives the page |
| `data/restaurants.json` | The cross-section registry (360+) |
| `scripts/scout-trackable.js` | One-time/periodic: find readable menus, extract candidate items (Haiku) |
| `scripts/build-panel.js` | Select panel, lock `data/panel.json` |
| `scripts/check-panel.js` | **Monthly:** re-price pinned items (deterministic, no AI) |
| `scripts/build-panel-history.js` | Rebuild `panel-history.js` (Jevons + dispersion + core) |
| `scripts/lib-core.js` | Shared core-category tagging |

## Running a monthly update

```sh
node scripts/check-panel.js          # re-price pinned items -> new snapshot
node scripts/build-panel-history.js  # rebuild the index
# review the diff (esp. winsorize/size/freshness flags), then commit + push
```

## Known limitations

- The panel measures *price change over time* for a fixed basket, **not** the
  citywide price level, and is not a representative sample.
- Selection toward machine-readable menus skews to chains / fast-casual / digital
  spots, which reprice more cheaply than printed-menu restaurants — so the panel
  may move sooner and more often than the city overall.
- Borough coverage is uneven (Bronx thinner).
- A renamed or removed dish drops out until re-pinned by hand; drinks are assumed.
- Web-menu staleness can lag true price changes; the freshness flag mitigates but
  does not eliminate this.
