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
  const span12 = `${myear(D.ref_ly)} to ${myear(D.ref)}`;
  const chg = v => v == null ? 'is not available' : Math.abs(v) < 0.05 ? 'was unchanged' : (v > 0 ? 'rose ' : 'fell ') + Math.abs(v).toFixed(1) + '%';
  const spanLY = `December ${D.base_ly.slice(0, 4)} to ${myear(D.ref_ly)}`;
  $('span-line').textContent = `Latest month: ${myear(D.ref)} · rebuilt ${D.built}`;

  // ---- opening -------------------------------------------------------------
  const INK = {SAH: 'cobalt', SAT: 'vermilion', SAF: 'sun', SAM: 'mint', SAE: 'cyan', SAR: 'lilac', SAA: 'rose', SAG: 'orange'};
  const byCode = (c, code) => c.groups.find(g => g.code === code);
  const tr = byCode(C, 'SAT'), trLY = CL && byCode(CL, 'SAT');
  const gas = tr.parts.find(p => p.code === 'SETB01');
  // BLS published no index for October 2025, so in that one case there is no same-months comparison.
  const gapNote = `BLS published no New York index for ${myear(D.ref_ly)} because of the federal shutdown, so this month has no same-months comparison.`;
  const diff = CL ? C.total - CL.total : 0;
  const trShare = CL && diff > 0 ? (tr.contrib - trLY.contrib) / diff : 0;
  const V = D.context.vehicles, noCar = Math.round(V.nyc.no_vehicle / V.nyc.households * 100);
  const pub = tr.parts[2];
  $('finding').textContent =
    `Prices in the New York area ${chg(C.total)} from ${span}` +
    (CL ? `, against ${CL.total.toFixed(1)}% from ${spanLY}. ` : '. ') +
    (trShare > 0.6 ? `Getting around accounts for ${trShare > 1 ? 'more than all' : 'most'} of the difference: gasoline, and fares for planes, trains and buses. ` : '') +
    `Leaving out car costs, prices rose ${C.without_car_costs.toFixed(1)}%` +
    (CL ? ` and ${CL.without_car_costs.toFixed(1)}% over those two spans` : ` from ${span}`) +
    `; ${noCar} percent of New York City households had no car in ${V.year}, according to the Census Bureau.`;
  const rent = D.lines.find(l => l.key === 'rent');
  const fs = D.administered.items.find(i => i.id === 'subway').steps, [fd, fv] = fs[fs.length - 1], fp = fs[fs.length - 2][1];
  const fareStep = `on ${MON[+fd.slice(5, 7) - 1]} ${+fd.slice(8)}, ${fd.slice(0, 4)}, from $${fp.toFixed(2)} to $${fv.toFixed(2)}`;
  $('lede').innerHTML =
    `Every figure on this page compares the same months in two years, so the normal seasonal ups and downs cancel out, and every price is the same thing measured the same way each month. ` +
    `From ${span}, gasoline in the metro area <b>${chg(gas.change)}</b> and fares for planes, trains and buses, which BLS groups together, <b>${chg(pub.change)}</b>; the subway and bus fare itself last changed ${fareStep}. ` +
    `Over the same months, the rent New York-area tenants actually pay, stabilized leases included, <b>${chg(rent.ytd)}</b>` +
    (rent.ytd_ly == null ? '' : `, against ${rent.ytd_ly.toFixed(1)}% from ${spanLY}`) + `, and groceries <b>${chg(D.lines.find(l => l.key === 'groceries').ytd)}</b>. ` +
    (D.lines[0].yoy == null ? gapNote : `From ${span12}, prices ${chg(D.lines[0].yoy)}.`);

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
    return `<div class="cbar"><div class="lab">${label}<small>${sub}</small></div><div class="track">${segs}</div><div class="tot">${sign(c.total)}</div></div>`;
  };
  $('contrib').innerHTML = barRow(C, 'This year', span) +
    (CL ? barRow(CL, 'Last year', spanLY) : `<p class="note">${gapNote}</p>`);
  let ax = '';
  for (let v = lo; v <= hi + 1e-9; v += 0.5) ax += `<span style="left:${X(v)}%">${v === 0 ? '0' : pts(v, 1).replace('+', '')}</span>`;
  $('contrib-axis').innerHTML = ax;
  $('contrib-key').innerHTML = order.map(code => `<span class="key"><i style="background:var(--${INK[code]})"></i>${esc(byCode(C, code).name)}</span>`).join('');
  $('contrib-note').innerHTML = `Bars are percentage points: each category's weight in the New York-area Consumer Price Index times its own price change. They add up exactly to the all-items change. Source: <a href="https://www.bls.gov/regions/northeast/news-release/consumerpriceindex_newyorkarea.htm">BLS Consumer Price Index, New York-Newark-Jersey City</a> and <a href="https://www.bls.gov/cpi/tables/relative-importance/home.htm">BLS relative importance tables</a>.`;

  $('wdate').textContent = `December ${D.base.slice(0, 4)}`;
  // ---- category table --------------------------------------------------------
  const maxC = Math.max(...C.groups.flatMap(g => [g.contrib, ...g.parts.map(p => p.contrib)]).map(Math.abs));
  const cbox = (v, ink) => `<span class="cbox">${pts(v)}<i style="width:${Math.abs(v) / maxC * 70}px;background:var(--${ink});opacity:${v < 0 ? .5 : 1}"></i></span>`;
  const lyFor = (code, partCode) => {
    if (!CL) return null;
    const g = byCode(CL, code);
    return partCode === undefined ? g : g.parts.find(p => p.code === partCode.code && p.name === partCode.name);
  };
  let t = `<thead><tr><th>Category</th><th>Of every $100</th><th>Change<br>${mshort(D.base)} ${D.base.slice(0, 4)} to ${mshort(D.ref)} ${D.ref.slice(0, 4)}</th><th>Same months a year earlier<br>${mshort(D.base_ly)} ${D.base_ly.slice(0, 4)} to ${mshort(D.ref_ly)} ${D.ref_ly.slice(0, 4)}</th><th>Points of the<br>${C.total.toFixed(1)}% total</th></tr></thead><tbody>`;
  C.groups.forEach(g => {
    const ly = lyFor(g.code);
    t += `<tr><td class="nm"><span class="sw" style="background:var(--${INK[g.code]})"></span>${esc(g.name)}</td><td>$${g.weight.toFixed(2)}</td><td class="${cls(g.change)}">${sign(g.change)}</td><td>${ly ? sign(ly.change) : 'n/a'}</td><td>${cbox(g.contrib, INK[g.code])}</td></tr>`;
    g.parts.forEach(p => {
      const lp = lyFor(g.code, p);
      t += `<tr class="part"><td class="nm">${esc(p.name)}${p.remainder ? ' (remainder)' : p.derived ? ' (derived)' : ''}</td><td>$${p.weight.toFixed(2)}</td><td class="${cls(p.change)}">${p.remainder ? '' : sign(p.change)}</td><td>${p.remainder || !lp ? '' : sign(lp.change)}</td><td>${cbox(p.contrib, INK[g.code])}</td></tr>`;
    });
  });
  t += `<tr><td class="nm">All items</td><td>$100.00</td><td class="${cls(C.total)}"><b>${sign(C.total)}</b></td><td>${CL ? sign(CL.total) : 'n/a'}</td><td><span class="cbox">${pts(C.total)}</span></td></tr></tbody>`;
  $('cat').innerHTML = t;

  // shared helpers for the sections other files fill in
  window.NYC = {D, $, tok, esc, sign, pts, cls, mname, mshort, myear, span, spanLY, span12, chg};
  for (const f of ['rent', 'energy', 'food', 'admin', 'pay', 'foot']) {
    if (window['render_' + f]) window['render_' + f](window.NYC);
  }
})();
