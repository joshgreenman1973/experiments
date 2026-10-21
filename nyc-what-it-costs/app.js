// What New York Costs: renders data/dashboard.json. All numbers come from that file.
(async function () {
  const D = await (await fetch('data/dashboard.json', {cache: 'no-cache'})).json();
  const $ = id => document.getElementById(id);
  const css = getComputedStyle(document.documentElement);
  const tok = n => css.getPropertyValue('--' + n).trim();

  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const MON = ['Jan.','Feb.','March','April','May','June','July','Aug.','Sept.','Oct.','Nov.','Dec.'];
  const mname = ym => MONTHS[+ym.slice(5) - 1];
  const mshort = ym => MON[+ym.slice(5) - 1];
  const myear = ym => mname(ym) + ' ' + ym.slice(0, 4);
  const sign = (v, d = 1) => v == null ? 'n/a' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%';
  const pts = (v, d = 2) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
  const cls = v => v == null ? '' : v > 0.05 ? 'up' : v < -0.05 ? 'dn' : '';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

  const C = D.contrib, CL = D.contrib_ly;
  // Every figure names its span. 'span' = this year, 'spanLY' = same months a year earlier, 'span12' = past twelve months.
  const span = `December ${D.base.slice(0, 4)} to ${myear(D.ref)}`;
  const spanLY = `December ${D.base_ly.slice(0, 4)} to ${myear(D.ref_ly)}`;
  const span12 = `${myear(D.ref_ly)} to ${myear(D.ref)}`;
  // Every figure on the page is a link to where it comes from: a BLS series, an
  // agency page or report, or the methodology section that shows a calculation.
  const cite = (txt, url, title) => `<a class="cite" href="${url}" title="${esc(title || 'Source')}" target="_blank" rel="noopener">${txt}</a>`;
  const blsUrl = id => `https://data.bls.gov/timeseries/${id}`;
  const riUrl = y => `https://www.bls.gov/cpi/tables/relative-importance/${y}.xlsx`;
  const calc = (txt, anchor, what) => cite(txt, `methodology.html#${anchor}`, `Calculated: ${what}`);
  const p1 = v => Math.abs(v).toFixed(1) + '%';
  const chg = (v, url, title) => v == null ? 'is not available' : Math.abs(v) < 0.05 ? cite('was unchanged', url, title) : (v > 0 ? 'rose ' : 'fell ') + cite(p1(v), url, title);
  $('span-line').textContent = `Latest month: ${myear(D.ref)} · rebuilt ${D.built}`;

  // ---- opening -------------------------------------------------------------
  const INK = {SAH: 'cobalt', SAT: 'vermilion', SAF: 'sun', SAM: 'mint', SAE: 'cyan', SAR: 'lilac', SAA: 'rose', SAG: 'orange'};
  const byCode = (c, code) => c.groups.find(g => g.code === code);
  const tr = byCode(C, 'SAT'), trLY = CL && byCode(CL, 'SAT');
  const gas = tr.parts.find(p => p.code === 'SETB01');
  const SA0 = blsUrl('CUURS12ASA0'), SA0t = 'BLS Consumer Price Index, all items, New York-Newark-Jersey City (CUURS12ASA0)';
  // BLS published no index for October 2025, so in that one case there is no same-months comparison.
  const gapNote = `BLS published no New York index for ${myear(D.ref_ly)} because of the federal shutdown, so this month has no same-months comparison.`;
  const diff = CL ? C.total - CL.total : 0;
  const trShare = CL && diff > 0 ? (tr.contrib - trLY.contrib) / diff : 0;
  const V = D.context.vehicles, noCar = Math.round(V.nyc.no_vehicle / V.nyc.households * 100);
  const pub = tr.parts[2];
  const noCarCalc = v => calc(p1(v), 'whose', 'all items without private transportation, from BLS indexes and December weights');
  $('finding').innerHTML =
    `Prices in the New York area ${chg(C.total, SA0, SA0t)} from ${span}` +
    (CL ? `, against ${cite(p1(CL.total), SA0, SA0t)} from ${spanLY}. ` : '. ') +
    (trShare > 0.6 ? `Gasoline and fares for planes, trains and buses account for ${cite(trShare > 1 ? 'more than all of the difference' : 'most of the difference', '#table-sec', 'See the transportation rows in the table below')}. ` : '') +
    `Without car costs, prices rose ${noCarCalc(C.without_car_costs)} this year` +
    (CL ? ` and ${noCarCalc(CL.without_car_costs)} last year` : '') +
    `. ${cite(noCar + ' percent', V.url, `Census Bureau, ${V.source}`)} of New York City households had no car in ${V.year}.`;
  const rent = D.lines.find(l => l.key === 'rent'), groc = D.lines.find(l => l.key === 'groceries');
  const fare = D.administered.items.find(i => i.id === 'subway'), fs = fare.steps, [fd, fv] = fs[fs.length - 1], fp = fs[fs.length - 2][1];
  const s = (l, t) => [blsUrl(l.id), `BLS, ${t} (${l.id})`];
  $('lede').innerHTML =
    `From ${span}, gasoline in the metro area ${chg(gas.change, ...s({id: 'CUURS12ASETB01'}, 'gasoline, New York area'))} and fares for planes, trains and buses, which the Bureau of Labor Statistics (BLS) groups together, rose ${calc(p1(pub.change), 'whose', 'BLS transportation minus private transportation, New York area')}. ` +
    `The subway and bus fare went from ${cite(`$${fp.toFixed(2)} to $${fv.toFixed(2)}`, fare.url, fare.source)} on ${MON[+fd.slice(5, 7) - 1]} ${+fd.slice(8)}, ${fd.slice(0, 4)}. ` +
    `Over the same months, the rent New York-area tenants pay, stabilized apartments included, ${chg(rent.ytd, ...s(rent, 'rent of primary residence, New York area'))}` +
    (rent.ytd_ly == null ? '' : `, against ${cite(p1(rent.ytd_ly), ...s(rent, 'rent of primary residence, New York area'))} from ${spanLY}`) +
    `, and groceries ${chg(groc.ytd, ...s(groc, 'food at home, New York area'))}. ` +
    (D.lines[0].yoy == null ? gapNote : `From ${span12}, prices ${chg(D.lines[0].yoy, SA0, SA0t)}.`);

  // ---- contribution bars ---------------------------------------------------
  const both = CL ? [C, CL] : [C];
  const maxTot = Math.max(...both.map(c => c.groups.filter(g => g.contrib > 0).reduce((a, g) => a + g.contrib, 0)));
  const minNeg = Math.min(0, ...both.map(c => c.groups.filter(g => g.contrib < 0).reduce((a, g) => a + g.contrib, 0)));
  const lo = Math.floor(minNeg * 2) / 2, hi = Math.ceil(maxTot * 2) / 2;
  const X = v => (v - lo) / (hi - lo) * 100;
  const order = C.groups.map(g => g.code);
  const barRow = (c, label, sub) => {
    let pos = 0, neg = 0, segs = '';
    order.forEach(code => {
      const g = byCode(c, code);
      if (g.contrib >= 0) { segs += `<i title="${esc(g.name)}: ${pts(g.contrib)} points" style="left:${X(pos)}%;width:${X(pos + g.contrib) - X(pos)}%;background:var(--${INK[code]})"></i>`; pos += g.contrib; }
      else { segs += `<i title="${esc(g.name)}: ${pts(g.contrib)} points" style="left:${X(neg + g.contrib)}%;width:${X(neg) - X(neg + g.contrib)}%;background:var(--${INK[code]});opacity:.55"></i>`; neg += g.contrib; }
    });
    return `<div class="cbar"><div class="lab">${label}<small>${sub}</small></div><div class="track">${segs}</div><div class="tot">${cite(sign(c.total), SA0, SA0t)}</div></div>`;
  };
  $('contrib').innerHTML = barRow(C, 'This year', span) +
    (CL ? barRow(CL, 'Last year', spanLY) : `<p class="note">${gapNote}</p>`);
  let ax = '';
  for (let v = lo; v <= hi + 1e-9; v += 0.5) ax += `<span style="left:${X(v)}%">${v === 0 ? '0' : pts(v, 1).replace('+', '')}</span>`;
  $('contrib-axis').innerHTML = ax;
  $('contrib-key').innerHTML = order.map(code => `<span class="key"><i style="background:var(--${INK[code]})"></i>${esc(byCode(C, code).name)}</span>`).join('');
  $('contrib-note').innerHTML = `Each segment is a category's weight in the New York-area price index, as of the December before, times that category's price change. The segments add up to the all-items change, and seasonal patterns that recur every year show up in both bars. Weights: <a href="${riUrl(D.base.slice(0, 4))}">BLS relative importance, December ${D.base.slice(0, 4)}</a> and <a href="${riUrl(D.base_ly.slice(0, 4))}">December ${D.base_ly.slice(0, 4)}</a>. Price changes: the BLS series linked in each row of the table below. <a href="methodology.html#december">How the calculation works</a>.`;

  $('wdate').textContent = `December ${D.base.slice(0, 4)}`;
  // ---- category table --------------------------------------------------------
  const maxC = Math.max(...C.groups.flatMap(g => [g.contrib, ...g.parts.map(p => p.contrib)]).map(Math.abs));
  const cbox = (v, ink) => `<span class="cbox">${calc(pts(v), 'december', 'weight times price change')}<i style="width:${Math.abs(v) / maxC * 70}px;background:var(--${ink});opacity:${v < 0 ? .5 : 1}"></i></span>`;
  const lyFor = (code, part) => {
    if (!CL) return null;
    const g = byCode(CL, code);
    return part === undefined ? g : g.parts.find(p => p.code === part.code && p.name === part.name);
  };
  const W = cite.bind(null);
  const wCell = v => W('$' + v.toFixed(2), riUrl(D.base.slice(0, 4)), `BLS relative importance, New York-Newark-Jersey City, December ${D.base.slice(0, 4)}`);
  const chCell = (v, part) => v == null ? '' : part && part.code ? cite(sign(v), blsUrl('CUURS12A' + part.code), `BLS series CUURS12A${part.code}`)
    : calc(sign(v), part && part.remainder ? 'december' : 'whose', 'from published BLS indexes and weights');
  let t = `<thead><tr><th>Category</th><th>Of every $100</th><th>Change<br>${mshort(D.base)} ${D.base.slice(0, 4)} to ${mshort(D.ref)} ${D.ref.slice(0, 4)}</th><th>Same months a year earlier<br>${mshort(D.base_ly)} ${D.base_ly.slice(0, 4)} to ${mshort(D.ref_ly)} ${D.ref_ly.slice(0, 4)}</th><th>Points of the<br>${C.total.toFixed(1)}% total</th></tr></thead><tbody>`;
  C.groups.forEach(g => {
    const ly = lyFor(g.code);
    t += `<tr><td class="nm"><span class="sw" style="background:var(--${INK[g.code]})"></span>${esc(g.name)}</td><td>${wCell(g.weight)}</td><td class="${cls(g.change)}">${chCell(g.change, g)}</td><td>${ly ? chCell(ly.change, g) : 'n/a'}</td><td>${cbox(g.contrib, INK[g.code])}</td></tr>`;
    g.parts.forEach(p => {
      const lp = lyFor(g.code, p);
      t += `<tr class="part"><td class="nm">${esc(p.name)}${p.remainder ? ' (remainder)' : p.derived ? ' (calculated)' : ''}</td><td>${wCell(p.weight)}</td><td class="${cls(p.change)}">${p.remainder ? '' : chCell(p.change, p)}</td><td>${p.remainder || !lp ? '' : chCell(lp.change, p)}</td><td>${cbox(p.contrib, INK[g.code])}</td></tr>`;
    });
  });
  t += `<tr><td class="nm">All items</td><td>$100.00</td><td class="${cls(C.total)}"><b>${cite(sign(C.total), SA0, SA0t)}</b></td><td>${CL ? cite(sign(CL.total), SA0, SA0t) : 'n/a'}</td><td><span class="cbox">${calc(pts(C.total), 'december', 'sum of the rows above')}</span></td></tr></tbody>`;
  $('cat').innerHTML = t;

  // shared helpers for the sections other files fill in
  window.NYC = {D, $, tok, esc, sign, pts, cls, mname, mshort, myear, span, spanLY, span12, chg, cite, calc, blsUrl, p1};
  for (const f of ['rent', 'energy', 'food', 'admin', 'pay', 'foot']) {
    if (window['render_' + f]) window['render_' + f](window.NYC);
  }
})();
