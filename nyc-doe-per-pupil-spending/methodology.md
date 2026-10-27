# Methodology: per-pupil spending in New York City public schools

**Last updated:** Oct. 26, 2026
**Author:** Built with Claude Code from public sources, checked against primary documents.

## Purpose

To present New York City Department of Education (DOE) per-pupil spending with full transparency about where each number comes from, what each number does and does not include, and which questions public data cannot answer.

## Correction notice (Oct. 26, 2026)

A third review (Oct. 26, 2026) re-derived every Census, CPI, NYSED and IBO figure and re-read the hold harmless, class size and special education sources. It found no wrong Census, CPI or IBO numbers, but found wording that misdescribed several sources, one misstated IBO percentage in this note, and 2025-26 NYSED enrollment that has since been finalized. Those changes, and a new three-school comparison box, are listed at the top of the corrections log.

## Earlier correction notice (Oct. 7, 2026)

A second claim-by-claim check, against primary sources, found errors that survived the July 2026 fact check, plus figures that newer releases have superseded. They are listed in the "Corrections log" at the end of this document. The largest: the page's "total district spending" series came from a broader Census table than the per-pupil figure, which led to a wrong statement that Census uses an unpublished pupil base; New York City was described as ranking first every year from FY2016 to FY2024 (Boston ranked first in FY2021); the special education table carried three misattributed figures; and the IBO and central-administration sections used superseded or budget-only data. Anyone who used an earlier version of this page should re-check any figure taken from it.

## Scope

- **Geography:** DOE district schools. Charter schools are shown separately (Section 3) and are excluded from the Census spending series.
- **Grade levels:** pre-K-12 as each source defines it. Coverage differs between sources and is noted per figure.
- **Fiscal years:** New York City fiscal years (FY) run July 1 to June 30. FY2024 = July 2023 to June 2024. NYSED school years are labeled by span (2025-26). The two conventions are kept distinct throughout.
- **Dollars:** dollars as spent in the year shown, unless labeled as constant FY2024 dollars.

## Data sources

### Government and official sources

| Source | Use |
|---|---|
| U.S. Census Bureau, Annual Survey of School System Finances, summary tables and district files, FY2016-FY2024 (FY2024 released May 7, 2026) | Per-pupil series, enrollment, district spending, cross-district comparison, the national average and the composition of the gap |
| Bureau of Labor Statistics, consumer price index for all urban consumers (CPI-U), New York-Newark-Jersey City, series CUURS12ASA0 | Deflator for constant-dollar figures |
| NYSED, BEDS Day public school enrollment files (all students; students with disabilities), 2012-13 to 2025-26 | Charter vs. district enrollment; students-with-disabilities shares |
| New York City Independent Budget Office (IBO), Education Spending Since 1990, chart book and data file, updated Oct. 6, 2026; news release of the same date | FY2025 total and its components, school-related programs, actual spending by unit of appropriation (U/A), fringe benefits, staffing, funding shares |
| IBO press release, June 17, 2025 (FY2024 edition) | Superseded FY2024 figures, kept for reference |
| IBO, "Barriers to Learning," March 2025 | Average school building age |
| City Council Finance Division, reports on the DOE budget: FY2019 Preliminary (March 2018), FY2027 Preliminary (March 2026), FY2027 Executive (June 2026) | FY2019 comparison and U/A descriptions (FY2019 report); due-process spending (FY2027 reports); hold harmless by year and class size budget changes (FY2027 Executive) |
| NYC DOE, School Based Expenditure Report (SBER), FY2018 System Wide Report | Functional per-pupil breakdown |
| NYC DOE, Demographic Snapshot 2021-22 to 2025-26 | District 75 enrollment |
| NYC DOE, FY2027 school funding presentation; FY2024 Fair Student Funding guide | District 75 funding; Fair Student Funding weights |
| Mayor's Management Report 2026, DOE chapter | Average due-process settlement cost |
| DOE due-process cases report to the City Council, December 2025; City Council education hearing, Jan. 30, 2025 (unofficial transcript) | What DOE does and does not track |
| NYC Public Schools, SY2025-26 Class Size Reduction Plan; Chancellor's announcement, Nov. 27, 2024 | Class size law details; hold harmless total |
| IBO class size cost analysis | Teacher and cost estimates for the class size law |
| NCES, Digest of Education Statistics 2023, Tables 204.70 and 208.40; Common Core of Data via the Urban Institute Education Data Portal | National disability share; pupil/teacher ratios |

### Non-government sources, used only where marked

Sections 4 and 5 carry figures from Chalkbeat New York articles: hold harmless totals and school-level examples, and class-size budget-negotiation figures. They are inside boxed, orange-labeled blocks marked "Reported figures, not primary-verified," are listed separately in the source list, and are never mixed into a chart with government data. Think-tank figures are not used.

## Key figures and how each was derived

### Headline metrics

- **$41.6 billion total DOE spending, FY2025:** IBO data file, full agency cost $41,591,898,540: operations $34,547,849,751; pensions $3,437,647,178; debt service $3,379,761,441; other health care costs $226,640,170. IBO's release rounds to $42 billion.
- **$35,796 per pupil, FY2024:** Census Table 18, New York City row. Census press release: "Among the 100 largest school systems (by enrollment), New York City School District in New York ($35,796) had the highest current expenditures per pupil in FY 2024."
- **Rank:** first in Table 18 in every year FY2016-FY2024 except FY2021, when Boston ($31,397) ranked ahead of New York City ($29,931). Boston has since dropped out of the 100 largest; computed the same way as Table 18 (below), it spent $39,929 per pupil in FY2024.
- **Enrollment -13.9 percent:** Census Table 18 enrollment, 981,667 (FY2016) to 845,509 (FY2024).

### Lead section: what the money pays for

Built by `scripts/build_composition.py` into `data/composition.json`.

