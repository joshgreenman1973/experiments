# Methodology: The empty classroom and the crowded one (`nyc-school-building-utilization`)

Version 2, Nov. 6, 2026. Rebuild with `python3 build_data.py`.

## Sources

1. **Enrollment, Capacity and Utilization Report (the Blue Book), target calculation.** School Construction Authority and Department of Education, NYC Open Data [`gkd7-3vk7`](https://data.cityofnewyork.us/Education/Enrollment-Capacity-And-Utilization-Report/gkd7-3vk7). 20,754 rows across seven editions. Each edition is labeled here by the October registers it uses; the 2025–26 label was checked against the header of the School Construction Authority's own PDF, which is dated Sept. 9, 2026, and based on Oct. 31, 2025 audited registers.

   | Data as of | School year | Buildings with capacity | Students | Target seats | Under 60% | Over 100% |
   |---|---|---|---|---|---|---|
   | 04/27/2015 | 2013–14 | 1,304 | 1,004,616 | 1,085,532 | 115 | 567 |
   | 09/12/2017 | 2015–16 | 1,332 | 1,035,617 | 1,082,219 | 113 | 639 |
   | 01/08/2018 | 2016–17 | 1,320 | 1,029,414 | 1,084,178 | 125 | 617 |
   | 01/31/2019 | 2017–18 | 1,330 | 1,023,869 | 1,096,931 | 153 | 605 |
   | 12/18/2019 | 2018–19 | 1,336 | 1,012,330 | 1,096,744 | 154 | 568 |
   | 01/04/2023 | 2021–22 | 1,337 | 915,272 | 1,087,390 | 224 | 405 |
   | 09/09/2026 | 2025–26 | 1,350 | 862,834 | 1,076,362 | 301 | 337 |

   The 2014–15, 2019–20, 2022–23, 2023–24 and 2024–25 editions are published as PDFs but are not in the dataset.

2. **Department of Education school directory (LCGMS)**, for each school's grades ("Grades Final"), address and district.

3. **Building locations**, in order of preference: the Department of City Planning's Facilities Database (address match to the building's own code), the 2019–20 school locations file (NYC Open Data `wg9x-4ke6`, `Primary_building_code`), then NYC GeoSearch on the building's address. 1,214 of the 1,350 buildings were placed this way. 130 more could be placed only at a school's main site; they are drawn on the map, marked as approximate in the building panel and left out of every distance comparison. Six could not be placed.

4. **Class size report, Table C**, Nov. 15, 2025, data as of Oct. 31, 2025 ([InfoHub](https://infohub.nyced.org/reports/government-reports/class-size-reports)), published under Education Law 211-d. Citywide: 1,533 schools, 150,744 classes, of which 10,535 were exempted and 140,209 counted; 89,749 of the counted classes (64 percent) were within the caps. District 75 and charter schools are not in Table C.

## Rules

- **Buildings.** The Blue Book has one row per organization per building (3,132 rows in 2025–26) and repeats the building totals on each. Buildings are counted once each. 34 administrative codes with no capacity are dropped, leaving 1,350.
- **Use of capacity.** Building enrollment divided by target building capacity. Under 60 percent and over 100 percent use the Blue Book's rounded percentage. 16 of the 301 buildings under 60 percent have no enrollment.
- **Formula break.** The 2019–20 Blue Book cut the planning class size from 28 to 23 in grades 4 to 8 and from 30 to 25 in high school. Editions before and after are not strictly comparable; the page breaks its lines there.
- **Grades.** Elementary is prekindergarten to fifth grade, middle is sixth to eighth, high school is ninth to 12th. A building is tagged with the union of the bands served by its general-education schools that each hold at least 10 percent of building enrollment. District 75 and District 79 programs are left out of the tag. 99 buildings have no tag.
- **Nearest under-60 building.** For each crowded building placed from its own address, the nearest building under 60 percent full with enrollment, measured in straight-line miles, three ways: any grades, sharing at least one band, and exactly the same tag. A pair is excluded if the two buildings share a school or are within 0.01 mile of each other (campus buildings that share one address point). "Within half a mile" means strictly less than 0.5 mile. Results: of 299 crowded buildings placed from their own address, 81 have an under-60 building of any grades within half a mile, 54 one sharing a band, 26 one with exactly the same grades. Within a mile: 177 and 119.
- **Featured pairs.** The ranked list on the page uses exact-grade pairs within half a mile where both buildings have at least 300 seats, ranked by the smaller of the crowded building's students over capacity and the other building's empty seats. Crowded buildings that house a charter school, and the specialized high schools (Stuyvesant, Brooklyn Tech, Bronx Science, Staten Island Tech, Brooklyn Latin, the High School of American Studies at Lehman College and LaGuardia), are left out of that list but stay on the map.
- **Split under one roof.** At least two schools in the building, each with at least 50 students and 50 seats, one above 100 percent of its assigned capacity and one below 60 percent. District 75 and District 79 programs are left out. 38 buildings qualify (55 at a 75 percent threshold): 20 where the crowded school is a charter and the emptier one a district school, 15 with only district schools and three other mixes. Charter capacity is the target formula applied to the rooms a charter was assigned, and charters are not bound by the class-size law, so a charter's percentage measures its space, not necessarily crowding.
- **Class sizes by building.** Each school's Table C counts are assigned to one building, the one where that school has the most students, so no class is counted twice. Then classes are summed by the building's utilization band.

  | Building band | Counted classes | Within caps | Share | Exempted |
  |---|---|---|---|---|
  | Under 60% | 23,445 | 18,924 | 80.7% | 0 |
  | 60% to 79% | 41,543 | 29,525 | 71.1% | 278 |
  | 80% to 99% | 38,065 | 21,938 | 57.6% | 1,095 |
  | Over 100% | 35,058 | 18,394 | 52.5% | 9,155 |

- **Class-size law.** Education Law 211-d caps classes at 20 (kindergarten to third grade), 23 (fourth to eighth) and 25 (high school). The 2026 amendment, S10615/A11539 (Chapter 155 of 2026), moved full compliance to the 2029–30 school year.

## Changes from version 1

Version 1 described an eighth "02/28/2026" snapshot that is not in the data; listed edition totals that did not match its own data; reported Table C totals (1,561 schools, 120,035 counted classes, 22,527 exempted) that do not appear in the source; assigned each school's classes to every building it occupies; gave the compliance deadline as 2027–28; placed buildings at a school's main-site coordinates rather than their own address; paired crowded and half-empty buildings regardless of grades; counted 46 split buildings by including District 75 and District 79 programs; and opened on LaGuardia High School, which admits citywide by audition.

## Limits

Target capacity is a planning figure, not a fire-code limit. Straight-line distance ignores highways, rail yards and attendance zones. Some underused buildings are new and still filling grade by grade. Moving students between buildings requires rezoning or a change in use, an educational impact statement and a Panel for Educational Policy vote.

## Rebuilding

`build_data.py` reads the Blue Book, LCGMS, facilities and class-size files saved in `../nyc-schools-atlas/data/` and writes `data/utilization.json` and four CSVs.
