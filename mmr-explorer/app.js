/* ===========================================================================
   Report card — Mayor's Management Report
   No framework, no chart library. Everything the page draws is an inline SVG
   built from the city's published figures.
   ======================================================================== */
'use strict';

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const el = (t, cls, txt) => { const n = document.createElement(t); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SVGNS = 'http://www.w3.org/2000/svg';
const svgEl = (t, attrs) => { const n = document.createElementNS(SVGNS, t); for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]); return n; };

/* --- state ------------------------------------------------------------- */
const D = { loaded: false };
const state = {
  view: 'board',
  flat: 0.01,          // |relative change| under this reads as no material change
  criticalOnly: false,
  fromYear: null,      // comparison baseline, set anywhere on the site
  toYear: null,        // the year being compared TO, latest by default
  agency: null,
  q: '',
  filters: { agency: '', dir: '', mt: '', live: 'live', critical: '' },
  measure: 'g1',
  extreme: 'best',
  hideLowBase: true,
};

/* --- formatting -------------------------------------------------------- */
const MT_NUMBER = 0, MT_PCT = 1, MT_CUR = 2, MT_TIME = 3;
/* The dataset's own words for units are internal jargon. These are the same
   categories in plain English; the raw value is never altered. */
const MT_WORD = { Number: 'Count', Percentage: 'Percentage', Currency: 'Dollars', TimeSpan: 'Elapsed time', Ratio: 'Ratio' };
const mtWord = i => (i >= 0 && D.mt[i]) ? (MT_WORD[D.mt[i]] || D.mt[i]) : 'Not stated';


function fmtNum(v) {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(a >= 1e10 ? 0 : 1) + 'bn';
  if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + 'm';
  if (a >= 1000) return Math.round(v).toLocaleString('en-US');
  if (a >= 100) return (Math.round(v * 10) / 10).toLocaleString('en-US');
  if (a >= 1) return (Math.round(v * 100) / 100).toLocaleString('en-US');
  if (a === 0) return '0';
  return (Math.round(v * 1000) / 1000).toLocaleString('en-US');
}
function fmtTime(v) {
  if (v == null) return '—';
  const neg = v < 0; v = Math.abs(v);
  const whole = Math.floor(v);
  const sub = Math.round((v - whole) * 60);
  return (neg ? '-' : '') + whole + ':' + String(sub === 60 ? 0 : sub).padStart(2, '0');
}
/* `rec` carries how this indicator's time figures are written: `ts` is 1 for a
   clock reading like 9:42 and 0 for a plain decimal like 74 minutes. */
function fmtVal(v, mt, rec) {
  if (v == null) return '—';
  if (mt === MT_TIME) {
    if (rec && rec.ts) return fmtTime(v);
    const u = rec && rec.tu ? ' ' + rec.tu : '';
    return fmtNum(v) + u;
  }
  if (mt === MT_PCT) return (Math.round(v * 10) / 10).toLocaleString('en-US') + '%';
  if (mt === MT_CUR) return '$' + fmtNum(v);
  return fmtNum(v);
}
function fmtPct(r, digits) {
  if (r == null) return '—';
  const p = r * 100;
  const d = digits != null ? digits : (Math.abs(p) >= 100 ? 0 : Math.abs(p) >= 10 ? 0 : 1);
  return (p > 0 ? '+' : '') + p.toFixed(d) + '%';
}
function fmtPoints(v, mt, rec) {
  if (v == null) return '—';
  const s = v > 0 ? '+' : '';
  if (mt === MT_TIME) return s + (rec && rec.ts ? fmtTime(v) : fmtNum(v) + (rec && rec.tu ? ' ' + rec.tu : ''));
  if (mt === MT_PCT) return s + (Math.round(v * 10) / 10) + ' pts';
  if (mt === MT_CUR) return (v < 0 ? '-$' : '+$') + fmtNum(Math.abs(v));
  return s + fmtNum(v);
}

/* verdict: +1 moved the city's way, -1 against it, 0 no material change,
   null when the city publishes no desired direction or a year is missing */
function verdictOf(r) {
  const st = r.st;
  if (!st || st.g1 == null) return null;
  if (Math.abs(st.g1) < state.flat) return 0;
  return st.g1 > 0 ? 1 : -1;
}
const VCLASS = { '1': 'g', '-1': 'b', '0': 'f' };
const VWORD = { '1': 'improved', '-1': 'worsened', '0': 'flat' };

/* --- small charts ------------------------------------------------------ */
function sparkline(vals, opts) {
  opts = opts || {};
  const w = opts.w || 100, h = opts.h || 26, pad = 3;
  const svg = svgEl('svg', { class: 'spark', viewBox: `0 0 ${w} ${h}`, width: w, height: h, 'aria-hidden': 'true' });
  const pts = [];
  vals.forEach((v, i) => { if (v != null) pts.push([i, v]); });
  if (pts.length < 2) return svg;
  const xs = vals.length - 1;
  let lo = Infinity, hi = -Infinity;
  pts.forEach(p => { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]); });
  const span = hi - lo || Math.abs(hi) || 1;
  const X = i => pad + (i / xs) * (w - pad * 2);
  const Y = v => h - pad - ((v - lo) / span) * (h - pad * 2);
  const d = pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ');
  svg.appendChild(svgEl('path', { class: 'ln ' + (opts.cls || ''), d }));
  const last = pts[pts.length - 1];
  const dot = svgEl('circle', { class: 'dot', cx: X(last[0]).toFixed(1), cy: Y(last[1]).toFixed(1), r: 2.4 });
  dot.style.fill = 'currentColor';
  svg.appendChild(dot);
  svg.style.color = opts.cls === 'g' ? 'var(--good)' : opts.cls === 'b' ? 'var(--bad)' : 'var(--ink3)';
  return svg;
}

/* A full year-by-year line, with a readout that follows the pointer. */
function lineChart(rec, opts) {
  opts = opts || {};
  const years = D.years, vals = rec.v, mt = rec.mt;
  const W = 680, H = opts.h || 250, L = 62, R = 16, T = 18, B = 34;
  const svg = svgEl('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img' });
  const pts = [];
  vals.forEach((v, i) => { if (v != null) pts.push([i, v]); });
  if (!pts.length) { svg.appendChild(svgEl('text', { class: 'tick', x: L, y: H / 2 })).textContent = 'No full-year figures published'; return svg; }
  let lo = Math.min(...pts.map(p => p[1])), hi = Math.max(...pts.map(p => p[1]));
  if (lo === hi) { lo -= Math.abs(lo) * 0.1 + 1; hi += Math.abs(hi) * 0.1 + 1; }
  if (lo > 0 && lo < hi * 0.45) lo = 0;            // only zero-base when it is honest to
  const pad = (hi - lo) * 0.08; hi += pad; if (lo !== 0) lo -= pad;
  const X = i => L + (i / (years.length - 1)) * (W - L - R);
  const Y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);

  // gridlines and value axis
  const ticks = niceTicks(lo, hi, 4);
  ticks.forEach(t => {
    svg.appendChild(svgEl('line', { class: 'axis', x1: L, x2: W - R, y1: Y(t).toFixed(1), y2: Y(t).toFixed(1) }));
    const tx = svgEl('text', { class: 'vlabel', x: L - 9, y: (Y(t) + 3.5).toFixed(1), 'text-anchor': 'end' });
    tx.textContent = fmtVal(t, mt, rec); svg.appendChild(tx);
  });
  // year axis
  years.forEach((y, i) => {
    const tx = svgEl('text', { class: 'tick' + (i === years.length - 1 ? ' on' : ''), x: X(i).toFixed(1), y: H - 12, 'text-anchor': 'middle' });
    tx.textContent = String(y).slice(2); svg.appendChild(tx);
  });
  const yl = svgEl('text', { class: 'tick', x: L, y: H - 1, 'text-anchor': 'start' });
  yl.textContent = 'FISCAL YEAR'; svg.appendChild(yl);

  // the line, broken wherever a year was not published
  let run = [];
  const flush = () => {
    if (run.length > 1) svg.appendChild(svgEl('path', { class: 'line', d: run.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ') }));
    run = [];
  };
  vals.forEach((v, i) => { if (v == null) flush(); else run.push([i, v]); });
  flush();

  const flagged = rec.sus || {};
  pts.forEach((p, k) => {
    const yr = years[p[0]];
    const isFlag = flagged[String(yr)];
    const fromPdf = !opts.plain && yr === D.pdfYear;
    svg.appendChild(svgEl('circle', {
      class: 'pt' + (k === pts.length - 1 && !fromPdf ? ' last' : '') + (isFlag ? ' flag' : '') + (fromPdf ? ' pdf' : ''),
      cx: X(p[0]).toFixed(1), cy: Y(p[1]).toFixed(1), r: isFlag ? 5 : 3.9
    }));
  });
  // the target the agency set itself, where the report prints one
  // Explicitly null, not false: `false != null` is true in JavaScript, which
  // once put a phantom "target 0" line on every chart drawn with plain:true.
  const tgt = (!opts.plain && rec.tgt && rec.tgt.t26 != null) ? rec.tgt.t26 : null;
  if (tgt != null && D.pdfYear && tgt >= lo && tgt <= hi) {
    const xi = years.indexOf(D.pdfYear);
    svg.appendChild(svgEl('line', { class: 'tgt', x1: (X(xi) - 12).toFixed(1), x2: (X(xi) + 12).toFixed(1), y1: Y(tgt).toFixed(1), y2: Y(tgt).toFixed(1) }));
    const tl = svgEl('text', { class: 'tgtlbl', x: (X(xi) - 16).toFixed(1), y: (Y(tgt) + 3.5).toFixed(1), 'text-anchor': 'end' });
    tl.textContent = 'target ' + fmtVal(tgt, mt, rec);
    svg.appendChild(tl);
  }

  // pointer readout
  const cursor = svgEl('line', { class: 'cursor', y1: T, y2: H - B, opacity: 0 });
  const read = svgEl('text', { class: 'vlabel', y: T - 4, 'text-anchor': 'middle', opacity: 0 });
  svg.appendChild(cursor); svg.appendChild(read);
  const hit = svgEl('rect', { class: 'hit', x: L, y: T, width: W - L - R, height: H - T - B });
  svg.appendChild(hit);
  const move = e => {
    const box = svg.getBoundingClientRect();
    const cx = (e.touches ? e.touches[0].clientX : e.clientX);
    const rel = ((cx - box.left) / box.width) * W;
    let best = null, bd = 1e9;
    pts.forEach(p => { const d = Math.abs(X(p[0]) - rel); if (d < bd) { bd = d; best = p; } });
    if (!best) return;
    cursor.setAttribute('x1', X(best[0]).toFixed(1)); cursor.setAttribute('x2', X(best[0]).toFixed(1));
    cursor.setAttribute('opacity', 1);
    read.setAttribute('x', Math.max(L + 40, Math.min(W - R - 40, X(best[0]))).toFixed(1));
    read.setAttribute('opacity', 1);
    read.textContent = 'FY' + years[best[0]] + '   ' + fmtVal(best[1], mt, rec);
  };
  const off = () => { cursor.setAttribute('opacity', 0); read.setAttribute('opacity', 0); };
  hit.addEventListener('mousemove', move); hit.addEventListener('mouseleave', off);
  hit.addEventListener('touchstart', move, { passive: true }); hit.addEventListener('touchmove', move, { passive: true });
  return svg;
}

function niceTicks(lo, hi, n) {
  const span = hi - lo;
  if (!(span > 0)) return [lo];
  const raw = span / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || 10 * mag;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(Math.round(t / step) * step);
  return out;
}

/* Year-to-date by fiscal month, one line per fiscal year. */
function paceChart(pace, rec) {
  const order = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6];
  const names = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
  const fys = Object.keys(pace).map(Number).sort();
  const show = fys.slice(-5);
  const W = 680, H = 230, L = 62, R = 74, T = 14, B = 30;
  const svg = svgEl('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img' });
  let lo = Infinity, hi = -Infinity, any = false;
  show.forEach(fy => order.forEach(m => { const v = pace[fy][m]; if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); any = true; } }));
  if (!any) return null;
  if (lo === hi) { hi = lo + 1; }
  if (lo > 0 && lo < hi * 0.45) lo = 0;
  const X = i => L + (i / 11) * (W - L - R);
  const Y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  niceTicks(lo, hi, 4).forEach(t => {
    svg.appendChild(svgEl('line', { class: 'axis', x1: L, x2: W - R, y1: Y(t).toFixed(1), y2: Y(t).toFixed(1) }));
    const tx = svgEl('text', { class: 'vlabel', x: L - 9, y: (Y(t) + 3.5).toFixed(1), 'text-anchor': 'end' });
    tx.textContent = fmtVal(t, rec.mt, rec); svg.appendChild(tx);
  });
  names.forEach((nm, i) => {
    const tx = svgEl('text', { class: 'tick', x: X(i).toFixed(1), y: H - 10, 'text-anchor': 'middle' });
    tx.textContent = nm; svg.appendChild(tx);
  });
  show.forEach((fy, k) => {
    const last = k === show.length - 1;
    const pts = [];
    order.forEach((m, i) => { const v = pace[fy][m]; if (v != null) pts.push([i, v]); });
    if (pts.length < 2) return;
    svg.appendChild(svgEl('path', {
      class: 'line' + (last ? '' : ' dim'),
      d: pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ')
    }));
    const end = pts[pts.length - 1];
    const lab = svgEl('text', { class: 'lbl', x: (X(end[0]) + 7).toFixed(1), y: (Y(end[1]) + 3.5).toFixed(1) });
    lab.textContent = 'FY' + fy;
    if (last) { lab.setAttribute('fill', 'var(--accent)'); }
    svg.appendChild(lab);
  });
  return svg;
}

