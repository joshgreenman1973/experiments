# NYC Price Watch — Methodology

**Version 1.1 · July 27, 2026**

This document specifies what the NYC Price Watch measures, how each
series is constructed, and — as precisely as possible — what it cannot
support. It is written for readers who will interrogate the estimator,
the sampling frame, and the geographic and temporal concordance before
they trust a number.

---

## 1. Object of measurement

The Price Watch is a **dashboard of individually-specified price series
for the New York City area**. It is not an index, not a cost-of-living
measure, and not a substitute for the Consumer Price Index.

The distinction is load-bearing, so state it plainly:

- A **price index** (CPI, PCE) tracks the cost of a fixed or
  chained basket of goods weighted by expenditure shares, with quality
  adjustment and substitution logic. It answers: *how much more does it
  cost to attain a comparable standard of living?*
- This dashboard tracks **the posted or published price of ~30 specific
  things**, each on its own terms. It answers: *what does this
  particular thing cost now, versus what it cost before?*

**There is no aggregate.** The page deliberately publishes no
composite "NYC affordability number," because the series carry no
expenditure weights and mix units (dollars, dollar-per-unit, index
levels, and year-over-year rates). Averaging them would be
meaningless. Any reader who wants an aggregate should use the CPI
series that are already on the page (`cpi_allitems`).

### What the dashboard is good for

Direction, magnitude, and composition of price change in named,
recognizable items — including several that no official index isolates
(a specific bridge toll, a specific transit fare, a benchmark taxi
trip). It is a reporting instrument, not an econometric one.

---

## 2. Relationship to official price statistics

Where an official statistic exists for a concept, we carry the official
statistic rather than construct our own. Eight series on the page are
BLS or S&P products reproduced without transformation:

| Concept | Series carried | Why not build our own |
|---|---|---|
| Overall inflation | BLS CPI-U, all items, NY-Newark-Jersey City | Expenditure-weighted, quality-adjusted; we cannot replicate |
| Groceries | BLS CPI, food at home, same CBSA | Same |
| Restaurants | BLS CPI, food away from home, same CBSA | Same |
| Energy | BLS CPI, energy, same CBSA | Same |
| Shelter | BLS CPI, shelter, same CBSA | Rental-equivalence framework; see §7.2 |
| Home prices | S&P Cotality Case-Shiller, NY metro | Repeat-sales estimator |
| Pay growth | BLS Employment Cost Index, NY metro | Fixed-weight compensation measure |
| Average pay | BLS QCEW, New York County | Near-census of covered employment |

The value added by this project is in the **other 22 series**: posted
tariffs, rate-schedule reconstructions, and market prices that are real,
locally salient, and not otherwise assembled in one place.

---

## 3. Series taxonomy and estimators

Every series falls into one of five construction types. The estimator
differs by type, and the type governs how the series may be read.

### 3.1 Administered prices (posted tariffs)

*Subway and bus base fare; Verrazzano-Narrows toll; Citi Bike annual
membership; NYC combined water and sewer rate.*

- **Estimator:** none. The published rate in effect at month *t* is
  recorded directly.
- **Sampling error:** zero. These are administered prices, not
  estimates from a sample.
- **Time-series behavior:** step functions. They are constant between
  regulatory actions and jump discretely. Month-over-month change is
  zero in almost every month by construction; the informative statistic
  is the date and size of each step.
- **Caution:** a mean of a step function over a window is not a
  meaningful "average price" — it is an artifact of where the step
  falls in the window. Read the level and the step, not the average.

### 3.2 Tariff reconstructions (synthetic bills)

*ConEd residential electricity (300 kWh); ConEd residential gas (100
therms); yellow taxi 3-mile Manhattan trip.*

- **Estimator:** a deterministic function of the published tariff and a
  **fixed, stipulated quantity vector**. For electricity:
  `bill(t) = 300 kWh × bundled_rate(t) + fixed_charges(t)`.
  For the taxi: `fare = drop + (3 mi × per-mile) + surcharges`, with
  no traffic time, no tip, no peak surcharge.
