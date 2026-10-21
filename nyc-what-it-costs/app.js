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
  const span = `December ${D.base.slice(0, 4)} to ${myear(D.ref)}`;
  const spanLY = `December ${D.base_ly.slice(0, 4)} to ${myear(D.ref_ly)}`;
  $('span-line').textContent = `Latest month: ${myear(D.ref)} · rebuilt ${D.built}`;

  // ---- opening -------------------------------------------------------------
  const INK = {SAH: 'cobalt', SAT: 'vermilion', SAF: 'sun', SAM: 'mint', SAE: 'cyan', SAR: 'lilac', SAA: 'rose', SAG: 'orange'};
  const byCode = (c, code) => c.groups.find(g => g.code === code);
  const tr = byCode(C, 'SAT'), trLY = byCode(CL, 'SAT');
  const gas = tr.parts.find(p => p.code === 'SETB01');
  const diff = C.total - CL.total;
  const trShare = (tr.contrib - trLY.contrib) / diff;
  $('finding').textContent =
    `Prices in the New York area rose ${C.total.toFixed(1)}% from December to ${mname(D.ref)}, ` +
    `against ${CL.total.toFixed(1)}% over the same months of ${D.ref_ly.slice(0, 4)}. ` +
    (trShare > 0.6 ? `Transportation, mostly gasoline, accounts for ${trShare > 1 ? 'more than all' : 'most'} of the difference.` : '');
  const rent = D.lines.find(l => l.key === 'rent');
  $('lede').innerHTML =
    `Every figure on this page compares the same months in two years, so the normal seasonal ups and downs cancel out, and every price is the same thing measured the same way each month. ` +
    `Gasoline in the metro area is up <b>${sign(gas.change)}</b> since December. The rent New York-area tenants actually pay, stabilized leases included, is up <b>${sign(rent.ytd)}</b>, ` +
    `about what it did over the same months last year (${sign(rent.ytd_ly)}). ` +
    `Groceries are up <b>${sign(D.lines.find(l => l.key === 'groceries').ytd)}</b>. ` +
    `Over the full twelve months to ${mname(D.ref)}, prices are up <b>${sign(D.lines[0].yoy)}</b>.`;

  // ---- contribution bars ---------------------------------------------------
  const maxTot = Math.max(...[C, CL].map(c => c.groups.filter(g => g.contrib > 0).reduce((a, g) => a + g.contrib, 0)));
  const minNeg = Math.min(0, ...[C, CL].map(c => c.groups.filter(g => g.contrib < 0).reduce((a, g) => a + g.contrib, 0)));
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
  $('contrib').innerHTML = barRow(C, 'This year', span) + barRow(CL, 'Last year', spanLY);
  let ax = '';
  for (let v = lo; v <= hi + 1e-9; v += 0.5) ax += `<span style="left:${X(v)}%">${v === 0 ? '0' : pts(v, 1).replace('+', '')}</span>`;
  $('contrib-axis').innerHTML = ax;
  $('contrib-key').innerHTML = order.map(code => `<span class="key"><i style="background:var(--${INK[code]})"></i>${esc(byCode(C, code).name)}</span>`).join('');
  $('contrib-note').innerHTML = `Bars are percentage points: each category's weight in the New York-area Consumer Price Index times its own price change. They add up exactly to the all-items change. Source: <a href="https://www.bls.gov/regions/northeast/news-release/consumerpriceindex_newyorkarea.htm">BLS Consumer Price Index, New York-Newark-Jersey City</a> and <a href="https://www.bls.gov/cpi/tables/relative-importance/home.htm">BLS relative importance tables</a>.`;

  // ---- category table --------------------------------------------------------
  const maxC = Math.max(...C.groups.flatMap(g => [g.contrib, ...g.parts.map(p => p.contrib)]).map(Math.abs));
  const cbox = (v, ink) => `<span class="cbox">${pts(v)}<i style="width:${Math.abs(v) / maxC * 70}px;background:var(--${ink});opacity:${v < 0 ? .5 : 1}"></i></span>`;
  const lyFor = (code, partCode) => {
    const g = byCode(CL, code);
    return partCode === undefined ? g : g.parts.find(p => p.code === partCode);
  };
  let t = `<thead><tr><th>Category</th><th>Of every $100</th><th>Change this year<br>${mshort(D.base)} to ${mshort(D.ref)}</th><th>Same months<br>last year</th><th>Points of the<br>${C.total.toFixed(1)}% total</th></tr></thead><tbody>`;
  C.groups.forEach(g => {
    const ly = lyFor(g.code);
    t += `<tr><td class="nm"><span class="sw" style="background:var(--${INK[g.code]})"></span>${esc(g.name)}</td><td>$${g.weight.toFixed(2)}</td><td class="${cls(g.change)}">${sign(g.change)}</td><td>${sign(ly.change)}</td><td>${cbox(g.contrib, INK[g.code])}</td></tr>`;
    g.parts.forEach(p => {
      const lp = lyFor(g.code, p.code);
      t += `<tr class="part"><td class="nm">${esc(p.name)}${p.remainder ? ' (remainder)' : ''}</td><td>$${p.weight.toFixed(2)}</td><td class="${cls(p.change)}">${p.remainder ? '' : sign(p.change)}</td><td>${p.remainder || !lp ? '' : sign(lp.change)}</td><td>${cbox(p.contrib, INK[g.code])}</td></tr>`;
    });
  });
  t += `<tr><td class="nm">All items</td><td>$100.00</td><td class="${cls(C.total)}"><b>${sign(C.total)}</b></td><td>${sign(CL.total)}</td><td><span class="cbox">${pts(C.total)}</span></td></tr></tbody>`;
  $('cat').innerHTML = t;

  // shared helpers for the sections other files fill in
  window.NYC = {D, $, tok, esc, sign, pts, cls, mname, mshort, myear, span, spanLY};
  for (const f of ['rent', 'energy', 'food', 'admin', 'pay', 'foot']) {
    if (window['render_' + f]) window['render_' + f](window.NYC);
  }
})();
