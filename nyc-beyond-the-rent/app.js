/* Beyond the Rent — renders data/dashboard.json (built by scripts/build.py).
   Every number in the copy is computed from that file, so a refresh updates the prose. */
(() => {
'use strict';

const $ = s => document.querySelector(s);
const css = getComputedStyle(document.documentElement);
const tok = n => css.getPropertyValue('--' + n).trim();
const C = {
  nyc: tok('vermilion'), nys: tok('cyan'), usa: '#c9cec7', ne: tok('lilac'), sun: tok('sun'), mint: tok('mint'),
  cobalt: tok('cobalt'), orange: tok('orange'), rose: tok('rose'), lilac: tok('lilac'), cyan: tok('cyan'),
  fg: tok('fg'), fg2: tok('fg2'), grid: tok('grid'), line: tok('line'), bg: tok('bg'), bg2: tok('bg2')
};
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const APMON = ['Jan.','Feb.','March','April','May','June','July','Aug.','Sept.','Oct.','Nov.','Dec.'];

// ---------- sources ----------
const SRC = {
  e861: 'https://www.eia.gov/electricity/data/eia861m/',
  bls: id => 'https://data.bls.gov/timeseries/' + id,
  nyiso: 'https://www.nyiso.com/energy-market-operational-data',
  hh: 'https://www.eia.gov/dnav/ng/hist/rngwhhdm.htm',
  gasny: 'https://www.eia.gov/dnav/ng/hist/n3010ny3m.htm',
  gasus: 'https://www.eia.gov/dnav/ng/hist/n3010us3m.htm',
  gasnj: 'https://www.eia.gov/dnav/ng/hist/n3010nj3m.htm',
  citygate: 'https://www.eia.gov/dnav/ng/hist/n3050ny3m.htm',
  nyserda: 'https://data.ny.gov/d/rc94-5y2u',
  oilus: 'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=W_EPD2F_PRS_NUS_DPG&f=W',
  spot: 'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EER_EPD2F_PF4_Y35NY_DPG&f=M',
  m: a => 'methodology.html#' + a
};
const L = (url, txt) => `<a class="c" href="${url}">${txt}</a>`;

// ---------- formatting ----------
const ym = k => { const [y, m] = k.split('-').map(Number); return { y, m }; };
const monthName = k => { const { y, m } = ym(k); return `${MONTHS[m - 1]} ${y}`; };
const apDate = d => { const [y, m, dd] = d.split('-').map(Number); return `${APMON[m - 1]} ${dd}, ${y}`; };
const shortM = k => { const { y, m } = ym(k); return `${MON[m - 1]} ${y}`; };
const addM = (k, n) => { let { y, m } = ym(k); m += n; while (m > 12) { m -= 12; y++; } while (m < 1) { m += 12; y--; } return `${y}-${String(m).padStart(2, '0')}`; };
const fx = (v, d = 1) => v == null ? '–' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const cents = (v, d = 1) => `${fx(v, d)} cents`;
const usd = (v, d = 2) => `$${fx(v, d)}`;
const pct = (a, b) => (a / b - 1) * 100;
const chg = (p, d = 1) => p >= 0 ? `rose ${fx(p, d)}%` : `fell ${fx(-p, d)}%`;
const chgShort = (p, d = 1) => p >= 0 ? `up ${fx(p, d)}%` : `down ${fx(-p, d)}%`;
const toT = k => { const { y, m } = ym(k); return y + (m - 1) / 12; };
const pts = obj => Object.keys(obj).sort().map(k => [toT(k), obj[k], k]).filter(p => p[1] != null);

// ---------- chart: lines ----------
function niceTicks(lo, hi, n = 5) {
  const span = hi - lo || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => span / s <= n) || 10 * mag;
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
const svgNS = 'http://www.w3.org/2000/svg';

function lineChart(el, o) {
  // o: {series:[{label,color,data:[[t,v,key]],width,dash,area}], fmt, yMin, yMax, h, ann:[{t,label}], right:{...}, zero, stack}
  const draw = () => {
    const W = el.clientWidth || 600, mob = W < 560;
    const H = o.h ? (mob ? Math.round(o.h * 0.8) : o.h) : (mob ? 230 : 320);
    const m = { t: 14, r: o.right ? 46 : 14, b: 26, l: o.lPad || 44 };
    const all = o.series.flatMap(s => s.data);
    let x0 = o.xMin ?? Math.min(...all.map(p => p[0])), x1 = o.xMax ?? Math.max(...all.map(p => p[0]));
    let vals = o.stack ? stackTotals(o.series) : all.map(p => p[1]);
    let y0 = o.yMin ?? Math.min(0, ...vals), y1 = o.yMax ?? Math.max(...vals);
    if (o.yMin == null && !o.zero) y0 = Math.min(...vals) - (y1 - Math.min(...vals)) * 0.08;
    const ticks = niceTicks(y0, y1 * 1.04, mob ? 4 : 5);
    y0 = Math.min(y0, ticks[0]); y1 = Math.max(y1, ticks[ticks.length - 1]);
    const X = t => m.l + (t - x0) / (x1 - x0) * (W - m.l - m.r);
    const Y = v => m.t + (1 - (v - y0) / (y1 - y0)) * (H - m.t - m.b);
    let s = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="${o.aria || ''}">`;
    ticks.forEach(v => { s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}" ${v === 0 ? `stroke="${C.fg2}"` : ''}/>`;
      s += `<text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${o.fmt(v, true)}</text>`; });
    const yr0 = Math.ceil(x0), yr1 = Math.floor(x1), span = yr1 - yr0;
    const every = span > 24 ? 5 : span > 12 ? (mob ? 4 : 2) : (mob ? 2 : 1);
    for (let y = yr0; y <= yr1; y++) if (y % every === 0 || (every === 1)) s += `<text x="${X(y)}" y="${H - 6}" text-anchor="middle">${y}</text><line x1="${X(y)}" x2="${X(y)}" y1="${H - m.b}" y2="${H - m.b + 4}" stroke="${C.fg2}"/>`;
    if (o.right) {
      const rt = niceTicks(o.right.min ?? 0, o.right.max, mob ? 4 : 5), rmax = rt[rt.length - 1], rmin = Math.min(o.right.min ?? 0, rt[0]);
      o.right.Y = v => m.t + (1 - (v - rmin) / (rmax - rmin)) * (H - m.t - m.b);
      rt.forEach(v => s += `<text x="${W - m.r + 6}" y="${o.right.Y(v) + 4}">${o.right.fmt(v)}</text>`);
    }
    (o.ann || []).forEach(a => { if (a.t < x0 || a.t > x1) return; const x = X(a.t);
      s += `<line x1="${x}" x2="${x}" y1="${m.t}" y2="${H - m.b}" stroke="${C.line}" stroke-dasharray="2 3"/>`;
      if (!mob) s += `<text class="ann" x="${x > W - m.r - 110 ? x - 4 : x + 4}" text-anchor="${x > W - m.r - 110 ? 'end' : 'start'}" y="${m.t + 10 + (a.row || 0) * 13}">${a.label}</text>`; });
    if (o.stack) {
      let base = null;
      o.series.forEach(se => {
        const d = se.data.filter(p => p[0] >= x0 && p[0] <= x1);
        const top = d.map((p, i) => [p[0], (base ? base[i][1] : 0) + p[1]]);
        const bot = base ? base.slice(0, d.length) : d.map(p => [p[0], 0]);
        const path = top.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('') +
          bot.slice().reverse().map(p => `L${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('') + 'Z';
        s += `<path d="${path}" fill="${se.color}" fill-opacity=".85"/>`;
        base = top;
      });
    } else {
      o.series.forEach(se => {
        const Yf = se.right ? o.right.Y : Y;
        let path = '', prev = null;
        se.data.forEach(p => { if (p[0] < x0 || p[0] > x1) return;
          const gap = prev && (p[0] - prev[0]) > (se.gap || 0.2);
          path += `${!prev || gap ? 'M' : 'L'}${X(p[0]).toFixed(1)},${Yf(p[1]).toFixed(1)}`; prev = p; });
        s += `<path d="${path}" fill="none" stroke="${se.color}" stroke-width="${se.width || 2}" ${se.dash ? `stroke-dasharray="${se.dash}"` : ''} stroke-opacity="${se.op || 1}" stroke-linejoin="round" style="mix-blend-mode:screen"/>`;
      });
    }
    s += `<line class="hov" x1="0" x2="0" y1="${m.t}" y2="${H - m.b}" stroke="${C.fg}" stroke-width="1" visibility="hidden"/>`;
    s += `<rect x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}" fill="transparent"/></svg>`;
    el.innerHTML = s + '<div class="tip"></div>';
    const svg = el.querySelector('svg'), tip = el.querySelector('.tip'), hov = el.querySelector('.hov');
    const move = ev => {
      const r = svg.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
      const t = x0 + (px - m.l) / (W - m.l - m.r) * (x1 - x0);
      if (t < x0 || t > x1) return hide();
      let rows = [], when = null, xs = null;
      o.series.forEach(se => {
        if (se.noTip) return;
        let best = null; for (const p of se.data) if (!best || Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
        if (best && Math.abs(best[0] - t) < (se.snap || 0.07)) { rows.push(`<div><i style="background:${se.color}"></i>${se.label}: <b style="display:inline">${(se.fmt || o.fmt)(best[1])}</b></div>`); when = when || best[2]; xs = xs ?? X(best[0]); }
      });
      if (!rows.length) return hide();
      hov.setAttribute('x1', xs); hov.setAttribute('x2', xs); hov.setAttribute('visibility', 'visible');
      tip.innerHTML = `<b>${o.when ? o.when(when) : (when.length === 7 ? shortM(when) : apDate(when))}</b>${rows.join('')}`;
      tip.style.display = 'block';
      const tw = tip.offsetWidth; tip.style.left = Math.min(Math.max(0, xs + 12), W - tw) + 'px';
      if (xs + 12 + tw > W) tip.style.left = Math.max(0, xs - tw - 12) + 'px';
      tip.style.top = (m.t + 4) + 'px';
    };
    const hide = () => { tip.style.display = 'none'; hov.setAttribute('visibility', 'hidden'); };
    svg.addEventListener('mousemove', move); svg.addEventListener('touchmove', move, { passive: true });
    svg.addEventListener('mouseleave', hide);
  };
  draw(); charts.push(draw); return draw;
}
function stackTotals(series) {
  const n = series[0].data.length, out = [];
  for (let i = 0; i < n; i++) out.push(series.reduce((a, s) => a + (s.data[i] ? s.data[i][1] : 0), 0));
  return out;
}
const charts = [];
let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => charts.forEach(f => f()), 120); });

function toggle(sel, attr, fn) {
  document.querySelectorAll(sel).forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll(sel).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false'));
    fn(b.dataset[attr]);
  }));
}