- **Interpretation:** these isolate the **price** effect by holding
  quantity constant. They are explicitly *not* estimates of what a
  household actually pays, which varies with consumption, weather,
  dwelling size, rate class, and (for taxis) traffic.
- **Known limitation:** the stipulated quantities (300 kWh, 100 therms,
  3 miles) are conventional round numbers, not the NYC modal or median
  consumption. Levels are therefore illustrative; **changes** are the
  meaningful signal, since the quantity vector is frozen.
- **Structural-break risk:** if a utility restructures its rate design
  (e.g., shifts cost recovery between fixed and volumetric charges),
  the reconstructed bill can move without any change in what a given
  household pays. Such breaks are flagged in `readings.json` and the
  series is re-stated rather than spliced silently.

### 3.3 Published market statistics (carried as-is)

*AAA gasoline average; StreetEasy median asking rent (citywide and four
boroughs); Case-Shiller; all BLS CPI series; Employment Cost Index;
QCEW average weekly wage.*

- **Estimator:** the publisher's. We record the published value on a
  fixed schedule and do not re-estimate, smooth, or re-base.
- **Each publisher's estimator differs** and is documented in §7.
- **Revisions:** several of these are revised (see §6.4).

### 3.4 Recipe indices (deterministic composites of published inputs)

*BEC ingredient index.*

- **Estimator:** a fixed-coefficient linear combination of five BLS
  average-price series:

  ```
  I(t) = 0.125·bacon(t) + 0.0833·eggs(t) + 0.046875·cheddar(t)
       + 0.15625·bread(t) + 0.0463·coffee(t)
  ```

  where coefficients are quantities (lb, dozen, lb, lb, lb) for one
  sandwich plus a 12 oz coffee, and each input is a BLS APU series.
- **This is a Laspeyres-type fixed-quantity aggregate** with quantity
  weights held permanently constant. It admits no substitution and no
  quality adjustment, by design.
- **Geographic caveat (important):** the BLS APU inputs are **U.S. city
  averages**, not New York prices. The index is therefore a *national
  ingredient-cost proxy* carried on a New York page, and is labeled as
  such on the card. It should not be read as the cost of ingredients in
  New York.
- **Provenance:** this reconstructs, from free public inputs, the
  concept behind Bloomberg's proprietary Terminal index
  `{ECAN US BEC}`. It is an independent construction, not that index,
  and the coefficient vector is ours.

### 3.5 Purposive panel surveys (not yet collected)

*Pizza slice; bagel with cream cheese; drip coffee; halal cart platter;
bacon-egg-and-cheese; Uber benchmark trip; family-of-four dinner.*

- **Estimator:** unweighted arithmetic mean of a fixed panel of named
  establishments:  `x̄(t) = (1/n) Σ pᵢ(t)`, n ≈ 5–10.
- **Sampling frame:** **purposive, not probabilistic.** The panels are
  hand-chosen for recognizability and geographic spread. They support
  **no inference to a population** of NYC pizzerias, delis, or carts.
  There is no sampling-error estimate because there is no probability
  design; a standard error computed from these panels would be
  meaningless as a population statement.
- **What they can support:** a same-store price change over time — the
  panel functions as a matched-sample tracker, which is legitimate for
  measuring *change* even though the level is not representative.
- **Status:** all seven are currently unpopulated (`TBD`) and are
  displayed as dashed placeholders. **No values are imputed.**
- **Panel maintenance:** on closure, the slot is frozen at last
  observation for that month, a replacement of similar neighborhood and
  price tier is chosen for the next month, and both the exit and entry
  are logged. Because the panel mean is unweighted, composition changes
  shift the level; splices are therefore documented rather than hidden.

---

## 4. Geographic concordance

Three distinct geographies appear on the page, and they are **not
interchangeable**. Every card carries a scope chip.

