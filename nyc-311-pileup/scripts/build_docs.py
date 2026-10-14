"""Write methodology.html and how-i-built-this.html from the build's own numbers.

Reads build/checks.json, data/summary.json and data/cadence.json. Run after
build_data.py and analyze_cadence.py.

Usage: python3 scripts/build_docs.py
"""
import html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
import build_data as B  # noqa: E402

K = json.load(open(os.path.join(ROOT, 'build', 'checks.json')))
S = json.load(open(os.path.join(ROOT, 'data', 'summary.json')))
C = json.load(open(os.path.join(ROOT, 'data', 'cadence.json')))
W = C['windows']
CAD = {r['address']: r for r in C['addresses']}


def f(n):
    return f'{int(round(n)):,}'


def p(x, d=1):
    s = f'{x * 100:.{d}f}'
    return (s[:-2] if s.endswith('.0') else s) + '%'


MON = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.']
WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']


def w(n):
    return WORDS[int(n)] if 0 <= n < 10 and n == int(n) else f(n)


def day(s, year=True):
    y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
    return f'{MON[m - 1]} {d}' + (f', {y}' if year else '')


def clock(s):
    h, mi = int(s[11:13]), int(s[14:16])
    if h == 12 and mi == 0:
        return 'noon'
    if h == 0 and mi == 0:
        return 'midnight'
    ap = 'a.m.' if h < 12 else 'p.m.'
    h = h % 12 or 12
    return f'{h}:{mi:02d} {ap}' if mi else f'{h} {ap}'


def mil(n):
    return f'{n / 1e6:.1f} million' if n >= 1e6 else f(n)


