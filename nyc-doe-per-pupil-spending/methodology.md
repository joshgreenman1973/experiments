# Methodology: NYC per-pupil K-12 spending infographic

**Last updated:** April 19, 2026
**Author:** Built with Claude Code, from public government sources only.

## Purpose

To present NYC Department of Education (DOE) per-pupil spending with full transparency about where each number comes from, what each number does and does not include, and which questions public data cannot answer.

## Scope

- **Geography:** NYC DOE traditional public schools, charter schools (as pass-through), and special education programs. Excludes SUNY/CUNY, private schools not receiving DOE funds, and non-DOE City agencies.
- **Grade levels:** K-12 primarily; 3-K and Pre-K are included where IBO reports them.
- **Fiscal years:** NYC fiscal years run July 1 - June 30. FY2024 = July 2023 - June 2024.

## Data sources

### Primary (official government only)

| Source | Use |
|---|---|
| NYC Independent Budget Office (IBO), *Annual DOE Spending: 2024 Shifts*, June 17, 2025 | FY2024 total ($40B), operating ($33B), school-related programs breakout, fringe benefits ($4.5B), pensions narrative |
| IBO, *Education Spending Tables*, June 2023 | Long-run DOE spending context, 1990-2022 |
| IBO, *Analysis of Board of Education Funding Trends* (1996) | FY1988-FY1997 per-pupil anchor points |
| IBO Education Indicators portal (ibo.nyc.ny.us/publicschool.html) | Enrollment, pupil-teacher ratio |
| NYC DOE, *School Based Expenditure Report*, FY2018 | Functional per-pupil breakdown (classroom instruction, admin, etc.) |
| NYC Comptroller, *Spotlight: School Budget Allocations* | FSF formula, total schools allocation FY2023 |
| NYC Comptroller, *Course Correction* (due-process special ed report) | Due-process settlement totals, Carter/Connors aggregate |
| U.S. Census Bureau, *2022 Annual Survey of School System Finances* (F-33), Table 20 | Cross-district "current spending per pupil" comparison |

### Not used

- Think-tank reports, advocacy group summaries, news articles, and state-level aggregates were consulted for orientation but are **not cited** on the page. Every number on the infographic traces to one of the sources above.

## Key figures and how each was derived

### Headline: $40B total, $36,000 per pupil (FY2024)

- **$40B total:** IBO June 2025 press release, verbatim ("actual spending totaled $40 billion").
- **Per-pupil denominator:** IBO reports ~1.1M total enrollment for recent years, including all general and special education students in DOE facilities, special education pre-K and school-age students in contract schools, 3K and Pre-K students in DOE sites and Early Education Centers, and charter school students. $40B / 1.1M ≈ $36,364, rounded to $36,000 to match IBO's own rounding in the release.
- **Caveat:** This is a "fully loaded" per-pupil figure (includes pensions and debt service outside the operating budget). It is not directly comparable to the Census Bureau's narrower "current spending per pupil" measure.

### Historical trend line

Six anchor points, each independently cited:

| Year | Value | Source | Methodology |
|---|---|---|---|
| FY1988 | $7,232 | IBO Funding Trends 1996 | Total per-pupil, nominal |
| FY1997 | $6,952 | IBO Funding Trends 1996 | Total per-pupil, nominal (budget figure, not actuals) |
| FY2018 | $26,266 | NYC DOE SBER FY2018 | Citywide public schools subtotal, per-pupil |
| FY2021 | $29,931 | Census F-33 | "Current spending per pupil" (excludes capital, debt) |
| FY2022 | $35,914 | Census F-33 | "Current spending per pupil" |
| FY2024 | $36,000 | IBO June 2025 | $40B / ~1.1M enrollment |

**Limitation:** These points use three different methodologies (IBO total, DOE SBER subtotal, Census current spending). The FY2021/FY2022 jump likely reflects both real COVID-era federal relief inflows and methodological differences versus SBER. The line on the chart is therefore indicative, not a single consistent series. A clean consistent series is charted in IBO's June 2023 Education Spending Tables but that source is published as images, not as a downloadable data table.

### FY2024 $40B breakdown (Section 2)

All figures directly from IBO June 17, 2025 release:
- Operating budget: $33B
- Pensions + debt service outside operating: $40B - $33B = ~$7B (derived)
- Within operating, "school-related programs": $19B
  - General ed schools: $8.4B
  - Charter schools: $3.1B
  - Categorical funding: $2.7B
  - Special education: $2.4B
  - Pre-K: $1.8B
