# NYC water and sewer rates: research notes

Data file: `water.json` (same folder). Every number there carries the nyc.gov URL it came from and a short verbatim quote. A script checked each quote against the extracted PDF text before the file was written. The exceptions are FY1988 to FY1996, where the percentages are bar labels on a chart.

## What's covered

- **Metered water rate, $ per 100 cubic feet (HCF):** FY1997 through FY2027. That's 31 straight years.
- **Annual rate increase:** FY1988 through FY2027. That's 40 years.
- **Typical annual bills:** FY2009 through FY2027, with FY2017 missing.
- **Rental payment to the City:** FY2006 through FY2027. FY2027 is a budget figure.
- **Recent increases:** the stated reasons for FY2015 through FY2027.
- **Assistance programs:** HWAP, MWAP, leak forgiveness and the minimum-charge freeze.

## Claims checked

- **FY2027:** a 6.0% increase, adopted June 10, 2026. Confirmed by the Water Board adoption notice. DEP had first forecast 7.0%. The metered water rate went from $5.05 to $5.35.
- **FY2026:** a 3.7% increase, adopted June 6, 2025. Confirmed. The rate went from $4.87 to $5.05.
- **Sewer charge:** 159% of the water charge. The rate schedules confirm this for every year from FY2008 to FY2027. The CAFR tables show the same 159% back to FY1997.

## Caveats

1. **Fiscal year.** The city's fiscal year runs from July 1 to June 30 and is named for the year it ends. New rates usually take effect July 1. Two mid-year schedules exist: January 26, 2018, which repealed the FY2017 increase, and May 11, 2026, a revised FY2026 schedule that kept the metered rate at $5.05.
2. **Sewer and combined rates are calculated, not copied.** Sewer = water × 1.59, rounded to the cent. This matches every wastewater rate the Board has printed (FY2009 to FY2020 reports). Don't trust DEP's "How We Bill You" page. It gives FY2027 combined as $13.50/HCF, but $5.35 × 2.59 = $13.86. Rounding at the sub-cent level could move a combined figure by one cent.
3. **Minimum charges.** Metered accounts pay at least $0.49 a day for water, plus 159% for sewer, about $463 a year combined. That amount has been frozen since FY2014. Low-use customers didn't see the percentage increases.
4. **Flat-rate vs. metered.** About 3% of accounts are billed at flat, non-metered rates (FY2024 to FY2027 reports). Most multifamily flat billing is the Multi-family Conservation Program (MCP), a fixed charge per apartment: $1,413 per unit in FY2027 (proposed column). Unmetered frontage billing also still exists. The $/HCF series applies only to metered accounts.
5. **FY2017 is complicated.** The Board adopted a 2.1% increase on May 20, 2016, together with a one-time $183 credit for 1-3 family homes. A state court annulled the increase, and the Board formally repealed it on January 26, 2018. The rate stayed at $3.81 for FY2016 through FY2018. Later Board charts and CAFRs show FY2017 and FY2018 as 0%. The $183 credit was paid in FY2018 and cost about $121 million.
6. **Small mismatches between proposed and adopted figures.** FY2016 was proposed at 3.24% and adopted at 2.97% (later CAFRs round it to 3.0%). FY2015's 3.35% is rounded to 3.4% in later documents. The FY2010 report proposed 14%, but the adopted rate ($2.61) works out to 12.9%. For increases, use the adoption notices.
7. **FY2007 CAFR rate table is labeled one year off.** It dates each row one July later than the FY2009 and FY2010 CAFRs and the rate schedules. The FY1997 to FY2000 values are lined up by fiscal year (each year's rate matches the next year's percentage increase exactly). The FY2008 CAFR's percent column is also misaligned, so I didn't use it for percentages.
8. **Typical-bill assumptions changed.** Single-family usage was 100,000 gallons a year in the FY2009 report, 80,000 from FY2010 to FY2019, and 70,000 from FY2019 on. The multifamily unit was 85,000 gallons in FY2009 and 52,000 after that. Because of this, the bill series has breaks: FY2018 is $1,055 on the 80,000-gallon basis, and FY2019 is $945 on the 70,000-gallon basis. Where a later report gave a "current" column (rates actually in effect), I used that over a "proposed" column.
9. **Rental payment.** Under the lease, the City can ask for rent each year. The rent can't exceed the greater of debt service on City GO bonds issued for water and sewer purposes or 15% of the Water Finance Authority's (NYW's) debt service. The amounts in the file are actuals from audited statements, except FY2027, which is budgeted. No rent was requested in FY2017, FY2018, FY2019, FY2022 or FY2023. FY2021's $137 million was called a "one-time reinstatement." From about FY2010 to FY2015 the City also sent back a "rental rebate," booked as System revenue. Those rebate amounts aren't netted out here. Budgeted rent can differ from actual: the FY2024 report budgeted $0 and the City took $145 million.
10. **What drives increases.** Board reports name debt service as the largest single cost: about 44% to 58% of the budget from FY2015 to FY2020. Earlier reports blame unfunded federal and state mandates for the capital program behind it (Croton filtration, Catskill/Delaware UV disinfection, Newtown Creek). Pandemic delinquencies weighed on FY2021 to FY2023. Rent requests came back in FY2024 and FY2025. Higher operating, vendor and personnel costs are cited for FY2026 and FY2027. A May 2019 federal consent decree requires the Hillview Reservoir to be covered by 2049 (FY2019 CAFR).

## Gaps

See `gaps` in `water.json`. In short:
- No official $/HCF rate before FY1997, and no percentage change before FY1988.
- No standalone FY2017 rate schedule. The FY2017 adoption notice PDF on nyc.gov is corrupt.
- No FY2018 or FY2021 rate report.
- No official reason given for the FY2018 freeze.
- Rental payment before FY2006 not collected.
- The IBO's 2024 water report link now redirects, so it couldn't be read.
- NYW official statements on EMMA weren't consulted.
