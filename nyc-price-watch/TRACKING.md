# NYC Price Watch — How the tracking actually works

A candid look at what each of the 15 prices takes to maintain, given the
operating reality: one person (Josh), working through Claude, no field
team, no paid data feeds.

---

## The constraint

Every line on this page has to be sustainable for a single person who
isn't going to walk to ten pizzerias on the first Monday of every month,
and who doesn't have a paid data subscription. That rules out a lot of
elegant ideas. It also means we have to be honest about which series
will get refreshed and which will quietly stop after two months.

The right move is to be explicit about difficulty up front, and lean
hardest on the items that are easy enough to actually keep going.

---

## Difficulty tiers

**Tier 1 — Trivial.** A single published number on a public webpage that
changes maybe once a year. Claude can verify it in 30 seconds; you can
verify it in a minute. Refresh effort: near zero.

**Tier 2 — Easy automated.** A public series that updates monthly or
faster, retrievable from a stable URL or API (AAA, FRED, BLS). Claude
can fetch it most months; the few months a fetch fails, a manual check
is a one-minute job.

**Tier 3 — Easy but fragile.** Public data that exists, but the
publisher actively blocks scraping (StreetEasy, sometimes FRED HTML).
Requires a copy/paste from the published page each month. Five-minute
job for a human, untenable to fully automate without a paid feed.

**Tier 4 — Construction.** No single number; you have to assemble it
from a published rate schedule (ConEd, taxi). The inputs are public,
the math is simple, but it takes 10–15 minutes to rebuild and verify.

**Tier 5 — Hand survey.** Requires physically observing prices that
aren't published online (pizza slice, bagel, coffee). No way around the
legwork. Realistically does not happen monthly without a deliberate
walking route or a friend network.

**Tier 6 — Generated quote.** Requires running an app at a specific
time (Uber benchmark). Hard to automate without a phone in hand;
realistic only if it's bolted onto an existing routine.

---

## Per-item assessment

| # | Item | Tier | Update freq | Who does it | Realistic? |
|---|---|---|---|---|---|
| 1 | Subway / bus fare | 1 | Annual or rarer | Claude verifies | ✅ Yes |
| 2 | Verrazzano toll | 1 | Annual | Claude verifies | ✅ Yes |
| 3 | Citi Bike annual | 1 | 1–2× per year | Claude verifies | ✅ Yes |
| 4 | Water & sewer | 1 | Annual (July) | Claude verifies | ✅ Yes |
| 5 | Yellow taxi | 1 | Multi-year | Claude verifies | ✅ Yes |
| 6 | Gas (NYC metro) | 2 | Daily | Claude pulls AAA | ✅ Yes |
| 7 | Grocery CPI (NY) | 2 | Monthly | Claude pulls FRED | ✅ Yes (with retries) |
| 8 | ConEd typical bill | 4 | Monthly | Claude rebuilds | ✅ Yes (15 min/mo) |
| 9 | Broadway avg | 2 | Weekly / season | Claude pulls League | ⚠️ Mostly — season number is best |
| 10 | StreetEasy rent | 3 | Monthly | Manual copy/paste | ⚠️ Yes if disciplined |
| 11 | Family dinner | 4* | Quarterly | Pull from sister project | ✅ Yes (quarterly) |
| 12 | Pizza slice (10-shop) | 5 | Monthly | Walking survey | ❌ Not without a route |
| 13 | Bagel + cream cheese | 5 | Monthly | Walking survey | ❌ Not without a route |
| 14 | Coffee, 12 oz | 5 | Monthly | Walking survey | ❌ Not without a route |
| 15 | Uber benchmark trip | 6 | Weekly | App quote | ❌ Not at scale |

\* Already systematized in the family-dinner-prices project.

---

## What this means for the published page

### Keep (10 items, all sustainable)

These are the ones where the monthly or quarterly refresh is genuinely
easy enough that the page won't go stale.

- **Tier 1 tariffs** (subway, toll, Citi Bike, water, taxi). Most months
  there's nothing to do. When something changes, a one-time verify
  updates the card and adds a step in the trendline.
- **Tier 2 published series** (gas, BLS food CPI, Broadway). Claude
  refreshes from the public source on the 15th of each month. Fallback
  to manual on the rare fetch failure.
- **Tier 4 ConEd reconstruction.** Claude rebuilds the typical 300 kWh
  bill from the posted rate schedule. Once you've done it once, it's a
  10-minute job.
- **Tier 3 StreetEasy rent.** Painful but doable: copy the citywide
  median number from the dashboard once a month. Five minutes.
- **Family dinner.** Already a working project; pull the headline
  number quarterly.

### Drop or rethink (5 items)

The hand-survey panels (pizza, bagel, coffee) and the Uber benchmark
were the right shape conceptually but won't hold up in practice without
field labor. Three options:

