# Methodology: NYC vacant storefronts

## Data source

This dashboard draws from the **Storefronts Reported Vacant or Not (SRVN)** dataset published by the NYC Department of Finance (DOF) on NYC Open Data.

**API endpoint:** `https://data.cityofnewyork.us/resource/92iy-9c3n.json`

### Background: Local Law 157 of 2019

In 2019, the New York City Council passed Local Law 157, which required the Department of Finance to establish and maintain a public registry of commercial storefronts and their vacancy status. The law was designed to improve transparency around commercial vacancy patterns across the city, particularly in response to growing concerns about empty storefronts in retail corridors.

Under the law, owners of ground-floor or second-floor commercial properties are required to report annually whether their storefronts are vacant or occupied. The resulting dataset -- the SRVN registry -- is published on NYC Open Data and updated as new filings come in.

## What counts as "vacant"

A storefront is classified as vacant based on the property owner's self-reported filing. The dataset contains two vacancy fields depending on the reporting period:

- `vacant_on_12_31`: Whether the storefront was vacant as of December 31 of the reporting year
- `vacant_6_30_or_date_sold`: Whether the storefront was vacant as of June 30 or the date sold

A storefront is coded as vacant if either field contains "YES." If both fields are absent or contain "NO," the storefront is coded as occupied.

## Deduplication

When multiple filings exist for the same property (identified by BBL -- borough, block, lot), the dashboard uses only the most recent reporting year for each property. This prevents double-counting properties that have filed in multiple years.

## How the vacancy rate is calculated

The vacancy rate displayed is:

**Vacancy rate = (number of vacant storefronts) / (total registered storefronts) x 100**

This is the vacancy rate among properties that have filed with DOF, not among all commercial storefronts citywide. The denominator includes only storefronts in the registry.

## Community district labels

Community district codes in the dataset are three-digit numbers where the first digit represents the borough (1 = Manhattan, 2 = Bronx, 3 = Brooklyn, 4 = Queens, 5 = Staten Island) and the remaining digits represent the district number. The dashboard translates these into labels like "MN 1" (Manhattan Community District 1) or "BK 7" (Brooklyn Community District 7).

## Limitations

- **Self-reported data.** Vacancy status is reported by property owners, not independently verified. Owners may have incentives to misreport, and compliance with the filing requirement varies.
- **Incomplete coverage.** Not all commercial storefronts in the city are captured. The registry depends on owners filing as required by law, and enforcement of the filing requirement has been inconsistent.
- **Lag.** The data reflects conditions at specific reporting dates (December 31 or June 30), not real-time vacancy. A storefront that became vacant or occupied between reporting dates will not be reflected until the next filing.
- **Definition of vacancy.** The law defines vacancy based on owner reporting. A storefront with a signed lease but no active business may or may not be reported as vacant, depending on how the owner interprets the question.
- **No distinction between types of vacancy.** The data does not distinguish between storefronts that are actively marketed for lease, those undergoing renovation, those held vacant for other reasons, or those in buildings slated for demolition or redevelopment.
- **Geographic accuracy.** Latitude and longitude coordinates are derived from property addresses and may not precisely reflect the storefront entrance location, especially for corner properties or large buildings.

## Other data considered

The DOB NOW: Build - Approved Permits dataset (`https://data.cityofnewyork.us/resource/rbx6-tga4.json`) was considered as a secondary source to provide context on new retail construction near vacant storefronts. It is not currently integrated into the dashboard but could be added in future iterations to show where new commercial space is being built relative to existing vacancies.

## Update frequency

The SRVN dataset is updated on a rolling basis as property owners file their annual reports. The dashboard fetches fresh data each time it loads and displays only the most recent filing for each property.
