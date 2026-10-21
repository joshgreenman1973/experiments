// Keeping Up in New York: renders data/pay.json. All numbers come from that file.
(async function () {
  const D = await (await fetch('data/pay.json', {cache: 'no-cache'})).json();
  const $ = id => document.getElementById(id);
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const MON = ['Jan.','Feb.','March','April','May','June','July','Aug.','Sept.','Oct.','Nov.','Dec.'];
  const myear = ym => MONTHS[+ym.slice(5) - 1] + ' ' + ym.slice(0, 4);
  const sign = (v, d = 1) => v == null ? 'n/a' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%';
  const pct = (v, d = 1) => v.toFixed(d) + '%';
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

  // ---- opening ------------------------------------------------------------
  const M = D.monthly, rows = M.rows, lastRow = rows[rows.length - 1];
  const Wg = D.wages, wl = Wg.years[Wg.years.length - 1], w0 = Wg.years[0];
  const A = D.acs.years, aYears = Object.keys(A), aLast = aYears[aYears.length - 1], a = A[aLast];
  $('span-line').textContent = `Pay through ${myear(M.ahe_ref)} · rent burden through ${aLast} · rebuilt ${D.built}`;
  $('finding').textContent =
    `The typical worker in the New York area earned ${money(wl.median_hourly)} an hour in May ${wl.year}, ` +
    `${sign(wl.median_since_first)} since May ${w0.year}, while prices rose ${sign(wl.cpi_since_first).replace('+', '')}. ` +
    `In ${aLast}, ${pct(a.share_30_plus)} of the city's renter households spent 30 percent or more of their income on rent.`;
  $('lede').innerHTML =
    `This page is the companion to <a href="./">the price tracker</a>. It sets pay beside prices over the same months, without subtracting one from the other, ` +
    `and shows how much of their income New York City renters spend on rent. In ${aLast}, <b>${pct(a.share_30_plus)}</b> of renter households paid 30 percent or more of income in rent and <b>${pct(a.share_50_plus)}</b> paid half or more. ` +
    `Over the twelve months to ${MONTHS[+M.ahe_ref.slice(5) - 1]}, average hourly pay in the city rose <b>${sign(lastRow.pay)}</b> and prices in the area <b>${sign(lastRow.prices)}</b>.`;

  // ---- monthly chart ------------------------------------------------------
  const idx = m => (+m.slice(0, 4) - 2025) * 12 + (+m.slice(5) - 1);
  const ticks = rows.filter(r => ['01', '04', '07', '10'].includes(r.m.slice(5))).map(r => [idx(r.m), `${MON[+r.m.slice(5) - 1]} ${r.m.slice(2, 4) === '25' && r.m.slice(5) !== '01' ? '' : "'" + r.m.slice(2, 4)}`.trim()]);
  $('c-monthly').innerHTML = lineChart([
    {name: 'Pay', ink: 'mint', pts: rows.map(r => [idx(r.m), r.pay])},
    {name: 'Prices', ink: 'vermilion', pts: rows.map(r => [idx(r.m), r.prices])},
  ], {el: $('c-monthly'), zero: true, ticks: ticks.filter((t, i) => innerWidth > 600 || i % 2 === 0), fmtY: v => (v > 0 ? '+' : '') + v.toFixed(0) + '%', fmtLast: v => sign(v), label: 'Pay and prices, change from a year earlier'});
  $('n-monthly').innerHTML = `Average hourly earnings are for private-sector jobs located in New York City, averaged over three months because a single month for one city moves a percent or more from sampling alone. An average rises when low-wage jobs disappear, even if no one gets a raise, which is why the yearly median below matters. The price line has a gap at October 2025, when BLS published no New York index. Sources: <a href="https://data.bls.gov/timeseries/${M.ahe_id}">BLS Current Employment Statistics</a>; <a href="https://data.bls.gov/timeseries/${M.cpi_id}">BLS Consumer Price Index, New York-Newark-Jersey City</a>.`;

  // ---- yearly wages ---------------------------------------------------------
  const mw = D.min_wage.steps, mwNow = mw[mw.length - 1];
  const wl2 = Wg.latest;
  const drawW = () => {
    $('c-wages').innerHTML = lineChart([
      {name: 'Median', ink: 'mint', dots: true, pts: Wg.years.map(r => [r.year, r.median_since_first])},
      {name: 'Average', ink: 'cobalt', dots: true, pts: Wg.years.map(r => [r.year, r.mean_since_first])},
      {name: 'Prices', ink: 'vermilion', dots: true, pts: Wg.years.map(r => [r.year, r.cpi_since_first])},
    ], {el: $('c-wages'), zero: true, h: 280, ticks: Wg.years.filter((r, i) => innerWidth > 600 || i % 2 === 0).map(r => [r.year, String(r.year)]), fmtY: v => (v > 0 ? '+' : '') + v.toFixed(0) + '%', fmtLast: v => sign(v), label: 'Median and average wages and prices since 2019'});
  };
  $('wages').innerHTML = `
    <h2>The typical worker, not the average</h2>
    <p class="aside">Once a year BLS surveys employers' payrolls for every occupation, which gives the median: the wage with half of workers above and half below. In May ${wl.year} the median in the New York area was ${money(wl.median_hourly)} an hour; the average, pulled up by high earners, was ${money(wl.mean_hourly)}. From May ${wl.year - 1} to May ${wl.year} the median rose ${sign(wl2.median_yoy)}, and prices in the same area over the same twelve months rose ${sign(wl2.cpi_yoy)}.</p>
    <div class="figcap"><span><b>Change since May ${w0.year}</b>, wages for all occupations and consumer prices, same metro area, May of each year</span><span><span class="key"><i style="background:var(--mint)"></i>Median wage</span><span class="key"><i style="background:var(--cobalt)"></i>Average wage</span><span class="key"><i style="background:var(--vermilion)"></i>Prices</span></span></div>
    <div class="chart" id="c-wages"></div>
    <div class="scroll"><table class="h" style="max-width:860px;margin-top:14px"><thead><tr><th>May of</th><th class="n">Median hourly</th><th class="n">Average hourly</th><th class="n">Jobs</th></tr></thead><tbody>
      ${Wg.years.map(r => `<tr><td>${r.year}</td><td class="n">${money(r.median_hourly)}</td><td class="n">${money(r.mean_hourly)}</td><td class="n">${(r.employment / 1e6).toFixed(2)} million</td></tr>`).join('')}
    </tbody></table></div>
    <p class="note">BLS cautions that these estimates are built for comparing places and occupations in a given year rather than over time; changes in survey methods and occupation codes add noise to year-to-year moves, so read the direction over several years, not a single year's change. Jobs in the area fell from ${(w0.employment / 1e6).toFixed(2)} million in May ${w0.year} to ${(Wg.years.find(r => r.year === 2021).employment / 1e6).toFixed(2)} million in May 2021; when lower-paid jobs disappear, the median and the average rise even if no one's pay does. The minimum wage in New York City has been ${money(mwNow[1])} since ${dt(mwNow[0])}. Source: <a href="${Wg.url}">BLS Occupational Employment and Wage Statistics</a>, New York-Newark-Jersey City metro area; prices from the BLS index for the same area.</p>`;
  drawW();

  // ---- rent burden -------------------------------------------------------------
  const H = D.hvs;
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
    <p class="aside">The Census Bureau asks renter households each year what they pay in rent and utilities and what they earn. In ${aLast}, the typical New York City renter household spent ${pct(a.median_ratio)} of its income on rent; ${pct(a.share_30_plus)} spent 30 percent or more, the federal line for being rent burdened, and ${pct(a.share_50_plus)} spent half or more. The median renter household earned $${Math.round(a.renter_median_income).toLocaleString()} and the median rent was $${Math.round(a.median_gross_rent).toLocaleString()} a month.</p>
    <div class="figcap"><span><b>New York City renter households</b>, share of income spent on rent and utilities</span><span><span class="key"><i style="background:var(--sun)"></i>Share paying 30% or more</span><span class="key"><i style="background:var(--vermilion)"></i>Share paying 50% or more</span><span class="key"><i style="background:var(--fg2)"></i>Median share of income</span></span></div>
    <div class="toggle"><button class="chip" data-z="0">Fit to data</button><button class="chip" data-z="1">Start at zero</button></div>
    <div class="chart" id="c-burden"></div>
    <p class="note">No standard figures exist for 2020, when the pandemic disrupted the survey. Census figures for 2025 are scheduled for Oct. 29, 2026. Each estimate has a margin of error; for the median share in ${aLast} it is ±${a.median_ratio_moe.toFixed(1)} points. Source: <a href="${D.acs.url}">Census Bureau, American Community Survey 1-year estimates, tables B25070, B25071, B25064 and B25119</a>.</p>
    <div class="two">
      <div><h3>Lower-income renters</h3>
        <p class="note" style="margin-top:0">The city's own Housing and Vacancy Survey, run every three years with the Census Bureau, shows what the citywide median hides. In 2023 the typical renter household spent ${pct(H.median_ratio_2023)} of income on rent, down from ${pct(H.median_ratio_2021)} in 2021. Among renters earning less than $${H.renter_median_income_2023.toLocaleString()}, the median renter income, the typical household spent <b style="color:var(--fg)">${pct(H.median_ratio_below_median_income_2023)}</b>. <a href="${H.url}">HPD, 2023 Housing and Vacancy Survey</a>.</p></div>
      <div><h3>Why the two surveys differ</h3>
        <p class="note" style="margin-top:0">The two surveys measure rent and income differently and in different years, so their citywide medians do not match (${pct(H.median_ratio_2023)} and ${pct(A['2023'].median_ratio)} for 2023). Each figure here is compared only with figures from the same survey. Neither tells you what the rent for a newly leased apartment would take from a household's income; see the asking-rent index on <a href="./#rent-sec">the price tracker</a>.</p></div>
    </div>`;
  document.querySelectorAll('#burden .chip').forEach(c => c.addEventListener('click', () => { zeroB = c.dataset.z === '1'; drawB(); }));
  drawB();

  // ---- reference shelf ----------------------------------------------------
  const inks = ['cobalt', 'rose', 'cyan', 'lilac', 'orange'];
  $('shelf').innerHTML = `
    <h2>The deeper measures</h2>
    <p class="aside">Several groups measure hardship in New York City more fully than any monthly figure can, each with its own method and a lag of a year or more. Their latest editions:</p>
    <div class="list shelf">${D.shelf.map((s, i) => `
      <div class="row"><span class="sw" style="background:var(--${inks[i % inks.length]})"></span>
        <span class="nm"><a href="${s.url}">${esc(s.name)}</a><span class="sub">${esc(s.headline)}</span>
        <span class="sub">${esc(s.publisher)}; published ${dt(s.published)}, describing ${s.data_year}. ${esc(s.method)}</span></span></div>`).join('')}
    </div>
    <p class="note">These figures are quoted from each publisher's own report. Their thresholds differ, which is why the share of New Yorkers they count as struggling ranges from about a quarter to more than three in five.</p>`;

  $('foot').innerHTML = `<p>A draft. Data rebuilt ${D.built}. Read the <a href="methodology.html#pay">methodology</a> or download the <a href="data/pay.json">data</a>. Built by Josh Greenman.</p>`;
})();
