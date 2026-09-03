"""Builds pairings-src.json from the research files plus the curated list below.
Each entry names the research file and the row (0-based) it draws its numbers,
URLs and verbatim quotes from, then adds the sentence, the place and its pin."""
import json, os, re
R = {f[:-5]: json.load(open(f'research/{f}')) for f in os.listdir('research') if f.endswith('.json')}
W = json.load(open('../data/world.json'))['centroids']
REALMS = [
  {"key":"people","label":"People"},
  {"key":"money","label":"Money"},
  {"key":"place","label":"Land, streets and pipes"},
  {"key":"movement","label":"Movement and visitors"},
  {"key":"life","label":"Daily life"},
  {"key":"safety","label":"Safety"},
]
def C(name, lonlat=None):
    if lonlat: return lonlat
    return W[name]
# (realm, file, row, kind, place, place_short, lonlat-or-None, sentence, nyc_display, match_display, caveat-on-page, note-for-methodology)
L = [
 # ---- people ----
 ("people","people",0,"country","Switzerland",None,None,
  "has as many <b>people</b> as <b class=k>Switzerland</b>","8.58 million","9.13 million",
  None,"Census Bureau Vintage 2025 estimate for New York City as of July 1, 2025, against Switzerland's provisional permanent resident population at Dec. 31, 2025, published by the Federal Statistical Office and republished by the Swiss foreign ministry. Virginia (8.88 million, ratio 1.034) is the closer U.S. state."),
 ("people","people",2,"country","Armenia",None,None,
  "has as many <b>foreign-born residents</b> as <b class=k>Armenia</b> has people","3.1 million","3.10 million",
  None,"The city's figure is the Department of City Planning's rounded 3.1 million from the 2023 American Community Survey, as used in its 2026 'Newest New Yorkers' report; the department notes the survey undercounted recent arrivals. Armenia's figure is the Statistical Committee's Jan. 1, 2026 count as reported by the Arka news agency."),
 ("people","people",3,"state","North Dakota",None,[-100.5,47.5],
  "has as many <b>public school students</b> as <b class=k>North Dakota</b> has people","793,300","799,358",
  "District schools only, kindergarten through 12th grade. Charters and pre-K would add roughly 200,000.",
  "Department of Education preliminary 2025-26 enrollment in district schools, K-12, as reported by City Journal quoting the department. The state education department's 2024-25 figure for the New York City district including charters and pre-K is 946,747. North Dakota is the Census Bureau's Vintage 2025 estimate as announced by the governor's office."),
 ("people","people",5,"country","Sweden",None,None,
  "has as many <b>babies born each year</b> as <b class=k>Sweden</b>","98,389 (2023)","97,500 (2025)",
  "Years differ: the city's latest annual vital statistics summary is for 2023.",
  "New York City Health Department 2023 Summary of Vital Statistics; Statistics Sweden's 2025 population statistics. City births have been falling about 1 percent a year, so the two figures are probably even closer today."),
 ("people","people",6,"city","Pittsburgh",None,[-79.99,40.44],
  "has as many people on the <b>city payroll</b> as <b class=k>Pittsburgh</b> has people","291,717","307,632",
  "Actual full-time employees in April 2026. The city was authorised to fill 307,247 positions and had 15,530 of them vacant.",
  "Actual full-time employees in April 2026, from the city Comptroller, who reports in the same document an authorised headcount of 307,247 positions for fiscal 2026 with 15,530 vacant. Pittsburgh is the Census Bureau's Vintage 2025 estimate as summarized by the University of Pittsburgh's Center for Social and Urban Research."),
 ("people","people",8,"city","Cleveland",None,[-81.69,41.50],
  "houses as many people in <b>public housing and its converted successors</b> as live in <b class=k>Cleveland</b>","344,661","363,608",
  "Public housing proper holds 298,206 authorised residents; another 46,455 live in developments converted to private management under PACT, which the housing authority no longer counts as public housing.",
  "Sum of two figures on the New York City Housing Authority's 2025 fact sheet: 298,206 authorized residents in conventional public housing and 46,455 in developments converted under PACT/RAD. Cleveland is the Census Bureau's Vintage 2025 estimate as tabulated by the Cuyahoga County Planning Commission."),
 ("people","people",10,"country","Andorra",None,[1.52,42.51],
  "shelters as many <b>homeless people each night</b> as <b class=k>Andorra</b> has people","83,549","89,058",
  "Department of Homeless Services shelters only; other agencies' shelters and migrant sites are not included.",
  "Department of Homeless Services daily report dated Sept. 2, 2026 (the PDF at this address is overwritten every day). Andorra's Department of Statistics figure for Dec. 31, 2025, as reported by the Andorran outlet Alto."),
 ("people","people",11,"structure","Anfield, Liverpool","Anfield",[-2.96,53.43],
  "had as many <b>marathon finishers</b> in 2025 as <b class=k>Anfield</b> holds fans","59,226","61,276",
  None,"New York Road Runners' finisher count for the Nov. 2, 2025 race, as reported by ABC7 and Running USA; Liverpool FC's announced Anfield capacity from the 2024-25 season. Greenland's population (56,836) is the alternate."),
 ("people","people",12,"country","Estonia",None,None,
  "has as many <b>residents 65 and older</b> as <b class=k>Estonia</b> has people","1.43 million (2023)","1.36 million",
  None,"State Comptroller's January 2025 report on older adults, citing 2023 data; Statistics Estonia's Jan. 1, 2026 population. The city's older population grows about 2 percent a year, so the gap has probably widened a little."),
 # ---- money ----
 ("money","money",0,"country","Dominican Republic","Dominican Republic",C("Dominican Rep."),
  "has a <b>city budget</b> the size of the <b class=k>Dominican Republic's</b> economy","$125.8 billion","$127.9 billion",
  None,"Adopted budget for fiscal 2027 per the city Comptroller; International Monetary Fund estimate of the Dominican Republic's 2025 nominal GDP from the WEO datamapper. Puerto Rico ($126.5 billion) is closer still but is a U.S. territory whose GDP is inflated by pharmaceutical transfer pricing."),
 ("money","money",1,"country","Indonesia",None,[106.85,-6.2],
  "has an <b>economy</b> the size of <b class=k>Indonesia's</b>","$1.38 trillion","$1.40 trillion",
  "The city total is the sum of five separate county series; the link opens the largest of them, Manhattan, at $1.01 trillion.","Sum of the Bureau of Economic Analysis 2024 GDP for the five counties (New York, Kings, Queens, Bronx, Richmond) as published on FRED; IMF figure for Indonesia's 2024 nominal GDP. Same year on both sides."),
 ("money","money",2,"country","Finland",None,None,
  "has <b>pension funds</b> worth as much as <b class=k>Finland's</b> whole economy","$326 billion","$317 billion",
  None,"Combined assets of the five city pension systems at June 30, 2026, per the city Comptroller; IMF estimate of Finland's 2025 nominal GDP."),
 ("money","money",3,"country","Iraq",None,None,
  "proposes to spend as much on its <b>police department</b> as <b class=k>Iraq</b> spends on its military","$6.59 billion","$6.4 billion",
  "Executive Plan figure for fiscal 2027, not the adopted line.",
  "NYPD fiscal 2027 budget in the May 2026 Executive Plan, per the City Council's budget report; Iraq's 2025 military expenditure from SIPRI's April 2026 fact sheet, Table 1. Czechia ($7.1 billion) is the alternate."),
 ("money","money",4,"country","Iceland",None,None,
  "proposes to spend as much on <b>public schools</b> as <b class=k>Iceland</b> produces in a year","$37.9 billion","$38.6 billion",
  "Executive Plan figure for fiscal 2027.",
  "Department of Education fiscal 2027 budget in the May 2026 Executive Plan, all funds, per the City Council's budget report; IMF estimate of Iceland's 2025 nominal GDP."),
 ("money","money",5,"company","Starbucks (Seattle)","Starbucks",[-122.33,47.61],
  "collects as much in <b>property tax</b> as <b class=k>Starbucks</b> takes in worldwide","$37.3 billion","$37.2 billion",
  None,"Comptroller's forecast of fiscal 2027 property tax revenue, so a projection rather than money collected, against Starbucks' closed-book net revenues for fiscal 2025."),
 ("money","money",6,"country","Tunisia",None,None,
  "takes in as much <b>visitor spending</b> as <b class=k>Tunisia's</b> entire economy","$55.6 billion","$57.6 billion",
  None,"Direct visitor spending in 2025 per New York City Tourism + Conventions' annual report; IMF estimate of Tunisia's 2025 nominal GDP. One industry's takings against a whole country's output: the same report's wider $84.7 billion total economic impact figure would overshoot Tunisia entirely."),
 ("money","money",11,"country","Cambodia",None,None,
  "pays out a <b>Wall Street bonus pool</b> the size of <b class=k>Cambodia's</b> economy","$49.2 billion","$49.3 billion",
  None,"State Comptroller's March 2026 estimate of 2025 securities-industry bonuses paid to New York City-based employees; IMF estimate of Cambodia's 2025 nominal GDP."),
 ("money","money",12,"country","Jamaica",None,None,
  "is served by a <b>transit authority</b> whose budget equals <b class=k>Jamaica's</b> economy","$21.3 billion","$22.3 billion",
  "The MTA is a state authority serving the whole region.",
  "MTA adopted operating budget for calendar 2026 per the City Council's budget report, corroborated on mta.info; IMF estimate of Jamaica's 2025 nominal GDP."),
 ("money","money",10,"country","Spain",None,None,
  "has <b>real estate</b> worth as much as <b class=k>Spain</b> produces in a year","$1.66 trillion","$1.73 trillion",
  "A stock against a flow: property value is what all the city's buildings are worth, national GDP is a single year of output. Department of Finance market values are the city's own estimates and lag sale prices.",
  "Total market value of all city property on the fiscal 2027 tentative assessment roll (Jan. 15, 2026); IMF figure for Spain's 2024 nominal GDP ($1,725.152 billion). Saudi Aramco's market capitalization ($1.676 trillion on Sept. 2, 2026) was the closer match but moves daily."),
 # ---- safety ----
 ("safety","crime",0,"city","Houston",None,[-95.37,29.76],
  "has as many <b>murders a year</b> as <b class=k>Houston</b> has homicides","305","272",
  "Houston counts homicides, which take in negligent manslaughter and other killings that New York City's murder figure leaves out, so the true gap is wider. Houston has 2.4 million people to New York City's 8.5 million, so its rate is about three times higher.",
  "NYPD year-end 2025 release (murder and non-negligent manslaughter); Houston Police Department 2025 homicide count obtained by the Houston Chronicle through a records request and syndicated on Yahoo News. Houston is 11 percent lower, the widest gap on this page; Memphis (235) and Philadelphia (222) were further off. Populations from Census Vintage 2024."),
 ("safety","crime",1,"city","Philadelphia",None,[-75.16,39.95],
  "has as many <b>people shot each year</b> as <b class=k>Philadelphia</b>","856","906",
  "Philadelphia has 1.57 million people; its per-capita rate is more than five times higher.",
  "NYPD year-end 2025 release; Philadelphia Police data as reported by WHYY on Dec. 31, 2025, running through Dec. 30."),
 ("safety","crime",2,"country","Austria",None,None,
  "has as many <b>police officers</b> as all of <b class=k>Austria</b>","33,614","32,500",
  "Uniformed headcount at the end of fiscal 2025; the department is hiring toward 35,555 by the end of 2026.",
  "NYPD uniformed personnel at the end of fiscal 2025 from the Mayor's Management Report; Austria's Interior Ministry 2025 personnel figure ('over 32,500 Exekutivbedienstete') as reported by 5min.at. The alternate match is the Royal Navy and Royal Marines' regular strength, 32,520."),
 ("safety","crime",4,"country","Sweden",None,None,
  "loses as many <b>people to traffic crashes</b> as all of <b class=k>Sweden</b>","205","203",
  None,"Department of Transportation's 2025 Vision Zero year-end release; Trafikanalys (Sweden's official transport statistics agency) release on 2025 road deaths. Ireland (185) is the backup."),
 ("safety","crime",5,"country","Switzerland",None,None,
  "holds as many <b>people in jail</b> as <b class=k>Switzerland</b> holds in all its prisons","6,823","7,119",
  "Fiscal 2025 average; the jail population passed 7,000 later in 2025.",
  "Department of Correction average daily population for fiscal 2025 from the Mayor's Management Report; Switzerland's total prison population at Jan. 31, 2026 per World Prison Brief, citing the Swiss Federal Statistical Office. The Board of Correction's January 2026 report gives a fiscal 2026 year-to-date average of 7,247."),
 ("safety","crime",6,"state","Arizona",None,[-111.9,34.3],
  "answers as many <b>911 calls a year</b> as <b class=k>Arizona</b> has people","7.49 million","7.58 million",
  None,"NYPD 911 calls in fiscal 2025 from the Mayor's Management Report; Arizona population, Census Bureau Vintage 2024."),
 ("safety","crime",7,"city","Buffalo",None,[-78.88,42.89],
  "makes as many <b>arrests a year</b> as <b class=k>Buffalo</b> has people","278,953","276,854",
  None,"Row count of 2025 arrests in the NYPD Arrests Data (Historic) dataset on NYC Open Data, all ages; Buffalo population, Census Vintage 2024, via a secondary site (the Census QuickFacts page blocks automated fetches)."),
 ("safety","crime",3,"city","Philadelphia","Philadelphia",[-75.16,39.95],
  "sends an <b>ambulance</b> as many times a year as <b class=k>Philadelphia</b> has people","1.62 million","1.57 million",
  None,"FDNY emergency medical incidents (ambulance) in fiscal 2025 from the Mayor's Management Report; Philadelphia population, Census Vintage 2024."),
 # ---- movement ----
 ("movement","transit",0,"city","Hong Kong",None,[114.17,22.32],
  "runs as many <b>public buses</b> as <b class=k>Hong Kong</b>'s whole franchised fleet","5,800","5,870",
  "Hong Kong's total is a sum: the government fact sheet lists five franchised networks separately and never states a combined figure.","MTA's New York City Transit page (2023 fleet); sum of the five franchised bus operations in the Hong Kong government's July 2025 transport fact sheet (3,895 + 1,326 + 226 + 281 + 142). Those five franchises are run by four companies: Citybus has held two of them since it absorbed New World First Bus in 2023. Whether the MTA's 5,800 includes the MTA Bus Company is not stated on its page."),
 ("movement","transit",1,"region","Sub-Saharan Africa",None,[22,-2],
  "carries as many <b>subway riders a year</b> as <b class=k>sub-Saharan Africa</b> has people","1.28 billion","1.29 billion",
  None,"MTA 2025 subway ridership; World Bank 2024 population aggregate for sub-Saharan Africa."),
 ("movement","transit",2,"city","Los Angeles",None,[-118.24,34.05],
  "carries the <b>population of Los Angeles</b> on the subway every weekday","4.00 million","3.87 million",
  None,"MTA average weekday subway ridership in 2025; Los Angeles city population, Census Bureau Vintage 2025."),
 ("movement","transit",3,"region","European Union",None,[4.35,50.85],
  "gives as many <b>bus rides a year</b> as the <b class=k>European Union</b> has people","442 million","451 million",
  "New York City Transit buses only; the MTA Bus Company adds about 120 million.",
  "MTA 2025 bus ridership for New York City Transit; World Bank 2024 population aggregate for the European Union."),
 ("movement","transit",4,"country","France",None,[2.35,48.85],
  "draws as many <b>visitors a year</b> as <b class=k>France</b> has people","65 million","68.6 million",
  None,"New York City Tourism + Conventions annual report for 2025; World Bank 2024 population for France. South Africa (64.0 million, ratio 0.985) is the closer match; the United Kingdom is 69.3 million."),
 ("movement","transit",5,"country","Belgium",None,None,
  "draws as many <b>international visitors a year</b> as <b class=k>Belgium</b> has people","12.5 million","11.9 million",
  None,"New York City Tourism + Conventions annual report for 2025; World Bank 2024 population for Belgium. Bolivia (12.4 million) and Tunisia (12.3 million) are closer but less familiar."),
 ("movement","transit",6,"country","Russia",None,[37.62,55.75],
  "is served by airports that move as many <b>passengers a year</b> as <b class=k>Russia</b> has people","142.7 million","143.7 million",
  "Counts Kennedy, LaGuardia and Newark, which is in New Jersey, plus Stewart.","Combined 2025 passengers at Kennedy, Newark, LaGuardia and Stewart, per the Port Authority as reported by AviationPros; World Bank 2024 population for Russia. Newark is in New Jersey and Stewart is in Orange County, so this is the airport system serving the region rather than airports inside the city: Kennedy and LaGuardia alone handled 95.4 million."),
 ("movement","transit",7,"city","London",None,[-0.12,51.5],
  "licenses as many <b>yellow cabs</b> as <b class=k>London</b> licenses black cabs","13,587","13,483",
  "Both are licence counts. About a fifth of New York City medallions are not currently in service, so fewer yellow cabs work the streets than the cap allows.","Taxi and Limousine Commission (the medallion count is fixed by law); Transport for London licensing figures for the week ending Aug. 16, 2026. Both figures count licences rather than vehicles on the road, and roughly 3,000 New York City medallions were sitting unused as of late 2025, so London has more working cabs than New York does."),
 ("movement","transit",8,"country","Argentina",None,None,
  "logs as many <b>Citi Bike rides a year</b> as <b class=k>Argentina</b> has people","46 million","45.7 million",
  None,"Lyft's March 2026 post on Citi Bike operations ('more than 46 million rides in 2025'); World Bank 2024 population for Argentina."),
 ("movement","transit",11,"state","Mississippi",None,[-89.7,32.7],
  "has as many <b>registered vehicles</b> as <b class=k>Mississippi</b>","2.14 million","2.21 million",
  "The city count includes trailers and motorcycles; the federal state count excludes trailers.",
  "Live count of unexpired vehicle registrations in the five boroughs from the state DMV's registration file on data.ny.gov, queried Sept. 2, 2026; Mississippi's 2024 total from the Federal Highway Administration's MV-1 table."),
 # ---- place ----
 ("place","land",0,"country","Singapore",None,[103.82,1.35],
  "covers as much <b>land</b> as <b class=k>Singapore</b>","300.5 sq mi","287.4 sq mi",
  None,"Census Bureau 2023 gazetteer land area for New York city (778.18 km²); Singapore's Department of Statistics land area at end of December 2025 (744.3 km²). Singapore keeps growing by reclamation."),
 ("place","land",1,"structure","Great Wall of China","Great Wall",[115.99,40.36],
  "has as many <b>miles of sidewalk</b> as the <b class=k>Great Wall of China</b> is long","12,760 mi","13,171 mi",
  "Sidewalk mileage counts both sides of the street; the wall figure counts every dynasty's sections, including ruins.",
  "Department of Transportation pedestrian ramps page; the State Administration of Cultural Heritage's 2012 survey total of 21,196.18 km, as reported by China Daily. The Ming-era wall alone is 8,851.8 km."),
 ("place","land",2,"distance","Tokyo",None,[139.69,35.69],
  "has enough <b>miles of streets</b> to reach <b class=k>Tokyo</b>","6,300 mi","6,755 mi",
  None,"Department of Transportation's about page (centerline miles of streets and highways); straight-line distance from New York to Tokyo per Travelmath."),
 ("place","land",3,"distance","Chicago",None,[-87.63,41.88],
  "has enough <b>subway track</b> to reach <b class=k>Chicago</b>","665 mi","713 mi",
  None,"MTA's 2019 subway and bus facts page ('more than 665 mainline track miles'; the MTA makes the Chicago comparison itself); straight-line distance from New York to Chicago per Travelmath."),
 ("place","land",5,"distance","Earth's equator","Earth",[-30,0],
  "has as many <b>miles of sewer</b> as the <b class=k>Earth</b> is wide","7,500 mi","7,926 mi",
  None,"Department of Environmental Protection July 2026 release (its sewer-system page says 'over 7,400 miles'); Earth's equatorial diameter per NASA."),
 ("place","land",6,"state","Rhode Island",None,[-71.5,41.7],
  "maintains as many <b>bridges and tunnels</b> as <b class=k>Rhode Island</b> has bridges","over 800","783",
  "The two sides count different things: the city figure mixes bridges with tunnels, the federal figure is bridges over 20 feet on public roads, and neither includes the big Port Authority and MTA crossings.",
  "Department of Transportation bridges page; Federal Highway Administration National Bridge Inventory 2024 state totals."),
 ("place","land",8,"structure","Jersey (Channel Islands)","Jersey",[-2.11,49.21],
  "has as much <b>parkland</b> as the island of <b class=k>Jersey</b>","30,000+ acres","29,120 acres",
  None,"NYC Parks about page ('more than 30,000 acres'); Government of Jersey profile (45.5 square miles, converted at 640 acres per square mile to 29,120 acres; the same page's rounded 120 square kilometres would give 29,650)."),
 ("place","land",9,"city","Boston",None,[-71.06,42.36],
  "has as many <b>street trees</b> as <b class=k>Boston</b> has people","666,134","673,822",
  "The tree count is from the 2015-16 census; a new count is under way.",
  "NYC Parks TreesCount 2015-2016 result; Boston population from the 2024 American Community Survey one-year estimate via the Census API. Park trees are not included."),
 ("place","land",10,"country","Iceland",None,None,
  "keeps as many <b>streetlights</b> lit as <b class=k>Iceland</b> has people","nearly 400,000","392,404",
  None,"Department of Transportation streetlights page ('nearly 400,000'); World Bank 2025 population for Iceland."),
 ("place","land",11,"country","Aruba",None,[-69.97,12.52],
  "has as many <b>fire hydrants</b> as <b class=k>Aruba</b> has people","109,725","108,785",
  None,"Row count of the Department of Environmental Protection's citywide hydrants dataset on NYC Open Data (updated Dec. 18, 2025), which may include out-of-service hydrants; World Bank 2025 population for Aruba."),
 ("place","land",13,"structure","Colorado River","Colorado River",[-112.1,36.1],
  "has as many <b>lane miles of bike lanes</b> as the <b class=k>Colorado River</b> is long","1,550 mi","1,450 mi",
  "Lane miles count each direction separately.",
  "Department of Transportation bicycle statistics page (2024 network); Colorado River length per the U.S. Geological Survey."),
 ("place","land",16,"state","Virginia",None,[-78.5,37.5],
  "has as many <b>homes</b> as all of <b class=k>Virginia</b>","3.74 million","3.75 million",
  None,"Housing units from the 2024 American Community Survey one-year estimates via the Census API, for New York city and for Virginia. New Jersey (3.82 million) is the alternate."),

 # ---- people, second batch ----
 ("people","learning",1,"country","Cabo Verde",None,[-23.6,15.1],
  "has as many <b>college students</b> as <b class=k>Cabo Verde</b> has people","503,000","524,877",
  None,"New York City Economic Development Corporation's November 2024 report on academia ('over 503,000'; the EDC's own comparison is Atlanta); World Bank 2024 population for Cabo Verde."),
 ("people","learning",3,"country","Ireland",None,None,
  "employs as many <b>public school teachers</b> as all of <b class=k>Ireland</b>","over 77,000","74,073 (2022)",
  "Ireland's count is from 2022, the most recent its education department publishes, and it was then rising by about 2,000 a year, so Ireland has probably passed New York City since.","Mayor's Management Report, fiscal 2025 Department of Education chapter; Ireland's Department of Education 2022 teacher count from its March 2024 indicators report. Ireland has hired since, so the gap is probably narrower."),
 ("people","health",0,"state","Utah",None,[-111.7,39.5],
  "has as many <b>people on Medicaid</b> as <b class=k>Utah</b> has people","3.58 million","3.54 million",
  None,"New York State Department of Health Medicaid enrollment by residential county, July 2026 (all Medicaid, not only the HRA-administered slice); Utah's population from the Census Bureau's Vintage 2025 state estimates file."),
 ("people","health",1,"city","Phoenix",None,[-112.07,33.45],
  "has as many <b>people on food stamps</b> as <b class=k>Phoenix</b> has people","1.63 million","1.67 million",
  "SNAP rolls are falling quickly: 1.79 million a year earlier.",
  "Human Resources Administration's HRA Facts for July 2026; Phoenix population from the Census Bureau's Vintage 2025 city estimates file."),
 ("people","health",2,"country","Slovakia",None,None,
  "records as many <b>deaths a year</b> as <b class=k>Slovakia</b>","55,459 (2023)","54,133 (2023)",
  "The city counts deaths that occur within it, including about 4,500 non-residents; Slovakia counts residents.","Health Department 2023 Summary of Vital Statistics, Table PC3; Eurostat deaths series for Slovakia, 2023. Denmark (58,384) is the alternate."),
 ("people","health",7,"state","Montana",None,[-109.6,47.0],
  "has as many <b>residents with a disability</b> as <b class=k>Montana</b> has people","1.17 million","1.14 million",
  "Civilian, non-institutional population only.",
  "2024 American Community Survey one-year estimate, table S1810, via the Census API; Montana's population from the Census Bureau's Vintage 2025 state estimates file. The 2023 survey put the figure at 1.06 million, so year-to-year sampling noise is real."),
 ("people","health",9,"city","Baltimore",None,[-76.61,39.29],
  "has as many <b>people on cash assistance</b> as <b class=k>Baltimore</b> has people","559,129","569,997",
  None,"Human Resources Administration's HRA Facts for July 2026, monthly unduplicated recipients; Baltimore population from the Census Bureau's Vintage 2025 city estimates file."),
 # ---- money, second batch ----
 ("money","wealth",0,"country","Bahamas",None,[-77.35,25.05],
  "has as many <b>millionaires</b> as the <b class=k>Bahamas</b> has people","384,500","401,283",
  "Millionaires here means people with at least $1 million in liquid, investable assets.",
  "Henley & Partners' World's Wealthiest Cities Report 2025 (New World Wealth data); World Bank 2024 population for the Bahamas. Iceland (386,506) is the closer match but already appears elsewhere on this page."),
 ("money","wealth",1,"country","Kuwait",None,None,
  "has as many <b>jobs</b> as <b class=k>Kuwait</b> has people","4.89 million","4.90 million",
  None,"Total nonfarm payroll employment in New York City for July 2026, not seasonally adjusted, from the Bureau of Labor Statistics series as republished on FRED; World Bank 2024 population for Kuwait."),
 ("money","wealth",4,"company","Alphabet (Mountain View)","Alphabet",[-122.08,37.42],
  "has as many <b>Wall Street jobs</b> as <b class=k>Alphabet</b> has employees worldwide","201,500","190,820",
  None,"State Comptroller's October 2025 report on securities-industry employment in the city for 2024 (preliminary 2025 data shows about 3,000 fewer); Alphabet's employee count at Dec. 31, 2025 from its Form 10-K."),
 ("money","wealth",9,"country","Slovakia","Slovakia",None,
  "has a <b>Brooklyn</b> whose economy is the size of <b class=k>Slovakia's</b>","$146 billion","$141 billion",
  "Both figures are 2024, the latest county figures published. The IMF puts Slovakia 10 percent higher in 2025.","Bureau of Economic Analysis 2024 GDP for Kings County via FRED; IMF figure for Slovakia's 2024 nominal GDP."),
 ("money","wealth",5,"country","Ethiopia",None,None,
  "has a <b>Queens</b> whose economy is the size of <b class=k>Ethiopia's</b>","$143 billion","$142 billion",
  "Holds for 2024 only. Ethiopia devalued the birr and the IMF puts its 2025 dollar GDP at $109 billion, a quarter lower, so the two have already parted company.",
  "Bureau of Economic Analysis 2024 GDP for Queens County via FRED; IMF figure for Ethiopia's 2024 nominal GDP. Ethiopia has about 130 million people."),
 ("money","wealth",6,"country","Jordan",None,None,
  "has a <b>Bronx</b> whose economy is the size of <b class=k>Jordan's</b>","$58.3 billion","$58.7 billion",
  "Both figures are 2024. The IMF puts Jordan 5 percent higher in 2025.","Bureau of Economic Analysis 2024 GDP for Bronx County via FRED; IMF figure for Jordan's 2024 nominal GDP."),
 ("money","wealth",7,"country","Guyana",None,None,
  "has a <b>Staten Island</b> whose economy is the size of <b class=k>Guyana's</b>","$23.8 billion","$24.7 billion",
  None,"Bureau of Economic Analysis 2024 GDP for Richmond County via FRED; IMF figure for Guyana's 2024 nominal GDP. Mongolia ($23.8 billion, ratio 1.001) is the closer match but appears elsewhere on this page."),
 # ---- place, second batch ----
 ("place","wealth",2,"city","Washington, D.C. (metro)","Washington",[-77.04,38.9],
  "has as much <b>office space in Manhattan</b> as the whole <b class=k>Washington</b> region","416 million sq ft","428 million sq ft",
  "Two brokerages, two inventory definitions.",
  "Cushman & Wakefield's Manhattan office MarketBeat for the first quarter of 2026 (Manhattan totals row); Lincoln Property Company's first-quarter 2026 Washington report, covering the District, Northern Virginia and suburban Maryland."),
 # ---- movement, second batch ----
 ("movement","health",8,"country","Saint Lucia",None,[-60.98,13.9],
  "licenses as many <b>for-hire drivers</b> (Uber, Lyft, liveries, black cars) as <b class=k>Saint Lucia</b> has people","180,334","179,744",
  "Licensed and in good standing; far fewer actually drive in a given month.",
  "Count of the Taxi and Limousine Commission's active for-hire-vehicle driver list on NYC Open Data, Sept. 2, 2026; World Bank 2024 population for Saint Lucia."),
 # ---- daily life and culture ----

 ("life","learning",4,"country","Finland",None,None,
  "draws as many <b>visitors to the Met</b> as <b class=k>Finland</b> has people","over 5.7 million","5.62 million",
  None,"The Metropolitan Museum of Art's fiscal 2025 attendance, from its press release as reprinted by ArtDependence (the museum's own site blocks automated fetches); World Bank 2024 population for Finland."),
 ("life","learning",5,"country","Uruguay",None,None,
  "sold as many <b>Yankees tickets</b> in 2025 as <b class=k>Uruguay</b> has people","3,392,659","3,386,588",
  None,"ESPN's 2025 MLB attendance table, Yankees home attendance over 80 dates; World Bank 2024 population for Uruguay. The Mets (3,182,052) match Puerto Rico (3,202,521)."),
 ("life","learning",7,"country","Guinea",None,None,
  "filled as many <b>Broadway seats</b> last season as <b class=k>Guinea</b> has people","14.66 million","14.75 million",
  None,"Broadway League season statistics table, 2024-25 attendance; World Bank 2024 population for Guinea. Rwanda (14.26 million) is the alternate."),
 ("life","health",4,"country","Germany",None,[13.4,52.52],
  "loses as many <b>people to drug overdoses</b> as all of <b class=k>Germany</b>","2,192 (2024)","2,137 (2024)",
  "Germany counts deaths from illegal drugs; the city counts unintentional poisoning by any drug. Germany has 83 million people.",
  "Health Department data brief on unintentional drug overdose deaths in 2024; Germany's Federal Drug Commissioner's 2024 figure, which uses the Federal Criminal Police definition. Both figures are provisional."),

 ("life","daily",0,"city","Mumbai",None,[72.88,19.08],
  "drinks as much <b>water</b> a day as <b class=k>Mumbai</b>","1 billion gallons","1.06 billion gallons",
  "For scale, that is roughly what the Central Park Reservoir holds, though the reservoir was taken out of service in 1993 and no longer supplies anyone.",
  "Greater Mumbai has about 12 to 13 million people. Department of Environmental Protection water supply page (one billion gallons a day); the BrihanMumbai Municipal Corporation's daily supply of 4,000 million litres as reported by the Free Press Journal in September 2025 (other outlets cite 3,950 to 4,100). Converted at 3.78541 litres per US gallon. The Central Park Conservancy's page says the reservoir 'holds 1 billion gallons of water' and, if it were still in use, would supply the city 'for about one day'. It was decommissioned in 1993. No country's tap-water production fell within 10 percent; the whole Netherlands produces 1,160 million cubic metres a year against the city's 1,382."),
 ("life","daily",2,"country","Hungary",None,None,
  "uses as much <b>electricity</b> in a year as all of <b class=k>Hungary</b>","49.7 TWh","48.7 TWh",
  None,"New York Independent System Operator 2025 Gold Book, Table I-2, 2024 actual annual energy for Zone J (New York City); Hungary's 2024 electricity demand from Ember's yearly data as republished by Our World in Data. Statewide load was 150.9 TWh."),
 ("life","daily",3,"country","Denmark",None,None,
  "emits as much <b>greenhouse gas</b> as all of <b class=k>Denmark</b>","47.9 million tons","45.9 million tons",
  "Scopes differ: the city counts electricity where it is used; national inventories count it where it is made.",
  "Mayor's Office of Climate and Environmental Justice citywide inventory on NYC Open Data, 2024 total (CO2 equivalent, 100-year); Denmark's 2024 total greenhouse gas emissions from Our World in Data (Jones et al.), a national series that includes land-use change. Hungary (47.5 million tons, ratio 0.99) is the closest but already carries the electricity line."),
 ("life","daily",4,"structure","Eiffel Tower","Eiffel Tower",[2.29,48.86],
  "hauls away an <b>Eiffel Tower</b> of trash and recycling every day","10,886 tonnes","10,100 tonnes",
  "The city figure is converted: the Sanitation Department states 24 million pounds a day, which is 10,886 tonnes.","Department of Sanitation about page ('24 million pounds of trash, recycling, and compostable material every day', converted to metric tonnes); the Eiffel Tower's official key figures (10,100 tonnes total, 7,300 of it the metal frame)."),
 ("life","daily",5,"company","KFC (worldwide)","KFC",[-85.76,38.25],
  "has as many <b>restaurants and cafes</b> as there are <b class=k>KFCs</b> in the world","31,304","33,897",
  "Every food-service place the Health Department inspects, including bars that serve food and college cafeterias.",
  "Distinct establishments in the Health Department's restaurant inspection dataset on NYC Open Data (active status, inspected in the last three years), queried Sept. 3, 2026; KFC's worldwide unit count at Dec. 31, 2025 from Yum! Brands' fourth-quarter earnings release filed with the SEC. Pinned at Louisville, KFC's home."),
 ("life","daily",6,"city","Orlando",None,[-81.38,28.54],
  "has as many <b>hotel rooms</b> as <b class=k>Orlando</b>","124,000","over 130,000",
  None,"State Comptroller's July 2026 report on the city's hotel industry (average monthly active rooms in 2025; about 16,000 rooms used as shelter are excluded); Visit Orlando's press kit for the destination. Las Vegas is larger (about 150,000) but no fetched page stated its total."),
 ("life","daily",7,"country","Indonesia",None,[106.85,-6.2],
  "sits at the centre of a region that speaks as many <b>languages</b> as <b class=k>Indonesia</b>","700-plus","710",
  "The 700-plus count covers the whole New York metropolitan area, not the five boroughs, and is a field tally of immigrant and heritage language varieties rather than a census. Indonesia's is distinct living languages.",
  "Endangered Language Alliance's New York City language map ('700-plus language varieties'); Ethnologue's 2024 count for Indonesia as cited by Our World in Data. Papua New Guinea (840) is outside the band."),
 ("life","daily",8,"country","Georgia (the country)","Georgia",None,
  "files as many <b>311 requests a year</b> as the country of <b class=k>Georgia</b> has people","3.66 million","3.81 million",
  None,"Count of 2025 service requests in the 311 dataset on NYC Open Data; Georgia's 2023 population from Our World in Data. The State Comptroller corroborates 2024 at 'over 3.4 million'."),


 ("movement","likeforlike",4,"city","Shanghai",None,[121.47,31.23],
  "has almost as many <b>subway stations</b> as <b class=k>Shanghai</b>","472","523",
  "Systems count stations differently: New York's 472 sit inside 423 complexes.",
  "MTA's New York City Transit page; Shanghai's rail transit network at the end of 2025 as reported by Xinhua from official data. Beijing's own site gives 380 stations, a worse match."),

 ("place","likeforlike",17,"city","Los Angeles",None,[-118.24,34.05],
  "has as many <b>miles of water pipe</b> as <b class=k>Los Angeles</b>","7,000 mi","7,341 mi",
  "New York City's figure bundles in-city mains with the upstate tunnels and aqueducts; Los Angeles's counts mains and trunk lines only.","The Environmental Protection Department's 7,000 miles of water mains, tunnels and aqueducts, against the 7,341 miles of mainlines and trunk lines in the Los Angeles Department of Water and Power's 2024-25 water infrastructure plan. Los Angeles reports a further 300 miles of aqueduct separately. An earlier version of this line cited the city's water supply page, which does not state a mileage anywhere on it."),

 ("life","likeforlike",15,"state","Maryland",None,[-76.6,39.0],
  "runs as many <b>public library outlets</b> as all of <b class=k>Maryland</b>","206","218",
  "Outlets, not just branch buildings: the count includes 3 central libraries and 5 books-by-mail outlets, against Maryland's 15 and 24.",
  "Both counts are row counts of one federal file, the Institute of Museum and Library Services Public Libraries Survey for fiscal 2024, so central libraries, branches and books-by-mail outlets are counted the same way on both sides. New York City runs three separate systems: the New York Public Library across the Bronx, Manhattan and Staten Island, plus Brooklyn and Queens. The three systems advertise more locations than the federal file records, 219 against 206, because the survey lists the New York Public Library as its branch libraries and does not count its four research centers as outlets. Vermont (190), Oklahoma (223) and Oregon (225) were the next closest states."),
 ("place","likeforlike",16,"structure","Englischer Garten, Munich","Munich",[11.6,48.16],
  "has a <b>Central Park</b> about the size of Munich's <b class=k>Englischer Garten</b>","843 acres","929 acres",
  None,"Central Park Conservancy; the Bavarian Administration of State Palaces, Gardens and Lakes, which gives 376 hectares, converted at 2.47105 acres per hectare. Counting the adjoining Maximilian Park and court gardens takes the Munich park to 411 hectares, or 1,015 acres. No other famous urban park came closer."),
]
# SWAP: replace the comparison side of a pairing, keyed by the (file,row) that
# supplied its New York City figure. Value is (file,row) in the like-for-like
# research plus the new place, pin, sentence, display and methodology note.
SWAP = json.load(open('swap.json')) if os.path.exists('swap.json') else {}
items=[]
for realm,f,row,kind,place,short,ll,sentence,nd,md,cav,note in L:
    r = R[f][row]
    sw = SWAP.get(f'{f}:{row}')
    if sw:
        m = R[sw['file']][sw['row']]
        kind, place, short = sw['kind'], sw['place'], sw.get('place_short')
        ll, sentence, md = sw.get('lonlat'), sw['sentence'], sw['match_display']
        cav, note = sw.get('caveat'), sw['note']
        r = dict(r, match_value=m['match_value'], match_year=m.get('match_year',''),
                 match_url=m['match_url'], match_label=m['match_label'], match_quote=m['match_quote'])
        if sw.get('both'):  # the New York City side is restated from the same source too
            r = dict(r, nyc_value=m['nyc_value'], nyc_year=m.get('nyc_year',''),
                     nyc_url=m['nyc_url'], nyc_label=m['nyc_label'], nyc_quote=m['nyc_quote'])
            nd = sw['nyc_display']
    lon,lat = ll if ll else W[place.replace(' (the country)','')]
    items.append(dict(realm=realm,kind=kind,place=place,place_short=short,lon=lon,lat=lat,sentence=sentence,
        nyc_value=r['nyc_value'],match_value=r['match_value'],nyc_display=nd,match_display=md,caveat=cav,note=note,
        nyc_year=r.get('nyc_year',''),nyc_url=r['nyc_url'],nyc_source=r['nyc_label'],nyc_quote=r['nyc_quote'],
        match_year=r.get('match_year',''),match_url=r['match_url'],match_source=r['match_label'],match_quote=r['match_quote'],
        confidence=r.get('confidence','')))
