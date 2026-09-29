# NYC Price Watch - Monthly Refresh Status

**Run date:** 2026-09-29 (last Tuesday of September 2026)
**Frame:** NM 28 -> 29; new month index 28 = Sep 2026
**Reference periods:** gas Sep 2026 (idx 28); CPI and BEC ingredient index Aug 2026 (idx 27, plotted at reference period per METHODOLOGY 5.1)
**Quarter:** September is a quarterly month (see the quarterly notes below)

---

## Data updated this run

| Series | Prior value | New value | Change | Source |
|--------|-------------|-----------|--------|--------|
| Gas (NYC, AAA Manhattan) | $4.190 (Aug 25) | $4.576 (Sep 29) | +$0.386 (+9.2%) | AAA NY page dated 9/29/26 |
| CPI food at home | +3.3% (Jul) | +3.1% (Aug) | -0.2 pp | BLS CUURS12ASAF11 |
| CPI restaurants | +3.6% (Jul) | +3.6% (Aug) | 0.0 pp | BLS CUURS12ASEFV |
| CPI all items | +4.6% (Jul) | +4.3% (Aug) | -0.3 pp | BLS CUURS12ASA0 |
| CPI energy | +15.7% (Jul) | +15.4% (Aug) | -0.3 pp | BLS CUURS12ASA0E |
| CPI shelter | +4.8% (Jul) | +4.4% (Aug) | -0.4 pp | BLS CUURS12ASAH1 |
| BEC ingredient index | $1.99 (Jul) | $2.01 (Aug) | +$0.02 | BLS APU (bacon $6.605, eggs $2.272, cheddar $5.983, bread $1.823, coffee $9.299) |
| Broadway weekly (not plotted) | $113.35 (Aug 23) | $115.18 (Sep 27) | +$1.83 | Broadway League |

CPI and APU values were read from the data.bls.gov series pages because the BLS API returned its daily-quota error. The July figures on those same pages reproduce last month's stored values exactly, which confirms the source matches.

## Held (not updated)

| Series | Last value | Reason |
|--------|-----------|--------|
| Rents (citywide, Manhattan, Brooklyn, Queens, Bronx) | Apr 2026 | fetch failed: StreetEasy 403 (third straight month). Web search surfaced conflicting, unverifiable figures and non-StreetEasy (Real Deal/Corcoran) numbers; none were used |
| Case-Shiller NY | +3.8% (Apr 2026) | fetch failed: FRED/ALFRED gave empty replies, S&P blocked. A web-fetch summary of FRED returned internally inconsistent values, so it was rejected |
| ConEd electric (300 kWh) | $127 (Jun 2026) | fetch failed: tariff page 404. No new point plotted |
| ConEd gas (100 therms) | $253 (Jun 2026) | fetch failed: tariff page 404. The rate-class question from August is still open |
| Subway $3.00, Verrazzano $7.46, Citi Bike $239, water $13.85/ccf | unchanged | No official change found |
| Taxi 3-mi | $18.25 | No official change. Note: the run prompt still lists $15.75, but the card was corrected to $18.25 on Jul 27 (state congestion surcharge); it was left as is |
| CES hourly/weekly earnings and the BLS spotlight | Jun 2026 | Not refreshed: the pipeline is API-only and the API quota was exhausted |

## ConEd seasonal note

There is no seasonal crossing this run: September sits inside the summer supply season (Jun 1 - Sep 30). **The October run will cross back into winter rates.** Any October move in the electric bill will be seasonal, not a rate case.

## Quarterly items

- **Family dinner:** not touched. It is on the field-survey do-not-touch list, and the sister-project page showed no headline figure a text fetch could read.
- **Wages (QCEW, ECI):** the page has no `wage_qcew` or `wage_eci` card. The income side is now the two CES cards (`wage_ahe`, `wage_awe`), and they were held this run (see above). Those wage cards are the income side of the page; pay and prices are shown side by side, never subtracted.

## Fetch failures

- BLS API: daily request threshold reached (used data.bls.gov pages instead)
- StreetEasy: 403
- FRED / ALFRED (NYXRSA): empty reply; S&P Global: security block
- Con Edison rates page: 404
- bls.gov regional release page and AAA via curl: 403 (AAA succeeded via web fetch)

## Takeaway

Metro inflation cooled to 4.3% in August as shelter and energy eased, but pump prices jumped more than 9% in September to about $4.58, and rents and home prices remain dark for a third month because StreetEasy and FRED are blocking automated retrieval.
