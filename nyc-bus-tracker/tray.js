/**
 * NYC Bus Tracker — the weekly-trends tray on index.html (method version 2).
 *
 * Loads independently of the live map, so a stalled tile server never blocks
 * the history. Everything here reads the published summaries; nothing is
 * computed from live positions. Rules, kept in step with collector/rollup.js:
 *   - headline speeds are "speed with stops" (distance over time, stopped time
 *     included), local/limited/SBS routes only, each route counting once,
 *     every hour 6 a.m. to 11 p.m. counting equally, weekdays kept apart;
 *   - only comparable weeks (seven days, every weekday and weekend hour
 *     collected often enough) enter a trend or a comparison;
 *   - a change is set against the average of the four comparable weeks
 *     before it, and a change smaller than the series' usual week-to-week
 *     wobble is labeled "no real change".
 */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const mean = a => { const v = a.filter(x => x != null && Number.isFinite(x)); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
  const median = a => { const v = a.filter(x => x != null).sort((p, q) => p - q); return v.length ? v[Math.floor(v.length / 2)] : null; };
  const f1 = x => (x == null ? '—' : x.toFixed(1));
  const pct = x => (x == null ? '—' : (100 * x).toFixed(1) + '%');
  const num = x => (x == null ? '—' : Math.round(x).toLocaleString('en-US'));
  const AP = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  const apDate = d => { const x = new Date(d + 'T00:00:00Z'); return `${AP[x.getUTCMonth()]} ${x.getUTCDate()}`; };
  const monthName = ym => { const [y, m] = ym.split('-').map(Number); return new Date(Date.UTC(y, m - 1, 15)).toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }); };
  const PANEL = new Set(['local', 'sbs', 'limited']);
  const routeLink = r => `<a class="route-link" href="route.html?r=${encodeURIComponent(r)}">${esc(r)}</a>`;

  const WATCH = [
    { code: 'M', name: 'Manhattan', routes: ['M15+', 'M4'] },
    { code: 'Bx', name: 'The Bronx', routes: ['BX12+', 'BX36'] },
    { code: 'B', name: 'Brooklyn', routes: ['B6', 'B41'] },
    { code: 'Q', name: 'Queens', routes: ['Q44+', 'Q58'] },
    { code: 'S', name: 'Staten Island', routes: ['S79+', 'S53'] },
  ];

  // ── small charts ──────────────────────────────────────────────────────────
  function linTrend(series) {
    const pts = series.map((v, i) => ({ i, v })).filter(p => p.v != null);
    if (pts.length < 2) return null;
    const m = pts.length, sx = pts.reduce((s, p) => s + p.i, 0), sy = pts.reduce((s, p) => s + p.v, 0);
    const sxx = pts.reduce((s, p) => s + p.i * p.i, 0), sxy = pts.reduce((s, p) => s + p.i * p.v, 0);
    const den = m * sxx - sx * sx;
    const slope = den ? (m * sxy - sx * sy) / den : 0;
    const icpt = (sy - slope * sx) / m;
    return { pts, slope, fit: i => icpt + slope * i, firstI: pts[0].i, lastI: pts[m - 1].i, n: m, net: slope * (pts[m - 1].i - pts[0].i) };
  }
  function spark(series, higherIsBetter = true) {
    const t = linTrend(series);
    if (!t) return '';
    const W = 100, H = 26, pad = 3, n = series.length;
    const xOf = i => (n > 1 ? (i / (n - 1)) * (W - 2 * pad) + pad : W / 2);
    const ys = [...t.pts.map(p => p.v), t.fit(t.firstI), t.fit(t.lastI)];
    const min = Math.min(...ys), max = Math.max(...ys), range = max - min || 1;
    const yOf = v => (H - pad) - ((v - min) / range) * (H - 2 * pad);
    const path = t.pts.map((p, k) => `${k ? 'L' : 'M'}${xOf(p.i).toFixed(1)} ${yOf(p.v).toFixed(1)}`).join(' ');
    const good = Math.abs(t.net) < 1e-9 ? null : (t.slope > 0) === higherIsBetter;
    const col = good === null ? 'var(--text-tertiary)' : good ? 'var(--vc-goodest-green)' : 'var(--vc-baddest-red)';
    const last = t.pts[t.pts.length - 1];
    return `<svg class="spark-trend" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <path d="${path}" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="1" vector-effect="non-scaling-stroke"/>
      <line x1="${xOf(t.firstI).toFixed(1)}" y1="${yOf(t.fit(t.firstI)).toFixed(1)}" x2="${xOf(t.lastI).toFixed(1)}" y2="${yOf(t.fit(t.lastI)).toFixed(1)}" stroke="${col}" stroke-width="2" vector-effect="non-scaling-stroke"/>
      <circle cx="${xOf(last.i).toFixed(1)}" cy="${yOf(last.v).toFixed(1)}" r="1.9" fill="rgba(255,255,255,0.6)"/>
    </svg>`;
  }

  /** Latest value against the mean of the previous four, with a noise band
   *  equal to the series' median week-to-week move (at least `floor`). */
  function change(series, floor, unitFmt, higherIsBetter) {
    const v = series.filter(x => x != null);
    if (v.length < 3) return '<div class="trend-change flat">too few comparable weeks to compare</div>';
    const latest = v[v.length - 1];
    const before = v.slice(-5, -1);
    const base = mean(before);
    const wobble = Math.max(floor, median(v.slice(1).map((x, i) => Math.abs(x - v[i]))) || 0);
    const d = latest - base;
    const label = `vs. the ${before.length} weeks before`;
    if (Math.abs(d) < wobble) return `<div class="trend-change flat">— no real change ${label} (moves under ${unitFmt(wobble)} are noise)</div>`;
    const good = (d > 0) === higherIsBetter;
    return `<div class="trend-change ${good ? 'up' : 'down'}">${d > 0 ? '▲' : '▼'} ${unitFmt(Math.abs(d))} ${label}</div>`;
  }

  // ── data ──────────────────────────────────────────────────────────────────
  const get = p => fetch(p).then(r => (r.ok ? r.json() : null)).catch(() => null);

  async function load() {
    const [weekly, health, wroutes, rider, classes, events, table] = await Promise.all([
      get('data/summary/weekly.json'), get('data/summary/health.json'), get('data/summary/weekly-routes.json'),
      get('data/ridership/routes-monthly.json'), get('data/summary/route-classes.json'),
      get('data/events/events.json'), get('data/routes/route-table.json'),
    ]);
    const periods = weekly?.periods || [];
    const comp = periods.filter(w => w.comparable);
    // Weekday figures need only the weekdays to be complete; a week whose
    // weekends were thin still counts for them.
    const compWd = periods.filter(w => w.days === 7 && w.wd.complete);
    const compWe = periods.filter(w => w.days === 7 && w.we.complete);
    // For the live headline in app.js: the latest comparable week's hour cells.
    const L = comp[comp.length - 1];
    if (L) window.BusTypical = { week: L.period, start: L.weekStart, end: L.weekEnd, hourly: L.hourly };
    window.dispatchEvent(new Event('bus-typical-ready'));
    const names = table?.routes || {};
    try { renderSummaryLine(compWd, compWe, health); } catch (e) { console.error(e); }
    try { renderHealth(health); } catch (e) { console.error(e); }
    try { renderCards(compWd, compWe); } catch (e) { console.error(e); }
    try { renderBoroughs(compWd, wroutes); } catch (e) { console.error(e); }
    try { renderRidership(rider, names); } catch (e) { console.error(e); }
    try { renderGeo(compWd, wroutes, classes); } catch (e) { console.error(e); }
    try { renderTable(periods); } catch (e) { console.error(e); }
    try { renderEvents(events, periods); } catch (e) { console.error(e); }
  }

  function renderSummaryLine(wd, we, health) {
    const el = $('tray-summary');
    if (!el) return;
    const L = wd[wd.length - 1], E = we[we.length - 1];
    const warn = health?.alert ? ' · ⚠ collection thin lately' : '';
    el.textContent = L
      ? `Weekdays, week of ${apDate(L.weekStart)}: ${f1(L.wd.all)} mph with stops${E ? ` · weekends, week of ${apDate(E.weekStart)}: ${f1(E.we.all)}` : ''}${warn}`
      : `No comparable week yet${warn}`;
  }

  function renderHealth(h) {
    const el = $('tray-health');
    if (!el || !h) return;
    const bars = h.days.map(d => {
      const hgt = Math.max(2, Math.round((d.hours / 17) * 26));
      const cls = d.hours < h.minHours ? 'bad' : '';
      return `<span class="hb ${cls}" style="height:${hgt}px" title="${apDate(d.date)}: ${d.hours} of 17 hours collected"></span>`;
    }).join('');
    el.innerHTML = `<div class="health-bars" aria-hidden="true">${bars}</div>
      <div class="health-text ${h.alert ? 'alert' : ''}"><strong>Collection, last ${h.days.length} days:</strong> ${esc(h.message)}
      Each bar is one day's hours collected, out of 17; red is under ${h.minHours}.</div>`;
  }

  function renderCards(comp, compWe) {
    const host = $('tray-cards');
    if (!host) return;
    const L = comp[comp.length - 1], E = compWe[compWe.length - 1];
    if (!L) { host.innerHTML = '<div class="tray-empty">No comparable week yet.</div>'; return; }
    $('tray-current-period').textContent = `Weekdays: ${L.period}, ${apDate(L.weekStart)} to ${apDate(L.weekEnd)}`
      + (E && E.period !== L.period ? `. Weekends: ${E.period}, the latest week with every weekend hour caught` : '')
      + '. Each against the average of the comparable weeks before it.';
    const mph = x => `${x.toFixed(1)} mph`;
    const card = (label, value, unit, sub, series, floor, fmt, higher) => `<div class="trend-card">
      <div class="trend-label">${label}</div>
      <div class="trend-value">${value}<span class="trend-unit">${unit}</span></div>
      ${change(series, floor, fmt, higher)}
      <div class="trend-period">${sub}</div>
      ${spark(series, higher)}
    </div>`;
    const s = k => comp.map(w => k(w));
    const cards = [
      card('Weekday speed', f1(L.wd.all), 'mph', 'with stops, 6 a.m.–11 p.m.', s(w => w.wd.all), 0.1, mph, true),
      card('Morning rush', f1(L.wd.bands?.am?.all), 'mph', 'weekdays 7–10 a.m., with stops', s(w => w.wd.bands?.am?.all), 0.1, mph, true),
      card('Evening rush', f1(L.wd.bands?.pm?.all), 'mph', 'weekdays 4–7 p.m., with stops', s(w => w.wd.bands?.pm?.all), 0.1, mph, true),
      card('Time stopped', pct(L.wd.stop), '', 'share of weekday bus time under 0.5 mph', s(w => w.wd.stop), 0.003, x => (100 * x).toFixed(1) + ' pts', false),
      card('Buses on the road', num(L.wd.buses), '', L.wd.sched ? `weekday average; ${num(L.wd.sched)} trips scheduled to be under way` : 'weekday average, every hour equal', s(w => w.wd.buses), 15, x => num(x), true),
      E ? card('Weekend speed', f1(E.we.all), 'mph', `with stops, Saturdays and Sundays, week of ${apDate(E.weekStart)}`, compWe.map(w => w.we.all), 0.1, mph, true) : '',
    ];
    host.innerHTML = cards.join('');
  }

  function groupSeries(comp, wroutes, pick) {
    if (!wroutes?.routes) return comp.map(() => null);
    const byPeriod = Object.fromEntries(comp.map(w => [w.period, []]));
    for (const [r, ps] of Object.entries(wroutes.routes)) {
      const m = wroutes.meta?.[r] || {};
      if (!PANEL.has(m.kind) || !pick(r, m)) continue;
      for (const p of ps) if (byPeriod[p.p] && p.cwd && p.wd?.all != null) byPeriod[p.p].push(p.wd.all);
    }
    return comp.map(w => (byPeriod[w.period].length >= 3 ? mean(byPeriod[w.period]) : null));
  }

  function mini(label, series, sub, href) {
    const v = series.filter(x => x != null);
    const t = linTrend(series);
    let ch = '';
    if (t) {
      const net = Math.round(t.net * 10) / 10;
      ch = net === 0 ? `<div class="trend-change flat">— flat over ${t.n} weeks</div>`
        : `<div class="trend-change ${net > 0 ? 'up' : 'down'}">${net > 0 ? '▲' : '▼'} ${Math.abs(net).toFixed(1)} over ${t.n} weeks</div>`;
    }
    const lab = href ? `<a class="route-link" href="${href}">${esc(label)}</a>` : esc(label);
    return `<div class="mini-trend">
      <div class="mini-label">${lab}</div>
      <div class="mini-value">${v.length ? f1(v[v.length - 1]) + '<span class="mini-unit">mph</span>' : '<span class="mini-nodata">no comparable week</span>'}</div>
      ${ch}${sub ? `<div class="trend-change flat">${sub}</div>` : ''}
      ${spark(series, true)}
    </div>`;
  }

  function renderBoroughs(comp, wroutes) {
    const host = $('tray-boro-trends');
    if (!host || !comp.length) return;
    const routeSeries = r => comp.map(w => {
      const p = wroutes?.routes?.[r]?.find(x => x.p === w.period);
      return p?.cwd ? p.wd?.all ?? null : null;
    });
    host.innerHTML = WATCH.map(b => `<div class="boro-trend">
      ${mini(b.name, groupSeries(comp, wroutes, (r, m) => m.group === b.code), 'borough average')}
      ${b.routes.map(r => (wroutes?.routes?.[r] ? mini(r, routeSeries(r), null, `route.html?r=${encodeURIComponent(r)}`) : `<div class="mini-trend"><div class="mini-label">${esc(r)}</div><div class="mini-nodata">route not in the data; check for a renamed route</div></div>`)).join('')}
    </div>`).join('');
  }

  function renderGeo(comp, wroutes, classes) {
    const host = $('tray-geo-cuts');
    const cls = classes?.routes;
    if (!host || !cls || !comp.length) return;
    const groups = [
      ['Priority corridors', '≥30% on bus lanes', c => c.busLaneShare >= 0.3],
      ['Little or no bus lane', '≤10% on bus lanes', c => c.busLaneShare <= 0.1],
      ['Congestion zone routes', 'in or crossing the CBD', c => c.cbd !== 'Outside CBD'],
      ['Rest of the city', 'never enter the CBD', c => c.cbd === 'Outside CBD'],
    ];
    host.innerHTML = groups.map(([label, sub, test]) => {
      const n = Object.values(cls).filter(test).length;
      return mini(label, groupSeries(comp, wroutes, r => cls[r] && test(cls[r])), `${sub} · ${n} routes`);
    }).join('');
  }

  function renderRidership(d, names) {
    const host = $('tray-ridership');
    if (!host || !d?.months?.length) return;
    const li = d.months.length - 1;
    // Two comparisons for the latest three months: the twelve months before
    // (recent trend) and the same three months a year earlier (fair to the
    // season). Either is suppressed when a network redesign changed the route
    // inside its window.
    const win = (from, to) => d.months.slice(Math.max(0, from), to);
    const cmp = (arr, breaks, from, to) => {
      if (!arr || from < 0) return null;
      if ((breaks || []).some(m => win(from, li + 1).includes(m))) return 'break';
      const a = mean(arr.slice(li - 2, li + 1)), b = mean(arr.slice(from, to));
      return a && b ? a / b - 1 : null;
    };
    const recentVsYear = (arr, breaks) => cmp(arr, breaks, li - 14, li - 2);
    const sameMonths = (arr, breaks) => cmp(arr, breaks, li - 14, li - 11);
    const span = `${monthName(d.months[li - 2]).split(' ')[0].slice(0, 3)}.–${monthName(d.months[li]).split(' ')[0].slice(0, 3)}.`;
    const chg = x => (x === 'break' ? '<span class="rid-break" title="A network redesign changed this route inside the comparison window">route changed</span>'
      : x == null ? '—' : `<span class="${x > 0.005 ? 'rid-up' : x < -0.005 ? 'rid-down' : ''}">${x > 0 ? '+' : ''}${(100 * x).toFixed(1)}%</span>`);
    const tile = (label, rec, href) => {
      const c = recentVsYear(rec.wdAvg, rec.breakMonths);
      const taps = rec.tapsWdAvg?.[li];
      return `<div class="mini-trend">
        <div class="mini-label">${href ? `<a class="route-link" href="${href}">${esc(label)}</a>` : esc(label)}</div>
        <div class="mini-value">${num(rec.wdAvg[li])}<span class="mini-unit">riders/wkday</span></div>
        <div class="trend-change flat">${span} vs. a year earlier: ${chg(sameMonths(rec.wdAvg, rec.breakMonths))}</div>
        <div class="trend-change flat">vs. the 12 months before: ${chg(c)}</div>
        ${taps ? `<div class="trend-change flat">fare taps ${num(taps)} · counters/taps ${(rec.wdAvg[li] / taps).toFixed(2)}</div>` : ''}
        ${spark(rec.wdAvg.map(x => x || null), true)}
      </div>`;
    };
    const tiles = [tile('All NYC buses', d.system)];
    for (const b of WATCH) for (const r of b.routes) if (d.routes[r]) tiles.push(tile(r, d.routes[r], `route.html?r=${encodeURIComponent(r)}`));
    const ranked = Object.entries(d.routes).map(([r, rec]) => ({ r, rec, now: rec.wdAvg[li] })).filter(x => x.now > 0)
      .sort((a, b) => b.now - a.now).slice(0, 15);
    const rows = ranked.map((x, i) => {
      const taps = x.rec.tapsWdAvg?.[li];
      return `<tr><td class="num">${i + 1}</td><td>${routeLink(x.r)}</td><td class="rid-name">${esc(names[x.r]?.long || '')}</td>
        <td class="num">${num(x.now)}</td><td class="num">${num(taps)}</td><td class="num">${taps ? (x.now / taps).toFixed(2) : '—'}</td>
        <td class="num">${chg(sameMonths(x.rec.wdAvg, x.rec.breakMonths))}</td><td class="num">${chg(recentVsYear(x.rec.wdAvg, x.rec.breakMonths))}</td></tr>`;
    }).join('');
    host.innerHTML = `<div class="boro-trend rid-tiles">${tiles.join('')}</div>
      <div class="rid-board"><div class="rid-board-title">Busiest routes, ${monthName(d.months[li])}: average weekday riders</div>
      <table class="tray-table rid-table"><thead><tr><th class="num">#</th><th>Route</th><th>Name</th><th class="num">Counters</th><th class="num">Fare taps</th><th class="num">Ratio</th><th class="num">${span} vs. year earlier</th><th class="num">vs. 12 months before</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }

  function renderTable(periods) {
    const tbody = $('tray-table-body');
    if (!tbody) return;
    const rows = [...periods].reverse();
    tbody.innerHTML = rows.map(w => {
      const note = [];
      if (w.days < 7) note.push(`${w.days} of 7 days`);
      if (!w.wd.complete && w.wd.missingHours.length) note.push(`weekday hours short: ${w.wd.missingHours.length} of 17`);
      if (!w.we.complete && w.we.missingHours.length) note.push(`weekend hours short: ${w.we.missingHours.length} of 17`);
      const hr = h => (h === 12 ? 'noon' : `${((h + 11) % 12) + 1} ${h < 12 ? 'a.m.' : 'p.m.'}`);
      if (w.comparable || w.wd.complete) {
        const f = [...(w.wd.filledHours || []).map(h => `${hr(h)} weekdays`), ...(w.we.filledHours || []).map(h => `${hr(h)} weekends`)];
        if (f.length) note.push(`filled: ${f.join(', ')}`);
      }
      for (const h of w.holidays || []) note.push(`${apDate(h.date)} left out (${h.reason.split(':')[0]})`);
      return `<tr class="${w.comparable ? '' : 'partial'}">
        <td>${w.period}</td><td>${apDate(w.weekStart)}–${apDate(w.weekEnd)}</td>
        <td class="num">${w.coveragePct}%</td><td class="num">${w.comparable ? '✓' : '—'}</td>
        <td class="num">${f1(w.wd.all)}</td><td class="num">${f1(w.wd.bands?.am?.all)}</td><td class="num">${f1(w.wd.bands?.pm?.all)}</td>
        <td class="num">${pct(w.wd.stop)}</td><td class="num">${f1(w.we.all)}</td><td class="num">${f1(w.wd.mov)}</td>
        <td class="num">${num(w.wd.buses)}</td><td class="num">${num(w.wd.sched)}</td>
        <td class="note">${esc(note.join('; '))}</td></tr>`;
    }).join('');
  }

  function renderEvents(ev, periods) {
    const host = $('tray-events');
    if (!host || !ev?.events) return;
    const cutoff = periods.length ? periods[Math.max(0, periods.length - 10)].weekStart : '';
    const list = ev.events.filter(e => e.date >= cutoff).reverse();
    const KIND = { holiday: 'Holiday or service cut', gap: 'Collection gap', weather: 'Weather', method: 'Method', network: 'Network change' };
    host.innerHTML = list.length ? `<ul class="event-list">${list.map(e => `<li><span class="ev-date">${apDate(e.date)}${e.end && e.end !== e.date ? '–' + apDate(e.end) : ''}</span>
      <span class="ev-kind ev-${e.kind}">${KIND[e.kind] || e.kind}</span> ${esc(e.label)}${e.detail ? ` <span class="ev-detail">${esc(e.detail)}</span>` : ''}</li>`).join('')}</ul>`
      : '<p>Nothing recorded in the last ten weeks.</p>';
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
})();