/* Horizontal bars, used for geographic breakouts and agency resources. */
function barChart(items, opts) {
  opts = opts || {};
  const rowH = 20, W = 680, L = opts.labelW || 210, R = 62, T = 6;
  const H = T * 2 + items.length * rowH;
  const svg = svgEl('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img' });
  const vals = items.map(i => i.v).filter(v => v != null);
  if (!vals.length) return svg;
  const hi = Math.max(...vals, 0), lo = Math.min(...vals, 0);
  const span = (hi - lo) || 1;
  const X = v => L + ((v - lo) / span) * (W - L - R);
  const zero = X(0);
  items.forEach((it, i) => {
    const y = T + i * rowH;
    const lab = svgEl('text', { class: 'lbl', x: L - 9, y: y + rowH / 2 + 3.5, 'text-anchor': 'end' });
    lab.textContent = it.label.length > 34 ? it.label.slice(0, 33) + '…' : it.label;
    svg.appendChild(lab);
    if (it.v == null) return;
    const x = X(it.v);
    svg.appendChild(svgEl('rect', {
      class: 'bar ' + (it.cls || 'n'),
      x: Math.min(zero, x).toFixed(1), y: y + 4, width: Math.max(1.5, Math.abs(x - zero)).toFixed(1), height: rowH - 8
    }));
    const vt = svgEl('text', { class: 'vlabel', x: (Math.max(zero, x) + 7).toFixed(1), y: y + rowH / 2 + 3.5 });
    vt.textContent = opts.fmt ? opts.fmt(it.v) : fmtNum(it.v);
    svg.appendChild(vt);
  });
  if (lo < 0) svg.appendChild(svgEl('line', { class: 'base', x1: zero, x2: zero, y1: T, y2: H - T }));
  return svg;
}

/* ===========================================================================
   Scoring
   Every comparison here names both of its years. A change from the last year
   published to the latest complete one is a different claim from a change
   since 2016, and the page never blurs them.
   ======================================================================== */
function relChange(rec, fromY, toY) {
  const a = rec.v[D.yi[fromY]], b = rec.v[D.yi[toY]];
  if (a == null || b == null || a === 0) return null;
  return (b - a) / Math.abs(a);
}
function ptChange(rec, fromY, toY) {
  const a = rec.v[D.yi[fromY]], b = rec.v[D.yi[toY]];
  if (a == null || b == null) return null;
  return b - a;
}
/* +1 the city's way, -1 against it, 0 no material change, null unscorable */
function score(rec, fromY, toY) {
  if (!rec.dir) return null;
  const r = relChange(rec, fromY, toY);
  if (r == null) return null;
  const g = r * rec.dir;
  if (Math.abs(g) < state.flat) return 0;
  return g > 0 ? 1 : -1;
}
function tally(recs, fromY, toY) {
  const t = { g: 0, b: 0, f: 0, n: 0, none: 0, gap: 0 };
  recs.forEach(r => {
    const s = score(r, fromY, toY);
    if (s === null) { if (!r.dir) t.none++; else t.gap++; return; }
    t.n++;
    if (s > 0) t.g++; else if (s < 0) t.b++; else t.f++;
  });
  return t;
}

/* ===========================================================================
   Shared pieces
   ======================================================================== */
function verdictBar(t, h) {
  const bar = el('div', 'verdictbar');
  if (h) bar.style.height = h + 'px';
  const tot = t.n || 1;
  [['g', t.g], ['f', t.f], ['b', t.b]].forEach(([c, v]) => {
    if (!v) return;
    const i = el('i', c); i.style.width = (v / tot * 100) + '%';
    i.title = v + ' ' + ({ g: 'moved the city\'s way', f: 'no material change', b: 'moved against it' }[c]);
    bar.appendChild(i);
  });
  return bar;
}
function keyRow(t) {
  const k = el('div', 'key');
  k.innerHTML =
    `<b><i style="background:var(--good)"></i>${t.g.toLocaleString()} the city's way</b>` +
    `<b><i style="background:var(--flat)"></i>${t.f.toLocaleString()} no material change</b>` +
    `<b><i style="background:var(--bad)"></i>${t.b.toLocaleString()} against it</b>`;
  return k;
}

function indicatorRow(rec, opts) {
  opts = opts || {};
  const b = el('button', 'row');
  b.type = 'button';
  const s = opts.score !== undefined ? opts.score : score(rec, state.fromYear, state.toYear);
  const cls = s === null ? '' : VCLASS[s];
  const t = el('div', 't');
  const title = el('b');
  if (rec.sus) { const f = el('span', 'flagdot'); f.title = 'Carries a published figure that cannot be what its label says'; title.appendChild(f); }
  title.appendChild(document.createTextNode(rec.n));
  t.appendChild(title);
  const meta = el('span', 'm');
  const bits = [D.agencies[rec.a].c];
  if (rec.cr) bits.push('critical');
  if (rec.rt) bits.push('retired');
  bits.push(rec.dir === 1 ? 'city wants higher' : rec.dir === -1 ? 'city wants lower' : 'no direction given');
  meta.innerHTML = bits.map((x, i) => i === 0 ? `<em>${esc(x)}</em>` : esc(x)).join(' &nbsp;·&nbsp; ');
  t.appendChild(meta);
  b.appendChild(t);

  const sp = el('div', 'sp');
  sp.appendChild(sparkline(rec.v, { cls, w: 104, h: 26 }));
  b.appendChild(sp);

  const lastIdx = lastIndex(rec.v);
  const val = el('div', 'val');
  val.innerHTML = esc(fmtVal(lastIdx == null ? null : rec.v[lastIdx], rec.mt, rec)) +
    '<small>' + (lastIdx == null ? 'no data' : 'FY' + D.years[lastIdx]) + '</small>';
  b.appendChild(val);

  const chg = el('div', 'chg ' + (cls || 'f'));
  if (opts.measureText) {
    chg.innerHTML = esc(opts.measureText) + '<small>' + esc(opts.measureLabel || '') + '</small>';
  } else {
    const r = relChange(rec, state.fromYear, state.toYear);
    const missing = rec.v[D.yi[state.toYear]] == null ? (state.toYear === D.pdfYear ? 'not in the ' + state.toYear + ' report' : 'no FY' + String(state.toYear).slice(2) + ' figure')
      : rec.v[D.yi[state.fromYear]] == null ? 'no FY' + String(state.fromYear).slice(2) + ' figure' : 'not comparable';
    chg.innerHTML = esc(fmtPct(r)) + '<small>' + (r == null ? missing : 'FY' + String(state.fromYear).slice(2) + '\u2192' + String(state.toYear).slice(2)) + '</small>';
  }
  b.appendChild(chg);
  b.addEventListener('click', () => openIndicator(rec.id));
  return b;
}
/* Near-zero baseline, or a one-year move of 100 per cent or more. Neither
   proves a counting change, but between them they account for almost every
   four-figure percentage in this data. Held back by default, never hidden. */
function looksLikeRecount(r) { return !!(r.st && (r.st.lowbase || r.st.bigstep)); }
function lastIndex(v) { for (let i = v.length - 1; i >= 0; i--) if (v[i] != null) return i; return null; }

