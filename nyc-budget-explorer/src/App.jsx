import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import './App.css'

// ============================================================
// SCROLL FADE-IN HOOK
// ============================================================
function useFadeIn(threshold = 0.15) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.unobserve(el) } },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return [ref, visible]
}

function FadeIn({ children, className = '', delay = 0 }) {
  const [ref, visible] = useFadeIn(0.1)
  return (
    <div ref={ref} className={`fade-in ${visible ? 'visible' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  )
}

// ============================================================
// VITAL CITY PALETTE
// ============================================================
const C = {
  black: '#050507', white: '#ffffff', cloud: '#dddddd',
  chartreuse: '#dde44c', orange: '#ff7c53', periwinkle: '#9b9fbc',
  rose: '#cea9be', magenta: '#e7466d', charcoal: '#707175',
  indigo: '#394882', cerulean: '#217ebe', green: '#3a9e5c',
  warmGray: '#f7f6f3', lightIndigo: '#e8eaf2', slate: '#4a4d55',
  chartreuse80: '#e4e871', chartreuse50: '#edefa8', chartreuse20: '#f7f8dd',
  orange80: '#f69577', orange50: '#fabcaa', magenta80: '#ec6b8a',
  cerulean80: '#4e98cb',
}

const font = "'Helvetica Neue', Arial, sans-serif"
const serif = "Georgia, 'Times New Roman', serif"

// ============================================================
// FY2026 BUDGET DATA — DETAILED
// Sources: NYC Comptroller FY2025 ACFR, Mayor’s FY2027 Preliminary Budget (Feb 2026),
// NYC IBO Fiscal History, CBC, OMB Financial Plan
// ============================================================

const REVENUE = [
  { id: 'property', label: 'Property Tax', amount: 35.3, color: C.indigo,
    desc: 'NYC\'s largest and most stable revenue source. The Council sets the rate annually. The system is notoriously unequal — a brownstone in Park Slope may be taxed at a lower effective rate than a condo in the Bronx.',
    subs: [
      { label: 'Class 1 (1-3 family homes)', amount: 5.6 },
      { label: 'Class 2 (apartments, co-ops, condos)', amount: 15.8 },
      { label: 'Class 3 (utilities)', amount: 1.2 },
      { label: 'Class 4 (commercial/industrial)', amount: 12.7 },
    ]
  },
  { id: 'income', label: 'Personal Income Tax', amount: 18.5, color: C.cerulean,
    desc: 'Highly volatile — swings with Wall Street bonuses and capital gains. The top 1% pay 37–48% of all city income tax, depending on the year. A bad year on Wall Street can blow a $3–4B hole in revenue.',
    subs: [
      { label: 'Withholding (wages/salary)', amount: 12.4 },
      { label: 'Estimated payments (investment income)', amount: 4.2 },
      { label: 'Final returns & other', amount: 1.9 },
    ]
  },
  { id: 'sales', label: 'Sales Tax', amount: 10.1, color: C.orange,
    desc: 'Combined 8.875% rate. Tourism and commuter spending boost this above what residents alone would generate. Clothing under $110 is exempt.',
    subs: [
      { label: 'General sales tax', amount: 8.2 },
      { label: 'Hotel occupancy tax', amount: 0.7 },
      { label: 'Commercial rent tax', amount: 0.9 },
      { label: 'Utility tax', amount: 0.3 },
    ]
  },
  { id: 'corporate', label: 'Business Taxes', amount: 11.0, color: C.magenta,
    desc: 'Taxes on businesses operating in the city. Highly cyclical — surged with Wall Street profits, then retreated. NYC\'s business tax burden is among the highest of any U.S. city.',
    subs: [
      { label: 'General corporation tax', amount: 5.8 },
      { label: 'Unincorporated business tax', amount: 3.6 },
      { label: 'Banking corporation tax', amount: 1.6 },
    ]
  },
  { id: 'other_tax', label: 'Other Taxes', amount: 5.2, color: C.periwinkle,
    desc: 'Real property transfer tax surges during real estate booms and crashes during downturns.',
    subs: [
      { label: 'Real property transfer tax', amount: 1.8 },
      { label: 'Mortgage recording tax', amount: 1.1 },
      { label: 'Cigarette & tobacco taxes', amount: 0.3 },
      { label: 'Other (parking, horse racing, etc.)', amount: 2.0 },
    ]
  },
  { id: 'state_aid', label: 'State Categorical Grants', amount: 19.0, color: C.chartreuse,
    desc: 'Education aid dominates (~$10.5 billion in Foundation Aid plus ~$1.6 billion in other school aid). NYC contributes 55% of state tax revenue but receives only 40% of state operating expenditures. The state caps NYC\'s local Medicaid share at 2015 levels, saving the city ~$4 billion a year — a benefit worth protecting.',
    subs: [
      { label: 'Foundation Aid (school year 2025-26)', amount: 10.5 },
      { label: 'Other school aid (transport, BOCES, etc.)', amount: 1.6 },
      { label: 'Medicaid reimbursement', amount: 3.6 },
      { label: 'Social services & child welfare', amount: 1.8 },
      { label: 'Public health & mental health', amount: 0.7 },
      { label: 'All other state aid', amount: 0.8 },
    ]
  },
  { id: 'federal_aid', label: 'Federal Categorical Grants', amount: 7.4, color: C.green,
    desc: 'Declining sharply as pandemic-era aid expires. Core ongoing funding supports Medicaid, Section 8 vouchers and Title I schools. Trump/DOGE cuts pose a major risk.',
    subs: [
      { label: 'Medicaid (federal share)', amount: 2.6 },
      { label: 'Section 8 housing vouchers', amount: 1.6 },
      { label: 'SNAP & child nutrition admin', amount: 0.7 },
      { label: 'Title I & IDEA (education)', amount: 1.0 },
      { label: 'Community development (CDBG, HOME)', amount: 0.4 },
      { label: 'All other federal grants', amount: 1.1 },
    ]
  },
  { id: 'fees', label: 'Fees, Fines & Miscellaneous', amount: 9.9, color: C.rose,
    desc: 'Water and sewer charges are the biggest component. Also includes permits, licenses, parking meter revenue and interest income.',
    subs: [
      { label: 'Water & sewer charges', amount: 4.5 },
      { label: 'Charges for services & permits', amount: 1.6 },
      { label: 'Fines & forfeitures', amount: 1.0 },
      { label: 'Interest income', amount: 1.2 },
      { label: 'Rental income & asset sales', amount: 0.6 },
      { label: 'Intra-city revenue & other', amount: 1.0 },
    ]
  },
]

const SPENDING = [
  { id: 'education', label: 'Education (DOE)', amount: 34.5, color: C.indigo,
    workers: 150000, personnel: 20.5, otps: 14.0,
    desc: 'The city\'s largest expenditure. Operates ~1,800 schools serving 906,000 students. The DOE expense budget is ~$34.5 billion; all-in per-pupil spending exceeds $43,000 when centrally allocated fringe benefits are included. The class size mandate requires reducing class sizes over 5 years at an estimated cost of $1.3 billion annually when fully phased in.',
    subs: [
      { label: 'Instruction & classroom', amount: 14.5 },
      { label: 'Special education', amount: 6.2 },
      { label: 'School support & administration', amount: 4.2 },
      { label: 'Transportation (school buses)', amount: 3.4 },
      { label: 'School food services', amount: 1.5 },
      { label: 'Pre-K & 3-K programs', amount: 2.8 },
      { label: 'Contractual services & other', amount: 1.9 },
    ]
  },
  { id: 'health', label: 'Health & Hospitals', amount: 13.2, color: C.cerulean,
    workers: 40000, personnel: 8.5, otps: 4.7,
    desc: 'NYC Health + Hospitals runs the largest public health system in the US: 11 acute-care hospitals, 70+ community health centers, more than 1 million patients a year.',
    subs: [
      { label: 'H+H hospital operations', amount: 7.2 },
      { label: 'DOHMH public health programs', amount: 2.4 },
      { label: 'Mental health services', amount: 1.5 },
      { label: 'Health insurance/Medicaid admin', amount: 1.1 },
      { label: 'EMS (health component)', amount: 1.0 },
    ]
  },
  { id: 'social', label: 'Social Services', amount: 12.8, color: C.green,
    workers: 15000, personnel: 3.2, otps: 9.6,
    desc: 'Administers cash assistance, SNAP, Medicaid enrollment and homeless services. NYC operates ~200 homeless shelters housing 100,000+ people nightly — more than any other city.',
    subs: [
      { label: 'Homeless services (DHS shelters)', amount: 4.4 },
      { label: 'Asylum seeker programs', amount: 1.4 },
      { label: 'Cash assistance & emergency aid', amount: 2.0 },
      { label: 'SNAP & WIC administration', amount: 0.8 },
      { label: 'Child welfare (ACS)', amount: 2.2 },
      { label: 'Employment programs & other', amount: 1.5 },
    ]
  },
  { id: 'police', label: 'Police (NYPD)', amount: 5.8, color: C.magenta,
    workers: 55000, personnel: 5.0, otps: 0.8,
    desc: 'The nation\'s largest police force: ~35,000 officers plus ~19,000 civilians. Actual spending consistently exceeds budget by $800 million to $1 billion due to overtime.',
    subs: [
      { label: 'Patrol services', amount: 2.4 },
      { label: 'Detective & investigative', amount: 0.8 },
      { label: 'Overtime (budgeted — actual higher)', amount: 0.7 },
      { label: 'Counterterrorism & intelligence', amount: 0.5 },
      { label: 'School safety division', amount: 0.4 },
      { label: 'Traffic, transit & housing', amount: 0.8 },
      { label: 'Administration & support', amount: 0.6 },
    ]
  },
  { id: 'fire', label: 'Fire & EMS (FDNY)', amount: 2.5, color: C.orange,
    workers: 17000, personnel: 2.1, otps: 0.4,
    desc: 'Operates 218 firehouses and responds to ~1.5 million calls a year. EMS response times have been rising.',
    subs: [
      { label: 'Fire suppression', amount: 1.6 },
      { label: 'Emergency medical services', amount: 0.9 },
      { label: 'Fire prevention & inspection', amount: 0.2 },
      { label: 'Administration & training', amount: 0.4 },
    ]
  },
  { id: 'corrections', label: 'Corrections (DOC)', amount: 3.5, color: C.rose,
    workers: 9300, personnel: 2.8, otps: 0.7,
    desc: 'Runs Rikers Island and borough facilities. Per-detainee cost exceeds $550,000/year — the highest in the nation and 10 times the national average. The DOC budget is ~$1.05 billion, but total criminal justice spending including correctional health, debt service on borough jails, courts and Board of Correction adds to ~$3.5 billion.',
    subs: [
      { label: 'DOC operations & uniformed staff', amount: 1.2 },
      { label: 'Correctional health (H+H)', amount: 0.8 },
      { label: 'Borough-based jails capital/debt', amount: 0.8 },
      { label: 'Overtime (chronically over budget)', amount: 0.4 },
      { label: 'Administration & Board of Correction', amount: 0.3 },
    ]
  },
  { id: 'sanitation', label: 'Sanitation (DSNY)', amount: 1.9, color: C.chartreuse,
    workers: 9500, personnel: 1.2, otps: 0.7,
    desc: 'Collects 12,000+ tons of waste daily. Also handles recycling, street sweeping, snow removal and composting.',
    subs: [
      { label: 'Waste collection', amount: 1.2 },
      { label: 'Street cleaning', amount: 0.4 },
      { label: 'Recycling & composting', amount: 0.3 },
      { label: 'Snow removal & equipment', amount: 0.3 },
      { label: 'Waste disposal/export', amount: 0.2 },
    ]
  },
  { id: 'debt', label: 'Debt Service', amount: 7.2, color: C.charcoal,
    personnel: 0, otps: 7.2,
    desc: 'Interest and principal on ~$110 billion in total outstanding debt (GO bonds ~$47 billion plus TFA ~$63 billion). Net debt service is ~$3.7 billion after prepayments; the $7.2 billion total includes lease-financing, energy adjustments and judgments & claims. A fixed cost — the city must pay or face default.',
    subs: [
      { label: 'GO bond debt service', amount: 3.0 },
      { label: 'TFA Future Tax Secured bonds', amount: 1.6 },
      { label: 'Lease-financing & conduit debt', amount: 1.0 },
      { label: 'Judgments, claims & energy', amount: 1.6 },
    ]
  },
  { id: 'pensions', label: 'Pensions', amount: 10.4, color: C.slate,
    personnel: 0, otps: 10.4,
    desc: 'Employer contributions covering ~330,000 active employees and ~370,000 retirees. Costs grew from $1.5 billion in FY2002 to $10 billion+ today. The single largest structural cost driver.',
    subs: [
      { label: 'Teachers\' Retirement System', amount: 3.4 },
      { label: 'NYC Employees\' Retirement', amount: 2.8 },
      { label: 'Police Pension Fund', amount: 2.1 },
      { label: 'Fire Pension Fund', amount: 1.0 },
      { label: 'Board of Education Retirement', amount: 0.9 },
    ]
  },
  { id: 'other', label: 'All Other & Citywide', amount: 24.1, color: C.periwinkle,
    workers: 45000, personnel: 12.8, otps: 11.3,
    desc: 'Includes 50+ agencies (parks, DOT, HPD, DEP, libraries, courts) plus centrally budgeted fringe benefits — health insurance for ~750,000 current and retired workers (~$9 billion) that is not allocated to individual agency budgets.',
    subs: [
      { label: 'Health insurance (active & retirees)', amount: 9.0 },
      { label: 'Parks & Recreation', amount: 2.0 },
      { label: 'Transportation (DOT)', amount: 1.7 },
      { label: 'Housing Preservation (HPD)', amount: 1.4 },
      { label: 'Environmental Protection (DEP)', amount: 1.3 },
      { label: 'Libraries (3 systems)', amount: 0.8 },
      { label: 'Courts & judiciary', amount: 1.1 },
      { label: 'Citywide admin (OMB, DCAS, Law, OTI)', amount: 2.5 },
      { label: 'All remaining agencies', amount: 4.3 },
    ]
  },
]

const totalRevenue = REVENUE.reduce((s, r) => s + r.amount, 0)
const totalSpending = SPENDING.reduce((s, r) => s + r.amount, 0)
const totalWorkers = SPENDING.reduce((s, r) => s + (r.workers || 0), 0)

// ============================================================
// HISTORICAL DATA
// ============================================================
const HISTORY = [
  // Pre-2000: NYC IBO Fiscal History estimates
  { fy: 1990, total: 28.5, pop: 7.32, gdp: 310, mayor: 'Dinkins' },
  { fy: 1992, total: 30.5, pop: 7.33, gdp: 325, mayor: 'Dinkins' },
  { fy: 1994, total: 31.9, pop: 7.38, gdp: 350, mayor: 'Giuliani' },
  { fy: 1996, total: 33.0, pop: 7.50, gdp: 380, mayor: 'Giuliani' },
  { fy: 1998, total: 34.1, pop: 7.65, gdp: 420, mayor: 'Giuliani' },
  // FY2000–FY2022: Comptroller ACFR actuals; GCP: BEA county-level GDP (5 boroughs)
  { fy: 2000, total: 38.1, pop: 8.01, gdp: 466, mayor: 'Giuliani' },
  { fy: 2002, total: 41.2, pop: 8.04, gdp: 478, mayor: 'Bloomberg' },
  { fy: 2004, total: 47.6, pop: 8.13, gdp: 507, mayor: 'Bloomberg' },
  { fy: 2006, total: 54.4, pop: 8.21, gdp: 586, mayor: 'Bloomberg' },
  { fy: 2008, total: 62.4, pop: 8.31, gdp: 584, mayor: 'Bloomberg' },
  { fy: 2010, total: 63.4, pop: 8.18, gdp: 656, mayor: 'Bloomberg' },
  { fy: 2012, total: 67.5, pop: 8.34, gdp: 736, mayor: 'Bloomberg' },
  { fy: 2014, total: 73.4, pop: 8.47, gdp: 818, mayor: 'de Blasio' },
  { fy: 2016, total: 80.5, pop: 8.54, gdp: 901, mayor: 'de Blasio' },
  { fy: 2018, total: 88.6, pop: 8.40, gdp: 1020, mayor: 'de Blasio' },
  { fy: 2020, total: 95.8, pop: 8.80, gdp: 1052, mayor: 'de Blasio' },
  { fy: 2021, total: 100.6, pop: 8.47, gdp: 1146, mayor: 'de Blasio' },
  { fy: 2022, total: 106.6, pop: 8.34, gdp: 1225, mayor: 'Adams' },
  // FY2023–FY2025: Comptroller adopted budget reports; GCP: BEA
  { fy: 2023, total: 107.8, pop: 8.26, gdp: 1287, mayor: 'Adams' },
  { fy: 2024, total: 105.3, pop: 8.19, gdp: 1378, mayor: 'Adams' },
  { fy: 2025, total: 109.6, pop: 8.10, gdp: 1430, mayor: 'Adams/Mamdani' },
  // FY2026: Mayor’s Preliminary Budget; GCP: BEA trend estimate
  { fy: 2026, total: 115.9, pop: 8.10, gdp: 1480, mayor: 'Mamdani' },
]

const CPI = {
  1990: 2.32, 1992: 2.15, 1994: 2.04, 1996: 1.93, 1998: 1.86, 2000: 1.76,
  2002: 1.68, 2004: 1.58, 2006: 1.47, 2008: 1.36, 2010: 1.32, 2012: 1.26,
  2014: 1.21, 2016: 1.17, 2018: 1.11, 2020: 1.08, 2021: 1.03, 2022: 0.95,
  2023: 0.93, 2024: 0.96, 2025: 0.98, 2026: 1.0,
}

// ============================================================
// CITY COMPARISON — FiSC METHODOLOGY
// ============================================================
const CITIES = [
  { name: 'New York City', abbrev: 'NYC', pop: 8100000, city: 115.9, county: 0, school: 0, countyShare: 1, schoolShare: 1, structure: 'consolidated', fy: 'FY2026',
    notes: 'Consolidated city-county. NYC\'s budget includes K-12 education ($34.5B), public hospitals ($13B), social services ($13B), corrections, and courts — functions other cities fund separately.',
    revMix: { property: 28, income: 15, sales: 9, intergovernmental: 26, other: 22 },
  },
  { name: 'Los Angeles', abbrev: 'LA', pop: 3900000, city: 14.0, county: 47.9, school: 18.8, countyPop: 10000000, schoolShare: 0.75, structure: 'fragmented', fy: 'FY2025-26',
    notes: 'City, LA County, and LAUSD are separate governments. County handles health, social services, courts. LAUSD serves city and 30+ other municipalities.',
    revMix: { property: 32, income: 0, sales: 10, intergovernmental: 30, other: 28 },
  },
  { name: 'Chicago', abbrev: 'CHI', pop: 2700000, city: 18.7, county: 9.94, school: 9.9, countyPop: 5200000, schoolShare: 1.0, structure: 'fragmented', fy: 'FY2025',
    notes: 'City, Cook County, and CPS are separate. No income tax — Illinois preempts it.',
    revMix: { property: 23, income: 0, sales: 14, intergovernmental: 28, other: 35 },
  },
  { name: 'Houston', abbrev: 'HOU', pop: 2300000, city: 6.7, county: 2.67, school: 2.2, countyPop: 4700000, schoolShare: 0.9, structure: 'fragmented', fy: 'FY2025',
    notes: 'Texas has no income tax — city relies on property and sales tax. Much narrower service mandate than NYC.',
    revMix: { property: 35, income: 0, sales: 22, intergovernmental: 18, other: 25 },
  },
  { name: 'Phoenix', abbrev: 'PHX', pop: 1700000, city: 5.0, county: 3.87, school: 3.5, countyPop: 4500000, schoolShare: 0.7, structure: 'fragmented', fy: 'FY2025-26',
    notes: 'Arizona caps local tax authority. City runs water/wastewater as enterprise fund.',
    revMix: { property: 20, income: 0, sales: 25, intergovernmental: 22, other: 33 },
  },
].map(c => {
  const countyShare = c.countyPop ? c.pop / c.countyPop : c.countyShare
  const proCounty = c.county * countyShare
  const proSchool = c.school * c.schoolShare
  const normalized = c.city + proCounty + proSchool
  return { ...c, countyShare, proCounty, proSchool, normalized, rawPC: (c.city * 1e9) / c.pop, normPC: (normalized * 1e9) / c.pop }
})

// ============================================================
// OUTYEAR GAP PROJECTIONS
// ============================================================
const OUTYEAR_GAPS = [
  { fy: 'FY2026', gap: 0, label: 'Adopted (balanced)' },
  { fy: 'FY2027', gap: 5.4, label: 'Preliminary gap' },
  { fy: 'FY2028', gap: 6.7, label: 'Projected' },
  { fy: 'FY2029', gap: 6.8, label: 'Projected' },
  { fy: 'FY2030', gap: 7.1, label: 'Projected' },
]

const RISKS = [
  { label: 'Federal funding cuts (OBBBA)', low: 1000, high: 4000, color: C.magenta, desc: 'The “One Big Beautiful Bill Act” threatens $90–150B in Medicaid cuts to NYS over 10 years. New work requirements (effective 2027) could strip coverage from 500,000 to 1.2 million New Yorkers. Section 8, Title I, SNAP and CDBG also at risk.' },
  { label: 'Labor contract costs', low: 800, high: 2000, color: C.cerulean, desc: 'NYC must negotiate contracts with all major unions. Every 1% raise costs ~$450 million/year. Pattern bargaining suggests 3-4% annual increases.' },
  { label: 'Asylum seeker costs', low: 500, high: 1400, color: C.orange, desc: 'Currently ~$1.4 billion/year in FY2026, down from the FY2024 peak. Could decline further if arrivals slow, or rebound if federal work permits are revoked.' },
  { label: 'Unbudgeted overtime', low: 559, high: 800, color: C.indigo, desc: 'Comptroller estimates $559 million. Historically, NYPD alone exceeds budget by 60-80%.' },
  { label: 'Class size mandate', low: 543, high: 1300, color: C.chartreuse, desc: 'State mandate requires hiring ~6,000 teachers over 5 years. Costs up to $1.3 billion annually when fully phased in.' },
  { label: 'Economic downturn risk', low: 0, high: 4000, color: C.rose, desc: 'A recession could cost $4 billion to $11 billion over two years. Average recession costs NYC ~$5 billion in lost revenue.' },
]

// ============================================================
// BUDGET BALANCER DATA — FY2027
// ============================================================
const BASELINE_GAP = 5400

const REVENUE_OPTIONS = [
  { id: 'pit_millionaire', label: 'Tax millionaires\' income (+2% on $1M+)', amount: 1800, category: 'tax_increase', difficulty: 'hard', desc: 'Raise PIT by ~2 pts on ~33,000 filers earning $1 million+. Requires Albany. The top 1% already pay 37–48% of city income tax depending on market conditions.', source: 'Mayor\'s FY2027 Preliminary Budget', sourceUrl: 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-releases-balanced-fiscal-year-2027-preliminary-bud', risk: 'Could push high earners to relocate. CBC warns economically sensitive taxes already generate ~60% of city revenue.', conflicts: [] },
  { id: 'corporate_tax', label: 'Raise corporate tax on top firms', amount: 1500, category: 'tax_increase', difficulty: 'hard', desc: 'The state Senate\'s one-house budget (March 2026) would authorize NYC to raise corporate taxes: financial sector from 9% to 10.8%, non-finance from 8.85% to 10.62%, plus UBT from 4% to 4.4% on income over $5 million. Requires final passage in Albany by April 1.', source: 'NYS Senate one-house budget (March 10, 2026)', sourceUrl: 'https://www.nysenate.gov/newsroom/press-releases/2026/new-york-state-senate-advances-2026-one-house-budget-resolution', risk: 'Manhattan Chamber warns of competitiveness risk. Requires Albany — and the governor has not endorsed it.', conflicts: [] },
  { id: 'property_tax', label: '9.5% property tax rate increase', amount: 3700, category: 'tax_increase', difficulty: 'medium', desc: 'The fallback in Mamdani\'s preliminary budget. Does NOT require Albany — the Council can do this on its own.', source: 'Mayor\'s FY2027 Preliminary Budget', sourceUrl: 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-releases-balanced-fiscal-year-2027-preliminary-bud', risk: 'Council Speaker Menin called this a “non-starter.” Hits homeowners hard.', conflicts: ['property_tax_half'] },
  { id: 'property_tax_half', label: 'Modest property tax increase (~4.5%)', amount: 1800, category: 'tax_increase', difficulty: 'medium', desc: 'Roughly half the proposed rate hike. More politically viable.', source: 'Author estimate', risk: 'Still hits working and middle-class homeowners.', conflicts: ['property_tax'] },
  { id: 'dof_auditors', label: 'Hire 50 new DOF auditors', amount: 100, category: 'efficiency', difficulty: 'easy', desc: 'Recover revenue from uncollected taxes. Enforcement of existing law, not new taxes.', source: 'Mayor\'s FY2027 Preliminary Budget', sourceUrl: 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-releases-balanced-fiscal-year-2027-preliminary-bud', risk: 'The $100 million projection is unproven.', conflicts: [] },
  { id: 'tort_lawyers', label: 'Add 200 lawyers to cut tort liability', amount: 125, category: 'efficiency', difficulty: 'easy', desc: 'Reduce claims and settlements (the city paid $1.9 billion in FY2024) with more legal staff.', source: 'Mayor\'s FY2027 Preliminary Budget', sourceUrl: 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-releases-balanced-fiscal-year-2027-preliminary-bud', risk: 'Savings projected, not guaranteed.', conflicts: [] },
  { id: 'parking_meters', label: 'Meter or auction free curb parking spaces', amount: 1500, category: 'new_revenue', difficulty: 'medium', desc: 'Only ~3% of NYC\'s curb spaces are metered. The Manhattan Institute estimates average revenue of ~$2,000–5,000 per space a year; City Journal modeled auctioning all curb space at $3.7 billion gross (~$2.9 billion net new). Mamdani\'s administration has signaled openness to a major expansion. Does not require Albany if structured as a municipal fee.', source: 'Manhattan Institute; Center for an Urban Future; CNBC (Mar 14, 2026)', sourceUrl: 'https://manhattan.institute/article/the-right-price-for-curb-parking', risk: 'Free residential parking is a deeply ingrained expectation. Politically explosive in car-dependent outer boroughs — but the subsidy is indefensible on fiscal or urbanist grounds.', conflicts: [] },
  { id: 'pied_a_terre', label: 'Pied-à-terre tax on luxury second homes', amount: 400, category: 'tax_increase', difficulty: 'hard', desc: 'Annual surcharge on non-primary residences valued above $5 million. An estimated 10,000+ luxury units in Manhattan are used as pieds-à-terre, removing them from the housing supply while consuming city services. Was estimated at $390–650M in 2019 proposals before being shelved. Requires Albany.', source: 'State Senate proposals; Fiscal Policy Institute', sourceUrl: 'https://fiscalpolicy.org/', risk: 'Real estate lobby has killed this repeatedly in Albany. Definitional issues (who counts as non-resident?) complicate enforcement.', conflicts: [] },
  { id: 'mansion_tax', label: 'Expand the mansion tax (+1.4 pts on $5 million+ sales)', amount: 320, category: 'tax_increase', difficulty: 'hard', desc: 'Raise transfer tax rates by ~1.4 percentage points on residential sales above $5 million. Both the Senate and Assembly included versions in their one-house budgets.', source: 'NYS Senate & Assembly one-house budgets (March 2026)', sourceUrl: 'https://gothamist.com/news/ny-lawmakers-back-mamdani-push-to-tax-the-rich-setting-up-clash-with-hochul', risk: 'Depresses high-end sales volume. Real estate lobby opposition. Requires Albany.', conflicts: [] },
  { id: 'gold_tax', label: 'Tax gold bar & precious metals sales', amount: 300, category: 'tax_increase', difficulty: 'hard', desc: 'Scrap the existing sales-tax exemption on gold bars and precious metals. Currently untaxed despite being an investment vehicle overwhelmingly used by the wealthy. Included in the Senate one-house budget.', source: 'NYS Senate one-house budget (March 2026)', sourceUrl: 'https://nysfocus.com/2026/03/10/senate-assembly-mamdani-tax-hikes', risk: 'Gold dealers may relocate transactions out of state. Novel — no precedent for enforcement.', conflicts: [] },
  { id: 'commercial_vacancy', label: 'Commercial vacancy tax', amount: 200, category: 'tax_increase', difficulty: 'hard', desc: 'Tax landlords who keep ground-floor retail space vacant for extended periods. An estimated 12,000+ storefronts sit empty citywide. State bill S6804/A669 would impose 1% of assessed value on spaces vacant 6+ months.', source: 'NYS Senate (S6804)', sourceUrl: 'https://www.nysenate.gov/legislation/bills/2025/S6804', risk: 'Landlords argue vacancy is driven by high property taxes and regulations, not speculation. May accelerate conversions.', conflicts: [] },
  { id: 'parks_concessions', label: 'Expand parks concessions & sponsorships', amount: 150, category: 'new_revenue', difficulty: 'easy', desc: 'NYC parks generate relatively little commercial revenue compared to peer cities. Expanding naming rights, concession contracts and event permitting could add significant revenue with dedicated funding for park maintenance.', source: 'Center for an Urban Future (2026)', sourceUrl: 'https://www.nycfuture.org/research/5-revenue-raising-ideas-for-nyc', risk: 'Equity concerns — wealthier parks would benefit more. Risk of over-commercialization.', conflicts: [] },
]

const SPENDING_OPTIONS = [
  { id: 'class_size', label: 'Seek state relief from class size mandate', amount: 1300, category: 'education', difficulty: 'hard', desc: 'CBC\'s top recommendation. Save up to $1.3 billion otherwise spent hiring ~6,000 teachers.', source: 'CBC; Chalkbeat', sourceUrl: 'https://www.chalkbeat.org/newyork/2026/02/17/nyc-mamdani-preliminary-budget-class-size-funding-school-program-cuts/', risk: 'Parents and unions support smaller classes. Requires Albany.', conflicts: [] },
  { id: 'enrollment', label: 'Adjust DOE funding for declining enrollment', amount: 400, category: 'education', difficulty: 'medium', desc: 'NYC public school enrollment has declined by ~120,000 students since pre-pandemic.', source: 'CBC “False Choice” (March 2026)', sourceUrl: 'https://cbcny.org/research/false-choice', risk: 'Would require closing or consolidating schools.', conflicts: [] },
  { id: 'cso_savings', label: 'Agency Chief Savings Officers (2.5%)', amount: 1770, category: 'efficiency', difficulty: 'medium', desc: 'Mamdani\'s EO 12 requires every agency to target 2.5% savings. $1.77 billion total.', source: 'Mayor\'s FY2027 Preliminary Budget', sourceUrl: 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-releases-balanced-fiscal-year-2027-preliminary-bud', risk: 'CBC: There\'s much more to be saved. But this is a target, not a plan.', conflicts: ['cso_half'] },
  { id: 'cso_half', label: 'Agency savings (conservative estimate)', amount: 900, category: 'efficiency', difficulty: 'medium', desc: 'Half the administration\'s target — what might actually materialize.', source: 'Author estimate', risk: 'Even this may be optimistic without concrete operational changes.', conflicts: ['cso_savings'] },
  { id: 'overtime', label: 'Reduce uniformed overtime spending', amount: 300, category: 'uniformed', difficulty: 'hard', desc: 'Comptroller estimates $559 million in unbudgeted overtime. NYPD alone exceeds by 60-80%.', source: 'Comptroller FY2027 Budget Preview', sourceUrl: 'https://comptroller.nyc.gov/newsroom/comptroller-levine-projects-2-2-billion-budget-shortfall-in-fiscal-year-2026-and-10-4-billion-in-fiscal-year-2027/', risk: 'Overtime reform has failed repeatedly.', conflicts: [] },
  { id: 'procurement', label: 'Procurement and contract reform', amount: 400, category: 'efficiency', difficulty: 'medium', desc: 'City registered $32 billion+ in contracts in FY2024 alone. Documented waste and cost overruns in CBC and Comptroller reports.', source: 'CBC; NYC Comptroller', sourceUrl: 'https://comptroller.nyc.gov/reports/annual-summary-contracts-report-for-the-city-of-new-york-fiscal-year-2024/', risk: 'Reform is slow. Savings may not materialize in a single fiscal year.', conflicts: [] },
  { id: 'vacancies', label: 'Reduce funded vacancies and headcount', amount: 600, category: 'efficiency', difficulty: 'easy', desc: '~5.8% vacancy rate against funded positions. 2-for-1 hiring freeze already in effect.', source: 'Comptroller FY2026 Comments', sourceUrl: 'https://comptroller.nyc.gov/reports/comments-on-new-york-citys-fiscal-year-2025-adopted-budget/', risk: 'Services may degrade. Some vacancies are in hard-to-fill roles.', conflicts: [] },
  { id: 'health_ins', label: 'Self-funded employee health plan', amount: 500, category: 'labor', difficulty: 'hard', desc: 'Replace the City\'s second premium-free plan with a self-funded option.', source: 'Comptroller; CBC', sourceUrl: 'https://cbcny.org/research/what-opeb-and-why-does-it-cost-94-billion', risk: 'Faces legal challenges from municipal unions.', conflicts: [] },
  { id: 'welfare_funds', label: 'Consolidate union welfare funds', amount: 200, category: 'labor', difficulty: 'hard', desc: 'CBC recommends consolidating fragmented union welfare/benefit funds.', source: 'CBC “False Choice” (March 2026)', sourceUrl: 'https://cbcny.org/research/false-choice', risk: 'Requires union cooperation. Strong labor opposition.', conflicts: [] },
]

const RESERVE_OPTIONS = [
  { id: 'rainy_day', label: 'Draw from Rainy Day Fund', amount: 980, category: 'reserves', difficulty: 'medium', desc: 'Fund held ~$2 billion. The CBC says this depletes funds meant for recession.', source: 'Mayor\'s Preliminary Budget; CBC', sourceUrl: 'https://cbcny.org/research/false-choice', risk: 'Leaves city highly vulnerable to recession.', isOneTime: true, conflicts: [] },
  { id: 'rhbt', label: 'Draw from Retiree Health Trust', amount: 229, category: 'reserves', difficulty: 'easy', desc: 'Draw $229 million from retiree health benefit trust in FY2027.', source: 'Mayor\'s FY2027 Preliminary Budget', sourceUrl: 'https://www.nyc.gov/mayors-office/news/2026/02/mayor-mamdani-releases-balanced-fiscal-year-2027-preliminary-bud', risk: 'Pushes retiree health liabilities to the future.', isOneTime: true, conflicts: [] },
]

const ALL_OPTIONS = [...REVENUE_OPTIONS, ...SPENDING_OPTIONS, ...RESERVE_OPTIONS]

// ============================================================
// UTILITIES
// ============================================================
const fmt = n => '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 })
const fmtB = n => '$' + n.toFixed(1) + 'B'
const fmtM = m => Math.abs(m) >= 1000 ? `$${(m / 1000).toFixed(1)}B` : `$${m}M`

// ============================================================
// SHARED COMPONENTS
// ============================================================

function Source({ children }) {
  return <div className="source-line">Source: {children}</div>
}

function WaffleChart({ data, total, hoveredId, onHover }) {
  const cells = 100
  const cols = 10
  const cellSize = 28
  const gap = 3
  const w = cols * (cellSize + gap) - gap
  const rows = Math.ceil(cells / cols)
  const h = rows * (cellSize + gap) - gap

  const assignments = []
  let remaining = cells
  const sorted = [...data].sort((a, b) => b.amount - a.amount)
  sorted.forEach((item, i) => {
    const share = item.amount / total
    const count = i === sorted.length - 1 ? remaining : Math.round(share * cells)
    for (let j = 0; j < count && assignments.length < cells; j++) {
      assignments.push(item)
    }
    remaining -= count
  })

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      {assignments.map((item, i) => {
        const col = i % cols
        const row = Math.floor(i / cols)
        const x = col * (cellSize + gap)
        const y = row * (cellSize + gap)
        const isFaded = hoveredId && hoveredId !== item.id
        return (
          <rect key={i} x={x} y={y} width={cellSize} height={cellSize} rx={3}
            fill={item.color} opacity={isFaded ? 0.15 : 1}
            style={{ transition: 'opacity 0.2s', cursor: 'pointer' }}
            onMouseEnter={() => onHover(item.id)} onMouseLeave={() => onHover(null)}
          />
        )
      })}
    </svg>
  )
}

// ============================================================
// ACT 1: THE SCALE
// ============================================================

function ActScale() {
  const [hovered, setHovered] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [showRevenue, setShowRevenue] = useState(false)
  const data = showRevenue ? REVENUE : SPENDING
  const total = showRevenue ? totalRevenue : totalSpending

  const spendingPS = SPENDING.reduce((s, r) => s + (r.personnel || 0), 0)
  const spendingOTPS = SPENDING.reduce((s, r) => s + (r.otps || 0), 0)

  const perResident = Math.round((totalSpending * 1e9) / 8100000)
  const perHousehold = Math.round(perResident * 2.5)
  const [countRef, countVal] = useCountUp(totalSpending * 1e9)

  return (
    <>
      {/* Hero number */}
      <div className="hero" id="act-scale">
        <div className="content-w">
          <div ref={countRef}>
            <FadeIn>
              <div className="hero-number">${Math.round(countVal).toLocaleString('en-US')}</div>
            </FadeIn>
          </div>
          <FadeIn delay={200}>
            <div className="hero-context">
              That’s New York City’s expense budget for fiscal year 2026 — the operating spending that pays for daily services, from schools to policing to sanitation. It’s <strong>larger than the budgets of 46 states</strong>.
              A separate ~$16 billion capital budget funds long-term infrastructure like roads, bridges, and new school buildings, mostly financed through bonds.
            </div>
          </FadeIn>
          <FadeIn delay={400}>
            <div className="hero-personal">
              <div className="personal-stat">
                <span className="personal-val">{fmt(perResident)}</span>
                <span className="personal-lbl">per resident</span>
              </div>
              <div className="personal-divider" />
              <div className="personal-stat">
                <span className="personal-val">{fmt(perHousehold)}</span>
                <span className="personal-lbl">per household</span>
              </div>
              <div className="personal-divider" />
              <div className="personal-stat">
                <span className="personal-val">{fmt(Math.round(totalSpending * 1e9 / 365 / 1e6))}M</span>
                <span className="personal-lbl">per day</span>
              </div>
            </div>
          </FadeIn>
        </div>
      </div>

      {/* The ledger */}
      <div className="act act--white">
        <div className="content-w">
          <FadeIn>
            <div className="act-number">The Ledger</div>
            <h2 className="act-headline">Every dollar in, every dollar out</h2>
            <p className="act-sub">Tap any category to see where exactly the money goes — and what it pays for.</p>
          </FadeIn>

          <div className="toggle-row">
            <button className={`toggle-btn ${!showRevenue ? 'active' : ''}`} onClick={() => { setShowRevenue(false); setExpanded(null) }}>Spending</button>
            <button className={`toggle-btn ${showRevenue ? 'active' : ''}`} onClick={() => { setShowRevenue(true); setExpanded(null) }}>Revenue</button>
          </div>

          <div className="waffle-section">
            <div className="waffle-layout">
              <div className="waffle-chart-wrap">
                <WaffleChart data={data} total={total} hoveredId={hovered} onHover={setHovered} />
                <div className="waffle-note">Each square = ~{fmtB(total / 100)}</div>
              </div>
              <div className="waffle-legend">
                {data.map(item => {
                  const pct = ((item.amount / total) * 100).toFixed(1)
                  const isActive = hovered === item.id
                  const isExpanded = expanded === item.id
                  return (
                    <div key={item.id}>
                      <div
                        className={`legend-row ${isActive ? 'active' : ''} ${hovered && !isActive ? 'faded' : ''}`}
                        onMouseEnter={() => setHovered(item.id)}
                        onMouseLeave={() => setHovered(null)}
                        onClick={() => setExpanded(isExpanded ? null : item.id)}
                      >
                        <span className="legend-swatch" style={{ background: item.color }} />
                        <div className="legend-text">
                          <div className="legend-label">
                            {item.label}
                            <span className="legend-arrow">{isExpanded ? '\u25B2' : '\u25BC'}</span>
                          </div>
                          <div className="legend-values">
                            <strong>{fmtB(item.amount)}</strong>
                            <span className="legend-pct">{pct}%</span>
                          </div>
                        </div>
                      </div>
                      {isExpanded && (
                        <div className="legend-expanded">
                          <p className="legend-desc">{item.desc}</p>
                          {item.personnel !== undefined && item.personnel > 0 && (
                            <div style={{ margin: '8px 0' }}>
                              <div style={{ display: 'flex', height: 10, borderRadius: 5, overflow: 'hidden', marginBottom: 3 }}>
                                <div style={{ width: `${(item.personnel / item.amount) * 100}%`, background: item.color, opacity: 0.8 }} />
                                <div style={{ width: `${(item.otps / item.amount) * 100}%`, background: item.color, opacity: 0.4 }} />
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: C.charcoal }}>
                                <span>Personnel: {fmtB(item.personnel)}</span>
                                <span>OTPS: {fmtB(item.otps)}</span>
                              </div>
                            </div>
                          )}
                          {item.subs && (
                            <div className="sub-breakdown">
                              {item.subs.map((sub, i) => (
                                <div key={i} className="sub-row">
                                  <div className="sub-bar-track">
                                    <div className="sub-bar" style={{
                                      width: `${(sub.amount / item.amount) * 100}%`,
                                      background: item.color,
                                      opacity: 0.6 + (sub.amount / item.amount) * 0.4,
                                    }} />
                                  </div>
                                  <span className="sub-label">{sub.label}</span>
                                  <span className="sub-amount">{fmtB(sub.amount)}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* PS vs OTPS */}
          {!showRevenue && (
            <FadeIn>
              <h3 className="chart-head">Half the budget pays people</h3>
              <p className="chart-sub">The city’s {(totalWorkers / 1000).toFixed(0)}K+ employees make it the largest municipal workforce in the US. If they were a city, they’d be America’s 35th-largest.</p>
              <div className="ps-bar-wrap">
                <div className="ps-bar">
                  <div className="ps-segment" style={{ width: `${(spendingPS / totalSpending) * 100}%`, background: C.indigo }}>
                    <span className="ps-label" style={{ color: C.white }}>Personnel</span>
                    <span className="ps-amount" style={{ color: C.white }}>{fmtB(spendingPS)}</span>
                  </div>
                  <div className="ps-segment" style={{ width: `${(spendingOTPS / totalSpending) * 100}%`, background: C.cerulean }}>
                    <span className="ps-label" style={{ color: C.white }}>OTPS</span>
                    <span className="ps-amount" style={{ color: C.white }}>{fmtB(spendingOTPS)}</span>
                  </div>
                </div>
              </div>
            </FadeIn>
          )}

          <div className="insight-box">
            <div className="insight-label">Beyond the annual budget</div>
            <p>
              The city also carries ~$110 billion in outstanding debt (GO bonds + TFA), more than $100 billion in unfunded retiree health obligations alone,
              and billions in deferred infrastructure maintenance. City-funded spending has grown from $60 billion to nearly $96 billion in
              a decade — <span className="hl">$16 billion above what inflation alone would explain</span>.
            </p>
          </div>

          <Source>NYC Comptroller FY2025 ACFR; Mayor’s FY2027 Preliminary Budget (Feb 2026); NYC IBO; CBC</Source>
        </div>
      </div>
    </>
  )
}


// ============================================================
// ACT 2: HOW WE GOT HERE
// ============================================================

function ActHistory() {
  const [mode, setMode] = useState('nominal')
  const [compView, setCompView] = useState('raw')
  const modes = [
    { id: 'nominal', label: 'Nominal $' },
    { id: 'real', label: 'Inflation-adjusted' },
    { id: 'percapita', label: 'Per capita (real)' },
    { id: 'gdpshare', label: '% of GDP' },
  ]

  const chartData = useMemo(() => {
    return HISTORY.map(d => {
      const cpi = CPI[d.fy] || 1
      const real = d.total * cpi
      const realPC = (real * 1e9) / (d.pop * 1e6)
      const gdpShare = (d.total / d.gdp) * 100
      let value
      switch (mode) {
        case 'real': value = real; break
        case 'percapita': value = realPC; break
        case 'gdpshare': value = gdpShare; break
        default: value = d.total
      }
      return { ...d, value, real, realPC, gdpShare }
    })
  }, [mode])

  const maxVal = Math.max(...chartData.map(d => d.value))
  const minVal = 0

  const W = 680, H = 320, padL = 60, padR = 50, padT = 20, padB = 50
  const chartW = W - padL - padR
  const chartH = H - padT - padB

  const xScale = (fy) => padL + ((fy - 1990) / (2026 - 1990)) * chartW
  const yScale = (v) => padT + chartH - ((v - minVal) / (maxVal - minVal)) * chartH

  const linePath = chartData.map((d, i) => `${i === 0 ? 'M' : 'L'}${xScale(d.fy).toFixed(1)},${yScale(d.value).toFixed(1)}`).join(' ')
  const areaPath = linePath + ` L${xScale(chartData[chartData.length - 1].fy)},${yScale(0)} L${xScale(1990)},${yScale(0)} Z`

  const transitions = [
    { fy: 1994, label: 'Giuliani' }, { fy: 2002, label: 'Bloomberg' },
    { fy: 2014, label: 'de Blasio' }, { fy: 2022, label: 'Adams' }, { fy: 2025.5, label: 'Mamdani' },
  ]

  const formatValue = (v) => {
    if (mode === 'percapita') return fmt(Math.round(v))
    if (mode === 'gdpshare') return v.toFixed(1) + '%'
    return fmtB(v)
  }

  const yLabels = (() => {
    const range = maxVal - minVal
    const step = range > 100 ? Math.ceil(range / 5 / 10) * 10 : range > 20 ? Math.ceil(range / 5 / 5) * 5 : Math.ceil(range / 5)
    const labels = []
    for (let v = Math.ceil(minVal / step) * step; v <= maxVal; v += step) labels.push(v)
    return labels
  })()

  const headlines = {
    nominal: 'The budget has quadrupled in 35 years',
    real: 'Even adjusting for inflation, spending is 75% higher than in 1990',
    percapita: 'Per person, the city spends nearly 60% more than in 1990',
    gdpshare: 'City government now claims nearly 8 cents of every dollar the local economy produces',
  }

  // City comparison
  const maxNorm = Math.max(...CITIES.map(c => c.normPC))
  const maxRaw = Math.max(...CITIES.map(c => c.rawPC))
  const sortedCities = compView === 'normalized'
    ? [...CITIES].sort((a, b) => b.normPC - a.normPC)
    : [...CITIES].sort((a, b) => b.rawPC - a.rawPC)
  const maxCompVal = compView === 'normalized' ? maxNorm : maxRaw

  return (
    <div className="act act--cloud" id="act-history">
      <div className="content-w">
        <FadeIn>
          <div className="act-number">Over Time</div>
          <h2 className="act-headline">{headlines[mode]}</h2>
        </FadeIn>
        <p className="act-sub">
          {mode === 'nominal' && 'Total city expenditures, FY1990–FY2026'}
          {mode === 'real' && 'Adjusted to 2026 dollars using CPI-U'}
          {mode === 'percapita' && 'Real spending per resident, 2026 dollars'}
          {mode === 'gdpshare' && 'City budget as a percentage of NYC gross city product'}
        </p>

        <div className="toggle-row">
          {modes.map(m => (
            <button key={m.id} className={`toggle-btn ${mode === m.id ? 'active' : ''}`} onClick={() => setMode(m.id)}>{m.label}</button>
          ))}
        </div>

        <div className="chart-wrap">
          <svg viewBox={`0 0 ${W} ${H}`}>
            {yLabels.map(v => (
              <g key={v}>
                <line x1={padL} x2={W - padR} y1={yScale(v)} y2={yScale(v)} stroke={C.cloud} strokeWidth={0.5} />
                <text x={padL - 8} y={yScale(v) + 4} textAnchor="end" fill={C.charcoal} fontSize={11} fontFamily={font}>{formatValue(v)}</text>
              </g>
            ))}
            {chartData.filter(d => d.fy % 4 === 0 || d.fy === 2026).map(d => (
              <text key={d.fy} x={xScale(d.fy)} y={H - 10} textAnchor="middle" fill={C.charcoal} fontSize={11} fontFamily={font}>{d.fy}</text>
            ))}
            {transitions.map(t => (
              <g key={t.label}>
                <line x1={xScale(t.fy)} x2={xScale(t.fy)} y1={padT} y2={padT + chartH} stroke={C.cloud} strokeWidth={1} strokeDasharray="3,3" />
                <text x={xScale(t.fy) + 3} y={padT + 12} fill={C.charcoal} fontSize={9} fontFamily={font} opacity={0.7}>{t.label}</text>
              </g>
            ))}
            <line x1={xScale(2020)} x2={xScale(2020)} y1={padT} y2={padT + chartH} stroke={C.magenta} strokeWidth={1} strokeDasharray="4,3" opacity={0.5} />
            <text x={xScale(2020) + 3} y={padT + chartH - 5} fill={C.magenta} fontSize={9} fontFamily={font} opacity={0.7}>COVID</text>
            <path d={areaPath} fill={C.chartreuse} opacity={0.15} />
            <path d={linePath} fill="none" stroke={C.orange} strokeWidth={2.5} strokeLinejoin="round" />
            {chartData.map(d => (
              <circle key={d.fy} cx={xScale(d.fy)} cy={yScale(d.value)} r={3} fill={C.orange} />
            ))}
            <text x={xScale(chartData[chartData.length - 1].fy) + 6} y={yScale(chartData[chartData.length - 1].value) + 4}
              fill={C.orange} fontSize={13} fontWeight={700} fontFamily={font}>
              {formatValue(chartData[chartData.length - 1].value)}
            </text>
          </svg>
        </div>

        <Source>NYC IBO Fiscal History; Comptroller ACFRs; BLS CPI-U</Source>

        <hr className="divider" />

        {/* City comparison */}
        <FadeIn>
          <div className="act-number" style={{ marginTop: 8 }}>vs. Other Cities</div>
          <h2 className="chart-head">
            {compView === 'normalized'
              ? 'When you add schools, hospitals, and courts, NYC isn\'t the outlier you think'
              : 'NYC\'s budget dwarfs other cities — but raw numbers are deeply misleading'}
          </h2>
          <p className="chart-sub">
          Per-capita government spending across the 5 largest US cities, using Lincoln Institute FiSC methodology to
          normalize for what each city government actually does.
        </p>
        </FadeIn>

        <div className="toggle-row">
          <button className={`toggle-btn ${compView === 'raw' ? 'active' : ''}`} onClick={() => setCompView('raw')}>City budget only</button>
          <button className={`toggle-btn ${compView === 'normalized' ? 'active' : ''}`} onClick={() => setCompView('normalized')}>FiSC normalized</button>
        </div>

        <div className="comp-chart">
          {sortedCities.map(city => {
            const val = compView === 'normalized' ? city.normPC : city.rawPC
            const isNYC = city.abbrev === 'NYC'
            return (
              <div key={city.abbrev} className="comp-row">
                <div className={`comp-city ${isNYC ? 'highlight' : ''}`}>{city.name}</div>
                <div className="comp-bar-track">
                  <div className="comp-bar" style={{
                    width: `${(val / maxCompVal) * 100}%`,
                    background: isNYC ? C.magenta : C.cerulean,
                  }} />
                </div>
                <div className="comp-val">{fmt(Math.round(val))}</div>
              </div>
            )
          })}
        </div>

        <FadeIn>
        <div className="insight-box">
          <div className="insight-label">Why this matters</div>
          <p>
            {compView === 'normalized'
              ? 'Once you normalize for all the functions NYC handles — K-12 education, public hospitals, social services, courts — its per-capita spending is still higher than peer cities, but far less dramatically. The gap narrows from 4-to-1 to roughly 1.4-to-1 vs. Chicago.'
              : 'NYC runs schools, hospitals, social services, and courts that other cities fund through separate county or school district budgets. Comparing NYC\'s $116 billion to Houston\'s $7B is like comparing a supermarket to a bodega — they\'re selling different things.'}
          </p>
        </div>
        </FadeIn>

        <Source>Lincoln Institute of Land Policy FiSC; city/county adopted budgets (FY2025)</Source>
      </div>
    </div>
  )
}


// ============================================================
// ACT 3: THE CLIFF
// ============================================================

function ActCliff() {
  const maxGap = Math.max(...OUTYEAR_GAPS.map(g => g.gap))
  const maxRisk = Math.max(...RISKS.map(r => r.high))

  return (
    <div className="act act--dark" id="act-cliff">
      <div className="content-w">
        <FadeIn>
          <div className="act-number">The Challenge</div>
          <h2 className="act-headline" style={{ color: C.white }}>
            The budget is balanced today. In twelve months, there’s a $5.4 billion hole.
          </h2>
        </FadeIn>
        <p className="act-sub">
          New York City is required by law to adopt a balanced budget every year — a rule imposed after the 1975 fiscal crisis, when the city nearly went bankrupt and the state created the Financial Control Board to oversee its finances. The FCB still exists today.
        </p>
        <p className="act-sub">
          That’s the mayor’s number. Comptroller Levine projects a combined <strong style={{ color: C.orange }}>$10.4 billion shortfall</strong> across
          FY2026–27 — the worst since the Great Recession. The Citizens Budget Commission’s "False Choice" report (March 2026) pegs it at <strong style={{ color: C.orange }}>$9.4 billion</strong>.
          But the Council found $1.7 billion in resources the administration missed, arguing the Rainy Day Fund doesn’t need to be tapped at all.
        </p>

        {/* Gap bars */}
        <FadeIn delay={150}>
        <div className="gap-visual">
          <div className="gap-bars">
            {OUTYEAR_GAPS.map(g => (
              <div key={g.fy} className="gap-bar-col">
                <div className="gap-bar-label">{g.fy}</div>
                <div className="gap-bar" style={{
                  height: g.gap === 0 ? 4 : (g.gap / maxGap) * 180,
                  background: g.gap === 0 ? C.periwinkle : C.orange,
                  opacity: g.gap === 0 ? 0.3 : 1,
                }} />
                <div className="gap-bar-val" style={{ color: g.gap === 0 ? C.periwinkle : C.orange }}>
                  {g.gap === 0 ? '—' : fmtB(g.gap)}
                </div>
              </div>
            ))}
          </div>
        </div>
        </FadeIn>

        <FadeIn>
        <h3 className="chart-head" style={{ color: C.white, marginTop: 36 }}>Mamdani’s opening gambit</h3>
        <p className="prose">
          Mamdani’s February 2026 preliminary budget was his first major fiscal test.
          The plan proposes <strong style={{ color: C.chartreuse }}>$3.7 billion in new property taxes</strong> (a 9.5% rate increase),
          a <strong style={{ color: C.chartreuse }}>millionaire income tax surcharge</strong> requiring Albany approval,
          and <strong style={{ color: C.chartreuse }}>$1.77 billion in agency savings</strong> through Executive Order 12,
          which installed Chief Savings Officers in every city agency with a mandate to find 2.5% cuts.
        </p>
        <p className="prose">
          The plan also draws down <strong style={{ color: C.chartreuse }}>$980 million from the Rainy Day Fund</strong> and
          $229 million from the Retiree Health Benefits Trust — one-time money that won’t be there next year. City Council Speaker
          Julie Menin immediately called the property tax hike a "non-starter" and released the Council’s own fiscal analysis showing
          <strong style={{ color: C.chartreuse }}>$1.7 billion in unrecognized resources</strong> — from higher-than-projected
          tax revenue, debt service savings, unfilled vacancies, and unrecognized interest earnings — arguing the Rainy Day Fund
          doesn’t need to be tapped at all. The CBC called the savings targets aspirational, not operational.
          And all of it assumes Albany cooperates on the income tax — during an election year.
        </p>
        </FadeIn>

        <FadeIn>
        <div className="insight-box dark">
          <div className="insight-label">Credit watch</div>
          <p>
            In March 2026, <span className="hl" style={{ color: C.chartreuse }}>three of four rating agencies revised NYC’s credit outlook to negative</span>:
            Moody’s on March 11, S&P warning two days later, then Fitch and KBRA on March 20. The agencies cited structural
            budget gaps, reliance on one-time revenues, and an uncertain path to balance. Days later, the city went to market
            with a <strong>$2.65 billion bond sale</strong> under these conditions. A full downgrade would raise borrowing costs on
            the city’s ~$110 billion in outstanding debt — every basis point costs taxpayers roughly $4.7 million per year.
          </p>
        </div>
        </FadeIn>

        <p className="prose" style={{ marginTop: 24 }}>
          <strong style={{ color: C.white }}>These gaps are projections, not certainties.</strong> They assume current tax
          rates, current service levels, and current labor costs. But each line item carries its own risk — and
          the risks are piling up.
        </p>

        {/* Risk range chart */}
        <FadeIn>
        <h3 className="chart-head" style={{ color: C.white, marginTop: 36 }}>The risks that keep budget wonks up at night</h3>
        <p className="chart-sub">Estimated additional costs beyond what’s already budgeted. Ranges reflect uncertainty.</p>

        <div className="risk-chart">
          {RISKS.map(r => {
            const barLeft = (r.low / maxRisk) * 100
            const barWidth = ((r.high - r.low) / maxRisk) * 100
            return (
              <div key={r.label} className="risk-row">
                <div className="risk-label">{r.label}</div>
                <div className="risk-bar-track">
                  <div className="risk-bar" style={{
                    left: `${barLeft}%`,
                    width: `${Math.max(barWidth, 1)}%`,
                    background: r.color,
                    opacity: 0.8,
                  }} />
                </div>
                <div className="risk-val">{fmtM(r.low)}–{fmtM(r.high)}</div>
              </div>
            )
          })}
        </div>
        </FadeIn>

        <FadeIn>
        <div className="insight-box dark">
          <div className="insight-label">The Albany arithmetic</div>
          <p>
            More than <span className="hl" style={{ color: C.chartreuse }}>a quarter of the city’s budget — $26.5 billion — comes from state and federal aid</span>.
            NYC sends far more to Albany than it gets back: the city generates 55% of state tax revenue but receives only 40% of state
            operating expenditures. Foundation Aid, the single largest state grant at $10.5 billion, was increased this year — but a
            formula revision in May 2025 cost the city <span className="hl" style={{ color: C.chartreuse }}>$314 million</span> relative
            to the old calculation. The state Medicaid cap, which freezes NYC’s local share at 2015 levels, saves the city roughly
            $4 billion annually — cumulative savings of nearly $54 billion since FY2016. If that cap were ever lifted,
            it would dwarf every other budget risk combined.
          </p>
          <p style={{ marginTop: 10 }}>
            Meanwhile, the federal "One Big Beautiful Bill Act," signed into law in July 2025, threatens <span className="hl" style={{ color: C.chartreuse }}>$90 billion to $150 billion in Medicaid cuts to New York State</span> over
            ten years. New work requirements taking effect in 2027 could strip coverage from 500,000 to 1.2 million New Yorkers. The state Senate’s
            one-house budget (March 10, 2026) would authorize NYC to raise corporate taxes by up to <span className="hl" style={{ color: C.chartreuse }}>$1.75 billion</span> ($1.5 billion corporate + $250 million UBT) — but that requires final passage by the April 1 deadline and the governor has not endorsed it.
          </p>
        </div>
        </FadeIn>

        <Source>Comptroller FY2027 Budget Preview (March 2026); OMB Financial Plan; CBC "False Choice" (March 2026); City Council Economic Forecast (March 10, 2026); Moody’s; Fitch; KBRA; CUNY ISLG Fiscal Flow Report; NYS Senate one-house budget; Fiscal Policy Institute</Source>
      </div>
    </div>
  )
}


// ============================================================
// ACT: THE IDEAS ON THE TABLE — expert proposals + labor costs
// ============================================================

function ActProposals() {
  const totalPS = SPENDING.reduce((s, r) => s + (r.personnel || 0), 0)
  const totalOTPS = SPENDING.reduce((s, r) => s + (r.otps || 0), 0)
  const psPct = ((totalPS / totalSpending) * 100).toFixed(0)

  return (
    <div className="act act--cloud" id="act-proposals">
      <div className="content-w">
        <FadeIn>
          <div className="act-number">The Ideas</div>
          <h2 className="act-headline">Before you try to close the gap, here’s what the experts are proposing</h2>
        </FadeIn>
        <p className="act-sub">
          The mayor, the comptroller, the Citizens Budget Commission, and the City Council all have plans. They overlap in some places, clash in others. Understanding the landscape makes the next section — where you try it yourself — more honest.
        </p>

        {/* Labor cost explainer */}
        <FadeIn>
        <h3 className="chart-head">The elephant in the room: labor costs</h3>
        <p className="chart-sub">Personnel spending, pensions and health benefits account for the vast majority of city expenditure</p>

        <div className="labor-bar-wrap">
          <div className="labor-bar">
            <div className="labor-segment" style={{ width: `${psPct}%`, background: C.indigo }}>
              <span className="labor-seg-label">Personnel {psPct}%</span>
            </div>
            <div className="labor-segment" style={{ width: `${((totalOTPS / totalSpending) * 100).toFixed(0)}%`, background: C.periwinkle }}>
              <span className="labor-seg-label">Non-personnel {((totalOTPS / totalSpending) * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        <p className="prose">
          NYC employs roughly <strong>306,000 people</strong> — more than the active-duty U.S. Marine Corps. Salaries, wages, overtime, pensions, and health insurance for current and retired workers consume about <strong>70 cents of every dollar</strong> the city spends. Pensions alone cost <strong>{fmtB(SPENDING.find(s => s.id === 'pensions').amount)}</strong> per year, up from $1.5 billion in 2002.
        </p>
        <p className="prose">
          The city negotiates contracts with more than <strong>150 municipal unions</strong>, led by DC 37 (the largest, representing ~150,000 members), the UFT (teachers), the PBA (police officers), and the UFA (firefighters). Pattern bargaining means that whatever the city agrees to with one major union sets the floor for the rest. Every 1% across-the-board raise costs roughly <strong>$450 million per year</strong>.
        </p>
        <p className="prose">
          Health insurance is the other pressure point. The city provides <strong>premium-free health coverage</strong> to employees and retirees — a benefit virtually no private employer still offers. The de Blasio administration tried to switch retirees to a Medicare Advantage plan; unions sued and won. The Adams administration tried again; same result. The annual cost of employee and retiree health benefits now exceeds <strong>$9 billion</strong>.
        </p>
        </FadeIn>

        <hr className="divider" />

        {/* Tax debate */}
        <FadeIn>
        <h3 className="chart-head">The tax debate: can New York raise its way out?</h3>
        <p className="chart-sub">Mamdani’s preferred approach — raising revenue — is the most politically divisive question in city fiscal policy</p>

        <div className="debate-grid">
          <div className="debate-col">
            <div className="debate-header for">The case for higher taxes</div>
            <ul className="debate-list">
              <li><strong>The wealthy can absorb it.</strong> The top 1% of NYC filers contribute 37–48% of city income tax revenue. A 2-point surcharge on millionaires would affect ~33,000 filers — and raise $1.8B.</li>
              <li><strong>Property taxes are low by national standards.</strong> NYC’s effective property tax rate (~0.9%) is below the national median. The assessment system is deeply regressive — wealthy homeowners in brownstone Brooklyn often pay lower effective rates than condo owners in the Bronx.</li>
              <li><strong>Cuts hurt the most vulnerable.</strong> The services most likely to be cut — homeless shelters, public hospitals, after-school programs — disproportionately serve low-income New Yorkers who have no private-market alternative.</li>
              <li><strong>The city has taxing authority the Council can use unilaterally.</strong> Property tax increases don’t require Albany. The Council can act on its own timeline.</li>
            </ul>
          </div>
          <div className="debate-col">
            <div className="debate-header against">The case against</div>
            <ul className="debate-list">
              <li><strong>The tax base is already dangerously volatile.</strong> CBC estimates ~60% of city revenue comes from economically sensitive sources. A recession or Wall Street downturn could erase $4 billion to $5 billion in a single year.</li>
              <li><strong>High earners can leave.</strong> Remote work has weakened the geographic lock-in. NYC saw elevated outmigration of high-income tax filers during and after COVID. Every departing millionaire takes ~$55,000 a year in city income tax revenue.</li>
              <li><strong>It doesn’t fix the structural problem.</strong> If spending grows 4–5% annually and revenue grows 2–3%, new taxes buy time but don’t close the gap permanently. FY2028's hole ($6.7B) will be even bigger.</li>
              <li><strong>Albany is unreliable.</strong> The millionaire and corporate tax proposals require state legislation. The governor and state Senate have shown little appetite for NYC-specific tax increases in an election year.</li>
            </ul>
          </div>
        </div>
        </FadeIn>

        <hr className="divider" />

        {/* Mamdani new spending */}
        <FadeIn>
        <h3 className="chart-head">It’s not just about closing the gap — Mamdani wants to spend more, too</h3>
        <p className="chart-sub">The preliminary budget includes new investments even as the city faces a $5.4 billion hole</p>

        <p className="prose">
          This is what makes budget politics so difficult: Mamdani wants Albany to authorize new taxes on the wealthy and on corporations. The 9.5% property tax hike in his budget is widely seen as a pressure tactic — a deliberately hard-to-swallow fallback designed to push Albany toward his preferred revenue package. Every major political partner, from the City Council speaker to the governor, has called the property tax increase a non-starter. Yet even as the city works to close a $5.4 billion hole, Mamdani is also proposing <strong>significant new spending</strong>. His preliminary budget includes:
        </p>

        <div className="new-spending-list">
          <div className="new-spend-item">
            <span className="new-spend-amount">$500M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">Universal childcare expansion</div>
              <div className="new-spend-desc">Extending 3-K and pre-K to cover more children under 3. Builds on de Blasio’s universal pre-K but at greater cost per seat.</div>
            </div>
          </div>
          <div className="new-spend-item">
            <span className="new-spend-amount">$350M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">Right to Counsel expansion & tenant protection</div>
              <div className="new-spend-desc">Expanding free legal representation for tenants facing eviction to all zip codes. Currently covers ~65% of the city.</div>
            </div>
          </div>
          <div className="new-spend-item">
            <span className="new-spend-amount">$300M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">Mental health & "B-HEARD" crisis response</div>
              <div className="new-spend-desc">Scaling up non-police mental health emergency response teams citywide. Currently operational in limited precincts.</div>
            </div>
          </div>
          <div className="new-spend-item">
            <span className="new-spend-amount">$250M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">Green buildings & climate resilience</div>
              <div className="new-spend-desc">Retrofitting city buildings for Local Law 97 compliance and flood resilience in vulnerable neighborhoods.</div>
            </div>
          </div>
          <div className="new-spend-item">
            <span className="new-spend-amount">$200M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">NYCHA capital repairs (city share)</div>
              <div className="new-spend-desc">Additional city contribution to address $78 billion+ in deferred maintenance at the nation’s largest public housing authority.</div>
            </div>
          </div>
          <div className="new-spend-item">
            <span className="new-spend-amount">$106M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">Summer Rising youth program</div>
              <div className="new-spend-desc">Summer academics and enrichment for K-12 students, with outyear funding committed.</div>
            </div>
          </div>
          <div className="new-spend-item">
            <span className="new-spend-amount">$54M</span>
            <div className="new-spend-body">
              <div className="new-spend-label">Community Food Connection (tripling food assistance)</div>
              <div className="new-spend-desc">More than triples HRA’s baseline food assistance funding in FY27.</div>
            </div>
          </div>
        </div>

        <div className="insight-box" style={{ marginTop: 16 }}>
          <div className="insight-label">Not yet funded — but on the horizon</div>
          <p>
            Two of Mamdani’s biggest campaign promises are <em>not</em> in the preliminary budget but loom over the fiscal picture.
            <strong> Free citywide bus service</strong> would cost an estimated $800 million to $1 billion a year in lost MTA fare revenue.
            MTA operations are traditionally state-funded, but the city could pick up the tab if it deems this a priority — as it has with other transit initiatives.
            Both legislative chambers included a fare-free bus pilot in their one-house budgets, and Mamdani proposed free buses during the 2026 FIFA World Cup ($3.8 million).
            But the MTA was not consulted, and Gov. Hochul has not endorsed the broader plan.
            <strong> A new Department of Community Safety</strong> would consolidate gun violence prevention, hate crime prevention, and
            community mental health into a single agency at an estimated $500M in new funding (plus ~$600M transferred from existing agencies).
            The administration says funding will appear in the executive budget due late April.
          </p>
        </div>

        <div className="insight-box">
          <div className="insight-label">The math problem</div>
          <p>
            The funded initiatives above total roughly <span className="hl">$1.76 billion</span>. Add that to the $5.4B structural gap and
            Mamdani actually needs to find <span className="hl">$7.2 billion</span> — through some combination of new taxes, spending cuts
            elsewhere, and reserve drawdowns. And that’s before free buses or the Department of Community Safety. Fiscal watchdogs question whether the math adds up. Supporters say the city can’t afford
            <em>not</em> to invest in childcare and climate. The tension between those two positions is what makes this budget so difficult.
          </p>
        </div>
        </FadeIn>

        <hr className="divider" />

        {/* Expert proposals */}
        <FadeIn>
        <h3 className="chart-head">What the experts propose</h3>
        <p className="chart-sub">Three serious plans, three different philosophies</p>
        </FadeIn>

        <FadeIn>
        <div className="proposal-card">
          <div className="proposal-header">
            <div className="proposal-source">Citizens Budget Commission</div>
            <div className="proposal-title">"False Choice" (March 2026)</div>
          </div>
          <p className="prose" style={{ marginBottom: 12 }}>
            The CBC — the city’s most influential fiscal watchdog — published its most aggressive reform agenda yet. Their core argument: the combined FY26–27 gap is <strong>$9.4 billion</strong>, city-funded spending grew <strong>6.8% annually</strong> from FY21–25 (outpacing tax revenue growth of 5.2%), and <strong>NYC’s spending problem is structural, not cyclical</strong>. No amount of new revenue will fix it without operational reform.
          </p>
          <div className="proposal-items">
            <div className="proposal-item"><span className="proposal-amount">{fmtM(1300)}</span> Seek state relief from class size mandate</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(400)}</span> Adjust school funding for declining enrollment (-120K students)</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(500)}</span> Switch to self-funded employee health plan</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(200)}</span> Consolidate fragmented union welfare funds</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(250)}</span> Overhaul $32 billion+ in city procurement contracts</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(600)}</span> Reduce funded vacancies and slow hiring</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(300)}</span> Curb uniformed-service overtime</div>
          </div>
          <p className="proposal-note">CBC explicitly opposes tax increases, arguing the city’s economically sensitive tax base (~60% of revenue) is already dangerously volatile.</p>
        </div>
        </FadeIn>

        <FadeIn>
        <div className="proposal-card">
          <div className="proposal-header">
            <div className="proposal-source">NYC Comptroller</div>
            <div className="proposal-title">FY2027 Budget Preview</div>
          </div>
          <p className="prose" style={{ marginBottom: 12 }}>
            The Comptroller takes a middle path: <strong>modest revenue increases paired with targeted cuts</strong>. He projects a combined <strong>$10.4 billion FY26–27 shortfall</strong> — the worst since the Great Recession — with city-funded spending understated by $3.16 billion in FY26 alone (rental assistance is underbudgeted by $795 million). Flags $559 million in unbudgeted overtime and warns that the mayor’s savings targets lack specifics.
          </p>
          <div className="proposal-items">
            <div className="proposal-item"><span className="proposal-amount">{fmtM(1800)}</span> Modest property tax increase (~4.5%)</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(100)}</span> 50 new DOF auditors to recover uncollected taxes</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(125)}</span> 200 new lawyers to reduce $1.9B in claims/settlements</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(300)}</span> Overtime reform across uniformed agencies</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(600)}</span> Vacancy reduction using existing hiring freeze</div>
          </div>
          <p className="proposal-note">Also recommends drawing $980M from the Rainy Day Fund — a move the comptroller’s own office has criticized in past administrations.</p>
        </div>
        </FadeIn>

        <FadeIn>
        <div className="proposal-card">
          <div className="proposal-header">
            <div className="proposal-source">Mayor Mamdani</div>
            <div className="proposal-title">FY2027 Preliminary Budget (Feb 2026)</div>
          </div>
          <p className="prose" style={{ marginBottom: 12 }}>
            Mamdani’s first budget leans heavily on <strong>new revenue and aspirational savings targets</strong>. The property tax increase is the backstop if Albany rejects the income and corporate tax proposals.
          </p>
          <div className="proposal-items">
            <div className="proposal-item"><span className="proposal-amount">{fmtM(3700)}</span> 9.5% property tax increase (Council authority)</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(1800)}</span> Millionaire income tax surcharge (requires Albany)</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(1500)}</span> Corporate tax increase on top firms (requires Albany; Senate one-house supports)</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(1770)}</span> Agency savings via EO 12 Chief Savings Officers (2.5%)</div>
            <div className="proposal-item"><span className="proposal-amount">{fmtM(980)}</span> Rainy Day Fund drawdown (one-time)</div>
          </div>
          <p className="proposal-note">Council Speaker Menin called the property tax hike a "non-starter." CBC warned the savings targets are aspirational, not operational. The plan’s total exceeds the gap — but much of it requires Albany or is one-time money.</p>
        </div>
        </FadeIn>

        <FadeIn>
        <div className="insight-box">
          <div className="insight-label">The union question</div>
          <p>
            Almost every serious savings proposal eventually runs into <span className="hl">organized labor</span>. Health insurance reform? Unions sued. Workforce reduction? DC 37 mobilizes. Overtime caps? PBA invokes public safety. Pension reform? State law protects existing benefits. This doesn’t mean reform is impossible — but it means any honest budget plan must account for the political cost of taking on the city’s most powerful constituency. The unions represent the workers who keep the city running. They also represent the single largest claim on every tax dollar the city collects.
          </p>
        </div>
        </FadeIn>

        <Source>CBC "False Choice" (March 2026); Comptroller FY2027 Budget Preview; Mayor’s FY2027 Preliminary Budget (Feb 2026); NYC Office of Labor Relations</Source>
      </div>
    </div>
  )
}

// ============================================================
// ACT 4: YOUR MOVE (Budget Balancer)
// ============================================================

function ActBalancer() {
  const [selected, setSelected] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    const planParam = params.get('plan')
    if (planParam) {
      const ids = planParam.split(',').filter(id => ALL_OPTIONS.some(o => o.id === id))
      return new Set(ids)
    }
    return new Set()
  })
  const [openDetails, setOpenDetails] = useState(new Set())

  const toggleOption = useCallback((id) => {
    setSelected(prev => {
      const next = new Set(prev)
      const opt = ALL_OPTIONS.find(o => o.id === id)
      if (next.has(id)) {
        next.delete(id)
      } else {
        // Remove conflicts
        if (opt.conflicts) {
          opt.conflicts.forEach(c => next.delete(c))
        }
        next.add(id)
      }
      return next
    })
  }, [])

  const toggleDetail = useCallback((id) => {
    setOpenDetails(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const totalSaved = useMemo(() => {
    return ALL_OPTIONS.filter(o => selected.has(o.id)).reduce((s, o) => s + o.amount, 0)
  }, [selected])

  const remaining = BASELINE_GAP - totalSaved
  const pctClosed = Math.min((totalSaved / BASELINE_GAP) * 100, 100)
  const isClosed = remaining <= 0

  const revSaved = REVENUE_OPTIONS.filter(o => selected.has(o.id)).reduce((s, o) => s + o.amount, 0)
  const cutSaved = SPENDING_OPTIONS.filter(o => selected.has(o.id)).reduce((s, o) => s + o.amount, 0)
  const resSaved = RESERVE_OPTIONS.filter(o => selected.has(o.id)).reduce((s, o) => s + o.amount, 0)
  const oneTimeSaved = ALL_OPTIONS.filter(o => selected.has(o.id) && o.isOneTime).reduce((s, o) => s + o.amount, 0)
  const hardCount = ALL_OPTIONS.filter(o => selected.has(o.id) && o.difficulty === 'hard').length

  const renderOptions = (options, title, context) => (
    <>
      <div className="section-head">{title}</div>
      <p className="section-context">{context}</p>
      {options.map(opt => {
        const isSelected = selected.has(opt.id)
        const isConflicted = !isSelected && opt.conflicts?.some(c => selected.has(c))
        return (
          <div key={opt.id} className={`option-card ${isSelected ? 'selected' : ''} ${isConflicted ? 'conflicted' : ''}`}
            onClick={() => !isConflicted && toggleOption(opt.id)}>
            <div className={`checkbox ${isSelected ? 'checked' : ''}`}>
              {isSelected && <span style={{ color: C.white, fontSize: 14, fontWeight: 900 }}>✓</span>}
            </div>
            <div className="option-body">
              <div className="option-top">
                <div className="option-label">{opt.label}</div>
                <div className={`option-amount ${isSelected ? 'active' : ''}`}>{fmtM(opt.amount)}</div>
              </div>
              <div className="option-tags">
                {opt.difficulty === 'hard' && <span className="tag neutral">Requires Albany</span>}
                {opt.isOneTime && <span className="tag conflict">One-time only</span>}
                {isConflicted && <span className="tag conflict">Conflicts with selection</span>}
              </div>
              <button className="detail-toggle" onClick={(e) => { e.stopPropagation(); toggleDetail(opt.id) }}>
                {openDetails.has(opt.id) ? 'Less' : 'More'} detail
              </button>
              {openDetails.has(opt.id) && (
                <div className="option-detail">
                  <p>{opt.desc}</p>
                  <p className="option-risk">Risk: {opt.risk}</p>
                  <p className="option-source">Source: {opt.sourceUrl ? <a href={opt.sourceUrl} target="_blank" rel="noopener noreferrer">{opt.source}</a> : opt.source}</p>
                </div>
              )}
            </div>
          </div>
        )
      })}
    </>
  )

  return (
    <div className="act act--white" id="act-balancer">
      <div className="content-w">
        <FadeIn>
          <div className="act-number">Your Move</div>
          <h2 className="act-headline">Close the gap. You have $5.4 billion to find.</h2>
        </FadeIn>
        <p className="balancer-intro">
          Every option below is drawn from real proposals by the mayor, the comptroller, the Citizens Budget Commission,
          or the City Council. Each comes with tradeoffs. None is painless. Can you balance it?
        </p>

        <div className="sticky-meter">
          <div className="gap-header">
            <div>
              <span className="gap-amount" style={{ color: isClosed ? C.green : C.magenta }}>{fmtM(Math.max(remaining, 0))}</span>
              <span className="gap-lbl">{isClosed ? 'surplus' : 'remaining gap'}</span>
            </div>
            <span className="gap-pct">{pctClosed.toFixed(0)}% closed</span>
          </div>
          <div className="gap-track">
            <div className="gap-fill" style={{
              width: `${pctClosed}%`,
              background: isClosed ? C.green : pctClosed > 60 ? C.chartreuse : C.orange,
            }}>
              {isClosed && <span className="gap-check">BALANCED</span>}
            </div>
          </div>
        </div>

        {renderOptions(REVENUE_OPTIONS, 'Raise Revenue',
          'New York City cannot print money or run a deficit. Revenue options mostly require state approval from Albany.')}

        {renderOptions(SPENDING_OPTIONS, 'Cut Spending',
          'The city spends more per capita than any peer. But most of the budget is locked in by labor contracts, mandates, and debt obligations.')}

        {renderOptions(RESERVE_OPTIONS, 'Use Reserves',
          'One-time money that buys time but doesn\'t fix the structural problem. The Rainy Day Fund exists for recessions — drawing it down now leaves the city exposed.')}

        {/* Scorecard */}
        <div className="scorecard">
          <h3>Your Budget Plan</h3>
          <div className="score-grid">
            <div className="score-cell">
              <div className="score-val" style={{ color: C.indigo }}>{fmtM(revSaved)}</div>
              <div className="score-label">New revenue</div>
            </div>
            <div className="score-cell">
              <div className="score-val" style={{ color: C.cerulean }}>{fmtM(cutSaved)}</div>
              <div className="score-label">Spending cuts</div>
            </div>
            <div className="score-cell">
              <div className="score-val" style={{ color: C.orange }}>{fmtM(resSaved)}</div>
              <div className="score-label">Reserves</div>
            </div>
            <div className="score-cell">
              <div className="score-val" style={{ color: isClosed ? C.green : C.magenta }}>{fmtM(Math.max(remaining, 0))}</div>
              <div className="score-label">{isClosed ? 'Surplus' : 'Remaining gap'}</div>
            </div>
          </div>

          {hardCount > 2 && (
            <div className="warning orange">
              Your plan requires Albany to approve {hardCount} measures. Good luck with that.
            </div>
          )}
          {oneTimeSaved > 500 && (
            <div className="warning magenta">
              {fmtM(oneTimeSaved)} of your plan is one-time money. The FY2028 gap ($6.7B) will be even harder.
            </div>
          )}
          {revSaved > cutSaved * 2 && (
            <div className="warning purple">
              You’re leaning heavily on revenue. CBC warns that economically sensitive taxes already generate ~60% of city revenue.
            </div>
          )}
          {cutSaved > revSaved * 2 && (
            <div className="warning purple">
              You’re leaning heavily on cuts. Service reductions have real consequences for 8.1 million residents.
            </div>
          )}
          {isClosed && (
            <div className="warning green">
              Congratulations — you’ve balanced FY2027. Now do FY2028 ($6.7B), FY2029 ($6.8B), and FY2030 ($7.1B).
            </div>
          )}

          <div className="score-actions">
            <button className="reset-btn" onClick={() => setSelected(new Set())}>Reset all</button>
            <button className="share-btn" onClick={() => {
              const ids = [...selected].sort().join(',')
              const url = `${window.location.origin}${window.location.pathname}?plan=${encodeURIComponent(ids)}`
              navigator.clipboard.writeText(url).then(() => {
                const el = document.querySelector('.share-btn')
                if (el) { el.textContent = 'Link copied!'; setTimeout(() => { el.textContent = 'Share your plan' }, 2000) }
              }).catch(() => {
                prompt('Copy this link:', url)
              })
            }}>Share your plan</button>
          </div>
        </div>

        {/* Benchmark comparison */}
        <FadeIn>
          <div className="benchmark-section">
            <h3 className="chart-head" style={{ marginTop: 32 }}>How does your plan compare?</h3>
            <p className="chart-sub">See how your choices stack up against the actual proposals on the table.</p>

            <div className="benchmark-grid">
              {/* Your plan */}
              <div className="benchmark-card yours">
                <div className="benchmark-header">Your Plan</div>
                <div className="benchmark-bar-wrap">
                  <div className="benchmark-bar" style={{ width: `${Math.min(pctClosed, 100)}%`, background: isClosed ? C.green : C.orange }} />
                </div>
                <div className="benchmark-pct">{pctClosed.toFixed(0)}% closed</div>
                <div className="benchmark-mix">
                  {revSaved > 0 && <span style={{ color: C.indigo }}>{Math.round((revSaved / Math.max(totalSaved, 1)) * 100)}% revenue</span>}
                  {cutSaved > 0 && <span style={{ color: C.cerulean }}>{Math.round((cutSaved / Math.max(totalSaved, 1)) * 100)}% cuts</span>}
                  {resSaved > 0 && <span style={{ color: C.orange }}>{Math.round((resSaved / Math.max(totalSaved, 1)) * 100)}% reserves</span>}
                </div>
              </div>

              {Object.entries(BENCHMARK_PLANS).map(([key, plan]) => {
                const planTotal = ALL_OPTIONS.filter(o => plan.selections.includes(o.id)).reduce((s, o) => s + o.amount, 0)
                const planPct = Math.min((planTotal / BASELINE_GAP) * 100, 100)
                const planRev = REVENUE_OPTIONS.filter(o => plan.selections.includes(o.id)).reduce((s, o) => s + o.amount, 0)
                const planCut = SPENDING_OPTIONS.filter(o => plan.selections.includes(o.id)).reduce((s, o) => s + o.amount, 0)
                const planRes = RESERVE_OPTIONS.filter(o => plan.selections.includes(o.id)).reduce((s, o) => s + o.amount, 0)
                const overlap = plan.selections.filter(id => selected.has(id)).length
                return (
                  <div key={key} className="benchmark-card">
                    <div className="benchmark-header">{plan.label}</div>
                    <div className="benchmark-bar-wrap">
                      <div className="benchmark-bar" style={{ width: `${planPct}%`, background: C.periwinkle }} />
                    </div>
                    <div className="benchmark-pct">{planPct.toFixed(0)}% closed</div>
                    <div className="benchmark-mix">
                      {planRev > 0 && <span style={{ color: C.indigo }}>{Math.round((planRev / planTotal) * 100)}% revenue</span>}
                      {planCut > 0 && <span style={{ color: C.cerulean }}>{Math.round((planCut / planTotal) * 100)}% cuts</span>}
                      {planRes > 0 && <span style={{ color: C.orange }}>{Math.round((planRes / planTotal) * 100)}% reserves</span>}
                    </div>
                    {selected.size > 0 && <div className="benchmark-overlap">{overlap} of {plan.selections.length} options in common with your plan</div>}
                    <button className="benchmark-load" onClick={() => setSelected(new Set(plan.selections))}>Load this plan</button>
                  </div>
                )
              })}
            </div>
          </div>
        </FadeIn>

        <Source>Mayor’s FY2027 Preliminary Budget (Feb 2026); Comptroller FY2027 Budget Preview; CBC NYC Budget Blueprint (Nov 2025); OMB Financial Plan</Source>
      </div>
    </div>
  )
}


// ============================================================
// BENCHMARK PLANS — for budget balancer comparisons
// ============================================================
const BENCHMARK_PLANS = {
  mayor: {
    label: "Mayor’s Plan",
    desc: 'Mamdani\'s FY2027 Preliminary Budget (Feb 2026)',
    selections: ['pit_millionaire', 'corporate_tax', 'dof_auditors', 'tort_lawyers', 'cso_savings', 'rainy_day', 'rhbt'],
  },
  cbc: {
    label: 'CBC Blueprint',
    desc: 'CBC “False Choice” (March 2026)',
    selections: ['class_size', 'enrollment', 'cso_savings', 'overtime', 'procurement', 'vacancies', 'health_ins', 'welfare_funds'],
  },
  comptroller: {
    label: 'Comptroller',
    desc: 'Comptroller FY2027 Budget Preview',
    selections: ['property_tax_half', 'dof_auditors', 'tort_lawyers', 'overtime', 'vacancies', 'cso_half', 'rainy_day'],
  },
}

// ============================================================
// PROGRESS NAV — sticky section tracker
// ============================================================
const SECTIONS = [
  { id: 'scale', label: 'The Scale' },
  { id: 'history', label: 'Over Time' },
  { id: 'cliff', label: 'The Cliff' },
  { id: 'proposals', label: 'The Ideas' },
  { id: 'balancer', label: 'Your Move' },
]

function ProgressNav() {
  const [active, setActive] = useState('')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY
      // Show nav after scrolling past the header
      setVisible(scrollY > 300)

      // Find which section is currently in view
      for (let i = SECTIONS.length - 1; i >= 0; i--) {
        const el = document.getElementById(`act-${SECTIONS[i].id}`)
        if (el) {
          const rect = el.getBoundingClientRect()
          if (rect.top <= 120) {
            setActive(SECTIONS[i].id)
            return
          }
        }
      }
      setActive('')
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  if (!visible) return null

  return (
    <nav className="progress-nav">
      {SECTIONS.map(s => (
        <button
          key={s.id}
          className={`progress-dot ${active === s.id ? 'active' : ''}`}
          onClick={() => {
            const el = document.getElementById(`act-${s.id}`)
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}
        >
          <span className="progress-label">{s.label}</span>
        </button>
      ))}
    </nav>
  )
}

// ============================================================
// ANIMATED COUNT-UP HOOK
// ============================================================
function useCountUp(target, duration = 1800) {
  const [value, setValue] = useState(0)
  const [started, setStarted] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setStarted(true); obs.unobserve(el) } },
      { threshold: 0.3 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  useEffect(() => {
    if (!started) return
    const start = performance.now()
    const tick = (now) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(eased * target)
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [started, target, duration])

  return [ref, value]
}

// ============================================================
// EDITORIAL BRIDGE — transition prose between acts
// ============================================================
function Bridge({ children }) {
  return (
    <FadeIn>
      <div className="bridge">
        <p className="bridge-text">{children}</p>
      </div>
    </FadeIn>
  )
}

// ============================================================
// MAIN APP
// ============================================================

export default function App() {
  return (
    <div className="story">
      <ProgressNav />

      <div className="story-header">
        <div className="header-tag">Data</div>
        <h1 className="story-title">$116 Billion and a $5.4 Billion Hole</h1>
        <p className="story-dek">See where New York City's money comes from, where it goes, and why it's not enough. Then try closing the gap yourself.</p>
        <div className="header-accent" aria-hidden="true" />
      </div>

      <ActScale />

      <Bridge>
        That’s the snapshot. But a budget is not a photograph — it’s a time-lapse. To understand why the city
        faces a $5.4 billion hole, you have to see how spending got here.
      </Bridge>

      <ActHistory />

      <Bridge>
        Growth this steep creates commitments. Pensions, labor contracts, debt service, and mandates lock in
        costs that don’t flex when revenue dips — and the risks are mounting.
      </Bridge>

      <ActCliff />

      <Bridge>
        So those are the risks. Before you try to close the gap yourself, here’s what the people paid to think about this are proposing — and where the plans converge and diverge.
      </Bridge>

      <ActProposals />

      <Bridge>
        Now it’s your turn. Every option below is drawn from the real proposals above. None is painless. Can you balance it?
      </Bridge>

      <ActBalancer />

      <footer className="story-footer">
        <div className="footer-inner">
          <div className="footer-text">
            Data as of Mayor’s FY2027 Preliminary Budget (February 2026). FiSC normalization uses Lincoln Institute
            methodology. All figures are estimates based on published government sources and may differ from final
            adopted budgets.
          </div>
        </div>
      </footer>
    </div>
  )
}
