// Section renderers for What New York Costs. app.js calls each with shared helpers.
(function () {
  const MON1 = ['J','F','M','A','M','J','J','A','S','O','N','D'];
  const MONS = ['Jan.','Feb.','March','April','May','June','July','Aug.','Sept.','Oct.','Nov.','Dec.'];

  // ---- the one chart type: change since the prior December, this year vs last year
  // series: [[YYYY-MM, value], ...] covering Dec two years back through the latest month
  function paths(series, ref) {
    const m = Object.fromEntries(series);
    const refYear = +ref.slice(0, 4), refMonth = +ref.slice(5);
    const mk = y => {
      const base = m[`${y - 1}-12`];
      if (base == null) return null;
      const pts = [[0, 0]];
      for (let i = 1; i <= refMonth; i++) {
        const k = `${y}-${String(i).padStart(2, '0')}`;
        pts.push([i, m[k] == null ? null : (m[k] / base - 1) * 100]);
      }
      return pts;
    };
    return {now: mk(refYear), last: mk(refYear - 1)};
  }

  function ytdChart(N, series, opts = {}) {
    const p = paths(series, opts.ref || N.D.ref);
    const W = 300, H = opts.h || 120, L = 30, R = 6, T = 8, B = 18;
    const vals = [0, ...(p.now || []), ...(p.last || [])].map(x => Array.isArray(x) ? x[1] : x).filter(v => v != null);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.12, 0.6);
    lo -= pad; hi += pad;
    const x = i => L + i / 12 * (W - L - R);
    const y = v => T + (hi - v) / (hi - lo) * (H - T - B);
    const step = niceStep(hi - lo);
    let g = '';
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      const yy = y(v).toFixed(1);
      g += `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" stroke="var(--${Math.abs(v) < 1e-9 ? 'fg2' : 'line2'})" stroke-width="${Math.abs(v) < 1e-9 ? 1 : .8}"/>` +
        `<text x="${L - 5}" y="${(+yy + 4).toFixed(1)}" text-anchor="end" font-size="10.5" fill="var(--fg2)">${Math.abs(v) < 1e-9 ? '0' : (v > 0 ? '+' : '−') + Math.abs(v).toFixed(step < 1 ? 1 : 0) + '%'}</text>`;
    }
    ['D', ...MON1].forEach((t, i) => { if (i % 3 === 0) g += `<text x="${x(i)}" y="${H - 4}" text-anchor="middle" font-size="10.5" fill="var(--fg2)">${t}</text>`; });
    const line = (pts, col, w, dash) => {
      if (!pts) return '';
      let d = '', pen = false, dots = '';
      pts.forEach(([i, v]) => {
        if (v == null) { pen = false; return; }
        d += (pen ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1); pen = true;
      });
      const lastPt = [...pts].reverse().find(q => q[1] != null);
      if (lastPt) dots = `<circle cx="${x(lastPt[0])}" cy="${y(lastPt[1])}" r="3.2" fill="${col}"/>`;
      return `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" ${dash ? 'stroke-dasharray="3 3"' : ''} stroke-linejoin="round"/>` + dots;
    };
    const col = `var(--${opts.ink || 'accent'})`;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${N.esc(opts.label || '')}">${g}${line(p.last, 'var(--fg2)', 1.5, true)}${line(p.now, col, 2.4)}</svg>`;
  }

  function niceStep(r) {
    const raw = r / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const n = raw / mag;
    return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * mag;
  }

  const keyHTML = (N, ink = 'accent') =>
    `<span class="key"><i style="background:var(--${ink})"></i>December ${N.D.base.slice(0, 4)} to now</span><span class="key"><i style="background:var(--fg2)"></i>Same months a year earlier</span>`;

  function smallMult(N, o) {
    // o: {title, sub, series, ytd, ytd_ly, yoy, ref, src, ink, extra}
    const ry = +o.ref.slice(0, 4), rm = +o.ref.slice(5) - 1;
    const s1 = `Dec. ${ry - 1} to ${MONS[rm]} ${ry}`, s0 = `Dec. ${ry - 2} to ${MONS[rm]} ${ry - 1}`, s12 = `${MONS[rm]} ${ry - 1} to ${MONS[rm]} ${ry}`;
    return `<figure><figcaption>${N.esc(o.title)}<small>${o.sub}</small></figcaption>
      ${ytdChart(N, o.series, {ink: o.ink, label: o.title, ref: o.ref})}
      <div class="big"><span class="${N.cls(o.ytd)}">${N.sign(o.ytd)}</span> <span style="color:var(--fg2);font-weight:400;font-size:.9rem">${s1}</span></div>
      <div style="font-size:13.5px;color:var(--fg2)">${N.sign(o.ytd_ly)} ${s0}; ${N.sign(o.yoy)} ${s12}</div>
      ${o.extra ? `<div class="note">${o.extra}</div>` : ''}
      <div class="src note">${o.src}</div></figure>`;
  }

  const bls = (N, id, label) => `Source: <a href="https://data.bls.gov/timeseries/${id}">BLS ${label || id}</a>`;
  const line = (N, k) => N.D.lines.find(l => l.key === k);

  // ---- rent ----------------------------------------------------------------
  window.render_rent = function (N) {
    const D = N.D, rent = line(N, 'rent'), z = D.zori, R = D.rent_rules, hvs = R.hvs2023;
    const tot = hvs.stock.reduce((a, s) => a + s.units, 0);
    const inks = {market: 'vermilion', stabilized: 'cobalt', nycha: 'mint', other: 'lilac', controlled: 'cyan'};
    const maxMed = Math.max(...hvs.stock.map(s => s.median));
    const rgb = R.rgb;
    const [o57, o58] = rgb;
    const stock = hvs.stock.map(s => `
      <div class="r"><div><b>${N.esc(s.label)}</b> <small>${Math.round(s.units / 1000).toLocaleString()} thousand apartments in 2023; median rent $${s.median.toLocaleString()} in 2023</small>
        <i style="width:${s.units / hvs.stock[0].units * 100}%;background:var(--${inks[s.key]});margin-top:4px"></i>
        <small style="display:block;margin-top:3px">${N.esc(s.rule)}</small></div>
        <div style="font-size:13px;color:var(--fg2);text-align:right">${s.in_cpi === 'yes' ? 'In the BLS rent index' : 'Not in the BLS rent index'}</div></div>`).join('');
    N.$('rent-sec').innerHTML = `
      <h2>Rent: what tenants pay, not just what landlords ask</h2>
      <p class="aside">About 41 percent of New York City's rental apartments are rent stabilized, and asking rents on vacant apartments describe only the few households moving that month. So the page leads with the measure that follows the rents sitting tenants actually pay, and puts the regulated and market rules beside it.</p>
      <div class="figcap"><span>${keyHTML(N, 'cobalt')}</span></div>
      <div class="sm">
        ${smallMult(N, {title: 'Rent tenants pay', sub: 'BLS rent of primary residence, New York area: the same occupied apartments, rent-stabilized and rent-controlled ones included, repriced every six months', series: rent.series, ytd: rent.ytd, ytd_ly: rent.ytd_ly, yoy: rent.yoy, ref: rent.ref, ink: 'cobalt', src: bls(N, rent.id, 'CPI rent, New York-Newark-Jersey City')})}
        ${smallMult(N, {title: 'Asking rent on new leases', sub: 'Zillow Observed Rent Index, New York City: listed apartments, the same units compared over time. A private source, shown because no government agency publishes a monthly new-lease rent', series: z.series, ytd: z.ytd, ytd_ly: z.ytd_ly, yoy: z.yoy, ref: z.ref, ink: 'vermilion', extra: `$${Math.round(z.latest).toLocaleString()} a month in ${N.myear(z.ref)}. Zillow smooths this series.`, src: `Source: <a href="${z.url}">Zillow Research</a>`})}
        <figure><figcaption>Rent-stabilized renewals<small>Maximum increase on a one-year renewal lease, set each June by the Rent Guidelines Board</small></figcaption>
          <div class="list" style="margin-top:10px">
            <div class="row"><span class="sw" style="background:var(--cobalt)"></span><span class="nm">Order ${o57.order}<span class="sub">Leases starting Oct. 1, 2025, to Sept. 30, 2026; two-year leases ${o57.two_year}%; vote ${o57.vote}</span></span><span class="num">${o57.one_year}%</span></div>
            <div class="row"><span class="sw" style="background:var(--cobalt)"></span><span class="nm">Order ${o58.order}<span class="sub">Leases starting Oct. 1, 2026, to Sept. 30, 2027; two-year leases ${o58.two_year}%; vote ${o58.vote}</span></span><span class="num">${o58.one_year}%</span></div>
          </div>
          <div class="note">The freeze reaches tenants only as leases come up for renewal, one-year leases over the next 12 months and two-year leases over 24. The BLS index reprices each apartment every six months, so it will show the freeze slowly, starting with the October figures.</div>
          <div class="src note">Source: <a href="${o58.url}">Rent Guidelines Board, Order ${o58.order}</a>; <a href="${o57.url}">Order ${o57.order}</a></div></figure>
      </div>
      <div class="rentgrid">
        <div><h3>Who rents what, and what governs the rent</h3>
          <p class="note" style="margin-top:0">New York City's rental apartments by regulation, from the 2023 Housing and Vacancy Survey, the most recent. Medians are monthly contract rent, including any voucher subsidy.</p>
          <div class="stock">${stock}</div>
          <div class="src note">Source: <a href="${hvs.url}">NYC Department of Housing Preservation and Development, 2023 Housing and Vacancy Survey, selected initial findings</a></div></div>
        <div><h3>How to read the three measures</h3>
          <p class="note" style="margin-top:0">The BLS index is the closest thing to a measure of the rent New Yorkers pay. It follows a fixed sample of occupied apartments across the 25-county metro area, prices each one every six months and counts the full contract rent, including a Section 8 subsidy. It covers stabilized and controlled apartments but excludes public housing by design, so NYCHA tenants, whose rent follows their income, are outside it.</p>
          <p class="note">The asking-rent index answers a different question: what a household that moves this month faces. From ${N.myear(N.D.ref_ly)} to ${N.myear(z.ref)} it ${N.chg(z.yoy)}, while the rent tenants pay ${N.chg(rent.yoy)} over the same twelve months. That gap is the cost of moving, and it is not what most renters see in a given year.</p>
          <p class="note">This page does not blend the three into a single homemade rent figure. Doing so would require guessing how many market-rate leases renew each month and at what increase, and no public source reports that. ${N.esc(R.acs.note)}</p></div>
      </div>`;
  };

  // ---- energy --------------------------------------------------------------
  window.render_energy = function (N) {
    const E = N.D.energy, g = E.gasoline, c = E.coned, o = E.heating_oil, ne = E.northeast, en = line(N, 'energy');
    const lw = g.last_week, ow = o.last_week;
    const d = s => { const [y, m, dd] = s.split('-'); return `${MONS[+m - 1]} ${+dd}, ${y}`; };
    N.$('energy-sec').innerHTML = `
      <h2>Energy</h2>
      <p class="aside">The New York-area energy index ${N.chg(en.ytd)} from ${N.span}, against ${en.ytd_ly.toFixed(1)}% from ${N.spanLY}. BLS stopped publishing New York-area electricity and piped-gas prices after December 2024, so electricity here comes from what Con Edison's own customers were billed, as reported to the federal Energy Information Administration, and piped gas from the Northeast regional index.</p>
      <div class="figcap"><span>${keyHTML(N, 'orange')}</span></div>
      <div class="sm">
        ${smallMult(N, {title: 'Gasoline, New York City', sub: 'Regular, average of EIA\'s weekly survey prices for each month', series: g.series, ytd: g.ytd, ytd_ly: g.ytd_ly, yoy: g.yoy, ref: g.ref, ink: 'orange',
          extra: `$${g.latest.toFixed(2)} a gallon in ${N.myear(g.ref)}. Latest week: $${lw.v.toFixed(2)} (${d(lw.date)}), against $${lw.year_ago.v.toFixed(2)} the same week last year. The BLS index for the whole metro area, all grades, ${N.chg(line(N, 'gasoline').ytd)} from ${N.span}.`,
          src: `Source: <a href="${g.url}">U.S. Energy Information Administration</a>`})}
        ${smallMult(N, {title: 'Con Edison electricity', sub: 'Residential revenue per kilowatt-hour, customers buying both delivery and supply from Con Edison', series: c.series, ytd: c.ytd, ytd_ly: c.ytd_ly, yoy: c.yoy, ref: c.ref, ink: 'sun',
          extra: `${c.latest.toFixed(1)} cents per kilowatt-hour in ${N.myear(c.ref)}, ${c.preliminary.toLowerCase()} data. This is average revenue, so it moves with how much households use, not only with rates; compare it with the same month a year earlier. The state approved Con Edison's current rate plan on Jan. 22, 2026, effective Jan. 1.`,
          src: `Source: <a href="${c.url}">EIA Form 861M</a>, Consolidated Edison Co. of New York`})}
        ${smallMult(N, {title: 'Electricity, Northeast', sub: 'BLS electricity index for the Northeast region, the closest BLS series still published', series: ne.electricity.series, ytd: ne.electricity.ytd, ytd_ly: ne.electricity.ytd_ly, yoy: ne.electricity.yoy, ref: ne.electricity.ref, ink: 'sun', src: bls(N, ne.electricity.id, 'CPI electricity, Northeast')})}
        ${smallMult(N, {title: 'Piped gas, Northeast', sub: 'BLS utility gas service index for the Northeast region', series: ne.piped_gas.series, ytd: ne.piped_gas.ytd, ytd_ly: ne.piped_gas.ytd_ly, yoy: ne.piped_gas.yoy, ref: ne.piped_gas.ref, ink: 'cyan', src: bls(N, ne.piped_gas.id, 'CPI utility gas, Northeast')})}
      </div>
      <p class="note" style="margin-top:18px"><b style="color:var(--fg)">Heating oil.</b> EIA surveys New York State residential heating oil only from October to March. The latest reading, $${ow.v.toFixed(2)} a gallon (${d(ow.date)}), is ${N.sign(o.yoy_week)} from the same week last year ($${ow.year_ago.v.toFixed(2)}). Source: <a href="${o.url}">EIA</a>.</p>`;
  };

  // ---- food ----------------------------------------------------------------
  window.render_food = function (N) {
    const D = N.D, gr = line(N, 'groceries'), rs = line(N, 'restaurants');
    const aisles = D.aisles.map(a => smallMult(N, {title: a.label, sub: 'BLS, New York area', series: a.series, ytd: a.ytd, ytd_ly: a.ytd_ly, yoy: a.yoy, ref: a.ref, ink: 'sun', src: bls(N, a.id)})).join('');
    const rows = D.staples.map(s => `<tr><td class="nm">${N.esc(s.label)}</td><td>$${s.latest.toFixed(2)}/${s.unit}</td><td class="${N.cls(s.ytd)}">${N.sign(s.ytd)}</td><td>${N.sign(s.ytd_ly)}</td><td class="${N.cls(s.yoy)}">${N.sign(s.yoy)}</td><td style="color:var(--fg2)">${N.myear(s.ref)}</td></tr>`).join('');
    N.$('food-sec').innerHTML = `
      <h2>Food</h2>
      <p class="aside">Groceries and restaurant meals in the New York area, then grocery prices aisle by aisle.</p>
      <div class="figcap"><span>${keyHTML(N, 'sun')}</span></div>
      <div class="sm">
        ${smallMult(N, {title: 'Groceries', sub: `BLS food at home, New York area; $${gr.weight.toFixed(2)} of every $100 spent`, series: gr.series, ytd: gr.ytd, ytd_ly: gr.ytd_ly, yoy: gr.yoy, ref: gr.ref, ink: 'sun', src: bls(N, gr.id)})}
        ${smallMult(N, {title: 'Restaurants and takeout', sub: `BLS food away from home, New York area; $${rs.weight.toFixed(2)} of every $100`, series: rs.series, ytd: rs.ytd, ytd_ly: rs.ytd_ly, yoy: rs.yoy, ref: rs.ref, ink: 'rose', src: bls(N, rs.id)})}
        ${aisles}
      </div>
      <h3 style="margin-top:28px">Prices of single items</h3>
      <p class="note" style="margin-top:0">BLS average prices for a fixed item description. BLS publishes these for the Northeast region, not for the New York area, and does not adjust them for quality, so they are a check on the indexes above rather than a substitute.</p>
      <div class="scroll"><table class="cat"><thead><tr><th>Item, Northeast</th><th>Latest price</th><th>Dec. to latest month</th><th>Same months a year earlier</th><th>12 months to latest month</th><th>Latest month</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="src note">Source: <a href="https://www.bls.gov/cpi/factsheets/average-prices.htm">BLS average price data</a></div>`;
  };

  // ---- city-set prices -------------------------------------------------------
  window.render_admin = function (N) {
    const A = N.D.administered;
    const fmt = (it, v) => v == null ? 'n/a' : it.fmt === 'dollars0' ? '$' + Math.round(v).toLocaleString() : '$' + v.toFixed(2);
    const d = s => { const [y, m, dd] = s.split('-'); return `${MONS[+m - 1]} ${+dd}, ${y}`; };
    const cards = A.items.map(it => {
      const steps = it.steps.map(([s, v]) => `<li>${d(s)}: ${fmt(it, v)}</li>`).join('');
      const ch = it.no_change_calc ? '' : `<span class="${N.cls(it.since_dec)}">${N.sign(it.since_dec)}</span> from Dec. 31, ${+it.as_of.slice(0, 4) - 1}, to ${d(it.as_of)}; ${N.sign(it.yoy)} from ${d((+it.as_of.slice(0, 4) - 1) + it.as_of.slice(4))}`;
      return `<figure><figcaption><b>${N.esc(it.label)}</b><small style="display:block;color:var(--fg2);font-size:13px">${N.esc(it.unit)}</small></figcaption>
        <div class="now">${fmt(it, it.now)}</div><div style="font-size:14px">${ch}</div>
        ${stepChart(N, it)}
        <ul>${steps}</ul>
        ${it.note ? `<div class="note">${N.esc(it.note)}</div>` : ''}
        <div class="src note">Source: <a href="${it.url}">${N.esc(it.source)}</a></div></figure>`;
    }).join('');
    N.$('admin-sec').innerHTML = `
      <h2>Prices the city and state set</h2>
      <p class="aside">Fares, tolls and utility rates are the same product at every date, so a change in the number is a change in the price, with nothing to adjust. Shown as of ${d(A.items[0].as_of)}; each was last checked against its source on ${d(A.verified)}.</p>
      <div class="steps">${cards}</div>`;
  };

  function stepChart(N, it) {
    const start = new Date(N.D.base_ly.slice(0, 4) + '-12-31'), end = new Date(it.as_of);
    const W = 320, H = 90, L = 4, R = 4, T = 8, B = 16;
    const pts = it.steps.map(([s, v]) => [new Date(s), v]);
    const vals = pts.map(p => p[1]);
    const lo = 0, hi = Math.max(...vals) * 1.05; // zero-based, so a step's height is its true size
    const x = t => L + (Math.max(t, start) - start) / (end - start) * (W - L - R);
    const y = v => T + (hi - v) / (hi - lo || 1) * (H - T - B);
    let d = '', prev = null;
    pts.forEach(([t, v]) => {
      if (t > end) return;
      if (prev == null) d = `M${x(t)},${y(v)}`;
      else d += `H${x(t)}V${y(v)}`;
      prev = v;
    });
    d += `H${x(end)}`;
    const yr = new Date(N.D.base.slice(0, 4) + '-12-31');
    return `<svg viewBox="0 0 ${W} ${H}"><line x1="${x(yr)}" x2="${x(yr)}" y1="${T}" y2="${H - B}" stroke="var(--line)" stroke-dasharray="2 3"/>
      <text x="${x(yr) + 4}" y="${T + 9}" font-size="10.5" fill="var(--fg2)">Dec. 31, ${N.D.base.slice(0, 4)}</text>
      <text x="${L}" y="${H - 3}" font-size="10.5" fill="var(--fg2)">${N.D.base_ly.slice(0, 4)}</text>
      <text x="${W - R}" y="${H - 3}" font-size="10.5" fill="var(--fg2)" text-anchor="end">today</text>
      <line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" stroke="var(--line)"/>
      <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2.4"/></svg>`;
  }

  // ---- owning and pay --------------------------------------------------------
  window.render_pay = function (N) {
    const D = N.D, p = D.pay, all = D.lines[0], oer = line(N, 'oer'), h = D.homes;
    const mw = D.administered.items.find(i => i.id === 'min_wage');
    N.$('pay-sec').innerHTML = `
      <h2>Owning, and pay</h2>
      <div class="split">
        <div><h3>Owning a home</h3>
          <p class="note" style="margin-top:0">BLS does not price owner housing from sales or mortgages. Its owners' equivalent rent asks what owned homes would rent for: it ${N.chg(oer.ytd)} from ${N.span} (${oer.ytd_ly.toFixed(1)}% from ${N.spanLY}), and the largest single weight in the index at $${oer.weight.toFixed(2)} of every $100. Sale prices come from the Federal Housing Finance Agency's quarterly index for the New York-Jersey City-White Plains metro division, which tracks repeat sales of the same houses with conforming mortgages and so leaves out most co-ops and condos: up ${N.sign(h.yoy)} from a year earlier in ${h.ref.replace('-Q', ', quarter ')}.</p>
          <div class="src note">Sources: ${bls(N, oer.id, "CPI owners' equivalent rent").replace('Source: ', '')}; <a href="${h.url}">FHFA House Price Index, purchase-only, not seasonally adjusted</a></div></div>
        <div><h3>Pay, alongside prices</h3>
          <p class="note" style="margin-top:0">Average hourly earnings for private-sector jobs in New York City, from the BLS payroll survey, were $${p.latest.toFixed(2)} in ${N.myear(p.ref)}. Averaged over the three months ending ${N.myear(p.ref)}, they were ${p.yoy_3mo >= 0 ? 'up' : 'down'} ${Math.abs(p.yoy_3mo).toFixed(1)}% from the three months ending ${N.myear(N.D.ref_ly)}. From ${N.myear(N.D.ref_ly)} to ${N.myear(all.ref)}, prices in the area ${N.chg(all.yoy)}.</p>
          <p class="note">The two are shown side by side, not subtracted. Average hourly earnings shift when the mix of jobs shifts, a single city's monthly figures are noisy, and the price index covers the whole 25-county metro area. The minimum wage in the city has been $${mw.now.toFixed(2)} since ${(([y, m, dd]) => `${MONS[+m - 1]} ${+dd}, ${y}`)(mw.steps[mw.steps.length - 1][0].split('-'))}, up ${Math.abs(mw.yoy).toFixed(1)}% from $${mw.at_year_ago.toFixed(2)}, and is set to stay there in 2027.</p>
          <div class="src note">${bls(N, p.id, 'Current Employment Statistics, New York City')}</div></div>
      </div>`;
  };

  window.render_foot = function (N) {
    const D = N.D;
    N.$('foot').innerHTML = `
      <p><b style="color:var(--fg)">How this is built.</b> Every number is pulled from its publisher by scripts in this page's folder and recomputed each month; nothing is typed in by hand except the city-set prices, each linked to the page it came from. The rules: only series that price the same thing the same way each month; every change compares the same calendar months in two years; nothing is seasonally adjusted, smoothed or nowcast; a series that fails to update shows its own latest month rather than a guess. BLS skipped October 2025 during the federal shutdown, so twelve-month changes for October 2026 will not exist.
      Read the full <a href="methodology.html">methodology</a>, or download the <a href="data/dashboard.json">data</a>.</p>
      <p>BLS data through ${N.myear(D.ref)}, pulled ${D.bls_fetched}. Page rebuilt ${D.built}. Built by Josh Greenman.</p>`;
  };
})();