// ---------- main ----------
fetch('data/dashboard.json').then(r => r.json()).then(D => render(D)).catch(err => {
  $('#finding').innerHTML = `<span class="err">The data file did not load (${err.message}).</span>`; console.error(err);
});

function render(D) {
  const E = D.elec, el = E.latest, G = D.gas, gl = G.latest, O = D.oil, ol = O.latest, CPI = D.cpi;
  const W = D.water || {}, R = D.coned_research || {};
  const LM = el.month, LMn = monthName(LM), LMy = monthName(addM(LM, -12));
  const win = `the 12 months through ${LMn}`, winY = `the 12 months through ${LMy}`;

  $('#through').innerHTML = `Electricity and gas through ${LMn}; heating oil through the week of ${apDate(ol.date)}`;

  // ---------- finding + lede ----------
  const peers50 = E.peers;
  const ci = peers50.findIndex(p => p.name.startsWith('Consolidated Edison'));
  const above = peers50.slice(0, ci);
  const aboveTxt = above.length ? `only ${listJoin(above.map(p => shortName(p.name)))} charged more` : 'none charged more';
  $('#finding').innerHTML = `New York City households that buy their power from Con Edison paid an average of ${L(SRC.e861, cents(el.coned_t12))} per kilowatt-hour over ${win}, ${L(SRC.m('ratio'), fx(el.coned_t12 / el.us_t12, 1) + ' times')} the national average of ${L(SRC.e861, cents(el.us_t12))}.`;

  const rentS = CPI.nyc_rent, allS = CPI.nyc_all, cm = Object.keys(allS).sort().pop();
  const rentY = pct(rentS[cm], rentS[addM(cm, -12)]), allY = pct(allS[cm], allS[addM(cm, -12)]);
  const wr = (W.rates || []).filter(x => x.increase_pct != null).sort((a, b) => b.fy - a.fy)[0];
  $('#lede').innerHTML =
    `Among U.S. utilities with at least 50,000 full-service residential customers, ${aboveTxt} over that period (${L(SRC.m('peers'), 'EIA-861M')}). ` +
    `Con Edison’s 12-month average price ${L(SRC.m('t12'), chg(el.coned_t12_yoy))} from ${winY}, and its average residential bill ${L(SRC.m('bill'), `${chg(el.coned_t12bill_yoy)}, to ${usd(el.coned_t12bill, 0)} a month`)}. ` +
    `Residential gas in New York State averaged ${L(SRC.gasny, usd(gl.ny_t12) + ' per thousand cubic feet')} over the 12 months through ${monthName(gl.month)}, ${L(SRC.m('gas'), chgShort(gl.ny_t12_yoy))} on the year. ` +
    `Heating oil in New York City cost ${L(SRC.nyserda, usd(ol.nyc) + ' a gallon')} the week of ${apDate(ol.date)}, against ${L(SRC.nyserda, usd(ol.nyc_yago))} the week of ${apDate(ol.yago_date)}` +
    (wr ? `. The city’s water and sewer rates ${wr.increase_pct >= 0 ? 'rose' : 'fell'} ${L(wr.increase_url || wr.url, fx(wr.increase_pct, 1) + '%')} on July 1, ${wr.fy - 1}, for fiscal year ${wr.fy}` : '') +
    `. For comparison, New York-area rent ${L(SRC.bls('CUURS12ASEHA'), chg(rentY))} and all prices ${L(SRC.bls('CUURS12ASA0'), chg(allY))} from ${monthName(addM(cm, -12))} to ${monthName(cm)}.`;

  // ---------- small multiples ----------
  overview(D);

  // ---------- electricity ----------
  const dec = el.decade;
  $('#e-intro').innerHTML = `Con Edison delivers power to the five boroughs and most of Westchester; about ${L(SRC.e861, fx(el.coned_cust / 1e6, 2) + ' million')} residential accounts bought their electricity from it in ${LMn}. Its 12-month average price ${L(SRC.m('t12'), chg(dec.coned.pct))} from ${L(SRC.e861, cents(dec.coned.from))} in the 12 months through ${monthName(el.decade_from)} to ${L(SRC.e861, cents(dec.coned.to))} in ${win}. Over the same decade, prices ${L(SRC.m('t12'), chg(dec.other.pct))} at the other New York utilities, which serve the rest of the state, and ${L(SRC.m('t12'), chg(dec.us.pct))} nationwide.`;
  const ann = planStarts(R);
  let emode = 't12';
  const eseries = mode => {
    const pick = k => E[k][mode] || {};
    const S = [
      { label: 'United States', color: C.usa, data: pts(pick('us')), width: 2 },
      { label: 'New York State, all customers', color: C.ne, data: pts(pick('nys')), width: 2 },
      { label: 'Other New York utilities', color: C.nys, data: pts(pick('other')), width: 2 },
      { label: 'Con Edison', color: C.nyc, data: pts(pick('coned')), width: 3 },
    ];
    return S.filter(s => s.data.length);
  };
  const drawE = () => {
    const isBill = emode === 't12bill';
    const box = $('#c-elec'); if (box._d) charts.splice(charts.indexOf(box._d), 1);
    box._d = lineChart(box, { series: eseries(emode), fmt: (v, ax) => isBill ? `$${fx(v, 0)}` : (ax ? fx(v, 0) + '¢' : fx(v, 1) + '¢'), zero: true, xMin: 2010, ann: emode === 'price' ? [] : ann, aria: 'Residential electricity prices' });
    $('#e-note').innerHTML = isBill
      ? `Average monthly bill = residential revenue divided by residential customers, averaged over 12 months. Con Edison’s apartment-heavy customer base uses less power per household than most of the country, so its bills sit closer to other utilities’ than its prices do. ${L(SRC.m('bill'), 'How this is calculated')}.`
      : `Con Edison and other utilities: full-service residential customers only, the households that buy both power and delivery from the utility (${L(SRC.e861, 'EIA-861M')}). State and national lines: all residential customers (${L(SRC.e861, 'EIA')}). ${emode === 't12' ? 'Twelve-month averages remove the summer and winter swings.' : 'Monthly figures move with the seasons; see the grid below.'} ${ann.length ? 'Dotted lines mark the start of each Con Edison electric rate plan approved by the Public Service Commission.' : ''}`;
  };
  $('#c-elec')._d = null; drawE();
  toggle('[data-e]', 'e', v => { emode = v; drawE(); });

  // ranking
  $('#e-rank-intro').innerHTML = `Average residential price over ${win}, every U.S. utility with at least 50,000 full-service residential customers (${L(SRC.e861, 'EIA-861M')}). Con Edison is in red, other New York utilities in blue.`;
  let rmode = 'price', eastOnly = false;
  const drawRank = () => {
    let rows = E.peers.filter(p => !eastOnly || p.east).slice();
    rows.sort((a, b) => b[rmode] - a[rmode]);
    const ix = rows.findIndex(p => p.name.startsWith('Consolidated Edison'));
    const show = rows.slice(0, 20);
    if (ix >= 20) show.push(rows[ix]);
    const max = Math.max(...rows.map(p => p[rmode]));
    $('#rank').innerHTML = show.map((p, i) => {
      const me = p.name.startsWith('Consolidated Edison'), ny = p.states.split('/').includes('NY');
      const n = rows.indexOf(p) + 1;
      return `<span class="n ${me ? 'me-row' : ''}" title="${p.name}">${n}. ${shortName(p.name)}<small>${p.states}</small></span>` +
        `<span><i class="b ${me ? 'me' : ny ? 'ny' : p.east ? 'east' : ''}" style="width:${(p[rmode] / max * 100).toFixed(1)}%"></i></span>` +
        `<span class="v">${rmode === 'price' ? fx(p.price, 1) + '¢' : '$' + fx(p.bill, 0)}</span>`;
    }).join('');
    $('#rank-note').innerHTML = `${rows.length} utilities ranked${eastOnly ? ' in the eastern states (the Eastern and Central time zones east of the Mississippi)' : ''}; the top 20 shown. Full-service customers only: households that buy power from another supplier are excluded from each utility’s figure. Lighter bars are eastern utilities.`;
  };
  drawRank();
  document.querySelectorAll('[data-r]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.r === 'east') { eastOnly = !eastOnly; b.setAttribute('aria-pressed', eastOnly); }
    else { rmode = b.dataset.r; document.querySelectorAll('[data-r]:not([data-r=east])').forEach(x => x.setAttribute('aria-pressed', x === b)); }
    drawRank();
  }));

  // metro table
  const ny = E.metro.find(m => m.metro === 'New York');
  const eastAbove = E.metro.filter(m => m.east && m.p2024 > ny.p2024).map(m => m.metro);
  $('#e-metro-intro').innerHTML = `BLS’s average price for electricity in 2024, the last full year before it stopped publishing most metro-area energy prices. New York’s metro average was ${L(SRC.bls('APUS12A72610'), cents(ny.p2024))} per kWh${eastAbove.length ? `; among eastern metros only ${listJoin(eastAbove)} was higher` : ''}.`;
  $('#metro').innerHTML = `<thead><tr><th>Metro area</th><th class="r">2014</th><th class="r">2024</th><th class="r">Change</th></tr></thead><tbody>` +
    E.metro.map(m => `<tr${m.metro === 'New York' ? ' style="font-weight:700"' : ''}><td>${m.metro}</td><td class="r">${m.p2014 ? fx(m.p2014) + '¢' : '–'}</td><td class="r">${L(SRC.bls(m.sid), fx(m.p2024) + '¢')}</td><td class="r">${m.p2014 ? fx(pct(m.p2024, m.p2014), 0) + '%' : '–'}</td></tr>`).join('') + '</tbody>';

  // split
  const sl = E.split_latest;
  $('#e-split-intro').innerHTML = `The wholesale price of energy in the New York City zone averaged ${L(SRC.nyiso, cents(sl.energy) + ' per kWh')} over the 12 months through ${monthName(sl.month)}, ${L(SRC.m('split'), fx(sl.share, 0) + '%')} of Con Edison’s ${L(SRC.e861, cents(sl.retail))} residential price. Ten years earlier, over the 12 months through ${monthName(sl.base_month)}, it was ${L(SRC.nyiso, cents(sl.energy_base))} of ${L(SRC.e861, cents(sl.retail_base))}. The rest of the price, ${L(SRC.m('split'), cents(sl.retail - sl.energy))} now against ${L(SRC.m('split'), cents(sl.retail_base - sl.energy_base))} then, covers delivery, generating capacity, grid services, line losses, taxes and state programs.`;
  const sp = E.split, keys = Object.keys(sp.retail).filter(k => sp.energy[k] != null).sort();
  lineChart($('#c-split'), { stack: true, zero: true, aria: 'Con Edison price split',
    series: [{ label: 'Wholesale energy', color: C.sun, data: keys.map(k => [toT(k), sp.energy[k], k]) },
             { label: 'Everything else', color: C.nyc, data: keys.map(k => [toT(k), sp.retail[k] - sp.energy[k], k]) }],
    fmt: (v, ax) => ax ? fx(v, 0) + '¢' : fx(v, 1) + '¢', ann });
  $('#split-note').innerHTML = `Wholesale energy is the simple average of NYISO day-ahead hourly prices for Zone J (${L(SRC.nyiso, 'NYISO')}). It leaves out capacity payments, which are large in New York City, and the utility’s hedging, so the real supply share of a bill is larger. ${L(SRC.m('split'), 'Method')}.`;

  // gas-power
  const J = E.lbmp.J, HH = E.henry_hub;
  $('#e-gas-intro').innerHTML = `Monthly Zone J wholesale prices and the Henry Hub gas price moved together from 2010 on, with a ${L(SRC.m('gaspower'), 'correlation of ' + fx(E.gas_power_r, 2))}.`;
  const hmax = Math.max(...Object.values(HH).filter((v, i) => Object.keys(HH)[i] >= '2010'));
  lineChart($('#c-gaspower'), { xMin: 2010, zero: true, h: 260, aria: 'Zone J power and Henry Hub gas',
    right: { max: hmax, fmt: v => '$' + fx(v, 0) },
    series: [{ label: 'Zone J, $/MWh', color: C.sun, data: pts(J), width: 2 },
             { label: 'Henry Hub, $/MMBtu', color: C.cobalt, data: pts(HH).filter(p => p[0] >= 2010), width: 2, right: true, fmt: v => '$' + fx(v, 2) }],
    fmt: (v, ax) => '$' + fx(v, ax ? 0 : 2) });

  // lag
  const pl = E.passthrough, best = pl.reduce((a, b) => b.r > a.r ? b : a);
  $('#e-lag-intro').innerHTML = `Comparing each month’s year-over-year change in Con Edison’s price with the year-over-year change in the Zone J wholesale price zero to six months earlier, 2011 to ${LM.slice(0, 4)}: the strongest link is ${best.lag === 0 ? 'in the same month' : best.lag + ' months later'}, and it is weak, a ${L(SRC.m('lag'), 'correlation of ' + fx(best.r, 2))}. Each extra cent per kWh of wholesale price came with about ${fx(best.slope * 100, 0)} hundredths of a cent of retail change.`;
  const lagBox = $('#c-lag');
  const lagDraw = () => {
    const w = lagBox.clientWidth || 400, h = 190, bw = (w - 60) / pl.length, Y = v => 20 + (1 - v / 0.5) * (h - 50);
    let s = `<svg viewBox="0 0 ${w} ${h}" height="${h}">`;
    [0, 0.25, 0.5].forEach(v => s += `<line x1="40" x2="${w}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="34" y="${Y(v) + 4}" text-anchor="end">${fx(v, 2)}</text>`);
    pl.forEach((p, i) => { const x = 46 + i * bw;
      s += `<rect x="${x}" y="${Y(Math.max(p.r, 0))}" width="${bw - 10}" height="${Math.abs(Y(0) - Y(p.r))}" fill="${p.lag === best.lag ? C.sun : C.line}"/>`;
      s += `<text x="${x + (bw - 10) / 2}" y="${h - 14}" text-anchor="middle">${p.lag}</text>`; });
    s += `<text x="${46 + (w - 60) / 2}" y="${h}" text-anchor="middle">months between wholesale change and retail change</text></svg>`;
    lagBox.innerHTML = s;
  };
  lagDraw(); charts.push(lagDraw);
  $('#lag-note').innerHTML = `Bars show the correlation coefficient at each lag. Most of the price is made up of charges other than wholesale energy (see the chart above), which do not move with wholesale prices.`;

  // heat grid
  $('#e-heat-intro').innerHTML = `Each square is one month for Con Edison’s full-service residential customers. Summer bills are the largest because use rises with air conditioning: from ${E.season_years[0]} to ${E.season_years[2]}, July use averaged ${L(SRC.m('season'), fx(E.season[6].kwh, 0) + ' kWh')} per customer against ${L(SRC.m('season'), fx(E.season[4].kwh, 0) + ' kWh')} in May.`;
  let hmode = 'bill';
  const drawHeat = () => {
    const src = E.coned[hmode], ks = Object.keys(src).sort(), years = [...new Set(ks.map(k => +k.slice(0, 4)))];
    const vs = ks.map(k => src[k]), lo = Math.min(...vs), hi = Math.max(...vs);
    const ramp = v => mix(C.bg2, C.nyc, (v - lo) / (hi - lo)), ramp2 = v => (v - lo) / (hi - lo) > 0.78;
    let h = `<div class="hg" style="grid-template-columns:3rem repeat(12,minmax(26px,1fr));min-width:420px"><span></span>` + MON.map(m => `<span class="h">${m}</span>`).join('');
    years.forEach(y => { h += `<span class="y">${y}</span>`;
      for (let m = 1; m <= 12; m++) { const k = `${y}-${String(m).padStart(2, '0')}`, v = src[k];
        h += v == null ? `<span class="c e"></span>` : `<span class="c" style="background:${ramp(v)};color:${ramp2(v) ? '#111311' : C.fg}" title="${shortM(k)}: ${fmtH(v)}">${fmtH(v, true)}</span>`; } });
    $('#heat').innerHTML = h + '</div>';
    $('#heat-scale').innerHTML = `<span>${fmtH(lo)}</span><span class="ramp" style="background:linear-gradient(90deg,${C.bg2},${C.nyc})"></span><span>${fmtH(hi)}</span><span>· Source: ${L(SRC.e861, 'EIA-861M')}</span>`;
  };
  const fmtH = (v, cell) => hmode === 'bill' ? (cell ? fx(v, 0) : usd(v, 0)) : hmode === 'price' ? (cell ? fx(v, 0) : fx(v, 1) + '¢') : (cell ? fx(v, 0) : fx(v, 0) + ' kWh');
  drawHeat();
  toggle('[data-h]', 'h', v => { hmode = v; drawHeat(); });

  conedResearch(R);

  // ---------- gas ----------
  const therm = 1 / 10.36; // $/Mcf -> $/therm (1 Mcf ≈ 1.036 MMBtu = 10.36 therms)
  const t12of = obj => { const ks = Object.keys(obj).sort(), o = {}; ks.forEach((k, i) => { if (i >= 11) { const w = ks.slice(i - 11, i + 1).map(x => obj[x]); if (w.every(v => v != null) && ks[i - 11] === addM(k, -11)) o[k] = w.reduce((a, b) => a + b) / 12; } }); return o; };
  const nycTherm = t12of(G.bls_therm.nyc);
  const scale = (o, f) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v * f]));
  const nycT = G.bls_therm.nyc, nycLast = Object.keys(nycT).sort().pop();
  const nyc24 = avgYear(nycT, 2024), nyc14 = avgYear(nycT, 2014), us24 = avgYear(G.bls_therm.us, 2024), us14 = avgYear(G.bls_therm.us, 2014);
  $('#g-intro').innerHTML = `Con Edison sells gas in Manhattan, the Bronx, parts of Queens and Westchester; National Grid serves Brooklyn, Staten Island and the rest of Queens. BLS’s New York-area price for piped gas averaged ${L(SRC.bls('APUS12A72620'), usd(nyc24, 2) + ' a therm')} in 2024, ${L(SRC.m('gas'), chgShort(pct(nyc24, nyc14), 0))} from ${L(SRC.bls('APUS12A72620'), usd(nyc14, 2))} in 2014; the national average went from ${L(SRC.bls('APU000072620'), usd(us14, 2))} to ${L(SRC.bls('APU000072620'), usd(us24, 2))} (${L(SRC.m('gas'), chgShort(pct(us24, us14), 0))}). BLS stopped the New York series after December 2024. Since then the closest official measure is EIA’s statewide residential price, which ${L(SRC.gasny, chg(gl.ny_t12_yoy))} over the 12 months through ${monthName(gl.month)} against the prior 12 months; the national price ${L(SRC.gasus, chg(gl.us_t12_yoy))}.`;
  lineChart($('#c-gas'), { xMin: 2005, zero: true, aria: 'Residential gas prices',
    series: [{ label: 'United States', color: C.usa, data: pts(scale(G.eia_t12.us, therm)) },
             { label: 'New Jersey', color: C.ne, data: pts(scale(G.eia_t12.nj, therm)) },
             { label: 'New York State', color: C.nys, data: pts(scale(G.eia_t12.ny, therm)) },
             { label: 'NYC metro (BLS)', color: C.nyc, data: pts(nycTherm), width: 3 }],
    fmt: (v, ax) => '$' + fx(v, 2) });
  $('#gas-note').innerHTML = `EIA prices per thousand cubic feet converted to therms at 10.36 therms per thousand cubic feet. The BLS city figure is an average retail price including taxes and fixed charges; EIA’s is revenue divided by volume. ${L(SRC.m('gas'), 'Method')}.`;
  const st = G.stack, sk = Object.keys(st.res).filter(k => st.hh[k] != null && st.cg[k] != null).sort();
  lineChart($('#c-gasstack'), { stack: true, zero: true, aria: 'New York residential gas price stack',
    series: [{ label: 'Henry Hub', color: C.cobalt, data: sk.map(k => [toT(k), st.hh[k], k]) },
             { label: 'To city gate', color: C.cyan, data: sk.map(k => [toT(k), Math.max(0, st.cg[k] - st.hh[k]), k]) },
             { label: 'Local delivery and charges', color: C.nyc, data: sk.map(k => [toT(k), Math.max(0, st.res[k] - st.cg[k]), k]) }],
    fmt: (v, ax) => '$' + fx(v, ax ? 0 : 2) });
  $('#stack-note').innerHTML = `Over the 12 months through ${monthName(gl.stack_month)}, gas at the Henry Hub averaged ${L(SRC.hh, usd(gl.hh_t12))} per thousand cubic feet, the city-gate price in New York ${L(SRC.citygate, usd(gl.cg_t12))} and the residential price ${L(SRC.gasny, usd(gl.ny_t12))}, so the commodity was ${L(SRC.m('stack'), fx(gl.commodity_share, 0) + '%')} of what households paid. Henry Hub is a Louisiana benchmark; New York’s winter supply costs run higher.`;
  const gs = G.season;
  $('#g-season-intro').innerHTML = `New York’s residential price per thousand cubic feet, averaged by calendar month for ${E.season_years[0]}–${E.season_years[2]} (${L(SRC.gasny, 'EIA')}). Utilities’ fixed monthly charges are spread over much less gas in summer, so the per-unit price peaks when bills are smallest: ${L(SRC.gasny, usd(gs[6].ny))} in July against ${L(SRC.gasny, usd(gs[0].ny))} in January.`;
  const gsBox = $('#c-gasseason');
  const gsDraw = () => {
    const w = gsBox.clientWidth || 600, h = 200, mx = Math.max(...gs.map(g => g.ny)) * 1.1, bw = (w - 50) / 12, Y = v => 10 + (1 - v / mx) * (h - 36);
    let s = `<svg viewBox="0 0 ${w} ${h}" height="${h}">`;
    niceTicks(0, mx, 4).forEach(v => s += `<line x1="40" x2="${w}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="34" y="${Y(v) + 4}" text-anchor="end">$${v}</text>`);
    gs.forEach((g, i) => { const x = 46 + i * bw;
      s += `<rect x="${x}" y="${Y(g.ny)}" width="${bw * 0.42}" height="${Y(0) - Y(g.ny)}" fill="${C.nys}"><title>${MONTHS[i]}: New York $${fx(g.ny, 2)}</title></rect>`;
      s += `<rect x="${x + bw * 0.44}" y="${Y(g.us)}" width="${bw * 0.42}" height="${Y(0) - Y(g.us)}" fill="${C.usa}"><title>${MONTHS[i]}: U.S. $${fx(g.us, 2)}</title></rect>`;
      s += `<text x="${x + bw * 0.43}" y="${h - 8}" text-anchor="middle">${MON[i]}</text>`; });
    gsBox.innerHTML = s + '</svg>';
  };
  gsDraw(); charts.push(gsDraw);

  // ---------- oil ----------
  const regs = Object.entries(ol.regions).filter(([k]) => k !== 'Statewide').sort((a, b) => b[1] - a[1]);
  const usW = O.us_weekly, usLast = usW.v[usW.v.length - 1];
  $('#o-intro').innerHTML = `Heating oil is sold by private dealers rather than a regulated utility. NYSERDA’s weekly survey put the city’s residential price at ${L(SRC.nyserda, usd(ol.nyc))} a gallon the week of ${apDate(ol.date)}, ${L(SRC.m('oilyoy'), chgShort(ol.nyc_yoy))} from ${L(SRC.nyserda, usd(ol.nyc_yago))} the week of ${apDate(ol.yago_date)}. The statewide average was ${L(SRC.nyserda, usd(ol.state))} (${L(SRC.m('oilyoy'), chgShort(ol.state_yoy))}), and EIA’s national residential average was ${L(SRC.oilus, usd(ol.us))} the week of ${apDate(ol.us_date)}.`;
  const owk = O.weekly, wpts = (arr) => owk.dates.map((d, i) => [dt(d), arr[i], d]).filter(p => p[1] != null);
  let orange_ = '5';
  const drawOil = () => {
    const x0 = orange_ === 'all' ? 1997.6 : dt(owk.dates[owk.dates.length - 1]) - 5;
    const box = $('#c-oil'); if (box._d) charts.splice(charts.indexOf(box._d), 1);
    box._d = lineChart(box, { xMin: x0, zero: true, aria: 'Heating oil prices',
      series: [{ label: 'United States', color: C.usa, data: usW.dates.map((d, i) => [dt(d), usW.v[i], d]), gap: 0.1, snap: 0.03 },
               { label: 'New York State', color: C.nys, data: wpts(owk.new_york_statewide_average), gap: 0.1, snap: 0.03 },
               { label: 'New York City', color: C.nyc, data: wpts(owk.new_york_city_average_gal), width: 2.5, gap: 0.1, snap: 0.03 }],
      fmt: (v, ax) => '$' + fx(v, 2), when: d => apDate(d) });
  };
  drawOil(); toggle('[data-o]', 'o', v => { orange_ = v; drawOil(); });
  $('#o-reg-intro').innerHTML = `NYSERDA surveys dealers in eight regions. The week of ${apDate(ol.date)}, New York City ${regs[0][0] === 'New York City' ? 'had the highest price of the eight' : 'ranked ' + (regs.findIndex(r => r[0] === 'New York City') + 1) + ' of eight'}.`;
  const rmax = Math.max(...regs.map(r => r[1]));
  $('#oilreg').innerHTML = regs.map(([k, v]) => `<span class="n ${k === 'New York City' ? 'me-row' : ''}">${k}</span><span><i class="b ${k === 'New York City' ? 'me' : 'ny'}" style="width:${(v / rmax * 100).toFixed(1)}%"></i></span><span class="v">${L(SRC.nyserda, '$' + fx(v, 2))}</span>`).join('');
  const sp_ = O.spot, mg = O.margin, mk = Object.keys(mg).filter(k => k >= '2010').sort();
  $('#o-margin-intro').innerHTML = `The wholesale spot price for heating oil in New York Harbor averaged ${L(SRC.spot, usd(ol.spot) + ' a gallon')} in ${monthName(ol.spot_month)}. The city’s retail price was ${L(SRC.m('margin'), usd(ol.margin))} above it that month; the gap averaged ${L(SRC.m('margin'), usd(ol.margin_t12))} over the 12 months through ${monthName(ol.margin_month)} and ${L(SRC.m('margin'), usd(ol.margin_t12_yago))} over the 12 months before. Summer retail prices come from fewer dealer reports.`;
  lineChart($('#c-oilmargin'), { stack: true, zero: true, h: 260, aria: 'Heating oil wholesale and markup',
    series: [{ label: 'Wholesale', color: C.sun, data: mk.map(k => [toT(k), sp_[k], k]) },
             { label: 'Retail markup', color: C.nyc, data: mk.map(k => [toT(k), Math.max(0, mg[k]), k]) }],
    fmt: (v, ax) => '$' + fx(v, 2) });

  // ---------- water ----------
  water(D);

  // ---------- rent ----------
  const ma = o => { const ks = Object.keys(o).sort(), out = {}; ks.forEach((k, i) => { if (i >= 11 && ks[i - 11] === addM(k, -11)) out[k] = ks.slice(i - 11, i + 1).reduce((a, x) => a + o[x], 0) / 12; }); return out; };
  const idx = o => { const m = ma(o), b = m['2000-12']; return Object.fromEntries(Object.keys(m).sort().filter(k => k >= '2000-12').map(k => [k, (m[k] / b - 1) * 100])); };
  const av = (o, y) => avgYear(o, y);
  const ch24 = id => pct(av(CPI[id], 2024), av(CPI[id], 2000));
  $('#r-intro').innerHTML = `Comparing annual averages for 2000 and 2024, the last full year BLS published New York-area utility indexes: electricity prices in the metro area ${L(SRC.bls('CUURS12ASEHF01'), chg(ch24('nyc_elec'), 0))}, piped gas ${L(SRC.bls('CUURS12ASEHF02'), chg(ch24('nyc_gas'), 0))}, rent ${L(SRC.bls('CUURS12ASEHA'), chg(ch24('nyc_rent'), 0))} and all prices ${L(SRC.bls('CUURS12ASA0'), chg(ch24('nyc_all'), 0))}. The rent and all-items lines continue through ${monthName(cm)}.`;
  lineChart($('#c-rent'), { xMin: 2000, zero: true, aria: 'Consumer price indexes since 2000',
    series: [{ label: 'All items', color: C.usa, data: pts(idx(CPI.nyc_all)) },
             { label: 'Rent', color: C.mint, data: pts(idx(CPI.nyc_rent)), width: 2.5 },
             { label: 'Piped gas', color: C.orange, data: pts(idx(CPI.nyc_gas)), width: 2 },
             { label: 'Electricity', color: C.nyc, data: pts(idx(CPI.nyc_elec)), width: 2.5 }],
    fmt: (v, ax) => (v >= 0 ? '+' : '') + fx(v, 0) + '%' });
  $('#rent-note').innerHTML = `CPI-U, New York-Newark-Jersey City, not seasonally adjusted (${L(SRC.bls('CUURS12ASEHF01'), 'BLS')}). Each point is the average of the 12 months ending that month, compared with the 2000 average. Rent moves slowly because the index measures leases in force, including rent-stabilized units.`;

  // ---------- nav highlight ----------
  const secs = ['electricity', 'gas', 'oil', 'water', 'rent'].map(id => document.getElementById(id));
  const links = [...document.querySelectorAll('#jump a')];
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) links.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id)); }), { rootMargin: '-40% 0px -55% 0px' });
  secs.forEach(s => io.observe(s));
}

