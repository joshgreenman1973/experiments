"""Write methodology.html with its tables filled from assets/meta.json,
so the numbers on the page always match the build. Run last."""
import json, gzip
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
meta = json.load(open(ROOT / "assets" / "meta.json"))
W, H = meta["W"], meta["H"]
nta = np.frombuffer(gzip.decompress((ROOT / "assets" / "nta.bin.gz").read_bytes()), dtype="<u2").reshape(H, W)

SOURCES = {
    1910: ("1910_tPop_NYC", "NT5, Sex by Race/Nativity (all cells summed)", "1910 tracts"),
    1920: ("1920_tPop_NYC", "NT1, Population, 1910 and 1920 (1920 column)", "1920 tracts"),
    1930: ("1930_tPop_NYC", "NT3, Sex by Race (all cells summed)", "1930 tracts"),
    1940: ("1940_tPH_NYC", "NT1, Total Population", "1930 tracts (see note)"),
    1950: ("1950_tPH_Major", "NT1, Total Population", "1950 tracts"),
    1960: ("1960_tPH", "NTSUP2, Total Persons", "1960 tracts"),
}
for y in (1970, 1980, 1990, 2000, 2010, 2020):
    SOURCES[y] = ("Time series D08 (nominal tracts)", "Persons under 18 plus persons 18 and over",
                  f"{y} tracts" + (" (Census cartographic file)" if y >= 2010 else ""))

def f(n): return f"{n:,}"

rows, dense = [], []
for e in meta["years"]:
    y = e["year"]
    diff = e["population"] / e["official"] - 1
    ds, tb, geo = SOURCES[y]
    rows.append(f"<tr><td>{y}</td><td>{ds}</td><td>{tb}</td><td>{geo}</td><td class=n>{f(e['tracts'])}</td>"
                f"<td class=n>{f(e['population'])}</td><td class=n>{f(e['official'])}</td><td class=n>{diff*100:+.2f}%</td>"
                f"<td class=n>{f(e['unplaced'])}</td></tr>")
    d = e["densestSqMi"]
    i = nta[int(d["row"]), int(d["col"])]
    name = meta["ntas"][i - 1]["name"] if i else "?"
    man = e["boroughs"]["Manhattan"] / e["population"]
    dense.append(f"<tr><td>{y}</td><td class=n>{f(round(d['people'], -3))}</td><td>{name}</td>"
                 f"<td class=n>{d['lat']:.4f}, {d['lon']:.4f}</td><td class=n>{man*100:.1f}%</td></tr>")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where New York lives: methodology</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Karla:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../house-style/house.css">
<style>
:root{{--accent:var(--sun)}}
.doc{{padding:8px clamp(16px,4vw,48px) 48px;max-width:900px}}
.doc p,.doc li{{max-width:70ch}}
.doc h2{{margin-top:34px}}
.tw{{overflow-x:auto;margin:12px 0 4px}}
table{{border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;min-width:640px}}
th,td{{text-align:left;padding:6px 14px 6px 0;border-bottom:1px solid var(--line2);vertical-align:top}}
th{{font-weight:700;border-bottom:1.5px solid var(--fg)}}
td.n,th.n{{text-align:right}}
code{{font-size:14px}}
</style>
</head>
<body>
<div class="sheet">
  <div class="strip"><span><a href="./">&larr; Where New York lives</a></span><span>Methodology</span></div>
  <div class="head">
    <h1>How the map was made</h1>
    <p class="finding">Twelve censuses of tract counts, spread over the city&rsquo;s land, smoothed and drawn as ground that rises with density.</p>
  </div>
  <div class="doc">

<h2>What the map shows</h2>
<p>For each decennial census from 1910 to 2020, the number of people living per square mile around every point in New York City, averaged over roughly an eighth of a mile. The ground is raised and colored by that density. The colors follow the legend exactly, and thin dark contour lines mark 25,000, 50,000, 100,000, 200,000 and 400,000 people per square mile. The height also rises with density, compressed slightly at the top (height is proportional to density to the 0.85 power) so the 1910 Lower East Side does not hide everything else. Light comes from the northwest and casts shadows to the southeast.</p>
<p>Between census years the map blends the two neighboring censuses in a straight line. The year counter moves through those in-between years, but only the census years are data.</p>

<h2>Sources</h2>
<p>All population counts are the Census Bureau&rsquo;s own tract tables, as compiled by IPUMS NHGIS at the University of Minnesota. New York City was one of eight cities the bureau divided into census tracts in 1910, which is why the map starts there. NHGIS also supplies the tract boundaries for 1910 through 2000. For 2010 and 2020 the boundaries are the Census Bureau&rsquo;s cartographic boundary files. The city&rsquo;s land, used to keep people out of the rivers and the harbor, is the Department of City Planning&rsquo;s borough boundaries clipped to the shoreline (<a href="https://data.cityofnewyork.us/City-Government/Borough-Boundaries/gthc-hcne">NYC Open Data gthc-hcne</a>).</p>
<p>Citation: Jonathan Schroeder, David Van Riper, Steven Manson, Grace Cooper, Zachary Krause, Tracy Kugler, Tsu Zhu and Steven Ruggles. IPUMS National Historical Geographic Information System: Version 21.0 [dataset]. Minneapolis, MN: IPUMS. 2026. <a href="http://doi.org/10.18128/D050.V21.0">doi.org/10.18128/D050.V21.0</a>. NHGIS&rsquo;s terms do not allow redistributing its tables, so this project publishes only the smoothed density grids derived from them. The scripts below fetch the original tables from NHGIS.</p>