- Fringe benefits: $4.5B
- "Other operating": $33B - $19B - $4.5B = ~$9.5B (derived as residual; includes central admin, support functions, and any items IBO did not separately enumerate)

The two derived figures ($7B pensions+debt, $9.5B other operating) are labeled as such on the chart and are arithmetic residuals from the IBO-stated components.

### FY2018 functional breakdown (Section 3)

Directly from NYC DOE School Based Expenditure Report FY2018 citywide summary:

| Category | Per-pupil |
|---|---|
| Classroom instruction | $12,276 |
| Instructional support services | $4,183 |
| Leadership / supervision | $2,087 |
| Ancillary support services | $1,970 |
| Building services | $1,650 |
| Direct services to schools subtotal | $22,170 |
| Field support costs | $506 |
| System-wide costs | $738 |
| System-wide obligations (pensions etc.) | $2,853 |
| Pass-throughs | Not per-pupil ($4.8B total, mostly charter) |
| Grand total | $31.6B / 1,021,229 enrollment |

**This is the last year DOE published SBER.** A follow-on post-2018 equivalent does not exist.

### Special education (Section 4)

- **$2.4B "special education"** - IBO June 2025 release, the narrowly-defined school-related-programs line. Excludes embedded special ed in general-ed schools, District 75, and Carter/Connors tuition.
- **$1.3B FY2025 due-process** and **$101,757 average settlement** - NYC Comptroller sources, reproduced in companion infographic [NYC special education due process spending tracker](https://joshgreenman1973.github.io/experiments/nyc-special-ed-spending/).
- **$47M FY2005 due-process baseline** - Comptroller's *Course Correction* report.

**Not in the public record:**
- District 75 per-pupil spending - DOE does not publish an annual D75-specific per-pupil figure.
- Carter vs. Connors disaggregation - DOE has stated on the record it cannot separate these.
- Recipient-school list for Carter/Connors payments.
- A total "all-in" special education spending figure that aggregates embedded general-ed special ed + District 75 + Carter/Connors.

### Cross-district comparison (Section 5)

U.S. Census Bureau, 2022 Annual Survey of School System Finances, Table 20 "current spending per pupil" for 100 largest school systems. Comparison values:
- NYC: $35,914 (FY2022)
- Boston: $31,397 (Census published Boston's most recent in FY2021 press release; noted on chart)
- Washington, D.C.: $27,425 (FY2022)
- San Francisco Unified: $23,654 (FY2022)
- Atlanta: $22,882 (FY2022)
- Los Angeles Unified: $21,940 (FY2022)
- Detroit: $21,771 (FY2022)
- Chicago: $18,216 (FY2021)
- U.S. national average: $15,633 (FY2022)

**Note on comparability:** Census "current spending per pupil" excludes capital outlay and debt service. That is why Census's NYC figure ($35,914) is lower than IBO's fully loaded $36,000 - though the two happen to land within rounding distance for FY2022/FY2024.

## Assumptions and limitations

1. **Nominal dollars, not inflation-adjusted.** The historical line is in then-current dollars. A real-dollar adjustment would compress the apparent growth substantially.
2. **"Total enrollment" denominator varies by source.** IBO includes pre-K, 3K, charter students, and contract-school special ed students. Census F-33 uses a narrower ADA-style count. This is one reason Census and IBO per-pupil figures diverge.
3. **SBER freeze (FY2018).** Without a post-2018 SBER, no current granular "classroom vs. admin" functional breakdown exists in official data.
4. **Special ed is systematically under-reported in simple breakouts.** The $2.4B IBO line is not a total-special-ed figure. A true total would sum embedded general-ed special ed + District 75 + Carter/Connors + related services + transportation carve-outs - and no single public document does that.
5. **All figures are as published.** No attempt was made to reconcile differences between IBO, DOE, Comptroller, and Census where they report the same concept with different numbers. Each chart cites exactly one source.

## Reproducibility

All sources are hyperlinked in the infographic's "Sources and methodology" section. All charts are static encodings of the numbers in this document; no live API calls. To update: pull the most recent IBO annual DOE Spending release each June and the Census F-33 district-level tables each spring.

## Contact

Corrections welcome. Report issues at https://github.com/joshgreenman1973/experiments/issues.