function renderRows(host, recs, limit, opts) {
  const wrap = el('div', 'rows');
  recs.slice(0, limit).forEach(r => wrap.appendChild(indicatorRow(r, typeof opts === 'function' ? opts(r) : opts)));
  host.appendChild(wrap);
  if (recs.length > limit) {
    const more = el('button', 'chip');
    more.style.cssText = 'margin:14px 30px;display:block';
    more.textContent = 'Show ' + Math.min(200, recs.length - limit).toLocaleString() + ' more of ' + recs.length.toLocaleString();
    more.addEventListener('click', () => {
      wrap.remove(); more.remove();
      renderRows(host, recs, limit + 200, opts);
    });
    host.appendChild(more);
  }
  return wrap;
}

function sectionHead(label, right, no) {
  const h = el('h3', 'sec');
  h.innerHTML = (no ? `<span class="no">${esc(no)}&nbsp;&nbsp;</span>` : '') + label + (right ? `<span>${right}</span>` : '');
  return h;
}

/* ===========================================================================
   View: scoreboard
   ======================================================================== */
function viewBoard(host) {
  const pool = () => D.live.filter(r => !state.criticalOnly || r.cr);

  const bar = el('div', 'bar2');
  bar.innerHTML =
    `<button class="chip" id="crit" aria-pressed="${state.criticalOnly}">Only the city's critical indicators</button>` +
    `<span class="spacer"></span><span class="count" id="bcount"></span>`;
  host.appendChild(bar);

  const board = el('div', 'board');
  const left = el('section'), right = el('section');
  board.appendChild(left); board.appendChild(right);
  host.appendChild(board);

  const drawLeft = () => {
    left.innerHTML = '';
    left.appendChild(sectionHead(`Citywide, fiscal ${state.fromYear} to fiscal ${state.toYear}`, '', '01'));
    const pad = el('div', 'pad');
    const t = tally(pool(), state.fromYear, state.toYear);
    $('#bcount').textContent = t.n.toLocaleString() + ' indicators scored';
    pad.appendChild(verdictBar(t, 34));
    pad.appendChild(keyRow(t));
    const note = el('p', 'note');
    note.innerHTML =
      `Of <b>${pool().length.toLocaleString()}</b> citywide indicators still being reported, ` +
      `<b>${t.n.toLocaleString()}</b> can be scored: they carry a figure for both fiscal ${state.fromYear} ` +
      `and fiscal ${state.toYear}, and the city states which direction it wants them to move. ` +
      `<b>${t.none.toLocaleString()}</b> are counted but carry no desired direction, so the city itself ` +
      `will not say whether a rise is good news. Another <b>${t.gap.toLocaleString()}</b> are missing one ` +
      `of the two years. Change is measured against each indicator's own fiscal ${state.fromYear} figure.`;
    pad.appendChild(note);

    // what moved most, both ways
    const scored = pool().map(r => ({ r, g: (relChange(r, state.fromYear, state.toYear) || 0) * r.dir, has: relChange(r, state.fromYear, state.toYear) != null && r.dir }))
      .filter(x => x.has && !(state.hideLowBase && looksLikeRecount(x.r)));
    scored.sort((a, b) => b.g - a.g);
    const mk = (title, list) => {
      const h = el('h4'); h.style.cssText = 'margin:26px 0 6px;font-family:var(--mono);font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--ink2);font-weight:400;padding-bottom:6px;border-bottom:1px solid var(--hair)';
      h.textContent = title; pad.appendChild(h);
      const ul = el('div');
      list.forEach(x => {
        const row = el('button');
        row.type = 'button';
        row.style.cssText = 'display:grid;grid-template-columns:minmax(0,1fr) 60px 74px;gap:12px;align-items:center;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--hair2);padding:7px 0;cursor:pointer;font:inherit;color:inherit';
        const nm = el('span');
        nm.style.cssText = 'min-width:0;font-size:13.5px;line-height:1.3';
        nm.innerHTML = `<span style="font-family:var(--mono);font-size:10px;letter-spacing:.09em;color:var(--ink3)">${esc(D.agencies[x.r.a].c)}</span> ${esc(x.r.n)}`;
        row.appendChild(nm);
        const spw = el('span'); spw.appendChild(sparkline(x.r.v, { cls: x.g > 0 ? 'g' : 'b', w: 58, h: 20 })); row.appendChild(spw);
        const v = el('span');
        v.style.cssText = 'text-align:right;font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums;color:' + (x.g > 0 ? 'var(--good)' : 'var(--bad)');
        v.textContent = fmtPct(relChange(x.r, state.fromYear, state.toYear));
        row.appendChild(v);
        row.addEventListener('click', () => openIndicator(x.r.id));
        ul.appendChild(row);
      });
      pad.appendChild(ul);
    };
    mk('Moved furthest the city\'s way', scored.slice(0, 8));
    mk('Moved furthest against it', scored.slice(-8).reverse());
    const foot = el('p', 'note');
    foot.innerHTML = 'Ranked by change from each indicator\'s own fiscal ' + state.fromYear + ' figure to its fiscal ' + state.toYear + ' one. ' +
      (state.hideLowBase
        ? 'Moves off a near-zero base, and one-year moves of 100 per cent or more, are held back: almost every one of them is a change in how something is counted rather than a change on the ground. <a href="#" id="showlow">Put them back in</a>.'
        : 'Moves off a near-zero base and one-year moves of 100 per cent or more are included, and they dominate. <a href="#" id="showlow">Hold them back</a>.');
    pad.appendChild(foot);
    left.appendChild(pad);
    $('#showlow').addEventListener('click', e => { e.preventDefault(); state.hideLowBase = !state.hideLowBase; drawLeft(); });
  };

  const drawRight = () => {
    right.innerHTML = '';
    right.appendChild(sectionHead('Agency by agency', '', '02'));
    const pad = el('div', 'pad');
    const rowsData = D.agencies.map((a, i) => {
      const recs = pool().filter(r => r.a === i);
      const t = tally(recs, state.fromYear, state.toYear);
      return { a, i, t, share: t.n ? t.g / t.n : null };
    }).filter(x => x.t.n >= 10);
    const table = el('table', 'league');
    const cols = [
      { k: 'nm', l: 'Agency', s: x => x.a.n },
      { k: 'n', l: 'Scored', n: 1, s: x => x.t.n },
      { k: 'bar', l: 'Way / flat / against', n: 0, s: x => x.share },
      { k: 'sh', l: '% city\'s way', n: 1, s: x => x.share },
    ];
    let sortK = 'sh', asc = false;
    const draw = () => {
      const c = cols.find(c => c.k === sortK);
      rowsData.sort((p, q) => {
        const a = c.s(p), b = c.s(q);
        if (typeof a === 'string') return asc ? a.localeCompare(b) : b.localeCompare(a);
        return asc ? a - b : b - a;
      });
      table.innerHTML = '';
      const thead = el('thead'), tr = el('tr');
      cols.forEach(c2 => {
        const th = el('th', c2.n ? 'n' : (c2.k === 'bar' ? 'ab' : ''), c2.l);
        if (c2.k === sortK) th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
        th.addEventListener('click', () => { if (sortK === c2.k) asc = !asc; else { sortK = c2.k; asc = c2.k === 'nm'; } draw(); });
        tr.appendChild(th);
      });
      thead.appendChild(tr); table.appendChild(thead);
      const tb = el('tbody');
      rowsData.forEach(x => {
        const r = el('tr');
        const td1 = el('td');
        td1.innerHTML = `<span class="nm">${esc(x.a.n)}</span> <span class="code">${esc(x.a.c)}</span>`;
        r.appendChild(td1);
        r.appendChild(el('td', 'n', String(x.t.n)));
        const tdb = el('td', 'ab');
        tdb.appendChild(verdictMini(x.t));
        r.appendChild(tdb);
        r.appendChild(el('td', 'n', (x.share * 100).toFixed(0) + '%'));
        r.addEventListener('click', () => { state.agency = x.i; go('agencies'); });
        tb.appendChild(r);
      });
      table.appendChild(tb);
    };
    draw();
    pad.appendChild(table);
    const n2 = el('p', 'note');
    n2.innerHTML = 'Agencies with fewer than ten scorable indicators are left out — a three-of-four "success rate" is not a fact about an agency. ' +
      'Share is of scored indicators only, and a big agency\'s share is a much sturdier number than a small one\'s. Click any row for the agency in full.';
    pad.appendChild(n2);
    right.appendChild(pad);
  };

  $('#crit').addEventListener('click', e => {
    state.criticalOnly = !state.criticalOnly;
    e.target.setAttribute('aria-pressed', state.criticalOnly);
    drawLeft(); drawRight();
  });
  drawLeft(); drawRight();
}
function verdictMini(t) {
  const bar = el('div', 'minibar');
  const tot = t.n || 1;
  [['g', t.g], ['f', t.f], ['b', t.b]].forEach(([c, v]) => {
    if (!v) return;
    const i = el('i', c); i.style.width = (v / tot * 100) + '%'; bar.appendChild(i);
  });
  return bar;
}

/* ===========================================================================
   View: agencies
   The report's own hierarchy — agency, then the service it provides, then the
   goal it has set itself, then the indicators filed under that goal.
   ======================================================================== */
