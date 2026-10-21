// Keeping Up in New York: renders data/pay.json. All numbers come from that file.
(async function () {
  const D = await (await fetch('data/pay.json', {cache: 'no-cache'})).json();
  const $ = id => document.getElementById(id);
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const MON = ['Jan.','Feb.','March','April','May','June','July','Aug.','Sept.','Oct.','Nov.','Dec.'];
  const myear = ym => MONTHS[+ym.slice(5) - 1] + ' ' + ym.slice(0, 4);
  const sign = (v, d = 1) => v == null ? 'n/a' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%';
  const pct = (v, d = 1) => v.toFixed(d) + '%';
  // Prose form of a change: 'rose 2.0%' / 'fell 0.8%'.
  const chg = v => v == null ? 'is not available' : Math.abs(v) < 0.05 ? 'was unchanged' : (v > 0 ? 'rose ' : 'fell ') + Math.abs(v).toFixed(1) + '%';
  const money = v => '$' + v.toFixed(2);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const dt = s => { const [y, m, d] = s.split('-'); return d ? `${MON[+m - 1]} ${+d}, ${y}` : `${MON[+m - 1]} ${y}`; };

  // ---- one line chart: series = [{name, ink, pts:[[x, y|null],...], dash}] ------
  function lineChart(series, o) {
    // Draw at the container's real width so type stays readable on a phone.
    const W = Math.min(860, Math.max(320, o.el ? o.el.clientWidth : 860));
    const H = Math.round((o.h || 300) * (W < 600 ? 0.9 : 1)), L = 40, R = 62, T = 12, B = 26;
    const xs = series.flatMap(s => s.pts.map(p => p[0]));
    const ys = series.flatMap(s => s.pts.map(p => p[1])).filter(v => v != null);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    let lo = Math.min(...ys), hi = Math.max(...ys);
    if (o.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const pad = (hi - lo) * 0.08 || 1;
    hi += pad;
    if (!(o.zero && lo === 0)) lo -= pad;
    const X = v => L + (v - x0) / (x1 - x0 || 1) * (W - L - R);
    const Y = v => T + (hi - v) / (hi - lo) * (H - T - B);
    const raw = (hi - lo) / 5, mag = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / mag;
    const step = (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * mag;
    let g = '';
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
      const z = Math.abs(v) < 1e-9;
      g += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--${z ? 'fg2' : 'line2'})"/>` +
        `<text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="12" fill="var(--fg2)">${o.fmtY(v)}</text>`;
    }
    o.ticks.forEach(([v, t]) => g += `<text x="${X(v)}" y="${H - 6}" text-anchor="middle" font-size="12" fill="var(--fg2)">${t}</text>`);
    series.forEach(s => {
      let d = '', pen = false;
      s.pts.forEach(([a, b]) => { if (b == null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(a).toFixed(1) + ',' + Y(b).toFixed(1); pen = true; });
      g += `<path d="${d}" fill="none" stroke="var(--${s.ink})" stroke-width="2.6" ${s.dash ? 'stroke-dasharray="4 4"' : ''} stroke-linejoin="round"/>`;
      s.pts.forEach(([a, b]) => { if (b != null && s.dots) g += `<circle cx="${X(a)}" cy="${Y(b)}" r="3" fill="var(--${s.ink})"/>`; });
      const last = [...s.pts].reverse().find(p => p[1] != null);
      g += `<circle cx="${X(last[0])}" cy="${Y(last[1])}" r="4" fill="var(--${s.ink})"/>` +
        `<text x="${X(last[0]) + 8}" y="${Y(last[1]) + 4}" font-size="12.5" font-weight="700" fill="var(--${s.ink})">${o.fmtLast(last[1])}</text>`;
    });
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label)}">${g}</svg>`;
  }

  // ---- sources: every figure is a link to where it comes from ---------------
  const cite = (txt, url, title) => `<a class="cite" href="${url}" title="${esc(title || 'Source')}" target="_blank" rel="noopener">${txt}</a>`;
  const calc = (txt, what) => cite(txt, 'methodology.html#pay', `Calculated: ${what}`);
  const p1 = v => Math.abs(v).toFixed(1) + '%';
  const chgC = (v, url, title) => v == null ? 'is not available' : (v > 0 ? 'rose ' : v < 0 ? 'fell ' : 'held at ') + cite(p1(v), url, title);
  const citeNums = (text, url, title) => esc(text).replace(/\$?\d[\d,]*(?:\.\d+)?(?: percent|%| million)?/g, m => cite(m, url, title));
  const blsUrl = id => `https://data.bls.gov/timeseries/${id}`;

  // ---- opening ------------------------------------------------------------
  const H = D.hvs, HV = t => cite(t, H.url, 'HPD, 2023 New York City Housing and Vacancy Survey, selected initial findings');
  const M = D.monthly, rows = M.rows, lastRow = rows[rows.length - 1];
  const Cm = D.comptroller;
  const Wg = D.wages, wl = Wg.years[Wg.years.length - 1], w0 = Wg.years[0];
  const A = D.acs.years, aYears = Object.keys(A), aLast = aYears[aYears.length - 1], a = A[aLast];
  const acsU = (y, t) => `https://data.census.gov/table/ACSDT1Y${y}.${t}?g=160XX00US3651000`;
  const acsT = (y, t) => `Census Bureau, American Community Survey ${y} 1-year, table ${t}, New York city`;
  const AC = (txt, y, t) => cite(txt, acsU(y, t), acsT(y, t));
  const oe = r => [r.file, `BLS Occupational Employment and Wage Statistics, May ${r.year}, New York-Newark-Jersey City metro area, all occupations`];
  const CPIu = blsUrl(M.cpi_id), CPIt = `BLS Consumer Price Index, all items, New York-Newark-Jersey City (${M.cpi_id})`;
  const AHEu = blsUrl(M.ahe_id), AHEt = `BLS Current Employment Statistics, New York City, average hourly earnings (${M.ahe_id})`;
  $('span-line').textContent = `Pay through ${myear(M.ahe_ref)} · rent burden through ${aLast} · rebuilt ${D.built}`;
  const refLY = `${+M.ahe_ref.slice(0, 4) - 1}${M.ahe_ref.slice(4)}`;
  $('finding').innerHTML =
    `From May ${w0.year} to May ${wl.year}, the median hourly wage in the New York area rose ${calc(p1(wl.median_since_first), 'change between the two BLS wage files')}, to ${cite(money(wl.median_hourly), ...oe(wl))}, and prices in the area rose ${cite(p1(wl.cpi_since_first), CPIu, CPIt)}. ` +
    `In ${aLast}, ${AC(pct(a.share_30_plus), aLast, 'B25070')} of New York City renter households spent 30 percent or more of their income on rent.`;
  $('lede').innerHTML =
    `In ${aLast}, ${AC(pct(a.share_50_plus), aLast, 'B25070')} of the city's renter households spent half or more of their income on rent. ` +
    `From ${myear(refLY)} to ${myear(M.ahe_ref)}, average hourly pay for jobs in the city rose ${calc(p1(lastRow.pay), 'three-month averages of the BLS series compared with the same months a year earlier')}, comparing three-month averages, and prices in the area ${chgC(lastRow.prices, CPIu, CPIt)}. ` +
    `Prices are tracked in detail on <a href="./">What New York Costs</a>.`;

  // ---- monthly chart ------------------------------------------------------
  const idx = m => (+m.slice(0, 4) - 2025) * 12 + (+m.slice(5) - 1);
  const ticks = rows.filter(r => ['01', '04', '07', '10'].includes(r.m.slice(5))).map(r => [idx(r.m), `${MON[+r.m.slice(5) - 1]} ${r.m.slice(2, 4) === '25' && r.m.slice(5) !== '01' ? '' : "'" + r.m.slice(2, 4)}`.trim()]);
  $('c-monthly').innerHTML = lineChart([
    {name: 'Pay', ink: 'mint', pts: rows.map(r => [idx(r.m), r.pay])},
    {name: 'Prices', ink: 'vermilion', pts: rows.map(r => [idx(r.m), r.prices])},
  ], {el: $('c-monthly'), zero: true, ticks: ticks.filter((t, i) => innerWidth > 600 || i % 2 === 0), fmtY: v => (v > 0 ? '+' : '') + v.toFixed(0) + '%', fmtLast: v => sign(v), label: 'Pay and prices, change from a year earlier'});
  $('n-monthly').innerHTML = `Pay is average hourly earnings for private-sector jobs located in New York City, averaged over three months because single months for one city are noisy. An average rises when low-wage jobs disappear even if no one's pay changes; the yearly median below avoids that. BLS published no New York price index for October 2025, so the price line has a gap. Sources: <a href="${AHEu}">${AHEt}</a>; <a href="${CPIu}">${CPIt}</a>.`;

  // ---- yearly wages ---------------------------------------------------------
  const mw = D.min_wage.steps, mwNow = mw[mw.length - 1];
  const wl2 = Wg.latest, w21 = Wg.years.find(r => r.year === 2021);
  const drawW = () => {
    $('c-wages').innerHTML = lineChart([
      {name: 'Median', ink: 'mint', dots: true, pts: Wg.years.map(r => [r.year, r.median_since_first])},
      {name: 'Average', ink: 'cobalt', dots: true, pts: Wg.years.map(r => [r.year, r.mean_since_first])},
      {name: 'Prices', ink: 'vermilion', dots: true, pts: Wg.years.map(r => [r.year, r.cpi_since_first])},
    ], {el: $('c-wages'), zero: true, h: 280, ticks: Wg.years.filter((r, i) => innerWidth > 600 || i % 2 === 0).map(r => [r.year, String(r.year)]), fmtY: v => (v > 0 ? '+' : '') + v.toFixed(0) + '%', fmtLast: v => sign(v), label: 'Median and average wages and prices since 2019'});
  };
  const CmC = t => cite(t, Cm.url, 'New York City Comptroller, Recent Trends in Personal Income and Wage Inequality');
  $('wages').innerHTML = `
    <h2>Median and average wages</h2>
    <p class="aside">Each May, BLS estimates wages for every occupation from a survey of employers, which yields a median: half of workers earn more and half less. In May ${wl.year} the median in the New York area was ${cite(money(wl.median_hourly), ...oe(wl))} an hour and the average, pulled up by high earners, was ${cite(money(wl.mean_hourly), ...oe(wl))}. From May ${wl.year - 1} to May ${wl.year} the median rose ${calc(p1(wl2.median_yoy), 'change between the two BLS wage files')}, and prices in the area rose ${cite(p1(wl2.cpi_yoy), CPIu, CPIt)} over the same twelve months.</p>
    <div class="figcap"><span><b>Change since May ${w0.year}</b>, wages for all occupations and consumer prices, same metro area, May of each year</span><span><span class="key"><i style="background:var(--mint)"></i>Median wage</span><span class="key"><i style="background:var(--cobalt)"></i>Average wage</span><span class="key"><i style="background:var(--vermilion)"></i>Prices</span></span></div>
    <div class="chart" id="c-wages"></div>
    <div class="scroll"><table class="h" style="max-width:860px;margin-top:14px"><thead><tr><th>May of</th><th class="n">Median hourly</th><th class="n">Average hourly</th><th class="n">Jobs</th></tr></thead><tbody>
      ${Wg.years.map(r => `<tr><td>${r.year}</td><td class="n">${cite(money(r.median_hourly), ...oe(r))}</td><td class="n">${cite(money(r.mean_hourly), ...oe(r))}</td><td class="n">${cite((r.employment / 1e6).toFixed(2) + ' million', ...oe(r))}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="note">BLS ${cite('advises', 'https://www.bls.gov/oes/oes_ques.htm', 'BLS, Occupational Employment and Wage Statistics frequently asked questions')} that these estimates are built for comparing places and occupations within a year; changes in methods and occupation codes add noise from one year to the next, so the trend over several years says more than any single year's change. Jobs in the area fell from ${cite((w0.employment / 1e6).toFixed(2) + ' million', ...oe(w0))} in May ${w0.year} to ${cite((w21.employment / 1e6).toFixed(2) + ' million', ...oe(w21))} in May 2021; when lower-paid jobs disappear, the median and the average rise even if no one's pay does. The city's minimum wage has been ${cite(money(mwNow[1]), D.min_wage.url, D.min_wage.source)} since ${dt(mwNow[0])}. Sources: BLS Occupational Employment and Wage Statistics files for each year, linked in the table; prices from the <a href="${CPIu}">BLS index for the same area</a>.</p>
    <h3 style="margin-top:26px">Income from all sources, ${esc(Cm.span)}</h3>
    <p class="note" style="margin-top:0">Wages leave out investment income, business income and people without a paycheck. The New York City Comptroller's office measured all income before taxes and benefits, using state income tax records for city residents. From 2019 to 2024, median income per tax unit rose ${CmC(pct(Cm.median_nominal))} before inflation and <b style="color:var(--fg)">fell ${CmC(pct(Math.abs(Cm.median_real)))}</b> after it, using a ${CmC(pct(Cm.deflator_change))} rise in New York-area prices. The bottom 90 percent averaged ${CmC('$' + Cm.bottom90_avg_2019.toLocaleString())} in 2019 and ${CmC('$' + Cm.bottom90_avg_2024.toLocaleString())} in 2024, up ${CmC(pct(Cm.bottom90_nominal))} before inflation and down ${CmC(pct(Math.abs(Cm.bottom90_real)))} after it. The report attributes part of that decline to a change in the mix of households filing; at 2019's mix, the group's income rose ${CmC(pct(Cm.bottom90_real_reweighted))} after inflation. The top 1 percent took ${CmC(Cm.top1_share_of_growth + ' percent')} of the city's income growth after inflation over those years, against ${CmC(Cm.top1_share_of_growth_us + ' percent')} nationally, and received ${CmC(Cm.top1_income_share_2024 + ' percent')} of all income in 2024, against ${CmC(Cm.top1_income_share_2024_us + ' percent')} nationally.</p>
    <p class="note">These figures, including the inflation adjustment, are the Comptroller's. They cover 2019 to 2024, a different span from the May-to-May wage figures above, so the two are not set against each other. Source: <a href="${Cm.url}">New York City Comptroller, Recent Trends in Personal Income and Wage Inequality</a>, ${dt(Cm.published)}.</p>`;
  drawW();

  // ---- rent burden -------------------------------------------------------------
  let zeroB = false;
  const drawB = () => {
    const pts = k => aYears.map(y => [+y, A[y][k]]);
    const withGap = p => { const out = []; p.forEach(q => { if (q[0] === 2021) out.push([2020, null]); out.push(q); }); return out; };
    $('c-burden').innerHTML = lineChart([
      {name: '30% or more', ink: 'sun', dots: true, pts: withGap(pts('share_30_plus'))},
      {name: '50% or more', ink: 'vermilion', dots: true, pts: withGap(pts('share_50_plus'))},
      {name: 'Median share', ink: 'fg2', dots: true, dash: true, pts: withGap(pts('median_ratio'))},
    ], {el: $('c-burden'), zero: zeroB, h: 280, ticks: aYears.filter(y => +y % (innerWidth > 600 ? 2 : 4) === 0).map(y => [+y, y]), fmtY: v => v.toFixed(0) + '%', fmtLast: v => pct(v), label: 'Rent burden of New York City renters'});
    document.querySelectorAll('#burden .chip').forEach(c => c.setAttribute('aria-pressed', String((c.dataset.z === '1') === zeroB)));
  };
  $('burden').innerHTML = `
    <h2>Rent as a share of income</h2>
    <p class="aside">Each year the Census Bureau's American Community Survey asks renter households what they pay in rent and utilities and what they earn. In ${aLast}, the typical New York City renter household spent ${AC(pct(a.median_ratio), aLast, 'B25071')} of its income on rent; ${AC(pct(a.share_30_plus), aLast, 'B25070')} spent 30 percent or more, which the city's housing survey ${HV('counts as rent burdened')}, and ${AC(pct(a.share_50_plus), aLast, 'B25070')} spent half or more. The median renter household earned ${AC('$' + Math.round(a.renter_median_income).toLocaleString(), aLast, 'B25119')} that year, and the median rent was ${AC('$' + Math.round(a.median_gross_rent).toLocaleString(), aLast, 'B25064')} a month.</p>
    <div class="figcap"><span><b>New York City renter households</b>, share of income spent on rent and utilities</span><span><span class="key"><i style="background:var(--sun)"></i>Share paying 30% or more</span><span class="key"><i style="background:var(--vermilion)"></i>Share paying 50% or more</span><span class="key"><i style="background:var(--fg2)"></i>Median share of income</span></span></div>
    <div class="toggle"><button class="chip" data-z="0">Fit to data</button><button class="chip" data-z="1">Start at zero</button></div>
    <div class="chart" id="c-burden"></div>
    <p class="note">The Census Bureau released ${cite('no standard 1-year figures for 2020', 'https://www.census.gov/newsroom/press-releases/2021/changes-2020-acs-1-year.html', 'Census Bureau, 2020 ACS 1-year experimental data')}, when the pandemic disrupted the survey. Its ${cite('2025 figures', 'https://www.census.gov/programs-surveys/acs/news/data-releases/2025/release.html', 'Census Bureau, 2025 ACS release schedule')} are scheduled for Oct. 29, 2026. Each estimate has a margin of error; for the ${aLast} median share it is ${AC('±' + a.median_ratio_moe.toFixed(1) + ' points', aLast, 'B25071')}. Sources: Census Bureau, American Community Survey 1-year estimates, tables ${['B25070', 'B25071', 'B25064', 'B25119'].map(t => `<a href="${acsU(aLast, t)}">${t}</a>`).join(', ')}; earlier years at the same tables for each year.</p>
    <div class="two">
      <div><h3>Lower-income renters</h3>
        <p class="note" style="margin-top:0">The city's Housing and Vacancy Survey, run every three years with the Census Bureau, breaks the figures out by income. In 2023 the typical renter household spent ${HV(pct(H.median_ratio_2023))} of income on rent, down from ${HV(pct(H.median_ratio_2021))} in 2021. Among renters earning less than ${HV('$' + H.renter_median_income_2023.toLocaleString())} in 2023, the median renter income that year, the typical household spent <b style="color:var(--fg)">${HV(pct(H.median_ratio_below_median_income_2023))}</b>. Source: <a href="${H.url}">HPD, 2023 Housing and Vacancy Survey</a>.</p></div>
      <div><h3>Why the two surveys differ</h3>
        <p class="note" style="margin-top:0">The two surveys measure rent and income differently, so their citywide medians for the same year differ: ${HV(pct(H.median_ratio_2023))} in the Housing and Vacancy Survey and ${AC(pct(A['2023'].median_ratio), 2023, 'B25071')} in the American Community Survey for 2023. Each figure here is compared only with figures from the same survey. For what a newly leased apartment costs, see the asking-rent index on <a href="./#rent-sec">What New York Costs</a>.</p></div>
    </div>`;
  document.querySelectorAll('#burden .chip').forEach(c => c.addEventListener('click', () => { zeroB = c.dataset.z === '1'; drawB(); }));
  drawB();

  // ---- reference shelf ----------------------------------------------------
  const inks = ['vermilion', 'cobalt', 'rose', 'cyan', 'lilac', 'orange'];
  $('shelf').innerHTML = `
    <h2>Other measures of hardship</h2>
    <p class="aside">These groups count New Yorkers in hardship with their own methods, a year or more after the period they describe. Their latest editions:</p>
    <div class="list shelf">${D.shelf.map((s, i) => `
      <div class="row"><span class="sw" style="background:var(--${inks[i % inks.length]})"></span>
        <span class="nm"><a href="${s.url}">${esc(s.name)}</a><span class="sub">${citeNums(s.headline, s.url, s.name)}</span>
        <span class="sub">${esc(s.publisher)}; published ${dt(s.published)}, describing ${esc(String(s.data_year))}. ${esc(s.method)}</span></span></div>`).join('')}
    </div>
    <p class="note">Each figure is quoted from the publisher's report, linked above. Their thresholds differ, so their counts differ.</p>`;

  $('foot').innerHTML = `<p>A draft. Every number links to its source. Data rebuilt ${D.built}. Read the <a href="methodology.html#pay">methodology</a> or download the <a href="data/pay.json">data</a>. Built by Josh Greenman.</p>`;
})();