// ---------- overview small multiples ----------
function overview(D) {
  const E = D.elec, G = D.gas, O = D.oil, W = D.water || {}, CPI = D.cpi;
  const ann = o => { const by = {}; Object.entries(o).forEach(([k, v]) => { if (v == null) return; const y = +k.slice(0, 4); (by[y] = by[y] || []).push(v); }); return by; };
  const yearly = (o, need = 12) => Object.fromEntries(Object.entries(ann(o)).filter(([y, a]) => a.length >= need).map(([y, a]) => [y, a.reduce((p, c) => p + c) / a.length]));
  // Electricity: 12-month average at each December, plus the latest month (sales-weighted t12 from build.py).
  const decs = (o, last) => { const out = {}; Object.keys(o).sort().forEach(k => { if (k.endsWith('-12') || k === last) out[k] = o[k]; }); return out; };
  const LM = E.latest.month;
  const oilM = monthlyFromWeekly(O.weekly.dates, O.weekly.new_york_city_average_gal), oilS = monthlyFromWeekly(O.weekly.dates, O.weekly.new_york_statewide_average);
  const usOil = monthlyFromWeekly(O.us_weekly.dates, O.us_weekly.v);
  // Heating-season (Oct-Mar) averages, labelled by the year the season ends, so all three series cover the same weeks.
  const season = o => { const out = {}; Object.entries(o).forEach(([k, v]) => { const { y, m } = ym(k); if (m >= 10 || m <= 3) { const s = m >= 10 ? y + 1 : y; (out[s] = out[s] || []).push(v); } }); return Object.fromEntries(Object.entries(out).filter(([s, a]) => a.length >= 5).map(([s, a]) => [s, a.reduce((p, c) => p + c) / a.length])); };
  const wr = (W.rates || []).filter(r => r.combined_per_hcf != null || (r.water_per_hcf != null && r.sewer_per_hcf != null));
  const wcomb = Object.fromEntries(wr.map(r => [r.fy, r.combined_per_hcf ?? (r.sewer_per_hcf != null ? r.water_per_hcf + r.sewer_per_hcf : null)]).filter(x => x[1] != null));
  const usW = yearlyFY(CPI.us_water);
  const panels = [
    { id: 'Electricity', what: `Average residential price, cents per kWh, 12 months to each December${LM.endsWith('-12') ? '' : ' and ' + monthName(LM)}`,
      nyc: decs(E.coned.t12, LM), nys: decs(E.other.t12, LM), usa: decs(E.us.t12, LM), unit: v => fx(v, 1) + '¢', base: '2016-12',
      cap: 'NYC: Con Edison. State: the other New York utilities, outside the city. U.S.: all customers.', link: SRC.e861 },
    { id: 'Gas heat', what: 'Average residential price, dollars per therm, by calendar year',
      nyc: keyY(yearly(G.bls_therm.nyc)), nys: keyY(scaleO(yearly(G.eia.ny), 1 / 10.36)), usa: keyY(scaleO(yearly(G.eia.us), 1 / 10.36)), unit: v => '$' + fx(v, 2), base: '2016',
      cap: 'NYC: BLS metro price, ends 2024. State (includes the city) and U.S.: EIA.', link: SRC.gasny },
    { id: 'Heating oil', what: 'Residential No. 2 oil, dollars per gallon, heating-season average (Oct.–March)',
      nyc: keyY(season(oilM)), nys: keyY(season(oilS)), usa: keyY(season(usOil)), unit: v => '$' + fx(v, 2), base: '2016',
      cap: 'NYC and state: NYSERDA. U.S.: EIA. Season labelled by the year it ends.', link: SRC.nyserda },
    { id: 'Water and sewer', what: wr.length ? 'Combined water and sewer rate per 100 cubic feet, by fiscal year' : 'NYC Water Board rates',
      nyc: keyY(wcomb), nys: null, usa: wr.length ? keyY(usW) : null, unit: v => '$' + fx(v, 2), base: '2016', usaIndexOnly: true,
      cap: 'NYC: Water Board rate schedules. U.S.: BLS water and sewerage index (no national dollar rate exists). No statewide series.', link: 'https://www.nyc.gov/site/nycwaterboard/rates/rates.page' }
  ];
  let mode = 'index';
  const box = $('#sm');
  const draw = () => {
    box.innerHTML = panels.map((p, i) => `<div><h3>${p.id}</h3><p class="what">${mode === 'index' ? 'Change since 2016, %' : p.what}</p><div class="chart" id="sm${i}"></div><p class="chg" id="smc${i}"></p></div>`).join('');
    panels.forEach((p, i) => {
      const el = document.getElementById('sm' + i);
      const S = [['usa', C.usa], ['nys', C.nys], ['nyc', C.nyc]].filter(([k]) => p[k] && Object.keys(p[k]).length);
      if (!S.length) { el.innerHTML = `<p class="note">Rates are being compiled.</p>`; return; }
      const series = S.map(([k, col]) => {
        let o = p[k];
        if (mode === 'index' || (k === 'usa' && p.usaIndexOnly)) { const b = o[p.base] ?? o[p.base + '-12'];
          if (b == null) return null; o = Object.fromEntries(Object.entries(o).map(([kk, v]) => [kk, (v / b - 1) * 100])); }
        if (mode === 'level' && k === 'usa' && p.usaIndexOnly) return null;
        return { label: k === 'nyc' ? 'New York City' : k === 'nys' ? 'New York State' : 'United States', color: col, width: k === 'nyc' ? 2.5 : 1.8,
          data: Object.keys(o).sort().filter(kk => kk >= '2010').map(kk => [kk.length === 4 ? +kk + 0.5 : toT(kk), o[kk], kk]), gap: 1.6, snap: 0.6 };
      }).filter(Boolean);
      lineChart(el, { series, h: 190, zero: mode !== 'index', xMin: 2010, lPad: 40,
        fmt: mode === 'index' ? (v => (v >= 0 ? '+' : '') + fx(v, 0) + '%') : ((v, ax) => ax ? (p.id === 'Electricity' ? fx(v, 0) + '¢' : '$' + fx(v, v < 10 ? 2 : 0)) : p.unit(v)),
        when: k => k.length === 4 ? (p.id === 'Heating oil' ? `Winter ${+k - 1}–${k.slice(2)}` : p.id === 'Water and sewer' ? `Fiscal year ${k}` : k) : shortM(k), aria: p.id });
      // change line under each panel
      const last = o => { const ks = Object.keys(o).sort(); return [ks[ks.length - 1], o[ks[ks.length - 1]]]; };
      const at = (o, b) => o[b] ?? o[b + '-12'];
      const endK = p.nyc && Object.keys(p.nyc).length ? last(p.nyc)[0] : null;
      const ch = S.map(([k]) => { const o = p[k], lk = endK && o[endK] != null ? endK : last(o)[0], lv = o[lk], bv = at(o, p.base); if (bv == null || (endK && lk !== endK)) return '';
        const nm = k === 'nyc' ? 'New York City' : k === 'nys' ? 'New York State' : 'U.S.';
        return `${nm} <b>${chgShort(pct(lv, bv), 0)}</b>`; }).filter(Boolean).reverse();
      const lastNyc = p.nyc && Object.keys(p.nyc).length ? last(p.nyc)[0] : null;
      document.getElementById('smc' + i).innerHTML = lastNyc ? `${p.base.slice(0, 4)} to ${lastNyc.length === 4 ? (p.id === 'Water and sewer' ? 'fiscal ' + lastNyc : p.id === 'Heating oil' ? 'winter ' + (lastNyc - 1) + '–' + lastNyc.slice(2) : lastNyc) : monthName(lastNyc)}: ${ch.join(', ')}. <span style="color:var(--fg2)">${p.cap} ${L(SRC.m('overview'), 'Method')}.</span>` : '';
    });
  };
  draw();
  toggle('[data-ov]', 'ov', v => { mode = v; draw(); });
  $('#smnote').innerHTML = `Each panel compares like with like inside it, but the four panels use different sources and periods, set out under each. The national water line is a price index, so it appears only as change.`;
}

