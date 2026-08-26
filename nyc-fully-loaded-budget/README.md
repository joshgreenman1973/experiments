# The fully loaded budget

What New York City's agencies actually cost, once the pooled money is put back
where it was run up.

The city books pensions, health insurance and legal payouts in three central
accounts rather than against the agencies that incur them. Every chart of the
budget inherits that structure. So the published fiscal 2027 budget shows the
Police Department as a $6.3 billion line carrying no pension contribution and no
health insurance, and shows Education at $35.0 billion — a figure that already
includes $5.1 billion of benefits, because Education buys its own out of its own
budget line. The two numbers are not comparable, and nothing on the chart says so.

Reassign the $17.6 billion that can honestly be traced and the picture changes:

| Agency | As published | Fully loaded |
|---|---|---|
| Education | $35.0B | $38.9B (1.11×) |
| Social Services | $12.0B | $12.6B (1.05×) |
| **Police** | **$6.3B** | **$11.5B (1.83×)** |
| **Fire** | **$2.6B** | **$5.2B (2.00×)** |
| Sanitation | $2.0B | $2.7B (1.35×) |
| Correction | $1.2B | $1.8B (1.47×) |
| Homeless Services | $3.6B | $3.7B (1.03×) |

Police, fire and jails together: $10.1 billion as printed, $18.5 billion loaded.

A second finding falls out of the same arithmetic. The agencies that barely move
are the ones that spend on contracts and benefit payments rather than on staff.
The multiple is a decent measure of how much of an agency's work city employees
actually do.

## What is here

- Every adopted expense budget New York City publishes as open data, fiscal 2017
  through 2027, with a year selector. The current year is the default.
- Every agency, ranked, with a toggle between the published line and the fully
  loaded cost. The ranking reshuffles when you switch.
- A per-agency panel showing the arithmetic line by line, each line marked with
  how it was assigned: named in the budget, shared on the city's own headcount,
  or followed to the agency that got sued.
- The $13.3 billion that belongs to nobody: debt service, retiree health care,
  reserves, transit subsidies.
- The multiple for every agency over $100 million, plotted across all eleven
  budgets.

That last chart is where the argument lands. The lines barely move. The Police
Department has been understated by between 77 and 93 percent in every budget
since fiscal 2017; the Fire Department has run between 1.85 and 2.06 times its
line. The share of the whole budget sitting in the three central accounts has
gone from 16.2% to 14.9%. This is not a distortion that crept in, and it is not
one the city has been closing. It is how the budget is written.

## How every dollar was assigned

In [METHODOLOGY.md](METHODOLOGY.md), in full, including the limitations. In
short: $8.0 billion of the pension bill is assigned exactly as the budget writes
it, because the budget names the retirement system on every line and four of the
five belong to a single workforce. Health insurance is the one modelled step,
divided by budgeted positions, and it is checked against the two agencies that
buy the same coverage directly — $29,895 a position in the pool against $28,270
at Education and $32,576 at the City University. Legal payouts follow the
comptroller's record of which agency was named in each settled claim.

Debt service and retiree health care are deliberately left unassigned. Note
which way that cuts: uniformed workers retire earlier and are covered longer,
so holding retiree coverage aside makes the police and fire figures on this page
conservative rather than generous.

## Building

    python3 build/build.py              # every year the dataset carries
    python3 build/build.py 2024 2027    # a range
    python3 build/build.py 2022         # a single year

No dependencies beyond the standard library. Every year reconciles against the
budget's own printed totals independently, and the script **fails rather than
writes** if any of them misses by more than the rounding on individual lines.
Drift runs $0 to $8 a year across roughly 150 rounded rows.

One trap worth knowing if you touch this: agency numbers in the dataset lose
their leading zero before fiscal 2027, so the pension agency is `095` in one
year and `95` in the next. A filter that does not pad matches nothing and the
year builds with an empty pension pool instead of failing. The build pads, and
refuses any year that comes back without all three central agencies.

## Files

    index.html  styles.css  app.js  house.css     the page
    data.json                                     what the page loads
    build/build.py                                fetch, assign, reconcile
    METHODOLOGY.md                                every rule, and the limitations

`house.css` is a copy of the shared house stylesheet in `house-style/` in the
Experiments repository. If that one changes, copy it again.

## Related

- [The New York City ledger](https://joshgreenman1973.github.io/nyc-budget-per-capita/) —
  the same money over 26 audited years, per resident and inflation adjusted.
- [What New York owes](https://joshgreenman1973.github.io/nyc-pension-dashboard/) —
  the five pension funds whose bills this page reassigns.
- [The settlement ledger](https://joshgreenman1973.github.io/nyc-settlement-ledger/) —
  the claims data behind the payouts split.
