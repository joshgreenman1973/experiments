# 311 streetlight outage map

## What it shows

This interactive map visualizes every 311 complaint about a broken or malfunctioning streetlight in New York City since Jan. 1, 2024. It draws on more than 50,000 complaints to reveal which blocks, neighborhoods and police precincts have the worst and most persistent outage problems.

The map offers several views:

- **Hex grid** shows complaint density across the city using a hexagonal grid. Darker red hexes have more complaints. This is the best view for seeing broad geographic patterns.
- **All spots** plots every complaint location as a dot, with size and color scaled to the number of repeat complaints at that spot.
- **Chronic dark spots (10+ and 20+)** isolate the locations with the highest complaint totals — places where streetlights have been reported out again and again. These appear as pulsing circles, with faster pulses indicating more complaints.

Rankings can be viewed three ways:

- **By address** shows the individual locations with the most repeat complaints.
- **By census tract** shows total complaints per 2020 census tract.
- **Per square mile** normalizes by census tract area, revealing which tracts have the highest concentration of outages relative to their size.

Clicking any dot or hex cell shows details including address, neighborhood, complaint count and how many are still open.

## What's included

The data covers eight complaint descriptors from the 311 "Street Light Condition" category:

- Street Light Out
- Multiple Street Lights Out
- Street Light Lamp Dim
- Street Light Lamp Missing
- Fixture/Luminaire Out of Position
- Fixture/Luminaire Damaged
- Fixture/Luminaire Missing
- Flood Light Lamp Out

These are all complaints about pole-mounted streetlights that illuminate streets and sidewalks. Traffic signals and pedestrian signals have entirely separate 311 categories and are not included.

## What's excluded

Complaints at parks, playgrounds, bridges, expressways, parkways, highways, cemeteries, greenways and other non-street locations are filtered out by address pattern matching. The goal is to focus on the streetlights that illuminate ordinary streets and sidewalks where people walk and drive at night.

## How it was built

The map is a single HTML file with no build step or server-side code. It runs entirely in the browser.

**Data source:** NYC Open Data's 311 Service Requests dataset (endpoint: `erm2-nwe9`), queried live via the Socrata API. The app fetches all matching complaints in 5,000-record batches and caches the results in the browser's localStorage for six hours so repeat visits load faster.

**Map:** Built with Leaflet.js on CARTO dark basemap tiles.

**Hex grid:** Uses Uber's H3 spatial indexing library (resolution 8, roughly 0.7 square kilometers per cell) to aggregate complaints into hexagonal cells.

**Chronic dark spots:** Locations are clustered to approximately 50-meter blocks by rounding coordinates. The 10+ and 20+ views show locations exceeding those complaint thresholds.

**Census tract assignment:** 2020 census tract boundaries are loaded from NYC Open Data (`weqx-t5xr`) and each complaint is assigned to a tract using a bounding-box-accelerated ray-casting point-in-polygon algorithm. Per-square-mile rates are calculated from the tract boundary's `shape_area` field (converted from square feet). Tracts with fewer than three complaints are filtered from the density view to reduce noise from small or low-population tracts.

**Neighborhoods:** Mapped from NYC community board codes to common neighborhood names using a built-in lookup table covering all 59 community boards.

**Progressive loading:** The map appears after the first batch of data arrives (a few seconds) rather than waiting for all 60,000+ records. Data continues loading in the background and the map updates when complete.

## Key findings

- **More than 50,000 streetlight outage complaints** have been filed since Jan. 2024.
- **Bedford-Stuyvesant, Brownsville and East New York** dominate the list of worst individual repeat locations, with some addresses logging 20 to 33 complaints.
- Normalizing by census tract area reveals the **highest outage concentrations** in dense neighborhoods across Manhattan, the Bronx and Brooklyn, rather than the sprawling tracts that dominate raw counts.
- Roughly **900 complaints remain open** at any given time.

## Tools and libraries

- [Leaflet.js](https://leafletjs.com/) — mapping
- [H3-js](https://h3geo.org/) — hexagonal spatial indexing
- [CARTO](https://carto.com/) — dark basemap tiles
- [NYC Open Data](https://opendata.cityofnewyork.us/) — 311 complaints and precinct boundaries
