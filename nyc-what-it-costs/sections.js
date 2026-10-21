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
    `<span class="key"><i style="background:var(--${ink})"></i>December ${N.D.base.slice(0, 4)} onward</span><span class="key"><i style="background:var(--fg2)"></i>Same months a year earlier</span>`;

  // Wrap every number in a piece of source text in a link to that source.
  const citeNums = (N, text, url, title) => N.esc(text).replace(/\$?\d[\d,]*(?:\.\d+)?(?: percent|%| cents)?/g, m => N.cite(m, url, title));

  function smallMult(N, o) {
    // o: {title, sub, series, ytd, ytd_ly, yoy, ref, src, url, srcTitle, ink, extra}
    const ry = +o.ref.slice(0, 4), rm = +o.ref.slice(5) - 1;
    const s1 = `Dec. ${ry - 1} to ${MONS[rm]} ${ry}`, s0 = `Dec. ${ry - 2} to ${MONS[rm]} ${ry - 1}`, s12 = `${MONS[rm]} ${ry - 1} to ${MONS[rm]} ${ry}`;
    const c = v => o.calc ? N.calc(N.sign(v), o.calc, o.srcTitle) : N.cite(N.sign(v), o.url, o.srcTitle);
    return `<figure><figcaption>${N.esc(o.title)}<small>${o.sub}</small></figcaption>
      ${ytdChart(N, o.series, {ink: o.ink, label: o.title, ref: o.ref})}
      <div class="big"><span class="${N.cls(o.ytd)}">${c(o.ytd)}</span> <span style="color:var(--fg2);font-weight:400;font-size:.9rem">${s1}</span></div>
      <div style="font-size:13.5px;color:var(--fg2)">${c(o.ytd_ly)} ${s0}; ${c(o.yoy)} ${s12}</div>
      ${o.extra ? `<div class="note">${o.extra}</div>` : ''}
      <div class="src note">Source: <a href="${o.url}">${o.src}</a></div></figure>`;
  }

  const blsMult = (N, l, title, sub, ink, label) => smallMult(N, {title, sub, series: l.series, ytd: l.ytd, ytd_ly: l.ytd_ly, yoy: l.yoy, ref: l.ref, ink,
    url: N.blsUrl(l.id), src: `BLS, ${label} (${l.id})`, srcTitle: `BLS series ${l.id}`});
  const line = (N, k) => N.D.lines.find(l => l.key === k);
  const dt = s => { const [y, m, dd] = s.split('-'); return `${MONS[+m - 1]} ${+dd}, ${y}`; };

  // ---- rent ----------------------------------------------------------------
  window.render_rent = function (N) {
    const D = N.D, rent = line(N, 'rent'), z = D.zori, R = D.rent_rules, hvs = R.hvs2023;
    const inks = {market: 'vermilion', stabilized: 'cobalt', nycha: 'mint', other: 'lilac', controlled: 'cyan'};
    const [o57, o58] = R.rgb;
    const H = (t) => N.cite(t, hvs.url, 'NYC Department of Housing Preservation and Development (HPD), 2023 Housing and Vacancy Survey');
    const stock = hvs.stock.map(s => `
      <div class="r"><div><b>${N.esc(s.label)}</b> <small>${H(Math.round(s.units / 1000).toLocaleString() + ' thousand')} apartments and a median rent of ${H('$' + s.median.toLocaleString())} in 2023</small>
        <i style="width:${s.units / hvs.stock[0].units * 100}%;background:var(--${inks[s.key]});margin-top:4px"></i>
        <small style="display:block;margin-top:3px">${s.key === 'stabilized' ? `Renewals capped by the Rent Guidelines Board: ${N.cite(o57.one_year + '%', o57.url, 'Rent Guidelines Board, Order ' + o57.order)} on one-year leases starting Oct. 1, 2025, then ${N.cite(o58.one_year + '%', o58.url, 'Rent Guidelines Board, Order ' + o58.order)} on leases starting Oct. 1, 2026.` : s.rule_src ? citeNums(N, s.rule, s.rule_src, s.rule_title) : N.esc(s.rule)}</small></div>
        <div style="font-size:13px;color:var(--fg2);text-align:right">${s.in_cpi === 'yes' ? 'In the BLS rent index' : 'Outside the BLS rent index'}</div></div>`).join('');
    const ry = +z.ref.slice(0, 4), zm = MONS[+z.ref.slice(5) - 1];
    const acs = R.acs, acsU = y => acs.url_tpl.replace('{y}', y);
    const bt = `BLS, rent of primary residence, New York area (${rent.id})`;
    N.$('rent-sec').innerHTML = `
      <h2>Rent</h2>
      <p class="aside">Rent-stabilized apartments are ${H('41 percent')} of New York City's rental units, according to the city's 2023 Housing and Vacancy Survey. The page leads with the BLS measure of rents sitting tenants pay, which includes them, and sets the rent rules and new-lease asking rents beside it.</p>
      <div class="figcap"><span>${keyHTML(N, 'cobalt')}</span></div>
      <div class="sm">
        ${blsMult(N, rent, 'Rent tenants pay', 'BLS rent of primary residence, New York area: the same occupied apartments, rent-stabilized and rent-controlled ones included, repriced every six months', 'cobalt', 'rent of primary residence, New York-Newark-Jersey City')}
        ${smallMult(N, {title: 'Asking rent on new leases', sub: 'Zillow Observed Rent Index, New York City: listed apartments, the same units compared over time. A private source; no government agency publishes a monthly new-lease rent', series: z.series, ytd: z.ytd, ytd_ly: z.ytd_ly, yoy: z.yoy, ref: z.ref, ink: 'vermilion',
          url: z.url, src: 'Zillow Research, Zillow Observed Rent Index', srcTitle: 'Zillow Observed Rent Index, New York city',
          extra: `${N.cite('$' + Math.round(z.latest).toLocaleString(), z.url, 'Zillow Observed Rent Index, New York city')} a month in ${N.myear(z.ref)}. Zillow smooths this series.`})}
        <figure><figcaption>Rent-stabilized renewals<small>Maximum increase on a one-year renewal lease, set each June by the Rent Guidelines Board</small></figcaption>
          <div class="list" style="margin-top:10px">
            ${[o57, o58].map(o => `<div class="row"><span class="sw" style="background:var(--cobalt)"></span><span class="nm">Order ${o.order}<span class="sub">Leases starting ${dt(o.leases_from)}, to ${dt(o.leases_to)}; two-year leases ${N.cite(o.two_year + '%', o.url, 'Rent Guidelines Board, Order ' + o.order)}; board vote ${N.cite(o.vote, o.vote_url, 'Rent Guidelines Board explanatory statement')}</span></span><span class="num">${N.cite(o.one_year + '%', o.url, 'Rent Guidelines Board, Order ' + o.order)}</span></div>`).join('')}
          </div>
          <div class="note">The freeze reaches tenants as their leases come up for renewal: one-year leases over the 12 months from Oct. 1, 2026, and two-year leases over 24. The BLS index reprices each apartment every six months, so the freeze will show up in it gradually from the October 2026 figures.</div>
          <div class="src note">Source: <a href="${o58.url}">Rent Guidelines Board, Order ${o58.order}</a>; <a href="${o57.url}">Order ${o57.order}</a></div></figure>
      </div>
      <div class="rentgrid">
        <div><h3>Who rents what, and what governs the rent</h3>
          <p class="note" style="margin-top:0">New York City's rental apartments by regulation in 2023, from the Housing and Vacancy Survey, the most recent. Medians are monthly contract rent, including any voucher subsidy.</p>
          <div class="stock">${stock}</div>
          <div class="src note">Source: <a href="${hvs.url}">HPD, 2023 Housing and Vacancy Survey, selected initial findings</a></div></div>
        <div><h3>How to read the three measures</h3>
          <p class="note" style="margin-top:0">The BLS index follows a fixed sample of occupied apartments across the ${N.cite('25-county', 'https://www.bls.gov/regions/northeast/news-release/consumerpriceindex_newyorkarea.htm', 'BLS New York-area CPI release, technical note')} metro area, prices each one every six months and counts the full contract rent, including any Section 8 subsidy. It includes stabilized and controlled apartments and leaves out public housing by design, so New York City Housing Authority (NYCHA) tenants, whose rent follows their income, are outside it.</p>
          <p class="note">The asking-rent index measures what a household moving this month faces. From ${zm} ${ry - 1} to ${zm} ${ry} it rose ${N.cite(N.p1(z.yoy), z.url, 'Zillow Observed Rent Index, New York city')}; the rent tenants pay rose ${N.cite(N.p1(rent.yoy), N.blsUrl(rent.id), bt)} over the same twelve months.</p>
          <p class="note">The three are kept separate. Combining them would mean guessing how many market-rate leases renew each month and at what increase, which no public source reports. For a level, the Census Bureau's median contract rent for New York City was ${Object.entries(acs.years).map(([y, v]) => `${N.cite('$' + v.toLocaleString(), acsU(y), `Census Bureau, American Community Survey ${y} 1-year, ${acs.table}`)} in ${y}`).join(' and ')}; the ${N.cite('2025 figure', acs.release_url, 'Census Bureau release schedule')} is due Oct. 29, 2026.</p></div>
      </div>`;
  };

  // ---- energy --------------------------------------------------------------
  window.render_energy = function (N) {
    const E = N.D.energy, g = E.gasoline, c = E.coned, o = E.heating_oil, ne = E.northeast, en = line(N, 'energy'), gl = line(N, 'gasoline');
    const lw = g.last_week, ow = o.last_week, cp = N.D.con_ed_plan;
    const G = t => N.cite(t, g.url, 'EIA, New York City regular gasoline, weekly');
    const enU = N.blsUrl(en.id), enT = `BLS, energy, New York area (${en.id})`;
    N.$('energy-sec').innerHTML = `
      <h2>Energy</h2>
      <p class="aside">The New York-area energy index ${N.chg(en.ytd, enU, enT)} from ${N.span}, against ${N.cite(N.p1(en.ytd_ly), enU, enT)} from ${N.spanLY}. BLS stopped publishing New York-area electricity and piped-gas prices after December 2024. Electricity here comes from what Con Edison billed its own customers, as reported to the federal Energy Information Administration (EIA); piped gas comes from the BLS Northeast index.</p>
      <div class="figcap"><span>${keyHTML(N, 'orange')}</span></div>
      <div class="sm">
        ${smallMult(N, {title: 'Gasoline, New York City', sub: 'Regular, average of EIA\'s weekly survey prices for each month', series: g.series, ytd: g.ytd, ytd_ly: g.ytd_ly, yoy: g.yoy, ref: g.ref, ink: 'orange',
          url: g.url, src: 'EIA, New York City retail gasoline (EMM_EPMR_PTE_Y35NY_DPG)', srcTitle: 'EIA, New York City regular gasoline, weekly',
          extra: `${G('$' + g.latest.toFixed(2))} a gallon, average for ${N.myear(g.ref)}. Week of ${dt(lw.date)}: ${G('$' + lw.v.toFixed(2))}, against ${G('$' + lw.year_ago.v.toFixed(2))} the week of ${dt(lw.year_ago.date)}. The BLS index for the whole metro area, all grades, ${N.chg(gl.ytd, N.blsUrl(gl.id), `BLS, gasoline, New York area (${gl.id})`)} from ${N.span}.`})}
        ${smallMult(N, {title: 'Con Edison electricity', sub: 'Residential revenue per kilowatt-hour, customers buying both delivery and supply from Con Edison', series: c.series, ytd: c.ytd, ytd_ly: c.ytd_ly, yoy: c.yoy, ref: c.ref, ink: 'sun',
          url: c.url, src: 'EIA Form 861M, Consolidated Edison Co. of New York', srcTitle: 'Calculated from EIA Form 861M: residential revenue divided by residential sales', calc: 'energy',
          extra: `${N.calc(c.latest.toFixed(1) + ' cents', 'energy', 'EIA Form 861M residential revenue divided by sales')} per kilowatt-hour in ${N.myear(c.ref)}, ${c.preliminary.toLowerCase()} data. Average revenue moves with how much households use as well as with rates, so compare a month only with the same month a year earlier. The state Public Service Commission approved Con Edison's current rate plan on ${N.cite(dt(cp.approved), cp.url, 'New York State Department of Public Service')}.`})}
        ${blsMult(N, ne.electricity, 'Electricity, Northeast', 'BLS electricity index for the Northeast region, the closest BLS series still published', 'sun', 'electricity, Northeast')}
        ${blsMult(N, ne.piped_gas, 'Piped gas, Northeast', 'BLS utility gas service index for the Northeast region', 'cyan', 'utility gas service, Northeast')}
      </div>
      <p class="note" style="margin-top:18px"><b style="color:var(--fg)">Heating oil.</b> EIA surveys New York State residential heating oil from October to March. It was ${N.cite('$' + ow.v.toFixed(2), o.url, 'EIA, New York State residential heating oil, weekly')} a gallon the week of ${dt(ow.date)}, against ${N.cite('$' + ow.year_ago.v.toFixed(2), o.url, 'EIA, New York State residential heating oil, weekly')} the week of ${dt(ow.year_ago.date)}, a change of ${N.cite(N.sign(o.yoy_week), o.url, 'Calculated from the two EIA weekly prices')}. Source: <a href="${o.url}">EIA</a>.</p>`;
  };

  // ---- food ----------------------------------------------------------------
  window.render_food = function (N) {
    const D = N.D, gr = line(N, 'groceries'), rs = line(N, 'restaurants');
    const RI = `https://www.bls.gov/cpi/tables/relative-importance/${D.base.slice(0, 4)}.xlsx`, RIt = `BLS relative importance, December ${D.base.slice(0, 4)}`;
    const aisles = D.aisles.map(a => blsMult(N, a, a.label, 'BLS, New York area', 'sun', a.label)).join('');
    const rows = D.staples.map(s => {
      const c = v => N.cite(N.sign(v), N.blsUrl(s.id), `BLS average price, ${s.id}`);
      return `<tr><td class="nm">${N.esc(s.label)}</td><td>${N.cite('$' + s.latest.toFixed(2), N.blsUrl(s.id), `BLS average price, ${s.id}`)}/${s.unit}</td><td class="${N.cls(s.ytd)}">${c(s.ytd)}</td><td>${c(s.ytd_ly)}</td><td class="${N.cls(s.yoy)}">${c(s.yoy)}</td><td style="color:var(--fg2)">${N.myear(s.ref)}</td></tr>`;
    }).join('');
    N.$('food-sec').innerHTML = `
      <h2>Food</h2>
      <p class="aside">Groceries and restaurant meals in the New York area, then grocery prices aisle by aisle. Groceries took ${N.cite('$' + gr.weight.toFixed(2), RI, RIt)} and restaurants ${N.cite('$' + rs.weight.toFixed(2), RI, RIt)} of every $100 spent in the area, by the BLS December ${D.base.slice(0, 4)} weights.</p>
      <div class="figcap"><span>${keyHTML(N, 'sun')}</span></div>
      <div class="sm">
        ${blsMult(N, gr, 'Groceries', 'BLS food at home, New York area', 'sun', 'food at home')}
        ${blsMult(N, rs, 'Restaurants and takeout', 'BLS food away from home, New York area', 'rose', 'food away from home')}
        ${aisles}
      </div>
      <h3 style="margin-top:28px">Prices of single items</h3>
      <p class="note" style="margin-top:0">BLS average prices for a fixed item description. BLS publishes these for the Northeast region, not for the New York area, and does not adjust them for quality, so they are a check on the indexes above.</p>
      <div class="scroll"><table class="cat"><thead><tr><th>Item, Northeast</th><th>Price in latest month</th><th>December to latest month</th><th>Same months a year earlier</th><th>12 months to latest month</th><th>Latest month</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="src note">Source: BLS average price data, series linked in each row.</div>`;
  };

  // ---- city-set prices -------------------------------------------------------
  window.render_admin = function (N) {
    const A = N.D.administered;
    const fmt = (it, v) => v == null ? 'n/a' : it.fmt === 'dollars0' ? '$' + Math.round(v).toLocaleString() : '$' + v.toFixed(2);
    const cards = A.items.map(it => {
      const steps = it.steps.map(([s, v], i) => `<li>${N.esc(it.step_labels[i])}: ${N.cite(fmt(it, v), it.step_src[i], it.source)}</li>`).join('');
      const last = it.step_src[it.step_src.length - 1];
      const y0 = +it.as_of.slice(0, 4) - 1;
      const ch = it.no_change_calc ? '' : `<span class="${N.cls(it.since_dec)}">${N.cite(N.sign(it.since_dec), last, 'Calculated from the prices listed below')}</span> from Dec. 31, ${y0}, to ${dt(it.as_of)}; ${N.cite(N.sign(it.yoy), last, 'Calculated from the prices listed below')} from ${dt(y0 + it.as_of.slice(4))} to ${dt(it.as_of)}`;
      const note = !it.note ? '' : it.note_srcs ? it.note.split(/(?<=\.)\s+/).map((sent, i) => citeNums(N, sent, it.note_srcs[Math.min(i, it.note_srcs.length - 1)], it.source)).join(' ') : citeNums(N, it.note, it.note_src, it.source);
      return `<figure><figcaption><b>${N.esc(it.label)}</b><small style="display:block;color:var(--fg2);font-size:13px">${N.esc(it.unit)}</small></figcaption>
        <div class="now">${N.cite(fmt(it, it.now), last, it.source)}</div><div style="font-size:14px">${ch}</div>
        ${stepChart(N, it)}
        <ul>${steps}</ul>
        ${note ? `<div class="note">${note}</div>` : ''}
        <div class="src note">Source: <a href="${it.url}">${N.esc(it.source)}</a></div></figure>`;
    }).join('');
    N.$('admin-sec').innerHTML = `
      <h2>Prices the city and state set</h2>
      <p class="aside">A fare, toll or rate is the same product at every date, so a change in the number is a change in the price. Prices are as of ${dt(A.items[0].as_of)}; each was checked against its source on ${dt(A.verified)}.</p>
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
    const mw = D.administered.items.find(i => i.id === 'min_wage'), mwSrc = mw.step_src[mw.step_src.length - 1];
    const oU = N.blsUrl(oer.id), oT = `BLS, owners' equivalent rent, New York area (${oer.id})`;
    const RI = `https://www.bls.gov/cpi/tables/relative-importance/${D.base.slice(0, 4)}.xlsx`;
    const pU = N.blsUrl(p.id), pT = `BLS Current Employment Statistics, New York City, average hourly earnings (${p.id})`;
    const [hy, hq] = h.ref.split('-Q'), qn = ['first', 'second', 'third', 'fourth'][hq - 1];
    N.$('pay-sec').innerHTML = `
      <h2>Owning, and pay</h2>
      <div class="split">
        <div><h3>Owning a home</h3>
          <p class="note" style="margin-top:0">BLS prices owner housing by what owned homes would rent for, a measure called owners' equivalent rent. It ${N.chg(oer.ytd, oU, oT)} from ${N.span}, against ${N.cite(N.p1(oer.ytd_ly), oU, oT)} from ${N.spanLY}, and carries ${N.cite('$' + oer.weight.toFixed(2), RI, `BLS relative importance, December ${D.base.slice(0, 4)}`)} of every $100 in the index, the largest single weight. Sale prices come from the Federal Housing Finance Agency (FHFA) index for the New York-Jersey City-White Plains metro division, which follows repeat sales of houses with conforming mortgages and so leaves out most co-ops and condos. It rose ${N.cite(N.p1(h.yoy), h.url, 'FHFA House Price Index, purchase-only, not seasonally adjusted, metro division 35614')} from the ${qn} quarter of ${hy - 1} to the ${qn} quarter of ${hy}.</p>
          <div class="src note">Sources: <a href="${oU}">${oT}</a>; <a href="${h.url}">FHFA House Price Index</a></div></div>
        <div><h3>Pay, alongside prices</h3>
          <p class="note" style="margin-top:0">Average hourly earnings for private-sector jobs in New York City were ${N.cite('$' + p.latest.toFixed(2), pU, pT)} in ${N.myear(p.ref)}, from the BLS payroll survey. Averaged over the three months ending ${N.myear(p.ref)}, they were ${p.yoy_3mo >= 0 ? 'up' : 'down'} ${N.calc(N.p1(p.yoy_3mo), 'pay', 'three-month averages of the BLS series, compared with the same three months a year earlier')} from the three months ending ${N.myear(N.D.ref_ly)}. From ${N.myear(N.D.ref_ly)} to ${N.myear(all.ref)}, prices in the area ${N.chg(all.yoy, N.blsUrl(all.id), `BLS, all items, New York area (${all.id})`)}.</p>
          <p class="note">Pay and prices are shown side by side only. Average hourly earnings move when the mix of jobs changes, a single city's monthly figures are noisy, and the price index covers the whole 25-county metro area. The city's minimum wage has been ${N.cite('$' + mw.now.toFixed(2), mwSrc, mw.source)} since ${dt(mw.steps[mw.steps.length - 1][0])}, up from ${N.cite('$' + mw.at_year_ago.toFixed(2), mwSrc, mw.source)}, and the state says it ${N.cite('stays there in 2027', mw.note_src, mw.source)}.</p>
          <div class="src note">Source: <a href="${pU}">${pT}</a>. More on pay and rent burden: <a href="pay.html">Keeping Up in New York</a>.</div></div>
      </div>`;
  };

  window.render_foot = function (N) {
    const D = N.D;
    N.$('foot').innerHTML = `
      <p><b style="color:var(--fg)">How this is built.</b> Every number links to its source. Scripts in this page's folder pull each series from its publisher and recompute the page each month; the city-set prices are entered by hand, each tied to the agency page it came from. The rules: only series that price the same thing the same way each month; every change compares the same calendar months in two years; nothing is seasonally adjusted, smoothed or estimated ahead of its release; a series that fails to update shows its own latest month rather than a guess. BLS skipped October 2025 during the federal shutdown, so twelve-month changes for October 2026 will not exist.
      Read the full <a href="methodology.html">methodology</a>, or download the <a href="data/dashboard.json">data</a>.</p>
      <p>BLS data through ${N.myear(D.ref)}, pulled ${D.bls_fetched}. Page rebuilt ${D.built}. Built by Josh Greenman.</p>`;
  };
})();