| Scope | Definition | Series |
|---|---|---|
| **New York City** | Five boroughs, or a city/state agency's jurisdiction | Subway, toll, Citi Bike, water/sewer, taxi, both ConEd bills, Broadway, all rent series, QCEW wage, all survey panels |
| **NYC metro area** | New York-Newark-Jersey City CBSA (or the Case-Shiller NY metro definition), **including parts of New Jersey and the lower Hudson Valley** | AAA gasoline, all five CPI series, Case-Shiller, Employment Cost Index |
| **U.S. city average** | National, not New York | BEC ingredient index |

**Consequences a careful reader should hold onto:**

1. **The dashboard is not a pure five-borough instrument.** Six of the
   most-cited series (gasoline, four CPI lines, Case-Shiller) are
   metro-area figures whose geography extends well beyond the city and
   includes lower-cost and higher-cost areas outside it.
2. **Cross-scope comparisons are hazardous.** Comparing city shelter
   costs to metro shelter CPI, for example, compares different
   populations.
3. **The QCEW wage series is New York County (Manhattan) only** — the
   city's dominant employment center, but not the city. A five-county
   aggregate would be materially lower. This is stated on the card.

---

## 5. Temporal alignment

### 5.1 Three distinct dates

Each observation carries up to three dates, which the project keeps
separate:

