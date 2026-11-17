/* Up and Down: Flatbush Avenue spotlight. Reads data/spotlight/flatbush.json
 * (built by scripts/flatbush/build_flatbush.py) and, when present,
 * data/spotlight/other-lanes.json. Charts come from charts.js. */
(() => {
  'use strict';
  const BC = window.BusCharts;
  const css = getComputedStyle(document.documentElement);
  const C = n => css.getPropertyValue(n).trim();
  const SOUTH = C('--ours'), NORTH = C('--b-Q'), MTA = C('--mta'), BASE = C('--base');
  const $ = id => document.getElementById(id);
  const f1 = v => (v == null ? '–' : v.toFixed(1));
  const mph = (v, unit) => (v == null ? '–' : `${v.toFixed(1)}${unit ? ' mph' : ''}`);
  const sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1);
  const sgn2 = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2);
  const pct = (a, b) => Math.round((a / b - 1) * 100);
  const ap = (s, y) => BC.apDate(s, y);
  const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
  const num = n => (n < 10 ? WORDS[n] : String(n));
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const zero = {};
  let D, L;

  const MONTH = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const monthName = ym => { const [y, m] = ym.split('-').map(Number); return `${MONTH[m - 1]} ${y}`; };

  function learned() {
    const g = D.groups, t = D.trip, cal = D.mta.calibration, o = D.others.B67;
    const ctrl = Object.values(D.control).map(c => c.change);
    const items = [
      ['On the rebuilt mile',
        `B41 buses between Livingston Street and Grand Army Plaza averaged ${mph(g.rebuilt.S.after, 1)} southbound and ${mph(g.rebuilt.N.after, 1)} northbound on the ${num(D.periods.afterDays)} weekdays from ${ap(D.periods.after[0])} to ${ap(D.periods.after[1])}. In the last four weeks of construction they averaged ${mph(g.rebuilt.S.during, 1)} and ${mph(g.rebuilt.N.during, 1)}.`],
      ['Against the time before construction',
        `On the MTA&rsquo;s 1.7-mile timing segment that holds the rebuilt stretch from Atlantic Avenue to Grand Army Plaza plus the run along Prospect Park, the first week came to about ${mph(cal.S.afterInMtaTerms, 1)} southbound and ${mph(cal.N.afterInMtaTerms, 1)} northbound. From January to April 2026, before the second phase of construction, the MTA measured ${mph(cal.S.preConstruction, 1)} and ${mph(cal.N.preConstruction, 1)}. The first week was about ${pct(cal.S.afterInMtaTerms, cal.S.preConstruction)}% faster southbound and ${pct(cal.N.afterInMtaTerms, cal.N.preConstruction)}% faster northbound.`],
      ['Up and down the rest of Flatbush',
        `From Grand Army Plaza to Kings Plaza, ${g.rest.miles.toFixed(1)} miles, speeds changed little: ${mph(g.rest.S.after, 1)} southbound (${sgn(g.rest.S.change)}) and ${mph(g.rest.N.after, 1)} northbound (${sgn(g.rest.N.change)}). Over the same weeks four other busy Brooklyn routes changed by ${sgn2(Math.min(...ctrl))} to ${sgn2(Math.max(...ctrl))} mph.`],
      ['The whole ride',
        `A B41 trip along Flatbush from Livingston Street to Kings Plaza took about ${Math.round(t.S.after)} minutes southbound and ${Math.round(t.N.after)} northbound in the first week, ${f1(t.S.saved)} and ${f1(t.N.saved)} minutes less than in the last weeks of construction.`],
      ['The B67',
        `The B67, which shares the rebuilt mile from Seventh Avenue north, went from ${mph(o.S.during, 1)} to ${mph(o.S.after, 1)} southbound and from ${mph(o.N.during, 1)} to ${mph(o.N.after, 1)} northbound on the same stretch.`],
      ['When the lanes opened to buses',
        `The faster speeds first show up on Saturday, ${ap(D.opened)}. The city unveiled the finished lanes on ${ap(D.unveiled)}. Until then, through the last day of construction, B41 and B67 buses kept running on Flatbush through the work zone.`],
    ];
    $('learned').innerHTML = items.map(([h, b]) => `<li><b>${h}</b>${b}</li>`).join('');
  }

  function daily() {
    const pts = (key, kind) => D.daily.filter(x => x[key] != null).map(x => ({ d: x.d, v: x[key], hollow: x.type !== 'weekday', note: x.type !== 'weekday' ? (x.type === 'weekend' ? 'Weekend' : 'Holiday or schools closed') : null }));
    const common = {
      fmt: (v, full) => (full ? `${v.toFixed(1)} mph` : v.toFixed(0)),
      start: '2026-07-01', end: '2026-11-17', zero: zero.daily,
      bands: [{ start: '2026-07-01', end: '2026-11-06', label: '' }],
      events: [
        { date: D.opened, kind: 'method', label: 'Faster speeds first appear' },
        { date: D.unveiled, kind: 'network', label: 'City unveils the lanes' },
      ],
    };
    // Daily points show both weekday lines; weekends are drawn but kept off the line.
    const series = (k) => [
      { label: 'Southbound', color: SOUTH, points: pts(`${k}S`), gapDays: 9, r: 2.2 },
      { label: 'Northbound', color: NORTH, points: pts(`${k}N`), gapDays: 9, r: 2.2 },
    ];
    BC.timeChart($('chart-daily'), { ...common, title: 'Livingston St to Grand Army Plaza, B41', sub: 'mph, 7 a.m. to 7 p.m., each day', series: series('rebuilt') });
    BC.timeChart($('chart-rest'), { ...common, title: 'Grand Army Plaza to Kings Plaza, B41', sub: 'mph, 7 a.m. to 7 p.m., each day', series: series('rest') });
  }

  function mtaCharts() {
    const cal = D.mta.calibration;
    const s = D.mta.series;
    const mk = key => s[key].filter(x => x.v != null).map(x => ({ d: `${x.m}-15`, v: x.v }));
    const gpsPts = dir => {
      const c = cal[dir];
      const p = Object.entries(c.gpsMonthly).map(([m, v]) => ({ d: `${m}-15`, v: +(v - c.offset).toFixed(2), note: `Tracker ${v.toFixed(2)} mph before adjustment` }));
      p.push({ d: '2026-11-12', v: c.afterInMtaTerms, note: `First week of the lanes, ${ap(D.periods.after[0])} to ${ap(D.periods.after[1])}` });
      return p;
    };
    const bands = [
      { start: '2025-09-25', end: '2025-10-02', label: 'Phase 1' },
      { start: '2026-04-28', end: '2026-11-06', label: 'Phase 2 construction' },
    ];
    const fmt = (v, full) => (full ? `${v.toFixed(2)} mph` : v.toFixed(0));
    const cfg = (dir, title) => ({
      title, sub: 'mph, weekdays 7 a.m. to 7 p.m.', fmt, zero: zero.mta, bands,
      start: '2023-01-15', end: '2026-11-12',
      tipHead: p => (p.d === '2026-11-12' ? 'First week of the lanes' : monthName(p.d.slice(0, 7))),
      series: [
        { label: 'MTA', color: MTA, points: mk(dir), gapDays: 40 },
        { label: 'Tracker (adjusted)', color: dir === 'S' ? SOUTH : NORTH, points: gpsPts(dir), gapDays: 40, marker: 'square', line: false },
      ],
    });
    BC.timeChart($('chart-mta-s'), cfg('S', 'Southbound, Atlantic Av to Ocean Av'));
    BC.timeChart($('chart-mta-n'), cfg('N', 'Northbound, Empire Blvd to Atlantic Av'));
    const offS = cal.S.offset, offN = cal.N.offset;
    $('mta-copy').innerHTML = `The MTA publishes speeds between timing points on each route, a month or so after the month ends. The two B41 segments that hold the rebuilt stretch south of Atlantic Avenue also take in about a mile along Prospect Park, where nothing changed. The MTA&rsquo;s figures run through ${monthName(D.mta.months[D.mta.months.length - 1])}; the last square is the tracker&rsquo;s first week of the lanes.`;
    $('mta-note').innerHTML = `From July to October 2026 the tracker read ${Math.abs(offS).toFixed(2)} mph ${offS < 0 ? 'below' : 'above'} the MTA on the southbound segment and ${Math.abs(offN).toFixed(2)} mph ${offN < 0 ? 'below' : 'above'} it northbound, on average. The squares are shifted by those amounts so the two series line up. The MTA segment from Downtown Brooklyn to Atlantic Avenue changed its path several times in 2025 and 2026, so it is left out.`;
  }

  function stretchTable() {
    const row = (st, cls) => {
      const cell = x => {
        const cl = x.ci90[0] > 0 ? 'up' : x.ci90[1] < 0 ? 'down' : '';
        return `<td class="num">${f1(x.during)} &rarr; ${f1(x.after)}</td><td class="num ${cl}">${sgn(x.change)}<small>${sgn(x.ci90[0])} to ${sgn(x.ci90[1])}</small></td>`;
      };
      return `<tr class="${cls || ''}"><td>${esc(st.name)}</td><td class="num">${st.miles.toFixed(2)}</td>${cell(st.S)}${cell(st.N)}</tr>`;
    };
    const g = D.groups, t = D.trip;
    const sum = (label, x, miles) => `<tr class="${label.startsWith('Rebuilt') ? 'rb' : ''}"><td><b>${label}</b></td><td class="num">${miles.toFixed(2)}</td>`
      + ['S', 'N'].map(d => { const v = x[d]; const cl = v.ci90[0] > 0 ? 'up' : v.ci90[1] < 0 ? 'down' : ''; return `<td class="num">${f1(v.during)} &rarr; ${f1(v.after)}</td><td class="num ${cl}">${sgn(v.change)}<small>${sgn(v.ci90[0])} to ${sgn(v.ci90[1])}</small></td>`; }).join('') + '</tr>';
    $('stretch-table').innerHTML = `
      <thead><tr><th>Stretch</th><th>Miles</th><th>Southbound mph</th><th>Change</th><th>Northbound mph</th><th>Change</th></tr></thead>
      <tbody>${D.stretches.map(s => row(s, s.rebuilt ? 'rb' : '')).join('')}
      ${sum('Rebuilt mile', g.rebuilt, g.rebuilt.miles)}
      ${sum('Rest of Flatbush', g.rest, g.rest.miles)}</tbody>
      <tfoot><tr><td>Livingston St to Kings Plaza, minutes</td><td></td><td class="num">${f1(t.S.during)} &rarr; ${f1(t.S.after)}</td><td class="num up">${sgn(-t.S.saved)} min</td><td class="num">${f1(t.N.during)} &rarr; ${f1(t.N.after)}</td><td class="num up">${sgn(-t.N.saved)} min</td></tr></tfoot>`;
    const ctrl = Object.entries(D.control).sort((a, b) => a[0].localeCompare(b[0], 'en', { numeric: true }));
    $('ctrl-range').textContent = ctrl.map(([r, c]) => `${r} ${sgn2(c.change)} mph`).join(', ');
  }

  function hourCharts() {
    const hours = Array.from({ length: 12 }, (_, i) => 7 + i);
    for (const [dir, id, label] of [['S', 'chart-hour-s', 'Southbound'], ['N', 'chart-hour-n', 'Northbound']]) {
      const h = D.hourly[dir];
      BC.hourChart($(id), {
        hours, title: `${label}, Livingston St to Grand Army Plaza`, sub: 'mph, B41',
        fmt: (v, full) => (full ? `${v.toFixed(1)} mph` : v.toFixed(0)), zero: zero.mta,
        lines: [
          { label: 'Last four weeks of construction', color: BASE, width: 1.5, values: h.during },
          { label: 'First week of the lanes', color: dir === 'S' ? SOUTH : NORTH, width: 2.5, values: h.after },
        ],
      });
    }
  }

  function otherTable() {
    const rows = ['B41', 'B67', 'B45'].map(rt => {
      const x = rt === 'B41' ? { S: D.groups.rebuilt.S, N: D.groups.rebuilt.N } : D.others[rt];
      const c = v => (v.during != null && v.after != null ? `<td class="num">${f1(v.during)} &rarr; ${f1(v.after)}</td>` : '<td class="num">–</td>');
      const hrs = rt === 'B41' ? '' : ` <small>${x.S.hoursObservedAfter + x.N.hoursObservedAfter} bus-hours observed in the first week</small>`;
      return `<tr><td><a href="route.html?r=${rt}">${rt}</a>${hrs}</td>${c(x.S)}${c(x.N)}</tr>`;
    }).join('');
    $('other-table').innerHTML = `<thead><tr><th>Route</th><th>Southbound mph</th><th>Northbound mph</th></tr></thead><tbody>${rows}</tbody>`;
  }

  function lanes() {
    if (!L || !L.projects?.length) return;
    $('lanes-block').hidden = false;
    $('lanes-copy').innerHTML = L.copy || '';
    $('lanes-note').innerHTML = L.note || '';
    const rows = L.projects.map(p => {
      const cl = p.diff_in_diff_mph == null ? '' : p.diff_in_diff_mph > 0.05 ? 'up' : p.diff_in_diff_mph < -0.05 ? 'down' : '';
      return `<tr><td><b>${esc(p.name)}</b><small>${esc(p.borough)} · opened ${esc(p.openedLabel)} · ${esc(p.routes.join(', '))}${p.months ? ` · ${num(p.months)} months compared` : ''}</small></td>
        <td class="num">${p.before_mph.toFixed(2)} &rarr; ${p.after_mph.toFixed(2)}<small>${sgn(p.change_pct)}%</small></td>
        <td class="num">${p.control_change_mph == null ? '–' : sgn2(p.control_change_mph)}</td>
        <td class="num ${cl}">${p.diff_in_diff_mph == null ? '–' : sgn2(p.diff_in_diff_mph)}</td>
        <td class="why">${esc(p.cityClaim || '')}${p.flags?.length ? `<small>${esc(p.flags.join(' '))}</small>` : ''}</td></tr>`;
    }).join('');
    $('lanes-table').innerHTML = `<thead><tr><th>Project</th><th>Before &rarr; after, mph</th><th>Same routes elsewhere, mph</th><th>Net change, mph</th><th>City&rsquo;s claim, notes</th></tr></thead><tbody>${rows}</tbody>`;
  }

  function method() {
    const p = D.periods;
    $('method').innerHTML = `
      <p><strong>Positions.</strong> The tracker records the GPS position of every bus in the MTA BusTime feed about a dozen times in each of two six-minute bursts an hour, 6 a.m. to 11 p.m. Eastern. The raw snapshots are archived on the project&rsquo;s <code>bus-data</code> branch. For this page, all positions on Flatbush were pulled from Tuesdays, Wednesdays and Thursdays from April 28 to Sept. 30, 2026, and from every day from Oct. 1 to Nov. 17, 2026, plus the weekends around the opening.</p>
      <p><strong>Speed along the street.</strong> Each position is placed on the B41&rsquo;s published route line (MTA GTFS shape B410126); positions more than 35 meters from it are ignored. Two positions of the same bus 15 seconds to 3 minutes apart give a reading: the distance traveled along Flatbush over the time between the two GPS timestamps. A reading that spans two stretches is split between them by distance. Time a bus spends standing at a stop or a light counts, so speeds include stops. Buses on layover and readings above 49 mph are dropped. Limited and local B41 trips are counted together, as the MTA&rsquo;s figures do.</p>
      <p><strong>Days and hours.</strong> Weekdays only, leaving out holidays and weekdays when public schools were closed (Nov. 3 and Nov. 11 in the period shown), and only days on which at least 10 of the 12 hours from 7 a.m. to 7 p.m. were caught. Within a period, each of the 12 hours counts equally. &ldquo;Before&rdquo; in the stretch table is ${p.duringDays} weekdays from ${ap(p.during[0])} to ${ap(p.during[1])}; &ldquo;after&rdquo; is ${p.afterDays} weekdays from ${ap(p.after[0])} to ${ap(p.after[1])}. The 90% ranges come from resampling those days 500 times.</p>
      <p><strong>The MTA&rsquo;s numbers.</strong> MTA Bus Route Segment Speeds (data.ny.gov <a href="https://data.ny.gov/d/58t6-89vi" target="_blank" rel="noopener">58t6-89vi</a> for 2023 and 2024, <a href="https://data.ny.gov/d/kufs-yh3x" target="_blank" rel="noopener">kufs-yh3x</a> from 2025), weekdays 7 a.m. to 7 p.m., weighted by trips. Southbound uses the Flatbush Av/Atlantic Av to Flatbush Av/Ocean Av segment (1.72 miles); northbound uses Flatbush Av/Empire Blvd to Flatbush Av/Atlantic Av (1.73 miles). Neither segment changed length over the period. The tracker&rsquo;s figure for the same 1.7 miles is pooled the same way and shifted by its average gap from the MTA in July through October 2026.</p>
      <p><strong>Construction and detours.</strong> The city installed center lanes between Livingston Street and State Street starting Sept. 25, 2025, and resumed work between State Street and Grand Army Plaza on April 28, 2026 (city press releases and the Transportation Department&rsquo;s April 2026 construction briefing). During construction the B69 was detoured around Grand Army Plaza and the B63 was rerouted off its short run on Flatbush. On every day sampled, B41 and B67 buses ran on Flatbush through the work zone. The opening date on this page is the first day the tracker&rsquo;s speeds jumped, not an announced date.</p>
      <p><strong>What this can and can&rsquo;t say.</strong> The comparison is before and after, so it cannot separate the lanes from anything else that changed at the same time. One week is a short read: new lanes can draw extra attention from drivers and enforcement at first, and November traffic differs from spring. The tracker&rsquo;s archive starts after construction began, so comparisons with the time before construction rest on the MTA&rsquo;s monthly figures. The Transportation Department&rsquo;s figure of 4 mph for the B41 on the corridor before the project could not be checked against either source.</p>
      <p><strong>Files.</strong> <a href="data/spotlight/flatbush.json">flatbush.json</a> holds every number on this page. The scripts that build it are in <a href="https://github.com/joshgreenman1973/experiments/tree/main/nyc-bus-tracker/scripts/flatbush" target="_blank" rel="noopener">scripts/flatbush</a>.</p>`;
  }

  function render() { learned(); daily(); mtaCharts(); stretchTable(); hourCharts(); otherTable(); lanes(); method(); }

  document.querySelectorAll('[data-zero]').forEach(cb => cb.addEventListener('change', () => { zero[cb.dataset.zero] = cb.checked; daily(); mtaCharts(); hourCharts(); }));
  let rt;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (D) { daily(); mtaCharts(); hourCharts(); } }, 150); });
  BC.caution();

  Promise.all([
    fetch('data/spotlight/flatbush.json?v=1').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch('data/spotlight/other-lanes.json?v=2').then(r => (r.ok ? r.json() : null)).catch(() => null),
  ]).then(([d, l]) => {
    D = d; L = l;
    $('edition').innerHTML = `Tracker data through <b>${ap(D.daily[D.daily.length - 1].d, true)}</b>. MTA segment speeds through <b>${monthName(D.mta.months[D.mta.months.length - 1])}</b>.`;
    render();
  }).catch(e => {
    $('learned').innerHTML = `<li>The data for this page didn&rsquo;t load (${esc(e.message)}). Try reloading.</li>`;
  });
})();
