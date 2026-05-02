# NYC Price Watch — additional candidate prices

A systematic scan of quintessentially New York costs that could be added.

**Filter:** every candidate must be systematically trackable on a
quarterly basis, apples-to-apples, with a public source. That is a
sharper bar than "iconically New York." A lot of distinctive NYC
prices fail it because they only change once a year (or once a
decade), so a quarterly axis just shows a flat line.

Each candidate is weighed on:

- **NYC-iconic** (1–5)
- **Quarterly-trackability** — does this produce a genuinely apples-to-apples reading every quarter, from a public source?
- **Signal value** (1–5)
- **Tier** (1–6, see TRACKING.md)

---

## The two kinds of "trackable"

A useful distinction surfaced as I worked through this:

**Step-function items** — change rarely (once a year, or every few
years), but the change is meaningful when it happens. Quarterly chart
shows a flat line punctuated by step jumps. Examples already on the
page: subway fare, toll, water rate, Citi Bike, taxi tariff. **Useful
for "what changed this year" not "what's happening this quarter."**

**Quarterly-moving series** — produce a different reading every
quarter from real underlying activity. Examples already on the page:
gas, ConEd typical bill, Broadway average paid admission. **These are
what gives a trendline its actual shape.**

The user's constraint — apples-to-apples per quarter — privileges the
second kind. The first kind earns a place only if its NYC-icon value
is so high that a flat-then-step line is still worth showing.

---

## Quarterly-moving candidates (the strong adds)

These items produce a fresh apples-to-apples reading every quarter,
from a public, NYC-specific source.

### A. Manhattan median rent — Douglas Elliman quarterly market report

Douglas Elliman publishes the gold-standard quarterly Manhattan
rental market report, written by Miller Samuel. Same metric, same
methodology, every quarter, going back to 2008. The cleanest
quarterly NYC rent series that exists.

