# NYC Price Watch — Run Status

**Run date:** 2026-07-28 (last Tuesday of July; full monthly auto-refresh)

---

## What moved this month

| Item | ID | Prior value | New value | Change | Source period |
|---|---|---|---|---|---|
| Regular gas, NYC metro | `gas` | $4.24 | $4.24 | −0.0% | Jul 28, 2026 (AAA NYC metro $4.241) |
| BEC ingredient index | `bec_ingredient` | $2.01 | $2.00 | −0.5% | June 2026 BLS APU |
| Case-Shiller NY YoY | `case_shiller` | +4.0% (Mar) | +3.8% (Apr) | −0.2 pp | Apr 2026 (released Jul 6) |
| Broadway latest weekly | `broadway_weekly` | $125.79 (Jun 28) | $127.68 (Jul 26) | +1.5% | Week ending Jul 26, 2026 |

## Confirmed unchanged

| Item | Value | Confirmed |
|---|---|---|
| Subway & bus fare | $3.00 | Jul 28, 2026 |
| Verrazzano toll (NYCSC E-ZPass) | $7.46 | Jul 28, 2026 |
| Citi Bike annual membership | $239 | Jul 28, 2026 |
| Water & sewer rate | $13.85/ccf | FY2027 effective Jul 1, confirmed |
| Yellow taxi 3-mi (TLC tariff) | $18.25 | Jul 28, 2026 |
| ConEd residential electric (300 kWh) | ~$127 | Summer 2026 rate; Jun 1 – Sep 30 unchanged |
| ConEd residential gas (100 therms) | ~$253 | 2026 rate filing unchanged |
| All five CPI cards | Jun 2026 values | Jul 2026 CPI not yet released (Aug 12) |
| Borough rents (all five) | Apr 2026 values | StreetEasy returned 403; Jul data not yet published |
| ECI NY metro total comp YoY | +3.4% | Q2 2026 ECI releases Jul 31 — after this run |
| QCEW avg weekly wage | $2,837 (Q3 '25) | Quarterly; next refresh Sep 2026 |

## Sources that returned data

- **AAA gas**: gasprices.aaa.com retrieved Jul 28, 2026; NYC metro $4.241/gal, NY state $4.236/gal
- **BLS APU June 2026**: BLS API v2 — bacon $6.561/lb, eggs $2.141/doz, cheddar $5.960/lb, white bread $1.814/lb, coffee $9.457/lb; all June 2026 values confirmed
- **FRED NYXRSA April 2026**: 342.618 vs April 2025 330.095 = +3.79% YoY; FRED CSV downloaded Jul 28 2026; note prior entries (Jan–Mar 2026) were obtained via web search and differ slightly from FRED SA computation (web search yielded NSA press-release figures)
- **Broadway League**: week ending Jul 26, 2026; gross $34,864,840, paid attendance 273,061; average paid admission $127.68; retrieved Jul 28 2026

## Sources that failed or returned partial data

| Source | Item | Status |
|---|---|---|
| BLS NY-area CPI July 2026 | All five CPI cards | Not yet released; scheduled Aug 12, 2026 |
| StreetEasy rents July 2026 | All five rent cards | July data not yet published by StreetEasy |
| StreetEasy rents June 2026 | All five rent cards | Site returned 403 on all direct fetches; unverified search snippets not used (hard rule: real numbers only) |
| ConEd SC-1 tariff July 2026 | `coned` | PSC tariff PDF not parseable; summer rate confirmed unchanged at $127 per ConEd announcement |
| ECI Q2 2026 | `wage_eci` | Releases Jul 31, after this run; held at Q1 2026 (+3.4%) |
| Family Dinner Prices project | `dinner` | Quarterly; not a July series |

## ConEd seasonal note

Both ConEd series remain in summer rate season (June 1 – September 30). No new rate case or mid-season adjustment found. The $127 electric and $253 gas bills are the summer rates established in the June reading; they carry forward without a new data point until September or October.

## Takeaway

July's picture is broadly stable: gas prices held flat versus June (−$0.002/gal, essentially unchanged at $4.24), ingredient costs edged down slightly (BEC index $2.00, −$0.01), and Case-Shiller decelerated to +3.8% YoY for April — the fourth consecutive monthly slowdown since January's +4.9% peak. The BLS CPI release for July (due August 12) and Q2 ECI (July 31) will be the next two data moves to watch; combined with the StreetEasy summer rental data, August's run should be meaningfully fuller.