function viewAgencies(host) {
  if (state.agency == null) state.agency = D.agencies.findIndex(a => a.c === 'NYPD');
  const pane = el('div', 'apane');
  const list = el('div', 'alist'), body = el('div', 'abody');
  pane.appendChild(list); pane.appendChild(body);
  host.appendChild(pane);

  D.agencies.forEach((a, i) => {
    const recs = D.live.filter(r => r.a === i);
    if (!recs.length && !D.byAgency[i].length) return;
    const t = tally(recs, state.fromYear, state.toYear);
    const b = el('button');
    b.type = 'button';
    if (i === state.agency) b.classList.add('on');
    b.innerHTML = `<span><span class="nm">${esc(a.n)}</span><span class="sub2">${esc(a.c)} · ${D.byAgency[i].length} indicators</span></span>`;
    const mb = el('span', 'mb');
    if (t.n) mb.appendChild(verdictMini(t));
    b.appendChild(mb);
    b.addEventListener('click', () => {
      state.agency = i;
      $$('.alist button').forEach(x => x.classList.remove('on'));
      b.classList.add('on');
      drawAgency(body);
      syncHash();
      body.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
    list.appendChild(b);
  });
  drawAgency(body);
}

function drawAgency(body) {
  const i = state.agency, a = D.agencies[i];
  const recs = D.byAgency[i];
  const live = recs.filter(r => !r.rt);
  const t = tally(live, state.fromYear, state.toYear);
  body.innerHTML = '';
  body.appendChild(sectionHead(esc(a.n), esc(a.c), '03'));

  const pad = el('div', 'pad');
  if (t.n) {
    pad.appendChild(verdictBar(t, 26));
    pad.appendChild(keyRow(t));
  }
  const note = el('p', 'note');
  note.innerHTML = `${recs.length.toLocaleString()} indicators on file, ${live.length.toLocaleString()} still reported` +
    (t.n ? `, ${t.n.toLocaleString()} scorable between fiscal ${state.fromYear} and fiscal ${state.toYear}` : '') + '.';
  pad.appendChild(note);

  const links = el('div', 'links');
  const chapter = a.mmr ? D.mmrBase + a.mmr : D.mmrPage;
  links.innerHTML =
    `<a href="${esc(chapter)}" target="_blank" rel="noopener">${a.mmr ? 'Fiscal 2026 MMR chapter (PDF)' : 'Mayor\'s Management Report'}</a>` +
    `<a href="https://data.cityofnewyork.us/resource/rbed-zzin.json?$order=valuedate&agency=${encodeURIComponent(a.c)}" target="_blank" rel="noopener">This agency's raw rows</a>` +
    `<a href="https://dmmr.nyc.gov/" target="_blank" rel="noopener">City's dynamic MMR</a>`;
  pad.appendChild(links);
  body.appendChild(pad);

  // what it spends and who it employs
  const res = D.res[a.c];
  if (res) {
    body.appendChild(sectionHead('What it spends, who it employs', '', '04'));
    const rp = el('div', 'pad');
    const yrs = Object.keys(res).map(Number).sort();
    const mkSeries = (key, label, fmt) => {
      const vals = yrs.map(y => res[String(y)][key]);
      if (!vals.some(v => v != null)) return;
      const fake = { v: vals, mt: MT_NUMBER, sus: null, ts: 0, tu: '' };
      const wrap = el('div');
      wrap.style.cssText = 'margin-bottom:18px';
      const h = el('div');
      h.style.cssText = 'font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink2);margin-bottom:4px';
      const lastV = [...vals].reverse().find(v => v != null);
      h.textContent = label + ' — ' + fmt(lastV) + ' in fiscal ' + yrs[vals.length - 1 - [...vals].reverse().findIndex(v => v != null)];
      wrap.appendChild(h);
      const saveYears = D.years, saveYi = D.yi;
      D.years = yrs; D.yi = {}; yrs.forEach((y, k) => D.yi[y] = k);
      const svg = lineChart(fake, { h: 170, plain: true });
      D.years = saveYears; D.yi = saveYi;
      wrap.appendChild(svg);
      rp.appendChild(wrap);
    };
    mkSeries('exp', 'Expenditures, $ millions', v => '$' + fmtNum(v) + 'm');
    mkSeries('pers', 'Personnel, full-time headcount', v => fmtNum(v));
    const rn = el('p', 'note');
    rn.innerHTML = 'Actual expenditures and personnel as reported in the agency resources table of the Mayor\'s Management Report ' +
      `(<a href="https://data.cityofnewyork.us/resource/4qmi-txnk.json?agency=${encodeURIComponent(a.c)}" target="_blank" rel="noopener">raw rows</a>). ` +
      'Where an agency reports uniformed and civilian headcount separately, the two are added. Dollars are as published and are not inflation-adjusted.';
    rp.appendChild(rn);
    body.appendChild(rp);
  }

  // indicators, grouped the way the report groups them
  body.appendChild(sectionHead('Indicators, by service and goal', recs.length + ' on file', '05'));
  const groups = new Map();
  recs.forEach(r => {
    const k = r.s + '|' + r.g;
    if (!groups.has(k)) groups.set(k, { svc: r.s >= 0 ? D.svc[r.s] : 'Not filed under a service', goal: r.g >= 0 ? D.goal[r.g] : 'No goal stated', rs: [] });
    groups.get(k).rs.push(r);
  });
  const order = Array.from(groups.values()).sort((x, y) => y.rs.length - x.rs.length);
  order.forEach(gr => {
    const gh = el('div', 'goalhead');
    gh.innerHTML = `<div class="svc">${esc(gr.svc)}</div><div class="gl">${esc(gr.goal)}</div>`;
    body.appendChild(gh);
    const sorted = gr.rs.slice().sort((p, q) => (q.cr - p.cr) || (p.rt - q.rt) || p.n.localeCompare(q.n));
    renderRows(body, sorted, 40);
  });
}

/* ===========================================================================
   View: search
   ======================================================================== */
function viewSearch(host) {
  const bar = el('div', 'bar2');
  bar.innerHTML =
    `<input type="search" id="q" placeholder="Search ${D.ind.length.toLocaleString()} indicators — try &quot;response time&quot;, &quot;mold&quot;, &quot;overtime&quot;, &quot;lead&quot;" value="${esc(state.q)}" autocomplete="off" spellcheck="false">` +
    `<select id="f-agency"><option value="">Every agency</option>` +
    D.agencies.map((a, i) => `<option value="${i}"${String(i) === state.filters.agency ? ' selected' : ''}>${esc(a.n)}</option>`).join('') + `</select>` +
    `<select id="f-live">` +
    [['live', 'Still reported'], ['', 'Including retired'], ['retired', 'Retired only']].map(([v, l]) =>
      `<option value="${v}"${v === state.filters.live ? ' selected' : ''}>${l}</option>`).join('') + `</select>` +
    `<select id="f-dir"><option value="">Any direction</option>` +
    [['1', 'City wants it higher'], ['-1', 'City wants it lower'], ['0', 'No direction given']].map(([v, l]) =>
      `<option value="${v}"${v === state.filters.dir ? ' selected' : ''}>${l}</option>`).join('') + `</select>` +
    `<select id="f-mt"><option value="">Any unit</option>` +
    D.mt.map((m, i) => `<option value="${i}"${String(i) === state.filters.mt ? ' selected' : ''}>${esc(MT_WORD[m] || m)}</option>`).join('') + `</select>` +
    `<button class="chip" id="f-crit" aria-pressed="${state.filters.critical === '1'}">Critical only</button>` +
    `<span class="spacer"></span><span class="count" id="scount"></span>`;
  host.appendChild(bar);
  const out = el('div');
  host.appendChild(out);

  const run = () => {
    const recs = searchRecords();
    $('#scount').textContent = recs.length.toLocaleString() + ' of ' + D.ind.length.toLocaleString();
    out.innerHTML = '';
    if (!recs.length) {
      out.appendChild(el('div', 'empty', 'Nothing matches. Search covers indicator names, the city\'s own description of each one, the agency, the service and the goal it sits under.'));
      return;
    }
    renderRows(out, recs, 120);
  };
  const qbox = $('#q');
  let timer;
  qbox.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.q = qbox.value.trim(); run(); syncHash(); }, 140);
  });
  $('#f-agency').addEventListener('change', e => { state.filters.agency = e.target.value; run(); });
  $('#f-live').addEventListener('change', e => { state.filters.live = e.target.value; run(); });
  $('#f-dir').addEventListener('change', e => { state.filters.dir = e.target.value; run(); });
  $('#f-mt').addEventListener('change', e => { state.filters.mt = e.target.value; run(); });
  $('#f-crit').addEventListener('click', e => {
    state.filters.critical = state.filters.critical === '1' ? '' : '1';
    e.target.setAttribute('aria-pressed', state.filters.critical === '1');
    run();
  });
  run();
  if (state.q) qbox.focus();
}

function searchRecords() {
  const f = state.filters;
  const terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  let recs = D.ind;
  if (f.agency !== '') recs = recs.filter(r => String(r.a) === f.agency);
  if (f.live === 'live') recs = recs.filter(r => !r.rt);
  else if (f.live === 'retired') recs = recs.filter(r => r.rt);
  if (f.dir !== '') recs = recs.filter(r => String(r.dir) === f.dir);
  if (f.mt !== '') recs = recs.filter(r => String(r.mt) === f.mt);
  if (f.critical === '1') recs = recs.filter(r => r.cr);
  if (terms.length) recs = recs.filter(r => terms.every(t => r._h.indexOf(t) >= 0));
  if (terms.length) {
    const first = terms[0];
    recs = recs.slice().sort((p, q) => {
      const a = p.n.toLowerCase().indexOf(first), b = q.n.toLowerCase().indexOf(first);
      const ra = a < 0 ? 999 : a, rb = b < 0 ? 999 : b;
      return ra - rb || (q.cr - p.cr) || p.n.localeCompare(q.n);
    });
  } else {
    recs = recs.slice().sort((p, q) => (q.cr - p.cr) || p.n.localeCompare(q.n));
  }
  return recs;
}

/* ===========================================================================
   View: outliers
   The same indicator can be the year's biggest percentage move and completely
   ordinary against its own ten-year record. These measures disagree on
   purpose; each one says what it is measuring and between which years.
   ======================================================================== */