1. **Drop them outright.** Goes from 15 items to 11. Honest, simple,
   keeps the page from quietly degrading.
2. **Replace with proxies that auto-refresh.** Some candidates:
   - **Pizza slice** → Domino's or Papa John's NYC delivery price for
     a fixed plain pizza. Posted, scrapeable, less cool but real.
   - **Coffee** → Starbucks app price for a tall coffee at a fixed NYC
     store. Posted, fetchable, less cool but real.
   - **Bagel** → no good proxy.
   - **Uber** → drop entirely; the benchmark idea doesn't work without
     a person holding a phone.
3. **Keep as opt-in panels.** Mark them clearly as "when surveyed" —
   collect on a known walk every quarter or two, accept that gaps will
   be honest gaps in the trendline. Don't pretend they're monthly.

My recommendation: **drop Uber, drop the bagel and coffee panels, keep
pizza but make it quarterly and replace the panel with chain-delivery
prices that are scrapeable. Add one or two replacements** that are
easy and meaningful (see below).

### Easy adds worth considering

These are items I missed in the first pass that fit Tier 1 or Tier 2:

- **NY Times newsstand price** — published, changes rarely. Trivial.
- **Average cooling bill, summer months** — ConEd publishes this each
  summer for typical apartment. Trivial.
- **Property tax average bill, Class 1 (1–3 family homes)** — NYC DOF
  publishes annually. Trivial.
- **Express bus fare or LIRR peak** — published, MTA. Trivial.
- **Manhattan parking meter rate** — DOT publishes; changes once every
  few years. Trivial.
- **NYC Health + Hospitals visit copay** — published, low frequency.
  Trivial.
- **Citi Bike day pass** — published. Already on the pricing page.
  Trivial.

The pattern: **the easiest series to track are also the most boring.**
That's a feature, not a bug — boring-and-real beats interesting-and-fake.

---

## The monthly / quarterly workflow

Here's what a refresh actually looks like:

### Monthly refresh — 15 minutes total

1. **Claude does in one pass:**
   - Pulls AAA NYC metro gas price (15th of the month).
   - Pulls BLS food-at-home CPI from FRED (mid-month release).
   - Verifies subway fare, toll, Citi Bike, water, taxi haven't changed.
   - Rebuilds ConEd typical bill from posted rate.
   - Appends each result to `readings.json` with date, value, source note.
   - Re-renders the page so sparklines extend by one quarter (when a
     quarter just closed).

2. **Josh does manually (5 minutes):**
   - Opens StreetEasy data dashboard, copies the citywide median rent
     for the latest month, pastes the value into the prompt.
   - That's it.

### Quarterly refresh — extra 10 minutes

- Pull family-dinner-prices project, append the latest quarterly mean.
- Pull Broadway League season-to-date if a new season has closed.
- Roll up the three monthly observations to one quarterly value per
  series, recompute YoY badges.

### When something genuinely breaks

- **Source moves or 403s.** Note it in `readings.json` (`source_status:
  "blocked YYYY-MM-DD"`) and try the alternate source in the methodology
  table. Don't invent a number.
- **Panel business closes.** Freeze its slot at last observed value for
  that month, pick a successor of similar tier and neighborhood, log
  the swap in a `CHANGELOG.md`. Both prices appear so the trend isn't
  silently distorted.
- **Two months in a row of TBD on a series.** Either fix the pull or
  drop the series. Don't let TBD stretch to three.

---

## Honesty notes

- **Backfilled history is not the same as live observation.** Pre-Q2
  2026 quarters on the gas and ConEd cards are flagged `est.` because
  they're approximations of the published archive, not precise monthly
  pulls. The shape is right. The exact level on any given quarter is
  approximate. Real monthly observations going forward will be precise.
- **No black boxes.** Every reading lives in `readings.json` with a
  source URL and a retrieval date. If a number on the page looks
  wrong, the raw entry is one click away.
- **No team, no field staff.** This document exists because the
  honest answer to "can you also track X" is sometimes "no, not
  sustainably" — and saying so up front is better than building
  something that quietly stops updating in month three.

---

## Recommended final shape

Eleven items, all sustainable, all real:

**Tier 1 (verify only when changes):** subway fare, Verrazzano toll,
Citi Bike annual, water & sewer rate, yellow taxi, NYT newsstand price,
parking meter rate.

**Tier 2 (Claude pulls each month):** gas (AAA), BLS food-at-home CPI
(FRED).

**Tier 3 (Josh copy/pastes each month):** StreetEasy citywide rent.

**Tier 4 (Claude rebuilds each month):** ConEd typical 300 kWh bill.

**Quarterly:** Broadway League season average, family-of-four dinner,
chain-delivery pizza price (proxy for the slice panel).

That's a page that can survive a year. Anything more aspirational is
decoration.
