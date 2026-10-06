/* Small SVG chart kit shared by route.html and compare.html. No library.
 * Styling comes from findings.css (.chart, .grid, .ctitle, .tip ...). */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const css = getComputedStyle(document.documentElement);
  const C = n => css.getPropertyValue(n).trim();
  const COL = { ours: C('--ours'), base: C('--base'), mta: C('--mta'), rose: C('--rose'), ink: C('--ink'), ink2: C('--ink-2'), ink3: C('--ink-3') };
  const EV_COL = { holiday: '#9b9fbc', gap: '#d2232a', weather: '#4fb3e8', method: '#dde44c', network: '#ff7c53' };
  const AP = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  const AP_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dt = s => new Date(s + 'T12:00:00Z');
  const apDate = (s, year) => { const d = dt(s); return `${AP[d.getUTCMonth()]} ${d.getUTCDate()}${year ? ', ' + d.getUTCFullYear() : ''}`; };
  const hourName = h => (h === 0 ? 'midnight' : h === 12 ? 'noon' : `${((h + 11) % 12) + 1} ${h < 12 ? 'a.m.' : 'p.m.'}`);
  const hourTick = h => (h === 12 ? 'noon' : `${((h + 11) % 12) + 1}${h < 12 ? 'a' : 'p'}`);

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  const txt = (p, x, y, s, a = {}) => { const t = el('text', { x, y, ...a }, p); t.textContent = s; return t; };
  const lin = (d0, d1, r0, r1) => { const k = (r1 - r0) / ((d1 - d0) || 1); const f = v => r0 + (v - d0) * k; f.inv = p => d0 + (p - r0) / k; return f; };
  function niceTicks(lo, hi, n = 4) {
    const span = hi - lo || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 1000) / 1000);
    return { ticks: out, lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step };
  }
  function yDomain(values, useZero, minSpan = 0) {
    const v = values.filter(x => x != null && Number.isFinite(x));
    if (!v.length) return niceTicks(0, 1);
    let lo = Math.min(...v), hi = Math.max(...v);
    if (hi - lo < minSpan) { const c = (hi + lo) / 2; lo = c - minSpan / 2; hi = c + minSpan / 2; }
    const pad = (hi - lo || hi || 1) * 0.12;
    return niceTicks(useZero ? 0 : lo - pad, hi + pad);
  }
  function frame(host, h) {
    host.innerHTML = '';
    const w = Math.max(320, host.clientWidth || 640);
    return { svg: el('svg', { viewBox: `0 0 ${w} ${h}`, height: h }, host), w, h };
  }
  const tip = document.getElementById('tip');
  function showTip(evt, html) {
    if (!tip) return;
    tip.innerHTML = html; tip.hidden = false;
    const pad = 14, r = tip.getBoundingClientRect();
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - pad;
    tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
  }
  const hideTip = () => { if (tip) tip.hidden = true; };
  const row = (k, v) => `<div class="t-r"><span>${k}</span><b>${v}</b></div>`;
  function hover(svg, m, w, h, onMove) {
    const guide = el('line', { class: 'guide', y1: m.t, y2: h - m.b, visibility: 'hidden' }, svg);
    const hit = el('rect', { x: m.l, y: m.t, width: Math.max(0, w - m.l - m.r), height: Math.max(0, h - m.t - m.b + 14), fill: 'transparent' }, svg);
    const move = e => {
      const b = svg.getBoundingClientRect();
      const px = (e.clientX - b.left) * (w / b.width), py = (e.clientY - b.top) * (h / b.height);
      const res = onMove(px, py, e);
      if (res && res.x != null) { guide.setAttribute('x1', res.x); guide.setAttribute('x2', res.x); guide.setAttribute('visibility', 'visible'); }
      else { guide.setAttribute('visibility', 'hidden'); hideTip(); }
    };
    hit.addEventListener('pointermove', move);
    hit.addEventListener('pointerdown', move);
    hit.addEventListener('pointerleave', () => { guide.setAttribute('visibility', 'hidden'); hideTip(); });
  }
  function grid(svg, m, w, yd, y, fmt) {
    const g = el('g', { class: 'grid' }, svg);
    for (const v of yd.ticks) {
      if (v < yd.lo || v > yd.hi) continue;
      el('line', { x1: m.l, x2: w - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : null }, g);
      txt(svg, m.l - 8, y(v) + 4, fmt(v), { 'text-anchor': 'end' });
    }
  }

  /** Time series. cfg.series: [{ label, color, width, dash, opacity, points:
   *  [{ d: 'YYYY-MM-DD' (center), v, hollow, note }], marker: 'dot'|'square',
   *  gapDays (break the line when points are further apart) }]. */
  function timeChart(host, cfg) {
    const H = +host.dataset.h || 220;
    const { svg, w, h } = frame(host, H);
    const m = { t: 34, r: 58, b: 34, l: 40 };
    // Keep only points inside the requested window.
    if (cfg.start || cfg.end) {
      const lo = cfg.start ? dt(cfg.start).getTime() - 20 * 864e5 : -Infinity, hi = cfg.end ? dt(cfg.end).getTime() + 20 * 864e5 : Infinity;
      cfg = { ...cfg, series: cfg.series.map(s => ({ ...s, points: s.points.filter(p => { const t = dt(p.d).getTime(); return t >= lo && t <= hi; }) })) };
    }
    const all = cfg.series.flatMap(s => s.points.filter(p => p.v != null));
    if (!all.length) { txt(svg, 0, 18, cfg.empty || 'No comparable data yet.', { class: 'csub' }); return; }
    const ts = all.map(p => dt(p.d).getTime());
    const t0 = cfg.start ? dt(cfg.start).getTime() : Math.min(...ts), t1 = cfg.end ? dt(cfg.end).getTime() : Math.max(...ts);
    const x = lin(t0 - 16 * 864e5, t1 + 16 * 864e5, m.l, w - m.r);
    const yd = yDomain(all.filter(p => !p.hollow).map(p => p.v), cfg.zero, cfg.minSpan || 0);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);
    txt(svg, 0, 14, cfg.title, { class: 'ctitle' });
    if (cfg.sub) txt(svg, 0, 28, cfg.sub, { class: 'csub' });
    grid(svg, m, w, yd, y, cfg.fmt);
    const d = new Date(t0); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1);
    const months = Math.max(1, (t1 - t0) / (30 * 864e5));
    for (; d.getTime() <= t1 + 3 * 864e5; d.setUTCMonth(d.getUTCMonth() + 1)) {
      if (months > 14 && d.getUTCMonth() % 3) continue;
      const px = x(d.getTime());
      el('line', { x1: px, x2: px, y1: h - m.b, y2: h - m.b + 5, stroke: COL.ink3 }, svg);
      txt(svg, px + 3, h - m.b + 15, AP_SHORT[d.getUTCMonth()] + (d.getUTCMonth() === 0 ? ` ${d.getUTCFullYear()}` : ''));
    }
    // shaded periods
    for (const b of cfg.bands || []) {
      const a = x(dt(b.start).getTime()), z = x(dt(b.end).getTime() + 864e5);
      el('rect', { class: 'band', x: a, y: m.t, width: Math.max(0, z - a), height: Math.max(0, h - m.t - m.b) }, svg);
      if (b.label) txt(svg, a + 4, m.t - 4, b.label, { class: 'band-label' });
    }
    // events
    const evs = (cfg.events || []).filter(e => { const t = dt(e.date).getTime(); return t >= t0 - 4 * 864e5 && t <= t1 + 4 * 864e5; });
    for (const e of evs) {
      const a = x(dt(e.date).getTime()), b = e.end ? x(dt(e.end).getTime() + 864e5) : a + 3;
      el('rect', { x: a, y: h - m.b + 20, width: Math.max(3, b - a), height: 5, fill: EV_COL[e.kind] || COL.ink3, opacity: 0.85 }, svg);
      if (e.kind === 'method' || e.kind === 'network') el('line', { x1: a, x2: a, y1: m.t, y2: h - m.b, stroke: EV_COL[e.kind], 'stroke-dasharray': '2 4', opacity: 0.5 }, svg);
    }
    for (const s of cfg.series) {
      const pts = s.points.filter(p => p.v != null && !p.hollow).sort((p, q) => p.d.localeCompare(q.d));
      let path = '', prev = null;
      for (const p of pts) {
        const px = x(dt(p.d).getTime()), py = y(p.v);
        const joined = prev && (dt(p.d) - dt(prev.d)) <= (s.gapDays || 8) * 864e5;
        path += (joined ? 'L' : 'M') + px.toFixed(1) + ',' + py.toFixed(1);
        prev = p;
      }
      if (s.line !== false) el('path', { d: path, fill: 'none', stroke: s.color, 'stroke-width': s.width || 2, 'stroke-dasharray': s.dash || null, opacity: s.opacity ?? 1, 'stroke-linejoin': 'round' }, svg);
      for (const p of s.points) {
        if (p.v == null || p.v < yd.lo || p.v > yd.hi) continue;
        const px = x(dt(p.d).getTime()), py = y(p.v);
        if (s.marker === 'square') el('rect', { x: px - 3.5, y: py - 3.5, width: 7, height: 7, fill: s.color, opacity: s.opacity ?? 1 }, svg);
        else if (s.marker !== 'none') el('circle', { cx: px, cy: py, r: p.hollow ? 3.2 : (s.r || 2.6), fill: p.hollow ? 'none' : s.color, stroke: p.hollow ? COL.ink3 : 'none', 'stroke-width': 1.2, opacity: s.opacity ?? 1 }, svg);
      }
      const last = pts[pts.length - 1];
      if (last && s.label && s.endLabel !== false) txt(svg, x(dt(last.d).getTime()) + 8, y(last.v) + 4, cfg.fmt(last.v, true), { class: 'dlabel', fill: s.color });
    }
    hover(svg, m, w, h, (px, py, e) => {
      const t = x.inv(px);
      if (py > h - m.b + 14) {
        const ev = evs.find(v => Math.abs(dt(v.date).getTime() - t) < 2.5 * 864e5 || (v.end && t >= dt(v.date).getTime() && t <= dt(v.end).getTime() + 864e5));
        if (ev) { showTip(e, `<div class="t-h">${apDate(ev.date)}${ev.end && ev.end !== ev.date ? ' to ' + apDate(ev.end) : ''}</div><div>${ev.label}</div>${ev.detail ? `<div class="t-n">${ev.detail}</div>` : ''}`); return { x: x(dt(ev.date).getTime()) }; }
      }
      let best = null;
      for (const p of all) if (!best || Math.abs(dt(p.d).getTime() - t) < Math.abs(dt(best.d).getTime() - t)) best = p;
      if (!best) return null;
      const near = cfg.series.map(s => [s, s.points.find(p => p.d === best.d) || s.points.find(p => Math.abs(dt(p.d) - dt(best.d)) < 4 * 864e5)]);
      const head = cfg.tipHead ? cfg.tipHead(best) : apDate(best.d, true);
      const lines = near.filter(([, p]) => p && p.v != null).map(([s, p]) => row(s.label, cfg.fmt(p.v, true) + (p.hollow ? ' (not comparable)' : ''))).join('');
      const notes = near.map(([, p]) => p?.note).filter(Boolean)[0];
      const onDay = evs.filter(v => v.kind !== 'weather' && Math.abs(dt(v.date) - dt(best.d)) <= 3.5 * 864e5).map(v => v.label);
      showTip(e, `<div class="t-h">${head}</div>${lines}${notes ? `<div class="t-n">${notes}</div>` : ''}${onDay.length ? `<div class="t-n">${onDay.join('; ')}</div>` : ''}`);
      return { x: x(dt(best.d).getTime()) };
    });
  }

  /** Hour-of-day lines with optional bars. cfg.lines: [{ label, color, width,
   *  values: { hour: v } }], cfg.bars: { hour: v } on its own scale. */
  function hourChart(host, cfg) {
    const H = +host.dataset.h || 220;
    const { svg, w, h } = frame(host, H);
    const m = { t: 34, r: 64, b: 28, l: 40 };
    const hours = cfg.hours;
    const x = lin(0, hours.length - 1, m.l + 10, w - m.r - 10);
    const vals = cfg.lines.flatMap(l => hours.map(hr => l.values[hr]));
    if (!vals.some(v => v != null)) { txt(svg, 0, 18, cfg.empty || 'No comparable weeks yet.', { class: 'csub' }); return; }
    const yd = yDomain(vals, cfg.zero, cfg.minSpan || 0);
    const y = lin(yd.lo, yd.hi, h - m.b, m.t);
    txt(svg, 0, 14, cfg.title, { class: 'ctitle' });
    if (cfg.sub) txt(svg, 0, 28, cfg.sub, { class: 'csub' });
    if (cfg.bars) {
      const bv = hours.map(hr => cfg.bars[hr] || 0), maxB = Math.max(...bv) || 1;
      const bw = Math.max(4, Math.abs(x(1) - x(0)) * 0.6), top = m.t + (h - m.t - m.b) * 0.45;
      bv.forEach((b, i) => { const bh = (b / maxB) * (h - m.b - top); el('rect', { x: x(i) - bw / 2, y: h - m.b - bh, width: bw, height: bh, fill: 'rgba(255,255,255,0.05)' }, svg); });
      txt(svg, w - m.r + 8, top + 4, `${Math.round(maxB)} ${cfg.barLabel || ''}`, { fill: COL.ink3 });
    }
    grid(svg, m, w, yd, y, cfg.fmt);
    hours.forEach((hr, i) => { if (hr % 3 === 0) txt(svg, x(i), h - 8, hourTick(hr), { 'text-anchor': 'middle' }); });
    for (const l of cfg.lines) {
      let path = '', on = false;
      hours.forEach((hr, i) => { const v = l.values[hr]; if (v == null) { on = false; return; } path += (on ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1); on = true; });
      el('path', { d: path, fill: 'none', stroke: l.color, 'stroke-width': l.width || 2, 'stroke-dasharray': l.dash || null }, svg);
      hours.forEach((hr, i) => { if (l.values[hr] != null) el('circle', { cx: x(i), cy: y(l.values[hr]), r: 2.3, fill: l.color }, svg); });
    }
    hover(svg, m, w, h, (px, py, e) => {
      const i = Math.max(0, Math.min(hours.length - 1, Math.round(x.inv(px))));
      const hr = hours[i];
      showTip(e, `<div class="t-h">${hourName(hr)} to ${hourName((hr + 1) % 24)}</div>`
        + cfg.lines.map(l => (l.values[hr] != null ? row(l.label, cfg.fmt(l.values[hr], true)) : '')).join('')
        + (cfg.bars && cfg.bars[hr] != null ? row(cfg.barLabel || 'Bars', Math.round(cfg.bars[hr]).toLocaleString('en-US')) : ''));
      return { x: x(i) };
    });
  }

  function caution() {
    const b = document.getElementById('ai-caution-btn'), p = document.getElementById('ai-caution-pop');
    if (!b || !p) return;
    b.addEventListener('click', e => { e.stopPropagation(); p.hidden = !p.hidden; });
    document.addEventListener('click', e => { if (!e.target.closest('#ai-caution-btn,#ai-caution-pop')) p.hidden = true; });
  }

  window.BusCharts = { timeChart, hourChart, apDate, hourName, caution, COL, EV_COL };
})();