// ---------- Con Edison research (rate cases, taxes) ----------
function planStarts(R) {
  // One marker per Con Edison electric rate plan: a new plan starts when the case number
  // changes or, for older plans without one in the file, when a year is skipped.
  const rows = (R.rate_cases || []).filter(c => c.utility === 'CECONY' && c.service === 'electric' && c.effective)
    .sort((a, b) => a.effective.localeCompare(b.effective));
  const out = []; let prev = null;
  rows.forEach(c => { const y = +c.effective.slice(0, 4);
    if (!prev || (c.case || '') !== (prev.case || '') || (!c.case && y - +prev.effective.slice(0, 4) > 1)) out.push({ c, y, n: 0 });
    out[out.length - 1].n++; out[out.length - 1].last = y; prev = c; });
  return out.map((p, i) => ({ t: toT(p.c.effective.slice(0, 7)), label: `Rate plan ${p.y}–${String(p.last).slice(2)}`, row: i % 2 }));
}
function dateTxt(d) { return d.length === 4 ? d : d.length === 7 ? monthName(d) : apDate(d); }
function conedResearch(R) {
  const box = $('#coned-research');
  if (!R || !Object.keys(R).length) { box.innerHTML = ''; return; }
  const T = R.taxes || [], N = R.nyc_side || [];
  const series = (arr, item, key) => arr.filter(t => t.item === item && t.amount_musd != null).sort((a, b) => (a[key]) - (b[key]));
  const prop = series(T, 'CECONY property taxes', 'year'), oth = series(T, 'CECONY taxes other than income taxes (total)', 'year');
  const c3 = series(N, 'Class 3 levy', 'fy'), ut = series(N, 'utility tax revenue', 'fy');
  const share = k => T.find(t => t.item === k);
  const at = (a, key, v) => a.find(x => x[key] === v), lastOf = a => a[a.length - 1];
  const B = (x, d = 2) => '$' + fx(x.amount_musd / 1000, d) + ' billion', M = x => '$' + fx(x.amount_musd, 0) + ' million';
  let h = '';
  if (prop.length && c3.length) {
    const p15 = at(prop, 'year', 2015), pl = lastOf(prop), c15 = at(c3, 'fy', 2015), cl = lastOf(c3), u15 = at(ut, 'fy', 2015), ul = lastOf(ut);
    h += `<div class="split"><div><h3>Taxes inside the bill</h3><p class="aside">No official source reports how much of Con Edison’s property tax goes to New York City alone. The two nearest official figures: Con Edison of New York reported property taxes of ${L(p15.url, B(p15))} in 2015 and ${L(pl.url, B(pl))} in ${pl.year}, across every place it owns property (annual reports to the SEC). The city’s property tax levy on Class 3, the equipment of all regulated utilities, was ${L(c15.url, B(c15))} in fiscal 2015 and ${L(cl.url, B(cl))} in fiscal ${cl.fy}${u15 && ul ? `. The city’s separate utility tax, 2.35% of utilities’ gross income, brought in ${L(u15.url, M(u15))} in fiscal 2015 and ${L(ul.url, M(ul))} in fiscal ${ul.fy}` : ''}.</p>
      <div class="figcap"><span><b>Billions of dollars a year</b></span><span><span class="key"><i class="k-nyc"></i>Con Edison property taxes, all places (calendar year)</span><span class="key"><i class="k-sun"></i>City levy on utility property, all utilities (fiscal year)</span><span class="key"><i class="k-cyan"></i>City utility tax (fiscal year)</span></span></div>
      <div class="chart" id="c-tax"></div></div><div><h3>How the taxes reach rates</h3><p class="aside">Taxes are a cost the Public Service Commission lets the utility recover through delivery rates. What the commission and the company say about them:</p><div class="why" id="taxwhy"></div></div></div>`;
  }
  const cases = (R.rate_cases || []).filter(c => c.delivery_increase_musd != null || c.bill_impact);
  if (cases.length) h += `<div style="margin-top:38px"><h3>Rate cases</h3><p class="aside">Delivery rates for Con Edison and National Grid are set by the Public Service Commission in multiyear rate plans. Each row is one approved step, in the agency’s or the company’s own figures. Bill effects are as stated in the source, for the typical customer it describes.</p><div class="tablewrap"><table class="h" id="cases"></table></div><p><button class="chip" id="cases-more"></button></p></div>`;
  const ev = (R.events || []).filter(e => e.date);
  if (ev.length) h += `<div style="margin-top:38px"><h3>Dated events</h3><p class="aside">Rate orders, plant closings, new lines and bill-relief actions that bear on city electricity and gas prices.</p><div class="why" id="events"></div></div>`;
  box.innerHTML = h;

  if (prop.length && c3.length) {
    const toS = (a, key, label, color) => ({ label, color, width: 2.5, gap: 1.6, snap: 0.6, data: a.map(t => [t[key] + (key === 'fy' ? 0 : 0.5), t.amount_musd / 1000, (key === 'fy' ? 'Fiscal ' : '') + t[key]]) });
    lineChart($('#c-tax'), { zero: true, h: 250, xMin: 2010, when: k => String(k), aria: 'Utility property taxes',
      series: [toS(ut, 'fy', 'City utility tax', C.cyan), toS(c3, 'fy', 'City Class 3 levy', C.sun), toS(prop, 'year', 'Con Edison property taxes', C.nyc)],
      fmt: (v, ax) => '$' + fx(v, ax ? 1 : 2) + (ax ? '' : 'B') });
    const rows = [];
    const s20 = share('property taxes as share of 2020-2022 increase'), s23 = share('property taxes as share of 2023-2025 increase'),
      s26 = share('property taxes as share of 2026-2028 electric increase'), s26p = share('property taxes as share of 2026-2028 electric increase (pct)'),
      s26g = share('property taxes as share of 2026-2028 gas increase (pct)'), mech = share('property tax recovery mechanism (2026-2028 plan)'), grt = share('how GRT is treated');
    if (s20) rows.push(['2020–22 plan', `Higher property taxes were more than 40% of the increased cost the commission allowed over the three years. ${L(s20.url, 'Source')}`]);
    if (s23) rows.push(['2023–25 plan', `Higher property taxes were more than 30% of the increased cost over the three years. ${L(s23.url, 'Source')}`]);
    if (s26p) rows.push(['2026–28 plan', `Property taxes are about 26% of the electric revenue increase${s26 ? ` (${L(s26.url, '$' + fx(s26.amount_musd, 1) + ' million')} of $1.024 billion over three years)` : ''}${s26g ? ` and about 22% of the gas increase` : ''}. ${L(s26p.url, 'Source')}`]);
    if (mech) rows.push(['Since 2026', `If actual property taxes differ from the amount built into rates, the full difference is charged or credited to customers through a surcharge or credit. ${L(mech.url, 'Source')}`]);
    if (grt) rows.push(['Revenue taxes', `Gross receipts and other revenue taxes are generally recovered in the revenue requirement of each approved rate plan. ${L(grt.url, 'Source')}`]);
    $('#taxwhy').innerHTML = rows.map(r => `<div class="fy" style="font-size:15px">${r[0]}</div><div><p>${r[1]}</p></div>`).join('');
  }
  if (cases.length) {
    const UN = { CECONY: 'Con Edison', 'KEDNY (Brooklyn Union Gas)': 'National Grid (Brooklyn Union)', 'KEDLI (KeySpan Gas East)': 'National Grid (KeySpan Gas East)' };
    cases.sort((a, b) => (b.effective || '').localeCompare(a.effective || '') || a.utility.localeCompare(b.utility));
    let showAll = false;
    const drawCases = () => {
    const vis = showAll ? cases : cases.filter(c => (c.effective || '') >= '2023');
    $('#cases').innerHTML = `<thead><tr><th>Takes effect</th><th>Utility</th><th>Service</th><th>Case and order</th><th class="r">Delivery revenue increase</th><th>Bill effect as stated</th></tr></thead><tbody>` +
      vis.map(c => `<tr><td>${c.effective ? dateTxt(c.effective.endsWith('-01') && c.effective.slice(5, 7) === '01' ? c.effective.slice(0, 4) : c.effective.slice(0, 7)) : c.rate_year}</td><td>${UN[c.utility] || c.utility}</td><td>${c.service}</td><td>${c.case ? c.case.replace(/ \(.*\)/, '') : '<span style="color:var(--fg2)">From annual report</span>'}${c.order_date ? `<br><small style="color:var(--fg2)">Order ${apDate(c.order_date)}</small>` : ''}</td><td class="r">${c.delivery_increase_musd != null ? L(c.url, '$' + fx(c.delivery_increase_musd, 1).replace(/\.0$/, '') + 'M') : '–'}${c.pct ? `<br><small style="color:var(--fg2)">${c.pct}</small>` : ''}</td><td><small>${c.bill_impact || ''}</small></td></tr>`).join('') + '</tbody>';
    $('#cases-more').textContent = showAll ? 'Show 2023 on only' : `Show all ${cases.length} steps back to 2010`;
    };
    drawCases();
    $('#cases-more').addEventListener('click', () => { showAll = !showAll; drawCases(); });
  }
  if (ev.length) {
    ev.sort((a, b) => a.date.localeCompare(b.date));
    $('#events').innerHTML = ev.map(e => `<div class="fy">${e.date.slice(0, 4)}<small>${e.date.length > 4 ? dateTxt(e.date).replace(/, \d{4}$/, '').replace(/ \d{4}$/, '') : ''}</small></div><div><p>${e.event} ${L(e.url, 'Source')}</p></div>`).join('');
  }
}