const MEASURES = [
  {
    k: 'win', label: 'Change between the two years chosen above', dir: true,
    blurb: 'Change from the baseline year to the compared year set at the top of the page, signed so that a rise counts as good news only when the city says a rise is good news. Change the pair up there and this list re-ranks.',
    ends: ['Moved furthest the city\'s way', 'Moved furthest against it'],
    get: r => { const c = relChange(r, state.fromYear, state.toYear); return c == null || !r.dir ? null : c * r.dir; },
    txt: r => fmtPct(relChange(r, state.fromYear, state.toYear)),
    sub: r => 'FY' + String(state.fromYear).slice(2) + '\u2192' + String(state.toYear).slice(2),
  },
  {
    k: 'g1', label: 'Change since the year before', dir: true,
    blurb: 'Percentage change between an indicator\'s two most recent published years, signed so that a rise counts as good news only when the city says a rise is good news.',
    ends: ['Moved furthest the city\'s way', 'Moved furthest against it'],
    get: r => r.st && r.st.g1,
    txt: r => fmtPct(r.st.d1), sub: r => 'FY' + String(r.st.py).slice(2) + '→' + String(r.st.ly).slice(2),
  },
  {
    k: 'gA', label: 'Change across its whole run', dir: true,
    blurb: 'Percentage change from the first year an indicator was published to the most recent, however many years apart those are.',
    ends: ['Furthest the city\'s way since it began', 'Furthest against it since it began'],
    get: r => r.st && r.st.gA,
    txt: r => fmtPct(r.st.dA), sub: r => 'FY' + String(r.st.fy).slice(2) + '→' + String(r.st.ly).slice(2),
  },
  {
    k: 'gcagr', label: 'Sustained trend, per year', dir: true,
    blurb: 'The first-to-last change compounded over the years between, so a rise of 60 per cent across nine years reads as the 5.4 per cent a year it actually is. This is the plainest answer to "which way has this been going, and how fast" — but it only looks at the two ends of the run.',
    ends: ['Strongest sustained trend the city\'s way', 'Strongest sustained trend against it'],
    get: r => r.st && r.st.n >= 5 ? r.st.gcagr : null,
    txt: r => fmtPct(r.st.cagr, 1) + '/yr',
    sub: r => 'FY' + String(r.st.fy).slice(2) + '→' + String(r.st.ly).slice(2),
  },
  {
    k: 'gtr', label: 'Trend through every year published', dir: true,
    blurb: 'A straight line fitted through every published year, not just the first and last, expressed as a percentage of the indicator\'s own average per year. The fit figure says how much of the movement that line actually explains: near 1 is a steady march, near 0 means the line is an artefact of two stray years and the per-year rate should not be quoted.',
    ends: ['Steepest line the city\'s way', 'Steepest line against it'],
    get: r => r.st && r.st.n >= 5 ? r.st.gtr : null,
    txt: r => fmtPct(r.st.tr, 1) + '/yr',
    sub: r => 'fit ' + (r.st.r2 != null ? r.st.r2.toFixed(2) : '—'),
  },
  {
    k: 'gp1', label: 'Point change since the year before', dir: true,
    blurb: 'The raw difference between the last two published figures, in the indicator\'s own units. For a percentage this is percentage points, which is usually the fairer reading; for a response time it is minutes and seconds.',
    ends: ['Biggest gain in the city\'s favour', 'Biggest loss'],
    get: r => r.st && r.st.gp1,
    txt: r => fmtPoints(r.st.p1, r.mt, r), sub: r => 'FY' + String(r.st.py).slice(2) + '→' + String(r.st.ly).slice(2),
  },
  {
    k: 'gz', label: 'Distance from its own normal', dir: true,
    blurb: 'How far the latest figure sits from the average of every earlier year, measured in standard deviations of that indicator\'s own history. This is the measure that finds a number that is strange for itself, not merely large.',
    ends: ['Furthest above its normal, in the city\'s favour', 'Furthest from normal, against it'],
    get: r => r.st && r.st.gz,
    txt: r => (r.st.z > 0 ? '+' : '') + r.st.z.toFixed(1) + ' sd', sub: r => (r.st.z > 0 ? 'above' : 'below') + ' its normal',
  },
  {
    k: 'grec', label: 'Best or worst reading on record', dir: true,
    blurb: 'Indicators whose latest figure is the highest or the lowest in everything the city has published for them since fiscal 2016.',
    ends: ['Best ever recorded', 'Worst ever recorded'],
    get: r => r.st && r.st.grec, needs: r => r.st && r.st.grec,
    txt: r => (r.st.grec > 0 ? 'best' : 'worst'), sub: r => 'of ' + r.st.n + ' years',
    tie: r => Math.abs(r.st.gz || 0),
  },
  {
    k: 'cv', label: 'How much it swings', dir: false,
    blurb: 'The spread of an indicator\'s values relative to its own average. High swing is often a real thing — a mass fatality count, a grant cycle — and just as often a sign that the definition has been changed underneath the series.',
    ends: ['Swings most', 'Steadiest'],
    get: r => r.st && r.st.cv,
    txt: r => r.st.cv.toFixed(2), sub: r => 'over ' + r.st.n + ' years',
  },
  {
    k: 'gst', label: 'Consecutive years in one direction', dir: true,
    blurb: 'An unbroken run of years all moving the same way, ending at the latest figure. A long run is a harder fact than a single year\'s move.',
    ends: ['Longest run the city\'s way', 'Longest run against it'],
    get: r => r.st && r.st.gst, needs: r => r.st && r.st.gst,
    txt: r => (r.st.gst > 0 ? '+' : '') + r.st.gst + ' yrs', sub: r => 'ending FY' + String(r.st.ly).slice(2),
  },
  {
    k: 'br', label: 'Biggest single-year step it ever took', dir: false,
    blurb: 'The largest one-year jump anywhere in the series. Above about 100 per cent this almost always means the indicator was redefined, recounted or restated — which is exactly why it is worth looking at.',
    ends: ['Biggest step', 'Smallest step'],
    get: r => r.st && r.st.br,
    txt: r => fmtPct(r.st.br, 0), sub: r => 'somewhere in FY' + String(r.st.fy).slice(2) + '–' + String(r.st.ly).slice(2),
  },
  {
    k: 'tgt', label: 'Distance from its own target', dir: true,
    blurb: 'The open data has never carried target figures; the printed report does. This is how far the latest year landed from the target the agency set itself, as a share of that target, signed so that positive means it cleared the bar. Only the indicators the report prints a target for can appear.',
    ends: ['Cleared its own target by most', 'Missed its own target by most'],
    needs: r => r.tgt && r.tgt.t26 != null && D.pdfYear && r.v[D.yi[D.pdfYear]] != null && r.dir && r.tgt.t26 !== 0,
    get: r => (r.tgt && r.tgt.t26 && D.pdfYear && r.v[D.yi[D.pdfYear]] != null && r.dir)
      ? ((r.v[D.yi[D.pdfYear]] - r.tgt.t26) / Math.abs(r.tgt.t26)) * r.dir : null,
    txt: r => fmtPct(((r.v[D.yi[D.pdfYear]] - r.tgt.t26) / Math.abs(r.tgt.t26))),
    sub: r => 'vs target ' + fmtVal(r.tgt.t26, r.mt, r),
  },
  {
    k: 'sus', label: 'Figures that cannot be right', dir: false,
    blurb: 'Published values that cannot be what their label says: a percentage filed in the tens of thousands, or a single year filed at a different scale from every other year in its own series. Nothing is corrected here — these are shown so they are not mistaken for news.',
    ends: ['Flagged', 'Flagged'],
    get: r => r.sus ? 1 : null, needs: r => r.sus,
    txt: r => Object.keys(r.sus).map(y => 'FY' + y.slice(2)).join(', '), sub: r => 'as filed',
  },
];

function viewOutliers(host) {
  const m = () => MEASURES.find(x => x.k === state.measure) || MEASURES[0];

  const bar = el('div', 'bar2');
  bar.innerHTML =
    `<label for="meas">Rank by</label><select id="meas">` +
    MEASURES.map(x => `<option value="${x.k}"${x.k === state.measure ? ' selected' : ''}>${esc(x.label)}</option>`).join('') +
    `</select><select id="ext"></select>` +
    `<select id="o-agency"><option value="">Every agency</option>` +
    D.agencies.map((a, i) => `<option value="${i}"${String(i) === state.filters.agency ? ' selected' : ''}>${esc(a.n)}</option>`).join('') + `</select>` +
    `<select id="o-live">` +
    [['live', 'Still reported'], ['', 'Including retired']].map(([v, l]) =>
      `<option value="${v}"${v === state.filters.live ? ' selected' : ''}>${l}</option>`).join('') + `</select>` +
    `<button class="chip" id="o-crit" aria-pressed="${state.filters.critical === '1'}">Critical only</button>` +
    `<button class="chip" id="o-low" aria-pressed="${state.hideLowBase}">Hold back likely recounts</button>` +
    `<span class="spacer"></span><span class="count" id="ocount"></span>`;
  host.appendChild(bar);
  const blurb = el('p', 'note');
  blurb.style.cssText = 'padding:14px 30px 0;margin:0;max-width:86ch';
  host.appendChild(blurb);
  const out = el('div');
  host.appendChild(out);

  const fillExt = () => {
    const c = m();
    $('#ext').innerHTML = `<option value="best">${esc(c.ends[0])}</option><option value="worst">${esc(c.ends[1])}</option>`;
    $('#ext').value = state.extreme;
    $('#ext').style.display = c.k === 'sus' ? 'none' : '';
  };

  const run = () => {
    const c = m();
    blurb.textContent = c.blurb;
    let recs = D.ind.filter(r => r.st || c.k === 'sus');
    if (state.filters.agency !== '') recs = recs.filter(r => String(r.a) === state.filters.agency);
    if (state.filters.live === 'live') recs = recs.filter(r => !r.rt);
    if (state.filters.critical === '1') recs = recs.filter(r => r.cr);
    if (state.hideLowBase) recs = recs.filter(r => !looksLikeRecount(r));
    if (c.needs) recs = recs.filter(c.needs);
    recs = recs.filter(r => c.get(r) != null);
    const sign = state.extreme === 'best' ? -1 : 1;
    recs.sort((p, q) => {
      const d = sign * (c.get(p) - c.get(q));
      if (d) return d;
      if (c.tie) return c.tie(q) - c.tie(p);
      return 0;
    });
    if (c.k === 'grec') recs = recs.filter(r => (state.extreme === 'best' ? r.st.grec > 0 : r.st.grec < 0));
    if (c.k === 'gst') recs = recs.filter(r => (state.extreme === 'best' ? r.st.gst > 0 : r.st.gst < 0));
    $('#ocount').textContent = recs.length.toLocaleString() + ' qualify';
    out.innerHTML = '';
    if (!recs.length) { out.appendChild(el('div', 'empty', 'Nothing qualifies with these filters.')); return; }
    renderRows(out, recs, 80, r => {
      const v = c.get(r);
      const sc = !c.dir ? null : v > 0 ? 1 : v < 0 ? -1 : 0;
      return { measureText: c.txt(r), measureLabel: c.sub(r), score: sc };
    });
  };

  $('#meas').addEventListener('change', e => { state.measure = e.target.value; fillExt(); run(); syncHash(); });
  $('#ext').addEventListener('change', e => { state.extreme = e.target.value; run(); syncHash(); });
  $('#o-agency').addEventListener('change', e => { state.filters.agency = e.target.value; run(); });
  $('#o-live').addEventListener('change', e => { state.filters.live = e.target.value; run(); });
  $('#o-crit').addEventListener('click', e => {
    state.filters.critical = state.filters.critical === '1' ? '' : '1';
    e.target.setAttribute('aria-pressed', state.filters.critical === '1'); run();
  });
  $('#o-low').addEventListener('click', e => {
    state.hideLowBase = !state.hideLowBase;
    e.target.setAttribute('aria-pressed', state.hideLowBase); run();
  });
  fillExt(); run();
}

