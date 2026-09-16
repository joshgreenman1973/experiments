/* Round and Round — weekly charts from data/findings/findings.json.
 * Plain SVG, no chart library. Every chart re-renders on resize and on its
 * zero-baseline toggle. */
(() => {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const css = getComputedStyle(document.documentElement);
  const C = name => css.getPropertyValue(name).trim();
  const COL = { ours: C('--ours'), base: C('--base'), mta: C('--mta'), rose: C('--rose'), ink: C('--ink'), ink2: C('--ink-2'), ink3: C('--ink-3') };
  const BORO_COL = code => C(`--b-${code}`) || COL.ink3;
  const BORO_NAME = { M: 'Manhattan', B: 'Brooklyn', Q: 'Queens', Bx: 'Bronx', S: 'Staten Island', X: 'Express' };

  const zero = {};      // chart key -> bool
  const renders = [];   // functions to re-run on resize
  let D = null;

  // ── formatting (AP style months) ──
  const AP = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  const AP_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dt = s => new Date(s + 'T12:00:00Z');
  const apDate = (s, year) => { const d = dt(s); return `${AP[d.getUTCMonth()]} ${d.getUTCDate()}${year ? ', ' + d.getUTCFullYear() : ''}`; };
  const apMonth = m => { const [y, mo] = m.split('-').map(Number); return `${AP[mo - 1].replace('.', '')} ${y}`.replace('Sept', 'September').replace('Jan ', 'January ').replace('Feb ', 'February ').replace('Aug ', 'August ').replace('Oct ', 'October ').replace('Nov ', 'November ').replace('Dec ', 'December '); };
  const num = n => n == null ? '–' : n.toLocaleString('en-US');
  const f1 = n => n == null ? '–' : (Math.round(n * 10) / 10).toFixed(1);
  const hourName = h => h === 0 ? 'midnight' : h === 12 ? 'noon' : `${((h + 11) % 12) + 1} ${h < 12 ? 'a.m.' : 'p.m.'}`;
  const hourTick = h => h === 0 ? '12a' : h === 12 ? 'noon' : `${((h + 11) % 12) + 1}${h < 12 ? 'a' : 'p'}`;

  // ── svg helpers ──
  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function txt(parent, x, y, s, attrs = {}) { const t = el('text', { x, y, ...attrs }, parent); t.textContent = s; return t; }
  const lin = (d0, d1, r0, r1) => { const k = (r1 - r0) / ((d1 - d0) || 1); const f = v => r0 + (v - d0) * k; f.inv = p => d0 + (p - r0) / k; return f; };

  function niceTicks(lo, hi, n = 4) {
    const span = hi - lo || 1;
    const step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 1000) / 1000);
    return { ticks: out, lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step };
  }
  // minSpan keeps a flat series looking flat: a 0.3 mph wobble should not fill the chart.
  function yDomain(values, useZero, padFrac = 0.12, minSpan = 0) {
    const v = values.filter(x => x != null);
    let lo = Math.min(...v), hi = Math.max(...v);
    if (hi - lo < minSpan) { const c = (hi + lo) / 2; lo = c - minSpan / 2; hi = c + minSpan / 2; }
    const pad = (hi - lo || hi || 1) * padFrac;
    lo = useZero ? 0 : lo - pad; hi = hi + pad;
    return niceTicks(Math.max(useZero ? 0 : lo, lo), hi);
  }

  function frame(host, h) {
    host.innerHTML = '';
    const w = host.clientWidth;
    const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, height: h }, host);
    return { svg, w, h };
  }

  // ── tooltip ──
  const tip = document.getElementById('tip');
  function showTip(evt, html) {
    tip.innerHTML = html; tip.hidden = false;
    const pad = 14, r = tip.getBoundingClientRect();
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - pad;
    tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
  }
  const hideTip = () => { tip.hidden = true; };
  const row = (k, v) => `<div class="t-r"><span>${k}</span><b>${v}</b></div>`;

  function hoverLayer(svg, m, w, h, onMove) {
    const guide = el('line', { class: 'guide', y1: m.t, y2: h - m.b, visibility: 'hidden' }, svg);
    const hit = el('rect', { x: m.l, y: m.t, width: Math.max(0, w - m.l - m.r), height: Math.max(0, h - m.t - m.b), fill: 'transparent' }, svg);
    const move = e => {
      const pt = svg.getBoundingClientRect();
      const px = (e.clientX - pt.left) * (w / pt.width), py = (e.clientY - pt.top) * (h / pt.height);
      const res = onMove(px, py, e);
      if (res && res.x != null) { guide.setAttribute('x1', res.x); guide.setAttribute('x2', res.x); guide.setAttribute('visibility', res.noGuide ? 'hidden' : 'visible'); }
      else { guide.setAttribute('visibility', 'hidden'); hideTip(); }
    };
    hit.addEventListener('pointermove', move);
    hit.addEventListener('pointerdown', move);
    hit.addEventListener('pointerleave', () => { guide.setAttribute('visibility', 'hidden'); hideTip(); });
    return guide;
  }

  // ── chart: one weekly system measure ──
  function weeklyChart(host, key, cfg) {
    const H = +host.dataset.h;
    const { svg, w, h } = frame(host, H);
    const m = { t: cfg.first ? 44 : 30, r: 58, b: cfg.last ? 26 : 10, l: 38 };
    const S = D.system;
    const t0 = dt(S[0].start).getTime(), t1 = dt(S[S.length - 1].end).getTime();
    const x = lin(t0, t1, m.l, w - m.r);
    const mid = s => (dt(s.start).getTime() + dt(s.end).getTime()) / 2;
    // Scale to the usable weeks; unreliable weeks outside that range are left off.
    const yd = yDomain(S.filter(s => s.comparable).map(s => s[key]), zero.weekly, 0.12, cfg.minSpan);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);

    txt(svg, 0, 14, cfg.title, { class: 'ctitle' });
    txt(svg, 0, 14, '', { class: 'csub' });
    const sub = svg.lastChild; sub.textContent = cfg.sub; sub.setAttribute('x', svg.firstChild.getComputedTextLength ? svg.firstChild.getComputedTextLength() + 8 : 120);

    // bands for the two comparison periods
    const P = D.periods;
    for (const [p, label] of [[P.baseline, 'first weeks'], [P.recent, 'recent weeks']]) {
      const bx0 = x(dt(p.start).getTime()), bx1 = x(dt(p.end).getTime() + 86400000);
      el('rect', { class: 'band', x: bx0, y: m.t, width: bx1 - bx0, height: h - m.t - m.b }, svg);
      if (cfg.first) txt(svg, bx0 + 4, m.t - 6, label, { class: 'band-label' });
    }

    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) {
      if (v < yd.lo || v > yd.hi) continue;
      el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g);
      txt(svg, m.l - 8, y(v) + 4, cfg.fmt(v), { 'text-anchor': 'end' });
    }
    if (cfg.last) {
      const d = new Date(t0); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1);
      for (; d.getTime() <= t1; d.setUTCMonth(d.getUTCMonth() + 1)) {
        const px = x(d.getTime());
        el('line', { x1: px, x2: px, y1: h - m.b, y2: h - m.b + 5, stroke: COL.ink3 }, svg);
        txt(svg, px + 3, h - 6, AP_SHORT[d.getUTCMonth()]);
      }
    }

    // line through usable weeks; break where a week is missing
    let dpath = '', prev = null;
    for (const s of S) {
      if (!s.comparable || s[key] == null) { prev = null; continue; }
      const px = x(mid(s)), py = y(s[key]);
      dpath += (prev && dt(s.start) - dt(prev.start) <= 8 * 86400000 ? 'L' : 'M') + px.toFixed(1) + ',' + py.toFixed(1);
      prev = s;
    }
    el('path', { d: dpath, fill: 'none', stroke: COL.ours, 'stroke-width': 2.2, 'stroke-linejoin': 'round' }, svg);
    for (const s of S) {
      if (s[key] == null) continue;
      const c = s.comparable;
      if (!c && (s[key] < yd.lo || s[key] > yd.hi)) continue;
      el('circle', { cx: x(mid(s)), cy: y(s[key]), r: c ? 3 : 3.5, fill: c ? COL.ours : 'none', stroke: c ? 'none' : COL.ink2, 'stroke-width': 1.3 }, svg);
    }
    const lastC = [...S].reverse().find(s => s.comparable && s[key] != null);
    if (lastC) txt(svg, x(mid(lastC)) + 9, y(lastC[key]) + 4, cfg.fmt(lastC[key], true), { class: 'dlabel', fill: COL.ours });

    hoverLayer(svg, m, w, h, (px, py, e) => {
      const t = x.inv(px);
      let best = null;
      for (const s of S) if (s[key] != null && (!best || Math.abs(mid(s) - t) < Math.abs(mid(best) - t))) best = s;
      if (!best) return null;
      showTip(e, `<div class="t-h">${apDate(best.start)} to ${apDate(best.end)}</div>`
        + row(cfg.title, cfg.fmt(best[key], true))
        + row('Buses in service', num(best.buses))
        + row('Hours captured', best.coverage + '%')
        + (best.comparable ? '' : '<div class="t-n">Too little of the day captured to compare.</div>'));
      return { x: x(mid(best)) };
    });
  }

  // ── chart: shape of the day ──
  const dayMetric = 'speed';
  const DAY_CFG = {
    speed: { label: 'Speed', unit: ' mph', fmt: v => f1(v), sub: 'miles per hour' },
  };
  function dayChart() {
    const host = document.getElementById('chart-day');
    const { svg, w, h } = frame(host, +host.dataset.h);
    const m = { t: 34, r: 64, b: 28, l: 38 };
    const R = D.dayShape.recent, B = D.dayShape.baseline;
    const hours = R.map(r => r.hour);
    const bHour = Object.fromEntries(B.map(b => [b.hour, b]));
    const x = lin(0, hours.length - 1, m.l + 12, w - m.r - 12);
    const cfg = DAY_CFG[dayMetric];
    const yd = yDomain([...R.map(r => r[dayMetric]), ...B.map(b => b[dayMetric])], zero.day);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);

    txt(svg, 0, 14, cfg.label, { class: 'ctitle' });
    txt(svg, 0, 30, cfg.sub + ', by hour of the day', { class: 'csub' });

    // buses in service, as quiet bars on their own scale
    const maxB = Math.max(...R.map(r => r.buses));
    const bw = Math.max(4, (x(1) - x(0)) * 0.62);
    const barTop = m.t + (h - m.t - m.b) * 0.45;
    for (let i = 0; i < R.length; i++) {
      const bh = (R[i].buses / maxB) * (h - m.b - barTop);
      el('rect', { x: x(i) - bw / 2, y: h - m.b - bh, width: bw, height: bh, fill: 'rgba(255,255,255,0.05)' }, svg);
    }
    txt(svg, w - m.r + 8, h - m.b - (h - m.b - barTop) + 4, `${num(maxB)} buses`, { fill: COL.ink3 });
    el('line', { x1: w - m.r, x2: w - m.r + 5, y1: barTop, y2: barTop, stroke: COL.ink3 }, svg);

    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) {
      if (v < yd.lo || v > yd.hi) continue;
      el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g);
      txt(svg, m.l - 8, y(v) + 4, cfg.fmt(v), { 'text-anchor': 'end' });
    }
    hours.forEach((hr, i) => { if (hr % 3 === 0) txt(svg, x(i), h - 8, hourTick(hr), { 'text-anchor': 'middle' }); });

    const path = (arr, get) => arr.map((r, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(get(r)).toFixed(1)).join('');
    const bIdx = hours.map((hr, i) => [i, bHour[hr]]).filter(([, b]) => b && b[dayMetric] != null);
    el('path', { d: bIdx.map(([i, b], k) => (k ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(b[dayMetric]).toFixed(1)).join(''), fill: 'none', stroke: COL.base, 'stroke-width': 1.5 }, svg);
    el('path', { d: path(R, r => r[dayMetric]), fill: 'none', stroke: COL.ours, 'stroke-width': 2.6, 'stroke-linejoin': 'round' }, svg);
    R.forEach((r, i) => el('circle', { cx: x(i), cy: y(r[dayMetric]), r: 2.6, fill: COL.ours }, svg));

    hoverLayer(svg, m, w, h, (px, py, e) => {
      const i = Math.max(0, Math.min(R.length - 1, Math.round(x.inv(px))));
      const r = R[i], b = bHour[r.hour];
      showTip(e, `<div class="t-h">${hourName(r.hour)} to ${hourName((r.hour + 1) % 24)}</div>`
        + row('Recent weeks', cfg.fmt(r[dayMetric]) + cfg.unit)
        + (b ? row('First weeks', cfg.fmt(b[dayMetric]) + cfg.unit) : '')
        + row('Buses in service', num(r.buses)));
      return { x: x(i) };
    });
  }

  // ── chart: boroughs ──
  const boroMetric = 'speed';
  function boroChart() {
    const host = document.getElementById('chart-boro');
    const { svg, w, h } = frame(host, +host.dataset.h);
    const m = { t: 34, r: 128, b: 28, l: 38 };
    const S = D.system;
    const t0 = dt(S[0].start).getTime(), t1 = dt(S[S.length - 1].end).getTime();
    const x = lin(t0, t1, m.l, w - m.r);
    const all = D.boroughs.flatMap(b => b.series.filter(s => s.comparable).map(s => s[boroMetric]));
    const yd = yDomain(all, zero.boro, 0.06);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);
    const unit = ' mph';

    txt(svg, 0, 14, 'Speed', { class: 'ctitle' });
    txt(svg, 0, 30, boroMetric === 'speed' ? 'miles per hour, usable weeks' : 'minutes at a stop, usable weeks', { class: 'csub' });

    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) {
      if (v < yd.lo || v > yd.hi) continue;
      el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g);
      txt(svg, m.l - 8, y(v) + 4, String(v), { 'text-anchor': 'end' });
    }
    const d = new Date(t0); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1);
    for (; d.getTime() <= t1; d.setUTCMonth(d.getUTCMonth() + 1)) txt(svg, x(d.getTime()) + 3, h - 8, AP_SHORT[d.getUTCMonth()]);

    const mid = s => dt(s.start).getTime() + 3.5 * 86400000;
    const ends = [];
    for (const b of D.boroughs) {
      let dp = '', prev = null, lastPt = null;
      for (const s of b.series) {
        if (!s.comparable || s[boroMetric] == null) { prev = null; continue; }
        dp += (prev && dt(s.start) - dt(prev.start) <= 8 * 86400000 ? 'L' : 'M') + x(mid(s)).toFixed(1) + ',' + y(s[boroMetric]).toFixed(1);
        prev = s; lastPt = s;
      }
      const col = BORO_COL(b.code);
      el('path', { d: dp, fill: 'none', stroke: col, 'stroke-width': 2, 'stroke-linejoin': 'round', opacity: b.code === 'X' ? 0.7 : 1 }, svg);
      if (lastPt) ends.push({ y: y(lastPt[boroMetric]), label: `${b.name} ${f1(lastPt[boroMetric])}`, col, x: x(mid(lastPt)) });
    }
    // dodge end labels so they don't collide
    ends.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
    for (const e of ends) txt(svg, e.x + 10, e.y + 4, e.label, { class: 'dlabel', fill: e.col });

    const weeks = S.filter(s => s.comparable);
    hoverLayer(svg, m, w, h, (px, py, e) => {
      const t = x.inv(px);
      const best = weeks.reduce((a, s) => (Math.abs(mid(s) - t) < Math.abs(mid(a) - t) ? s : a), weeks[0]);
      const vals = D.boroughs.map(b => ({ b, v: b.series.find(s => s.week === best.week)?.[boroMetric] })).filter(r => r.v != null).sort((p, q) => q.v - p.v);
      showTip(e, `<div class="t-h">${apDate(best.start)} to ${apDate(best.end)}</div>` + vals.map(r => row(`<span style="color:${BORO_COL(r.b.code)}">●</span> ${r.b.name}`, f1(r.v) + unit)).join(''));
      return { x: x(mid(best)) };
    });
  }

  // ── chart: routes scatter ──
  const boroOn = { M: true, B: true, Q: true, Bx: true, S: true, X: true };
  function routesChart() {
    const host = document.getElementById('chart-routes');
    const { svg, w, h } = frame(host, +host.dataset.h);
    const m = { t: 34, r: 16, b: 40, l: 44 };
    const R = D.routes.filter(r => boroOn[r.borough] !== false);
    const xs = D.routes.map(r => r.speed), ys = D.routes.map(r => r.riders || 0);
    const xd = niceTicks(Math.min(...xs) - 0.3, Math.max(...xs) + 0.3, 6);
    const yd = niceTicks(0, Math.max(...ys) * 1.08, 4);
    const x = lin(xd.lo, xd.hi, m.l, w - m.r), y = lin(0, yd.hi, h - m.b, m.t);
    const rad = () => (w < 600 ? 4.5 : 6);

    txt(svg, 0, 14, 'Speed against riders', { class: 'ctitle' });
    txt(svg, 0, 30, 'one dot per route', { class: 'csub' });
    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) { el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g); txt(svg, m.l - 8, y(v) + 4, v >= 1000 ? (v / 1000) + 'k' : String(v), { 'text-anchor': 'end' }); }
    for (const v of xd.ticks) { el('line', { x1: x(v), x2: x(v), y1: m.t, y2: h - m.b }, g); txt(svg, x(v), h - m.b + 16, String(v), { 'text-anchor': 'middle' }); }
    txt(svg, w - m.r, h - 4, 'miles per hour →', { 'text-anchor': 'end' });
    txt(svg, m.l + 4, m.t + 12, '↑ weekday riders');

    for (const r of R) el('circle', { cx: x(r.speed), cy: y(r.riders || 0), r: rad(r), fill: BORO_COL(r.borough), 'fill-opacity': 0.55, stroke: BORO_COL(r.borough), 'stroke-width': 1 }, svg);

    const pick = new Set([
      ...[...R].sort((a, b) => a.speed - b.speed).slice(0, 3),
      ...[...R].sort((a, b) => (b.riders || 0) - (a.riders || 0)).slice(0, 5),
      ...[...R].sort((a, b) => b.speed - a.speed).slice(0, 2),
    ]);
    for (const r of pick) {
      const right = x(r.speed) < w * 0.8;
      txt(svg, x(r.speed) + (right ? rad(r) + 4 : -rad(r) - 4), y(r.riders || 0) + 4, r.route, { class: 'rlabel', 'text-anchor': right ? 'start' : 'end' });
    }

    hoverLayer(svg, m, w, h, (px, py, e) => {
      let best = null, bd = 1e9;
      for (const r of R) { const dd = Math.hypot(x(r.speed) - px, y(r.riders || 0) - py); if (dd < bd) { bd = dd; best = r; } }
      if (!best || bd > 28) return null;
      showTip(e, `<div class="t-h"><span style="color:${BORO_COL(best.borough)}">●</span> ${best.route}</div>`
        + row('Speed', f1(best.speed) + ' mph')
        + row('Weekday riders', best.riders ? num(best.riders) : 'not in counter data')
        + (best.busLaneShare != null ? row('Route on bus lanes', Math.round(best.busLaneShare * 100) + '%') : ''));
      return { x: x(best.speed), noGuide: true };
    });
  }

  function slowestList() {
    const ol = document.getElementById('slowest');
    ol.innerHTML = D.routes.slice(0, 10).map(r =>
      `<li><b>${r.route}</b><i style="background:${BORO_COL(r.borough)}"></i>${f1(r.speed)} mph</li>`).join('');
  }

  // ── chart: riders ──
  function ridersChart() {
    const host = document.getElementById('chart-riders');
    const { svg, w, h } = frame(host, +host.dataset.h);
    const m = { t: 34, r: 60, b: 28, l: 48 };
    const S = D.ridership.series;
    const x = lin(0, S.length - 1, m.l + 6, w - m.r);
    const yd = yDomain([...S.map(s => s.riders), ...S.map(s => s.priorYear)], zero.riders, 0.08);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);
    txt(svg, 0, 14, 'Average weekday boardings', { class: 'ctitle' });
    txt(svg, 0, 30, 'millions', { class: 'csub' });
    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) { if (v < yd.lo || v > yd.hi) continue; el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g); txt(svg, m.l - 8, y(v) + 4, (v / 1e6).toFixed(v % 1e6 ? 2 : 0), { 'text-anchor': 'end' }); }
    S.forEach((s, i) => { const mo = +s.month.slice(5); if (mo === 1 || i === 0) txt(svg, x(i), h - 8, (mo === 1 ? '' : AP_SHORT[mo - 1] + ' ') + s.month.slice(0, 4), { 'text-anchor': 'start' }); else if (mo % 3 === 1) txt(svg, x(i), h - 8, AP_SHORT[mo - 1], { 'text-anchor': 'middle' }); });

    const seg = (get) => { let d = '', on = false; S.forEach((s, i) => { const v = get(s); if (v == null) { on = false; return; } d += (on ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1); on = true; }); return d; };
    el('path', { d: seg(s => s.priorYear), fill: 'none', stroke: COL.ink3, 'stroke-width': 1.5, 'stroke-dasharray': '4 4' }, svg);
    el('path', { d: seg(s => s.riders), fill: 'none', stroke: COL.rose, 'stroke-width': 2.4, 'stroke-linejoin': 'round' }, svg);
    S.forEach((s, i) => el('circle', { cx: x(i), cy: y(s.riders), r: 2.5, fill: COL.rose }, svg));
    const L = S[S.length - 1];
    txt(svg, x(S.length - 1) + 8, y(L.riders) + 4, (L.riders / 1e6).toFixed(2) + 'M', { class: 'dlabel', fill: COL.rose });

    hoverLayer(svg, m, w, h, (px, py, e) => {
      const i = Math.max(0, Math.min(S.length - 1, Math.round(x.inv(px))));
      const s = S[i];
      const diff = s.priorYear ? Math.round((s.riders / s.priorYear - 1) * 1000) / 10 : null;
      showTip(e, `<div class="t-h">${apMonth(s.month)}</div>` + row('Weekday average', num(s.riders))
        + (s.priorYear ? row('Same month a year earlier', num(s.priorYear)) + row('Change', (diff > 0 ? '+' : '') + diff + '%') : ''));
      return { x: x(i) };
    });
  }

  // ── MTA comparison (present once data/mta/official.json exists) ──
  function officialBlock() {
    const O = D.official;
    if (!O) return;
    document.getElementById('official-block').hidden = false;
    document.getElementById('official-copy').innerHTML = O.intro || '';
    const main = document.getElementById('official-main');
    main.innerHTML = '';
    if (O.speedSeries && O.speedSeries.months?.length) {
      main.insertAdjacentHTML('beforeend', `<div class="chart-head"><p class="legend" style="margin-right:auto"><span><i class="sw ours"></i><b>Our estimate</b></span><span><i class="sw mta"></i><b>${O.speedSeries.mtaLabel || 'MTA published'}</b></span></p><label class="zero"><input type="checkbox" data-zero="official" /> Start y-axis at zero</label></div><div class="chart" id="chart-official" data-h="260"></div>`);
      renders.push(officialChart);
      officialChart();
      bindZero(main);
    }
    if (O.metrics?.length) {
      main.insertAdjacentHTML('beforeend', `<table class="cmp-table"><thead><tr><th>Measure</th><th>Ours</th><th>MTA</th><th>Why they differ</th></tr></thead><tbody>${
        O.metrics.map(r => `<tr><td>${r.label}<br><span style="color:var(--ink-3);font-size:12px">${r.period || ''}</span></td><td class="num ours">${r.ours}</td><td class="num mta">${r.mta}</td><td class="why">${r.why || ''}</td></tr>`).join('')}</tbody></table>`);
    }
    if (O.flags?.length) {
      main.insertAdjacentHTML('beforeend', `<ul class="flags">${O.flags.map(f => `<li><b>${f.head}</b>${f.text}${f.detail ? `<span>${f.detail}</span>` : ''}</li>`).join('')}</ul>`);
    }
    if (O.sources?.length) {
      main.insertAdjacentHTML('beforeend', `<p class="note" style="margin-top:24px;color:var(--ink-3);font-size:12.5px">MTA sources: ${O.sources.map(s => `<a href="${s.url}" target="_blank" rel="noopener">${s.name}</a> (through ${s.through})`).join('; ')}. Pulled ${apDate(O.fetchedAt.slice(0, 10), true)}.</p>`);
    }
  }
  function officialChart() {
    const host = document.getElementById('chart-official');
    if (!host) return;
    const O = D.official.speedSeries;
    const { svg, w, h } = frame(host, +host.dataset.h);
    const m = { t: 34, r: 56, b: 28, l: 38 };
    const n = O.months.length;
    const x = lin(0, n - 1, m.l + 10, w - m.r);
    const yd = yDomain([...O.ours, ...O.mta], zero.official, 0.12, 2);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);
    txt(svg, 0, 14, O.title || 'Average bus speed', { class: 'ctitle' });
    txt(svg, 0, 30, O.sub || 'miles per hour, by month', { class: 'csub' });
    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) { if (v < yd.lo || v > yd.hi) continue; el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g); txt(svg, m.l - 8, y(v) + 4, String(v), { 'text-anchor': 'end' }); }
    const step = Math.ceil(n / Math.max(4, Math.floor((w - 100) / 60)));
    O.months.forEach((mo, i) => { if (i % step === 0) txt(svg, x(i), h - 8, AP_SHORT[+mo.slice(5) - 1] + (mo.slice(5) === '01' || i === 0 ? ' ' + mo.slice(0, 4) : ''), { 'text-anchor': 'middle' }); });
    const line = (arr, col, wd) => {
      let d = '', on = false;
      arr.forEach((v, i) => { if (v == null) { on = false; return; } d += (on ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1); on = true; });
      el('path', { d, fill: 'none', stroke: col, 'stroke-width': wd, 'stroke-linejoin': 'round' }, svg);
      arr.forEach((v, i) => { if (v != null) el('circle', { cx: x(i), cy: y(v), r: 2.8, fill: col }, svg); });
    };
    line(O.mta, COL.mta, 2.2); line(O.ours, COL.ours, 2.2);
    hoverLayer(svg, m, w, h, (px, py, e) => {
      const i = Math.max(0, Math.min(n - 1, Math.round(x.inv(px))));
      showTip(e, `<div class="t-h">${apMonth(O.months[i])}</div>` + row('Our estimate', O.ours[i] != null ? f1(O.ours[i]) + ' mph' : 'not collected')
        + row('MTA', O.mta[i] != null ? f1(O.mta[i]) + ' mph' : 'not yet published') + (O.notes?.[i] ? `<div class="t-n">${O.notes[i]}</div>` : ''));
      return { x: x(i) };
    });
  }

  // ── text ──
  function copy() {
    const T = D.totals, A = D.asOf, P = D.periods;
    document.getElementById('dek').textContent =
      `What ${T.weeksElapsed} weeks of watching every New York City bus has shown so far: how fast they move, how many are on the road and how many people ride.`;
    document.getElementById('edition').innerHTML =
      `Updated every Monday. This edition runs through <b>${apDate(A.end, true)}</b>, with ${T.comparableWeeks} usable weeks out of ${T.weeksElapsed} and ${num(T.snapshots)} snapshots of the fleet since ${apDate(T.firstDate)}.`;
    document.getElementById('learned').innerHTML = D.learned.map(l => `<li><b>${l.head}</b>${l.text}</li>`).join('');
    document.getElementById('day-recent-label').textContent = `Recent weeks, ${apDate(P.recent.start)} to ${apDate(P.recent.end)}`;
    document.getElementById('day-base-label').textContent = `First weeks, ${apDate(P.baseline.start)} to ${apDate(P.baseline.end)}`;
    document.getElementById('riders-copy').textContent =
      `Average weekday boardings across the system through ${apMonth(D.ridership.lastMonth)}, counted by the MTA's on-board passenger counters. The dashed line is the same month a year earlier.`;
  }

  // ── controls ──
  function bindZero(scope) {
    scope.querySelectorAll('input[data-zero]').forEach(inp => {
      if (inp.dataset.bound) return; inp.dataset.bound = 1;
      inp.checked = !!zero[inp.dataset.zero];
      inp.addEventListener('change', () => { zero[inp.dataset.zero] = inp.checked; renderAll(); });
    });
  }
  function bindSeg(id, set) {
    const box = document.getElementById(id);
    box.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      box.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
      set(b.dataset.m); renderAll();
    });
  }
  function chips() {
    const box = document.getElementById('boro-chips');
    const present = [...new Set(D.routes.map(r => r.borough))].filter(c => BORO_NAME[c]);
    box.innerHTML = present.map(c => `<button data-b="${c}"><i style="background:${BORO_COL(c)}"></i>${BORO_NAME[c]}</button>`).join('');
    box.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      boroOn[b.dataset.b] = !boroOn[b.dataset.b];
      b.classList.toggle('off', !boroOn[b.dataset.b]);
      routesChart();
    });
  }
  function caution() {
    const btn = document.getElementById('ai-caution-btn'), pop = document.getElementById('ai-caution-pop');
    btn.addEventListener('click', e => { e.stopPropagation(); pop.hidden = !pop.hidden; });
    document.addEventListener('click', e => { if (!e.target.closest('.caution-wrap')) pop.hidden = true; });
  }

  function renderAll() {
    weeklyChart(document.getElementById('chart-speed'), 'speed', { title: 'Speed', sub: 'miles per hour', fmt: (v, u) => f1(v) + (u ? ' mph' : ''), first: true, minSpan: 2 });
    weeklyChart(document.getElementById('chart-buses'), 'buses', { title: 'Buses in service', sub: 'average at any moment', fmt: (v) => num(Math.round(v)), last: true, minSpan: 600 });
    dayChart(); boroChart(); routesChart(); ridersChart();
    for (const r of renders) r();
  }

  async function init() {
    caution();
    try {
      const res = await fetch('data/findings/findings.json?t=' + Date.now().toString().slice(0, -6), { cache: 'no-cache' });
      if (!res.ok) throw new Error(res.status);
      D = await res.json();
    } catch (e) {
      document.getElementById('learned').innerHTML = `<li>The findings file did not load (${e.message}). Try again shortly.</li>`;
      return;
    }
    copy(); chips(); slowestList(); officialBlock();
    bindZero(document);
    renderAll();
    let t; new ResizeObserver(() => { clearTimeout(t); t = setTimeout(renderAll, 120); }).observe(document.querySelector('.page'));
  }
  init();
})();
