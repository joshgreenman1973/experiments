# Methodology: New York City school building utilization (`nyc-school-building-utilization`)

## Data sources

1. **Enrollment, Capacity and Utilization Report (the Blue Book), Target Calculation (`gkd7-3vk7`)**
   - Published jointly by the New York City School Construction Authority (SCA) and Department of Education (DOE) on NYC Open Data: <https://data.cityofnewyork.us/Education/Enrollment-Capacity-And-Utilization-Report/gkd7-3vk7>
   - Archive contains 20,754 rows across eight `Data As Of` timestamps. One snapshot (`02/28/2026`, 6 rows) is an incomplete fragment and is excluded. The seven complete historical editions correspond to the following school years (verified against New York State Education Department Oct. 31 audited enrollment registers):
     - `04/27/2015`: 2013–14 school year (1,304 buildings with positive capacity; 1,004,616 students; 1,085,532 target seats)
     - `09/12/2017`: 2015–16 school year (1,341 buildings; 1,035,617 students; 1,082,219 target seats)
     - `01/08/2018`: 2016–17 school year (1,367 buildings; 1,033,669 students; 1,087,796 target seats)
     - `01/31/2019`: 2017–18 school year (1,376 buildings; 1,021,599 students; 1,087,899 target seats)
     - `12/18/2019`: 2018–19 school year (1,384 buildings; 1,006,640 students; 1,089,076 target seats)
     - `01/04/2023`: 2021–22 school year (1,394 buildings; 891,829 students; 1,093,502 target seats)
     - `09/09/2026`: 2025–26 school year, Oct. 31, 2025 register (1,350 buildings with positive capacity out of 1,384 distinct `Bldg ID` codes; 862,834 students; 1,076,362 target seats)

2. **DOE Location Code Generation and Management System (LCGMS) and 2019–20 School Locations (`wg9x-4ke6`)**
   - Used to geocode `Bldg ID` codes to street addresses, Neighborhood Tabulation Areas (NTAs) and latitude/longitude coordinates. Out of 1,350 buildings with positive target capacity in 2025–26, **1,344 (99.6%)** matched to coordinates.

3. **DOE 2025–26 Class Size Report (Table C, Nov. 15, 2025, data as of Oct. 31, 2025)**
   - Published pursuant to New York State Education Law 211-d (<https://infohub.nyced.org/reports/government-reports/class-size-reports>).
   - Covers 1,561 District 1–32 schools (120,035 non-exempt classes and 22,527 exempted classes). Schools are matched by DBN and Blue Book Organization ID (`Org ID`) to their primary building in the 2025–26 Blue Book.

## Definitions and processing rules

- **Building-level deduplication:** The Blue Book is structured with one row per organization per building (`3,132` rows in 2025–26), repeating `Bldg Enroll`, `Target Bldg Cap` and `Target Bldg Util` on every row sharing a `Bldg ID`. Building-level metrics are computed after deduplicating on `Bldg ID` and excluding 34 administrative or unrated building codes with zero or blank `Target Bldg Cap`.
- **Proximity pairs:** For each of the 337 geocoded buildings with `Target Bldg Util > 100%`, straight-line haversine distance is computed to every active building (`Bldg Enroll > 0`) with `Target Bldg Util < 60%`. Any pair of buildings that shares a school organization (`Org ID`) or resolves to coordinates within 0.01 miles (such as campus buildings sharing a single parcel centroid) is excluded.
- **Co-location splits:** A building is classified as having a co-located split if it houses at least two active K–12 school organizations (`Org ID` matching `^[MXKQR]\d{3}$`, `Incl. Class == ""`, `Org Enroll >= 50` and `Org Target Cap >= 50`, excluding Alternate Learning Centers and citywide Pathways to Graduation programs) where at least one organization has `Org Target Util > 100%` and at least one has `Org Target Util < 60%`.

## Rebuilding the data

Run `python3 build_data.py` to regenerate `data/utilization.json` and the four CSV files in `data/`.