// ---------- water ----------
function water(D) {
  const W = D.water || {}, CPI = D.cpi;
  const rates = (W.rates || []).filter(r => r.fy).sort((a, b) => a.fy - b.fy);
  if (!rates.length) { $('#w-intro').innerHTML = 'The rate history is being compiled from NYC Water Board schedules.'; return; }
  const comb = r => r.combined_per_hcf ?? (r.water_per_hcf != null && r.sewer_per_hcf != null ? r.water_per_hcf + r.sewer_per_hcf : null);
  const withC = rates.filter(r => comb(r) != null), last = withC[withC.length - 1], first = withC[0];
  const b16 = withC.find(r => r.fy === 2016);
  const usFY = yearlyFY(CPI.us_water), allFY = yearlyFY(CPI.nyc_all);
  const lastInc = rates.filter(r => r.increase_pct != null).slice(-1)[0];
  const bills = (W.typical_bills || []).filter(b => b.single_family != null).sort((a, b) => a.fy - b.fy);
  const lb = bills[bills.length - 1];
  $('#w-intro').innerHTML = `The NYC Water Board sets one citywide rate, billed by the Department of Environmental Protection on metered use; sewer charges are a fixed share of the water charge. The combined rate was ${L(last.url, usd(comb(last)) + ' per 100 cubic feet')} (748 gallons) in fiscal year ${last.fy}, against ${L(first.url, usd(comb(first)))} in fiscal ${first.fy}` +
    (b16 && last.fy > 2016 ? `, and ${L(SRC.m('water'), chgShort(pct(comb(last), comb(b16)), 0))} from fiscal 2016` : '') +
    (lastInc ? `. The fiscal ${lastInc.fy} increase was ${L(lastInc.increase_url || lastInc.url, fx(lastInc.increase_pct, 1) + '%')}${lastInc.adopted_date ? `, adopted ${apDate(lastInc.adopted_date)}` : ''}` : '') +
    (lb ? `. The board’s typical single-family bill for fiscal ${lb.fy} was ${L(lb.url, usd(lb.single_family, 0) + ' a year')}${lb.multifamily_unit != null ? `, and ${L(lb.url, usd(lb.multifamily_unit, 0))} for a typical apartment in a multifamily building` : ''}` : '') + '.';

  let h = `<div class="split"><div><div class="figcap"><span><b>Annual rate increase, % (bars) and combined rate per 100 cubic feet (line)</b></span></div><div class="chart" id="c-water"></div><p class="note">Fiscal years run July 1 to June 30. Source: NYC Water Board rate schedules and rate reports; each year links in the table below.</p></div>` +
    `<div><div class="figcap"><span><b>Change since fiscal 2016</b></span><span><span class="key"><i class="k-nyc"></i>NYC water and sewer rate</span><span class="key"><i class="k-usa"></i>U.S. water and sewerage price index</span><span class="key"><i class="k-mint"></i>NYC-area all items</span></span></div><div class="chart" id="c-water2"></div><p class="note">The national comparison is BLS’s CPI for water and sewerage maintenance, averaged over the same July–June fiscal years (${L(SRC.bls('CUUR0000SEHG01'), 'BLS')}). BLS publishes no water index for the New York area and no statewide rate series exists.</p></div></div>`;
  const NOTE_FY = [2017, 2018, 2021];
  const byFY = {}; (W.reasons || []).filter(r => r.reason).forEach(r => (byFY[r.fy] = byFY[r.fy] || []).push(r));
  const fysR = Object.keys(byFY).map(Number).sort((a, b) => b - a);
  if (fysR.length) h += `<div style="margin-top:36px"><h3>Why rates went up, as the board explained it</h3><p class="aside">The reasons the Water Board and DEP gave in each year’s rate documents, summarized, each with a link to the document. Where a year has two lines, they come from two documents.</p><div class="why">${fysR.map(fy => { const rt = rates.find(x => x.fy === fy);
    return `<div class="fy">FY${fy}<small>${rt && rt.increase_pct != null ? fx(rt.increase_pct, 1) + '%' : ''}</small></div><div>${byFY[fy].map(r => `<p>${r.reason} ${L(r.url, 'Source')}</p>`).join('')}</div>`; }).join('')}</div></div>`;
  const rent = (W.rental_payment || []).filter(r => r.amount_musd != null).sort((a, b) => a.fy - b.fy);
  const bills2 = (W.typical_bills || []).slice().sort((a, b) => b.fy - a.fy);
  if (rent.length || bills2.length) {
    h += `<div class="split" style="margin-top:36px">`;
    if (rent.length) { const rmx = Math.max(...rent.map(r => r.amount_musd));
      const zeros = rent.filter(r => r.amount_musd === 0).map(r => r.fy);
      h += `<div><h3>The rental payment to the city</h3><p class="aside">The Water Board leases the water and sewer system from the City of New York, and the city can ask for rent each year, which rates must cover. Millions of dollars a year, from the system’s audited financial statements${rent.some(r => /budget/i.test(r.note || '')) ? '; the latest year is the budgeted amount' : ''}. ${zeros.length ? 'No payment was taken in fiscal ' + listJoin(zeros.map(String)) + '.' : ''}</p><div class="rank" style="grid-template-columns:4.5rem minmax(0,1fr) 4.6rem">${rent.slice().reverse().map(r => `<span class="n">FY${r.fy}</span><span><i class="b ${/budget/i.test(r.note || '') ? 'east' : 'ny'}" style="width:${(r.amount_musd / rmx * 100).toFixed(1)}%"></i></span><span class="v">${L(r.url, '$' + fx(r.amount_musd, 0) + 'M')}</span>`).join('')}</div></div>`; }
    if (bills2.length) h += `<div><h3>The board’s typical bills</h3><p class="aside">Annual water and sewer charges for the board’s model customers. The assumed water use changed over time, so years on different bases are not comparable.</p><div class="tablewrap"><table class="h"><thead><tr><th>Fiscal year</th><th class="r">Single-family home</th><th class="r">Apartment in a multifamily building</th><th>Assumed use</th></tr></thead><tbody>${bills2.map(b => `<tr><td>${b.fy}</td><td class="r">${b.single_family != null ? L(b.url, usd(b.single_family, 0)) : '–'}</td><td class="r">${b.multifamily_unit != null ? L(b.url, usd(b.multifamily_unit, 0)) : '–'}</td><td><small>${(b.basis || '').replace('SF ', 'house ').replace('MF unit ', 'apartment ').replace(' gal/yr', ' gallons a year').replace(' gal/yr', ' gallons a year')}</small></td></tr>`).join('')}</tbody></table></div></div>`;
    h += `</div>`;
  }
  h += `<div style="margin-top:32px"><h3>Rate schedule by fiscal year</h3><div class="tablewrap"><table class="h"><thead><tr><th>Fiscal year</th><th class="r">Water</th><th class="r">Sewer</th><th class="r">Combined</th><th class="r">Increase</th><th>Adopted</th></tr></thead><tbody>${rates.slice().reverse().map(r => `<tr><td>${r.fy}</td><td class="r">${r.water_per_hcf != null ? usd(r.water_per_hcf) : '–'}</td><td class="r">${r.sewer_per_hcf != null ? usd(r.sewer_per_hcf) : '–'}</td><td class="r">${comb(r) != null ? L(r.url, usd(comb(r))) : '–'}</td><td class="r">${r.increase_pct != null ? L(r.increase_url || r.url, fx(r.increase_pct, 1) + '%') : '–'}</td><td>${r.adopted_date ? apDate(r.adopted_date) : ''}${NOTE_FY.includes(r.fy) && r.note ? `<br><small style="color:var(--fg2)">${r.note}</small>` : ''}</td></tr>`).join('')}</tbody></table></div>` +
    `<p class="note">Per 100 cubic feet (748 gallons) of metered use. Water rates from FY1997 come from rate schedules and the system’s audited financial statements; the sewer charge has been 159% of the water charge throughout, and the sewer and combined figures here are calculated that way. Increases for FY1988–FY1996 are read from a Water Board chart.</p></div>` + ((W.assistance || []).length ? `<div style="margin-top:28px"><h3>Help with water bills</h3><div class="why">${W.assistance.filter(a => !/origin/i.test(a.program)).map(a => `<div class="fy" style="font-size:15px">${a.program.replace(/ \(.*\)/, '')}</div><div><p>${a.summary} ${L(a.url, 'Source')}</p></div>`).join('')}</div></div>` : '');
  $('#water-body').innerHTML = h;

  // bars + line
  const inc = rates.filter(r => r.increase_pct != null);
  const wbox = $('#c-water');
  const wdraw = () => {
    const w = wbox.clientWidth || 600, hh = w < 560 ? 220 : 280, m = { l: 36, r: 46, t: 12, b: 26 };
    const fys = rates.map(r => r.fy), f0 = Math.min(...fys), f1 = Math.max(...fys);
    const X = f => m.l + (f - f0 + 0.5) / (f1 - f0 + 1) * (w - m.l - m.r), bw = (w - m.l - m.r) / (f1 - f0 + 1) * 0.7;
    const imax = Math.max(...inc.map(r => r.increase_pct), 1), imin = Math.min(0, ...inc.map(r => r.increase_pct));
    const it = niceTicks(imin, imax, 4), Y = v => m.t + (1 - (v - it[0]) / (it[it.length - 1] - it[0])) * (hh - m.t - m.b);
    const cmax = Math.max(...withC.map(comb)), ct = niceTicks(0, cmax, 4), Y2 = v => m.t + (1 - v / ct[ct.length - 1]) * (hh - m.t - m.b);
    let s = `<svg viewBox="0 0 ${w} ${hh}" height="${hh}">`;
    it.forEach(v => s += `<line x1="${m.l}" x2="${w - m.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`);
    ct.forEach(v => s += `<text x="${w - m.r + 6}" y="${Y2(v) + 4}">$${v}</text>`);
    inc.forEach(r => s += `<rect x="${X(r.fy) - bw / 2}" y="${Math.min(Y(r.increase_pct), Y(0))}" width="${bw}" height="${Math.abs(Y(r.increase_pct) - Y(0))}" fill="${C.cyan}"><title>FY${r.fy}: ${fx(r.increase_pct, 1)}%</title></rect>`);
    s += `<path d="${withC.map((r, i) => `${i ? 'L' : 'M'}${X(r.fy)},${Y2(comb(r))}`).join('')}" fill="none" stroke="${C.nyc}" stroke-width="2.5"/>`;
    withC.forEach(r => s += `<circle cx="${X(r.fy)}" cy="${Y2(comb(r))}" r="2.5" fill="${C.nyc}"><title>FY${r.fy}: $${fx(comb(r), 2)} per 100 cu. ft.</title></circle>`);
    const every = (f1 - f0) > 24 ? 5 : (f1 - f0) > 10 ? 2 : 1;
    for (let f = f0; f <= f1; f++) if (f % every === 0) s += `<text x="${X(f)}" y="${hh - 6}" text-anchor="middle">${f}</text>`;
    wbox.innerHTML = s + '</svg>';
  };
  wdraw(); charts.push(wdraw);
  if (b16) {
    const idxW = Object.fromEntries(withC.filter(r => r.fy >= 2016).map(r => [String(r.fy), (comb(r) / comb(b16) - 1) * 100]));
    const idxO = o => { const b = o['2016']; return b ? Object.fromEntries(Object.entries(o).filter(([k]) => +k >= 2016).map(([k, v]) => [k, (v / b - 1) * 100])) : {}; };
    const toP = o => Object.keys(o).sort().map(k => [+k, o[k], k]);
    lineChart($('#c-water2'), { h: 240, zero: true, xMin: 2016, when: k => 'Fiscal year ' + k, aria: 'Water rate change since 2016',
      series: [{ label: 'NYC-area all items', color: C.mint, data: toP(idxO(allFY)), gap: 1.5, snap: 0.5 },
               { label: 'U.S. water and sewerage', color: C.usa, data: toP(idxO(usFY)), gap: 1.5, snap: 0.5 },
               { label: 'NYC water and sewer rate', color: C.nyc, data: toP(idxW), width: 3, gap: 1.5, snap: 0.5 }],
      fmt: v => (v >= 0 ? '+' : '') + fx(v, 0) + '%' });
  }
}

