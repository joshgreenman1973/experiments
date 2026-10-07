"""Write methodology.html from the built data, so every count and the placement table match it."""
import csv, collections, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = json.load(open(os.path.join(ROOT, 'data', 'sites.json')))
rows = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'chargers.csv'))))
e = html.escape
nf = lambda n: f'{n:,}'

src = [r for r in rows if r['source'].startswith('NYC Open Data')]
fixed = [r for r in rows if r['placement'] != 'none']
how = collections.Counter(r['placement'] for r in src)
no_coord = [r for r in src if r['placement'] not in ('city', 'corrected')]
no_coord_fixed = [r for r in no_coord if r['placement'] != 'none']
ports = lambda rs: sum(int(r['ports']) for r in rs)
sites = D['sites']
approx_sites = [s for s in sites if s['how'] == 'approx']

LABEL = {'address': 'Geocoded address', 'block': 'Mid-block', 'corner': 'Street corner', 'facility': 'Named facility or station group',
         'approx': 'Approximate', 'corrected': 'Corrected', 'none': 'Not mapped'}
log = [r for r in rows if r['placement'] != 'city']
log.sort(key=lambda r: (list(LABEL).index(r['placement']), r['address'], r['station']))

table = '\n'.join(
    f"<tr><td>{e(r['station'])}</td><td>{e(r['agency'])}</td><td>{e(r['address'] or '(none)')}</td><td>{e(LABEL[r['placement']])}</td>"
    f"<td>{e(r['placement_note'])}</td></tr>" for r in log)

