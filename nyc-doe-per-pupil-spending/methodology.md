# Methodology: NYC per-pupil K-12 spending infographic

**Last updated:** July 28, 2026
**Author:** Built with Claude Code, from public government sources only.

## Purpose

To present NYC Department of Education (DOE) per-pupil spending with full transparency about where each number comes from, what each number does and does not include, and which questions public data cannot answer.

## Correction notice (July 27, 2026)

A fact check on this date found that several figures in earlier versions of this page were estimates rather than sourced data, and were presented without saying so. They have been replaced with values read directly from source files, or removed. The specific corrections are listed in the "Corrections log" section at the end of this document. Anyone who used an earlier version of this page should re-check any figure taken from it.

## Scope

- **Geography:** NYC DOE district schools. Charter schools are shown separately (Section 3) and are excluded from the Census spending series, because New York law treats them as separate local education agencies.
- **Grade levels:** PreK-12 as each source defines it. Grade coverage differs between sources and is noted per figure.
- **Fiscal years:** NYC fiscal years run July 1 to June 30. FY2024 = July 2023 to June 2024. NYSED school years are labeled by span (2025-26). These two conventions are not interchangeable and are kept distinct throughout.

## Data sources

### Primary (official government only)

| Source | Use |
|---|---|
| U.S. Census Bureau, *Annual Survey of School System Finances* (F-33), summary tables FY2016-FY2024 | All per-pupil, total district spending, enrollment, and cross-district figures |
| NYSED, BEDS Day public school enrollment files (all students; students with disabilities), 2012-13 to 2025-26 | Charter vs. district enrollment; students-with-disabilities shares |
| NYC Independent Budget Office, *Annual DOE Spending: 2024 Shifts*, June 17, 2025 | FY2024 total ($40B), operating ($33B), school-related programs breakout, fringe benefits ($4.5B), pupil-teacher ratio, funding source mix, building age |
| NYC Council Finance Division, *Report on the Fiscal 2019 Preliminary Budget for the DOE* (March 2018) | U/A-level operating-budget breakdown (schools vs. central administration vs. other) |
| NYC DOE, *School Based Expenditure Report*, FY2018 | Functional per-pupil breakdown (classroom instruction, admin, etc.) |
| NYC Comptroller, *Course Correction* (due-process special ed report) | Due-process settlement totals, Carter/Connors aggregate |
| NCES, *Condition of Education* | National IDEA participation rate, used only as a flagged, non-comparable reference |

### Deliberately not used

Think-tank and advocacy figures were encountered during research and are **not** on the page. Two were removed during the July 2026 fact check specifically because they are not government sources:

- The Citizens Budget Commission's $42,168 FY2026 fully-loaded per-pupil projection.
- A $448M FY2025 central-administration figure that could not be traced to a primary document.

Both may well be accurate. They are excluded because this page's stated rule is government sources only, and applying that rule selectively would make the rule meaningless.

**One deliberate, labeled exception (July 28, 2026).** Sections 4 and 5 carry figures from two Chalkbeat New York articles: hold harmless totals and school-level examples, and class-size budget-negotiation figures. These are not government documents. They are included because the school-level and budget-negotiation detail is not published in any form this page could verify from source files, and omitting it would leave the two policies described but unquantified. Every such figure is inside a boxed, orange-labeled block marked "Reported figures, not primary-verified," is separated in the source list under its own heading, and is never mixed into a chart alongside government data. The distinction is visible to the reader rather than resolved silently.

## Key figures and how each was derived

### Headline metrics

- **$40B total DOE spending, FY2024** - IBO June 2025 press release, verbatim: actual spending totaled $40 billion.
- **$35,796 per pupil, FY2024** - Census F-33 Table 18, NYC row, "Current spending / Total" column, from the release published May 2026. District only; excludes charters, capital outlay, and debt service.
- **Rank 1 of the 100 largest districts** - Census F-33 Table 18 rank column. Verified as rank 1 in each of FY2016 through FY2024 by reading each year's table.
- **Pupil-to-teacher ratio 9.4, down from 12.1 in 1990** - IBO June 2025 release.

### Section 1: the per-pupil trend (FY2016-FY2024)

Every point read directly from Census F-33 Table 18, NYC row, in that fiscal year's own summary-tables workbook:

