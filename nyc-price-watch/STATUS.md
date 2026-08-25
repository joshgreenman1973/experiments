# NYC Price Watch — Monthly Refresh Status

**Run date:** 2026-08-25 (last Tuesday of August 2026)
**Month covered:** August 2026 refresh (CPI reference period: July 2026; gas/ConEd reference period: August 2026)
**Quarter:** Q3 — NOT a quarterly month; wages (QCEW, ECI) and family dinner skipped.

---

## Data Updated This Run

| Series | Prior value | New value | Change | Source |
|--------|-------------|-----------|--------|--------|
| Gas (NYC metro) | $4.241 (Jul 28) | $4.190 (Aug 25) | −$0.051 | AAA Manhattan proxy |
| ConEd electric (300 kWh) | $127.00 | $127.00 | held | Summer rate continues |
| CPI food at home (Jul 2026) | +4.0% (Jun) | +3.3% | −0.7 pp | BLS Aug 12 release |
| CPI restaurants (Jul 2026) | +3.2% (Jun) | +3.6% | +0.4 pp | BLS Aug 12 release |
| CPI all items (Jul 2026) | +4.1% (Jun) | +4.6% | +0.5 pp | BLS Aug 12 release |
| CPI energy (Jul 2026) | +16.2% (Jun) | +15.7% | −0.5 pp | BLS Aug 12 release |
| CPI shelter (Jul 2026) | +4.3% (Jun) | +4.8% | +0.5 pp | BLS Aug 12 release |
| BEC ingredient index (Jul 2026) | $2.00 (Jun) | $1.99 | −$0.01 | BLS APU series |
| Broadway weekly (ref only) | $127.68 (Jul 26) | $113.35 (Aug 23) | −$14.33 | Broadway League |

---

## Series Held (Not Updated)

| Series | Last value | Reason |
|--------|-----------|--------|
| Rent (citywide, Manhattan, Brooklyn, Queens, Bronx) | Apr 2026 values | StreetEasy returned 403 for 2nd consecutive month |
| Case-Shiller NY (NYXRSA) | +3.8% (Apr 2026) | FRED NYXRSA returned 403 |
| ConEd gas (100 therms) | $253 (Jun 2026) | Rate-class mismatch flagged (see note below) |
| Subway fare | $3.00 | No rate change |
| All tolls | prior values | No confirmed change |
| Citi Bike | prior value | No confirmed change |
| Water | prior value | No confirmed change |
| Taxi | prior value | No confirmed change |
| Wages (AHE, AWE) | Jun 2026 values | Not a quarterly month; wages updated monthly but held this run |
| Case-Shiller | Apr 2026 | FRED 403 |

---

## Fetch Failures

- **StreetEasy** (all 5 rent series): HTTP 403 — second consecutive month. Web search returned conflicting figures ($3,950 vs $4,200 citywide) from unverified press coverage; per hard rules, all rent series held at April 2026 values.
- **FRED NYXRSA** (Case-Shiller NY): HTTP 403. Cannot substitute 20-city composite — must be NY-specific. Held at +3.8% (April 2026).
- **ConEd electric tariff page**: HTTP 404 (URL structure appears to have changed). Summer rate season (Jun 1–Sep 30) continues unchanged; $127 carried forward with seasonal note.

---

## Data Quality Notes

**ConEd gas rate-class mismatch (flagged, not updated):**
The tariff retrieval agent computed a bill of ~$270–290 for 100 therms under SC3 (large commercial), versus the prior $253 value which appears to reflect SC1 (small general service) rates. Since the "same spec each month" rule applies and the rate class cannot be definitively confirmed from this run, ConEd gas is held at $253 (June 2026). Action required: verify which rate class was used for the original ConEd gas baseline and document in METHODOLOGY.md before the next update.

**AAA gas — no unified NYC metro composite:**
AAA does not publish a single "NYC metro" composite price. Manhattan ($4.1898/gal) was used as the closest available proxy for NYC proper, consistent with the historical pattern of the series tracking above NY state average ($4.174/gal). This proxy choice is noted in the card's work rows.

**ConEd electric — seasonal note:**
The $127 rate is a summer-season rate (June 1–September 30, 2026). YoY comparisons crossing this seasonal boundary reflect a tariff-season change as well as any underlying cost movement; interpret with caution.

**Broadway weekly — reference only:**
$113.35 (week ending Aug 23, 2026) recorded in `broadway_weekly` in readings.json only. Not plotted. The 2025–26 season is still in progress; the season series remains at the 2024–25 average ($129.12) until the current season closes.

---

## One-Sentence Takeaway

NYC inflation edged up in July 2026 (+4.6% headline vs +4.1% in June), with shelter and restaurant prices firming while groceries and energy continued to cool; rent data remains unavailable for a second month due to StreetEasy blocking.
