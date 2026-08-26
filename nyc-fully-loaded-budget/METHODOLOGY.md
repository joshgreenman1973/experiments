# Method

New York City's expense budget assigns money to 141 agencies. Three of those
agencies do not run anything. Agency 095 holds the city's pension
contributions, agency 098 holds health insurance, payroll taxes and legal
payouts, agency 099 holds debt service. Between them they hold about $31
billion of a $118 billion budget.

Every published chart of the city budget inherits that structure, which is why
they all show the Police Department as a $6.3 billion line with no pension
contribution and no health insurance in it. This page moves the pooled money
back to the agencies that incur it, and says for every dollar how confident
that assignment is.

## Sources

| What | Dataset | Notes |
|---|---|---|
| Expense budget by agency, unit, object code and position | [`mwzb-yiwb`](https://data.cityofnewyork.us/City-Government/Expense-Budget/mwzb-yiwb) | Office of Management and Budget |
| Settled claims against the city, by agency | [`ex6k-ym48`](https://data.cityofnewyork.us/City-Government/Claims-Report-Underlying-Settlements-and-Claims-Fi/ex6k-ym48) | Comptroller's claims report |
| Population denominator | Census Bureau vintage 2025 estimate, 8,584,629 | Same denominator as The New York City ledger; held flat for budget years |

The budget dataset keeps every publication snapshot of a fiscal year as its own
set of rows — a year is republished two or three times as it moves from
preliminary to executive to adopted. Grouping on `fiscal_year` alone therefore
sums the snapshots and overstates the year by two or three times. The build
takes the newest `publication_date` for the year and records which one it used
in `data.json`.

## Pensions: named in the budget

The pension agency writes its payment to each retirement system on its own line,
and four of the five systems belong to a single workforce:

| Budget line | Goes to | Fiscal 2027 |
|---|---|---|
| Teachers' Retirement System (two lines) | Department of Education | $3.62B |
| Board of Education Retirement System | Department of Education | $0.24B |
| Police Actuarial Pension Fund | Police Department | $2.54B |
| Fire Actuarial Pension Fund | Fire Department | $1.63B |
| Contingent Reserve Fund | shared — see below | $2.32B |
| Non-city pensions | left unassigned | $0.11B |

$8.0 billion of the $10.5 billion pension bill is assigned exactly as the budget
writes it. Nothing is modelled.

The contingent reserve fund is the city's payment to the New York City
Employees' Retirement System, which covers nearly everyone the other four funds
do not. It is divided across agencies by payroll, after removing the pay that
belongs to the four named funds. That removal uses the budget's own object
codes, not an estimate: `FULL TIME UNIFORMED PERSONNEL` at the police and fire
departments, and all Education payroll, come out of the base. What is left at
the police and fire departments is their civilian and emergency medical staff,
who are in fact employees' retirement system members, so they get a share.

**Known limitation.** Pension contributions are actuarially determined per
fund, not proportional to payroll, and the employer rate differs sharply
between funds — the fire fund's rate runs near 100% of covered payroll while
the employees' system runs near a quarter of it. Sharing *within* the
employees' system by payroll is reasonable because one rate applies across it.
Sharing *between* funds by payroll would not be, and is not done here.

## Health insurance and payroll taxes: modelled, then checked

The miscellaneous agency's fringe benefits unit holds $9.39 billion. It is split
three ways.

**Held out.** The retiree health benefits trust, budget code 3006, is $2.94
billion. It pays for people who no longer work for the city. It is not charged
to any current agency.

**Divided by budgeted positions, $4.74 billion.** Health insurance, welfare fund
contributions, workers' compensation, unemployment and uniform allowances follow
people rather than salaries, so they are divided by each agency's budgeted
positions.

**Divided by payroll, $1.70 billion.** Payroll taxes track wages.

The Department of Education and the City University buy their own health
insurance and pay their own payroll taxes out of their own budget lines. They
are detected by rate rather than by name — an agency spending more than $5,000 a
position on health insurance, or more than 3% of payroll on payroll taxes, is
taken out of the corresponding pool rather than charged twice.

**The check.** This is the only modelled step on the page, and the city's own
behaviour tests it. The pooled headcount rate works out to **$29,895 a budgeted
position**. Education, buying the same coverage directly, spends **$28,270** a
position on the same components, and the City University **$32,576**. Three
independent numbers within about a tenth of each other. The build fails if any
self-funding agency's rate falls outside 0.65 to 1.55 times the pooled rate.

**Known limitation.** Workers' compensation is not evenly distributed — sanitation,
police and fire generate far more of it per employee than an office agency does,
and dividing it by headcount understates them. It is $616 million of a $9.4
billion pool.

## Judgments and claims: followed to the agency that got sued

The budget provides one line, $823 million in fiscal 2027, for judgments and
claims across the whole city. The comptroller's claims report names the agency
in every settled claim. The line is split on each agency's share of settlement
dollars over fiscal 2021 to 2023, the most recent three years published.

95.5% of settlement dollars name an agency that also appears in the budget. The
rest stays unassigned rather than being spread around. The build fails below
85%.

The police share is 35.8%, transportation 13.6%, sanitation 10.4%, education
10.0%, health and hospitals 9.3%.

**Known limitation.** The judgments line is budgeted well below what the city has
recently paid. Actual settlements ran about $1.4 billion in fiscal 2025. Using
the budget's own figure keeps the page internally consistent, but it means the
payout component here is conservative for every agency.

## What is deliberately not assigned

$13.3 billion, 11% of the budget, stays where the budget puts it.

- **Debt service, $4.87 billion.** It could be pushed onto agencies by tracing
  which function the capital was built for, but the answer would be a guess
  dressed as arithmetic. It is a bill from capital budgets of past years.
- **Retiree health care, $2.94 billion.** Note which way this cuts: uniformed
  workers retire earlier and are covered longer than other city employees, so
  holding this aside makes the police and fire figures conservative.
- **Reserves and contingency, $1.58 billion.** Not yet assigned to anything.
- **Transit subsidies, $1.30 billion.** The city pays the Metropolitan
  Transportation Authority; it does not operate it.
- **State building aid, $1.20 billion.** A pass-through tied to school
  construction debt.
- **Collective bargaining reserve, $673 million.** Raises not yet written into
  any agency's payroll line.
- **Other central charges, $719 million.**

Capital spending is not on this page at all. This is the expense budget, the
same thing the published charts show. The city spent about $15.6 billion on
capital in fiscal 2025 on top of it.

## What reconciles

The build fails rather than writes if any of these do not hold:

1. Agency totals sum to the citywide total.
2. Pension object codes sum to the pension agency's total.
3. Miscellaneous detail sums to the miscellaneous agency's total.
4. Each pool's allocations plus its unassigned remainder equal the pool.
5. Fully loaded agency costs plus unassigned central charges equal the citywide
   total, within the rounding on individual lines. Current drift: **$8** across
   roughly 150 rounded rows.
6. Every self-funding agency's own benefits rate lands within 0.65 to 1.55 times
   the pooled rate.
7. At least 85% of settlement dollars map to a budget agency.

## What this is not

An agency costing more than its published line is not an argument that it
should cost less. The claim is narrower, and it is about the chart rather than
the policy: the number the city prints next to an agency's name is not that
agency's cost, the gap is different for every agency, and so any ranking built
on published lines is wrong in a way nobody can see from the chart.

Nor is a low multiple a compliment. Agencies that barely move — homeless
services at 1.03, education at 1.11 — are mostly agencies that spend on
contracts and benefits payments rather than on staff. The multiple measures how
much of an agency's work is done by city employees, which is worth knowing on
its own.

## Rebuilding

    python3 build/build.py           # fiscal 2027, the current adopted budget
    python3 build/build.py 2026      # any fiscal year in the dataset

The script writes `data.json` only if every check passes. Bump the `?v=` stamp
on the asset links in `index.html` when deploying, so a cached copy of one file
is never paired with a fresh copy of another.