TOT, UN, BL, NA, N, TK = K['total'], K['unplaced'], K['blank'], K['named'], K['locations'], K['top_k']
at = K['at']
top5 = at['0.05']
newest = K['newest_record'][:10]

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Karla:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../house-style/house.css">
<style>
.doc{{max-width:820px}}
.doc p,.doc li{{max-width:70ch}}
.doc h2{{margin-top:34px}}
.doc h3{{margin-top:22px}}
.doc code{{font-size:.92em;background:var(--bg2);padding:1px 5px}}
.doc table.h{{margin:10px 0 18px}}
.call{{border-top:1px solid var(--line);padding:14px 0 6px}}
.call h3{{margin:0 0 6px}}
.call dl{{display:grid;grid-template-columns:120px 1fr;gap:4px 14px;margin:0 0 8px}}
.call dt{{font-weight:700;color:var(--fg2);font-size:var(--t-small);padding-top:2px}}
.call dd{{margin:0}}
@media(max-width:560px){{.call dl{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="sheet">
  <div class="strip"><span><a href="index.html">Where 311 complaints pile up</a></span><span>{other}</span></div>
  <div class="sec doc">
'''
FOOT = '''  </div>
</div>
</body>
</html>
'''


def cat_table():
    rows = []
    for key, label in B.CATS:
        if key == 'noise':
            members = 'Every complaint type whose name starts with "Noise"'
        elif key == 'other':
            members = 'Every complaint type not listed above'
        else:
            s = {'building': B.BUILDING, 'vehicles': B.VEHICLES, 'streets': B.STREETS, 'order': B.ORDER}[key]
            members = ', '.join(sorted(x.capitalize() for x in s))
        c = next(c for c in S['cats'] if c['key'] == key)
        rows.append(f'<tr><td>{label}</td><td class="n">{f(c["total"])}</td><td>{html.escape(members)}</td></tr>')
    return ('<table class="h"><tr><th>Category</th><th class="n">Complaints</th><th>Complaint types in it</th></tr>'
            + ''.join(rows) + '</table>')


def methodology():
    a655, a672 = CAD['655 EAST 230 STREET'], CAD['672 EAST 231 STREET']
    named_ex = ', '.join(f'<code>{html.escape(a)}</code> in {z} ({f(n)})' for a, z, n in K['top_named'][:6])
    share_rows = ''.join(
        f'<tr><td>Top {p(float(k), 2 if float(k) < 0.001 else 1 if float(k) < 0.01 else 0)}</td><td class="n">{f(v["k"])}</td>'
        f'<td class="n">{f(v["min"])}</td><td class="n">{f(v["cum"])}</td><td class="n">{p(v["share"])}</td></tr>'
        for k, v in at.items())
    pl, on = W['bronx_plateau'], W['bronx_overnight']
    o = HEAD.format(title='Methodology: where 311 complaints pile up', other='<a href="how-i-built-this.html">How I built this</a>')
    o += f'''
<h1>Methodology</h1>
<p class="lede">How the numbers on <a href="index.html">Where 311 complaints pile up</a> were made, with every filter and formula. The <a href="how-i-built-this.html">build log</a> lists each judgment call and who made it.</p>

<h2>Source</h2>
<p>New York City's <a href="https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9/about_data">311 Service Requests from 2020 to Present</a> (dataset <code>erm2-nwe9</code>) on NYC Open Data, queried through its Socrata Open Data API (SODA) endpoint <code>https://data.cityofnewyork.us/resource/erm2-nwe9.csv</code> on Oct. 14, 2026. At that moment the dataset held {f(TOT)} service requests from Jan. 1, 2020, to {day(newest)}; the newest was logged at {clock(K['newest_record'])} that day. Each service request is counted as one complaint. Times are 311's <code>created_date</code>, which is New York local time.</p>

<h2>What was pulled</h2>
<ul>
<li><b>Counts by address and type.</b> One aggregate query per calendar quarter (28 in all), grouping by <code>incident_address</code>, <code>incident_zip</code> and <code>complaint_type</code> and counting rows. The quarterly counts sum to {f(K['rows_summed'])}, matching the dataset's own row count exactly. The build stops if they don't match.</li>
<li><b>Coordinates.</b> One aggregate query per quarter grouping by address, ZIP code and borough, with the average latitude and longitude and the number of located records.</li>
<li><b>Individual records</b> for 22 of the busiest addresses: every complaint's created and closed time, type, descriptor, channel (phone, website, mobile app), agency and status. These feed the timing analysis.</li>
</ul>

<h2>What counts as a location</h2>
<p>A location is a street address with a house number, plus its five-digit ZIP code. Before matching, every address is uppercased, stripped of extra spaces (older records store some addresses with doubled spaces, such as <code>655 EAST&nbsp;&nbsp;230 STREET</code>) and has six abbreviations spelled out: BLVD, AVE, ST at the end, RD at the end, PL at the end and PKWY. That rewrite touched {f(K['abbrev_rewritten_complaints'])} complaints under {f(K['abbrev_rewritten_addresses'])} spellings.</p>
<p>An entry counts as a street address when it starts with a house number followed by a street name. Entries with no house number, and bare numbered streets such as <code>1 AVENUE</code> or <code>85 STREET</code>, name a stretch of street, a park or an airport rather than one place. They are set aside: {f(NA)} complaints under {f(K['named_entries'])} such entries, led by {named_ex}. Another {f(BL)} complaints have no address at all. Together that is {f(UN)} complaints, {p(UN / TOT)} of the total, that count toward every total but are never ranked as a location.</p>
<p>That leaves {f(N)} street addresses with at least one complaint. Addresses with no complaints are not in the data, so they are not counted.</p>

<h2>Ranking and shares</h2>
<p>Addresses are sorted by total complaints, largest first, with ties broken alphabetically by address. The top X% is the first <code>round(N &times; X)</code> addresses, where N = {f(N)}. A slice's share is the complaints at those addresses divided by all {f(TOT)} complaints, including the ones with no street address. Using only complaints with a street address as the base would raise the top 5% figure from {p(top5['share'])} to {p(top5['cum'] / (TOT - UN))}.</p>
<table class="h"><tr><th>Slice</th><th class="n">Addresses</th><th class="n">Fewest complaints in slice</th><th class="n">Complaints</th><th class="n">Share of all</th></tr>{share_rows}</table>
<p>The median address has {w(K['median'])} complaints; {f(K['one_complaint'])} addresses have exactly one. The 10 busiest addresses hold {p(K['top10_share'])} of all complaints and the 100 busiest {p(K['top100_share'])}. With the 100 busiest removed from both the top and the total, the top 5% still holds {p(K['top5_without_top100'])}.</p>
<p>The slider stops every 0.01 percentage point up to 0.1%, every 0.1 point up to 10% and every point after that. Below 0.1%, the slice is less than one square in the address grid, so that square is drawn partly filled.</p>

<h2>Complaint types and categories</h2>
<p>311 uses {K['types_total']} complaint type names in this period once spellings that differ only in capitalization are merged (the most common spelling is kept). The page groups them into six categories. The grouping is a judgment call; the full list:</p>
{cat_table()}
<p>The chart of complaint types shows the {K['types_big']} types with at least 40,000 complaints. For each, its position is the type's complaints at addresses in the slice divided by all complaints of that type, including those with no street address. Types that 311 mostly logs without an address, such as traffic signal problems, sit near zero at every slice for that reason.</p>

<h2>The map</h2>
<p>The map shows the top 5% ({f(TK)} addresses). Each address takes the coordinates from the quarter in which it had the most located complaints. Averaging across quarters would have placed some addresses between two geocoded spots: for {f(K['top_coord_spread_over_100m'])} of the {f(TK)}, the quarterly points sit more than 100 meters apart. {w(K['top_missing_coords']).capitalize()} address{'' if K['top_missing_coords'] == 1 else 'es'} {'has' if K['top_missing_coords'] == 1 else 'have'} no coordinates and {'is' if K['top_missing_coords'] == 1 else 'are'} not drawn. A dot's color is the category with the most complaints at that address; its area grows with the square root of its complaint count.</p>

<h2>Timing at the busiest addresses</h2>
<p>For each of the 22 addresses pulled record by record, complaints are sorted by created time and these are measured:</p>
<ul>
<li><b>Gap:</b> seconds between one complaint and the next at the same address.</li>
<li><b>Run:</b> a sequence of complaints each less than two minutes after the one before. The longest run at 655 East 230th Street went from {clock(a655['longest_burst_start'])} on {day(a655['longest_burst_start'])}, to {clock(a655['longest_burst_end'])} on {day(a655['longest_burst_end'], False)}: {f(a655['longest_burst_n'])} complaints over {a655['longest_burst_min'] / 60:.1f} hours. {a655['runs_over_24h']} runs there lasted 24 hours or more; at 672 East 231st Street, {a672['runs_over_24h']}. None of the other 20 addresses had one.</li>
<li><b>Evenness:</b> within a window, complaints are counted by clock hour and the standard deviation of those hourly counts is compared with the square root of their mean, which is the standard deviation expected if complaints arrived independently at random (a Poisson process) at the same average rate. From {clock(pl['from'])} on {day(pl['from'])}, to {clock(pl['to'])} on {day(pl['to'], False)}, 655 East 230th Street averaged {pl['hourly_mean']} complaints an hour with a standard deviation of {pl['hourly_sd']}; random arrivals at that rate would give about {pl['random_sd_at_that_rate']}. From {clock(on['from'])} to {clock(on['to'])} on {day(on['from'])}, the median gap was {on['median_gap_s']:.0f} seconds and {p(on['share_within_1s_of_median'], 0)} of gaps were within one second of it.</li>
<li><b>Switching:</b> complaints at a group of addresses are merged into one sorted stream, and each time consecutive complaints name different addresses counts as a switch. Fast switches suggest one source naming several addresses.</li>
<li><b>Time of day:</b> each complaint's clock hour.</li>
</ul>
<p>The timing describes when 311 logged a request. A phone that saves requests offline and sends them later could log several in the same second, so same-second pairs are not treated as evidence on their own. Nothing in the public data identifies who filed a complaint or how, beyond the channel field, so the page describes the timing and does not name a cause.</p>

<h2>Limits</h2>
<ul>
<li>Counts are not adjusted for building size. A large apartment building draws more complaints because more people live there.</li>
<li>Complaints are counted at the address 311 recorded, which is where the problem was reported to be, not where the caller was.</li>
<li>The data is as published on Oct. 14, 2026. 311 updates the dataset daily, and old records can change.</li>
<li>The groups in "The top of the list" were chosen by reading the top 45 addresses; they are examples, not a complete sorting.</li>
</ul>

<h2>Files</h2>
<ul>
<li><code>scripts/fetch_311.py</code> pulls the quarterly aggregates. <code>scripts/build_data.py</code> builds <code>data/summary.json</code>, <code>data/points.json</code>, <code>data/top-5-percent-addresses.csv</code> and <code>build/checks.json</code>.</li>
<li><code>scripts/fetch_records.py</code> and <code>scripts/analyze_cadence.py</code> pull the individual records and build <code>data/cadence.json</code>.</li>
<li><code>scripts/build_docs.py</code> writes this page and the build log from those files.</li>
</ul>
'''
    return o + FOOT


def call(title, decision, why, alt, effect, who):
    return (f'<div class="call"><h3>{title}</h3><dl><dt>Decision</dt><dd>{decision}</dd><dt>Why</dt><dd>{why}</dd>'
            f'<dt>Alternative</dt><dd>{alt}</dd><dt>Effect</dt><dd>{effect}</dd><dt>Who decided</dt><dd>{who}</dd></dl></div>')


def build_log():
    first_share, first_k = 0.5531, 66371
    o = HEAD.format(title='How I built this: where 311 complaints pile up', other='<a href="methodology.html">Methodology</a>')
    o += f'''
<h1>How I built this</h1>
<p class="lede">Every step from the city's 311 file to <a href="index.html">the page</a>, and every judgment call along the way: what was decided, why, the alternative, what difference it makes and who made the call. Formulas and exact counts are in the <a href="methodology.html">methodology</a>.</p>
<p class="caution">Who did what. Josh Greenman asked the questions: which 5% (or whatever share made sense) of locations draw the most 311 complaints, what those complaints are and what share of all complaints they make up; then for an interactive infographic; then whether the most prolific filers file too fast to be human. Claude (Anthropic's Claude Code) chose the definitions, pulled and processed the data, wrote the code and the text and ran the checks. Calls marked "Claude" are open to Josh's review.</p>

<h2>The build, step by step</h2>
<ol>
<li>Pulled counts of complaints by address, ZIP code and complaint type for each quarter since January 2020 (28 queries) and checked that they add up to the dataset's row count.</li>
<li>Cleaned addresses, set aside entries with no house number, and ranked {f(N)} street addresses by complaints.</li>
<li>Computed the share of complaints held by each slice of addresses, and the mix of complaint types inside each slice.</li>
<li>Pulled coordinates for every address and every individual record for 22 of the busiest addresses.</li>
<li>Measured the timing of complaints at those 22 addresses.</li>
<li>Built the page: two grids of 1,000 squares tied to a slider, category and type charts, a map of the top 5% and an annotated list of the busiest addresses.</li>
</ol>

<h2>Judgment calls</h2>
{call('A location is a street address plus ZIP code',
      'Rank addresses as 311 records them, after cleanup, keyed by address and ZIP code.',
      'It matches what a reader means by "a location" and needs no outside data.',
      'Tax lot (BBL) would merge buildings with several addresses and split nothing; rounded coordinates would merge neighbors.',
      'A big complex with several street addresses counts as several locations.',
      'Claude')}
{call('Entries without a house number are not ranked',
      f'Set aside {f(NA)} complaints filed under a street name, park or airport (Broadway in one ZIP code, Central Park, JFK) along with {f(BL)} with no address.',
      'Those entries cover a stretch of street or a whole park, so ranking them beside single buildings mixes different things.',
      'Rank them as locations, which the first answer in chat did.',
      f'The top 5% share fell from {p(first_share)} ({f(first_k)} addresses, in the first answer in chat) to {p(top5["share"])} ({f(TK)} addresses). The headline "just over half" holds either way.',
      'Claude')}
{call('Shares use all complaints as the base',
      f'Divide by all {f(TOT)} complaints, including the {p(UN / TOT)} with no street address.',
      'Josh asked what share of total complaints the slice accounts for.',
      'Divide by complaints that have a street address.',
      f'The top 5% share would be {p(top5["cum"] / (TOT - UN))} instead of {p(top5["share"])}.',
      "Claude, following Josh's wording")}
{call('Address cleanup',
      'Uppercase, collapse spaces and spell out six abbreviations.',
      'Older records store some addresses with doubled spaces, which would split one building into two.',
      'Use the raw strings.',
      f'The abbreviation rule touched {f(K["abbrev_rewritten_complaints"])} complaints. The doubled spaces matter more: 655 East 230th Street has {f(237208)} of its complaints under the doubled-space spelling.',
      'Claude')}
{call('Six categories',
      'Group complaint types into apartment and building conditions, noise, parking and vehicles, police and street order, streets and sanitation, and everything else.',
      'Readers need a handful of kinds to compare slices; 311 has 261 type names.',
      'Group by the agency that handles each type, which puts most noise and parking together under the police.',
      'Category shares depend on the lists in the methodology.',
      'Claude')}
{call('Default slice of 5%',
      'Open the page at the top 5% and let readers move the slider from 0.1% to 100%.',
      'Josh suggested 5% "or whatever is the right number." The curve has no natural break, so the slider lets readers pick.',
      'Open at 1%, where the top slice holds about 30% of complaints.',
      'None on the numbers.',
      'Josh (5%), Claude (the slider)')}
{call('Map coordinates',
      "Use each address's coordinates from the quarter with the most located complaints.",
      'The geocoder sometimes places one address in two spots; an average could fall between them.',
      'Average all coordinates.',
      f'{f(K["top_coord_spread_over_100m"])} of the top 5% have quarterly points more than 100 meters apart.',
      'Claude')}
{call('Naming addresses',
      'Show and name the busiest addresses, including private homes.',
      "They are published in the city's open data, and the timing findings depend on them. The page says these are complaints filed, not problems found, and that the data does not identify filers.",
      'Show only counts by neighborhood.',
      'Readers can find a specific building. Josh should review this call before the page is shared widely.',
      'Claude, flagged for review')}
{call('How to describe the fastest filing',
      'Say the timing "looks automated" and give the measurements; say nothing about who files or why.',
      'Hours of complaints at an even 172 an hour and nights of gaps of 38 seconds are hard to square with a person filing by hand, but the data cannot show what tool or person is behind them.',
      'Call it a bot, or speculate about the filer.',
      'The page stops short of the tip that the filer is a bot and sticks to what the timing shows.',
      'Claude')}
{call('Chart colors',
      'Use the house inks, with a pink in place of lilac and a gray for "everything else."',
      'Lilac and cobalt were too close for readers with normal vision and with red-green color blindness; the swap passed a color-separation check against the black page.',
      'Keep lilac.',
      'None on the numbers.',
      'Claude')}

<h2>How the numbers were checked</h2>
<ul>
<li>The 28 quarterly pulls sum to {f(K['rows_summed'])}, equal to the dataset's own count of {f(K['rows_in_feed'])}.</li>
<li>The concentration figures were computed twice: once in the first analysis in chat and again in the page build, with matching results before the house-number rule was added.</li>
<li>The first record-level pull returned 4,522 complaints for 655 East 230th Street, against 241,730 in the counts. The cause was the doubled-space spelling; the pull was rewritten to match every spelling, and the record counts now match the aggregate counts for all 22 addresses.</li>
<li>Group facts quoted on the page (distances between addresses, totals, years) were checked against the built data, and the page computes its numbers from the data files rather than typing them in.</li>
<li>The page's script was syntax-checked, and the page was loaded and clicked through at desktop and phone widths.</li>
</ul>

<h2>Change log</h2>
<ul>
<li>Oct. 14, 2026: first version.</li>
<li>Oct. 14, 2026: the slider now goes down to the top 0.01% (130 addresses), at Josh's request.</li>
</ul>

<h2>What this page does not do</h2>
<ul>
<li>It does not adjust for building size or population.</li>
<li>It does not identify who filed any complaint, or say whether a complaint was valid.</li>
<li>It does not follow complaints over time beyond the yearly bars and the timing study of 22 addresses.</li>
<li>It does not cover 311 requests before 2020, which sit in a separate dataset.</li>
</ul>
'''
    return o + FOOT


open(os.path.join(ROOT, 'methodology.html'), 'w').write(methodology())
open(os.path.join(ROOT, 'how-i-built-this.html'), 'w').write(build_log())
print('wrote methodology.html and how-i-built-this.html')