| FY | Per pupil |
|---|---|
| 2016 | $24,109 |
| 2017 | $25,199 |
| 2018 | $26,588 |
| 2019 | $28,004 |
| 2020 | $28,828 |
| 2021 | $29,931 |
| 2022 | $35,914 |
| 2023 | $33,387 |
| 2024 | $35,796 |

The FY2022 peak reflects federal pandemic relief (ESSER). The FY2023 decline to $33,387 is in the published series and is the first year-over-year fall in this series.

**Total spending toggle.** The total-dollar view is read from Census F-33 **Table 16**, NYC row, "Current spending" column (thousands, converted to billions): $26.26B, $27.48B, $29.05B, $30.37B, $31.27B, $31.13B, $34.76B, $32.67B, $34.97B for FY2016-FY2024 respectively.

**Important:** the total is *not* the per-pupil figure multiplied by the enrollment column. Census computes per-pupil amounts on a pupil base that differs from the fall-membership count it prints in the same table; for FY2024 the implied per-pupil base is roughly 977,000 against a printed enrollment of 845,509. Census does not publish the per-pupil base directly. Both series are reproduced as published and are **not** reconciled here. An earlier version of this page derived totals by multiplication, which produced figures $2B-$4B off from the published totals.

**Nominal dollars.** No figure on the page is inflation-adjusted. Consumer prices rose substantially over FY2016-FY2024, so real growth is materially smaller than the nominal growth shown. A real-dollar version would be preferable and is not currently included.

**Y-axis.** The default view does not start at zero, which amplifies year-to-year movement. A zero-baseline toggle is provided.

### Section 2: spending vs. enrollment

- Enrollment from Census F-33 Table 18 enrollment column: 981,667 (FY2016) falling to 845,509 (FY2024), **-13.9%**.
- Total current spending from Table 16: $26.26B to $34.97B, **+33.2%**.
- Published per-pupil: $24,109 to $35,796, **+48.5%**.

Because per-pupil grew faster than spending, the pupil base Census used for the per-pupil calculation must have fallen roughly 10% over the period. That is stated as an arithmetic consequence of two published series, not as an independent measurement.

The page does **not** publish a "what per-pupil would be at flat enrollment" counterfactual. An earlier version did; it relied on treating the printed enrollment column as the per-pupil denominator, which the paragraph above shows is incorrect.

### Section 3: charter enrollment

Computed from NYSED BEDS Day school-level enrollment files, summing PreK-12 enrollment for all schools in the five NYC counties (Bronx, Kings, New York, Queens, Richmond) and splitting on NYSED's own "School Type" field (values: Public, Charter).

| School year | Charter | District | Charter schools | Charter share |
|---|---|---|---|---|
| 2012-13 | 58,493 | 985,388 | 159 | 5.6% |
| 2015-16 | 94,334 | 980,197 | 205 | 8.8% |
| 2019-20 | 128,951 | 934,109 | 260 | 12.1% |
| 2021-22 | 139,315 | 846,833 | 271 | 14.1% |
| 2023-24 | 143,575 | 832,218 | 274 | 14.7% |
| 2025-26 | 149,879 | 810,653 | 285 | 15.6% |

(The chart plots all fourteen years; the table above is a sample.)

Over the full span the district lost 174,735 students and charters gained 91,386. Counting both sectors, total NYC public enrollment fell 8.0%, against 17.7% for the district alone.

**This is not a transfer statistic.** An earlier version of this section said charter growth "accounts for roughly half of the district's enrollment loss." That was a causal claim the data does not support, and it has been removed. The two series are independent headcounts. A child entering a charter kindergarten was never enrolled in a district school, so charter gains cannot be read as district departures. District enrollment also fell for reasons not measured here at all - declining births in the city, out-migration, and shifts to private schooling or homeschooling. No source used on this page apportions the district decline among these causes, and the page does not attempt to.

**Comparability caveats.** BEDS Day is a fall snapshot collected by NYSED; Census F-33 enrollment comes from the NCES Common Core of Data. The two differ by roughly 10,000-30,000 students for the same nominal year and are not interchangeable. This section covers enrollment only; charter per-pupil spending comes from a separate funding stream and is not in the Census district series or the IBO breakdowns.

### Section 4: hold harmless

