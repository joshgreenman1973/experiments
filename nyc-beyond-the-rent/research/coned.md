# Con Edison rates and utility taxes: research notes

Compiled 2026-10-30 for the utility-prices section. The data is in `coned.json` in this folder. Every figure in that file has the URL it was read on and a short quote. These notes cover the caveats.

Sources: Con Edison, Inc. 10-Ks (combined filings that include CECONY) on sec.gov, NY Department of Public Service (DPS) and Public Service Commission (PSC) press releases and rate-case summaries, NYC Department of Finance (DOF) Annual Report on the Property Tax for FY2026, NYC OMB Tax Revenue Forecasting Documentation (June 2025 Plan), and the Governor's and NYC Law Department press releases.

## What the official numbers show

**CECONY property taxes, all jurisdictions (10-K):** $1,271M in 2010, $1,463M in 2015, $2,738M in 2024 and $3,004M in 2025. Over the same years, total "taxes other than income taxes" grew from $1,656M to $3,655M. Including sales tax on customer bills, the 2025 total was $4,488M. State and local taxes tied to revenue receipts (mostly gross receipts taxes) were $315M in 2010 and $445M in 2025.

**NYC Class 3 levy (DOF Table 19):** Class 3 is utility real property of regulated utilities, excluding land and buildings. The levy was $1,331.7M in FY2010, $1,374.5M in FY2015, $2,952.0M in FY2025 and $3,145.0M in FY2026. Class 3's share of the total levy fell to about 6.0% in FY2015–2017 and then rose to 8.28% in FY2026.

**NYC utility tax (OMB history table):** The tax is 2.35% of utilities' gross income and has stayed roughly flat: $375M in FY2010, $384M in FY2015 and $409M in FY2024. OMB's FY2025 figure of $464M is a forecast, not an actual.

**What the PSC says about property taxes in rate cases:**
- 2020–2022 plan: property taxes were "more than 40 percent" of the increased cost.
- 2023–2025 plan: "more than 30 percent."
- 2026–2028 plan: about 26% of the electric increase ($305.6M of $1.024B over three years, read from the DPS chart) and about 22% of the gas increase.
- Starting in 2026, the new plan reconciles property taxes in full. If actual property taxes differ from the amount built into rates, the whole difference is surcharged to or credited back to customers. The old plan limited this to 90%.

**Latest CECONY rate order (Cases 25-E-0072 / 25-G-0073):** The PSC adopted it on 2026-01-22.
- Electric revenue requirement: +$234M (2026), +$409.7M (2027), +$421.1M (2028). That is 2.8% of total revenue a year.
- Gas: +$27.5M, +$68.8M, +$70.3M. That is 2.0% of total revenue a year.
- A 280 kWh NYC residential customer pays about $4.00, $3.55 and $3.58 more a month in each year.

## Caveats for the page

1. **Neither series is "NYC taxes on Con Ed."**
   - CECONY's 10-K property tax total includes Westchester and other jurisdictions.
   - DOF's Class 3 covers every regulated utility (Con Ed, National Grid, Verizon and others) and excludes utility land and buildings, which are in Class 4.
   - No official source found gives Con Ed's NYC-only property tax bill. Con Ed's own economic-impact reports give NYC figures, but they are company-sourced and were not used.
2. **The post's "$1B in 2015 to over $2B last year" did not match any official series.**
   - DOF Class 3 went from $1.37B (FY2015) to $2.95B (FY2025).
   - CECONY property taxes went from $1.46B (2015) to $3.0B (2025).
   - Present both with their scope labels. Don't call either one "what NYC gets from Con Ed."
3. **The 10-K's "taxes other than income taxes" includes items that aren't NYC's.** It includes payroll taxes, and its "Other taxes" line includes deferrals of under-collected property taxes (as much as +$88M) and can be negative. Use the property-tax row for property taxes.
4. **2011 was restated.** The FY2011 10-K reported 2011 property taxes of $1,372M. The FY2012 10-K's comparative column shows $1,320M. `coned.json` uses each year's own 10-K, the first time that year was reported.
5. **Rate-case dollar figures aren't comparable across sources.**
   - PSC press releases report "revenue requirement" or "levelized" increases.
   - The 10-K reports "base rate changes" plus how they were implemented. For 2023–2025, for example, the 10-K shows $442M/$518M/$382M, implemented as $457M a year, and the PSC says $457.5M levelized.
   - `coned.json` keeps the PSC figure as the main number for 2020 and later, the 10-K figure for 2010–2019, and the other source's figure in `alt_quote`.
6. **Rate years differ.** Before 2014, CECONY electric ran April to March and gas ran October to September. From 2014 on, both use calendar years. National Grid's KEDNY and KEDLI use April to March, except that the 2024 plan started on September 1, 2024.
7. **National Grid (KEDNY/KEDLI) numbers are on a different basis.** The 2024 PSC release states each year as a levelized revenue increase and gives bill impacts for an 83-therm heating customer. Don't add them to Con Ed's.
8. **Supply vs. delivery split.** No PSC or DPS document found splits a typical Con Ed bill. DPS says statewide that supply is "about 35-45%" of a bill. The 10-K's CECONY residential average revenue per kWh is an all-in price for full-service customers: 26.3¢ in 2015, 30.1¢ in 2023, 35.7¢ in 2024 and 36.7¢ in 2025. It is not a delivery-only figure.
9. **How quotes were taken.** Quotes for table cells (DOF Class 3, OMB utility tax, some 10-K rows) are reconstructions of the cell, marked with "..." or brackets, because tables have no sentences. The $305.6M (electric) and $35.1M (gas) property-tax driver values were read from chart images in the DPS visual supplement. A script checked every 10-K quote in the JSON against the downloaded filing text, and all matched.

## Gaps (also listed in the `gaps` array of `coned.json`)

- Con Ed's NYC-only property tax payments.
- The FY2025 actual for the NYC utility tax.
- Official case numbers and exact order dates for the 2010, 2014 and 2017 CECONY orders. Only the month is known, from the 10-K.
- Typical bill impacts for rate years before 2020.
- The Con Ed tariff leaf on gross receipts tax.
- A Con Ed-specific split of supply and delivery.
- Any official statement on a 2026 supply-price spike.
- A DEC source for the Peaker Rule. It is currently dated from Con Ed's 10-K.
- The exact day Indian Point Unit 2 shut down (April 2020).
- Which of 23-G-0225 and 23-G-0226 is KEDNY and which is KEDLI.
- EIA, NYISO, NYSERDA and DTF series were not pulled in this pass.

Working files (10-K text, PDFs) are in `/private/tmp/claude-501/-Users-joshgreenman-Experiments/cdd2bde1-4891-488a-b27c-cd66bb82cc9e/scratchpad/coned/`.
