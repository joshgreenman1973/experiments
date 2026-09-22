# MMR explorer audit and fixes — September 18, 2026

## Scope and evidence

Reviewed the live site, its source and build documentation at commit `9a4aa557e030f04f0ac24e5ac021698b851e2f31`, the original build prompts (as historical context, not instructions), and the supplied 544-page FY2026 MMR. The supplied PDF matches the build source: SHA256 `c37349e065e6306d972fc2a2ec2cb8c053efc48fea276c631f62caefd44fcb7d`. Live app, HTML, methodology and principal data files matched the original checkout.

A fresh source download contained 768,409 indicator rows. An independent June-row comparison checked all 49,219 originally populated FY2016–2025 cells across citywide and geographic series, including clock conversion, with no discrepancies. Twenty duplicate indicator-year June rows carried identical values. This establishes faithful transcription of those source cells, not correctness of the city's definitions.

An independent PDF extraction using column coordinates uniquely matched 1,992 of the original 2,029 extracted records numerically. Another 36 had multiple numerical candidates; one DCLA row needed visual review because its page lacked the expected year header. No historical numeric discrepancy was found among the uniquely matched, non-restated rows. Repeated numbers cannot prove row identity. These checks do not certify every label, chapter footnote or newly introduced indicator.

All 23 original ratios and all 238 plotted points reproduced arithmetically. The important errors were in interpretation, source precedence, scoring and interface behavior.

## Implemented fixes

| Problem | Correction and evidence |
| --- | --- |
| Exact equality was called deterioration at a zero threshold | Equality is always unchanged. The original FY2025–26 pool contained 108 affected indicators. |
| Stale desired directions reversed results and target judgments | Preserve directions by reporting year; use the printed FY2026 direction for that year. Found 18 metadata conflicts. For example, Pre-K vacant seats fell from 15,181 to 12,609: an improvement under the report's **Down** direction, meeting its 12,881 target. |
| Directional targets disappeared | Preserve printed arrows separately from numeric targets; distinguish them from no printed target and extraction gaps. The original parse lost 174 directional targets. |
| Larger DOB revisions prevented matching | Add five explicitly reviewed mappings, checked against both old and revised histories. Values are on PDF page 371; the revision explanation is on page 375. |
| Historical comparisons mixed publication vintages | Use available printed FY2022–25 history with FY2026, retaining differing Open Data values visibly in each drawer. Repeated PDF builds restore original matching inputs first; repeated matching produced identical record output. |
| Final spending actuals were ignored | Read PMMR `previous_fy_actual` into the preceding year, superseding provisional MMR actuals; exclude budget plans. DOC FY2025 expenditures change from $1,342.6m to $1,356.2m. Divided by average custody population 6,823, this changes the displayed departmental spending ratio from $196,776 to $198,769. |
| Missing staffing components could masquerade as a total | Require both uniformed and civilian counts before summing a total; retain resource provenance. |
| Missing years counted as consecutive | Streaks break at missing years; biggest annual steps require adjacent years; compounded growth excludes zero-crossing series. Flagged observations are excluded from derived statistics. |
| A documented library definition change looked like a performance change | Mark the FY2026 six-day-opening denominator break for four library indicators, based on PDF page 321. Preserve figures but exclude comparisons crossing the break. This is a specific reviewed break, not a comprehensive footnote inventory. |
| Percentage-point ranking mixed incompatible units | Restrict this ranking to percentage indicators. Make outlier time windows and selected-year recount checks explicit. |
| Ratio labels and explanations overstated meaning | Correct personnel/overtime component labels; retain full numbers and component names; correct TLC, CCRB and library interpretations; enforce known matching reporting periods and 0–100 bounds for true shares. |
| Controls and URLs could describe different comparisons | Rebuild year controls after automatic baseline adjustment; encode comparison years, threshold and filters in shareable URLs. Ratio charts use the selected window and their own year axes. |
| Indicator drawers allowed keyboard focus to escape | Contain focus, make background inert and restore focus on closing. Add keyboard sorting and native agency buttons. |
| Display and provenance errors | Correct seconds rounding, display actual build date, explain extraction gaps honestly, preserve raw precision, and stop describing FY2026 as still underway. |
| Build could silently reuse stale text or save partial downloads | Key extracted text cache to PDF checksum; provide PDF refresh; replace raw snapshots only after expected row-count validation. Completed Open Data observations take priority over the PDF fallback. |