**Mechanism** (from DOE Fair Student Funding documentation): schools are budgeted in spring on projected enrollment; actual enrollment is counted in fall; mid-year the budget is normally trued up in both directions. Hold harmless switches off the downward adjustment only. Schools that gain students still receive increases. The cost is the difference between the formula-generated allocation and the protected allocation, paid centrally.

**Government figure:** NYC Public Schools, *SY2025-2026 Class Size Reduction Plan*, states verbatim that "New York City has invested a total of $1.2 billion since FY 2021 in 'hold harmless' funding for schools losing enrollment to ensure they can maintain services." DOE also announced a mid-year hold harmless in November 2024 (Chancellor Aviles-Ramos) and has extended the policy since.

**Non-government figures, boxed and labeled on the page.** The annual and cumulative totals, the school counts, and both school-level examples come from Chalkbeat's June 22, 2026 analysis of DOE data: about $290 million in 2025-26; 723 schools receiving funds with 55 above $1 million each; nearly $1.9 billion cumulatively since 2020; I.S. 339 in the Bronx at roughly $2.5 million of a $7.8 million budget with enrollment down from 315 to about 150; Urban Assembly Institute of Math and Science for Young Women at roughly $374,000 with enrollment down from nearly 500 to about 350.

**Unresolved discrepancy, stated on the page.** DOE says $1.2 billion since FY2021. Chalkbeat says nearly $1.9 billion since 2020. Citizens Budget Commission testimony put 2025-26 near $400 million against Chalkbeat's $290 million. Start dates and definitions differ and no published document reconciles them. This page reports the spread rather than choosing.

### Section 5: class size mandate

All statutory and compliance detail from NYC Public Schools, *SY2025-2026 (FY2026) Class Size Reduction Plan*, and Chapter 556 of the Laws of 2022:

- Caps under Chapter 556: K-3 = 20, grades 4-5 = 23, grades 6-8 = 23, grades 9-12 = 25, PE and performing groups = 40. Prior UFT contract caps were 25/32/32/30-33/34/50.
- Phase-in by share of classes: 20% SY2023-24, 40% SY2024-25, 60% SY2025-26, 80% SY2026-27, 100% SY2027-28.
- SY2024-25 result: 46% of classes at or below caps, exceeding the 40% requirement.
- SY2025-26: over 800 school applications; funding notified in April for 3,700 teachers and more than 100 assistant principals; DOE expected to spend over $400 million.
- Exemptions require the circumstances to fit a statutory category and agreement of the Chancellor, the UFT president, and the CSA president.

**IBO estimate:** up to 17,700 additional teachers at roughly $1.6-$1.9 billion annually at full compliance. Capital cost estimates vary widely across published sources and the page does not select among them.

**Non-government figures, boxed and labeled on the page.** From Chalkbeat, April 2, 2026: $543 million in the Mamdani preliminary budget for the coming fiscal year, $943 million annually for the three years after, a projection of roughly $1.7 billion annually at full implementation, a proposed extension to four years (about 70% by September plus 10 points a year), State Senator Liu's position that timeline changes are not fiscal relief, and a $600 million Assembly proposal. These are budget-negotiation figures as reported; the enacted outcome is not reflected.

### Section 6: FY2024 $40B breakdown

All figures from the IBO June 17, 2025 release:
- Operating budget: $33B
- Pensions + debt service outside operating: $40B - $33B = ~$7B (arithmetic residual, labeled as such)
- School-related programs: $19B, comprising general ed schools $8.4B, charter schools $3.1B, categorical funding $2.7B, special education $2.4B, Pre-K $1.8B
- Fringe benefits: $4.5B
- Central services and overhead: $33B - $19B - $4.5B = ~$9.5B (arithmetic residual, labeled as such)

Slice labels on the chart are plain-English descriptions written for this page, not IBO's own category names. The caption states what each contains.

**No general-education per-pupil figure is published here.** Dividing the $8.4B general education schools line by any published enrollment count would mix a spending line and a student population that do not correspond. An earlier version of this page did exactly that, producing a "~$10,300 per pupil" figure on an invented 813,000 denominator. It has been removed.

### Section 7: schools vs. central administration vs. everything else

From the NYC Council Finance Division's Fiscal 2019 Preliminary Budget report on the DOE, aggregating U/A-level lines into five buckets:

| Bucket | FY2019 | Notes |
|---|---|---|
| Schools | $14.7B | GE instruction, SE instruction at district schools, charter payments, UPK, early childhood, school support orgs, categorical |
| Staff health and welfare benefits | $3.5B | Centrally budgeted fringe, mostly covering school-based staff |
| Operations | $3.7B | Facilities, pupil transportation, food, safety, energy and leases |
| Central SPED + non-public payments | $3.4B | District 75 and citywide SPED support, SE Pre-K contracts, contract schools / Carter cases, non-public / FIT |
| Central administration | $0.345B | U/A 453 + 454, supporting 2,055 FTE |

Total: $25.6B FY2019 Preliminary operating budget. Central administration is about **1.35%**.

**Two significant caveats, both stated on the page.** First, these are Fiscal 2019 *Preliminary Budget* figures - a plan, not actuals - and are now seven years old; the operating budget has grown substantially since. Second, the five buckets are groupings made by this page, not categories the Council publishes; a different reasonable grouping would shift dollars between bars. The chart caption lists which lines went into each bucket so the grouping can be audited.

Fringe is shown as a separate bar because that is how it appears in the budget document, but economically most of it is compensation for school-based staff. Schools plus fringe is about 71% of the operating budget.

### Section 8: FY2018 functional breakdown

Directly from NYC DOE School Based Expenditure Report FY2018 citywide summary:

| Category | Per-pupil |
|---|---|
| Classroom instruction | $12,276 |
| Instructional support services | $4,183 |
| Leadership / supervision | $2,087 |
| Ancillary support services | $1,970 |
| Building services | $1,650 |
| *Direct services to schools subtotal* | *$22,170* |
| Field support costs | $506 |
| System-wide costs | $738 |
| System-wide obligations (pensions etc.) | $2,853 |

Grand total $31.6B over 1,021,229 enrollment. Pass-throughs (~$4.8B, mostly charter and contract schools) are excluded from the per-pupil calculation.

**This is the last year DOE published SBER.** No post-2018 equivalent exists, so there is no current official functional split of classroom vs. administration vs. overhead.

### Section 9: special education

