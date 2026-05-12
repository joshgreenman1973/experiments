// NYC Civics Quiz — question bank
// Format: { category, question, options[5], correct (index 0-4), explanation (HTML) }
// Convention: option index 4 is always the joke option. The engine pins it last
// even when other options are shuffled.

export const MAIN_QUESTIONS = [
  {
    category: "Government Structure",
    question: "How many members serve on the New York City Council?",
    options: ["35", "51", "59", "100", "However many can fit in a room without killing each other"],
    correct: 1,
    explanation: 'The Council has 51 members, each representing a district of roughly 173,000 people. The body was expanded to 51 in 1991 after a Voting Rights Act lawsuit forced redistricting that better reflected the city\'s demographics. <a href="https://council.nyc.gov" target="_blank" rel="noopener">Council</a>.'
  },
  {
    category: "Budget",
    question: "What is the approximate size of New York City's annual operating budget?",
    options: ["$45 billion", "$75 billion", "$115 billion", "$210 billion", "Whatever Albany says you can have, minus a little extra"],
    correct: 2,
    explanation: "The adopted budget for fiscal year 2026 is roughly $115 billion — larger than the budgets of most U.S. states and many sovereign nations. Federal and state aid account for a significant chunk; the rest comes mostly from property, income, and sales taxes."
  },
  {
    category: "Mayor's Office",
    question: "How long is a New York City mayor's term, and how many terms can they serve?",
    options: [
      "Two years, unlimited terms",
      "Four years, two-term limit",
      "Four years, three-term limit",
      "Six years, single term",
      "Until the tabloids stop returning their calls"
    ],
    correct: 1,
    explanation: 'Mayors serve four-year terms with a two-term limit, restored by referendum in 2010 after Michael Bloomberg controversially extended limits to a third term in 2008. Bloomberg remains the only modern mayor to serve three. <a href="https://www.nyc.gov/site/cfb/voters/term-limits.page" target="_blank" rel="noopener">Term limits</a>.'
  },
  {
    category: "Agencies",
    question: "What does the city agency abbreviated DOI primarily do?",
    options: [
      "Run the city's IT systems",
      "Investigate corruption and misconduct in city government",
      "Manage the city's public hospitals",
      "Distribute identification cards",
      "Mostly leak things to The City"
    ],
    correct: 1,
    explanation: 'The Department of Investigation, established in the 1873 Charter, is the city\'s independent inspector general. It investigates fraud, corruption, and misconduct across every city agency, and works alongside NYPD\'s Internal Affairs Bureau. The DOI Commissioner is appointed by the Mayor but the agency operates with structural independence. <a href="https://www.nyc.gov/site/doi/index.page" target="_blank" rel="noopener">DOI</a>.'
  },
  {
    category: "Transit",
    question: "Who controls the Metropolitan Transportation Authority?",
    options: [
      "New York City",
      "New York State",
      "A joint city-state authority",
      "The federal government",
      "Whichever official last got stuck on the F train"
    ],
    correct: 1,
    explanation: "The MTA is a state public-benefit corporation controlled by the Governor, who appoints its chair and a majority of board members — even though New York City riders account for the vast majority of subway and bus trips. The Mayor recommends only four of 17 voting board members. This city-vs-state tension shapes nearly every transit policy debate."
  },
  {
    category: "Transit",
    question: "When did congestion pricing actually start charging drivers entering Manhattan below 60th Street?",
    options: [
      "January 2023",
      "June 2024",
      "January 2025",
      "It hasn't started yet",
      "The morning after the lawsuit Trump filed got laughed out of court"
    ],
    correct: 2,
    explanation: 'Congestion pricing took effect January 5, 2025, after years of delay and a last-minute pause and unpause by Governor Hochul. Most passenger cars pay $9 during peak hours to enter the Central Business District. Revenue is dedicated to MTA capital projects. <a href="https://congestionreliefzone.mta.info" target="_blank" rel="noopener">MTA</a>.'
  },
  {
    category: "Housing",
    question: "What did the FARE Act, which took effect in 2025, do?",
    options: [
      "Capped annual rent increases at 3%",
      "Shifted broker fees from tenants to whichever party hires the broker (usually the landlord)",
      "Repealed rent stabilization on vacant units",
      "Required brokers to be licensed by the city",
      "Made it illegal to charge a key fee, an application fee, or a 'just because' fee"
    ],
    correct: 1,
    explanation: 'The Fairness in Apartment Rentals (FARE) Act, passed by the Council over Mayor Adams\'s veto in late 2024 and effective June 2025, ended the longstanding NYC practice of forcing tenants to pay a broker\'s commission (often 12–15% of annual rent) when the landlord — not the tenant — hired the broker. Real estate industry groups sued; the law has largely held up. <a href="https://council.nyc.gov" target="_blank" rel="noopener">Council</a>.'
  },
  {
    category: "Housing",
    question: "What did the City of Yes for Housing Opportunity, adopted by the Council in late 2024, primarily do?",
    options: [
      "Created a citywide rent freeze for two years",
      "Modestly upzoned every neighborhood to allow more housing, including transit-oriented density and accessory dwelling units",
      "Required every new building to be 30% affordable",
      "Banned short-term rentals",
      "Said yes to roughly half of what the Mayor asked for and no to the half with parking minimums"
    ],
    correct: 1,
    explanation: 'City of Yes for Housing Opportunity is a citywide zoning text amendment passed by the Council in December 2024. It loosens rules on accessory dwelling units, allows modest density near transit, eliminates parking mandates in much of the city, and is projected to enable around 80,000 new homes over 15 years — the biggest zoning change in decades. <a href="https://www.nyc.gov/site/planning/plans/city-of-yes/city-of-yes-housing-opportunity.page" target="_blank" rel="noopener">DCP</a>.'
  },
  {
    category: "Land Use",
    question: "What does ULURP stand for?",
    options: [
      "Uniform Land Use Review Procedure",
      "Urban Land Use Regulatory Plan",
      "Universal Land Use Restoration Project",
      "Unified Local Urban Reform Process",
      "Usually Lots of Unhappy Residents Pretending"
    ],
    correct: 0,
    explanation: 'The Uniform Land Use Review Procedure is the seven-month-or-so public process major rezonings, dispositions of city property, and certain other land-use actions must go through. Community Boards and Borough Presidents review and advise; the City Planning Commission and City Council vote. <a href="https://www.nyc.gov/site/planning/applicants/applicant-portal/step5-ulurp-overview.page" target="_blank" rel="noopener">DCP</a>.'
  },
  {
    category: "Education",
    question: "Who currently has authority over New York City's public schools?",
    options: [
      "An elected board of education",
      "The Mayor, through an appointed Chancellor",
      "The state Board of Regents directly",
      "Each borough president, for schools in their borough",
      "A panel of weary parents"
    ],
    correct: 1,
    explanation: 'NYC has had mayoral control of schools since 2002, when the legislature replaced the old Board of Education. The Mayor appoints the Schools Chancellor, who runs the Department of Education — the largest school district in the country, with about 900,000 students. Mayoral control is reauthorized periodically by the state legislature and remains contested. <a href="https://www.schools.nyc.gov" target="_blank" rel="noopener">DOE</a>.'
  },
  {
    category: "Government Structure",
    question: "What is the role of New York City's Public Advocate?",
    options: [
      "Run the city's legal department",
      "Investigate complaints against city agencies and serve as ombudsperson, first in line of mayoral succession",
      "Manage the city's public relations",
      "Oversee public hospitals",
      "Tweet a lot and hope someone notices"
    ],
    correct: 1,
    explanation: "The Public Advocate is a citywide elected official who serves as a watchdog over city agencies, fields citizen complaints, introduces legislation in the City Council (without a vote), and is first in line of mayoral succession. The role replaced the old City Council President position in 1993."
  },
  {
    category: "Elections",
    question: "What voting system does New York City use for primary elections for most offices?",
    options: [
      "First-past-the-post",
      "Top-two runoff",
      "Ranked-choice voting",
      "Approval voting",
      "An elaborate system involving rabbis, bodega owners, and prayer"
    ],
    correct: 2,
    explanation: 'NYC adopted ranked-choice voting via 2019 referendum, with the first major use in the 2021 mayoral primary. Voters can rank up to five candidates; if no one wins a majority of first-place votes, the lowest-vote candidate is eliminated and their voters\' next choices counted, repeating until someone has a majority. General elections still use first-past-the-post. <a href="https://vote.nyc/page/ranked-choice-voting" target="_blank" rel="noopener">BOE</a>.'
  },
  {
    category: "Elections",
    question: "Who won the November 2025 New York City mayoral general election?",
    options: [
      "Eric Adams (independent)",
      "Andrew Cuomo (independent)",
      "Zohran Mamdani (Democratic)",
      "Curtis Sliwa (Republican)",
      "Whichever candidate had the best TikTok"
    ],
    correct: 2,
    explanation: 'Zohran Mamdani won the November 2025 general election after defeating Andrew Cuomo in the June Democratic primary. Cuomo and Adams both ran in the general as independents; Sliwa was the Republican nominee. Mamdani became the city\'s first Muslim mayor, first South Asian mayor, and first millennial mayor. He took office January 1, 2026.'
  },
  {
    category: "Mayor's Office",
    question: "Mayor Mamdani campaigned on a citywide rent freeze for stabilized apartments. Through which body would such a freeze actually be enacted?",
    options: [
      "By executive order from the Mayor",
      "By a vote of the Rent Guidelines Board, whose members are appointed by the Mayor",
      "By the City Council, with mayoral signature",
      "By the State Legislature in Albany",
      "By whoever holds the Excel sheet that day"
    ],
    correct: 1,
    explanation: 'The Rent Guidelines Board sets annual rent adjustments for the roughly 1 million stabilized apartments in NYC. Its nine members are appointed by the Mayor — two from tenant ranks, two from owner ranks, and five "public" members including the chair. A "freeze" requires a board majority, which is why mayoral appointment power, not statute, is the lever. Mayor Mamdani named new members shortly after taking office; their first vote of his term comes in June 2026. <a href="https://www.nyc.gov/site/rentguidelinesboard/index.page" target="_blank" rel="noopener">RGB</a>.'
  },
  {
    category: "Transit",
    question: "Mayor Mamdani campaigned on fare-free city buses. What's the central legal obstacle to him simply ordering it?",
    options: [
      "The City Charter forbids subsidizing fares",
      "Bus fares are set by the MTA, a state authority — not by the Mayor",
      "Federal transit law prohibits zero-fare service",
      "Only the City Council, not the Mayor, can change transit pricing",
      "The B61 driver said no"
    ],
    correct: 1,
    explanation: 'NYC Transit (which runs the buses) is a subsidiary of the MTA, a state public-benefit corporation. Fares are set by the MTA Board, whose chair and majority are appointed by the Governor. The Mayor recommends only four of 17 voting board members. Any free-bus program requires either MTA cooperation, a state law change, or a city payment that fully replaces lost fare revenue — which is why Mamdani has framed the policy as a city-funded subsidy negotiated with Albany rather than a unilateral move.'
  },
  {
    category: "Budget",
    question: "Mamdani has proposed funding much of his agenda by raising taxes on corporations and high-income earners. Which level of government must approve those increases?",
    options: [
      "The City Council alone",
      "The Mayor by executive order, subject to Council override",
      "The State Legislature and Governor — the city has no independent power to raise income or corporate tax rates",
      "A citywide referendum",
      "Whoever Albany owes a favor that week"
    ],
    correct: 2,
    explanation: 'Under New York State law, NYC cannot unilaterally raise its personal income tax, corporate tax, or most other major tax rates. Each of those changes requires "home rule" approval from Albany — a State Legislature bill signed by the Governor. This is the structural reason Mamdani\'s revenue proposals depend on the Governor and the State Senate and Assembly leadership, not on City Hall alone.'
  },
  {
    category: "Mayor's Office",
    question: "Which of the following positions does the Mayor of New York City NOT directly appoint?",
    options: [
      "Police Commissioner",
      "Schools Chancellor",
      "Sanitation Commissioner",
      "MTA Chair",
      "Whoever the Mayor's chief of staff went to college with"
    ],
    correct: 3,
    explanation: 'The MTA Chair is appointed by the Governor, with State Senate confirmation. The Police Commissioner, Schools Chancellor, and Sanitation Commissioner are all mayoral appointments. This split is why every NYC mayor — Mamdani included — must negotiate with the Governor on transit, even though city residents are most of the riders.'
  },
  {
    category: "Government Structure",
    question: "Mamdani has pledged to pilot city-owned grocery stores in food-insecure neighborhoods. Which existing city entity is the closest model for owning and operating retail outlets directly?",
    options: [
      "The Economic Development Corporation, which manages city real estate and waterfront concessions",
      "Health + Hospitals, the public benefit corporation that runs city hospitals",
      "NYCHA, the public housing authority",
      "The Department of Citywide Administrative Services",
      "A bodega that the city accidentally inherited in a tax foreclosure"
    ],
    correct: 1,
    explanation: 'New York City Health + Hospitals is the public-benefit corporation that operates 11 acute-care hospitals and dozens of clinics directly — the largest municipal health system in the country. It is the closest existing precedent for a city entity that owns and runs public-facing service operations. Critics of city-owned grocery stores point to H+H\'s recurring fiscal strain; supporters point to the same agency as proof that direct public provision is possible at scale.'
  },
  {
    category: "Legislation",
    question: "Adrienne Adams, the previous Council Speaker, ran against Mamdani in the 2025 Democratic primary and did not return to the Council in 2026. Who is elected by the Council to lead it each term?",
    options: [
      "The most senior member by tenure",
      "The Speaker, chosen by the 51 members at the start of each term",
      "The Mayor's nominee, subject to Council confirmation",
      "The Council Member representing the largest district by population",
      "Whoever the borough chairs let win this round"
    ],
    correct: 1,
    explanation: 'The Speaker is elected by the 51 members at the start of each two-year session and serves as the Council\'s presiding officer, chief negotiator with the Mayor, and arguably the second-most-powerful elected official in the city. Adrienne Adams (D-Queens), Speaker from 2022 through the end of 2025, ran for mayor in 2025 rather than seeking re-election to her seat. The new Speaker was elected by Council members in January 2026.'
  },
  {
    category: "Charter",
    question: "Mayor Adams convened a Charter Revision Commission in 2024 widely seen as an effort to blunt Council power. What is the only way Charter changes can take effect once a commission proposes them?",
    options: [
      "Ratification by a two-thirds Council vote",
      "Approval by voters in a referendum",
      "Signature by the Governor",
      "Adoption by the Mayor as an executive order",
      "Whatever the Daily News editorial board endorses"
    ],
    correct: 1,
    explanation: 'Charter Revision Commission proposals must be approved by NYC voters at the next general election. Several Adams-era ballot proposals passed in November 2024, including one giving the Mayor more control over the timing of certain Council legislation. Critics, including then-candidate Mamdani, argued the commission was used to outflank the Council; defenders called it overdue process reform.'
  },
  {
    category: "Budget",
    question: "Mayor Mamdani must submit his first preliminary budget in January and a final executive budget in the spring. The City Charter requires a final adopted budget by what date?",
    options: [
      "January 1",
      "April 1",
      "June 5",
      "July 1, the start of the fiscal year",
      "Whenever the Council Speaker stops returning calls"
    ],
    correct: 3,
    explanation: 'NYC\'s fiscal year runs July 1 through June 30, and the Charter requires the Council to adopt a budget by June 5 (with the Mayor\'s preliminary budget due in January and executive budget in the spring). In practice the deadline is honored most years; late-night handshake deals just before July 1 are a recurring tradition. Mamdani\'s first adopted budget — for FY 2027 — is due by June 5, 2026.'
  },
  {
    category: "Public Safety",
    question: "Mamdani campaigned on a new Department of Community Safety to handle mental-health and homelessness calls separate from the NYPD. Creating a new mayoral agency typically requires what?",
    options: [
      "A simple mayoral executive order",
      "A Charter amendment approved by voters",
      "Council legislation that establishes the agency, plus budget appropriation",
      "State Legislature approval",
      "A new acronym nobody can pronounce"
    ],
    correct: 2,
    explanation: 'Standing up a new city agency generally requires Council legislation establishing it (defining its powers, head, and reporting structure) together with budget lines that fund it. The Mayor can reorganize within existing agencies by executive order, but a wholly new department with statutory authority — like Mamdani\'s proposed Department of Community Safety — typically goes through the Council. The B-HEARD pilot under Adams used a different model: it sat inside H+H and FDNY rather than as a standalone agency.'
  },
  {
    category: "Elections",
    question: "Andrew Cuomo lost the June 2025 Democratic primary to Mamdani after a ranked-choice tabulation. Roughly how many candidates can NYC voters rank in a primary using ranked-choice voting?",
    options: [
      "2",
      "3",
      "5",
      "Up to 10",
      "As many as fit on the touchscreen before it freezes"
    ],
    correct: 2,
    explanation: 'NYC voters can rank up to five candidates in primaries that use ranked-choice voting, adopted by referendum in 2019 and first used at scale in 2021. If no one wins a majority of first-place votes, the lowest-ranked candidate is eliminated and their voters\' next choices are counted, repeating until someone has a majority. The 2025 mayoral primary went multiple rounds before Mamdani crossed the threshold against Cuomo.'
  },
  {
    category: "Housing",
    question: "Mamdani has called for the city to massively expand social housing. Which existing entity owns and operates the largest stock of permanently affordable, publicly owned apartments in NYC today?",
    options: [
      "HPD (Housing Preservation and Development)",
      "NYCHA (New York City Housing Authority)",
      "The Mitchell-Lama program",
      "The Department of Citywide Administrative Services",
      "A series of LLCs nobody can quite untangle"
    ],
    correct: 1,
    explanation: 'NYCHA owns and operates roughly 175,000 apartments housing nearly 350,000 New Yorkers — about 1 in 17 city residents — making it by far the largest public housing authority in North America. Any city-led "social housing" expansion either builds on NYCHA, on HPD-financed mixed-income development, or on a new entity created for the purpose. Mamdani\'s plan leans toward a new public developer plus aggressive use of the city\'s land and capital budget.'
  },
  {
    category: "Government Structure",
    question: "Within his first months in office, Mayor Mamdani named several deputy mayors. How is the number of deputy mayors set?",
    options: [
      "Fixed at four by the City Charter",
      "Set by the Mayor — the Charter does not cap the number",
      "Set by the Council each term",
      "Limited to one per borough",
      "However many fit at the Gracie Mansion dinner table"
    ],
    correct: 1,
    explanation: 'The number and portfolios of deputy mayors are set by the Mayor, not the Charter. Recent administrations have ranged from four to seven, with portfolios for operations, public safety, health and human services, housing and economic development, intergovernmental affairs, and communications. Each new mayor reshuffles to match priorities — Mamdani\'s lineup reflects his housing, transit, and affordability focus.'
  },
  {
    category: "Housing",
    question: "About what percentage of New York City's rental apartments are rent-stabilized?",
    options: [
      "About 15%",
      "About 30%",
      "About 45%",
      "About 60%",
      "Depends on what your landlord told the DOB last Tuesday"
    ],
    correct: 2,
    explanation: 'Roughly 1 million apartments — about 44% of the city\'s rental stock — are rent-stabilized, governed by laws set in Albany and rent increases set annually by the city\'s Rent Guidelines Board. Stabilization, distinct from the much smaller rent-control program, dates to 1969. <a href="https://www.nyc.gov/site/rentguidelinesboard/index.page" target="_blank" rel="noopener">RGB</a>.'
  },
  {
    category: "Boroughs",
    question: "Which borough is the largest by land area?",
    options: ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Whichever one you're trying to leave at the moment"],
    correct: 2,
    explanation: "Queens is by far the largest at about 109 square miles, more than four times the size of Manhattan (23 sq mi) and roughly 50% larger than Brooklyn (71 sq mi). The Bronx is 42 sq mi and Staten Island is 59. Queens also leads in residential population growth this decade."
  },
  {
    category: "Comptroller",
    question: "What is the primary responsibility of the New York City Comptroller?",
    options: [
      "Prosecute criminal cases",
      "Audit city agencies and manage city pensions",
      "Set tax rates",
      "Run the city's prison system",
      "Yell at the Mayor on television"
    ],
    correct: 1,
    explanation: "The Comptroller is the city's chief financial officer. The office audits agencies, oversees roughly $250 billion in city pension fund assets, registers contracts, and reviews the city's fiscal health. It is one of three citywide elected offices, along with Mayor and Public Advocate."
  },
  {
    category: "Agencies",
    question: "What does the city agency abbreviated DOB do?",
    options: [
      "Manages benefits for city workers",
      "Issues building permits and enforces the building code",
      "Runs day care programs",
      "Operates the city's ferries",
      "Mostly tells you to come back tomorrow"
    ],
    correct: 1,
    explanation: 'The Department of Buildings reviews construction plans, issues permits, performs inspections, and enforces the construction codes and zoning resolution. It\'s the agency most likely to be involved when you\'re renovating a kitchen, putting up a new building, or wondering why scaffolding has been outside your apartment for three years. <a href="https://www.nyc.gov/site/buildings/index.page" target="_blank" rel="noopener">DOB</a>.'
  },
  {
    category: "Mayor's Office",
    question: "Which of the following is NOT directly appointed by the Mayor?",
    options: [
      "Police Commissioner",
      "Schools Chancellor",
      "District Attorney",
      "Sanitation Commissioner",
      "Whoever the Mayor's most generous donor recommends"
    ],
    correct: 2,
    explanation: "The five borough District Attorneys are independently elected county officials — not city employees, despite operating within the city. They have full prosecutorial discretion. The Manhattan, Brooklyn, Queens, Bronx, and Staten Island DAs are accountable to voters, not to City Hall."
  },
  {
    category: "Charter",
    question: "Roughly how often is the New York City Charter — the city's constitution — typically revised by a Charter Revision Commission?",
    options: [
      "Every year",
      "Every 5–10 years",
      "Every 25 years",
      "Only when the state forces it",
      "Whenever a mayor wants to outflank the City Council"
    ],
    correct: 1,
    explanation: "Charter Revision Commissions are appointed by the Mayor (or, less commonly, by the City Council) and put proposed amendments on the ballot for voter approval. Recent commissions met in 2018, 2019, 2024, and 2025. Critics argue mayors increasingly use them to outflank Council priorities — which makes the funny answer not entirely wrong."
  },
  {
    category: "Public Safety",
    question: "What is 311?",
    options: [
      "An emergency services line",
      "A non-emergency city services hotline",
      "A complaint line specifically for noise",
      "The Mayor's direct phone line",
      "Where you go when you really, deeply need to yell at someone about a pothole"
    ],
    correct: 1,
    explanation: 'The 311 system, launched under Bloomberg in 2003, is the city\'s non-emergency hotline and online portal for everything from noise complaints to pothole reports to lost-property questions. It handles roughly 40 million contacts a year and generates one of the city\'s most-used open datasets. <a href="https://portal.311.nyc.gov" target="_blank" rel="noopener">311</a>.'
  },
  {
    category: "Boroughs",
    question: "What official represents each borough citywide and chairs land-use review for projects in that borough?",
    options: [
      "Borough Commissioner",
      "Borough President",
      "Borough Mayor",
      "Borough Speaker",
      "Borough Cheerleader-in-Chief"
    ],
    correct: 1,
    explanation: "Each of the five boroughs elects a Borough President. They no longer have direct legislative power — the old Board of Estimate, on which they sat, was dissolved in 1989 after a Supreme Court ruling on equal representation — but they have a budget, appoint members to community boards and the City Planning Commission, and weigh in on every ULURP application in their borough."
  },
  {
    category: "Fiscal",
    question: "When does New York City's fiscal year begin?",
    options: ["January 1", "April 1", "July 1", "October 1", "Whenever the budget actually gets passed"],
    correct: 2,
    explanation: "NYC's fiscal year runs July 1 through June 30. The City Charter requires the Mayor to submit a preliminary budget in January, the Council to negotiate, and a final adopted budget by July 1. (The funny answer is closer to true than it should be — late budgets do happen.)"
  },
  {
    category: "Legislation",
    question: "How many City Council votes are needed to override a mayoral veto?",
    options: [
      "Simple majority (26 of 51)",
      "Three-fifths (31 of 51)",
      "Two-thirds (34 of 51)",
      "Three-quarters (39 of 51)",
      "More than have ever agreed on anything in this city's history"
    ],
    correct: 2,
    explanation: "A two-thirds supermajority — 34 of 51 — is required to override a mayoral veto. In practice, vetoes are rare; the Council more often shapes legislation through negotiation with City Hall before passage. The 2024 FARE Act override was a notable recent exception."
  },
  {
    category: "Legislation",
    question: "What is the title of the leader of the New York City Council, elected by the members from among themselves?",
    options: [
      "Council President",
      "Majority Leader",
      "Speaker",
      "Chair",
      "The one who got the most other Council Members to owe them a favor"
    ],
    correct: 2,
    explanation: "The Speaker is the Council's presiding officer, chief negotiator with the Mayor, and arguably the second-most-powerful elected official in the city. Speakers control committee assignments, the legislative calendar, and a substantial share of discretionary spending. The Speaker is elected by the 51 members at the start of each term."
  },
  {
    category: "Tax",
    question: "What is the largest single source of New York City's tax revenue?",
    options: [
      "Personal income tax",
      "Property tax",
      "Sales tax",
      "Business and corporate taxes",
      "Whatever Albany lets us keep this year"
    ],
    correct: 1,
    explanation: "Property tax is by far the city's largest tax source, generating roughly a third of all tax revenue and about $35 billion a year. Personal income tax is second. The property tax system is famously inequitable — capped assessment growth on Class 1 (one- to three-family homes) shifts burden to renters and commercial owners — and reform efforts have stalled for decades."
  },
  {
    category: "Government Structure",
    question: "How is New York City's government structure usually described relative to other large U.S. cities?",
    options: [
      "Weak-mayor / strong-council",
      "Strong-mayor / strong-council",
      "City-manager",
      "Commission",
      "An ungovernable mess shaped by 400 years of grudges"
    ],
    correct: 1,
    explanation: "NYC is a strong-mayor city — the Mayor controls agencies, the budget proposal, and most appointments — but the Council is also unusually powerful by U.S. standards, with line-item budget authority, veto override capacity, and full ULURP voting rights. Most large U.S. cities have weaker councils or use a city-manager model entirely."
  },
  {
    category: "Public Safety",
    question: "What is the Civilian Complaint Review Board (CCRB)?",
    options: [
      "An NYPD unit that investigates internal misconduct",
      "An independent city agency that investigates civilian complaints of police misconduct",
      "A panel of judges who try officers accused of misconduct",
      "A volunteer community board that meets monthly",
      "A place complaints go to retire peacefully"
    ],
    correct: 1,
    explanation: 'The CCRB is an independent agency created in its current form in 1993 to investigate civilian complaints against NYPD officers — primarily for excessive force, abuse of authority, discourtesy, and offensive language. It can recommend discipline, but the Police Commissioner has final say on penalties, a tension that has produced repeated legal and political fights. <a href="https://www.nyc.gov/site/ccrb/index.page" target="_blank" rel="noopener">CCRB</a>.'
  },
  {
    category: "Charter",
    question: "What is the role of New York City's Independent Budget Office (IBO)?",
    options: [
      "Approve the Mayor's budget before it goes to the Council",
      "Provide nonpartisan fiscal analysis to the public, the Council, and other officials",
      "Audit completed city spending",
      "Issue municipal bonds",
      "Be the only people in city government who actually read the budget"
    ],
    correct: 1,
    explanation: 'The IBO is a nonpartisan publicly funded fiscal analysis office, modeled loosely on the federal CBO. It provides independent revenue forecasts, budget options, and reports on city finances and programs. Its analyses often differ from the Mayor\'s OMB estimates and are widely cited in budget fights. <a href="https://ibo.nyc.gov" target="_blank" rel="noopener">IBO</a>.'
  },
  {
    category: "Public Safety",
    question: "Roughly how many uniformed officers does the NYPD have on payroll?",
    options: ["About 12,000", "About 24,000", "About 35,000", "About 55,000", "Enough to police a small country, statistically speaking"],
    correct: 2,
    explanation: "The NYPD has roughly 33,000–36,000 uniformed officers, plus civilian employees, making it the largest municipal police force in the United States by a wide margin and larger than many national militaries. Headcount has trended down from a 40,000+ peak in the early 2000s."
  },
  {
    category: "Education",
    question: "Roughly how many students are enrolled in the New York City public school system?",
    options: ["About 400,000", "About 700,000", "About 900,000", "About 1.3 million", "Whatever the DOE reports the day before the budget hearing"],
    correct: 2,
    explanation: "The NYC Department of Education enrolls roughly 900,000 students across about 1,600 schools — by far the largest school district in the United States. Enrollment has been gradually declining for years, in part because of pandemic-era moves and the high cost of raising children in the city."
  },
  {
    category: "Land Use",
    question: "What is a community board?",
    options: [
      "A salaried citywide planning body",
      "A 50-member volunteer body that advises on land use, liquor licenses, and budget priorities for a defined neighborhood",
      "A judicial panel that hears zoning appeals",
      "An elected legislature for each neighborhood",
      "A meeting where the loudest person wins"
    ],
    correct: 1,
    explanation: "Each of the city's 59 community districts has a community board of up to 50 unpaid volunteer members appointed by the Borough President. They review ULURP applications, weigh in on liquor licenses and capital priorities, and run public hearings. Their votes are advisory, not binding — but politically meaningful."
  },
  {
    category: "Mayor's Office",
    question: "How many deputy mayors does New York City have?",
    options: ["1", "2", "Usually 4–6, varies by administration", "Exactly 10 by Charter", "However many are needed to absorb the blame"],
    correct: 2,
    explanation: "The number of deputy mayors is set by the Mayor, not the Charter, and typically lands somewhere between four and seven. Recent administrations have had deputy mayors for operations, public safety, health and human services, housing and economic development, communications, and intergovernmental affairs, with the lineup reshuffled regularly."
  },
  {
    category: "Transit",
    question: "Roughly how many subway stations does New York City have?",
    options: ["About 240", "About 330", "About 425", "About 472", "More than have working elevators"],
    correct: 3,
    explanation: 'The MTA counts 472 stations on the New York City subway system, the most of any subway in the world by a comfortable margin. London\'s Tube has about 272. Only about a quarter of NYC stations are fully ADA-accessible, a longstanding lawsuit-driving inequity. <a href="https://new.mta.info/agency/new-york-city-transit/subway-bus-ridership" target="_blank" rel="noopener">MTA</a>.'
  },
  {
    category: "Transit",
    question: "What is the MTA's biggest single funding source for its operating budget in a typical year?",
    options: [
      "Federal grants",
      "City of New York contributions",
      "Fares and tolls paid by riders and drivers",
      "State of New York general fund",
      "Magic"
    ],
    correct: 2,
    explanation: "Fares and tolls historically account for roughly 35–45% of MTA operating revenue, with dedicated taxes (payroll mobility tax, real estate transfer tax, etc.) covering most of the rest, plus state and city subsidies. Pandemic-era ridership losses opened a structural gap that congestion pricing and new state taxes were partially designed to fill."
  },
  {
    category: "Housing",
    question: "What is NYCHA?",
    options: [
      "A regulatory body that oversees private landlords",
      "The city's public housing authority",
      "A nonprofit that builds affordable housing for the city",
      "A homelessness services provider",
      "The most underfunded acronym in the five boroughs"
    ],
    correct: 1,
    explanation: 'The New York City Housing Authority owns and operates roughly 175,000 apartments housing nearly 350,000 New Yorkers — about 1 in 17 city residents. It is the largest public housing authority in North America, and faces tens of billions of dollars of unmet capital needs. <a href="https://www.nyc.gov/site/nycha/index.page" target="_blank" rel="noopener">NYCHA</a>.'
  },
  {
    category: "Housing",
    question: "What is a CityFHEPS voucher?",
    options: [
      "A federal Section 8 voucher reissued by the city",
      "A city-funded rental subsidy used to move people out of shelter or prevent eviction",
      "A construction subsidy paid to private developers",
      "A bond that finances NYCHA repairs",
      "Whatever the city decides counts this fiscal year"
    ],
    correct: 1,
    explanation: "CityFHEPS (City Fighting Homelessness and Eviction Prevention Supplement) is a city-funded rental assistance voucher administered by HRA, used both to help people exit shelter and to prevent eviction. The Council and Mayor have repeatedly fought over expansions; rules around eligibility and broker fees have shifted multiple times in recent years."
  },
  {
    category: "Public Safety",
    question: "Where does the city run its main jail complex?",
    options: ["Hart Island", "Rikers Island", "Wards Island", "Governors Island", "An island that nobody actually wants to visit"],
    correct: 1,
    explanation: 'Rikers Island, a roughly 400-acre island in the East River between Queens and the Bronx, holds the city\'s main jail complex. A Council-approved plan adopted in 2019 calls for closing Rikers and replacing it with four borough-based jails by 2027, though that deadline has slipped and remains contested. <a href="https://www.nyc.gov/site/doc/index.page" target="_blank" rel="noopener">DOC</a>.'
  },
  {
    category: "Agencies",
    question: "Which agency runs the city's homeless shelter system?",
    options: [
      "The Department of Housing Preservation and Development",
      "The Department of Homeless Services (within the Department of Social Services)",
      "The New York City Housing Authority",
      "The Human Resources Administration directly",
      "A patchwork of contractors and prayers"
    ],
    correct: 1,
    explanation: 'The Department of Homeless Services, operating within the Department of Social Services, runs the city\'s shelter system, which under the right-to-shelter mandate has grown to house tens of thousands of single adults and families on any given night. Most beds are operated by nonprofit contractors, not the city directly. <a href="https://www.nyc.gov/site/dhs/index.page" target="_blank" rel="noopener">DHS</a>.'
  },
  {
    category: "Budget",
    question: "What does OMB stand for in NYC government?",
    options: [
      "Office of Municipal Banking",
      "Office of Management and Budget",
      "Office of the Mayor's Bureau",
      "Office of Municipal Bonds",
      "Other Mostly Boring acronyms"
    ],
    correct: 1,
    explanation: "OMB — the Office of Management and Budget — is the Mayor's central budget agency. It builds the executive budget proposal, monitors agency spending, and produces the city's official revenue forecasts. It's distinct from the IBO, which is independent."
  },
  {
    category: "Elections",
    question: "What is the New York City Campaign Finance Board's matching-funds rate for small-dollar contributions to participating candidates?",
    options: [
      "$1 of public money for every $1 raised",
      "$3 of public money for every $1 raised",
      "$8 of public money for every $1 raised",
      "$25 of public money for every $1 raised",
      "Whatever it takes to outspend Cuomo"
    ],
    correct: 2,
    explanation: 'NYC\'s public matching system pays $8 in public funds for each $1 raised from city residents in small contributions, up to a per-donor cap. The system is widely credited with reducing the influence of large donors and broadening the donor base, though it does not prevent independent expenditures by super PACs. <a href="https://www.nyccfb.info" target="_blank" rel="noopener">CFB</a>.'
  },
  {
    category: "Government Structure",
    question: "Which of the following is a citywide elected office in New York City?",
    options: [
      "Sheriff",
      "Public Advocate",
      "City Clerk",
      "City Marshal",
      "The mayor's brother-in-law, occasionally"
    ],
    correct: 1,
    explanation: "There are three citywide elected offices: Mayor, Comptroller, and Public Advocate. Borough Presidents and District Attorneys are elected, but only within their boroughs. The Sheriff and City Marshals are appointed officials, despite the medieval titles."
  },
  {
    category: "Boroughs",
    question: "Which borough has the largest population?",
    options: ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Whichever one had the cheapest rent five years ago"],
    correct: 1,
    explanation: "Brooklyn has the largest population at about 2.6 million, followed by Queens (~2.3M), Manhattan (~1.6M), the Bronx (~1.4M), and Staten Island (~490,000). Queens leads in land area; Brooklyn leads in people; Manhattan leads in jobs and offices."
  },
  {
    category: "Public Safety",
    question: "What does the FDNY do besides fight fires?",
    options: [
      "Nothing significant",
      "Operate the city's emergency medical services and respond to most 911 medical calls",
      "Investigate building code violations",
      "Run the marine police force",
      "Mainly post on Instagram"
    ],
    correct: 1,
    explanation: 'The FDNY operates the city\'s 911-dispatched emergency medical services through its EMS Bureau, responding to roughly 1.5 million medical calls a year — far more than its fire calls. The bureau was created in 1996 when EMS was transferred from the Health and Hospitals Corporation. <a href="https://www.nyc.gov/site/fdny/index.page" target="_blank" rel="noopener">FDNY</a>.'
  },
  {
    category: "Tax",
    question: "Which class of property pays the lowest effective property tax rate per dollar of market value in NYC?",
    options: [
      "Class 1 (1- to 3-family homes)",
      "Class 2 (apartment buildings, co-ops, condos)",
      "Class 3 (utilities)",
      "Class 4 (commercial)",
      "Whichever class hired the best lobbyist"
    ],
    correct: 0,
    explanation: "Class 1 properties — predominantly 1- to 3-family homes — pay by far the lowest effective rate, because the law caps how fast their assessed values can grow regardless of actual market price. The result: brownstones in Park Slope often pay a fraction of the rate that a similarly valued condo across the street pays. Reform efforts have stalled for decades."
  },
  {
    category: "Land Use",
    question: "What is the difference between affordable housing built under MIH and ZQA?",
    options: [
      "MIH is voluntary; ZQA is mandatory",
      "MIH (Mandatory Inclusionary Housing) requires affordable units in rezonings; ZQA (Zoning for Quality and Affordability) eased rules to enable senior and affordable housing",
      "They are the same program",
      "MIH applies citywide; ZQA only applies in Manhattan",
      "ZQA was repealed in 2019 — trick question"
    ],
    correct: 1,
    explanation: "MIH and ZQA were a paired set of zoning changes adopted in 2016 under the de Blasio administration. MIH required permanently affordable units in many rezonings; ZQA loosened envelope and parking rules to make affordable and senior housing easier to build. Both have been amended multiple times since, including by City of Yes."
  },
  {
    category: "Charter",
    question: "What is a 'message of necessity' in NYC government?",
    options: [
      "An emergency budget request",
      "A mayoral mechanism to advance some kinds of charter or budget action faster",
      "A state-level tool that bypasses normal three-day aging of legislation, occasionally relevant to city law",
      "A formal request for a federal disaster declaration",
      "What you send when the State Senate isn't returning your calls"
    ],
    correct: 2,
    explanation: "A message of necessity is a state-government tool — used by the Governor — that allows the legislature to vote on a bill without the normal three-day aging requirement. It's relevant to city governance because much of NYC's most consequential law (rent regulation, mayoral control of schools, transit funding) is set in Albany, sometimes via fast-tracked bills."
  },
  {
    category: "Education",
    question: "Who picks the eight 'specialized' high schools' admission method, including for Stuyvesant and Bronx Science?",
    options: [
      "The Mayor",
      "The Schools Chancellor",
      "The State Legislature, by statute (the Hecht-Calandra Act)",
      "Each school's principal",
      "Whatever judge gets the latest lawsuit"
    ],
    correct: 2,
    explanation: "The Hecht-Calandra Act, passed in 1971, locked in the Specialized High Schools Admissions Test (SHSAT) as the sole admissions criterion for the original three specialized schools (Stuyvesant, Bronx Science, Brooklyn Tech). State law would need to change to alter that — a politically heavy lift that has failed repeatedly. The other five specialized schools, added later, fall under the same statutory framework."
  },
  {
    category: "Government Structure",
    question: "Which official is technically the head of city government in the Mayor's absence (e.g., out of state)?",
    options: [
      "The Comptroller",
      "The Public Advocate",
      "The Council Speaker",
      "The First Deputy Mayor (who is not in the line of succession)",
      "Whoever has the keys to the press office"
    ],
    correct: 1,
    explanation: "The Public Advocate is first in the formal line of mayoral succession; the Comptroller is second. If the Mayor leaves the state or is otherwise unable to act, executive authority briefly transfers under Charter rules. The First Deputy Mayor runs operations day-to-day but is not in the elected line of succession."
  },
  {
    category: "Elections",
    question: "What percentage of voters typically turn out for NYC mayoral primaries (Democratic primary, the de facto general)?",
    options: [
      "About 5–10%",
      "About 15–25%",
      "About 35–45%",
      "About 60%",
      "Whichever number lets the winner claim a mandate"
    ],
    correct: 1,
    explanation: "Democratic primary turnout in mayoral years usually lands in the high teens to mid-20s as a share of registered Democrats, and even lower as a share of all voting-age New Yorkers. The 2025 primary saw unusually high turnout but still well under 30% of registered Democrats — and the winner of that primary is the overwhelming favorite in the general election."
  },
  {
    category: "Public Safety",
    question: "Roughly how many people work for the city government in total (excluding contractors)?",
    options: [
      "About 100,000",
      "About 200,000",
      "About 300,000",
      "About 500,000",
      "Enough to staff a mid-sized European country"
    ],
    correct: 2,
    explanation: "The city's full-time workforce is roughly 300,000 employees across all agencies, including teachers (around 75,000), police (around 33,000), firefighters, sanitation workers, and the rest. Add MTA, NYCHA, and Health and Hospitals (separate authorities and corporations) and the broader civic workforce is well over half a million."
  },
  {
    category: "Agencies",
    question: "What does HPD do?",
    options: [
      "Runs the public hospitals",
      "Preserves historic landmarks",
      "Enforces the housing code, finances affordable housing, and inspects buildings for habitability",
      "Manages Hudson River Park",
      "Mostly hands out violations the landlord ignores"
    ],
    correct: 2,
    explanation: 'The Department of Housing Preservation and Development is the city\'s housing agency. It enforces the Housing Maintenance Code (so HPD is who you call for heat-and-hot-water complaints), finances affordable housing development, and oversees several rental subsidy programs. It is the largest municipal housing agency in the country. <a href="https://www.nyc.gov/site/hpd/index.page" target="_blank" rel="noopener">HPD</a>.'
  },
  {
    category: "Tax",
    question: "Does New York City levy its own income tax on residents?",
    options: [
      "No — only the state does",
      "Yes, on top of state income tax",
      "Only on residents earning over $1 million",
      "Only on commuters",
      "It used to, but the bond market intervened"
    ],
    correct: 1,
    explanation: "NYC residents pay a city personal income tax in addition to state income tax. Rates are graduated and add roughly 3–4 percentage points to the combined burden depending on income. The commuter tax was repealed in 1999, so non-resident commuters no longer pay city income tax."
  },
  {
    category: "Boroughs",
    question: "Which is the only borough connected to the rest of the city solely by tunnel or ferry, with no fixed rail or road bridge?",
    options: ["Manhattan", "Brooklyn", "The Bronx", "Staten Island", "The borough that politely keeps to itself"],
    correct: 3,
    explanation: 'Staten Island connects to the rest of New York City only via the Verrazzano-Narrows Bridge (to Brooklyn) — but that\'s tolled by the MTA, and there is no direct subway link. The Staten Island Ferry to Manhattan and the SI Railway are the main mass-transit links. Geographically, Staten Island is closer to New Jersey, to which it is connected by three free bridges. <a href="https://www.siferry.com" target="_blank" rel="noopener">SI Ferry</a>.'
  },
  {
    category: "Government Structure",
    question: "How is the New York City Charter amended?",
    options: [
      "By a simple Council majority",
      "By a Council supermajority",
      "By voter referendum after recommendations from a Charter Revision Commission, or sometimes by state law",
      "By executive order",
      "By a ceremony involving an old typewriter and a pigeon"
    ],
    correct: 2,
    explanation: "Most Charter changes go on the ballot for voter approval, after being recommended by a Charter Revision Commission appointed by the Mayor or, less commonly, the Council. Some provisions can also be changed by state law, since cities are creatures of the state under New York's constitutional structure."
  },
  {
    category: "Public Safety",
    question: "What is the Mayor's Management Report?",
    options: [
      "A weekly memo from the Mayor to the Council",
      "An annual public report card on the performance of every major city agency",
      "A confidential audit of mayoral staff",
      "An internal monthly cabinet briefing",
      "Where bad metrics go to be quietly buried"
    ],
    correct: 1,
    explanation: 'The Mayor\'s Management Report (MMR), required by the Charter, is published twice a year (preliminary in January, final in September) and tracks key performance indicators across every major city agency — from average 311 response time to overtime spending to permit issuance speed. It\'s one of the most useful single documents on how city government is actually performing. <a href="https://www.nyc.gov/site/operations/performance/mmr.page" target="_blank" rel="noopener">MMR</a>.'
  },
  {
    category: "Charter",
    question: "Which city official is the city's chief lawyer and is appointed by the Mayor?",
    options: [
      "The Chief Justice of the Civil Court",
      "The Corporation Counsel (head of the Law Department)",
      "The Public Advocate",
      "The District Attorney",
      "Whoever can read a 200-page brief without crying"
    ],
    correct: 1,
    explanation: "The Corporation Counsel heads the city's Law Department and serves as the city's chief legal officer — defending the city in lawsuits, advising agencies, and prosecuting some matters in family court and civil enforcement. The Corporation Counsel is appointed by the Mayor with Council advice and consent."
  }
];

