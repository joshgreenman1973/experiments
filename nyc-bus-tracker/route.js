/* Route by Route — one route's history (route.html?r=M15+) or, with no route
 * given, a sortable table of every route. Reads data/route-history/,
 * data/summary/weekly.json, data/mta/routes.json, data/ridership/
 * routes-monthly.json, data/events/events.json and data/routes/route-table.json. */
(() => {
  'use strict';
  const BC = window.BusCharts;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const mean = a => { const v = a.filter(x => x != null && Number.isFinite(x)); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
  const median = a => { const v = a.filter(x => x != null).sort((p, q) => p - q); return v.length ? v[Math.floor(v.length / 2)] : null; };
  const f1 = x => (x == null ? '–' : x.toFixed(1));
  const pct = x => (x == null ? '–' : (100 * x).toFixed(1) + '%');
  const num = x => (x == null ? '–' : Math.round(x).toLocaleString('en-US'));
  const slug = r => r.replace(/\+/g, 'plus');
  const canon = r => String(r || '').toUpperCase().replace(/^([A-Z]+)0+(\d)/, '$1$2');
  const GROUP = { M: 'Manhattan', Bx: 'Bronx', B: 'Brooklyn', Q: 'Queens', S: 'Staten Island', X: 'Express' };
  const KIND = { local: 'local', limited: 'limited-stop', sbs: 'Select Bus Service', express: 'express', shuttle: 'temporary shuttle' };
  const get = p => fetch(p).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const zero = { weekly: false };
  let redraw = () => {};

  const params = new URLSearchParams(location.search);
  const want = params.get('r');

  async function main() {
    BC.caution();
    const [index, table, weekly, events] = await Promise.all([
      get('data/route-history/index.json'), get('data/routes/route-table.json'), get('data/summary/weekly.json'), get('data/events/events.json'),
    ]);
    const names = table?.routes || {};
    const ids = Object.keys(index?.routes || {}).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    $('route-options').innerHTML = ids.map(r => `<option value="${esc(r)}">${esc(names[r]?.long || '')}</option>`).join('');
    $('picker').addEventListener('submit', e => {
      e.preventDefault();
      const v = $('pick').value.trim().toUpperCase();
      const hit = ids.find(r => r.toUpperCase() === v) || ids.find(r => canon(r) === canon(v));
      if (hit) location.search = '?r=' + encodeURIComponent(hit);
      else $('pick').setCustomValidity('No route by that name'), $('pick').reportValidity(), setTimeout(() => $('pick').setCustomValidity(''), 1500);
    });
    const weeks = Object.fromEntries((weekly?.periods || []).map(w => [w.period, w]));
    if (want) {
      const id = ids.find(r => r.toUpperCase() === want.toUpperCase()) || ids.find(r => canon(r) === canon(want));
      if (!id) { $('dek').textContent = `No route called ${want} in the tracker's data.`; return showAll(index, names); }
      return showOne(id, names[id] || {}, weeks, events?.events || []);
    }
    showAll(index, names);
  }

  // ── one route ─────────────────────────────────────────────────────────────
  async function showOne(id, info, weeks, events) {
    const [doc, mta, rider] = await Promise.all([get(`data/route-history/${slug(id)}.json`), get('data/mta/routes.json'), get('data/ridership/routes-monthly.json')]);
    if (!doc) { $('dek').textContent = `No history file for ${id} yet.`; return; }
    document.title = `${id} — Route by Route`;
    $('title').innerHTML = `${esc(id.replace(/\+$/, ''))}${id.endsWith('+') ? '<span>+</span>' : ''}`;
    $('dek').textContent = [info.long, `${KIND[doc.kind] || doc.kind} route`, GROUP[doc.group]].filter(Boolean).join(' · ');
    $('one').hidden = false;
    $('dl-json').href = `data/route-history/${slug(id)}.json`;

    const mid = p => { const w = weeks[p]; if (!w) return null; const d = new Date(w.weekStart + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + 3); return d.toISOString().slice(0, 10); };
    const W = doc.weekly.map(w => ({ ...w, d: mid(w.p), sys: weeks[w.p] })).filter(w => w.d);
    const C = W.filter(w => w.cwd);
    const L = C[C.length - 1];
    $('edition').innerHTML = L
      ? `${C.length} comparable weeks of ${W.length} with this route on the road. Latest: <b>${BC.apDate(L.sys.weekStart)} to ${BC.apDate(L.sys.weekEnd, true)}</b>.`
      : `${W.length} weeks on the road; none comparable yet.`;

    // stat cards, each against the average of the four comparable weeks before
    const series = k => C.map(w => k(w));
    const stat = (label, get, fmt, unitFmt, higherIsBetter, floor, sub) => {
      const s = series(get).filter(v => v != null);
      const v = L ? get(L) : null;
      let ch = '';
      if (s.length >= 3 && v != null) {
        const base = mean(s.slice(-5, -1));
        const wob = Math.max(floor, median(s.slice(1).map((x, i) => Math.abs(x - s[i]))) || 0);
        const d = v - base;
        ch = Math.abs(d) < wob ? `<span class="flat">no real change vs. the ${Math.min(4, s.length - 1)} weeks before</span>`
          : `<span class="${(d > 0) === higherIsBetter ? 'up' : 'down'}">${d > 0 ? '▲' : '▼'} ${unitFmt(Math.abs(d))} vs. the ${Math.min(4, s.length - 1)} weeks before</span>`;
      }
      return `<div class="stat"><div class="k">${label}</div><div class="v">${fmt(v)}</div><div class="c">${ch}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`;
    };
    const mph = x => `${x.toFixed(1)} mph`;
    $('stats').innerHTML = !L ? '<p class="empty">No comparable week yet for this route.</p>' : [
      stat('Weekday speed', w => w.wd?.all, v => `${f1(v)}<i>mph</i>`, mph, true, 0.15, `moving only: ${f1(L.wd?.mov)} mph`),
      stat('7–10 a.m.', w => w.wd?.am?.all, v => `${f1(v)}<i>mph</i>`, mph, true, 0.2),
      stat('4–7 p.m.', w => w.wd?.pm?.all, v => `${f1(v)}<i>mph</i>`, mph, true, 0.2),
      stat('Time stopped', w => w.wd?.stop, v => pct(v), x => (100 * x).toFixed(1) + ' pts', false, 0.005),
      stat('Buses on the road', w => w.wd?.buses, v => f1(v), x => x.toFixed(1), true, 0.3, L.wd?.sched != null ? `${f1(L.wd.sched)} trips scheduled to be under way` : 'average across 6 a.m.–11 p.m.'),
      stat('Passengers per bus', w => w.wd?.pax, v => f1(v), x => x.toFixed(1), true, 0.5, 'live counter estimate, buses that report one; recorded from Oct. 6, 2026'),
      stat('Weekend speed', w => (w.cwe ? w.we?.all : null), v => `${f1(v)}<i>mph</i>`, mph, true, 0.15),
    ].join('');

    // MTA weekday figure by month, placed mid-month
    const mtaKey = mta ? Object.keys(mta.weekday || {}).find(k => canon(k) === canon(id)) : null;
    const mtaPts = mtaKey ? mta.months.map((m, i) => ({ d: `${m}-15`, v: mta.weekday[mtaKey][i] })).filter(p => p.v != null) : [];
    const pts = (k, onlyC = true) => W.map(w => ({ d: w.d, v: k(w), hollow: onlyC && !w.cwd, note: w.cwd ? null : 'not comparable' }));
    const evs = events.filter(e => e.kind !== 'weather' || true);
    const start = W[0]?.d, end = W[W.length - 1]?.d;

    // riders
    const rk = rider ? Object.keys(rider.routes).find(k => canon(k) === canon(id)) : null;
    const rr = rk ? rider.routes[rk] : null;

    redraw = () => {
      BC.timeChart($('chart-weekly'), {
        title: 'Speed', sub: 'mph, weekdays unless noted', fmt: (v, u) => f1(v) + (u ? ' mph' : ''), zero: zero.weekly, minSpan: 1.5, events: evs, start, end,
        series: [
          { label: 'Moving only', color: BC.COL.base, width: 1.2, opacity: 0.6, points: pts(w => w.wd?.mov), marker: 'none', endLabel: false },
          { label: 'Weekends', color: BC.COL.ours, width: 1.4, dash: '4 4', opacity: 0.7, points: W.map(w => ({ d: w.d, v: w.cwe ? w.we?.all : null })), marker: 'none', endLabel: false },
          { label: 'MTA, weekdays', color: BC.COL.mta, line: false, marker: 'square', points: mtaPts, endLabel: false },
          { label: 'Weekdays, with stops', color: BC.COL.ours, width: 2.4, points: pts(w => w.wd?.all) },
        ],
      });
      BC.timeChart($('chart-rush'), {
        title: 'Rush hours', sub: 'weekday mph with stops', fmt: (v, u) => f1(v) + (u ? ' mph' : ''), zero: zero.weekly, minSpan: 1.5, events: evs, start, end,
        series: [
          { label: '7–10 a.m.', color: BC.COL.ours, points: pts(w => w.wd?.am?.all) },
          { label: '4–7 p.m.', color: BC.COL.rose, points: pts(w => w.wd?.pm?.all) },
        ],
      });
      const P = doc.profile;
      BC.hourChart($('chart-day'), {
        title: 'Speed by hour', sub: 'weekday mph with stops', hours: Array.from({ length: 17 }, (_, i) => i + 6), fmt: (v, u) => f1(v) + (u ? ' mph' : ''),
        zero: false, minSpan: 2, barLabel: 'buses',
        bars: Object.fromEntries(Object.entries(P.recent.wd || {}).map(([h, c]) => [h, c.buses])),
        lines: [
          { label: 'First weeks', color: BC.COL.base, width: 1.5, values: Object.fromEntries(Object.entries(P.first.wd || {}).map(([h, c]) => [h, c.all])) },
          { label: 'Recent weeks', color: BC.COL.ours, width: 2.6, values: Object.fromEntries(Object.entries(P.recent.wd || {}).map(([h, c]) => [h, c.all])) },
        ],
      });
      BC.timeChart($('chart-buses'), {
        title: 'Buses on the road vs. trips scheduled', sub: 'weekday average, every hour equal', fmt: v => f1(v), zero: zero.weekly, minSpan: 2, events: evs, start, end,
        series: [
          { label: 'Trips scheduled', color: BC.COL.base, width: 1.5, dash: '5 3', points: W.map(w => ({ d: w.d, v: w.cwd ? w.wd?.sched ?? null : null })), marker: 'none' },
          { label: 'Buses on the road', color: BC.COL.ours, points: pts(w => w.wd?.buses) },
        ],
      });
      const rpts = (arr) => (rider && arr ? rider.months.map((m, i) => ({ d: `${m}-15`, v: arr[i] || null })) : []);
      const breaks = (rr?.breakMonths || []).map(m => ({ date: `${m}-01`, kind: 'network', label: 'Network redesign changed this route', detail: '' }));
      BC.timeChart($('chart-riders'), {
        title: 'Average weekday riders', sub: 'by month', fmt: v => Math.round(v).toLocaleString('en-US'), zero: true, events: breaks,
        empty: 'No counter data for this route.', tipHead: p => new Date(p.d + 'T12:00:00Z').toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
        series: [
          { label: 'Fare taps', color: BC.COL.base, width: 1.5, points: rpts(rr?.tapsWdAvg), gapDays: 40 },
          { label: 'Passenger counters', color: BC.COL.rose, width: 2.4, points: rpts(rr?.wdAvg), gapDays: 40 },
        ],
      });
    };
    redraw();
    if (rr) {
      const li = rider.months.length - 1;
      const ratio = rr.wdAvg[li] && rr.tapsWdAvg?.[li] ? (rr.wdAvg[li] / rr.tapsWdAvg[li]).toFixed(2) : null;
      $('rider-note').textContent = ratio ? `In ${new Date(rider.months[li] + '-15T12:00:00Z').toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' })}, counters recorded ${ratio} boardings for every paid tap on this route.` : '';
    }

    const rows = [...W].reverse().map(w => `<tr class="${w.cwd ? '' : 'nc'}"><td>${w.p}</td><td>${BC.apDate(w.sys.weekStart)}</td>
      <td class="n">${w.wdN}/${w.weN}</td><td class="n">${f1(w.wd?.all)}</td><td class="n">${f1(w.wd?.mov)}</td><td class="n">${f1(w.wd?.am?.all)}</td>
      <td class="n">${f1(w.wd?.pm?.all)}</td><td class="n">${pct(w.wd?.stop)}</td><td class="n">${f1(w.we?.all)}</td><td class="n">${f1(w.wd?.buses)}</td>
      <td class="n">${f1(w.wd?.sched)}</td><td class="n">${f1(w.wd?.pax)}</td></tr>`).join('');
    $('weeks').innerHTML = `<thead><tr><th>Week</th><th>Starting</th><th class="n" title="Weekdays / weekend days the route ran">Days</th><th class="n">Weekday</th><th class="n">Moving</th><th class="n">7–10 a.m.</th><th class="n">4–7 p.m.</th><th class="n">Stopped</th><th class="n">Weekend</th><th class="n" title="Average weekday buses in service at any moment, 6 a.m. to 11 p.m., every hour counting equally">Buses on the road</th><th class="n" title="Average weekday trips the MTA timetable has under way at the same hours (from Sept. 6, 2026)">Scheduled</th><th class="n" title="Passengers per bus, from the live counter estimate (from Oct. 6, 2026)">Per bus</th></tr></thead><tbody>${rows}</tbody>`;
  }

  // ── every route ───────────────────────────────────────────────────────────
  function showAll(index, names) {
    $('all').hidden = false;
    const rows = Object.entries(index?.routes || {}).filter(([, r]) => r.kind !== 'shuttle' && r.kind !== 'unknown')
      .map(([id, r]) => ({ id, ...r, long: names[id]?.long || '' }));
    $('edition').textContent = `${rows.length} routes. Latest week with every weekday hour caught: ${index?.lastWeekdayWeek || '–'}.`;
    let group = 'all', sortKey = 'id', dir = 1;
    const seg = $('group-seg');
    seg.innerHTML = ['all', 'M', 'Bx', 'B', 'Q', 'S', 'X'].map(g => `<button data-g="${g}" class="${g === 'all' ? 'on' : ''}">${g === 'all' ? 'All' : GROUP[g]}</button>`).join('');
    seg.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; group = b.dataset.g; seg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
    const cols = [
      ['id', 'Route'], ['long', 'Name'], ['wdAll', 'Weekday mph'], ['chg', 'Change'], ['buses', 'Buses on the road'], ['nWeeks', 'Comparable weeks'],
    ];
    function draw() {
      const list = rows.filter(r => group === 'all' || r.group === group).sort((a, b) => {
        const x = a[sortKey], y = b[sortKey];
        if (x == null) return 1; if (y == null) return -1;
        return (typeof x === 'string' ? x.localeCompare(y, undefined, { numeric: true }) : x - y) * dir;
      });
      const TIP = { buses: 'Average weekday buses in service at any moment, 6 a.m. to 11 p.m., every hour counting equally (layovers left out; hours the route does not run count as zero)', nWeeks: 'Weeks with every weekday hour collected often enough to compare', chg: 'Latest comparable week against the average of the four before it' };
      $('routes').innerHTML = `<thead><tr>${cols.map(([k, l]) => `<th data-k="${k}" title="${TIP[k] || ''}" class="${['wdAll', 'chg', 'buses', 'nWeeks'].includes(k) ? 'n' : ''}${k === sortKey ? ' sorted' : ''}">${l}${k === sortKey ? (dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>${
        list.map(r => {
          const quiet = r.chg == null || r.wobble == null || Math.abs(r.chg) < r.wobble;
          const c1 = r.chg == null ? null : Math.round(r.chg * 10) / 10;
          const ch = c1 == null ? '–' : c1 === 0 ? '<span class="flat">0.0</span>' : `<span class="${quiet ? 'flat' : c1 > 0 ? 'up' : 'down'}">${c1 > 0 ? '+' : '−'}${Math.abs(c1).toFixed(1)}</span>`;
          return `<tr><td><a href="route.html?r=${encodeURIComponent(r.id)}">${esc(r.id)}</a></td><td class="nm">${esc(r.long)}</td><td class="n">${f1(r.wdAll)}</td><td class="n">${ch}</td><td class="n">${f1(r.buses)}</td><td class="n">${r.nWeeks ?? '–'}</td></tr>`;
        }).join('')}</tbody>`;
      $('routes').querySelectorAll('th').forEach(th => th.addEventListener('click', () => { const k = th.dataset.k; dir = k === sortKey ? -dir : (['id', 'long'].includes(k) ? 1 : -1); sortKey = k; draw(); }));
    }
    draw();
  }

  document.querySelectorAll('[data-zero]').forEach(cb => cb.addEventListener('change', () => { zero[cb.dataset.zero] = cb.checked; redraw(); }));
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => redraw(), 150); });
  main();
})();