<h2>Each census, checked against the official total</h2>
<p>&ldquo;Tract sum&rdquo; is the number of people the map places on the grid. &ldquo;Not placed&rdquo; counts people in tract records that have no boundary in any nearby census; they are left off the map.</p>
<div class="tw"><table>
<thead><tr><th>Census</th><th>NHGIS dataset</th><th>Table</th><th>Boundaries used</th><th class=n>Tracts with people</th><th class=n>Tract sum</th><th class=n>Official city total</th><th class=n>Difference</th><th class=n>Not placed</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table></div>
<ul>
<li><b>1920:</b> 20,590 people are in records NHGIS labels &ldquo;persons not associated with a specific tract.&rdquo; The bureau&rsquo;s own 1920 tract tables also sum to about 10,000 fewer people than the city total.</li>
<li><b>1930:</b> the tract tables sum to 12,930 more people than the published city total (0.19 percent). The difference is in the source tables and is left as is.</li>
<li><b>1940:</b> New York kept its 1930 census tracts for the 1940 census, and NHGIS&rsquo;s 1940 boundary file covers the city only at the coarser level of health areas. So the 1940 tract counts are joined to the 1930 tract boundaries by tract number: 99.6 percent of the 1940 tract numbers match. Each matched tract&rsquo;s 1940 count was compared with its 1930 count. The median tract grew 7 percent, close to the city&rsquo;s 8 percent. The biggest jumps are real: Queens tract 25 went from 277 people to 10,731 when the Queensbridge Houses opened in 1939. Seven tracts with 4,211 people, four of them Manhattan tracts numbered 311 to 317, have no boundary in any nearby census and are left off.</li>
<li><b>1970 to 1990:</b> the people left off are almost all in tracts whose numbers end in .99, which the bureau used for the crews of ships in port.</li>
</ul>

<h2>From tracts to a grid</h2>
<ol>
<li>The city is covered by a grid of squares a twentieth of a mile (80.5 meters) on a side, {W} by {H} squares, in the UTM zone 18N projection. With that size, 20 by 20 squares make exactly one square mile.</li>
<li>A square counts as land if its center falls inside today&rsquo;s shoreline-clipped boroughs.</li>
<li>Each tract&rsquo;s people are spread evenly over the land squares whose centers fall inside the tract. No tract was too small to own at least one square.</li>
<li>The grid is smoothed with a Gaussian kernel with a standard deviation of {meta['sigma_cells']} squares (about {meta['sigma_cells']*meta['cell_m']/1609.344:.2f} mile). The smoothing is divided by the share of land under the kernel, so people near the shore stay on the shore instead of draining into the water, and water squares are then set to zero.</li>
<li>The result is converted to people per square mile and stored as 16-bit values on a square-root scale. The page decodes them and draws the map with WebGL.</li>
</ol>

<h2>The most crowded square mile, and Manhattan&rsquo;s share</h2>
<p>The most crowded square mile is the 20-by-20-square window, anywhere on the grid, that holds the most people before smoothing. Because people are spread evenly within each tract, it is an estimate. Its location is named by the 2020 Neighborhood Tabulation Area under its center. Manhattan&rsquo;s share counts the people placed inside Manhattan&rsquo;s borough boundary. Before 1914 the Bronx was part of New York County, so the boundary, not the county field in the census tables, decides which borough a 1910 tract belongs to. For 1970 through 2010 the placed borough totals were compared with the sums of the Department of City Planning&rsquo;s community-district counts (<a href="https://data.cityofnewyork.us/City-Government/New-York-City-Population-By-Community-Districts/xi7c-iiu2">xi7c-iiu2</a>) and agree within 0.8 percent for every borough.</p>
<div class="tw"><table>
<thead><tr><th>Census</th><th class=n>People in the most crowded square mile</th><th>Centered in</th><th class=n>Center (lat., long.)</th><th class=n>Share in Manhattan</th></tr></thead>
<tbody>
{''.join(dense)}
</tbody></table></div>

<h2>What to keep in mind</h2>
<ul>
<li>Early tracts in Queens, Staten Island and the outer Bronx were large and thinly settled, so in the first decades those areas look like smooth plains. The map cannot show where within a big tract people lived.</li>
<li>The shoreline is today&rsquo;s. Land made later, like Battery Park City, shows as land in 1910 but has no people until a tract there does. Parks, cemeteries and airports show as low ground in years when the tracts covering them were drawn separately, which is most of them.</li>
<li>Tract boundaries change from census to census. Smoothing hides most of that, but small shifts between frames can come from redrawn tracts rather than people moving.</li>
<li>The 2020 tract counts include the small amount of noise the Census Bureau adds to protect privacy.</li>
</ul>

<h2>Rebuilding it</h2>
<p>Scripts are in <code>scripts/</code>: <code>fetch_nhgis_historic.py</code> requests the 1910&ndash;1960 tables and boundaries from the NHGIS API (it needs a free IPUMS API key); the 1970&ndash;2020 time series and boundaries come from the same NHGIS sources. <code>build_grids.py</code> makes the grids, <code>build_places.py</code> adds labels and the neighborhood lookup, and <code>build_methodology.py</code> writes this page.</p>
<p>The idea comes from an animated density map of France, &ldquo;L&agrave; o&ugrave; vit la France,&rdquo; shared by Yan Holtz of the R Graph Gallery.</p>
  </div>
</div>
</body>
</html>
"""
(ROOT / "methodology.html").write_text(html)
print("wrote methodology.html")