export const BONUS_QUESTIONS = [
  {
    category: "Bonus: Charter",
    question: "What body, abolished in 1989, used to share land-use and budget power with the Mayor and was struck down by the Supreme Court for violating one-person-one-vote?",
    options: [
      "The Board of Aldermen",
      "The Board of Estimate",
      "The Tammany Council",
      "The City Commission",
      "The League of Annoyed Borough Presidents"
    ],
    correct: 1,
    explanation: "The Board of Estimate was a body of eight officials — the Mayor, Comptroller, Council President, and five Borough Presidents — that approved the city budget and land-use decisions. The Supreme Court unanimously struck it down in Morris v. Board of Estimate (1989) because Brooklyn (2.3 million residents) and Staten Island (350,000) had identical voting weight. The 1989 Charter revision dissolved it and expanded the Council's power."
  },
  {
    category: "Bonus: Agencies",
    question: "Which obscure city body must approve all major contracts (such as school busing) for the Department of Education and is appointed mostly by the Mayor and the Borough Presidents?",
    options: [
      "The Procurement Policy Board",
      "The Panel for Educational Policy",
      "The School Construction Authority",
      "The Board of Standards and Appeals",
      "An exhausted PTA"
    ],
    correct: 1,
    explanation: "The Panel for Educational Policy replaced the old Board of Education in 2002. It has 23 members — most appointed by the Mayor — and votes on major DOE contracts. PEP meetings sometimes become flashpoints when the Mayor's appointees are pressured to defy City Hall on controversial votes."
  },
  {
    category: "Bonus: Land Use",
    question: "The Board of Standards and Appeals (BSA) primarily does what?",
    options: [
      "Sets the city's zoning rules",
      "Hears appeals from DOB decisions and grants zoning variances and special permits",
      "Approves citywide rezonings",
      "Inspects elevators and boilers",
      "Reminds you that 'as-of-right' is a state of mind"
    ],
    correct: 1,
    explanation: "The BSA is a five-member quasi-judicial body that hears appeals from Department of Buildings determinations and grants zoning variances, special permits, and other relief from the strict application of the Zoning Resolution. It is one of the last places a property owner can go when DOB says no."
  },
  {
    category: "Bonus: Tax",
    question: "What is the New York State constitutional cap on the city's general real-property tax levy, expressed as a percentage of the five-year average full value of taxable real estate?",
    options: ["1.5%", "2.0%", "2.5%", "3.0%", "Whatever the bond market will tolerate"],
    correct: 2,
    explanation: "The State Constitution caps the city's general property tax levy at 2.5% of the five-year average full value of taxable real estate. Debt service is exempt from the cap. The city has at times been close to the limit, which can constrain new revenue from property tax — a major reason periodic discussions of expanding the tax base or reforming the assessment system come up."
  },
  {
    category: "Bonus: Legal",
    question: "Which city commission investigates discrimination claims, and what standard of proof does it apply?",
    options: [
      "NYCCHR; preponderance of the evidence",
      "COIB; beyond a reasonable doubt",
      "DOI; clear and convincing evidence",
      "BSA; substantial evidence",
      "Their gut feeling, mostly"
    ],
    correct: 0,
    explanation: 'The NYC Commission on Human Rights enforces one of the strongest anti-discrimination laws in the country, using the "preponderance of the evidence" standard — i.e., more likely than not. Its source-of-income protection (which makes it illegal to refuse housing-voucher holders) is among the most contested and litigated provisions. <a href="https://www.nyc.gov/site/cchr/index.page" target="_blank" rel="noopener">CCHR</a>.'
  },
  {
    category: "Bonus: Ethics",
    question: "Which city agency enforces conflict-of-interest rules on city employees, including financial disclosure and outside-employment limits?",
    options: [
      "The Department of Investigation",
      "The Conflicts of Interest Board",
      "The Office of the Inspector General",
      "The Law Department",
      "Whoever's reading the Daily News that morning"
    ],
    correct: 1,
    explanation: 'The Conflicts of Interest Board (COIB) is a five-member body that enforces Chapter 68 of the Charter — the city ethics law. It issues advisory opinions, requires annual financial disclosure from senior officials, and can fine employees up to $25,000 per violation. It operates separately from DOI, which investigates corruption. <a href="https://www.nyc.gov/site/coib/index.page" target="_blank" rel="noopener">COIB</a>.'
  },
  {
    category: "Bonus: Charter",
    question: "Roughly how many community boards are there in New York City?",
    options: ["12", "32", "59", "100", "One per neighborhood that thinks it's special, so all of them"],
    correct: 2,
    explanation: "There are 59 community boards — 12 in Manhattan and the Bronx, 18 in Brooklyn, 14 in Queens, and 3 in Staten Island. Each has up to 50 unpaid volunteer members appointed by the Borough President (with half nominated by the Council Member). They review ULURP applications, advise on liquor licenses, and weigh in on the local capital budget. Their votes are advisory, not binding."
  },
  {
    category: "Bonus: History",
    question: "What was Tammany Hall, and when did it last meaningfully control New York City government?",
    options: [
      "An 18th-century fraternal society that ended before the city consolidated",
      "A Democratic Party political machine that dominated city politics for over a century, finally broken in the 1960s",
      "A Republican-aligned reform organization of the Progressive Era",
      "An organized-crime syndicate, never a formal political party",
      "Whatever the Times's editorial board says it is this week"
    ],
    correct: 1,
    explanation: "Tammany Hall was the political machine that dominated New York City Democratic politics from the early 19th century through the mid-20th. Its grip survived the indictment of Boss Tweed (1873), the LaGuardia reform era (1930s), and many lesser shocks before finally crumbling in the 1960s after a series of federal corruption prosecutions and reform-era charter changes."
  },
  {
    category: "Bonus: Charter",
    question: "What is the 'message of necessity' from the State Senate, and why does it matter for NYC?",
    options: [
      "A formal request for federal disaster aid",
      "A Governor's note allowing the legislature to pass a bill before the standard three-day aging period",
      "A required filing whenever a city law conflicts with state law",
      "A petition to the Court of Appeals for emergency review",
      "The state's polite way of saying 'good luck'"
    ],
    correct: 1,
    explanation: "Many of the most consequential laws governing NYC — rent regulation, mayoral control of schools, transit funding, congestion pricing — are enacted in Albany. A 'message of necessity' from the Governor lets the legislature waive the three-day aging period and pass a bill immediately, a tool used (and sometimes abused) at the end of legislative sessions when negotiations slip past deadlines."
  },
  {
    category: "Bonus: History",
    question: "Five separate counties consolidated into New York City in 1898. Which county is NOT one of them?",
    options: [
      "New York County (Manhattan)",
      "Kings County (Brooklyn)",
      "Hudson County (parts of New Jersey)",
      "Richmond County (Staten Island)",
      "Westchester County, before the Bronx was carved out"
    ],
    correct: 2,
    explanation: 'The 1898 consolidation merged New York County (Manhattan), Kings (Brooklyn), Queens (the western part — eastern Queens became Nassau County in 1899), Richmond (Staten Island), and the western part of Westchester (which became the Bronx). Hudson County is in New Jersey and was never part of the consolidation, despite Jersey City being closer to Lower Manhattan than parts of Brooklyn. <a href="https://www.nyc.gov/site/nyc100/index.page" target="_blank" rel="noopener">History</a>.'
  },
  {
    category: "Bonus: Government Structure",
    question: "Which official heads the city's Office of Administrative Trials and Hearings (OATH)?",
    options: [
      "An elected commissioner",
      "The Chief Administrative Law Judge, appointed by the Mayor",
      "A panel of three rotating Borough Presidents",
      "The Corporation Counsel",
      "Whoever drew the short straw at the Law Department"
    ],
    correct: 1,
    explanation: "OATH is the city's central, independent administrative tribunal — it adjudicates summonses from agencies like Sanitation, DEP, and the Health Department, plus employee disciplinary cases. The Chief Administrative Law Judge runs OATH and is appointed by the Mayor. It hears more than 700,000 cases a year, more than most state court systems."
  }
];