- NYC-iconic: 5/5
- Quarterly-trackability: ✅ designed for it (the report is quarterly)
- Signal value: 5/5
- Tier: 2 (PDF release each quarter; pull median rent and net effective rent)
- Source: [Douglas Elliman / Miller Samuel](https://www.elliman.com/resources/siteresources/commonresources/static%20pages/images/corporate-resources/q1-2024-manhattan-rental-pdf.pdf) (quarterly URLs)
- **Verdict: Add. This is arguably stronger than StreetEasy for quarterly purposes.**

### B. Brooklyn median rent — Douglas Elliman quarterly

Same publisher, same quarterly cadence, distinct NYC trend. Brooklyn
has decoupled from Manhattan repeatedly, so tracking both is worth
the marginal cost.

- NYC-iconic: 5/5
- Quarterly-trackability: ✅
- Signal value: 4/5
- Tier: 2
- **Verdict: Add (paired with Manhattan).**

### C. Case-Shiller NY metro home price index — monthly, FRED

S&P Case-Shiller Home Price Index for the New York metro area, monthly
via FRED. Roll three months to a quarterly value. The standard
home-price benchmark.

- NYC-iconic: 3/5 — the index is NY-metro, not 5-borough
- Quarterly-trackability: ✅ monthly index → trivial quarterly average
- Signal value: 5/5 — most-cited home-price series in the country
- Tier: 2 (FRED series CSUSHPISA / NYXRSA)
- **Verdict: Add — gives the homeowner side of the rent index.**

### D. NYC unemployment rate (BLS LAUS)

Monthly. Quarterly average is straightforward. Affordability is income
divided by costs; a tracker that only watches the costs is half-blind.
Adding the unemployment rate adds a small dose of the income side
without pretending we're calculating burden.

- NYC-iconic: 3/5 — every city has one, but NYC's is published cleanly
- Quarterly-trackability: ✅ monthly BLS release
- Signal value: 4/5
- Tier: 2 (FRED series NYNYC0URN)
- **Verdict: Add as a context line — flag clearly as "income side, for context."**

### E. NYC-Newark-JC food-away-from-home CPI

Companion to the food-at-home CPI we already track. This is the
restaurant-prices index, distinct from grocery prices, monthly. Pairs
with grocery basket to give two halves of the food story.

- NYC-iconic: 3/5
- Quarterly-trackability: ✅
- Signal value: 4/5
- Tier: 2 (FRED series CUURA101SEFV)
- **Verdict: Add — natural twin of the existing food-at-home line.**

### F. NYS home heating oil weekly average

NYSERDA publishes statewide heating-oil prices weekly. Quarterly
average is trivial. Heating oil affects ~600,000 NY households,
heavily concentrated downstate. Notable for tracking energy
affordability beyond just electricity.

- NYC-iconic: 3/5 — region, not just city
- Quarterly-trackability: ✅ weekly source
- Signal value: 4/5 in winter quarters, less in summer
- Tier: 2
- Source: [NYSERDA Weekly Heating Oil](https://www.nyserda.ny.gov/Researchers-and-Policymakers/Energy-Prices/Home-Heating-Oil/Weekly-Average-Home-Heating-Oil-Prices)
- **Verdict: Borderline add. Useful complement to ConEd.**

### G. ConEd natural gas typical bill, residential

The gas counterpart to the electric bill we already construct. ConEd
posts gas tariffs monthly. Typical residential winter usage produces
a large enough seasonal swing that quarterly readings are meaningful.

- NYC-iconic: 4/5
- Quarterly-trackability: ✅ rate-built each quarter
- Signal value: 4/5
- Tier: 4 (rate reconstruction)
- **Verdict: Add — natural twin of the ConEd electric line.**

### H. MTA average weekday subway ridership

Not a price, but a quintessentially NYC indicator that contextualizes
the affordability story (post-pandemic recovery; congestion pricing
effects). Published monthly, MTA dashboard. Could anchor a "context"
section rather than a price card.

- NYC-iconic: 5/5
- Quarterly-trackability: ✅
- Signal value: 4/5
- Tier: 2
- **Verdict: Maybe — context only, not a price.**

---

## Step-function candidates (genuine NYC, but flat-line on a quarterly chart)

These are distinctive NYC prices that are real and trackable, but
won't move most quarters. Each one earns its place only if its
icon-value is unusually high.

| Candidate | NYC-icon | Moves how often | Recommendation |
|---|---|---|---|
| Rent Guidelines Board renewal cap | 5/5 | Annual (June vote) | ✅ Add — the most important NYC rent number |
| CUNY in-state undergraduate tuition | 4/5 | Annual or every 2 yrs | ⚠️ Maybe |
| Met Museum non-resident admission | 5/5 | Multi-year | ⚠️ Skip — too flat |
| NYC Ferry single ride | 5/5 | Multi-year | ⚠️ Skip — too flat |
| AirTrain JFK | 4/5 | Multi-year | ⚠️ Skip — too flat |
| NYC parking ticket — common offense | 5/5 | Multi-year | ⚠️ Skip — too flat |
| TMR Yankees ballpark hot dog | 4/5 | Annual | ⚠️ Maybe |
| Knicks/Rangers MSG average ticket | 4/5 | Annual | ⚠️ Skip — sports-heavy |
| NYT weekday newsstand | 3/5 | Multi-year | ❌ Cut — not distinctive enough |
| NYC dog license | 5/5 | Doesn't move | ❌ Cut — flat is flat |
| Mortgage Recording Tax | 4/5 | Doesn't move | ❌ Cut |
| Marriage license | 4/5 | Doesn't move | ❌ Cut |

The honest read: **only RGB renewal cap is icon enough to justify a
flat-line card.** Everything else is more useful as a sidebar fact
than as a tracked line.

---

## Recommended adds — the strong list

A cleaner final lineup of additions, each producing a meaningful
quarterly reading:

1. **Manhattan median rent (Douglas Elliman)** — quarterly, the cleanest NYC quarterly rent series
2. **Brooklyn median rent (Douglas Elliman)** — quarterly, distinct trend
3. **Case-Shiller NY metro home price index** — monthly, rolls to quarterly cleanly
4. **NYC food-away-from-home CPI** — monthly, twin to existing food-at-home
5. **ConEd typical gas bill** — monthly rate, twin to electric
6. **RGB renewal cap** — annual but highest-icon flat-line card

Optional 7th:

7. **NYC unemployment rate** — monthly, context for the cost side

That brings the page to 17 items: the 11 sustainable from
TRACKING.md + 6 strong adds. All quarterly-trackable, all real, all
sourced.

---

## What's deliberately not on this list

- Hand-survey panels (pizza, bagel, coffee) — already cut in TRACKING.md
- Step-function items below RGB-tier icon-value
- Property tax (math too dense for a clean monthly)
- Median NYC home sale (volatile, small samples by month)
- Anything that requires a paid data subscription
- "Average meal price at a New York restaurant" — too varied to be
  apples-to-apples without a panel

The discipline: **distinctive, trackable, AND meaningful, AND moves
on a quarterly axis.** Three out of four isn't enough for the page,
though those items can live in supporting docs as context.
