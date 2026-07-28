# Catalog audit — findings

## FIXED
1. **nyc-data/women-and-guns** — section headline claimed American women are 21x more likely to die
   from gun violence "than women in any other rich country". Source (Giffords/Grinshteyn-Hemenway) is an
   aggregate comparison across high-income countries, not a per-country claim. Changed to
   "than women in other high-income countries", matching the card and the ledger.
2. **45-minute-city** — "223 express routes" was the sum of express rows across six overlapping MTA
   borough GTFS feeds (36+36+43+36+36+36=223). True unique count is 79. Verified from the cached feeds;
   Staten Island's separately-stated 29 SIM routes is correct, which was the tell.
   Fixed in index.html (x2) and METHODOLOGY.md. Router itself is unaffected: trips are not duplicated
   across feeds (each route's trips live in exactly one feed), so waits/frequencies were never inflated.

## CLEAN (checked, no action)
- nyc-doe-per-pupil-spending — all arithmetic reverified (growth rates, CPI deflators, bucket sums,
  SBER subtotals, charter series). Already carries a detailed correction log.
- nyc-price-watch — figures machine-derived from BLS API; internally consistent.

## JUDGMENT CALLS (to summarize, not act on)

3. **personal/france-trip-2026** — three practical errors:
   - "Lola (11) and Sasha (5) ride FREE — no ticket or card needed on Paris transit" (stated twice).
     Wrong: only under-4s ride free in Île-de-France; ages 4-9 pay half fare (~EUR1.30), 10+ pay full
     adult fare. Riding without a valid ticket risks a fine. Corrected both places.
   - Cité des Sciences (30 Ave Corentin Cariou) directions gave Line 5 to Porte de Pantin. That station
     serves the Philharmonie at the far south end of Parc de la Villette. Correct stop is Porte de la
     Villette on Line 7. Corrected in both the day card and the transit cheat-sheet.
   - Montmartre funicular fare listed at EUR2.15 (stale "t+" ticket). 2026 single fare is EUR2.55.
4. **nyc-parking-revenue** — page states it uses the Schwartz "Digital City Map" figure of ~1,027,844
   parkable spaces "for every revenue scenario", but three passages said "~1.1 million" (which is the
   *Google-estimates* column the page explicitly declined to use). One of them drove a published number:
   $258M spread over "~1.1 million" spaces gave "$230 a year, or roughly 64 cents a day". Recomputed on
   the page's own denominator: $251/year, ~69 cents/day. Aligned all four.
   (Waterfall arithmetic, MTA budget shares, cost-per-trip and fare-evasion figures all reverified: OK.)
5. **subway-vs-street-crime** (password-gated) — the "all index crimes" chain rested on a wrong input:
   grand larceny listed as 15,802 for 2023. Actual 2023 NYPD complaint count is **50,514** (grand larceny
   is by far the largest index category in NYC). Grand larceny auto was also off (13,741 vs 15,797).
   The tell: the page's own citywide total (126,678) is correct and its components summed to only ~89,900.
   Verified against NYPD Complaint Data Historic (qgea-i56i), 2023, by report date; murder (386),
   robbery, felony assault, rape and burglary all matched, isolating grand larceny as the error.
   Recomputed the chain the page itself lays out: street total index ~48,000 -> ~59,000;
   street rate 30.00 -> 36.88 per million person-hours; all-index ratio 11.54x -> 14.18x;
   bottom-line range "6-12x" -> "6-14x". The direction of the argument is unchanged and slightly
   strengthened. Violent-index (7.9x) and violent+misdemeanor (6.0x) chains were unaffected and verified.
6. **lolas-library** (and the personal/ copy) — "two-time Newbery Honor author Margi Preus". Preus has
   one Newbery Honor (Heart of a Samurai, 2011). Changed to "Newbery Honor author" in both copies.
7. **nyc-performance-dashboard** and **vital-city-tools/neighborhood-story-finder** — both dated NYPD
   crime by occurrence date (cmplnt_fr_dt) rather than report date (rpt_dt), undisclosed.
   Measured the effect on 2026 felonies (5uac-w243): occurrence-dated counts run 2.6% short in January
   but 10.1% short in the latest month (Jun: 13,841 vs 15,397), because crimes occurring recently but
   not yet reported are missing from the file. Both dashboards compare a current period against a prior
   period, so the artifact systematically manufactures an apparent decline at the right edge every
   refresh. Switched all date filters/bins to rpt_dt in both.
   - nyc-data/crime-per-walker checked: correct already — filters on rpt_dt, uses cmplnt_fr_dt/tm only
     to classify time-of-day slots, which is the right use.
   - No project uses the misspelled variants; the RPT_DT rule holds everywhere else.

## JUDGMENT CALLS
A. **nyc-data/nyc-assault-tracker** — also dates everything by occurrence (cmplnt_fr_dt), but unlike the
   two above it *discloses* this ("All counts are based on the date of occurrence, not the date of
   report"). Mixed case: its day-of-week and time-of-day breakdowns genuinely need occurrence date,
   but its headline monthly/annual trend lines carry the same ~10%-in-the-latest-month understatement,
   and it bills itself as a continuously updating tracker. Recommend: keep occurrence date for the
   when-did-it-happen cuts, switch the trend series to rpt_dt. Not changed — it's a real design call.

B. **vital-city-tools/nyc-sidewalk-sheds** — RESOLVED 2026-07-28. The live Vital City page said
   "Numbers update nightly" while its data sat at `as_of: 2026-04-27` (92 days) because the nightly
   workflow the README described had never actually been applied — there was no `.github/workflows`
   directory, so nothing ever ran. Fixed by porting the hardened pipeline from the sibling
   joshgreenman1973/nyc-sidewalk-sheds rebuild:
     - refresh.yml (nightly 07:20 UTC) + staleness-check.yml (opens an issue if data >3 days old)
     - build_data.py replaced: atomic writes, gated on validate.py (count floors/ceilings, NYC
       coordinate bounds, all five boroughs present, duplicate BINs, 35% swing guard)
     - data refreshed 7,439 -> 7,130 active sheds; verified against an independent run of the same
       pipeline in the sibling repo, which produced an identical count
     - sheds.json gained a `complaints` field that assets/js/app.js already read but the April data
       never contained — a latent bug on the live embed, now fixed
     - README section rewritten (it had claimed the workflow was "applied separately")
   Pushed to vitalcity-nyc/main as 79df5de; Pages redeployed and the live page verified rendering
   today's data with no console errors.
   NOTE: the repo's `default_workflow_permissions` is "read". refresh.yml declares `contents: write`
   at job level, which should elevate, but the first unattended run is the real test.

## HOUSEKEEPING NOTED
- Stale local clones (live remotes are ahead; edit these only after fetching):
  vital-city-tools/neighborhood-story-finder (was 70 days behind — synced during this audit),
  nyc-vice-map (81 days behind; its weekly CI refresh is healthy),
  personal/lolas-library (duplicate clone of the same repo as top-level lolas-library, 3 commits behind).
- Verified healthy auto-refresh: nyc-sidewalk-sheds (JG), nyc-wild-census, nyc-nypd-officer-profiles,
  nyc-vice-map, nyc-mamdani-transcripts, vital-city-catalogue, nyc-data/nyc-building-age.
- nyc-vendor-ledger's "daily" refers to Checkbook NYC's own cadence, not the site. Correct as written.
