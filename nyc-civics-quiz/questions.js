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
    explanation: 'The Council has 51 members, each representing a district of roughly 173,000 people. The body was expanded to 51 by the 1989 Charter revision (post-Morris v. Board of Estimate), with the new lines first elected in 1991, after Voting Rights Act litigation forced districts that better reflected the city\'s demographics. <a href="https://council.nyc.gov" target="_blank" rel="noopener">Council</a>.'
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
    explanation: 'The Department of Investigation traces back to 1873, when post-Tweed reformers created the Office of the Commissioners of Accounts; the 1938 Charter revision renamed it DOI and gave it its current form as the city\'s independent inspector general. It investigates fraud, corruption, and misconduct across every city agency, and works alongside NYPD\'s Internal Affairs Bureau. The DOI Commissioner is appointed by the Mayor but the agency operates with structural independence. <a href="https://www.nyc.gov/site/doi/index.page" target="_blank" rel="noopener">DOI</a>.'
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
    explanation: 'The Fairness in Apartment Rentals (FARE) Act passed the Council 42–8 in November 2024. Mayor Adams declined to sign or veto it, so it became law by inaction in mid-December and took effect June 2025. It ended the longstanding NYC practice of forcing tenants to pay a broker\'s commission (often 12–15% of annual rent) when the landlord — not the tenant — hired the broker. Real estate industry groups sued; the law has largely held up. <a href="https://council.nyc.gov" target="_blank" rel="noopener">Council</a>.'
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
    explanation: "The Public Advocate is a citywide elected official who serves as a watchdog over city agencies, fields citizen complaints, introduces legislation in the City Council (without a vote), and is first in line of mayoral succession. The 1989 Charter revision created the role and put it first in the line of succession; in 1993 the title was renamed from \"President of the Council\" to \"Public Advocate.\""
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
    explanation: 'NYCHA owns and operates roughly 175,000 apartments housing nearly 350,000 New Yorkers — about 1 in 16 New Yorkers when you include Section 8 voucher holders NYCHA also administers — making it by far the largest public housing authority in North America. Any city-led "social housing" expansion either builds on NYCHA, on HPD-financed mixed-income development, or on a new entity created for the purpose. Mamdani\'s plan leans toward a new public developer plus aggressive use of the city\'s land and capital budget.'
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
    options: ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island", "Whichever one you're trying to leave at the moment"],
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
    explanation: "The Comptroller is the city's chief financial officer. The office audits agencies, oversees roughly $295 billion in city pension fund assets, registers contracts, and reviews the city's fiscal health. It is one of three citywide elected offices, along with Mayor and Public Advocate."
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
    explanation: 'The 311 system, launched under Bloomberg in 2003, is the city\'s non-emergency hotline and online portal for everything from noise complaints to pothole reports to lost-property questions. It handles nearly 40 million contacts a year and generates one of the city\'s most-used open datasets. <a href="https://portal.311.nyc.gov" target="_blank" rel="noopener">311</a>.'
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
    explanation: "NYC's fiscal year runs July 1 through June 30. The City Charter requires the Mayor to submit a preliminary budget in January, the Council to negotiate, and a final adopted budget by June 5 — well before the July 1 fiscal year start. (The funny answer is closer to true than it should be — handshake deals just before the deadline are a recurring tradition.)"
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
    explanation: "A two-thirds supermajority — 34 of 51 — is required to override a mayoral veto. In practice, vetoes are rare; the Council more often shapes legislation through negotiation with City Hall before passage. The Council\'s January 2024 override of Mayor Adams\'s vetoes of the How Many Stops Act and the solitary-confinement ban was a notable recent example."
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
    explanation: "The NYPD has about 35,000 uniformed officers, plus civilian employees, making it the largest municipal police force in the United States by a wide margin and larger than many national militaries. Headcount fell into the low 30,000s after pandemic-era attrition; a recent hiring push aims to bring it back to the high 30,000s."
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
    explanation: "Each of the city's 59 community districts has a community board of up to 50 unpaid volunteer members appointed by the Borough President — half of them on the nomination of local Council Members. They review ULURP applications, weigh in on liquor licenses and capital priorities, and run public hearings. Their votes are advisory, not binding — but politically meaningful."
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
    explanation: 'The New York City Housing Authority owns and operates roughly 175,000 apartments housing nearly 350,000 New Yorkers — about 1 in 16 New Yorkers when you include Section 8 voucher holders NYCHA also administers. It is the largest public housing authority in North America, and faces tens of billions of dollars of unmet capital needs. <a href="https://www.nyc.gov/site/nycha/index.page" target="_blank" rel="noopener">NYCHA</a>.'
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
    options: ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island", "Whichever one had the cheapest rent five years ago"],
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
    question: "Who controls the admissions method at Stuyvesant, Bronx Science, and Brooklyn Tech?",
    options: [
      "The Mayor",
      "The Schools Chancellor",
      "The State Legislature, by statute (the Hecht-Calandra Act)",
      "Each school's principal",
      "Whatever judge gets the latest lawsuit"
    ],
    correct: 2,
    explanation: "The Hecht-Calandra Act, passed in 1971, locked in the Specialized High Schools Admissions Test (SHSAT) as the sole admissions criterion for the three named schools — Stuyvesant, Bronx Science, and Brooklyn Tech. Changing their admissions requires Albany, a politically heavy lift that has failed repeatedly. The other five specialized schools (Brooklyn Latin, HSMSE at CCNY, HSAS at Lehman, Queens HS for the Sciences, and Staten Island Tech) were designated by the city and use the SHSAT by city policy, not state law — meaning the Mayor and Chancellor can change their admissions without Albany."
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
    question: "Which is the only borough with no subway connection to the rest of New York City?",
    options: ["Manhattan", "Brooklyn", "The Bronx", "Staten Island", "The borough that politely keeps to itself"],
    correct: 3,
    explanation: 'Staten Island is the only borough not on the New York City subway map. Its main links to the rest of the city are the free Staten Island Ferry to Lower Manhattan and the Verrazzano-Narrows Bridge to Brooklyn (tolled by the MTA). The Staten Island Railway runs the length of the borough but is internal — it connects to the ferry terminal, not to the subway. Geographically, Staten Island is closer to New Jersey, to which it is connected by three free bridges. <a href="https://www.siferry.com" target="_blank" rel="noopener">SI Ferry</a>.'
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
    explanation: "The Corporation Counsel heads the city's Law Department and serves as the city's chief legal officer — defending the city in lawsuits, advising agencies, and prosecuting some matters in family court and civil enforcement. The Corporation Counsel is appointed by the Mayor; since a 2019 Charter amendment, the appointment requires Council advice and consent."
  },
  {
    category: "Land Use",
    question: "If a Council Member opposes a rezoning in their own district, what usually happens?",
    options: [
      "The Council overrides them and approves it anyway",
      "The Council typically defers to them and votes the project down — an unwritten norm called member deference",
      "The Mayor can veto the Council Member's objection",
      "The Borough President casts a tiebreaking vote",
      "The project gets approved at half the size as a compromise nobody wanted"
    ],
    correct: 1,
    explanation: "Member deference (sometimes called \"member item\" courtesy) is the unwritten Council convention that the body votes the way the affected district\'s Council Member wants on land-use items in their district. It is not in the Charter. Critics blame it for blocking housing in wealthy districts; defenders call it democratic localism. City of Yes was one of the rare modern citywide rezonings that worked around it by being citywide rather than parcel-specific."
  },
  {
    category: "Elections",
    question: "Roughly how much money did Andrew Cuomo and the super PACs supporting him spend in the 2025 Democratic mayoral primary, before losing to Mamdani?",
    options: [
      "Around $5 million",
      "Around $15 million",
      "Around $25 million",
      "More than $35 million",
      "Enough to make every TV ad you saw last June feel like a personal grudge"
    ],
    correct: 3,
    explanation: "Cuomo\'s campaign and the affiliated Fix the City super PAC together spent more than $35 million in the primary — by far the most expensive Democratic primary for any office in NYC history. Mamdani\'s campaign spent a small fraction of that and qualified for matching funds at the city\'s 8-to-1 rate, which under NYC law cannot flow to super PACs. The race became a textbook case for proponents of public financing."
  },
  {
    category: "Government Structure",
    question: "Which of the following positions is filled by a competitive civil-service exam, not by mayoral appointment?",
    options: [
      "Police Commissioner",
      "Sanitation Commissioner",
      "Most uniformed sergeants, lieutenants, and captains in the NYPD and FDNY",
      "Schools Chancellor",
      "Whoever the Mayor\'s donor lunch was last Tuesday"
    ],
    correct: 2,
    explanation: "Most rank-and-file and supervisory civil-service positions in NYC — including the uniformed promotional ranks at NYPD and FDNY — are filled through competitive exams under New York State civil-service law, with hiring lists ranked by score. The agency heads (Commissioner, Chancellor) are political appointees of the Mayor; the people doing the actual day-to-day work mostly aren\'t."
  },
  {
    category: "Public Safety",
    question: "What is the legal status of New York City\'s \"right to shelter\"?",
    options: [
      "A right written into the U.S. Constitution",
      "A right written into New York State law",
      "A right established by a 1981 consent decree (Callahan v. Carey) that the city has been bound to ever since",
      "A right granted by City Council legislation in 2003",
      "A polite suggestion, depending on the mayor"
    ],
    correct: 2,
    explanation: "The right to shelter for single homeless men was established by the Callahan v. Carey consent decree in 1981, after a Coalition for the Homeless lawsuit; subsequent court rulings extended it to women and families. It is a court-enforced obligation specific to NYC — neither the U.S. nor New York State guarantees a right to shelter generally. The Adams administration successfully negotiated some flexibility around the decree during the migrant influx; advocates argue it remains binding."
  },
  {
    category: "Tax",
    question: "What is the \"421-a\" tax abatement (recently replaced by \"485-x\") best known for?",
    options: [
      "Capping property tax bills for one-to-three-family homes",
      "A multi-decade property tax break for new multifamily rental construction, conditioned on affordability requirements",
      "A sales tax holiday for purchases under $110",
      "A small-business commercial rent tax exemption",
      "Whichever loophole Crain\'s wrote about most recently"
    ],
    correct: 1,
    explanation: "421-a (named for its section in the Real Property Tax Law) was a state-authorized property tax exemption used for the bulk of new rental construction in NYC for decades. It expired in 2022 and was replaced in 2024 by 485-x (\"Affordable Neighborhoods for New Yorkers\"), with stricter affordability and wage requirements. Both programs are set in Albany — the city can\'t change them on its own — and both are central to any NYC housing-supply debate."
  },

  // ---------- Mamdani administration: first 4.5 months ----------

  {
    category: "Mamdani Watch",
    question: "Who is Mayor Mamdani's NYPD Commissioner?",
    options: [
      "He named a new commissioner from outside NYPD",
      "Jessica Tisch — he kept Adams's commissioner",
      "He elevated the NYPD Chief of Department to commissioner",
      "The post is vacant pending Council confirmation",
      "Whoever was willing to take the job and the press conferences"
    ],
    correct: 1,
    explanation: "In one of the most-watched personnel decisions of the transition, Mamdani retained Jessica Tisch — the Adams-era NYPD Commissioner — over loud objections from parts of his left base. Tisch and Mamdani jointly announced in early February 2026 that January had set a modern record low for shootings (40) and murders (12)."
  },
  {
    category: "Mamdani Watch",
    question: "What was Mayor Mamdani's literal first official act on January 1, 2026?",
    options: [
      "Signing an executive order on rent stabilization",
      "Riding the M15 bus to Gracie Mansion",
      "Naming Mike Flynn as DOT Commissioner",
      "Issuing a sanctuary city executive order",
      "Posting a TikTok"
    ],
    correct: 2,
    explanation: "Mamdani's first formal act as mayor was announcing Mike Flynn as Department of Transportation Commissioner. The signal: streets, buses, and bike infrastructure — the DOT portfolio — would be early administration priorities."
  },
  {
    category: "Mamdani Watch",
    question: "Mamdani's Executive Order 1, signed January 1, 2026, did what?",
    options: [
      "Froze all city hiring",
      "Revoked all Eric Adams executive orders signed after his September 2024 federal indictment",
      "Declared a citywide housing emergency",
      "Ordered fare-free buses to start on January 5",
      "Renamed Gracie Mansion 'The People's House'"
    ],
    correct: 1,
    explanation: "EO 1 wiped out every executive order Adams signed after his federal indictment, including the order banning city contracts with firms that boycott Israel and the order adopting the IHRA antisemitism definition. The legal theory: a mayor under indictment shouldn't be making major policy via fiat in his lame-duck months."
  },
  {
    category: "Mamdani Watch",
    question: "Did Mamdani's appointed Rent Guidelines Board freeze stabilized-apartment rents in their May 2026 preliminary vote?",
    options: [
      "Yes — a clean 0% freeze on both one- and two-year leases",
      "No — they passed double-digit increases anyway",
      "They voted a preliminary range of 0–2% for one-year leases and 0–4% for two-year leases; the final vote is in June",
      "They tabled the vote indefinitely",
      "They froze rents only in zip codes that voted for Mamdani"
    ],
    correct: 2,
    explanation: "On May 7, 2026, the Mamdani-appointed RGB majority set a preliminary range of 0–2% for one-year leases and 0–4% for two-year leases — the lowest preliminary range in years, but not the clean freeze Mamdani had promised on the campaign trail. The final binding vote comes in late June."
  },
  {
    category: "Mamdani Watch",
    question: "What happened to Mamdani's signature campaign promise of citywide fare-free buses?",
    options: [
      "It launched on January 5, 2026, citywide",
      "It launched on all express buses only",
      "It was scaled back to a 3-routes-per-borough pilot, plus a separate proposed free-bus program for the 5-week FIFA World Cup",
      "It was abandoned entirely after MTA refused",
      "It launched, but only on the buses MTA was already going to retire"
    ],
    correct: 2,
    explanation: "The citywide free-bus pledge collided with the MTA's state control over fares. Mamdani's administration pivoted to a roughly $45M, three-routes-per-borough pilot plus a separate ~$100M proposal for fully free buses during the 2026 FIFA World Cup. MTA Chair Janno Lieber publicly said no one had spoken to him about the World Cup plan when reporters asked."
  },
  {
    category: "Mamdani Watch",
    question: "Where is the first city-owned grocery store, announced in April 2026, going to open?",
    options: [
      "Co-op City, the Bronx",
      "East New York, Brooklyn",
      "La Marqueta in East Harlem, Manhattan",
      "Far Rockaway, Queens",
      "Wherever the bodega association sued first"
    ],
    correct: 2,
    explanation: "On April 13, 2026, Mamdani announced La Marqueta in East Harlem — already a city-owned public market under EDC — as the site of the first 9,000-square-foot city-owned grocery store, with construction projected at roughly $30 million and opening in late 2027 or 2028. Plans call for one store per borough."
  },
  {
    category: "Mamdani Watch",
    question: "Mamdani campaigned on ending mayoral control of NYC public schools. What did he do once in office?",
    options: [
      "Followed through and asked Albany to end mayoral control",
      "Tried to end it but was blocked by the Council",
      "Reversed the position and asked the State Legislature to extend mayoral control",
      "Ended it unilaterally by executive order",
      "Outsourced the question to a panel of teenagers"
    ],
    correct: 2,
    explanation: "On December 31, 2025, alongside naming Kamar Samuels as Schools Chancellor, Mamdani announced he was reversing his campaign pledge and would ask Albany to extend mayoral control of schools. Education advocates split: some saw a betrayal, others saw governing pragmatism."
  },
  {
    category: "Mamdani Watch",
    question: "What did Mamdani do about homeless encampment sweeps after taking office?",
    options: [
      "Ended them permanently on day one",
      "Ended them on January 5, then resumed them on February 18 after a cold-snap death toll, this time run by DHS instead of NYPD with 7-day notice",
      "Continued the Adams-era sweep policy unchanged",
      "Replaced sweeps with a guaranteed-shelter offer that homeless New Yorkers could refuse",
      "Held a press conference about ending them but never actually did"
    ],
    correct: 1,
    explanation: "Mamdani paused encampment sweeps January 5, 2026. After roughly 20 New Yorkers died during a January cold snap, he resumed them on February 18 — but with the operation moved from NYPD to the Department of Homeless Services and a 7-day notice requirement. The reversal was one of the administration's most contentious early moments."
  },
  {
    category: "Mamdani Watch",
    question: "What happened with the city's lawsuit over expanding CityFHEPS housing vouchers?",
    options: [
      "Mamdani dropped the lawsuit on day one as promised",
      "Mamdani's administration appealed the court order requiring the expansion in March 2026, citing a $4 billion-plus annual cost",
      "The Council overrode the Mayor and dropped the suit",
      "The Court of Appeals ended the case before Mamdani took office",
      "It was settled with a coupon"
    ],
    correct: 1,
    explanation: "Mamdani had pledged on the trail to drop the city's appeal of the Council's CityFHEPS expansion law. In March 2026 his administration did the opposite — appealing the lower-court order requiring the expansion, citing a projected $4 billion-plus annual cost. Tenant advocates were furious; budget hawks argued it was responsible."
  },
  {
    category: "Mamdani Watch",
    question: "Mamdani's preliminary FY2027 budget assumed a 9.5% property tax rate increase. What ended up in his executive budget released May 12, 2026?",
    options: [
      "The same 9.5% property tax hike",
      "A larger property tax hike to close the gap",
      "No property tax hike, plus a new pied-à-terre tax on luxury second homes projected to raise around $500 million",
      "A repeal of the Class 1 cap on assessed-value growth",
      "A hike that exempted Park Slope on the grounds of vibes"
    ],
    correct: 2,
    explanation: "After backlash to the February preliminary budget, Mamdani dropped the property tax rate increase from his executive budget and instead proposed a pied-à-terre tax on luxury second homes — projected at roughly $500 million annually. The pied-à-terre tax requires Albany approval and has failed there before."
  },
  {
    category: "Mamdani Watch",
    question: "How much additional state aid did Governor Hochul commit to NYC alongside Mamdani's May 2026 executive budget?",
    options: [
      "Zero — Hochul refused to provide additional aid",
      "Roughly $500 million one-time",
      "Roughly $4 billion in additional aid (totaling nearly $8 billion over two years), paired with cuts to programs like CityFHEPS and special-ed tuition reimbursement",
      "A blanket assumption of MTA debt service",
      "Whatever was left over after the upstate canal budget"
    ],
    correct: 2,
    explanation: "The Hochul-Mamdani deal announced alongside the May 2026 executive budget brought roughly $4 billion in additional state aid (nearly $8 billion over two years), paired with cuts to fast-growing city programs. The deal is widely read as a working detente between the city's left-flank mayor and a centrist governor with her own 2026 reelection on the horizon."
  },
  {
    category: "Mamdani Watch",
    question: "Mamdani's new Office of Community Safety launched March 19, 2026. How does its first-year funding compare with what he proposed on the campaign trail?",
    options: [
      "Larger — about $1.5 billion",
      "About the same as promised — roughly $1.1 billion",
      "Far smaller — about $260 million, with only 2 staff at launch",
      "Funded entirely by federal grants",
      "Funded by a GoFundMe his press shop is too embarrassed to acknowledge"
    ],
    correct: 2,
    explanation: "Mamdani had pitched roughly $1.1 billion for a Department of Community Safety to handle mental-health and homelessness calls outside the NYPD. The office that actually launched in March 2026 — under Deputy Mayor Renita Francois — opened with about $260 million and 2 staff. Critics call it a fig leaf; supporters call it realistic phasing."
  },
  {
    category: "Mamdani Watch",
    question: "How many times had Mamdani met with President Trump at the White House by April 2026?",
    options: [
      "Zero",
      "Once",
      "Twice — November 21, 2025 and February 26, 2026",
      "Four times",
      "He's blocked, but a friend of a friend got a message through"
    ],
    correct: 2,
    explanation: "Mamdani met with Trump at the White House twice: November 21, 2025 (between the election and his inauguration) and February 26, 2026. Both meetings were described as cordial. At the February meeting, Mamdani pitched a $21 billion federal grant for 12,000 housing units in Queens and gave Susie Wiles a list of pro-Palestinian student detainees to consider for release."
  },
  {
    category: "Mamdani Watch",
    question: "Mamdani's February 6, 2026 sanctuary executive order did what?",
    options: [
      "Banned all federal law enforcement from entering NYC",
      "Barred federal immigration agents from entering city-owned property without a judicial warrant; designated schools, hospitals, and shelters as protected; ordered an audit of sanctuary compliance",
      "Repealed every Bloomberg-era cooperation agreement with ICE",
      "Required city employees to interfere physically with ICE arrests",
      "Renamed ICE 'The Federal People We Don't Talk To'"
    ],
    correct: 1,
    explanation: "The February 6, 2026 sanctuary EO barred federal immigration agents from entering city-owned property without a judicial warrant and designated schools, hospitals, and shelters as protected. The Department of Homeland Security responded by demanding NYC turn over more than 7,000 immigrants in city custody with active detainers."
  },
  {
    category: "Mamdani Watch",
    question: "How did the Mamdani administration respond to two major snowstorms in January and February 2026?",
    options: [
      "Closed the city for a week and called in the National Guard",
      "Was caught flat-footed and lost two Sanitation Commissioners",
      "Declared a local state of emergency, closed schools, raised emergency snow-shoveler pay to $30/hour, deployed about 2,600 sanitation workers per shift, and cleared 2,200 bus stops",
      "Outsourced cleanup to a private contractor that immediately went bankrupt",
      "Tweeted through it"
    ],
    correct: 2,
    explanation: "The administration's snow response — particularly to Winter Storm Fern (Jan 25–26, 2026) and the February 22–24 blizzard — got generally favorable reviews. Mamdani raised emergency snow-shoveler pay to $30/hour, deployed roughly 2,600 sanitation workers per shift, and made bus-stop clearance an explicit priority for the first time."
  },
  {
    category: "Mamdani Watch",
    question: "What was the Williamsburg Bridge 'Zohramp,' completed January 6, 2026?",
    options: [
      "A new pedestrian-only entrance on the Manhattan side",
      "A long-stalled accessibility ramp upgrade for cyclists, completed in Mamdani's first week",
      "A literal ramp built so the Mayor could film a campaign-style video",
      "A truck-restriction lane",
      "Whatever the New York Post needed a one-word slur for"
    ],
    correct: 1,
    explanation: "The 'Zohramp' was the community nickname for a long-stalled cyclist accessibility ramp on the Williamsburg Bridge that DOT completed in Mamdani's first week. It became an early viral signal that the new administration was actually going to build small things quickly."
  },
  {
    category: "Mamdani Watch",
    question: "Who is Steven Banks, named to a key Mamdani cabinet role and confirmed by the Council in February 2026?",
    options: [
      "Schools Chancellor",
      "Police Commissioner",
      "Corporation Counsel — the city's chief legal officer and head of the Law Department",
      "Sanitation Commissioner",
      "The mayor's apparently very patient press secretary"
    ],
    correct: 2,
    explanation: "Steven Banks — a longtime legal-aid lawyer who later served as Human Resources Administration Commissioner under de Blasio — was named Corporation Counsel and confirmed by the Council in February 2026. The pick signaled the administration's intent to use the Law Department aggressively on tenant and immigration issues."
  },
  {
    category: "Mamdani Watch",
    question: "What was Mamdani's approval rating in the early-April 2026 Marist poll, after roughly 100 days in office?",
    options: [
      "About 25% approve, 60% disapprove",
      "About 35% approve, 50% disapprove",
      "About 48% approve, 30% disapprove",
      "About 65% approve, 20% disapprove",
      "However many people answered the phone that week"
    ],
    correct: 2,
    explanation: "An early-April 2026 Marist poll put Mamdani at 48% approve / 30% disapprove, with a 55% positive personal favorability rating and 33% unfavorable. Solid for a polarizing first-term mayor, but well below his honeymoon ceiling."
  },
  {
    category: "Mamdani Watch",
    question: "Mamdani's first 4.5 months in office included new mayor's offices for which of the following?",
    options: [
      "Just one — Community Safety",
      "Mass Engagement, LGBTQIA+ Affairs, Community Safety, and Deed Theft Prevention — four new mayor's offices, plus a reestablished Office to Protect Tenants",
      "Only one new office, but he renamed five existing ones",
      "None — he froze all new agency creation",
      "An Office of Vibes (acting director: TBD)"
    ],
    correct: 1,
    explanation: "Mamdani used executive orders to stand up new mayor's offices for Mass Engagement (Jan 2), Community Safety (March 19), LGBTQIA+ Affairs (March 13), and Deed Theft Prevention (April 24), and reestablished the Mayor's Office to Protect Tenants. Critics called it bureaucratic proliferation; supporters called it organizing capacity around campaign priorities."
  },
  // ---------- Analogy / compare-and-contrast ---------- //

  {
    category: "Compare & Contrast",
    question: "If the President of the United States is roughly analogous to the Mayor of NYC, who is the closest federal analogue to the Speaker of the City Council?",
    options: [
      "The Vice President",
      "The Senate Majority Leader",
      "The Speaker of the U.S. House of Representatives",
      "The White House Chief of Staff",
      "Whoever leaks fastest to Politico"
    ],
    correct: 2,
    explanation: "Both Speakers are the elected presiding officer of the legislative chamber, control the calendar and committee assignments, negotiate directly with the executive, and command an independent power base. The analogy isn't perfect — the U.S. House Speaker is third in presidential succession, while the NYC Council Speaker is not in mayoral succession — but functionally they play the same role."
  },
  {
    category: "Compare & Contrast",
    question: "Congress has the Congressional Budget Office for independent fiscal analysis. NYC has its closest analogue in which body?",
    options: [
      "The Office of Management and Budget (OMB)",
      "The Independent Budget Office (IBO)",
      "The Comptroller's Bureau of Budget",
      "The Citizens Budget Commission",
      "Whoever the New York Times's metro desk is talking to that day"
    ],
    correct: 1,
    explanation: "The Independent Budget Office was created in the 1989 Charter revision and explicitly modeled on the federal CBO: nonpartisan, publicly-funded, separate from the Mayor's OMB, and tasked with producing independent revenue forecasts and policy analyses. Its numbers regularly diverge from OMB's — and Council members frequently cite IBO when negotiating with City Hall."
  },
  {
    category: "Compare & Contrast",
    question: "If the Mayor is roughly analogous to the President, who in NYC plays the role most similar to the Vice President — first in line of succession, limited day-to-day formal power, often used as a watchdog or platform?",
    options: [
      "The Comptroller",
      "The Public Advocate",
      "The City Council Speaker",
      "The First Deputy Mayor",
      "The mayor's most-quoted critic on cable, automatically"
    ],
    correct: 1,
    explanation: "The Public Advocate is first in mayoral succession (the Comptroller is second) and has structurally limited day-to-day power: they can introduce Council legislation but not vote on it, can field complaints, and can run citywide investigations. The role often functions as a launching pad for higher office — Bill de Blasio and Letitia James both became Mayor (de Blasio) and State AG (James) from it."
  },
  {
    category: "Compare & Contrast",
    question: "The Federal Reserve sets interest rates. The closest NYC analogue — an independent expert-political board that sets a key price across millions of leases — is which body?",
    options: [
      "The Office of Management and Budget",
      "The Department of Housing Preservation and Development",
      "The Rent Guidelines Board",
      "The Public Service Commission",
      "Whoever your landlord blames"
    ],
    correct: 2,
    explanation: "The Rent Guidelines Board sets annual rent-adjustment ranges for the roughly 1 million stabilized apartments in NYC. Like the Fed, it is a small board — nine members — appointed by an executive (the Mayor), structurally insulated from a single political vote, and required by law to weigh competing data inputs (here: operating costs vs. tenant ability to pay). Unlike the Fed, RGB members serve fixed terms but no Senate-style confirmation."
  },
  {
    category: "Compare & Contrast",
    question: "Morris v. Board of Estimate (1989), which struck down NYC's old executive board, is the direct lineal descendant of which earlier U.S. Supreme Court ruling?",
    options: [
      "Brown v. Board of Education (1954)",
      "Reynolds v. Sims (1964), which extended 'one person, one vote' to state legislatures",
      "Roe v. Wade (1973)",
      "Marbury v. Madison (1803)",
      "Whichever case New York lawyers are quoting at parties"
    ],
    correct: 1,
    explanation: "Reynolds v. Sims (1964) ruled that state legislative districts must be roughly equal in population — extending Baker v. Carr's 'one person, one vote' principle. Morris v. Board of Estimate (1989) applied the same principle to a municipal body: the Board of Estimate gave Brooklyn (then 2.3M) and Staten Island (then ~380K) equal voting weight. Morris is essentially Reynolds for cities."
  },
  {
    category: "Compare & Contrast",
    question: "The MTA is a state public-benefit corporation that runs transit infrastructure NYC depends on but the city doesn't control. Which OTHER famous bistate or multi-jurisdictional authority is the closest structural analogue?",
    options: [
      "The U.S. Postal Service",
      "Amtrak",
      "The Port Authority of New York & New Jersey",
      "FEMA",
      "Whichever agency owns the bridge you're stuck on"
    ],
    correct: 2,
    explanation: "The Port Authority of NY & NJ is the canonical structural cousin of the MTA: a public-benefit corporation, controlled by appointees from outside NYC (in PANYNJ's case, both governors split appointments), running transportation infrastructure (airports, PATH, tunnels, World Trade Center) that NYC residents and businesses depend on but the city has no formal authority over. Both authorities are constant tension points between city and state-level executives."
  },
  {
    category: "Compare & Contrast",
    question: "NYC has had mayoral control of its public schools since 2002. Which other major U.S. city was the model — having adopted mayoral control nearly a decade earlier?",
    options: [
      "Los Angeles",
      "Boston",
      "Chicago",
      "Philadelphia",
      "Whichever city offered Bloomberg the best PowerPoint slide"
    ],
    correct: 2,
    explanation: "Chicago has had mayoral control of its public schools since 1995, when Mayor Richard M. Daley took over Chicago Public Schools. Boston technically preceded both (1992). When Bloomberg pushed Albany to give NYC mayoral control in 2002, Chicago was the explicit model. Most U.S. school districts still use independently elected school boards; mayoral control remains a minority structure even among large cities."
  },
  {
    category: "Compare & Contrast",
    question: "ULURP's months-long, multi-body sequence (Community Board → Borough President → CPC → Council) is most structurally analogous to which federal process?",
    options: [
      "How a federal bill becomes law",
      "Federal environmental review under the National Environmental Policy Act (NEPA), which requires sequential agency review and public comment before a major project decision",
      "The federal budget reconciliation process",
      "How a federal judge gets confirmed",
      "However many agencies the developer's lobbyist can fit on one phone call"
    ],
    correct: 1,
    explanation: "Both ULURP and federal NEPA review are sequential, time-bounded, multi-stage public processes attached to discrete project decisions, with formal points for public comment and advisory and binding votes by different bodies. NEPA review can take years; ULURP is capped at roughly seven months. Both are blamed by reformers for delaying needed projects and credited by communities as essential checks."
  },
  {
    category: "Compare & Contrast",
    question: "The Manhattan, Brooklyn, Bronx, Queens, and Staten Island District Attorneys are independently elected — not appointed by the Mayor. Their federal counterpart, the U.S. Attorneys, are filled how?",
    options: [
      "Also independently elected",
      "Appointed by the President with Senate confirmation; they serve at the President's pleasure and are typically replaced when the White House changes parties",
      "Selected by a panel of senior federal judges",
      "Promoted from within the Justice Department by civil-service exam",
      "Whoever the most senior senator's law-school roommate recommends"
    ],
    correct: 1,
    explanation: "U.S. Attorneys — including the SDNY and EDNY positions that prosecute many of the most consequential NYC federal cases — are presidentially appointed with Senate confirmation, and serve at the President's pleasure. The contrast is sharp: NYC's borough DAs answer to local voters every four years; U.S. Attorneys answer to the President. The structural difference shapes which kinds of cases each tends to bring."
  },

  // ---------- Narrative / scenario ---------- //

  {
    category: "City Stories",
    question: "It's February. Your apartment has had no heat for four days, your landlord won't return calls, and the boiler is officially busted. Which path actually gets you results fastest?",
    options: [
      "Call 911 — no heat is a public-safety emergency",
      "File a complaint with HPD via 311 or the city portal; an inspector visits, the violation is logged, and you can use it in Housing Court",
      "Sue the landlord directly in Supreme Court for breach of warranty of habitability",
      "Withhold rent unilaterally and assume the eviction case will sort it out",
      "Light a small symbolic fire in the lobby"
    ],
    correct: 1,
    explanation: "The standard, legally-protected path is: call 311 or file via HPD's portal, an HPD inspector documents the violation, and the violation supports remedies in Housing Court — including a rent abatement and an HP action to force repairs. Withholding rent without filing creates eviction risk; suing in Supreme Court is rarely cost-effective for an individual tenant. NYC heat law: 68°F by day, 62°F by night, October 1 through May 31."
  },
  {
    category: "City Stories",
    question: "The City Council passes a bill 35–16. Mayor Mamdani disagrees. He has how long to act before it becomes law on its own?",
    options: [
      "10 days, or it becomes law without his signature",
      "30 days, or it becomes law without his signature",
      "60 days, after which it must be reintroduced",
      "He can sit on it indefinitely",
      "Until the next New York Times editorial"
    ],
    correct: 1,
    explanation: "Under the City Charter the Mayor has 30 days to sign, veto, or do nothing. If nothing, the bill becomes law on its own — exactly how the 2024 FARE Act (broker-fee reform) became law under Adams, and how a future bill might quietly pass under Mamdani. Vetoes need 34 of 51 Council votes to override."
  },
  {
    category: "City Stories",
    question: "In 1975, New York City came within hours of declaring bankruptcy. What actually saved it?",
    options: [
      "A federal bailout signed by President Ford on the eve of default",
      "A new state-created Municipal Assistance Corporation (MAC, or 'Big MAC') to refinance city debt, plus an Emergency Financial Control Board with state-level authority over the city's budget — the city traded fiscal sovereignty for survival",
      "Wall Street banks rolling over the city's short-term debt at the request of the mayor",
      "An emergency property-tax surcharge approved by city voters",
      "An impromptu telethon hosted by Bella Abzug"
    ],
    correct: 1,
    explanation: "Albany created the Municipal Assistance Corporation in June 1975 to refinance NYC's debt and the Emergency Financial Control Board (later renamed the Financial Control Board) to oversee the city's budget. The federal government later provided seasonal loans, but the structural rescue was state-imposed fiscal supervision. The Daily News headline 'FORD TO CITY: DROP DEAD' came after Ford initially refused federal aid; he relented in December 1975. The FCB still technically exists in dormant 'monitoring' mode."
  },
  {
    category: "City Stories",
    question: "March 25, 1911: 146 garment workers, mostly young immigrant women, die in the Triangle Shirtwaist Factory fire near Washington Square. What lasting change in city and state government followed?",
    options: [
      "The creation of the FDNY",
      "Sweeping new factory-safety, fire-code, and labor laws — driven by a state Factory Investigating Commission whose investigators included Frances Perkins, who later became the first woman in a U.S. presidential cabinet",
      "The first NYC Building Code, written from scratch in response",
      "The end of garment manufacturing in NYC",
      "An annual press release that nobody reads"
    ],
    correct: 1,
    explanation: "The Triangle fire spurred the New York State Factory Investigating Commission (1911–15), which produced 38 new state laws on fire safety, sweatshop conditions, and worker protection, and incubated the careers of Al Smith, Robert F. Wagner, and Frances Perkins (later FDR's Labor Secretary, the first woman in a U.S. cabinet). The disaster is widely cited as the legislative spark for the modern American workplace-safety state — much of it written in Albany, applied first in NYC."
  },
  {
    category: "City Stories",
    question: "How did the High Line — the elevated freight rail above the West Side that was scheduled for demolition in 1999 — become a park instead?",
    options: [
      "A federal court ordered the city to preserve it",
      "Two neighborhood residents (Joshua David and Robert Hammond) founded Friends of the High Line, used a federal rail-banking law to block demolition, and persuaded the Bloomberg administration to back conversion via a city rezoning",
      "Mayor Giuliani authorized conversion as an early second-term initiative",
      "It was preserved by an act of Congress as a National Historic Landmark",
      "A Goldman Sachs partner bought it personally and then donated it"
    ],
    correct: 1,
    explanation: "Two neighborhood residents, Joshua David and Robert Hammond, founded Friends of the High Line in 1999 to fight Giuliani-era demolition plans. They invoked a federal rail-banking statute that lets dormant rail corridors be preserved for future transit use, then worked with the Bloomberg administration on the city rezoning that financed conversion. Section 1 opened in 2009. The High Line is now a cited model — and cautionary tale — for park-driven gentrification worldwide."
  },
  {
    category: "City Stories",
    question: "In 2013, a federal judge ruled in Floyd v. City of New York that the NYPD's stop-and-frisk practice was unconstitutional. What did the ruling actually order?",
    options: [
      "An immediate end to all NYPD stop-and-frisk encounters",
      "Criminal charges against named NYPD officers",
      "A federal monitor and reforms — including a body-camera pilot, supervisory changes, and updated training and stop documentation — while leaving the underlying tactic legally permissible if used constitutionally",
      "The disbanding of the NYPD's Street Crime Unit",
      "A polite suggestion that the NYPD do a little less of it"
    ],
    correct: 2,
    explanation: "Judge Shira Scheindlin found that the NYPD's stop-and-frisk practice violated the Fourth and Fourteenth Amendments through racially disproportionate stops without reasonable suspicion. The remedy was structural: a federal monitor, a body-worn camera pilot, supervisory and training reforms, and a 'Joint Remedial Process' for community input. The tactic itself remained lawful when used constitutionally; recorded stops fell from a 2011 peak above 685,000 to a small fraction of that within a few years."
  },
  {
    category: "City Stories",
    question: "Times Square's pedestrian plazas — the painted barriers and folding chairs that took over Broadway in 2009 — were created how?",
    options: [
      "A binding referendum",
      "An act of the State Legislature",
      "An administrative DOT pilot under the Bloomberg/Sadik-Khan DOT, made permanent after data showed traffic actually improved and injuries dropped",
      "A federal court order following a pedestrian-injury lawsuit",
      "Whichever production company was filming a movie that week and never left"
    ],
    correct: 2,
    explanation: "Bloomberg's DOT Commissioner Janette Sadik-Khan launched the Broadway pedestrianization as an administrative pilot — folding chairs, paint, and barriers — over Memorial Day weekend 2009. After data showed faster crosstown travel times and fewer pedestrian injuries, the change was made permanent. It is the most-cited modern example of a major street redesign accomplished entirely by agency action, no legislation required."
  },
  {
    category: "City Stories",
    question: "NYC's modern Landmarks Preservation Commission was created in 1965, two years after a transformative loss. Which loss?",
    options: [
      "The original Madison Square Garden",
      "The original Pennsylvania Station, demolished in 1963 over public protest",
      "The Brokaw Mansion on Fifth Avenue",
      "The Singer Building, then the world's tallest demolished structure",
      "Whatever bar the architecture critics drank at"
    ],
    correct: 1,
    explanation: "The 1963 demolition of McKim, Mead & White's original Pennsylvania Station — replaced by the current underground station and Madison Square Garden — galvanized public outrage and produced the 1965 Landmarks Law, which created the Landmarks Preservation Commission. (The Brokaw Mansion and Singer Building demolitions later in the 1960s reinforced the case.) The U.S. Supreme Court upheld the law in Penn Central v. New York City (1978), one of the most consequential land-use rulings of the 20th century."
  },
  {
    category: "City Stories",
    question: "Until 2024, NYC could not lower the speed limit on its own streets below 25 mph without state permission. What changed?",
    options: [
      "The City Charter was amended by referendum",
      "Sammy's Law, passed in Albany in 2024, gave the city the authority to set speed limits as low as 20 mph — the city used that authority almost immediately",
      "A federal court ruled that home rule allowed it",
      "Mayor Adams set lower limits by executive order",
      "Drivers slowed down voluntarily, on the recommendation of a study"
    ],
    correct: 1,
    explanation: "Sammy's Law — named for Sammy Cohen Eckstein, a 12-year-old killed by a van in 2013 — was passed by the State Legislature in April 2024 as part of the state budget, after years of advocacy by Families for Safe Streets. It authorized NYC to set speed limits as low as 20 mph on most streets. The city moved quickly to lower limits in pilot corridors. Before Sammy's Law, the citywide 25 mph limit set in 2014 itself required state authorization."
  },
  {
    category: "City Stories",
    question: "A developer wants to build a 12-story building where current zoning allows 6. They submit a rezoning application. Roughly how long does the public ULURP process take, and who has the final binding vote?",
    options: [
      "About 6 weeks; the City Planning Commission has the final vote",
      "About 7 months; the City Council has the final vote (though the Borough President and Community Board vote first as advisory)",
      "About 18 months; the Mayor signs off",
      "About 2 years; the State Legislature has final say",
      "Until somebody gets bored, usually"
    ],
    correct: 1,
    explanation: "ULURP — the Uniform Land Use Review Procedure — runs roughly seven months. The Community Board votes first (advisory, ~60 days), then the Borough President (advisory, ~30 days), then the City Planning Commission (binding, ~60 days), then the City Council (binding, ~50 days). The Mayor can veto but the Council can override 34–17. Council 'member deference' often determines the outcome long before the formal vote."
  },
  {
    category: "City Stories",
    question: "In 1989, the U.S. Supreme Court unanimously ruled that NYC's Board of Estimate — which gave Brooklyn (then 2.3 million residents) and Staten Island (then about 380,000) equal voting power — violated 'one person, one vote.' What replaced it?",
    options: [
      "A weighted voting system that survived legal challenge",
      "A 51-member City Council with primary land-use and budget authority, paired with a stronger Mayor — the basic structure of NYC government today",
      "A Borough Mayor system, with five sub-mayors reporting to the citywide Mayor",
      "A return to the pre-1898 county governments",
      "An apologetic Borough President fundraiser circuit"
    ],
    correct: 1,
    explanation: "Morris v. Board of Estimate (1989) struck down the Board of Estimate as malapportioned. The 1989 Charter Revision Commission, anticipating the ruling, produced a new structure: the 51-member City Council took on most of the Board's powers (land use, budget), the Mayor's executive authority was somewhat strengthened, and the Public Advocate was created to head the line of succession. The new Council was first elected in 1991. Modern NYC government is essentially a 1989 invention."
  },
  {
    category: "Mamdani Watch",
    question: "As of mid-May 2026, how many of Mamdani's four MTA Board seats had he filled?",
    options: [
      "All four",
      "Three of four",
      "Two of four — with two vacancies still open and a hard June 4 deadline at the end of Albany's session",
      "Zero of four",
      "Trick question — the Mayor doesn't appoint MTA Board members"
    ],
    correct: 2,
    explanation: "By mid-May 2026, Mamdani had filled only two of his four MTA Board seats, with the State Senate's June 4 confirmation deadline closing fast. Transit advocates noted the irony: a mayor whose signature issue was the buses had not yet seated his full slate at the agency that runs them."
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