/* ===========================================================================
   View: ratios
   Two figures the report already prints, divided. Nothing here is mined: a
   machine looking for pairs whose ratio stays under one will cheerfully
   propose sewer miles over satisfaction surveys returned. Each pair was
   picked because the two indicators genuinely share a denominator, and
   checked against the city's own description of both.
   ======================================================================== */
let RATIOS_DATA = null;
function viewRatios(host) {
  host.appendChild(sectionHead('Ratios the city has the numbers for but does not publish', '', '09'));
  const intro = el('div', 'pad');
  const p = el('p', 'note');
  p.style.maxWidth = '84ch';
  p.innerHTML = 'Everything on this page is two figures from the report divided by one another. ' +
    'The report prints both and never puts them together — the cost of a jail bed, the share of ' +
    'complaints an inspector actually goes out to, how many people leave the shelter system for a ' +
    'home against how many arrive. Each one states the question it answers and the thing it cannot ' +
    'be read as, and shows both components so the arithmetic stays visible. ' +
    '<span id="rcount"></span>';
  intro.appendChild(p);
  host.appendChild(intro);

  const body = el('div');
  host.appendChild(body);
  body.appendChild(el('div', 'loading', 'Loading\u2026'));

  const draw = data => {
    const c = $('#rcount');
    if (c) c.innerHTML = `There are <b>${data.ratios.length}</b>, not eighty, because these are the ` +
      'pairs that survived checking: both sides have to be measured over the same period, cover the ' +
      'same unbroken run of years, and mean something when divided.';
    body.innerHTML = '';
    data.ratios.forEach((r, i) => {
      const sec = el('section', 'ratio');
      const h = el('div', 'rhead');
      h.innerHTML = `<span class="rag">${esc(r.agency)}</span><h3>${esc(r.title)}</h3>`;
      sec.appendChild(h);
      const basis = el('p', 'rbasis');
      basis.textContent = (r.years ? r.years.charAt(0).toUpperCase() + r.years.slice(1) : '') +
        (r.period ? ' \u00b7 both sides measured over the ' + r.period.toLowerCase() : '') +
        ' \u00b7 only years where both figures exist are plotted';
      sec.appendChild(basis);
      const pad = el('div', 'pad');
      const q = el('p'); q.className = 'rq'; q.textContent = r.question;
      pad.appendChild(q);

      const last = r.pts[r.pts.length - 1], first = r.pts[0];
      const fmtR = v => r.money ? '$' + Math.round(v).toLocaleString('en-US') : (Math.round(v * 10) / 10).toLocaleString('en-US');
      const lead = el('p', 'rlead');
      lead.innerHTML = `<b>${esc(fmtR(last.v))}</b> <span>${esc(r.unit)}</span> in fiscal ${last.y}, ` +
        `against ${esc(fmtR(first.v))} in fiscal ${first.y}.`;
      pad.appendChild(lead);

      const fake = {
        v: D.years.map(y => { const pt = r.pts.find(x => x.y === y); return pt ? pt.v : null; }),
        mt: r.money ? MT_CUR : MT_NUMBER, sus: null, ts: 0, tu: '',
      };
      pad.appendChild(lineChart(fake, { h: 150, plain: true }));

      const tbl = el('table', 'vtable');
      tbl.style.marginTop = '14px';
      const ys = r.pts.map(x => x.y);
      const row = (label, get, cls) => '<tr><td>' + esc(label) + '</td>' +
        r.pts.map(x => `<td class="${cls || ''}">${esc(get(x))}</td>`).join('') + '</tr>';
      tbl.innerHTML = '<thead><tr><th>Fiscal year</th>' + ys.map(y => `<th>${y}</th>`).join('') + '</tr></thead><tbody>' +
        row(r.numLabel.length > 58 ? r.numLabel.slice(0, 57) + '\u2026' : r.numLabel, x => fmtNum(x.n)) +
        row(r.denLabel.length > 58 ? r.denLabel.slice(0, 57) + '\u2026' : r.denLabel, x => fmtNum(x.d)) +
        row('The ratio', x => fmtR(x.v)) +
        '</tbody>';
      pad.appendChild(tbl);

      const links = el('div', 'links');
      links.style.marginTop = '12px';
      r.numIds.concat(r.denIds).forEach(id => {
        if (!D.byId[id]) return;
        const a = document.createElement('a');
        a.href = '#i/' + id;
        a.textContent = D.byId[id].n.length > 46 ? D.byId[id].n.slice(0, 45) + '\u2026' : D.byId[id].n;
        links.appendChild(a);
      });
      pad.appendChild(links);

      const c = el('div', 'warn');
      c.innerHTML = '<b>What it is not.</b> ' + esc(r.caveat);
      pad.appendChild(c);
      sec.appendChild(pad);
      body.appendChild(sec);
    });
  };

  if (RATIOS_DATA) { draw(RATIOS_DATA); return; }
  fetch('data/ratios.json').then(r => r.ok ? r.json() : null).then(data => {
    if (!data) { body.innerHTML = '<div class="empty">Could not load the ratios.</div>'; return; }
    RATIOS_DATA = data;
    draw(data);
  });
}

/* ===========================================================================
   View: retired
   ======================================================================== */