The rebuilt overlay contains 2,042 matched records, including 2,006 FY2026 values and 565 numeric FY2026 targets. These counts include target-only records and should not be confused with the smaller live, citywide scoreboard universe.

## Ratio review

Do not rank all these as if they were efficiency or success rates. Three different questions are being asked: composition of a total, balance between separate flows, and agency resources relative to one activity. Keep those distinctions prominent.

**Best candidates to feature:** shelter exits relative to arrivals, subsidized exits as a share of housing exits, DOB complaint responses relative to receipts, overtime as a share of agency expenditures, and homeless applicants' share of direct public-housing placements. The flow comparisons do not track the same cohort, and housing-exit composition cannot establish that a subsidy was necessary or caused an outcome. DOC spending per average person in custody is useful with its explicit departmental cost scope; it is not the fully loaded cost of incarceration.

**Move lower or reconsider:** total DSNY budget per ton and tons per employee have an unrelated-function problem (street cleaning, snow and other work); potholes per work order describes administrative bundling more than service quality; circulation per non-expired library card is sensitive to card administration; arrests divided by reported crimes is not a clearance rate. These can be exploratory calculations, but are weak headline measures of agency performance.

**Two material corrections already made:**

- TLC inspections passed / inspections conducted includes initial inspections and retests: 77.0% in FY2026 is an inspection-event pass share. It is not a first-pass rate. The separately printed initial-inspection failure rate is 29.9%, implying 70.1% initial passes (PDF page 196).
- CCRB substantiated complaints / all case closures is 15.1% in FY2026. CCRB's official substantiation rate uses fully investigated complaints as the denominator. Closure categories also do not exactly reconcile with total cases closed. See CCRB's [definition illustrated in its protest-case snapshot](https://www.nyc.gov/assets/ccrb/downloads/pdf/policy_pdf/issue_based/Protest-Data-Snapshot-March-2024.pdf); that source defines the denominator, not the explorer's FY2026 rate. Prefer the official rate if a compatible annual series is obtained.

### Additions worth pursuing

1. **OATH default decisions as a share of all decisions.** IDs `15920 / 15918 × 100`. On PDF page 136, default and hearing/administrative decisions sum exactly to all decisions in each of FY2022–26. Shares are 61.5%, 64.3%, 67.4%, 68.0% and **66.1%**; FY2026 is 453,811 / 686,960. The default category includes auto-default, default and guilty-after-inquest decisions. Count decisions, not unique people; do not infer a cause such as lack of notice. This is the strongest near-term addition.
2. **Shelter re-entry comparison by housing-exit type.** Display the existing subsidized and unsubsidized re-entry percentages side by side, with a percentage-point gap, rather than another opaque quotient. For single adults FY2026 shows 2.8% versus 21.0%, an 18.2-point difference. Confirm cohort and follow-up definitions before implementation. Selection into housing types prevents treating the gap as a causal subsidy effect.
3. **Restore service-specific cost measures where valid sources exist.** Prefer refuse collection cost per ton to total DSNY spending per ton, and the official fully loaded jail cost alongside departmental spending. These require additional sources with aligned years, scope and inflation treatment; they cannot be manufactured from the current denominators.

### Plausible additions rejected or held

- **Homeless share of Section 8 placements (`11073 / 3179`):** FY2023 gives 3,775 / 2,974 = 126.9%. Labels do not establish a coherent subset. Reconcile definitions or revisions before publishing any year as a share.
- **Remote OATH hearing share:** FY2022 phone plus online hearings already exceeds all hearings (220,580 / 204,952). FY2026 modes reconcile, but a continuous historical share needs the earlier discrepancy resolved.
- **SYEP participants / applications:** a fiscal-year label can combine the previous summer's participants and the next summer's applications. Verify the summer cohort before calling this an acceptance or coverage rate.

These candidate ratios are recommendations, not silently added production metrics.

## Next features, in priority order

1. **Coverage and source status:** for each agency show published/matched/scorable counts, missing-year reasons, PDF links and a queue of unmatched rows. It would reveal how much a ranking depends on extraction coverage.
2. **Fixed-cohort comparison:** let readers compare agency trends using the same indicator set in every selected year. Today's headline changes can reflect changes in the measured population as well as performance.
3. **Download the evidence:** CSV exports with full precision, units, reporting period, desired direction, source page, original/revised values and current filters. Shareable state links are already implemented in this patch.
4. **Compare related indicators together:** pairs of counts, rates and denominators, with a structured distinction between a share, a flow comparison and a resource-intensity ratio. This is particularly valuable for shelter and OATH.
5. **Footnotes and target view:** a structured revision/definition timeline and a separate target-achievement view. Improving is different from meeting a target; neither is an overall agency grade.

## Validation and remaining limits

Run `python3 -m unittest discover -s tests -v`, `node tests/test_app.cjs`, and `node --check app.js` from this directory. Tests cover source precedence, real revised records, direction and targets, missing-year statistics, definition breaks, formatting, equality and every generated ratio's arithmetic. Fourteen Python tests and the JavaScript regression assertions pass. Browser checks cover all six main views, comparison controls and URL restoration (including empty filters), ratio rendering, drawer content and keyboard containment. A narrow mobile preview showed no page-level horizontal overflow. No browser warnings or errors were captured during these checks. The PDF matcher was repeated against its rebuilt output and produced identical matched records.

Most PDF footnotes remain unstructured. Numerically ambiguous matches still need semantic review. School/calendar/fiscal reporting periods remain different. Indicator counts have no importance weighting and are correlated; an agency ranking is not a statistically independent sample or comprehensive performance grade. A selected period does not eliminate composition changes. Future source releases and new indicators require review rather than blind trust in the parser.

The fixes and regenerated data are published from the repository’s main branch through GitHub Pages.


## Follow-up: stricter ratios and full trend context

The earlier recommendations above are superseded by this implemented curation decision. The page now has **eight subset shares**, replacing the 23 assorted quotients. Retained: DHS subsidized exit shares (single adults and families with children), NYCHA homeless applicants’ share of conventional placements, TLC inspection-event pass share, and DOC/NYPD/FDNY overtime shares. Added: OATH default decisions / all decisions. Removed: three shelter exit/arrival comparisons; DOC spending/population; both DSNY spending or staffing/tonnage measures; two DOB response/receipt comparisons; graffiti closures/receipts; housing violation closures/issues; CCRB substantiations/all closures; arrests/crimes; all three circulation/card ratios; and potholes/work orders.

Each card now always shows five years, its complete component table, the latest arithmetic, and a percentage-point change. The scoreboard controls are hidden on this page and cannot crop those histories. No historical range is extended merely because earlier data exist.

Evidence for the displayed spans:

- DHS, NYCHA, TLC and OATH: both components are printed side by side in the FY2026 report's FY2022–2026 tables, PDF pages 265, 429, 196 and 136 respectively. Definitions in the raw FY2022–2026 observations were consistent for the ten component indicators. Reviewed change notes on pages 268, 432, 200 and 139 do not identify a break for these measures. DHS subsidized plus unsubsidized exits, and OATH default plus hearing/administrative decisions, reconcile to their totals in all five years.
- DOC, NYPD, FDNY: FY2021–2025 numerator and denominator each use the same resource categories and monetary units, with final prior-year actuals from the FY2022–2026 PMMR releases. The build enforces that final-actual field and fiscal-year alignment. These are shares of each agency's own reported expenditures; no claim about staffing adequacy or service quality follows from them.
- Library ratios are dropped because the historical comparability issue remains unresolved. The other removed comparisons either do not describe a subset of a common total or have a material scope mismatch. They are not retained merely with stronger caveats.

Build checks require all five reviewed years, matching period types, shares in range, no flagged values or known definition breaks, and component reconciliation where a complement is available. The curation is intentionally conservative; these checks still cannot guarantee that the source has disclosed every change.


## Implemented reader-navigation features

Added six topics and twelve curated questions; topic-led search with reviewed synonyms; comparison sets of up to four indicators; related measures; reading boxes separating change from target achievement; attributed chapter explanations with page links; chart markers for known definition breaks; and CSV exports with definitions, periods, sources, original values and flags. Existing deep links remain supported. Comparison selections are shareable through URL state, and the topic view is the default for new visits.

Curated relationships are stored in `data/guide.json`. Definitions were checked for all selected indicators. Chapter commentary was checked against the supplied PDF, including DHS page 265 and DOT page 358. It is identified as the agency's explanation, not an independently established causal conclusion. Other indicators use explicitly labeled same-goal suggestions and source links, without fabricated summaries.

Charts align years while keeping separate vertical scales. Different reporting periods generate a warning. Definitions and missing coverage remain visible. The comparisons do not reinstate any removed ratio or manufacture one from unrelated quantities. The new tests cover curated IDs, synonyms, selection validation, target judgments, revision/source exports and CSV escaping; browser checks cover reader journeys, link restoration, selection changes and mobile layout.