// ---------- helpers ----------
function yearlyFY(o) { // July-June fiscal-year averages, labelled by the year the fiscal year ends
  const by = {}; Object.entries(o).forEach(([k, v]) => { const { y, m } = ym(k); const fy = m >= 7 ? y + 1 : y; (by[fy] = by[fy] || []).push(v); });
  return Object.fromEntries(Object.entries(by).filter(([f, a]) => a.length === 12).map(([f, a]) => [f, a.reduce((p, c) => p + c) / 12]));
}
function monthlyFromWeekly(dates, vals) { const by = {}; dates.forEach((d, i) => { if (vals[i] == null) return; const k = d.slice(0, 7); (by[k] = by[k] || []).push(vals[i]); });
  return Object.fromEntries(Object.entries(by).map(([k, a]) => [k, a.reduce((p, c) => p + c) / a.length])); }
function avgYear(o, y) { const v = []; for (let m = 1; m <= 12; m++) { const x = o[`${y}-${String(m).padStart(2, '0')}`]; if (x != null) v.push(x); } return v.length === 12 ? v.reduce((a, b) => a + b) / 12 : null; }
function keyY(o) { return Object.fromEntries(Object.entries(o).map(([k, v]) => [String(k), v])); }
function scaleO(o, f) { return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v * f])); }
function dt(d) { const [y, m, dd] = d.split('-').map(Number); return y + (m - 1) / 12 + (dd - 1) / 365; }
function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
function listJoin(a) { return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }
function shortName(n) {
  const map = { 'Consolidated Edison Co-NY Inc': 'Con Edison', 'San Diego Gas & Electric Co': 'San Diego Gas & Electric', 'Hawaiian Electric Co Inc': 'Hawaiian Electric (Oahu)',
    'Hawaii Electric Light Co Inc': 'Hawaii Electric Light', 'Maui Electric Co Ltd': 'Maui Electric', 'Pacific Gas & Electric Co.': 'Pacific Gas & Electric',
    'Long Island Power Authority': 'PSEG Long Island (LIPA)', 'Niagara Mohawk Power Corp.': 'National Grid upstate', 'New York State Elec & Gas Corp': 'NYSEG',
    'Rochester Gas & Electric Corp': 'RG&E', 'Central Hudson Gas & Elec Corp': 'Central Hudson', 'Orange & Rockland Utils Inc': 'Orange & Rockland',
    'Public Service Elec & Gas Co': 'PSE&G', 'Los Angeles Department of Water & Power': 'Los Angeles DWP' };
  return map[n] || n.replace(/ (Co|Corp|Inc|LLC|Company|Ltd)\.?$/i, '').replace(/,$/, '');
}
function mix(a, b, t) {
  const p = h => { h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
  const A = p(a), B = p(b); t = Math.max(0, Math.min(1, t));
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
}
})();
