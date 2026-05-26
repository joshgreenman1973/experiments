# NYC Price Watch — tracking schedule

A schedule built around when each source actually publishes, so a
refresh lands on fresh data instead of an arbitrary calendar date.

The design goal: **one monthly run, one quarterly add-on, one annual
watch** — few enough touchpoints that it actually happens.

---

## The release calendar (when sources publish)

Knowing this is the whole game. Each row is when new data becomes
available for the prior period.

| Source | Publishes | Covers | Lag |
|---|---|---|---|
| AAA gas (NYC metro) | Daily | Same day | None |
| ConEd electric & gas tariff | ~1st of month | Current month | None |
| BLS CPI, NY-Newark-JC | ~10th–15th | Prior month | ~2 weeks |
| StreetEasy monthly rent | ~8th–12th | Prior month | ~1–2 weeks |
| Case-Shiller NY (FRED NYXRSA) | Last Tuesday | 2 months prior | ~2 months |
| Douglas Elliman Manhattan/Brooklyn | ~10th–14th of Jan/Apr/Jul/Oct | Prior quarter | ~2 weeks |
| Broadway grosses (weekly) | Each Mon/Tue | Prior week | Days |
| Broadway League season stats | ~late spring | Full season | Annual |
| MTA fares & tolls | On change (rare) | — | — |
| Citi Bike pricing | On change (rare) | — | — |
| NYC Water Board rate | Annual, July 1 | Fiscal year | — |
| NYC TLC taxi tariff | On change (rare) | — | — |

The key insight: by **the last Tuesday of the month**, every monthly
source for the prior month is already out, and the fresh Case-Shiller
release just dropped. That's the natural anchor date.

---

## The monthly run — last Tuesday of every month

One sitting, ~15 minutes. Anchor it to Case-Shiller's release day so
everything is fresh.

**Claude does, in one pass (~10 min):**
1. Pull AAA NYC metro gas price → append to `readings.json`.
2. Pull BLS NY-Newark-JC food-at-home YoY (prior month) → append.
3. Pull StreetEasy citywide median (prior month) → append.
4. Pull Case-Shiller NY YoY (just released) → append.
5. Rebuild ConEd electric + gas typical bills from current tariff → append.
6. Verify the five rare-change tariffs (subway, toll, Citi Bike, water,
   taxi) are unchanged; only touch them if a hike was announced.
7. Re-render `index.html` so the current-quarter values update and, if
   a quarter just closed, the sparkline frame advances one quarter.
8. Update the masthead "rev." date and the verified/pending counts.

**Josh does (~5 min):**
- Nothing required if Claude's StreetEasy pull succeeds. If StreetEasy
  blocks the fetch (it sometimes does), open the
  [data dashboard](https://streeteasy.com/blog/nyc-housing-market-data/rentals/),
  copy the citywide median, paste it into the prompt.

---

## The quarterly add-on — Jan / Apr / Jul / Oct run

In those four months, the last-Tuesday run also picks up:

1. **Douglas Elliman Manhattan & Brooklyn** quarterly reports (out by
   mid-month) → append the new quarter's median rent for each.
2. **Family-of-four dinner** → pull the latest figure from the
   family-dinner-prices project → append.
3. **Quarter roll-up** → for the monthly series (gas, CPI, rent,
   Case-Shiller, ConEd), compute the quarter's average and lock the
   closed quarter's value into the trendline.
4. **Panel surveys** (pizza, bagel, coffee, Uber) → if collected this
   quarter, append; if not, leave the quarter as an honest gap.

---

## The annual watch — once a year, no fixed date

These move rarely; watch for the announcement rather than checking on
a schedule.

| Item | Watch for | Typical timing |
|---|---|---|
| NYC Water Board rate | New FY rate vote | May, effective July 1 |
| Rent Guidelines Board cap | Annual vote (if added) | June |
| MTA fares & tolls | Board-adopted hikes | Announced ~Dec, effect Jan |
| Citi Bike pricing | Lyft price change | Usually January |
| Broadway League | Season-end stats | Late spring |
| CUNY tuition (if added) | Board vote | Summer |

When any of these is announced, do a one-off update that day and add
the step to the trendline — don't wait for the monthly run.

---

## At-a-glance: what happens when

```
EVERY MONTH (last Tuesday)
  ├─ gas .................. AAA, auto
  ├─ food CPI ............ BLS, auto
  ├─ citywide rent ....... StreetEasy, auto (manual fallback)
  ├─ Case-Shiller ........ FRED, auto
  ├─ ConEd elec + gas .... rate rebuild, auto
  └─ tariff check ........ verify 5 rare-change items, auto

ALSO IN JAN / APR / JUL / OCT
  ├─ Manhattan rent ...... Douglas Elliman, auto
  ├─ Brooklyn rent ....... Douglas Elliman, auto
  ├─ family dinner ....... sister project, auto
  ├─ quarter roll-up ..... lock closed quarter, auto
  └─ panel surveys ....... pizza/bagel/coffee/Uber, if collected

WHEN ANNOUNCED (annual watch)
  └─ water · RGB cap · MTA · Citi Bike · Broadway season · CUNY
```

---

## Automating the reminder

The monthly run only works if something nudges it. Options, easiest
first:

1. **Recurring reminder → iMessage.** A `launchd` job fires on the last
   Tuesday of each month and texts a reminder to start the run. Lowest
   tech, most reliable. (Matches the existing weekly-catalogue setup.)
2. **Scheduled agent.** A scheduled task runs the Claude pull
   automatically on the last Tuesday, appends to `readings.json`,
   re-renders, commits, and texts a summary of what moved. Hands-off
   except for the StreetEasy fallback.
3. **Manual.** Just run it yourself when you remember. Works, but the
   last-Tuesday anchor exists precisely so it doesn't drift.

Recommended: **option 2**, with the iMessage summary so you see what
changed without opening anything — and a manual confirmation step only
if StreetEasy blocks the fetch.

---

## Why last Tuesday, not the 1st or 15th

- The **1st** is too early — none of the prior month's CPI, rent, or
  home-price data is out yet.
- The **15th** catches CPI and StreetEasy but misses Case-Shiller,
  which releases the last Tuesday.
- The **last Tuesday** is the first date when *everything* for the
  prior period is available simultaneously. One trip, all fresh.

The only thing that's "stale" on the last Tuesday is Case-Shiller
itself, which is inherently two months lagged — but that lag is the
same every month, so the series stays apples-to-apples.
