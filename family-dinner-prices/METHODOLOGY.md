# Family Dinner Prices — Methodology

This project answers one question — *what does a weeknight dinner for a family of
four cost at everyday New York City restaurants?* — in two deliberately separate
parts. Keeping them apart is the whole point: one is a broad one-time photo, the
other is a narrow but trustworthy ongoing measurement.

## 1. The cross-section (the map)

A one-time snapshot of **360+ restaurants** across all five boroughs, compiled in
**spring 2026**.

- Restaurants were drawn from every NYC neighborhood, weighted toward everyday,
  family-friendly spots with **at least 25 Google reviews**.
- Each was validated against the **Google Places API**: must exist, be currently
  open, not flagged permanently closed, and sit within 500 m of Google's
  coordinates.
- For each restaurant we selected the most ordered-looking items — the signature
  entrée or pie, a plain kid-friendly option, and a standard shared side.
- **This is a dated snapshot, not a live feed.** The prices on the map are not
  re-checked every month. Treat them as "around spring 2026."

The map, the distribution chart, the cuisine/neighborhood breakdowns, and the
big-number stats are all derived from this cross-section.

## 2. The tracked panel (the trend)

A smaller set of **22 restaurants** (current count; see `data/panel.json`) chosen
because their menus are **reliably readable online**, used to track price change
*over time*.

### Why only 22, and not all 360?

Most restaurant menus today are rendered by JavaScript or sit behind ordering
widgets (Toast, Square, Wix, BentoBox, etc.). A simple HTTP fetch receives an
empty shell — no prices. A probe of the 251 cross-section restaurants that had a
menu URL found only **~19%** exposed prices in static HTML; the rest were
JS-rendered, bot-blocked (403), empty, or gone. And when an AI is asked to
free-pick a "similar" item each month, it grabs *different dishes* month to month
(a whole pie one month, a slice the next), manufacturing fake price swings.

We would rather track 22 restaurants honestly than 360 unreliably.

### Pinned line items + same-item verification

This is what makes the trend trustworthy:

1. **Baseline pinning** (`scripts/pin-panel.js` → `scripts/build-panel.js`): for
   each panel restaurant we extract and store the **exact menu line text** for
   each component (e.g. `"Saigon Shack Phở"`, `"Chicken Samosa (Each)"`), copied
   verbatim, plus its price. Stored in `data/panel.json`.
2. **Monthly re-check** (`scripts/check-panel.js`): we re-fetch the menu and look
   for *that same pinned line*. We read the price attached to that same line —
   skipping quantity numbers like "24 oz" or "6 pcs" — and accept it only if it's
   within a plausible band (0.5×–2× the known price; anything wilder is treated as
   a mis-read). **If the pinned line is gone or unreadable, we carry its last
   price forward and flag it** (the amber ● on the page) rather than substituting
   a different dish. No AI is used at re-check time — it's pure string matching,
   so it's free and deterministic.

### The meal

`2 adult entrées + 2 kid meals + 1 shared appetizer + 2 soft drinks`, then **NYC
sales tax (8.875%)**. Soft drinks are **standardized at $2.50 citywide** — menus
almost never list soda prices in readable HTML, and a can of soda costs about the
same everywhere, so standardizing removes a noise source and lets drinks add zero
false month-to-month movement.

> Note: the page's *cross-section* meal also adds an 18% tip in its displayed
> "total bill"; the *panel* total is food + tax (no tip) so its month-over-month
> change reflects menu prices only. Both formulas are shown on the page.

### Selection rules (a baseline is only kept if it's a credible family meal)

Applied in `scripts/build-panel.js`:

- adult entrée price in **[$8, $40]**
- kid meal in **[$2, $16]** and **cheaper than the adult entrée**
- appetizer **≤ 1.15 × adult entrée**
- whole-meal total in **[$25, $110]**
- item strings contain no price/HTML cruft (so they can be re-matched)

Restaurants whose auto-extracted baseline failed these rules (e.g. a whole
"Cheese Pizza" mistakenly picked as a kid meal) were dropped, not shipped. The
panel can grow as more menus are hand-pinned.

## Files

| File | What it is |
|---|---|
| `data/restaurants.json` | The cross-section registry (360+) |
| `data/panel.json` | The locked tracked panel + pinned line items + baseline |
| `data/panel-snapshots/<date>.json` | One monthly re-check of the panel |
| `data/panel-candidates.json` | Raw output of the pinning pass (audit trail) |
| `panel-history.js` | `PANEL_HISTORY` — drives the page's panel section + trend |
| `scripts/pin-panel.js` | One-time: extract pinned line items from readable menus (uses Claude Haiku) |
| `scripts/build-panel.js` | Apply selection rules, lock `data/panel.json` |
| `scripts/check-panel.js` | **Monthly:** re-price the pinned lines (no AI, string match) |
| `scripts/build-panel-history.js` | Rebuild `panel-history.js` from snapshots |
| `scripts/check-prices.js` | Legacy cross-section scraper (closures only fire on 404/410 or closure keywords) |

## Running a monthly update

```sh
node scripts/check-panel.js          # re-price pinned lines → new panel snapshot
node scripts/build-panel-history.js  # rebuild panel-history.js
# review the diff, then commit + push
```

No always-on automation runs this — it is executed manually.

## Known limitations

- The panel is small (22) and skewed toward menus that happen to be readable;
  it is **not** a representative sample of all NYC restaurants. It measures
  *change over time* for a fixed basket, not the citywide level.
- Borough coverage is uneven (the Bronx is thin) because reliably-readable menus
  are unevenly distributed.
- A pinned item that is renamed or removed drops out (carried forward + flagged)
  until re-pinned by hand.
- Drinks are assumed, not measured.
- The cross-section is a single dated snapshot; do not read its prices as current.