- **Reference period** — the period the value describes (e.g., "April
  2026" for a CPI print).
- **Release date** — when the publisher issued it.
- **Retrieval date** — when we recorded it.

The chart plots values at their **reference period**, not their release
or retrieval date. The card's "as of" line shows retrieval. Confusing
these is the most common way a dashboard like this goes wrong, and
`readings.json` stores the reference period explicitly.

### 5.2 Publication lag

Lags are constant per series, which preserves comparability across time
even though the panel is unbalanced in real time:

| Series | Typical lag |
|---|---|
| AAA gasoline | none (daily) |
| Administered tariffs | none (effective date known in advance) |
| BLS CPI (metro) | ~2 weeks after month end |
| StreetEasy rents | ~1–2 weeks |
| Case-Shiller | **~2 months** |
| Employment Cost Index | ~1 month after quarter end |
| QCEW | **~5–7 months** |

The panel is therefore **ragged**: the newest column is not equally
fresh across series. Cross-series comparisons at "the latest reading"
implicitly compare different reference periods. This is disclosed and
unavoidable without discarding information.

### 5.3 Frame

All charts share a 27-month frame, May 2024 – July 2026, indexed 0–26.
The window since January 1, 2026 (index 20 onward) is shaded and drawn
in a heavier stroke to isolate the current year, and each card carries a
change-since-January figure computed as first-available 2026
observation versus latest 2026 observation.

---

## 6. Data handling conventions

### 6.1 Seasonal adjustment

**Series are carried as published; most are not seasonally adjusted.**
The CPI metro series used here are NSA; Case-Shiller is available in
both forms and the YoY rate we carry is not sensitive to the choice at
the level of precision displayed.

Because most series are NSA, **year-over-year change is the preferred
statistic** and is what the page emphasizes. Month-over-month changes on
NSA series confound seasonal and trend components and should not be
annualized.

Gasoline and utility bills have pronounced seasonality (driving season;
summer cooling and winter heating). A summer gasoline increase is not
evidence of a trend break.

### 6.2 Nominal, not real

**Every dollar figure is nominal.** Nothing is deflated. A reader
wanting real terms should deflate by the all-items CPI series carried
on the page (`cpi_allitems`), noting that doing so for a metro-scope
deflator against a city-scope price is itself an approximation.

Similarly, the income-side series are nominal. The comparison a reader
usually wants — real wage change — is approximately nominal wage growth
minus all-items inflation, and the page provides both inputs rather than
computing the difference, because the two have different geographies and
reference periods.

### 6.3 Percent change versus percentage points

Series whose *values are already rates* (the five CPI lines,
Case-Shiller YoY, ECI) move in **percentage points**, and their change
figures are labeled `pp`. Series whose values are levels (dollars) move
in **percent**. The page does not mix these. Broadway paid admission is
a dollar level and is treated as such despite being suppressed from the
year-over-year badge for a separate reason (§7.4).

### 6.4 Revisions

BLS CPI (NSA series are not routinely revised, but seasonal factors and
some inputs are), Case-Shiller (routinely revised for several months),
and QCEW (revised at each subsequent release) all change after first
publication. **We record the value as first observed and do not
retroactively revise history**, because the log is intended as a record
of what was knowable at each date. Where a revision is material, it is
appended as a new note rather than silently overwriting. This means the
displayed history can differ slightly from a fresh pull of the
publisher's current vintage — a deliberate, documented trade-off in
favor of an audit trail. Readers needing the current vintage should go
to the source, which every card links.

### 6.5 Interpolation and the `est.` flag

Where a series has real observations at non-adjacent months, the
connecting line segment is **linear interpolation for display only**.
Interpolated months are not stored as observations in `readings.json`
and are not used in any computed statistic. Series containing any
interpolated display segment are flagged `est.` on the chart.

The same flag marks a series whose baseline is **back-derived** rather
than observed. Four borough rent series and the QCEW wage series carry
a year-ago point reconstructed from the publisher's own reported
year-over-year change. Such a point is arithmetically sound and
reproduces the published rate exactly — but it is not an independent
observation, so a year-over-year figure computed across it is circular
by construction: it restates the publisher's number rather than
corroborating it. It is marked `~` wherever it drives a displayed
change.

### 6.5.0 One estimator per line (no splicing)

A single plotted series must come from **one estimator, one source and
one geography throughout**. Two statistics that describe roughly the
same subject are not interchangeable, and joining them produces a
visual move that is an artifact of the join rather than a change in
price.

This rule was added after an audit found three violations:

- **Broadway** plotted a 12-month *season average* adjacent to two
  *single-week* averages. The apparent late spike was entirely the
  splice. The line now carries closed-season averages only; the latest
  weekly figure is reported in the card detail and deliberately not
  plotted.
- **Gasoline** plotted a FRED/BLS metro average for the back-history
  against AAA readings for the current period — different panels,
  different geography definitions. The line now carries AAA only.
- **ConEd** and **Case-Shiller** carried shape-approximated back-history
  beneath month-specific readings. Both now carry only real observations.

The cost of the rule is shorter series; the benefit is that every
plotted move is a real move. Where removing a splice leaves fewer than
three points, the series falls under §6.5.1 and is drawn as discrete
points rather than a line.

### 6.5.1 Minimum observations for a trend line

A series with **fewer than three observations is not drawn as a line.**
Connecting two points across a 27-month frame asserts a continuity the
data does not contain, and because the vertical axis is scaled to the
observed range, a small move between two points renders as a visually
dramatic cliff. Such series are instead plotted as **discrete points
with the observation count stated on the chart**. As of v1.1 this
affects 15 of 30 series. The count rose when the no-splice rule in
6.5.0 removed approximated back-history.

This is a display rule only; it does not alter stored values.

### 6.5.2 Baseline labeling for year-to-date change

The change-since-2026 figure compares the **first available observation
at or after January 2026** with the latest. For several series the first
2026 observation is not January — the badge therefore names the month it
actually starts from (for example "since Apr") rather than asserting a
January baseline it does not have. Where that baseline falls inside an
interpolated `est.` stretch, the figure is prefixed `~` to mark it as
approximate.

**No value is ever imputed, extrapolated, or nowcast.** A series with no
observation is blank; a series with no observations at all is a dashed
placeholder reading "awaiting data." If a scheduled fetch fails, the
prior value is held and the failure is logged in `STATUS.md` — the
series is never advanced with a modeled number.

### 6.6 Missingness

Missingness is **not at random** in one important respect: fetch
failures correlate with publisher anti-scraping behavior, not with the
underlying prices. This biases *coverage*, not *level*. Held-forward
values are visible as flat segments and are documented per run.

---

## 6.7 The 2026 view

A toggle switches every card from the full frame to 2026 alone. In that
view the headline number is replaced by the change across the series'
2026 observations, and the chart is clipped to January 2026 onward.

Two safeguards apply, because a naive year-to-date figure is easy to
misread:

1. **The window is stated, not assumed.** Several series have no
   January reading — gasoline begins in April, the CPI lines in April,
   ConEd in April. Each card prints its actual span ("Apr → Jul 2026")
   rather than implying a January baseline. The control is labeled
   "2026 so far" for the same reason.
2. **Unknowable means TBD.** Where a series has no 2026 observation, or
   only one, no change is computed and the card reads `TBD`. As of v1.0
   that applies to 16 of 30 cards, including all seven uncollected
   survey items, both wage series, and Broadway (whose 2025-26 season
   has not closed).

Series whose window can straddle a tariff season are additionally
flagged on the card, since a raw start-to-end change is then partly
seasonal — see §7.5.

## 7. Known biases and interpretive hazards, by series

### 7.1 Asking rent is not contract rent

The StreetEasy series are **median asking rents on active listings**.
They are subject to:

- **Selection on vacancy.** Only units turning over appear. Units with
  sitting tenants — the large majority of the stock — never enter.
- **Exclusion of the regulated stock.** Roughly half of NYC rental
  units are rent-stabilized; their renewal increases are set annually by
  the Rent Guidelines Board and are largely invisible to a listings
  median.
- **Composition drift.** The mix of listed units changes with the
  market; a shift toward larger or newer units raises the median with no
  price change for any unit.
- **Asking, not transacted.** Concessions and negotiated rents are not
  captured.

Consequently the asking-rent series **lead and overstate** what the
typical tenant experiences. The page carries **shelter CPI** alongside
precisely as the counterweight: shelter CPI is estimated from a
probability sample of *all* renters, including sitting and regulated
tenants, and rises more slowly. Where the two diverge, shelter CPI is
the better estimate of tenant experience and asking rent is the better
leading indicator of the marginal mover's cost.

Shelter CPI has its own well-known properties: it uses **owners'
equivalent rent** for owner-occupied housing (an imputed rental value,
not a cash outlay), and it lags market rents by roughly a year because
of lease-renewal cycles and the six-month sample rotation.

### 7.2 Averages are not medians

The QCEW wage series is an **average weekly wage** = total quarterly
wages ÷ average monthly employment. In a jurisdiction with New York
County's income distribution, this is far above the median and is
**highly sensitive to the upper tail**. It also includes bonuses on a
cash basis, which makes Q1 spike in finance-heavy geographies. Growth in
this series may reflect bonus timing or compositional change (which
jobs exist) rather than any worker's raise.

The **Employment Cost Index** is carried specifically because it fixes
occupational and industry weights, isolating pay growth from
composition. Where the two disagree, ECI is the better measure of "are
wages rising"; QCEW is the better measure of "what is total pay."

No published monthly or quarterly **median** wage exists for this
geography. The page therefore cannot answer "what happened to the
typical worker's pay," and says so.

### 7.3 Average paid admission is not ticket price

Broadway "average paid admission" is weekly gross ÷ paid attendance. It
nets out discounts and excludes comps, so it is not a list price and not
a price index: it moves with **which shows are running** and with the
premium/discount mix, not only with pricing. A season average and a
single week's figure are different objects and are not spliced into one
series; the season value is held across its months and the latest weekly
read is reported separately.

### 7.4 Repeat-sales properties

Case-Shiller is a repeat-sales index: it controls for quality by
comparing the same properties across sales, but it therefore covers only
properties that transact at least twice, excludes new construction until
a second sale, is weighted toward the single-family market, and is
smoothed by a three-month moving average. Its NY metro definition is
much larger than the city, and co-op transactions — a large share of
Manhattan housing — are handled differently from detached housing
markets. It is a sound index of its own concept; that concept is not
"the price of a New York apartment."

### 7.5 Seasonal rate structures (ConEd electricity)

Con Edison charges higher supply rates from **June 1 through September
30**. The reconstructed 300 kWh bill therefore contains a **deterministic
seasonal break**: a June figure is not comparable to a May figure, and
the recent move from roughly $120 to roughly $127 is substantially the
seasonal switch rather than a rate case. Compare summer to summer, or
use the year-over-year change. The same caution applies in reverse to
the gas bill, which is winter-weighted in consumption though we hold
quantity fixed.

### 7.6 Composition of the energy index

The metro energy CPI rose roughly 27% over the year to May 2026, a
figure corroborated by the Northeast regional release. That move is
driven **overwhelmingly by gasoline**, not by household utility bills;
electricity was approximately flat in the same release. A reader who
takes "energy +27%" to mean utility bills rose 27% will be badly wrong.
Component detail matters more than the aggregate for this line.

### 7.7 Retail gasoline averages

AAA's average is a volume-unweighted average of station-level prices
from a credit-card-transaction panel (OPIS). It is not an
expenditure-weighted price. It is highly reliable for direction and
timing, and is the standard reference.

---

## 8. Reproducibility

- **`readings.json`** is the authoritative log. One entry per series per
  observation, each carrying `date` (reference period), `value`,
  `source`, `source_url`, `cadence`, and a free-text `note` recording
  provenance and any caveat specific to that observation. Panel
  definitions and the BEC coefficient vector are stored there.
- **`index.html`** contains the display layer only; every displayed
  value traces to a `readings.json` entry.
- **`STATUS.md`** records each automated run: what moved, what was held,
  and every source that failed.
- **`SCHEDULE.md`** documents the release calendar and the refresh
  cadence.
- **`TRACKING.md`** documents per-item collection difficulty and
  sustainability.
- Version control: every change to a displayed number is a git commit
  with the source and date in the message.

**Refresh:** an automated job runs on the last Tuesday of each month —
the first date on which all prior-month sources have published — pulls
the machine-retrievable series, appends to `readings.json`, and writes
`STATUS.md`. Quarterly series (wages, family dinner) refresh in March,
June, September and December. The job is instructed never to invent a
value; on fetch failure it holds the prior reading and logs the failure.

---

## 9. Statements this dashboard does not support

Stated explicitly, because the failure modes are predictable:

1. **"New York got X% more expensive."** No composite exists here. Use
   `cpi_allitems` for that claim, with its metro caveat.
2. **"The typical New Yorker pays $X."** Nothing on this page is a
   median household outlay. The tariff reconstructions use stipulated
   quantities; the rent series are asking rents; the wage series are
   averages.
3. **"Wages are/aren't keeping up."** The page provides nominal wage and
   price series with different geographies and reference periods.
   Constructing a real-wage claim from them requires assumptions the
   page does not make on the reader's behalf.
4. **Inference from the survey panels to any population.** They are
   purposive samples usable for same-store change only, and are
   currently unpopulated in any case.
5. **Causal claims.** Nothing here identifies a causal effect of any
   policy, including congestion pricing, rate cases, or fare changes.
6. **Sub-monthly or turning-point precision.** Ragged publication lags
   and NSA data make short-window inference unreliable.

---

## 10. Change log

| Version | Date | Change |
|---|---|---|
| 1.1 | 2026-07-27 | Skeptical audit. Corrected the modeled taxi fare, which omitted the $2.50 state congestion surcharge while including the $0.75 central-business-district charge — a combination no real trip incurs; the trip is now specified by zone. Disclosed that the June ConEd figure is an announced-increase escalation, not a rate-sheet reconstruction. Added the two displayed series (Case-Shiller, ConEd gas) that had no entry in the log, which had contradicted the reproducibility claim in section 8. Split Broadway weekly reads out of the season log. Documented the circularity of back-derived baselines. Refreshed counts that drifted after the no-splice cleanup. |
| 1.0 | 2026-07-27 | First formal specification. Documents the 27-month frame, the January 2026 isolation window, the five estimator types, geographic concordance, revision and interpolation policy, the three-observation minimum for trend lines, year-to-date baseline labeling, and per-series biases including the ConEd seasonal break and the composition of the energy index. |

---

*Questions, corrections, and methodological objections are welcome as
issues on the repository. Where this document and the display disagree,
this document is the specification and the display is the bug.*