**Published:**
- $2.4B "special education" within school-related programs (IBO June 2025). This is a narrow line: it excludes District 75, most classroom-level special ed embedded in general ed schools, and Carter/Connors tuition.
- $1.3B FY2025 due-process and $101,757 average settlement (NYC Comptroller, reproduced in the [companion tracker](https://joshgreenman1973.github.io/experiments/nyc-special-ed-spending/)).
- $47M FY2005 due-process baseline (Comptroller, *Course Correction*).

**Not in the public record:**
- District 75 per-pupil spending.
- Carter vs. Connors disaggregation - DOE has stated it cannot separate these.
- Recipient-school list for Carter/Connors payments.
- Any all-in special education total combining embedded general-ed SPED, District 75, and Carter/Connors.

### Section 10: why NYC is higher

FY2024 gap: NYC $35,796 vs. U.S. average $17,619 = **$18,177**.

**No dollar decomposition is published.** An earlier version of this page carried a bar chart splitting the gap into amounts for special education mix, staffing levels, and teacher pay. Producing those bars required assuming a fully-loaded cost per teacher and an excess cost per special education student. No official source publishes either for New York City, so the splits were assumptions presented as findings. The chart has been removed and is not replaced with a corrected version, because no government source decomposes the gap.

**Students with disabilities**, computed from a single NYSED BEDS Day 2024-25 file so the first three are directly comparable:

| Group | Share |
|---|---|
| NYC district schools | 24.4% |
| NYC charter schools | 20.8% |
| New York State, all public | 19.8% |
| U.S. reference (NCES, IDEA ages 3-21, SY2022-23) | 15.0% |

The national figure uses a different collection, year, and age range, and is flagged on the chart as not directly comparable. An earlier version showed NYC at 20% alongside unsourced peer-city bars (including an implausible 7% for Houston); those have been removed.

**Documented cost factors**, listed without apportioning the gap: pupil-teacher ratio 9.4 vs. 12.1 in 1990 (IBO); students with disabilities 24.4% (NYSED); average school building age 75 years (IBO); funding mix 52% City / 35% State / 12% Federal (IBO).

### Section 11: cross-district comparison

Census F-33 FY2024 Table 18, every district read from the same table so all bars share a year and definition: NYC $35,796; District of Columbia $31,529; Atlanta $26,117; Los Angeles Unified $25,631; San Francisco Unified $25,173; Chicago $24,330; Detroit $21,406; Philadelphia $19,525; U.S. average $17,619; Clark County $14,774; Houston $13,950; Miami-Dade $13,931; Broward $13,412.

Boston appeared in earlier versions and has been removed: it is not among the 100 largest systems, so it is not in this table, and the figure previously shown was from a different year.

**Comparability caveat.** Per-pupil spending is heavily shaped by state funding systems, regional labor costs, and cost of living. These bars are not a measure of efficiency or of how much money reaches classrooms.

## Assumptions and limitations

1. **Nominal dollars throughout.** No inflation adjustment. Real growth is materially smaller than shown.
2. **Enrollment denominators are not interchangeable.** Census F-33 (NCES CCD fall membership), NYSED BEDS Day, and IBO's "total enrollment" (which includes charter, contract, and Pre-K students) all differ. Figures are never divided across sources.
3. **Census per-pupil is not total divided by printed enrollment.** See Section 1. The page does not reconcile the two.
4. **SBER freeze at FY2018.** No current official functional breakdown exists.
5. **The Council FY19 chart is old and its bucketing is editorial.** See Section 5.
6. **Special education is under-represented in every simple breakout.** The $2.4B IBO line is not a total.
7. **No outcomes data.** The page reports spending only. It makes no claim about results, efficiency, or value.
8. **Visual verification was limited.** Chart data was verified programmatically against the source files. Full visual rendering could not be confirmed in the available preview environment.

## Reproducibility

Census F-33 summary tables: `https://www2.census.gov/programs-surveys/school-finances/tables/<YEAR>/secondary-education-finance/elsec<YY>_sumtables.xlsx` (older years use `.xls`). NYC is the rank-1 row of Tables 16 and 18.

NYSED BEDS Day files: archive at `https://www.p12.nysed.gov/irs/statistics/enroll-n-staff/ArchiveEnrollmentData.html` (files named `PublicSchool<YYYY>AllStudents.xlsx`, where the year is the spring of the school year); recent years at `enrollment-public-school-<SPAN>-all-students.xlsx`.

To update: pull the IBO annual DOE Spending release each June, the Census F-33 tables each May, and the NYSED BEDS Day files each fall.

## Corrections log

**July 27, 2026 fact check.** The following were wrong or unsupported in earlier versions:

| Item | Was | Now |
|---|---|---|
| Per-pupil FY2016 | $22,850 | $24,109 |
| Per-pupil FY2017 | $24,147 | $25,199 |
| Per-pupil FY2018 | $25,199 | $26,588 |
| Per-pupil FY2019 | $26,588 | $28,004 |
| Per-pupil FY2020 | $28,004 | $28,828 |
| Total spending, all years | Derived by multiplication, $2B-$4B off | Census Table 16 as published |
| Enrollment, FY2016-FY2022 | Rounded guesses; FY2017 shown falling when it rose | Census Table 18 as published |
| Per-pupil growth FY16-FY24 | +57% | +48.5% |
| Spending growth FY16-FY24 | +35% | +33.2% |
| NYC students with disabilities | 20% | 24.4% (NYSED 2024-25) |
| Peer-city IEP bars | Unsourced, incl. Houston 7% | Removed |
| Cross-district comparison | Mixed FY2021/FY2022, incl. Boston | All FY2024, Boston removed |
| Gen-ed per-pupil | "~$10,300" on invented 813,000 denominator | Removed, with explanation |
| NYC-vs-US dollar decomposition | Bars built on assumed teacher and SPED costs | Removed, replaced with documented-factors table |
| CBC $42,168 FY2026 projection | Plotted on the trend chart | Removed (not a government source) |
| $448M FY2025 central admin | Stated in a callout | Removed (untraced attribution) |
| Charter enrollment | "~140,000 students, ~275 schools" in passing | Full NYSED series, 2012-13 to 2025-26 |
| Sections 4-5 added (hold harmless, class size mandate) | Not covered | Added July 28, 2026 |
| Charter section framing | Headed "Where the students went"; claimed charter growth "accounts for roughly half of the district's enrollment loss" | Reframed as a counting point, not a transfer or causal claim |

The per-pupil series error was systematic: values for FY2017-FY2020 had each been assigned to the following year, understating every year in that range.

## Contact

Corrections welcome. Report issues at https://github.com/joshgreenman1973/experiments/issues.
