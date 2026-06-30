# NYC Price Watch — Run Status

**Run date:** 2026-06-30 (last Tuesday of June; full refresh)

---

## What moved this month

| Item | ID | Prior value | New value | Change | Source period |
|---|---|---|---|---|---|
| Regular gas, NYC metro | `gas` | $4.63 | $4.24 | −8.4% | Jun 30, 2026 (AAA) |
| Groceries CPI YoY | `cpi` | +5.9% | +4.0% | −1.9 pp | May 2026 BLS |
| Restaurants CPI YoY | `restaurant_cpi` | +3.4% | +3.2% | −0.2 pp | May 2026 BLS |
| Overall CPI YoY | `cpi_allitems` | +4.6% | +5.1% | +0.5 pp | May 2026 BLS |
| Energy CPI YoY | `cpi_energy` | +24.0% | +26.9% | +2.9 pp | May 2026 BLS |
| Shelter CPI YoY | `cpi_shelter` | +4.1% | +4.8% | +0.7 pp | May 2026 BLS |
| BEC ingredient index | `bec_ingredient` | $2.05 | $2.01 | −2.0% | May 2026 BLS APU |
| Broadway avg paid admission | `broadway` | wk $120.43 | wk $125.79 | +5.4% | Wk of Jun 28, 2026 |
| Case-Shiller NY YoY | `case_shiller` | +4.7% (Feb) | +4.0% (Mar) | −0.7 pp | Mar 2026 |
| ConEd residential electric (300 kWh) | `coned` | ~$120 | ~$127 | +5.8% | Summer 2026 rate |
| Water & sewer rate | `water` | $13.07/ccf | $13.85/ccf | +6.0% | FY2027 eff. Jul 1, 2026 |

## Confirmed unchanged

| Item | Value | Confirmed |
|---|---|---|
| Subway & bus fare | $3.00 | Jun 30, 2026 |
| Verrazzano toll (NYCSC E-ZPass) | $7.46 | Jun 30, 2026 |
| Citi Bike annual membership | $239 | Jun 30, 2026 |
| Yellow taxi 3-mi (TLC tariff) | $15.75 | Jun 30, 2026 |
| ConEd residential gas (100 therms) | ~$253 | Jun 30, 2026 |
| All five borough rents | Apr 2026 values | May 2026 StreetEasy data not yet published |
| ECI NY metro total comp YoY | +3.4% | Q1 2026 (Q2 releases Jul 31) |
| QCEW avg weekly wage | $2,837 (Q3 '25) | See note below |

## Sources that returned data

- **AAA gas**: Retrieved direct from gasprices.aaa.com, June 30, 2026
- **BLS NY-Newark-JC CPI May 2026**: Retrieved via BLS northeast news release (web search; direct URL returned 403)
- **BLS APU average prices May 2026**: bacon ($6.712/lb), eggs ($2.191/doz), cheddar ($5.685/lb), white bread ($1.830/lb), coffee ($9.511/lb) — retrieved from data.bls.gov/timeseries
- **Broadway League**: June 28, 2026 weekly grosses page fetched directly
- **Case-Shiller NYXRSA**: March 2026 value (+4.0% YoY) confirmed via web search (FRED returned 403)
- **ConEd rate info**: Retrieved via web search; summer 2026 residential electric +5.7% per ConEd outlook page
- **NYC Water Board FY2027**: +6.0% rate proposed by DEP, Water Board vote June 10, 2026, effective July 1, 2026 — confirmed via DEP press release and third-party coverage

## Sources that failed or returned partial data

| Source | Item | Status |
|---|---|---|
| StreetEasy May 2026 rent data | `rent`, `manhattan_rent`, `brooklyn_rent`, `queens_rent`, `bronx_rent` | May 2026 data not yet published; April 2026 figures held |
| QCEW Q4 2025 dollar amount | `wage_qcew` | Q4 2025 released June 2, 2026; New York County +5.8% YoY confirmed, but specific dollar figure not retrievable from search results; card held at Q3 2025 = $2,837 |
| Family Dinner Prices project | `dinner` | Sister project page did not return a specific current value; still TBD |
| ConEd exact tariff (per-kWh) | `coned` | rates.coned.com returned empty; estimate rebuilt from announced +5.7% summer increase applied to prior $119.70 baseline |
| BLS NY CPI direct page | Multiple CPI cards | bls.gov returned 403; values obtained via web search of release content |
| FRED NYXRSA | `case_shiller` | fred.stlouisfed.org returned 403; March 2026 value confirmed via web search |

## Takeaway

June's picture is **mixed**: energy and shelter costs are both accelerating (energy CPI +26.9% YoY, shelter CPI +4.8% — the highest in this series), but gas prices at the pump fell sharply this month (−8.4% from the May peak, now $4.24/gal), grocery inflation eased noticeably (food-at-home CPI cooling from +5.9% to +4.0%), and the BEC ingredient index dipped to $2.01. The ConEd summer rate bump and the new FY2027 water rate (+6%) add to household utility costs starting this month. Against this, the income-side gauges — QCEW wage growth confirmed at +5.8% YoY for Q4 2025 (dollar figure pending), ECI total comp +3.4% — are running well below the +5.1% all-items CPI, pointing to continued real wage compression in the metro area.
