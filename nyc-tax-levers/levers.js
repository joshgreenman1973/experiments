/* The levers. Each one edits a copy of the PolicyEngine parameters, or, where
 * PolicyEngine has no parameter for the idea, P.extra, which engine.js reads.
 * Statuses were checked Nov. 18, 2026; the sources are linked on each lever
 * and summarized on methodology.html. */
const TOP_PLANS = [
  // Senate one-house budget, March 2026: 10.8% from $5M to $25M, 11.4% above $25M.
  [{ t: 5e6, d: 0.005 }, { t: 25e6, d: 0.005 }],
  // Assembly one-house budget, March 2026: 10.5% ($5M-$10M), 10.75% ($10M-$25M),
  // 11.75% ($25M-$100M), 12% (over $100M). Today: 10.3% and 10.9%.
  [{ t: 5e6, d: 0.002 }, { t: 10e6, d: 0.0045 }, { t: 25e6, d: 0.0085 }, { t: 100e6, d: 0.011 }],
];
const ESCC = "gov.states.ny.tax.income.credits.ctc.post_2024";

const LEVERS = [
  {
    id: "toprates", level: "state",
    title: "Higher state rates above $5 million",
    what: "The state's top rates are now 10.3 percent on taxable income from $5 million to $25 million and 10.9 percent above $25 million. The Senate proposed 10.8 and 11.4 percent. The Assembly proposed 10.5 percent up to $10 million, 10.75 percent up to $25 million, 11.75 percent up to $100 million and 12 percent above that.",
    status: "Both passed only as part of each house's March 2026 budget proposal and were dropped from the final budget. Gov. Kathy Hochul has opposed raising income taxes but in November left room for new revenue for child care",
    note: "As under today's law, a filer well past a bracket's start pays that bracket's rate on all taxable income, not just the part above it.",
    sources: [["EY, March 19, 2026", "https://taxnews.ey.com/news/2026-0679-new-york-budget-negotiations-continue-as-assembly-and-senate-bills-are-introduced"], ["NY Focus, March 10, 2026", "https://nysfocus.com/2026/03/10/senate-assembly-mamdani-tax-hikes"], ["Spectrum News, Nov. 7, 2026", "https://nystateofpolitics.com/state-of-politics/new-york/politics/2026/11/07/hochul-does-not-rule-out-new-taxes-to-help-fund-programs-like-universal-childcare"]],
    controls: [{ k: "plan", type: "choice", label: "Version", value: 0, options: [[0, "Senate"], [1, "Assembly"]] }],
    apply(P, v) { P.extra.nyTop = TOP_PLANS[v.plan]; },
  },
  {
    id: "escc", level: "state",
    title: "Empire State Child Credit after 2027",
    what: "Today the state pays $1,000 per child under 4 and $500 per child 4 to 16. That expansion ends after 2027, when the credit falls back to the old formula: 33 percent of a 2017-style federal child credit, or $100 per child if that's more. A bill from Sen. Andrew Gounardes, S9077, would instead raise it over several years.",
    status: "The fallback is current law for 2028. S9077 is in committee",
    note: "S9077 doesn't say whether today's phase-out, $16.50 per $1,000 of income over $110,000 for couples and $75,000 for others, still applies. The calculator assumes it does.",
    sources: [["Tax Law 606(c-1)", "https://www.nysenate.gov/legislation/laws/TAX/606"], ["S9077", "https://www.nysenate.gov/legislation/bills/2025/S9077"]],
    controls: [{ k: "plan", type: "choice", label: "Version", value: 0, options: [[0, "Lapses (2028 rules)"], [1, "S9077 in 2029: $1,500 under 4, $1,250 ages 4 to 17"], [2, "S9077 in 2030: $1,500 per child under 18"]] }],
    apply(P, v) {
      const c = P.ny.credits.ctc.post_2024;
      if (v.plan === 0) c.in_effect = false;
      else { c.amount.amounts[0] = 1500; c.amount.amounts[1] = v.plan === 1 ? 1250 : 1500; c.amount.thresholds[2] = 18; }
    },
  },
  {
    id: "nyeitc", level: "state",
    title: "Bigger state earned income credit",
    what: "New York adds 30 percent of the federal earned income credit. S4425, from Sen. Patricia Fahy, would raise that to 35 percent in 2027 and 40 percent after. A5661, from Assembly Republican leader Will Barclay, would make it 45 percent.",
    status: "Both bills are in committee",
    note: "S4425 would also change who qualifies and pay part of the credit in advance; only the higher match is modeled.",
    sources: [["S4425", "https://www.nysenate.gov/legislation/bills/2025/S4425"], ["A5661", "https://www.nysenate.gov/legislation/bills/2025/A5661"]],
    controls: [{ k: "match", label: "Share of the federal credit", min: 0.30, max: 0.45, step: 0.05, value: 0.40, fmt: "pct" }],
    apply(P, v) { P.ny.credits.eitc.match = v.match; },
  },
  {
    id: "wftc", level: "state",
    title: "Working Families Tax Credit",
    what: "S2082, from Gounardes and Assemblymember Andrew Hevesi, would replace the Empire State Child Credit with one refundable credit per child. For families with children it would also end the state earned income credit and the $1,000 dependent exemption. Fully phased in, it pays $1,600 per child through age 17, less $20 per $1,000 of income over $25,000 ($50,000 for couples), and never less than $100 per child.",
    status: "Cleared the Senate budget committee in February 2025 and is back in committee. If both this and the child credit lever are on, this one replaces the child credit",
    note: "This is the bill's fifth year and after. Its amounts and thresholds rise with inflation from 2023; the calculator uses the dollar figures in the bill. The bill doesn't name head of household filers; they're treated like single filers.",
    sources: [["S2082", "https://www.nysenate.gov/legislation/bills/2025/S2082"]],
    controls: [],
    apply(P) { P.extra.wftc = { amount: 1600, floor: 100, per1000: 20, thrSingle: 25000, thrJoint: 50000 }; },
  },
  {
    id: "fairshare", level: "city",
    title: "Mamdani's tax on incomes over $1 million",
    what: "Mayor Zohran Mamdani's Fair Share Act would add 2 percent to the city income tax on city taxable income over $1 million, on top of today's top city rate of 3.876 percent. The bill (S8577, Sen. John Liu; A8953, Assemblymember Phara Souffrant Forrest) needs a state law and would start no earlier than 2027.",
    status: "In committee all of 2026 and left out of the state budget. Mamdani's allies say they will try again in 2027",
    note: "The bill's text doesn't make clear whether the 2 percent applies only to income over $1 million or to all of a millionaire's income. The sponsor's memo describes the first; Mamdani's example, $20,000 more from someone earning $1 million, matches the second. Pick one below.",
    sources: [["S8577", "https://www.nysenate.gov/legislation/bills/2025/S8577"], ["Mamdani in Albany, Feb. 11, 2026", "https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-s-prepared-remarks-at-the-2026-joint-legislative-b.html"], ["NY Focus, June 17, 2026", "https://nysfocus.com/2026/06/17/mamdani-hochul-nyc-budget-gaps"]],
    controls: [
      { k: "base", type: "choice", label: "Taxes", value: 0, options: [[0, "Only income over the threshold"], [1, "All income, once over it"]] },
      { k: "rate", label: "Added rate", min: 0.005, max: 0.04, step: 0.0025, value: 0.02, fmt: "pct" },
      { k: "threshold", label: "Threshold", min: 250000, max: 2000000, step: 50000, value: 1000000, fmt: "usd" },
    ],
    apply(P, v) {
      P.mamdani.in_effect = true; P.mamdani.rate.rates[1] = v.rate; P.mamdani.rate.thresholds[1] = v.threshold;
      P.extra.fairShareAllIncome = v.base === 1;
    },
  },
];
if (typeof module !== "undefined" && module.exports) module.exports = { LEVERS };