# Tag each pairing by what the comparison measures. "same" means the other side
# is the same quantity (subway riders vs subway riders); "scale" means it is a
# population, a length or a capacity standing in for the size of the number.
# A "population" pairing stands the number against a headcount of people; a
# "landmark" pairing stands a length against a famous distance. Both are scale
# stand-ins rather than measurements of the same thing.
# Everything else compares two measurements of the same kind: riders against
# riders, dollars against dollars, beds against beds.
POP = re.compile(r'has people|holds fans')
DIST = re.compile(r'is long|is wide')
for it in items:
    plain = re.sub(r'<[^>]+>','',it['sentence'])
    it['compare'] = ('population' if POP.search(plain)
                     else 'landmark' if DIST.search(plain)
                     else 'same')
OV = {
 "Spain": dict(match_value=1725152000000, match_url="https://www.imf.org/external/datamapper/api/v1/NGDPD", match_source="GDP of Spain", match_quote="\"ESP\": {... \"2024\": 1725.152 ...}", match_year="2024 (IMF WEO NGDPD)"),
 "Jersey (Channel Islands)": dict(match_value=29120),
 "Guinea": dict(nyc_url="https://www.broadwayleague.com/press/press-releases/broadways-2024-2025-season-wraps-with-147-million-attendances-and-grosses-of-189-billion/", nyc_quote="During the 2024-2025 season, Broadway shows yielded $1.89 billion in grosses and total attendance reached 14.7 million.", nyc_source="Broadway attendance, 2024-25 season (Broadway League press release)", nyc_value=14700000, nyc_display="14.7 million", nyc_year="2024-25 season"),
 "Utah": dict(match_value=3538904, match_url="https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv", match_source="Population of Utah", match_quote="Utah,3271601,3283970,3339874,3393928,3449259,3502983,3538904 (NAME, ESTIMATESBASE2020, POPESTIMATE2020 ... POPESTIMATE2025)", match_year="2025 (Census Vintage 2025)"),
 "Guyana": dict(match_value=24659000000, match_url="https://www.imf.org/external/datamapper/api/v1/NGDPD", match_source="The GDP of Guyana", match_quote="\"GUY\": {... \"2024\": 24.659 ...}", match_year="2024 (IMF WEO NGDPD)"),
 "Bahamas": dict(match_value=401283, match_url="https://api.worldbank.org/v2/country/BHS/indicator/SP.POP.TOTL?date=2024&format=json", match_source="Population of the Bahamas", match_quote="{\"country\": {\"id\": \"BS\", \"value\": \"Bahamas, The\"}, \"countryiso3code\": \"BHS\", \"date\": \"2024\", \"value\": 401283}", match_year="2024"),
 "France": dict(match_value=68551653, match_url="https://api.worldbank.org/v2/country/FRA/indicator/SP.POP.TOTL?date=2024&format=json", match_source="Population of France", match_quote="France, 2024, 68,551,653", match_year="2024"),
}
for it in items:
    if it['place'] in OV: it.update(OV[it['place']])
order={r['key']:i for i,r in enumerate(REALMS)}
items.sort(key=lambda it: order[it['realm']])
extra = json.load(open('extra.json')) if os.path.exists('extra.json') else []
items += extra
intro = open('methodology_intro.html').read() if os.path.exists('methodology_intro.html') else '<p>Pending.</p>'
json.dump({"years":"2023 to 2026, mostly 2025","methodology_intro":intro,"realms":REALMS,"items":items},open('pairings-src.json','w'),indent=1)
print(len(items),'items')
