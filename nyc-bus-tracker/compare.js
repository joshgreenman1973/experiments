/* Before and After — compare any route set across two runs of weeks, with an
 * optional comparison group (difference in differences). Reads
 * data/summary/weekly-routes.json, weekly.json, route-classes.json,
 * route-table.json and events.json. State lives in the URL query string. */
(() => {
  'use strict';
  const BC = window.BusCharts;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const mean = a => { const v = a.filter(x => x != null && Number.isFinite(x)); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
  const sd = a => { const m = mean(a); return a.length > 1 ? Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)) : null; };
  const canon = r => String(r || '').toUpperCase().replace(/^([A-Z]+)0+(\d)/, '$1$2');
  const get = p => fetch(p).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const PANEL = new Set(['local', 'sbs', 'limited']);

  const METRIC = {
    all: { label: 'speed with stops', fmt: v => v.toFixed(2), unit: ' mph', d: v => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)} mph`, bands: true },
    mov: { label: 'moving speed', fmt: v => v.toFixed(2), unit: ' mph', d: v => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(2)} mph`, bands: true },
    stop: { label: 'time stopped', fmt: v => (100 * v).toFixed(1) + '%', unit: '', d: v => `${v >= 0 ? '+' : '−'}${Math.abs(100 * v).toFixed(1)} pts`, bands: false },
    buses: { label: 'buses on the road', fmt: v => v.toFixed(1), unit: '', d: v => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`, bands: false },
    pax: { label: 'passengers per bus', fmt: v => v.toFixed(1), unit: '', d: v => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`, bands: false },
  };
  const BAND_LABEL = { all: '6 a.m. to 11 p.m.', am: '7 to 10 a.m.', mid: '10 a.m. to 4 p.m.', pm: '4 to 7 p.m.', eve: '7 to 11 p.m.' };

  let R, W, CLS, NAMES, EVENTS;

  const GROUPS = () => {
    const by = test => Object.keys(R.routes).filter(r => { const m = R.meta[r] || {}; return test(r, m); });
    const local = (r, m) => PANEL.has(m.kind);
    return {
      local: ['All local, limited and SBS routes', by(local)],
      M: ['Manhattan local routes', by((r, m) => local(r, m) && m.group === 'M')],
      Bx: ['Bronx local routes', by((r, m) => local(r, m) && m.group === 'Bx')],
      B: ['Brooklyn local routes', by((r, m) => local(r, m) && m.group === 'B')],
      Q: ['Queens local routes', by((r, m) => local(r, m) && m.group === 'Q')],
      S: ['Staten Island local routes', by((r, m) => local(r, m) && m.group === 'S')],
      sbs: ['Select Bus Service routes', by((r, m) => m.kind === 'sbs')],
      X: ['Express routes', by((r, m) => m.kind === 'express')],
      lanes: ['Bus-lane corridors (≥30% of length)', by((r, m) => local(r, m) && CLS[r]?.busLaneShare >= 0.3)],
      nolanes: ['Little or no bus lane (≤10%)', by((r, m) => local(r, m) && CLS[r]?.busLaneShare <= 0.1)],
      cbd: ['Congestion-zone routes', by((r, m) => local(r, m) && CLS[r] && CLS[r].cbd !== 'Outside CBD')],
      nocbd: ['Routes outside the congestion zone', by((r, m) => local(r, m) && CLS[r]?.cbd === 'Outside CBD')],
      custom: ['Custom list…', []],
    };
  };

  function parseList(text) {
    const ids = Object.keys(R.routes);
    return text.split(/[\s,;]+/).filter(Boolean).map(t => ids.find(r => r.toUpperCase() === t.toUpperCase()) || ids.find(r => canon(r) === canon(t))).filter(Boolean);
  }

  function value(p, dayType, band, metric) {
    const side = p[dayType];
    if (!side) return null;
    if (band === 'all') return side[metric] ?? null;
    return side[band]?.[metric] ?? null;
  }

  // Each route's mean over its comparable weeks in a period.
  function routeMeans(routes, weeks, dayType, band, metric) {
    const set = new Set(weeks);
    const out = {};
    for (const r of routes) {
      const vals = (R.routes[r] || []).filter(p => set.has(p.p) && (dayType === 'wd' ? p.cwd : p.cwe)).map(p => value(p, dayType, band, metric)).filter(v => v != null);
      if (vals.length) out[r] = { v: mean(vals), n: vals.length };
    }
    return out;
  }

  function diff(routes, A, B, opt) {
    const a = routeMeans(routes, A, opt.dayType, opt.band, opt.metric), b = routeMeans(routes, B, opt.dayType, opt.band, opt.metric);
    const both = routes.filter(r => a[r] && b[r]);
    const ch = both.map(r => b[r].v - a[r].v);
    const m = mean(ch), s = sd(ch);
    return { n: both.length, routes: both, a: mean(both.map(r => a[r].v)), b: mean(both.map(r => b[r].v)), change: m, se: s != null ? s / Math.sqrt(both.length) : null, per: Object.fromEntries(both.map(r => [r, b[r].v - a[r].v])) };
  }

  function weekOptions(sel, weeks) {
    sel.innerHTML = weeks.map(w => `<option value="${w.period}">${w.period} · ${BC.apDate(w.weekStart)}${w.comparable ? '' : ' (not comparable)'}</option>`).join('');
  }

  async function main() {
    BC.caution();
    [R, W, CLS, NAMES, EVENTS] = await Promise.all([
      get('data/summary/weekly-routes.json'), get('data/summary/weekly.json'), get('data/summary/route-classes.json').then(x => x?.routes || {}),
      get('data/routes/route-table.json').then(x => x?.routes || {}), get('data/events/events.json').then(x => x?.events || []),
    ]);
    if (!R || !W) { $('result').textContent = 'Could not load the weekly data.'; return; }
    const weeks = W.periods;
    const comp = weeks.filter(w => w.comparable);
    $('edition').textContent = `${comp.length} comparable weeks so far, ${BC.apDate(comp[0]?.weekStart || weeks[0].weekStart, true)} to ${BC.apDate(comp[comp.length - 1]?.weekEnd || weeks[weeks.length - 1].weekEnd, true)}.`;
    const G = GROUPS();
    $('group').innerHTML = Object.entries(G).map(([k, [l, rs]]) => `<option value="${k}">${l}${k === 'custom' ? '' : ` (${rs.length})`}</option>`).join('');
    $('control').innerHTML = '<option value="">No comparison group</option><option value="rest">All other local routes</option>' + Object.entries(G).map(([k, [l, rs]]) => `<option value="${k}">${l}${k === 'custom' ? '' : ` (${rs.length})`}</option>`).join('');
    for (const id of ['a0', 'a1', 'b0', 'b1']) weekOptions($(id), weeks);

    // defaults: the four comparable weeks before the latest four, against the latest four
    const q = new URLSearchParams(location.search);
    const pick = (k, d) => q.get(k) ?? d;
    const c = comp.map(w => w.period);
    $('group').value = pick('g', 'local');
    $('control').value = pick('c', '');
    $('custom').value = pick('gl', '');
    $('custom2').value = pick('cl', '');
    $('daytype').value = pick('d', 'wd');
    $('band').value = pick('h', 'all');
    $('metric').value = pick('m', 'all');
    $('a0').value = pick('a0', c[Math.max(0, c.length - 8)] || weeks[0].period);
    $('a1').value = pick('a1', c[Math.max(0, c.length - 5)] || weeks[0].period);
    $('b0').value = pick('b0', c[Math.max(0, c.length - 4)] || weeks[weeks.length - 1].period);
    $('b1').value = pick('b1', c[c.length - 1] || weeks[weeks.length - 1].period);
    const sync = () => {
      $('custom').hidden = $('group').value !== 'custom';
      $('custom2').hidden = $('control').value !== 'custom';
      const bandsOk = METRIC[$('metric').value].bands && $('daytype').value === 'wd';
      if (!bandsOk) $('band').value = 'all';
      $('band').disabled = !bandsOk;
    };
    ['group', 'control', 'metric', 'daytype'].forEach(id => $(id).addEventListener('change', sync));
    sync();
    $('form').addEventListener('submit', e => { e.preventDefault(); run(true); });
    run(false);
  }

  function run(push) {
    const weeks = W.periods;
    const idx = Object.fromEntries(weeks.map((w, i) => [w.period, i]));
    const range = (a, b) => { let i = idx[$(a).value], j = idx[$(b).value]; if (i > j) [i, j] = [j, i]; return weeks.slice(i, j + 1).map(w => w.period); };
    const A = range('a0', 'a1'), B = range('b0', 'b1');
    const opt = { dayType: $('daytype').value, band: $('band').value, metric: $('metric').value };
    const G = GROUPS();
    const gKey = $('group').value, cKey = $('control').value;
    const treat = gKey === 'custom' ? parseList($('custom').value) : G[gKey][1];
    let ctrl = null;
    if (cKey === 'rest') ctrl = G.local[1].filter(r => !treat.includes(r));
    else if (cKey === 'custom') ctrl = parseList($('custom2').value);
    else if (cKey) ctrl = G[cKey][1].filter(r => !treat.includes(r));
    const M = METRIC[opt.metric];
    const overlap = A.some(p => B.includes(p));

    const t = diff(treat, A, B, opt);
    const k = ctrl ? diff(ctrl, A, B, opt) : null;
    const dd = k && t.change != null && k.change != null ? t.change - k.change : null;
    const ddSe = k && t.se != null && k.se != null ? Math.sqrt(t.se ** 2 + k.se ** 2) : null;
    const ci = (v, se) => (se == null ? '' : ` <span class="flat">(95% range ${M.d(v - 1.96 * se)} to ${M.d(v + 1.96 * se)})</span>`);
    const nComp = list => list.filter(p => weeks[idx[p]].comparable).length;
    const gName = gKey === 'custom' ? `your ${treat.length} routes` : G[gKey][0].replace(/^./, c => c.toLowerCase());
    const span = (P) => `${BC.apDate(weeks[idx[P[0]]].weekStart)} to ${BC.apDate(weeks[idx[P[P.length - 1]]].weekEnd, true)}`;
    const what = `${M.label}, ${opt.dayType === 'wd' ? 'weekdays' : 'weekends'}, ${BAND_LABEL[opt.band]}`;
    let html = '';
    if (overlap) html += '<p class="warn">The two periods overlap; the comparison is not meaningful.</p>';
    if (!t.n) html += `<p class="warn">No route in this group has comparable ${opt.dayType === 'wd' ? 'weekday' : 'weekend'} data in both periods. Period A has ${nComp(A)} comparable week(s); period B has ${nComp(B)}.</p>`;
    else {
      const sig = (v, se) => se != null && Math.abs(v) > 1.96 * se;
      html += `<div class="cmp-big">
        <div class="stat"><div class="k">Period A</div><div class="v">${M.fmt(t.a)}<i>${M.unit}</i></div><div class="s">${span(A)} · ${nComp(A)} comparable wk</div></div>
        <div class="stat"><div class="k">Period B</div><div class="v">${M.fmt(t.b)}<i>${M.unit}</i></div><div class="s">${span(B)} · ${nComp(B)} comparable wk</div></div>
        <div class="stat"><div class="k">Change</div><div class="v ${sig(t.change, t.se) ? (t.change > 0 ? 'up' : 'down') : ''}">${M.d(t.change)}</div><div class="s">${t.n} routes, each against itself</div></div>
        ${k && k.n ? `<div class="stat"><div class="k">Comparison group</div><div class="v">${M.d(k.change)}</div><div class="s">${k.n} routes</div></div>
        <div class="stat"><div class="k">Against the comparison</div><div class="v ${sig(dd, ddSe) ? (dd > 0 ? 'up' : 'down') : ''}">${M.d(dd)}</div><div class="s">difference in differences</div></div>` : ''}
      </div>
      <p class="cmp-explain">For ${esc(gName)}, ${what}: <b>${M.fmt(t.a)}${M.unit}</b> in period A and <b>${M.fmt(t.b)}${M.unit}</b> in period B, a change of <b>${M.d(t.change)}</b>${ci(t.change, t.se)}.
      ${k && k.n ? ` The comparison group moved ${M.d(k.change)} over the same weeks, so against it the change is <b>${M.d(dd)}</b>${ci(dd, ddSe)}.` : ''}
      ${t.se != null ? (Math.abs(t.change) <= 1.96 * t.se ? ' The change is inside the range of route-to-route variation.' : '') : ''}</p>
      <p class="cmp-explain flat">Largest moves: ${Object.entries(t.per).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1])).slice(0, 6).map(([r, v]) => `<a href="route.html?r=${encodeURIComponent(r)}">${esc(r)}</a> ${M.d(v)}`).join(', ')}.</p>`;
    }
    const qs = new URLSearchParams({ g: gKey, c: cKey, d: opt.dayType, h: opt.band, m: opt.metric, a0: $('a0').value, a1: $('a1').value, b0: $('b0').value, b1: $('b1').value });
    if (gKey === 'custom') qs.set('gl', treat.join(','));
    if (cKey === 'custom') qs.set('cl', (ctrl || []).join(','));
    const url = `${location.pathname}?${qs}`;
    html += `<p class="cmp-explain"><a href="${url}">Link to this comparison</a></p>`;
    $('result').innerHTML = html;
    if (push) history.replaceState(null, '', url);

    // weekly group means (routes present in both periods), with the periods shaded
    const series = (routes) => weeks.map(w => {
      const vals = routes.map(r => (R.routes[r] || []).find(p => p.p === w.period)).filter(p => p && (opt.dayType === 'wd' ? p.cwd : p.cwe)).map(p => value(p, opt.dayType, opt.band, opt.metric));
      const d = new Date(w.weekStart + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + 3);
      return { d: d.toISOString().slice(0, 10), v: vals.length >= Math.max(1, routes.length * 0.5) ? mean(vals) : null };
    });
    const sr = [{ label: 'Chosen routes', color: BC.COL.ours, width: 2.4, points: series(t.routes) }];
    if (k && k.n) sr.unshift({ label: 'Comparison group', color: BC.COL.base, width: 1.6, points: series(k.routes) });
    BC.timeChart($('chart'), {
      title: `Weekly ${M.label}`, sub: `${opt.dayType === 'wd' ? 'weekdays' : 'weekends'}, ${BAND_LABEL[opt.band]}; routes in both periods`,
      fmt: (v, u) => M.fmt(v) + (u ? M.unit : ''), zero: false, events: EVENTS,
      bands: [{ start: weeks[idx[A[0]]].weekStart, end: weeks[idx[A[A.length - 1]]].weekEnd, label: 'A' }, { start: weeks[idx[B[0]]].weekStart, end: weeks[idx[B[B.length - 1]]].weekEnd, label: 'B' }],
      series: sr,
    });
  }

  main();
})();