page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How the chargers were mapped</title>
<meta name="description" content="Sources, placement rules and limits for the map of New York City's fleet charging sites.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Karla:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../house-style/house.css">
<style>
:root{{--accent:var(--cyan)}}
.doc{{padding:10px clamp(16px,4vw,48px) 40px;max-width:78ch}}
.doc h2{{margin:30px 0 8px}}
.doc p,.doc li{{line-height:1.6}}
.doc li{{margin-bottom:6px}}
.wide{{padding:0 clamp(16px,4vw,48px) 40px;overflow-x:auto}}
.wide table.h{{min-width:820px;font-size:.88rem}}
.wide td{{vertical-align:top}}
</style>
</head>
<body>
<div class="sheet">
  <div class="strip"><a href="./">&larr; Back to the map</a><span>Built {e(D['meta']['built'])}</span></div>
  <div class="head">
    <h1>How the chargers were mapped</h1>
    <p class="finding">The city publishes addresses for {nf(len(src))} fleet charging stations; {nf(len(no_coord))} of them came without map coordinates, and each of those was placed by a rule written down below.</p>
  </div>
  <div class="doc">
    <h2>Sources</h2>
    <ul>
      <li><a href="https://data.cityofnewyork.us/City-Government/NYC-EV-Fleet-Station-Network/fc53-9hrv">NYC EV Fleet Station Network</a> (dataset fc53-9hrv) on New York City Open Data, published by the Department of Citywide Administrative Services. Last updated May 12, 2026. One row per charging station, with agency, charger type, number of ports, address and, for most rows, latitude and longitude. {nf(len(src))} rows, {nf(ports(src))} ports.</li>
      <li>The department's <a href="https://www.nyc.gov/assets/dcas/downloads/pdf/fleet/electric-vehicle-public-charging-rules.pdf">public charging rules and list of public chargers</a>, updated Sept. 23, 2026. It names 30 fleet stations open to anyone: 26 fast chargers and 4 solar carports. Ten of them, the fast chargers at the Seuffert Bandshell lot in Forest Park, are not in the May dataset; they are added here from that list and marked as such. Prices shown on the map for these sites come from this document.</li>
      <li>The department's <a href="https://www.nyc.gov/assets/dcas/downloads/pdf/fleet/electric-vehicle-charging-stations-map.pdf">October 2026 network map</a>, a picture with counts and no addresses. It is used only for the comparison table on the map page.</li>
    </ul>

    <h2>What counts as public</h2>
    <p>A site is marked open to the public if any station there is on the Sept. 23 public list, is a Transportation Department curbside charger, is in a Transportation Department municipal parking lot, or is one of the six Brooklyn Army Terminal lamppost chargers the dataset lists as public with an adapter. The dataset's own "public charger" column was used for the last three; it also labels the two City Hall ports "City Hall Charging," which this map does not treat as public. The prices for curbside and municipal-lot chargers are the dataset's "fee for city drivers" column, shown as the listed price. In all, {nf(sum(s['pp'] for s in sites))} ports at {sum(1 for s in sites if s['pub'])} sites are marked public.</p>

    <h2>Grouping stations into sites</h2>
    <p>Each dot is a site: all stations whose final coordinates agree to five decimal places (about a meter). That turns {nf(len(fixed))} fixed stations into {nf(len(sites))} sites. A site is labeled with the address the city itself geocoded there when there is one, and drawn in the color of the kind of charger with the most ports at it. Neighborhood names come from the city's 2020 Neighborhood Tabulation Areas; a site on a beach or pier that falls just outside every area takes the nearest one. Eleven mobile chargers have no address and are not mapped.</p>

    <h2>Placing the stations the city did not geocode</h2>
    <p>{nf(len(no_coord))} rows arrive with no coordinates, including every upstate and Westchester site. Leaving out the 11 mobile units, the other {nf(len(no_coord_fixed))} were placed this way, in this order:</p>
    <ul>
      <li><b>Mid-block ({how['block']} stations).</b> Transportation Department curbside chargers are listed as a street and two cross streets. Each was placed halfway between the two corners, using the city's street centerline file (<a href="https://data.cityofnewyork.us/City-Government/Centerline/inkn-q76z">CSCL, inkn-q76z</a>).</li>
      <li><b>Street corner ({how['corner']}).</b> Listings that name an intersection, placed at that corner from the same centerline file. Two Sanitation rows listed as "47-01 48th Street" were put at 48th Street and 47th Avenue, following the Queens convention that the first part of a house number names the cross street.</li>
      <li><b>Geocoded address ({how['address']}).</b> City addresses run through the city's own address search (<a href="https://geosearch.planninglabs.nyc/">Planning Labs GeoSearch</a>) and accepted only when the house number it returned matched the one asked for (obvious typos, like "350 80 St" for 350 Beach 80th Street, were fixed first and are noted on the row); upstate addresses run through the <a href="https://geocoding.geo.census.gov/">Census Bureau geocoder</a>, and a handful it could not find through OpenStreetMap's Nominatim, again only on a house-level match.</li>
      <li><b>Named facility or station group ({how['facility']}).</b> When the listing names a place rather than an address (Orchard Beach, Pier 36, the Queens Museum) the station was placed there; when other stations in the same group (same station-name prefix, same ZIP code) already had city coordinates, it was placed with them.</li>
      <li><b>Approximate ({how['approx']}).</b> Everything that could not be matched at house level: listings like "Hazen St" on Rikers Island, numbers that do not exist on the named street, and a few upstate road addresses. These are placed on the right street or at the right facility, and the map says "Approximate" on each of the {len(approx_sites)} sites they fall into. All Rikers Island stations without a usable address share one point, the city's own "Rikers Island" location, which is why that site shows {next(s['n'] for s in sites if s['a'] == 'Rikers Island')} ports.</li>
    </ul>

    <h2>Checking the city's coordinates</h2>
    <p>Each of the {nf(how['city'] + how['corrected'])} rows that came with coordinates was checked two ways: whether the point falls inside the ZIP code it is listed with, using the city's ZIP code boundaries (<a href="https://data.cityofnewyork.us/Health/Modified-Zip-Code-Tabulation-Areas-MODZCTA-/pri4-ifjk">MODZCTA</a>), and how far it sits from where the city's address search puts the same address. Most mismatches were wrong ZIP codes on correctly placed points, or addresses the search could not read. Two were wrong points, and both were moved ({how['corrected']} stations):</p>
    <ul>
      <li>Sanitation's Brooklyn 18 garage, listed at 105-01 Foster Avenue in Canarsie, was plotted at Foster Avenue in Midwood, about 4.7 kilometers west. Moved to 10501 Foster Avenue.</li>
      <li>One of four Sanitation chargers at 80 Henry Street, ZIP 10002, was plotted at 80 Henry Street in Brooklyn Heights; the other three are in Manhattan. Moved to join them.</li>
    </ul>
    <p>One disagreement is left as published. A Transportation Department station listed as 99-2703 Richmond Terrace, ZIP 10303, which would put it in Mariners Harbor, is plotted near the St. George ferry terminal, about 6 kilometers east, and the dataset's own neighborhood code agrees with the point. With no way to tell which is right, the map keeps the city's point. The check can be rerun with <code>build/check_coords.py</code>.</p>

    <h2>Against the October 2026 map</h2>
    <p>The department's October picture counts 2,632 ports. Its line items add up to 2,662, which is 30 more; 30 is the number of public chargers those lines add on. This map has {nf(ports(rows))} ports including the mobile units. Nearly all of the gap is in ordinary Level 2 plugs (103 fewer), fast chargers (33 fewer) and solar canopies (12 fewer), which points to installations made between May and October that the open dataset does not yet include. The map will catch up when the dataset is updated; rebuilding is one command.</p>

    <h2>Limits</h2>
    <ul>
      <li>This is the city's list as published. A listed charger may be broken, removed or behind a gate; the dataset says nothing about status.</li>
      <li>Most sites are for city vehicles only. Being on this map does not mean a member of the public can use a charger; look for the public marking and the posted rules.</li>
      <li>Approximate placements are on the right street or at the right facility, not at the exact plug.</li>
      <li>Agency names are spelled out from the dataset's acronyms. A site used by two agencies shows both; the agency chart splits its ports evenly between them.</li>
    </ul>

    <h2>Files</h2>
    <ul>
      <li><a href="data/chargers.csv">data/chargers.csv</a>: every station, with final coordinates and how each was placed.</li>
      <li><a href="data/sites.json">data/sites.json</a>: the sites the map draws.</li>
      <li>The build scripts, in <code>build/</code> in the repository: <code>build_data.py</code> (the placement rules), <code>curbside.py</code> (the block and corner table), <code>lookup.py</code> (the cached geocoder calls) and this page's generator.</li>
    </ul>

    <h2>Every station not placed by the city's own coordinates</h2>
    <p>{nf(len(log))} rows: the {nf(len(no_coord))} the city did not geocode, the {how['corrected']} it geocoded wrongly and the 10 Forest Park fast chargers from the September public list.</p>
  </div>
  <div class="wide">
    <table class="h">
      <tr><th>Station</th><th>Agency</th><th>Listed address</th><th>Placement</th><th>Note</th></tr>
{table}
    </table>
  </div>
</div>
</body>
</html>
'''
open(os.path.join(ROOT, 'methodology.html'), 'w').write(page)
print('methodology rows', len(log), dict(how))