- **NYSED 2024-25, $35,058 per pupil:** the "NYC Chancellor's Office" districtwide column of the 2024-25 Financial Transparency Report (identical on every NYC school's report; parsed from the saved P.S. 307 page). Salaries $17,157, employee benefits $10,154, all other $7,747. The state's 12 functions are combined into seven groups: instruction (1 Instruction $18,425 + 3 Support Services, Instructional Staff $520 = $18,944); pupil support (2; $5,116); school administration (5; $2,030); transportation (7; $1,733); building operation and maintenance (6; $2,984); food services (9; $827); central administration and other districtwide costs (4 General Admin $257 + 8 Business/Central/Other $1,796 + 12 Districtwide Current Operations $1,368 = $3,422). Rows 10 and 11 are zero. Chart values are rounded so each group's three parts sum to its rounded total; any $1 remainder goes to salaries.
- **Census FY2024, $35,796 per pupil:** district file, NYC (NCESID 3620580), divided by V33 = 845,509: instruction TCURINST - V91 - V92 = $26,092 (Table 18's instruction column; Table 18 also gives instruction salaries $13,742 and benefits $7,957, leaving $4,394 other); pupil support E17 $75; instructional staff support E07 $362; general administration E08 $584; school administration E09 $1,572; operation and maintenance V40 $3,313; student transportation V45 $2,044; business, central and other support V90 + V85 $1,100; food services E11 (all of TCUROTH) $652. They sum to $35,796, matching Table 18. U.S.: Table 8, instruction $10,346 (salaries $6,293, benefits $2,764, other $1,289), pupil support $1,229, instructional staff support $916, general administration $351, school administration $946; other support services $3,140 is Table 8's support total ($6,582) minus those four; food and other $691 is the total ($17,619) minus instruction and support. Salaries plus benefits: 70.3 percent of the NYC total ($16,218 + $8,943) and 79.0 percent of the U.S. total.
- **Why pupil support differs:** Census Appendix B: "Instructional expenditure for the New York City School District includes expenditure for guidance counselors." The state's report assigns pupil-support costs to function 2.
- **FY2018 SBER:** no longer charted (see the FY2018 entry below); the lead section links to DOE's last edition.

### Lead section, box: three Brooklyn schools

Schools: P.S. 307 Daniel Hale Williams (13K307; NYSED 331300010307), P.S. 321 William Penn (15K321; 331500010321), P.S. K369 Coy L. Cox School (75K369; 307500013369; Galaxy code K369). Chosen at the reader's request; P.S. 369 was picked among Brooklyn District 75 schools because its headquarters (383 State St.) sits between the other two. Its 2024-25 spending ($123,090) is above that of 40 of the 60 District 75 schools in the state file (median $112,990).

- **Actual spending per pupil, 2024-25:** NYSED Financial Transparency Reports, `https://data.nysed.gov/expenditures.php?year=2025&instid=<id>` (800000045541, 800000045158, 800000043560). Each report has a districtwide column (NYC Chancellor's Office) and a school column; rows 1-12 are functions, each split into salaries, employee benefits and all other; row 13 is the total. Totals: P.S. 307 $52,349.02; P.S. 321 $26,129 (rounded from the report); P.S. 369 $123,090; districtwide $35,057.69. Per-pupil amounts divide by the school's BEDS-day P-12 enrollment (278; 1,306; 497). Excluded from the totals: charter school tuition, debt service and other exclusions (BOCES tuition, services to nonpublic and charter schools, pre-K payments to community organizations, community services). Saved copies: `data/three-schools/nysed/`; parsed by `scripts/parse_nysed_transparency.py` into `data/three-schools/nysed_2024_25.json`, which checks that every school's rows sum to its total.
- **Chart grouping (this page's):** instruction = rows 1 and 3; pupil support = row 2; school administration = row 5; transportation = row 7; "building, food, central" = rows 4, 6, 8, 9 and 12. Rows 4, 6, 8 and 9 are identical at all three schools ($260, $3,014, $1,814, $836), which shows they are allocated per pupil rather than measured per building.
- **Ranks:** NYSED report card database SRC2025, table "Expenditures per Pupil," YEAR 2025. District schools = entity codes for schools in the 32 geographic districts (1,811 with spending reported; median $33,032). P.S. 307 is above 97 percent of them, P.S. 321 above 15 percent. District 75 = entity codes beginning 3075 (60 schools; median $112,990); P.S. 369 is above 67 percent.
- **Positions and school budgets, FY2026:** DOE Galaxy Budget Summaries (tables of organization as of June 25, 2026), fetched by form post with `scripts/fetch_galaxy.py`; saved text in `data/three-schools/galaxy/`; parsed by `scripts/galaxy_parse.py`, which reproduces each site total and P.S. 369's all-sites grand total ($27,827,073; 309 positions; 11 sites) exactly. Totals: P.S. 307 $8,970,968 (74 positions); P.S. 321 $17,310,200 (144). Groups: teachers = Classroom Teacher, Elementary Cluster/Quota, Cluster/Quota Teacher, Q Rate and the District 75 homeroom and classroom teacher sections; related services and counseling = Special Needs - Support Services (speech, OT, PT, ESL, adaptive PE), Guidance/Social Workers and SBST; paraprofessionals; leadership and office = Leadership, Coordinator/Supervisor/Dean, Secretary, School Aides and Other Support Staff, Family Workers. Coaches (Professional/Curriculum Development) are counted in the dollar total but not in the position rows. Per-pupil amounts use 2025-26 enrollment from the DOE Demographic Snapshot (277; 1,332; 488). `scripts/build_three_schools.py` produces `data/three-schools/three_schools.json`.
- **What Galaxy dollars are:** DOE's budget summary glossary: "The budget amount is the cost to the school of the item or group of items. It is not necessarily a person's actual salary. Most teacher positions are budgeted at the school's average salary ... mandated related service providers ... are budgeted at a citywide average salary." "Budget amounts for reimbursable funded items include fringe benefits." Annual positions are prorated for assignment dates.
- **Payroll:** NYC Open Data Citywide Payroll Data (k397-673e) has agency, title, work-location borough and pay, but no school field. For fiscal 2025, DOE agency records show "MANHATTAN" for all but 3,195 records (3,194 "OTHER", one blank).
- **Also reviewed, not shown:** the 2022-23 New York State School Funding Transparency Form (Parts B and C), the last year of that form (Education Law §3614 was repealed effective June 30, 2023). It reports planned allocations with benefits at a 50.8 percent district average fringe rate and central costs of $9,618.46 per pupil spread evenly across all 1,610 schools: P.S. 307 $37,656, P.S. 321 $24,638, P.S. 369 $87,376 per pupil. The 2024-25 actuals replace it on the page.

### Section 1: the per-pupil trend (FY2016-FY2024)

Every point is read from Census Table 18, New York City row, in that year's summary-tables workbook (`elsecYY_sumtables`): $24,109; $25,199; $26,588; $28,004; $28,828; $29,931; $35,914; $33,387; $35,796.

**What the Census figure measures.** We reproduced Table 18 exactly from the Census district file:

per pupil = (TCURELSC - V91 - V92) / V33

TCURELSC is current spending for elementary-secondary education, V91 payments to private schools, V92 payments to charter schools and V33 fall enrollment. For FY2024: (34,591,210 - 916,029 - 3,409,570) thousand / 845,509 = $35,795.73. The same formula reproduces Table 18 to the dollar for the District of Columbia, Atlanta, Los Angeles, San Francisco, Chicago and Detroit. Current spending includes salaries and employee benefits (including pension contributions and health insurance). It excludes capital outlay and debt service. Census excludes charter schools whose charters are held by nongovernmental entities; no New York charter school appears in its file. Enrollment is Common Core of Data fall membership for DOE schools (845,509 in fall 2023, including 39,025 pre-K pupils).

**Total district spending.** The total shown is the per-pupil numerator, TCURELSC - V91 - V92, so per pupil times enrollment reproduces it exactly: $23.67B, $24.81B, $25.97B, $26.90B, $27.58B, $27.33B, $30.87B, $28.28B, $30.27B for FY2016-FY2024. Census Table 16's "current spending" column ($26.26B in FY2016 to $34.97B in FY2024) is a broader figure: it equals TCURELSC plus spending on programs outside kindergarten through 12th grade, so it includes payments to charter and private schools ($4.33 billion in FY2024) and adult education and similar programs ($0.38 billion). An earlier version of this page used Table 16 and concluded that Census must use an unpublished pupil base of about 977,000 for FY2024. That conclusion was wrong: the difference is in the numerator, not the denominator.

**Inflation adjustment.** Deflator: CPI-U, New York-Newark-Jersey City, all items, not seasonally adjusted (series CUURS12ASA0), averaged over the twelve months July through June, from the BLS public API. FY2024 is the base. IBO uses the same regional index for its own constant-dollar figures. Earlier versions of this page used the national CPI-U (CUUR0000SA0); its figures are shown for comparison.

| FY | CPI-U NY area | CPI-U U.S. | Enrollment | Per pupil, as spent | Per pupil, FY2024 $ (NY area) | Per pupil, FY2024 $ (U.S. CPI) | Total, as spent ($B) | Total, FY2024 $ (NY area, $B) |
|---|---|---|---|---|---|---|---|---|
| 2016 | 261.619 | 238.273 | 981,667 | 24,109 | 30,196 | 31,323 | 23.67 | 29.64 |
| 2017 | 266.234 | 242.656 | 984,462 | 25,199 | 31,014 | 32,147 | 24.81 | 30.53 |
| 2018 | 270.966 | 248.126 | 976,771 | 26,588 | 32,152 | 33,171 | 25.97 | 31.41 |
| 2019 | 275.769 | 253.268 | 960,484 | 28,004 | 33,275 | 34,229 | 26.90 | 31.96 |
| 2020 | 280.645 | 257.230 | 956,634 | 28,828 | 33,660 | 34,694 | 27.58 | 32.20 |
| 2021 | 286.438 | 263.151 | 912,994 | 29,931 | 34,240 | 35,211 | 27.33 | 31.26 |
| 2022 | 300.896 | 282.025 | 859,514 | 35,914 | 39,111 | 39,422 | 30.87 | 33.62 |
| 2023 | 316.811 | 299.685 | 847,030 | 33,387 | 34,532 | 34,488 | 28.28 | 29.25 |
| 2024 | 327.676 | 309.570 | 845,509 | 35,796 | 35,796 | 35,796 | 30.27 | 30.27 |

**What the adjustment shows.** FY2016 to FY2024: per pupil +48.5 percent as spent, +18.5 percent in New York-area constant dollars (+14.3 percent with the national CPI-U); total district spending +27.9 percent as spent, +2.1 percent constant (-1.6 percent with the national CPI-U). Splitting the log change in per-pupil spending (0.395): inflation 0.225 (57 percent), fewer students 0.149 (38 percent), real spending 0.021 (5 percent).

**FY2022 and FY2023.** Per pupil +20.0 percent in FY2022 (spending +13.0 percent, enrollment -5.9 percent); spending -8.4 percent in FY2023. IBO's data file shows federal aid to DOE of $3.29 billion (FY2021), $6.14 billion (FY2022), $4.44 billion (FY2023), $4.93 billion (FY2024) and $2.80 billion (FY2025), in 2025 dollars. The Census revenue series records federal aid in different years (FY2022 $2.55 billion, FY2023 $4.64 billion), so this page does not attribute the swing to pandemic aid alone.

**Y-axis.** The default view does not start at zero, which amplifies year-to-year movement. A zero-baseline toggle is provided.

### Section 2: spending vs. enrollment

- Enrollment from Census Table 18: 981,667 (FY2016) to 845,509 (FY2024), -13.9 percent (-136,158). The fall 2019 to fall 2021 drop (97,120) is 71 percent of the total.
- Spending is the per-pupil numerator above: $23.67 billion to $30.27 billion as spent (+27.9 percent); $29.64 billion to $30.27 billion in FY2024 dollars (+2.1 percent).
- Decomposition, dollars as spent: FY2024 spending over FY2016 enrollment = $30,831 per pupil, so $4,965 of the $11,687 rise (42.5 percent) reflects fewer students; FY2016 spending over FY2024 enrollment = $27,991, giving $3,882 (33.2 percent). In FY2024 dollars, the same two calculations give 88.7 and 86.8 percent of the $5,600 real rise.
- IBO's broader series (full agency cost, which includes charter payments, pensions and debt service, divided by an enrollment count that includes charter students): in 2025 dollars, full agency cost rose 12.9 percent from FY2016 to FY2024 ($36.55 billion to $41.28 billion) and per-pupil cost rose 19.4 percent ($31,247 to $37,299), while its enrollment fell 5.4 percent (1,169,730 to 1,106,649); fewer students account for roughly 30 percent of its real per-pupil increase. (Earlier versions of this note called the 12.9 percent a per-pupil rise.)
- Both y-axes are zoomed by default; a toggle starts them at zero.

### Section 3: charter enrollment

Computed from NYSED BEDS Day school-level "All Students" files, summing pre-K-12 enrollment ("PK12 TOTAL") for all schools in the five New York City counties and splitting on NYSED's "School Type" field (Public, Charter). Every public row in those counties belongs to a DOE district, including District 75. Charter counts are the number of charter rows (state location codes). An independent re-run reproduced every value.

| School year | Charter | District | Charter school locations | Charter share |
|---|---|---|---|---|
| 2012-13 | 58,493 | 985,388 | 159 | 5.6% |
| 2015-16 | 94,334 | 980,197 | 205 | 8.8% |
| 2019-20 | 128,951 | 934,109 | 260 | 12.1% |
| 2021-22 | 139,315 | 846,833 | 271 | 14.1% |
| 2023-24 | 143,575 | 832,218 | 274 | 14.7% |
| 2025-26 | 148,847 | 809,873 | 285 | 15.5% |

(The chart plots all fourteen years.) The district lost 175,515 students and charters gained 90,354; total public enrollment fell 8.2 percent against 17.8 percent for the district alone. District counts include 22,369 to 37,592 pre-K pupils a year in school buildings; the 2023-24 district uptick is pre-K, and district K-12 fell that year. 2025-26 uses NYSED's final files (data as of Aug. 22, 2026, pulled Oct. 8, 2026); the preliminary files used before Oct. 26, 2026 (data as of March 14, 2026) gave 149,879 charter and 810,653 district students.

**This is not a transfer statistic.** The two series are independent headcounts; charter growth cannot be read as district departures, and no source used here apportions the district decline among births, migration, private schooling and other causes.

**Comparability.** For the same year, the Census district enrollment is higher than NYSED's by 1,470 (2015-16) to 22,525 (2019-20). NYC DOE's demographic snapshot counts slightly more charter students than NYSED (by 437 to 2,422 a year, 2021-22 to 2025-26), mostly because it includes charter pre-K and uses a different count date.

### Section 4: hold harmless

**Mechanism** (DOE Fair Student Funding guides, FY2024 and FY2027): schools get a foundation amount ($225,000 in FY2027) plus per-student funding weighted by grade (K-5 1.00, 6-8 1.08, 9-12 1.03) and needs weights for academic intervention, special education and English language learners, plus weights for students in temporary housing (0.12) and for schools with a concentration of need (both new in FY2024), and portfolio weights for some high schools. Poverty is not a standalone weight; it is used inside the academic intervention weight only where prior test scores are not available. Budgets are set in spring on projected enrollment and adjusted mid-year using the end-of-October register. Two protections, per the comptroller's Aug. 12, 2026 comments: "register relief" replaces Fair Student Funding lost at the mid-year adjustment (FY2021-FY2023 at varying shares, funded largely with federal pandemic aid, and every year since FY2025), and, since FY2024, "hold harmless" "ensured that schools start the year at a funding level no lower than the prior year inclusive of most categories of funding, including FSF." "While register relief is purely a replacement of per-pupil Fair Student Funding, the hold harmless formula compares the entire school funding of the prior year (with a few exceptions, such as for Pre-K and Summer Rising)." Council Table 1 shows no mid-year allocation in FY2024. Earlier versions of the page described hold harmless mainly as switching off the mid-year cut.

**Government figures:**
- NYC Public Schools, SY2025-2026 Class Size Reduction Plan (July 2025), p. 11: "New York City has invested a total of $1.2 billion since FY 2021 in 'hold harmless' funding for schools losing enrollment to ensure they can maintain services."
- City Council Finance Division, FY2027 Executive Plan report on DOE (June 2026), Table 1, from DOE school allocation memos: FY2026 initial $126,817,852 plus mid-year $261,652,063 = $388,469,915; FY2021-FY2026 total $1,637,578,173. (FY2021-FY2025 sums to $1.249 billion, consistent with DOE's $1.2 billion.)
- City Comptroller, Comments on the FY2027 Adopted Budget (Aug. 12, 2026), Table 6: FY2026 $391 million (including $2 million for District 75); FY2027 initial allocation $286 million ($271 million general education plus $15 million District 75); FY2021-FY2027 total $1,932 million. "FY 2027 initial hold harmless allocations were released on June 15, 2026, with general education schools receiving $271 million in total City funding." The note says these exclude centrally budgeted fringe costs.
- DOE announcement, Nov. 27, 2024: "approximately 50% of schools would have been subject to a mid-year adjustment totaling $157 million dollars. These schools will now see no change in funding."

**Chalkbeat figures (boxed on the page).** Chalkbeat, June 22, 2026, "NYC's $1.9 billion dilemma: How long can schools be 'held harmless' for enrollment losses?" (the URL slug reads "hold-harmless-costs-grow-enrollment-losses-continue"). All figures are for 2026-27: "New York City is spending nearly $290 million next year"; "It's more than double what the city spent prior to the beginning of the 2025-26 school year"; "723 schools got some amount of hold harmless money. Fifty-five of those schools got over $1 million"; "nearly $1.9 billion" since 2020; I.S. 339 "shrunk from 315 students in 2020 to 150 this year, is slated to get nearly $2.5 million," "roughly a third of the school's overall budget of $7.8 million"; the Urban Assembly school "slated to receive about $374,000 ... The school's enrollment has shrunk to 350 this year from nearly 500 in 2020."

**What changed.** Earlier versions said the $290 million was for 2025-26 and called the official and reported totals irreconcilable, citing a Citizens Budget Commission figure of about $400 million for 2025-26. With years matched, the figures agree: about $388 million to $391 million in 2025-26 (Council, comptroller), about $286 million to $290 million initially for 2026-27 (comptroller, Chalkbeat), and about $1.9 billion cumulatively. The think-tank figure is no longer needed and was removed, consistent with this page's sourcing rule.

### Section 5: class size mandate

- Chapter 556 of the Laws of 2022 (A10498/S9460), signed Sept. 8, 2022 (Assembly bill record: "09/08/2022 SIGNED CHAP.556").
- Caps table: FY2026 Class Size Reduction Plan, Figure 1, which lists both the UFT contract caps and the Chapter 556 caps. Footnote: the contract cap of 50 "reflects PE and required music classes in grades 6-12."
- Phase-in before 2026: an additional 20 percent of classes each year, full compliance by September 2028. Chapter 556 as signed (A10498) said compliance was "to be achieved by September two thousand twenty-seven"; the 2023-24 start and September 2028 end come from Chapter 86 of the Laws of 2023, which the Chapter 155 text cites. Earlier versions called the 2023-2028 schedule the original law.
- Chapter 155 of the Laws of 2026 (A11539/S10615): passed both houses June 4, 2026; "06/26/2026 signed chap.155." Text: "For each of the first three years of the plan, an additional twenty percent ... and for each of the following four years, an additional ten percent," with full compliance by September 2030. The City Council: "The changes to the Class Size Law were not decided as part of the State budget, but rather as legislation in the current State legislative session."
- Exemptions: limited to statutory categories and approved by the chancellor and the presidents of the UFT and CSA (FY2026 plan).
- Compliance: FY2026 plan, "46% of classes at or below the class size caps" for 2024-25; DOE annual report, Nov. 15, 2025: "data as of October 31, 2025 shows that 64% of classes ... are at or below the class size caps," and "These counts reflect the number of non-exempted classes." Council: 10,535 exempt classes in 2025-26.
- 2025-26 funding: FY2026 plan: "notification to schools of funding for 3,700 teachers and over 100 Assistant Principals in April"; "expects to spend over $400 million at roughly 750 schools."
- Costs: IBO, July 2023: 17,700 teachers, "between $1.6 to $1.9 billion annually." IBO, December 2025: "16,300 additional teachers ... range from $1.5 billion to $1.7 billion." DOE Financial Impact Statement, Nov. 15, 2025: "between $949.2 million and $1.7 billion in additional costs in teacher salary alone," and the School Construction Authority "is projecting costs of approximately $18 billion." Comptroller certification letter, June 20, 2024: the authority's estimate "could total between $22.3 billion and $26.8 billion."
- FY2027 budget: Council FY2027 Executive report: "Cost Containment Class Size ... savings of $508 million in Fiscal 2027"; a "year-over-year increase of $122 million in funding for class size in Fiscal 2027 ... will allow for the hiring of 1,000 additional teachers." Comptroller, adopted budget: "OMB also added $122 million in State education funding beginning in FY 2027 ... This brings the total funding added during the Mamdani administration to implement the mandate to $914 million in FY 2030."
- Chalkbeat, April 2, 2026, "Mamdani campaigned on fulfilling NYC's class size mandate. So why is he pushing for a delay?" (boxed): "$543 million in additional city funding to reduce class sizes next fiscal year and $943 million in each of the three fiscal years after that"; Liu: "Adjustments in the timeline are not meant to provide fiscal relief."
- Removed: "The largest identified future driver of NYC school spending." No official source ranks the class size law that way.

### Section 6: the whole department, IBO's FY2025 total

All from IBO's Oct. 6, 2026, data file (amounts in 2025 dollars, which equal dollars as spent for FY2025).

- School-related programs, $19.50 billion: IBO's grouping of U/A 401/402 general education district schools ($8.97B), 406 charter schools ($3.36B), 403/404 special education district schools ($2.57B), 481/482 categorical programs ($2.13B), 407/408 pre-K ($1.94B) and 409/410 early childhood ($0.54B). IBO's release rounds the total to $20 billion.
- Fringe benefits, U/A 461: $4.23 billion. IBO's object-code table puts all fringe benefits in DOE operations at $4.88 billion, so about $0.65 billion sits in other U/As. (IBO's June 2025 "$4.5 billion" for FY2024 was the object-code total, not U/A 461.)
- All other operating: operations ($34.55 billion) minus the two items above = $10.82 billion, net of $0.12 billion in intracity sales.
- Pensions, debt service and other health care costs: IBO's full-agency-cost items managed by other city agencies.

The superseded June 2025 release reported FY2024 as $40 billion total, $33 billion operating, $19 billion in school-related programs and $4.5 billion in fringe benefits. Its five bullets summed to $18.42 billion; the missing piece was early childhood (U/A 409/410, $0.49 billion). Earlier versions of this page split that $40 billion into a "central services" residual of $33B - $19B - $4.5B = $9.5B, which double-counted about $0.5 billion of fringe benefits that sit inside school-program lines.

No general education per-pupil figure is published: IBO cautions that "not all categories of spending apply to all students reported in that total enrollment."

### Section 6 (continued): operating spending by U/A, FY2025

From IBO's sheet E (actual spending by U/A). Total of all U/As: $34.67 billion.

| Bucket | U/As | $B | Share |
|---|---|---|---|
| School-related programs | 401-410, 481/482 | 19.50 | 56.3% |
| Central special education and private placements | 421-424, 470, 472, 474 | 5.08 | 14.7% |
| Operations | 435-444 | 5.02 | 14.5% |
| Fringe benefits | 461 | 4.23 | 12.2% |
| Central administration | 453/454 | 0.45 | 1.29% |
| School support organizations | 415/416 | 0.39 | 1.12% |

Central administration's share of actual spending ranged from 1.24 percent to 1.77 percent over FY2011-FY2025 (FY2019: 1.41 percent). The Council's FY2019 preliminary budget, used in earlier versions, had $345.0 million of $25.6 billion (1.35 percent), 2,055 positions; re-adding every U/A in that report reproduced the earlier FY2019 buckets exactly. The earlier claim that no U/A-level breakdown had been published since FY2019 was wrong: the Council publishes one each year and IBO publishes actuals by U/A. Starting with the FY2026 budget, new U/As 433/434 (Division of Technology) appear ($131.3 million adopted) and U/A 453/454 falls ($448.0 million FY2025 actual to $176.0 million FY2026 adopted), so FY2026 and later budgets are not comparable with these figures. Council descriptions used for labels, all from the FY2019 Preliminary report (March 2018): U/A 403/404 "provides for the direct special education instruction, school supervision and support services ... in a resource room, self-contained and collaborative team classroom setting"; U/A 421/422 includes "funding for District 75 schools"; U/A 423/424 "contains funds for centrally-managed special education related services"; U/A 472 funds "Contract Schools, Carter Cases, Foster Care and Blind and Deaf schools"; U/A 461 covers "social security, health insurance, payments to welfare funds, annuity contributions, workers compensation and unemployment benefits."

### FY2018 School Based Expenditure Report (no longer charted)

From the FY2018 System Wide Report #1 (run Aug. 6, 2019), enrollment 1,021,229 (879,907 general education; 141,322 full-time special education). Per student: classroom instruction $12,276; instructional support $4,183; leadership, supervision and support $2,087; ancillary support $1,970; building services $1,650; other $3; direct services subtotal $22,170; field support $506; system-wide costs $738; system-wide obligations $2,853 (debt service $2,132, retiree health and welfare $713, Special Commissioner for Investigation $8); public schools total $26,266. Pass-throughs, not per student: $4.75 billion (charter $2.39 billion; non-public schools $2.29 billion, of which special education $2.04 billion; Fashion Institute of Technology $0.06 billion). Grand total $31.57 billion. InfoHub: "The final School Based Expenditure Report (SBER) for 2018 is available." Earlier versions described system-wide obligations as "primarily pension contributions"; they are mostly debt service and retiree health.

### Section 7: special education

- U/A amounts: IBO sheet E, FY2025.
- $1.14 billion due process ($1,138.7 million): City Council Finance Division, June 2026 report on DOE, Chart 2; the Council's FY2027 Preliminary Plan report rounds the same figure down: "This change explains why Fiscal 2025 actual spending, at $1.13 billion, appears to decrease from prior years." DOE now charges costs to the fiscal year of the decision or settlement rather than charging them back. The budget code covers tuition for Carter and Connors cases, direct services, legal fees and transportation. Due-process cases became their own U/A (476) in the FY2027 budget.
- $109,859: Mayor's Management Report 2026, DOE chapter: "Average settlement cost for both filing types increased eight percent from $101,424 to $109,859" (FY2025 to FY2026). It is an average per settlement, not per student.
- District 75: DOE demographic snapshot, 25,937 (2021-22) to 30,694 (2025-26). DOE's FY2027 funding presentation: "D75/Citywide Special Education programs are also funded separately. Funding is provided based on a class model."
- Carter and Connors: DOE general counsel at the Jan. 30, 2025, Council hearing: "We don't track the distinction between Carters and Connors" (citymeetings.nyc unofficial transcript). Connors cases are direct payments to the school for families who cannot pay tuition up front.
- Payees: the December 2025 DOE case-level file reports payments and student ZIP codes, not schools. Checkbook NYC payee records were not searched.

### Section 8: why New York City is higher

- Gap: $35,796 - $17,619 = $18,177 (Census FY2024; national figure from Table 8).
- By object (Table 18 and Table 8): salaries $16,218 vs. $9,685; benefits $8,943 vs. $4,243; other $10,635 vs. $3,691. By function: instruction $26,092 vs. $10,346.
- Students with disabilities, NYSED 2024-25 (students-with-disabilities table divided by pre-K-12 total): New York City district 202,442 / 829,880 = 24.4 percent; New York City charter 30,528 / 147,009 = 20.8 percent; New York State all public schools including charters 491,776 / 2,484,250 = 19.8 percent (19.9 percent excluding charters). Final 2025-26: district 206,675 / 809,873 = 25.5 percent; charter 30,967 / 148,847 = 20.8 percent (earlier versions cited preliminary figures of 24.6 and 19.9 percent that could not be re-checked against any file NYSED still posts). NYSED blanks out small school-level counts; the 2024-25 numerators fill those cells as All Students minus General Education, which is why a plain sum of the printed rows gives slightly smaller counts (202,425; 30,525; 491,677) and identical percentages. Counting kindergarten through 12th grade only, the 2024-25 district share is about 24.8 percent. National reference: NCES Digest Table 204.70, 15.2 percent of public school enrollment served under IDEA, ages 3-21, 2022-23.
- Students per teacher, fall 2022: New York City DOE schools 847,030 / 68,905 full-time-equivalent teachers = 12.3 (sum of the 33 DOE local education agencies in the Common Core of Data); New York State 11.7 and the U.S. 15.4 (NCES Digest Table 208.40).
- IBO ratio: 12.07 (FY1990) to 8.88 (FY2025), total IBO enrollment divided by DOE full-time pedagogical positions; the student count includes charter students. IBO calls the staff count "pedagogic staff"; the City Council's FY2027 Preliminary report lists the same counts as "Full-Time Positions - Pedagogical" and describes added District 75 personnel as "primarily pedagogical, including paraprofessionals," so the category includes paraprofessionals.
- Building age: IBO, March 2025: "The Average NYC School Building is 75 Years Old."
- Funding shares (IBO full agency cost): FY2025 city 57.2 percent, state 35.7 percent, federal 6.7 percent; FY2024 52 / 35 / 12 percent.
- No dollar decomposition of the gap is published, because none exists in a government source.

### Section 9: cross-district comparison

Census Table 18, FY2024: New York City $35,796; District of Columbia $31,529; Atlanta $26,117; Los Angeles Unified $25,631; San Francisco Unified $25,173; Chicago $24,330; Detroit $21,406; Philadelphia $19,525; Clark County $14,774; Houston $13,950; Miami-Dade $13,931; Broward $13,412. U.S. average (Table 8) $17,619. Boston $39,929, computed from the district file with the Table 18 formula; not in Table 18.

## Assumptions and limitations

1. **Census and IBO measure different things.** Neither is "the" per-pupil number.
2. **Deflator choice.** New York-area CPI-U. School costs are mostly wages, so a wage-based index could show a different real trend.
3. **Enrollment denominators are not interchangeable.** Census (Common Core of Data fall membership), NYSED BEDS Day and IBO's total enrollment (which includes charter, contract and community-based pre-K students) all differ. Figures are never divided across sources.
4. **SBER stopped at FY2018.** No current official functional breakdown exists.
5. **The U/A bucketing is this page's.** The caption lists every line.
6. **Special education costs are spread across many lines.** No public total exists.
7. **No outcomes data.** The page reports spending only.

## Reproducibility

Census: `https://www2.census.gov/programs-surveys/school-finances/tables/<YEAR>/secondary-education-finance/elsec<YY>_sumtables.xlsx` (older years `.xls`) and `elsec<YY>.xlsx` (district file; New York City is NCESID 3620580). NYSED: `https://www.p12.nysed.gov/irs/statistics/enroll-n-staff/home.html` (current) and `ArchiveEnrollmentData.html` (files `PublicSchool<YYYY>AllStudents.xlsx`, where the year is the spring of the school year; 2015-16 is `PublicSchool2016AllStudents_000.xlsx`). IBO: `https://www.ibo.nyc.gov/assets/ibo/downloads/pdf/fiscal-history/data-fiscal-history/education-spending.xlsx`. BLS: series CUURS12ASA0. To update: Census each spring, IBO each year (most recently Oct. 6, 2026), NYSED each fall.

## Corrections log

**Oct. 27, 2026: page restructured**

| Item | Was | Now | Why |
|---|---|---|---|
| Section order | Lead breakdown; 1-5; 6 IBO $41.6 billion; 7 schools vs. central administration; 8 FY2018 School Based Expenditure Report plus the three-school box; 9 special education; 10 the gap; 11 peer districts | Lead breakdown with the three-school box; 1-5 unchanged; 6 the whole department ($41.6 billion and the six-bucket U/A chart); 7 special education; 8 the gap; 9 peer districts | Old 6 and 7 used the same IBO FY2025 data twice; old 8's FY2018 chart was superseded by the 2024-25 and FY2024 breakdowns in the lead section |
| IBO donut and school-related programs charts | Two charts in old Section 6 | Removed; their figures (pensions, debt service, other health care; the six school-related program lines) are now in Section 6's text and chart caption | Same data as the U/A bucket chart |
| FY2018 SBER chart | Old Section 8 | Removed from the page; derivation kept below; the source stays in the source list and is linked from the lead section | Eight years old, categories match neither current source |

Earlier log entries refer to the old section numbers.

**Oct. 26, 2026**

| Item | Was | Now | Source |
|---|---|---|---|
| Section 3, 2025-26 enrollment | Preliminary: charter 149,879, district 810,653; +156%, -17.7%, lost 174,735, gained 91,386, total -8.0% | Final: 148,847 and 809,873; +154%, -17.8%, lost 175,515, gained 90,354, total -8.2% | NYSED 2025-26 final files |
| Section 10, 2025-26 disability shares | Preliminary 24.6% district, 19.9% charter | Final 25.5% and 20.8%; K-12-only 2024-25 district share (24.8%) added | NYSED |
| Section 4, how hold harmless works | Mainly a switched-off mid-year cut, with spring protection as an add-on | Spring "hold harmless" since FY2024 (no school starts below its prior-year budget) and mid-year "register relief," described separately | Comptroller, Aug. 12, 2026; Council Table 1 |
| Section 4, Urban Assembly example | "a much smaller cushion because it lost a much smaller share of its students" | Inference removed; Chalkbeat's note that it used older roster figures added | Chalkbeat |
| Section 4, Chalkbeat total | "consistent with" the comptroller's $1.93 billion | "close to" | Chalkbeat says "nearly $1.9 billion" |
| Section 5, phase-in | "The original law" set 20% in 2023-24 to 100% in 2027-28 | Law as signed: compliance by September 2027; the 2023-2028 schedule came from Chapter 86 of 2023 | A10498; A11539 text |
| Section 5, FY2027 budget | Executive Plan "replaced most" of the new money, "leaving" a $122 million increase that the Council "estimated" pays for 1,000 teachers | All $542.9 million removed ($508 million as savings, the rest swapped to state funds); the $122 million rise is $92 million state plus $30 million city; the adopted budget's separate $122 million noted | Council FY2027 Executive report; comptroller |
| Section 5, DOE cost estimate | "added teacher salaries" | "added teacher costs"; DOE's tables include fringe | DOE financial impact statement |
| Section 5, Liu | "about 70 percent" | 70 percent, contingent on more detailed city plans | Chalkbeat |
| Section 5 sources | Chapter 556 bill record, Nov. 2025 annual report and comptroller's June 2024 letter cited but not linked | Linked | Assembly; DOE; comptroller |
| Section 7, U/A 433/434 | U/A 453/454 "shrank by a similar amount" | "shrank" ($272 million, about twice the new line's $131 million adopted) | IBO; budget |
| Section 7 labels | Credited to the FY2027 Preliminary report | FY2019 Preliminary report, where the quoted U/A descriptions appear | Council |
| Section 8 caption | "the first five functional bars" | Named categories (the fifth bar is system-wide obligations, not building services) | SBER FY2018 |
| Section 8 note | State reports list school-level spending "by funding source" and do not use functional categories | NYSED's school reports split spending by function and by salaries, benefits and other | NYSED |
| Section 10, IBO ratio | "counts charter students and paraprofessionals" | Kept, with the source: the City Council's FY2027 Preliminary report shows DOE's pedagogical positions include paraprofessionals (briefly removed earlier on Oct. 26) | Council |
| Methodology, IBO broader series | "rose 12.9 percent" described as per pupil | Total rose 12.9%; per pupil rose 19.4% | IBO sheet C |
| Headline | "Per-pupil K-12 spending" | "Per-pupil spending in New York City public schools" (the Census enrollment includes about 39,000 pre-K pupils) | Census; CCD |
| New lead section | Only per-pupil breakdown was FY2018 (SBER), in Section 8 | Page now opens with NYSED 2024-25 districtwide composition by function and by salaries, benefits and other, and a Census FY2024 function table for NYC and the U.S.; Section 8 keeps the FY2018 SBER and the three-school box, which uses the same seven groups | NYSED; Census |
| New | | Box comparing P.S. 307, P.S. 321 and P.S. 369: 2024-25 actual spending by function, FY2026 staffing and what public data say about building-level personnel costs | NYSED; DOE Galaxy; DOE snapshot; NYC payroll |

Checked and unchanged: every Census Table 18 value FY2016-FY2024, the rank in every year (Boston first in FY2021), Boston's $39,929 and 45,742 students, the per-pupil numerator, Table 8 national figures, all 13 peer-district bars, the CPI deflators and every real-dollar value, the log decomposition, the CCD student-teacher ratio (847,030 / 68,905 = 12.29), and all IBO, SBER, Mayor's Management Report and Council special education figures. All 35 external links returned HTTP 200 on Oct. 26, 2026. One Census note: the FY2024 Table 18 footnote says enrollment is fall 2022 membership, but the 845,509 figure equals the CCD fall 2023 count for DOE's 32 geographic districts (fall 2022 is 847,030, the FY2023 figure), so the footnote appears to be carried over from the prior year.

**Oct. 7, 2026**

| Item | Was | Now | Source |
|---|---|---|---|
| Headline subtitle | "The nation's largest school district is also the highest-spending" | Highest per pupil among the 100 largest | Census Table 18; Boston (not in the 100 largest) spent $39,929 in FY2024 |
| Rank | First "in every year from FY2016 through FY2024" (metric, Section 10 table, Section 11, methodology) | First every year except FY2021, when Boston ranked first ($31,397 vs. $29,931) | Census FY2021 Table 18 |
| Total district spending series | Census Table 16 "current spending," $26.26B to $34.97B | Census per-pupil numerator, $23.67B to $30.27B | Table 16 includes payments to charter and private schools and non-K-12 programs; per pupil times enrollment reproduces the numerator exactly |
| "Census computes per-pupil amounts on a different pupil base" (about 977,000 in FY2024) | Stated as fact in Sections 1 and 2 and the methodology | Removed; explained | Same as above |
| Deflator | National CPI-U | New York-area CPI-U (IBO's index); national results kept here for comparison | BLS CUURS12ASA0 |
| Inflation-adjusted results | Per pupil +14.3%; total +2.5%; $34.12B to $34.97B; FY2022 peak $38.15B; real per-pupil peak $39,422 | Per pupil +18.5%; total +2.1%; $29.64B to $30.27B; peak $33.62B; real per-pupil peak $39,111 | Recomputed |
| "Almost all of the apparent growth in the nominal chart is price change" | As stated | Per pupil: about 57% inflation, 38% fewer students, 5% real money | Log decomposition |
| ESSER causal claims for FY2022 and FY2023 | Stated as cause | Described without a single cause; IBO federal aid series cited | Census and IBO time federal money differently |
| Section 2 chart | Both y-axes zoomed, no toggle; right axis "K-12 students" | Zero toggle added; "students enrolled (fall count)," which includes pre-K | Site rule; Census footnote |
| Section 3 caveat | Census and NYSED district totals differ by "roughly 10,000-30,000" | 1,470 to 22,525 | Computed |
| Section 3 school counts | "schools" | Charter school locations; 2025-26 preliminary; 2023-24 district uptick is pre-K | NYSED files |
| Hold harmless: $290 million | "in the 2025-26 school year" | 2026-27; 2025-26 was about $388 million | Chalkbeat text; Council; comptroller |
| Hold harmless: totals "do not agree"; CBC $400 million | As stated | Official totals added (Council $1.64B FY2021-FY2026; comptroller $1.93B FY2021-FY2027); they agree once years match; CBC removed | Council, comptroller |
| Fair Student Funding weights | "grade level, poverty, English language learners, and students with disabilities" | Foundation, grade, academic intervention, special education, English language learners, temporary housing, concentration of need, portfolio | DOE FSF guides |
| Chalkbeat headlines | URL slugs given as titles | Actual headlines | Chalkbeat pages |
| Liu quote | "not intended to provide fiscal relief" | "Adjustments in the timeline are not meant to provide fiscal relief" | Chalkbeat |
| Class size timeline | 80% in 2026-27, 100% in 2027-28; "enacted outcome not reflected" | Chapter 155 of 2026: 70%, 80%, 90%, 100% by 2029-30; FY2027 budget changes added | Assembly bill record; Council; comptroller |
| Class size compliance | 46% (2024-25) | Also 64% (2025-26) | DOE, Nov. 2025 |
| Class size costs | IBO 17,700 teachers, $1.6B-$1.9B; capital "high teens of billions into the tens of billions" | Adds IBO December 2025 (16,300, $1.5B-$1.7B), DOE's $949M-$1.7B and $18B; capital $18B-$26.8B with sources | IBO; DOE; comptroller |
| "Largest identified future driver" of spending | Section 5 deck | Removed | No source |
| $40 billion breakdown (FY2024) | IBO June 2025 | IBO FY2025, $41.6 billion, six slices | IBO, Oct. 6, 2026 |
| "Central services & overhead" $9.5B | Residual | Replaced; it double-counted about $0.5B in fringe | IBO object codes |
| "$2.4B special education ... excludes ... most classroom-level special ed spending embedded in general ed schools" | As stated | That line (U/A 403/404) is special education instruction in district schools | Council; IBO labels |
| Section 7 | Council FY2019 budget; "no comparable U/A-level aggregation has been published ... since" | IBO FY2025 actuals by U/A (central administration 1.29%); FY2019 kept as comparison | IBO sheet E |
| "Staff health & welfare" and "mostly school staff" | As stated | U/A 461 includes Social Security; school-staff share not published | Council |
| SBER "system-wide obligations (pensions etc.)" | Pensions | Debt service and retiree health | SBER FY2018 |
| Special education table | $1.3B FY2025 "NYC Comptroller"; $101,757 "per student, FY2024, NYC Comptroller"; $47M FY2005 "NYC Comptroller" | $1.14B FY2025 actual ($1,138.7 million; Council, from DOE); $109,859 average per settlement FY2026, $101,424 FY2025 (Mayor's Management Report); $47M and 28x removed | No Comptroller source for any of the three |
| District 75 | ~24,000 | 30,694 (2025-26) | DOE snapshot |
| Connors cases | "nonpublic related services" | Direct payment of tuition for families who cannot pay up front | Council, Chalkbeat |
| "Special education is the single largest driver of NYC DOE cost growth" | As stated | Removed | No source; Council cites labor contracts, charters and Carter cases |
| Students-with-disabilities chart | U.S. 15.0%; state bar "all public" | U.S. 15.2% (Digest 204.70); state bar labeled as including charters | NCES; NYSED |
| Pupil-teacher ratio | "9.4 in 2024" as a pupil-to-teacher ratio | IBO's measure labeled (8.9 in FY2025; counts charter students and paraprofessionals); added 12.3 students per teacher in DOE schools vs. 15.4 nationally, fall 2022 | IBO; CCD; NCES |
| Funding shares | 52/35/12 (2024) | Adds 57/36/7 (FY2025) | IBO |
| Links | Three dead ibo.nyc.ny.us links; a BLS bulk-download link that blocks scripts; Course Correction cited with wrong years (FY2012-FY2022, not FY2023) and no longer used | Removed or replaced | Checked Oct. 7, 2026 |

**July 27, 2026 fact check** (summary). Per-pupil values for FY2016-FY2020 had each been shifted a year and were corrected; unsourced enrollment guesses were replaced with Census Table 18; peer-city IEP bars and the dollar decomposition of the gap with the national average were removed; the cross-district chart was moved to a single year; a general-education per-pupil figure built on an invented denominator was removed; and non-government figures were removed or boxed and labeled. Sections on charter enrollment, hold harmless, the class size mandate and an inflation toggle were added July 28, 2026.

## Contact

Corrections welcome. Report issues at https://github.com/joshgreenman1973/experiments/issues.