function viewRetired(host) {
  const dead = D.agencies.map((a, i) => {
    const rs = D.byAgency[i];
    const ret = rs.filter(r => r.rt).length;
    return { a, i, n: rs.length, ret, share: rs.length ? ret / rs.length : 0 };
  }).filter(x => x.n >= 10 && x.share >= 0.75);

  host.appendChild(sectionHead('Chapters the report stopped keeping', dead.length + ' of ' + D.agencies.length, '06'));
  const p1 = el('div', 'pad');
  const note = el('p', 'note');
  note.style.maxWidth = '84ch';
  note.innerHTML = 'The report carries citywide initiatives alongside agencies, and initiatives end. ' +
    'Listed here is every section where at least three quarters of the indicators on file are marked ' +
    'retired — in most cases after reporting right up to the last complete year, which means the ' +
    'numbers stopped being collected rather than the trend running out.';
  p1.appendChild(note);
  const tbl = el('table', 'league');
  tbl.innerHTML = '<thead><tr><th>Initiative or agency</th><th class="n">Retired / on file</th><th class="n">Last figure filed</th></tr></thead>';
  const tb = el('tbody');
  dead.sort((x, y) => y.ret - x.ret).forEach(x => {
    const last = Math.max(...D.byAgency[x.i].map(r => { const li = lastIndex(r.v); return li == null ? 0 : D.years[li]; }));
    const tr = el('tr');
    tr.innerHTML = `<td><span class="nm">${esc(x.a.n)}</span> <span class="code">${esc(x.a.c)}</span></td>` +
      `<td class="n">${x.ret} / ${x.n}</td><td class="n">${last ? 'fiscal ' + last : '—'}</td>`;
    tr.addEventListener('click', () => { state.agency = x.i; go('agencies'); });
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); p1.appendChild(tbl);
  host.appendChild(p1);

  const stopped = D.ind.filter(r => {
    if (r.rt) return false;
    const li = lastIndex(r.v);
    return li != null && D.years[li] < D.latest;
  }).sort((p, q) => lastIndex(q.v) - lastIndex(p.v) || p.n.localeCompare(q.n));
  host.appendChild(sectionHead('Still listed as current, no longer filing a figure', stopped.length + ' indicators', '07'));
  const p2 = el('div', 'pad');
  const n2 = el('p', 'note');
  n2.style.maxWidth = '84ch';
  n2.innerHTML = `Not marked retired, but carrying no full-year figure for fiscal ${D.latest}. Some are genuinely ` +
    'lapsed; some are indicators the city reports on a longer cycle. Either way the latest report has nothing to say about them.';
  p2.appendChild(n2);
  host.appendChild(p2);
  renderRows(host, stopped, 60, r => {
    const li = lastIndex(r.v);
    return { measureText: 'FY' + String(D.years[li]).slice(2), measureLabel: 'last filed', score: null };
  });

  const retired = D.ind.filter(r => r.rt).sort((p, q) => (lastIndex(q.v) || 0) - (lastIndex(p.v) || 0) || p.n.localeCompare(q.n));
  host.appendChild(sectionHead('Retired indicators', retired.length.toLocaleString() + ' on file', '08'));
  const p3 = el('div', 'pad');
  const n3 = el('p', 'note');
  n3.innerHTML = 'Everything the city has taken off the books since fiscal 2016, newest last figure first. ' +
    'These are still in the dataset, which is the only reason the history survives at all.';
  p3.appendChild(n3);
  host.appendChild(p3);
  renderRows(host, retired, 60, r => {
    const li = lastIndex(r.v);
    return { measureText: li == null ? '—' : 'FY' + String(D.years[li]).slice(2), measureLabel: 'last filed' };
  });
}

/* ===========================================================================
   One indicator, in full
   ======================================================================== */
const cache = { pace: {}, geo: {} };
function loadAgencyFile(kind, code) {
  const key = code.replace(/[^A-Za-z0-9_+-]/g, '_');
  if (cache[kind][key]) return cache[kind][key];
  cache[kind][key] = fetch(`data/${kind}/${key}.json`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);
  return cache[kind][key];
}

function openIndicator(id) {
  const rec = D.byId[id];
  if (!rec) return;
  const a = D.agencies[rec.a];
  const body = $('#dbody');
  $('#dlbl').textContent = [a.n, rec.cr ? 'Critical indicator' : null, rec.rt ? 'Retired' : null].filter(Boolean).join('  ·  ');
  $('#dtitle').textContent = rec.n;
  body.innerHTML = '';

  if (rec.sus) {
    const w = el('div', 'warn');
    w.innerHTML = '<b>Flagged.</b> ' + Object.entries(rec.sus).map(([y, why]) =>
      `The fiscal ${y} figure is ${esc(why)}.`).join(' ') +
      ' It is shown exactly as the city published it, and it distorts every average and change that runs through it.';
    body.appendChild(w);
  }

  if (rec.d >= 0) {
    body.appendChild(Object.assign(el('h4'), { textContent: 'What the city says it is counting' }));
    const p = el('p'); p.textContent = D.desc[rec.d]; body.appendChild(p);
  }

  body.appendChild(Object.assign(el('h4'), { textContent: 'Full fiscal years, ' + D.years[0] + ' to ' + D.latest }));
  body.appendChild(lineChart(rec));
  if (D.pdfYear && rec.v[D.yi[D.pdfYear]] != null) {
    const pr = el('p', 'prov');
    const pg = rec.pdf && rec.pdf.p;
    pr.innerHTML = `Fiscal ${D.pdfYear} (the open circle) is read from the printed report` +
      (rec.pdf && rec.pdf.raw ? `, where it is printed as <b>${esc(rec.pdf.raw)}</b>` : '') +
      (pg ? ` on <a href="${esc(D.pdfPageBase + pg)}" target="_blank" rel="noopener" style="color:inherit">page ${pg}</a>` : '') +
      `. Every earlier year comes from the open data table.`;
    body.appendChild(pr);
    if (rec.pdf && rec.pdf.restated) {
      const w = el('div', 'warn');
      const yrs = [2022, 2023, 2024, 2025];
      const was = yrs.map(y => fmtVal(rec.v[D.yi[y]], rec.mt, rec)).join('  ');
      w.innerHTML = '<b>Restated.</b> The printed report gives this series a different history from ' +
        'the one the open data holds. Fiscal 2022 to 2025 read ' +
        `<span style="font-family:var(--mono)">${esc(rec.pdf.restated.join('  '))}</span> in the report ` +
        `and <span style="font-family:var(--mono)">${esc(was)}</span> in the data. The chart plots the ` +
        'open data for those years and the report for fiscal ' + D.pdfYear + '.';
      body.appendChild(w);
    }
  }
  const st = rec.st;
  const cap = el('p', 'chartcap');
  if (st) {
    const s = score(rec, st.py, st.ly);
    cap.innerHTML =
      `<b>${esc(fmtVal(st.lv, rec.mt, rec))}</b> in fiscal ${st.ly}, against ${esc(fmtVal(st.pv, rec.mt, rec))} in fiscal ${st.py} — ` +
      `${esc(fmtPct(st.d1))} (${esc(fmtPoints(st.p1, rec.mt, rec))}). ` +
      (rec.dir ? `The city wants this ${rec.dir === 1 ? 'higher' : 'lower'}, so that ${s === null ? 'is not scorable' : s > 0 ? 'counts as an improvement' : s < 0 ? 'counts as a deterioration' : 'falls under the ' + (state.flat * 100) + '% threshold this page treats as no material change'}. ` : 'The city states no desired direction for this indicator, so it is not scored. ') +
      (st.rec === 1 ? 'It is the highest figure on record. ' : st.rec === -1 ? 'It is the lowest figure on record. ' : '') +
      (st.z != null ? `It sits ${Math.abs(st.z).toFixed(1)} standard deviations ${st.z > 0 ? 'above' : 'below'} the average of its earlier years. ` : '') +
      (st.gst ? `That is ${Math.abs(st.gst)} consecutive years moving ${st.gst > 0 ? 'the city\'s way' : 'against it'}. ` : '') +
      (rec.tgt && rec.tgt.t26 != null && rec.v[D.yi[D.pdfYear]] != null && rec.dir
        ? `The agency set itself a target of ${esc(fmtVal(rec.tgt.t26, rec.mt, rec))} for fiscal ${D.pdfYear} and ` +
          ((rec.dir === 1 ? rec.v[D.yi[D.pdfYear]] >= rec.tgt.t26 : rec.v[D.yi[D.pdfYear]] <= rec.tgt.t26) ? 'met it. ' : 'missed it. ')
        : '') +
      (st.cagr != null && st.n >= 5
        ? `Across the whole run it has moved ${esc(fmtPct(st.cagr, 1))} a year, and a straight line through every published year explains ${st.r2 != null ? (st.r2 * 100).toFixed(0) + ' per cent' : 'an unknown share'} of the movement.`
        : '');
  } else {
    cap.textContent = 'Too few published years to compare.';
  }
  body.appendChild(cap);

  // the numbers themselves
  body.appendChild(Object.assign(el('h4'), { textContent: 'The figures as filed' }));
  const vt = el('table', 'vtable');
  const yrs = D.years.filter((y, i) => rec.v[i] != null);
  vt.innerHTML = '<thead><tr><th>Fiscal year</th>' + yrs.map(y => `<th>${y}</th>`).join('') + '</tr></thead>' +
    '<tbody><tr><td>Value</td>' + yrs.map(y => {
      const v = rec.v[D.yi[y]];
      const flagged = rec.sus && rec.sus[String(y)];
      return `<td class="${flagged ? 'flagged' : ''}" ${flagged ? 'title="' + esc(flagged) + '"' : ''}>${esc(fmtVal(v, rec.mt, rec))}</td>`;
    }).join('') + '</tr></tbody>' +
    (rec.vr ? '<tbody><tr><td>As filed</td>' + yrs.map(y =>
      `<td>${rec.vr[D.yi[y]] == null ? '—' : rec.vr[D.yi[y]]}</td>`).join('') + '</tr></tbody>' : '');
  body.appendChild(vt);

  // how the current year is pacing
  const paceHost = el('div');
  body.appendChild(paceHost);
  loadAgencyFile('pace', a.c).then(d => {
    const p = d && d[rec.id];
    if (!p) return;
    const chart = paceChart(p, rec);
    if (!chart) return;
    paceHost.appendChild(Object.assign(el('h4'), { textContent: 'Year to date, month by month' }));
    paceHost.appendChild(chart);
    const c = el('p', 'chartcap');
    const partial = D.partialFy && p[D.partialFy];
    c.innerHTML = 'Each line is one fiscal year running July to June, showing the figure as reported year to date. ' +
      (rec.ad ? 'This indicator accumulates, so each line climbs through its year and the gap between lines is the gap in pace. '
        : 'This indicator is an average or a rate, so each month restates the year so far rather than adding to it. ') +
      (partial ? `Fiscal ${D.partialFy} is still running: the open data carries it only through ${monthName(lastMonth(partial))} ${monthYear(lastMonth(partial), D.partialFy)}.` : '');
    paceHost.appendChild(c);
  });

  // geography, where the city breaks it out
  const geoHost = el('div');
  body.appendChild(geoHost);
  if (D.hasGeo.indexOf(rec.id) >= 0) {
    loadAgencyFile('geo', a.c).then(d => {
      const kids = d && d[rec.id];
      if (!kids || !kids.length) return;
      const li = lastIndex(rec.v);
      const items = kids.map(k => {
        const ki = lastIndex(k.v);
        const label = (k.n.split(/\s+[-–—]\s+/).pop() || k.n).trim();
        return { label, v: ki == null ? null : k.v[ki], id: k.id, year: ki == null ? null : D.years[ki] };
      }).filter(x => x.v != null);
      if (items.length < 2) return;
      items.sort((p, q) => q.v - p.v);
      const type = D.geotype[kids[0].gt] || 'Area';
      geoHost.appendChild(Object.assign(el('h4'), { textContent: 'Broken out by ' + type.toLowerCase() }));
      geoHost.appendChild(barChart(items.slice(0, 40), { fmt: v => fmtVal(v, rec.mt, rec), labelW: 200 }));
      const c = el('p', 'chartcap');
      c.textContent = `${items.length} ${type.toLowerCase()} series, latest published figure for each. ` +
        (items.length > 40 ? 'Showing the 40 highest. ' : '') +
        'The city files these as separate indicators hanging off this one.';
      geoHost.appendChild(c);
    });
  }

  // the record
  body.appendChild(Object.assign(el('h4'), { textContent: 'On the record' }));
  const dl = el('dl', 'f');
  const rows = [
    ['Agency', a.n + ' (' + a.c + ')'],
    ['Service', rec.s >= 0 ? D.svc[rec.s] : '—'],
    ['Goal', rec.g >= 0 ? D.goal[rec.g] : '—'],
    ['Where the number comes from', rec.src >= 0 ? D.src[rec.src] : 'Not stated'],
    ['Unit', mtWord(rec.mt) + (rec.mt === MT_TIME ? ' (' + (rec.tu || 'unit not stated in the title') + (rec.ts ? ', read as a clock reading' : ', read as a decimal') + ')' : '') +
      (rec.mf > 1 ? ' · reported in units of ' + rec.mf.toLocaleString() : '')],
    ['Direction the city wants', rec.dir === 1 ? 'Up' : rec.dir === -1 ? 'Down' : 'None stated'],
    ['Reporting', (rec.fq >= 0 ? D.fq[rec.fq] : '—') + ' · ' + (rec.rp >= 0 ? D.rp[rec.rp] : '—')],
    ['Accumulates through the year', rec.ad ? 'Yes' : 'No'],
    ['Flagged critical by the city', rec.cr ? 'Yes' : 'No'],
    ['Retired', rec.rt ? 'Yes' : 'No'],
    ['Target, fiscal ' + (D.pdfYear || ''), rec.tgt && rec.tgt.t26 != null ? fmtVal(rec.tgt.t26, rec.mt, rec) : 'none printed'],
    ['Target, fiscal ' + ((D.pdfYear || 0) + 1), rec.tgt && rec.tgt.t27 != null ? fmtVal(rec.tgt.t27, rec.mt, rec) : 'none printed'],
    ['Indicator id', rec.id],
  ];
  rows.forEach(([k, v]) => {
    const d = el('div');
    d.innerHTML = `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`;
    dl.appendChild(d);
  });
  body.appendChild(dl);

  const links = el('div', 'links');
  links.innerHTML =
    `<a href="${esc(D.rowsUrl + encodeURIComponent(rec.id))}" target="_blank" rel="noopener">Every raw row for this indicator</a>` +
    `<a href="${esc(a.mmr ? D.mmrBase + a.mmr : D.mmrPage)}" target="_blank" rel="noopener">${a.mmr ? 'Agency chapter (PDF)' : 'The report'}</a>` +
    `<a href="${esc(D.datasetUrl)}" target="_blank" rel="noopener">The dataset</a>` +
    `<a href="${esc(D.dmmr)}" target="_blank" rel="noopener">City's dynamic MMR</a>`;
  body.appendChild(links);

  const dr = $('#drawer');
  dr.classList.add('open');
  document.body.style.overflow = 'hidden';
  $('.panel', dr).scrollTop = 0;
  $('.xbtn', dr).focus();
  if (location.hash !== '#i/' + rec.id) history.pushState(null, '', '#i/' + rec.id);
}
function lastMonth(p) { const order = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]; let m = null; order.forEach(x => { if (p[x] != null) m = x; }); return m; }
function monthName(m) { return ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][m] || ''; }
function monthYear(m, fy) { return m >= 7 ? fy - 1 : fy; }

function closeDrawer() {
  $('#drawer').classList.remove('open');
  document.body.style.overflow = '';
  if (location.hash.indexOf('#i/') === 0) history.pushState(null, '', '#' + state.view);
}

/* ===========================================================================
   Masthead strip: the citywide verdict, year by year
   ======================================================================== */
function drawMast() {
  const svg = $('#mast-svg');
  if (!svg) return;
  svg.innerHTML = '';
  const W = 420, H = 96, T = 4, B = 18, L = 0;
  const yrs = D.years.slice(1);
  const bw = (W - L) / yrs.length;
  yrs.forEach((y, i) => {
    const t = tally(D.live, D.years[D.yi[y] - 1], y);
    const x = L + i * bw;
    const h = H - T - B;
    let acc = T;
    [['g', t.g, 'var(--good)'], ['f', t.f, 'var(--flat)'], ['b', t.b, 'var(--bad)']].forEach(([c, v, col]) => {
      if (!t.n || !v) return;
      const seg = (v / t.n) * h;
      const r = svgEl('rect', { x: (x + 1.5).toFixed(1), y: acc.toFixed(1), width: (bw - 3).toFixed(1), height: seg.toFixed(1), fill: col });
      const title = svgEl('title');
      title.textContent = `FY${y}: ${t.g} the city's way, ${t.f} flat, ${t.b} against it, of ${t.n} scored`;
      r.appendChild(title);
      svg.appendChild(r);
      acc += seg;
    });
    const tx = svgEl('text', { class: 'tick', x: (x + bw / 2).toFixed(1), y: H - 5, 'text-anchor': 'middle' });
    tx.setAttribute('font-family', 'IBM Plex Mono, monospace');
    tx.setAttribute('font-size', '9.5');
    tx.setAttribute('fill', 'var(--ink3)');
    tx.textContent = String(y).slice(2);
    svg.appendChild(tx);
  });
}

/* ===========================================================================
   The comparison window, set once and obeyed everywhere
   Every change on this site is a change between two named years. Rather than
   bury that on one tab, the pair sits above every view and the whole page
   answers to it.
   ======================================================================== */
function yearBar() {
  const bar = el('div', 'yearbar');
  const opts = (sel, skip) => D.years.filter(y => y !== skip).map(y => {
    let tag = '';
    if (y === D.pdfYear) tag = ' — printed report';
    else if (y === D.years[0]) tag = ' — start of this data';
    else if (y === 2019) tag = ' — before the pandemic';
    return `<option value="${y}"${y === sel ? ' selected' : ''}>fiscal ${y}${tag}</option>`;
  }).join('');
  bar.innerHTML =
    `<span class="lbl">Compare</span>` +
    `<select id="y-to" aria-label="Year being compared">${opts(state.toYear)}</select>` +
    `<span class="lbl">with</span>` +
    `<select id="y-from" aria-label="Baseline year">${opts(state.fromYear)}</select>` +
    `<span class="lbl">calling it unchanged below</span>` +
    `<select id="y-flat" aria-label="Threshold for no material change">` +
    [[0, 'any change'], [0.01, '1%'], [0.02, '2%'], [0.05, '5%'], [0.1, '10%']].map(([v, l]) =>
      `<option value="${v}"${v === state.flat ? ' selected' : ''}>${l}</option>`).join('') + `</select>` +
    `<span class="spacer"></span>` +
    `<button class="chip" id="y-reset">Reset</button>`;
  bar.querySelector('#y-to').addEventListener('change', e => { state.toYear = +e.target.value; refresh(); });
  bar.querySelector('#y-from').addEventListener('change', e => { state.fromYear = +e.target.value; refresh(); });
  bar.querySelector('#y-flat').addEventListener('change', e => { state.flat = +e.target.value; refresh(); });
  bar.querySelector('#y-reset').addEventListener('click', () => {
    state.toYear = D.latest; state.fromYear = D.latest - 1; state.flat = 0.01; refresh(true);
  });
  return bar;
}
function refresh(rebuildBar) {
  if (state.fromYear === state.toYear) {
    state.fromYear = D.years[Math.max(0, D.yi[state.toYear] - 1)];
  }
  if (rebuildBar) {
    const old = $('.yearbar');
    if (old) old.replaceWith(yearBar());
  }
  drawMast();
  countBand();
  go(state.view);
  syncHash();
}

/* ===========================================================================
   Routing and boot
   ======================================================================== */
const VIEWS = { board: viewBoard, agencies: viewAgencies, search: viewSearch, outliers: viewOutliers, ratios: viewRatios, retired: viewRetired };

function go(v) {
  state.view = v;
  $$('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
  const host = $('#view');
  host.innerHTML = '';
  VIEWS[v](host);
  syncHash();
  window.scrollTo({ top: Math.min(window.scrollY, $('#tabs').offsetTop), behavior: 'auto' });
}
function syncHash() {
  if (location.hash.indexOf('#i/') === 0) return;
  let h = '#' + state.view;
  if (state.view === 'agencies' && state.agency != null) h += '/' + D.agencies[state.agency].c;
  if (state.view === 'search' && state.q) h += '/' + encodeURIComponent(state.q);
  if (state.view === 'outliers') h += '/' + state.measure + '/' + state.extreme;
  if (location.hash !== h) history.replaceState(null, '', h);
}
function fromHash() {
  const h = decodeURIComponent(location.hash.replace(/^#/, ''));
  if (!h) return go('board');
  const parts = h.split('/');
  if (parts[0] === 'i' && parts[1]) { go(state.view); openIndicator(parts[1]); return; }
  if (!VIEWS[parts[0]]) return go('board');
  if (parts[0] === 'agencies' && parts[1]) {
    const i = D.agencies.findIndex(a => a.c === parts[1]);
    if (i >= 0) state.agency = i;
  }
  if (parts[0] === 'search' && parts[1]) state.q = parts[1];
  if (parts[0] === 'outliers') {
    if (parts[1] && MEASURES.some(m => m.k === parts[1])) state.measure = parts[1];
    if (parts[2]) state.extreme = parts[2];
  }
  go(parts[0]);
}

function countBand() {
  const t = tally(D.live, state.fromYear, state.toYear);
  const withLatest = D.ind.filter(r => r.v[D.yi[state.toYear]] != null).length;
  $('#capline').innerHTML =
    `Full fiscal years <b>${D.years[0]}</b> to <b>${D.latest}</b>` +
    (D.pdfYear ? ` &nbsp;·&nbsp; fiscal ${D.pdfYear} is read from the <b>printed report</b>, not the open data, which still stops at ${monthName(D.partialThrough)} ${monthYear(D.partialThrough, D.partialFy)}` : '');
  const span = `fiscal ${String(state.fromYear).slice(2)}\u2192${String(state.toYear).slice(2)}`;
  const cells = [
    [D.ind.length.toLocaleString(), 'citywide indicators on file'],
    [D.agencies.length, 'agencies and initiatives'],
    [withLatest.toLocaleString(), 'filed a fiscal ' + state.toYear + ' figure'],
    [t.g.toLocaleString(), 'moved the city\'s way, ' + span, 'g'],
    [t.b.toLocaleString(), 'moved against it, ' + span, 'b'],
    [D.ind.filter(r => !r.dir).length.toLocaleString(), 'carry no direction the city will name'],
  ];
  $('#counts').innerHTML = cells.map(([v, l, c]) =>
    `<div><b class="${c || ''}">${v}</b><span>${l}</span></div>`).join('');
}

function boot(raw) {
  Object.assign(D, raw);
  D.yi = {}; D.years.forEach((y, i) => D.yi[y] = i);
  D.byId = {}; D.byAgency = D.agencies.map(() => []);
  D.ind.forEach(r => {
    D.byId[r.id] = r;
    D.byAgency[r.a].push(r);
    r._h = [
      r.n, D.agencies[r.a].n, D.agencies[r.a].c,
      r.d >= 0 ? D.desc[r.d] : '', r.g >= 0 ? D.goal[r.g] : '',
      r.s >= 0 ? D.svc[r.s] : '', r.src >= 0 ? D.src[r.src] : ''
    ].join(' ').toLowerCase();
  });
  D.live = D.ind.filter(r => !r.rt);
  state.toYear = D.latest;
  state.fromYear = D.years[D.yi[D.latest] - 1];
  D.loaded = true;

  $('#strip-range').innerHTML = `Fiscal ${D.years[0]} – fiscal ${D.latest}`;

  countBand();

  $('#footnote').innerHTML =
    `Built ${new Date().toISOString().slice(0, 10)} from dataset <a href="${esc(D.datasetUrl)}" target="_blank" rel="noopener">rbed-zzin</a> ` +
    `(${(768409).toLocaleString()} rows), the MMR agency resources tables, and the published agency chapters. ` +
    `<a href="methodology.html">Method, checks and known limits</a> &nbsp;·&nbsp; ` +
    `<a href="https://www.nyc.gov/site/operations/reports/mmr.page" target="_blank" rel="noopener">The report itself</a>`;

  $('#tabs').insertAdjacentElement('afterend', yearBar());
  drawMast();
  $$('#tabs button').forEach(b => b.addEventListener('click', () => go(b.dataset.v)));
  $('#drawer').addEventListener('click', e => { if (e.target.closest('[data-close]')) closeDrawer(); });
  window.addEventListener('hashchange', () => {
    const h = location.hash;
    if (h.indexOf('#i/') === 0) { openIndicator(h.slice(3)); return; }
    if ($('#drawer').classList.contains('open')) {
      $('#drawer').classList.remove('open');
      document.body.style.overflow = '';
      if (!h || h === '#' + state.view) return;   // the drawer's own close
    }
    fromHash();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && $('#drawer').classList.contains('open')) { closeDrawer(); return; }
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && !$('#drawer').classList.contains('open')) {
      e.preventDefault();
      if (state.view !== 'search') go('search');
      const q = $('#q'); if (q) q.focus();
    }
  });
  fromHash();
}

(function themeToggle() {
  const btn = document.getElementById('theme');
  const set = t => {
    document.documentElement.setAttribute('data-theme', t);
    btn.textContent = t === 'dark' ? 'Light' : 'Dark';
    try { localStorage.setItem('mmr-theme', t); } catch (e) { }
  };
  let t;
  try { t = localStorage.getItem('mmr-theme'); } catch (e) { }
  if (!t) t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  set(t);
  btn.addEventListener('click', () => set(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'));
})();

fetch('data/indicators.json')
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(boot)
  .catch(err => {
    $('#view').innerHTML = '<div class="empty">Could not load the data (' + esc(err.message) +
      '). This page needs <code>data/indicators.json</code> alongside it.</div>';
  });
