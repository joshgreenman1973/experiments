#!/usr/bin/env node
/**
 * Build data/findings/findings.json for findings.html ("Round and Round").
 *
 * Runs weekly (bus-tracker-findings.yml, Monday morning, after the daily
 * processor has rolled up Sunday). It reads only files the other workflows
 * already publish, and it freezes everything at the LAST COMPLETE ISO WEEK,
 * so the page changes once a week rather than every morning.
 *
 * Inputs:
 *   data/summary/weekly.json          system + borough + hourly, per ISO week
 *   data/summary/weekly-routes.json   per route, per ISO week
 *   data/summary/route-classes.json   bus-lane share per route
 *   data/ridership/routes-monthly.json  MTA passenger-counter boardings
 *   data/mta/official.json            (optional) MTA published metrics, from
 *                                     scripts/fetch_mta_official.py
 *
 * Fails loud (exit 1) on missing or implausible inputs, so a broken upstream
 * never quietly publishes an empty page.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));
const die = msg => { console.error('build_findings: ' + msg); process.exit(1); };

const RECENT_N = 4;      // "recently" = the last 4 comparable weeks
const BASELINE_N = 5;    // "at the start" = the first 5 comparable weeks
const ROUTE_MIN_BUSES = 5;

const r1 = x => (x == null || Number.isNaN(x) ? null : Math.round(x * 10) / 10);
const mean = a => { const v = a.filter(x => x != null); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };

// ── inputs ──
const weekly = read('data/summary/weekly.json');
const weeklyRoutes = read('data/summary/weekly-routes.json');
const classes = read('data/summary/route-classes.json').routes || {};
const ridership = read('data/ridership/routes-monthly.json');
const official = existsSync(join(ROOT, 'data/mta/official.json')) ? read('data/mta/official.json') : null;

if (!Array.isArray(weekly) || weekly.length < 5) die('weekly.json missing or too short');

// Complete weeks only. The current, still-running week is excluded so the page
// only moves when a week closes.
const full = weekly.filter(w => w.days === 7 && w.avgSpeedHourNorm != null);
const comparable = full.filter(w => w.comparable);
if (comparable.length < BASELINE_N + RECENT_N) die(`only ${comparable.length} comparable weeks`);
const last = full[full.length - 1];

// ET offset for a date (hourly keys in weekly.json are the runner's UTC hours).
function etOffsetHours(dateStr) {
  const d = new Date(dateStr + 'T12:00:00Z');
  const et = new Date(d.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const utc = new Date(d.toLocaleString('en-US', { timeZone: 'UTC' }));
  return Math.round((et - utc) / 3600000); // -4 in summer, -5 in winter
}

// Buses in service with every captured hour weighted equally, so weeks that
// caught more late-evening hours (fewer buses) don't look like service cuts.
const busesHourNorm = w => {
  const v = Object.values(w.hourly || {}).map(h => h.avgBuses).filter(x => x != null);
  return v.length ? Math.round(mean(v)) : null;
};

// ── system series ──
const system = full.map(w => ({
  week: w.period,
  start: w.startDate,
  end: w.endDate,
  comparable: !!w.comparable,
  coverage: w.coveragePct,
  speed: w.avgSpeedHourNorm,
  buses: busesHourNorm(w),
  peakBuses: w.peakActiveBuses,
  weekdaySpeed: w.weekday?.avgSpeed ?? null,
  weekendSpeed: w.weekend?.avgSpeed ?? null,
}));

for (const s of system) {
  if (s.comparable && (s.speed < 4 || s.speed > 20 || s.buses < 500)) die(`implausible week ${s.week}: ${JSON.stringify(s)}`);
}

const baseline = comparable.slice(0, BASELINE_N);
const recent = comparable.slice(-RECENT_N);
const periodOf = ws => ({ weeks: ws.map(w => w.period), start: ws[0].startDate, end: ws[ws.length - 1].endDate });
const avgOf = (ws, k) => r1(mean(ws.map(w => w[k])));
const summarize = ws => ({
  ...periodOf(ws),
  speed: avgOf(ws, 'avgSpeedHourNorm'),
  buses: Math.round(mean(ws.map(busesHourNorm))),
});

// Least-squares slope per week across comparable weeks, indexed by real week
// number so the June hole counts as elapsed time.
function isoWeekIndex(label) { const [y, w] = label.split('-W').map(Number); return y * 53 + w; }
function slopePerWeek(ws, k) {
  const pts = ws.map(w => [isoWeekIndex(w.period), w[k]]).filter(p => p[1] != null);
  const n = pts.length, mx = mean(pts.map(p => p[0])), my = mean(pts.map(p => p[1]));
  const num = pts.reduce((s, [x, y]) => s + (x - mx) * (y - my), 0);
  const den = pts.reduce((s, [x]) => s + (x - mx) ** 2, 0);
  return den ? num / den : 0;
}

// ── the shape of the day ──
function dayShape(ws) {
  const acc = {};
  for (const w of ws) {
    const off = etOffsetHours(w.startDate);
    for (const [h, v] of Object.entries(w.hourly || {})) {
      const et = (Number(h) + off + 24) % 24;
      (acc[et] ||= []).push(v);
    }
  }
  return Object.keys(acc).map(Number).sort((a, b) => ((a + 21) % 24) - ((b + 21) % 24)) // 3am-first ordering
    .map(h => {
      const vs = acc[h];
      const buses = mean(vs.map(v => v.avgBuses));
      return {
        hour: h,
        speed: r1(mean(vs.map(v => v.avgSpeed))),
        buses: Math.round(buses),
        weeks: vs.length,
      };
    });
}

// ── boroughs ──
// Rebuilt from route-level weeks so express buses (BM, BxM, QM, SIM, X) form
// their own group instead of riding along with the borough letter. The MTA
// comparison showed SIM express routes were dragging the "S" line.
const EXPRESS = /^(BM|BXM|QM|SIM|X)\d/i;
const groupOf = route => {
  if (EXPRESS.test(route)) return 'X';
  const r = route.toUpperCase();
  if (r.startsWith('BX')) return 'Bx';
  for (const c of ['B', 'Q', 'M', 'S']) if (r.startsWith(c)) return c;
  return null;
};
const BORO = { M: 'Manhattan', B: 'Brooklyn', Q: 'Queens', Bx: 'Bronx', S: 'Staten Island', X: 'Express' };
const boroWeek = {}; // code -> week -> {speed:[]}
for (const [route, recs] of Object.entries(weeklyRoutes)) {
  const code = groupOf(route);
  if (!code) continue;
  for (const r of recs) {
    if (r.avgSpeed == null || r.daysSeen < 4) continue;
    const cell = ((boroWeek[code] ||= {})[r.period] ||= { speed: [] });
    cell.speed.push(r.avgSpeed);
  }
}
const boroughs = Object.entries(BORO).map(([code, name]) => ({
  code, name,
  series: full.map(w => ({
    week: w.period, start: w.startDate, comparable: !!w.comparable,
    speed: r1(mean(boroWeek[code]?.[w.period]?.speed || [])),
  })),
}));

// ── routes (recent comparable weeks) ──
const months = ridership.months;
const lastRideMonth = months[months.length - 1];
const recentWeeks = new Set(recent.map(w => w.period));
const routes = [];
for (const [route, recs] of Object.entries(weeklyRoutes)) {
  const rs = recs.filter(r => recentWeeks.has(r.period) && r.avgSpeed != null && r.daysSeen >= 5);
  if (rs.length < RECENT_N - 1) continue;
  const buses = mean(rs.map(r => r.avgBuses));
  if (buses < ROUTE_MIN_BUSES) continue;
  const ride = ridership.routes[route];
  routes.push({
    route,
    borough: rs[0].borough,
    speed: r1(mean(rs.map(r => r.avgSpeed))),
    buses: r1(buses),
    busLaneShare: classes[route]?.busLaneShare ?? null,
    riders: ride ? ride.wdAvg[ride.wdAvg.length - 1] : null,
  });
}
if (routes.length < 50) die(`only ${routes.length} routes qualified`);
routes.sort((a, b) => a.speed - b.speed);

// ── ridership ──
const sys = ridership.system.wdAvg;
const monthIdx = Object.fromEntries(months.map((m, i) => [m, i]));
const rideSeries = months.map((m, i) => {
  const prior = `${Number(m.slice(0, 4)) - 1}${m.slice(4)}`;
  return { month: m, riders: sys[i], priorYear: monthIdx[prior] != null ? sys[monthIdx[prior]] : null };
});
const lastTen = sys.slice(-10), priorTen = months.length >= 22 ? sys.slice(-22, -12) : null;

// ── what we've learned (facts, generated from the numbers above) ──
const b = summarize(baseline), rc = summarize(recent);
const AP = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
const apDate = d => { const x = new Date(d + 'T00:00Z'); return `${AP[x.getUTCMonth()]} ${x.getUTCDate()}`; };
const fmtRange = (s, e) => `${apDate(s)} to ${apDate(e)}`;
const monthName = m => new Date(m + '-15T00:00Z').toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const shape = dayShape(recent);
const svc = shape.filter(h => h.buses > 1000);
const fastest = svc.reduce((a, h) => (h.speed > a.speed ? h : a));
const slowest = svc.reduce((a, h) => (h.speed < a.speed ? h : a));
const hourLabel = h => `${((h + 11) % 12) + 1} ${h < 12 ? 'a.m.' : 'p.m.'}`;
const recentBoro = boroughs.filter(x => x.code !== 'X').map(x => ({ name: x.name, speed: r1(mean(x.series.filter(s => recentWeeks.has(s.week)).map(s => s.speed))) }))
  .sort((p, q) => q.speed - p.speed);
const speedSlope = slopePerWeek(comparable, 'avgSpeedHourNorm');

const num = n => n.toLocaleString('en-US');
const dir = (d, eps, up, down, flat) => (Math.abs(d) < eps ? flat : d > 0 ? up : down);
const learned = [
  {
    head: 'Speed',
    text: `Buses averaged ${rc.speed} mph over the last ${RECENT_N} full weeks (${fmtRange(rc.start, rc.end)}), against ${b.speed} mph in the first ${BASELINE_N} (${fmtRange(b.start, b.end)}). `
      + dir(speedSlope * comparable.length, 0.3, `The trend across all ${comparable.length} usable weeks points up.`, `The trend across all ${comparable.length} usable weeks points down.`, `Across all ${comparable.length} usable weeks the trend is flat, moving less than a third of a mph end to end.`),
  },
  {
    head: 'The day',
    text: `Buses move fastest around ${hourLabel(fastest.hour)} (${fastest.speed} mph) and slowest around ${hourLabel(slowest.hour)} (${slowest.speed} mph).`
      + (slowest.hour >= 12 ? ' The afternoon, not the morning rush, is the slow part of the day.' : ''),
  },
  {
    head: 'Boroughs',
    text: `Among local routes, ${recentBoro[0].name} is the fastest at ${recentBoro[0].speed} mph and ${recentBoro[recentBoro.length - 1].name} the slowest at ${recentBoro[recentBoro.length - 1].speed} mph. The slowest busy route is the ${routes[0].route} at ${routes[0].speed} mph.`,
  },
  {
    head: 'Riders',
    text: priorTen
      ? `Weekday boardings averaged ${(mean(lastTen) / 1e6).toFixed(2)} million over the 10 months through ${monthName(lastRideMonth)}, ${Math.abs(Math.round((mean(lastTen) / mean(priorTen) - 1) * 1000) / 10)}% ${mean(lastTen) < mean(priorTen) ? 'below' : 'above'} the same 10 months a year earlier (${(mean(priorTen) / 1e6).toFixed(2)} million).`
      : `Weekday boardings averaged ${(mean(lastTen) / 1e6).toFixed(2)} million over the 10 months through ${monthName(lastRideMonth)}.`,
  },
];
if (official?.numbers?.rankCorrelation != null) {
  const n = official.numbers;
  learned.splice(1, 0, {
    head: 'Checked against the MTA',
    text: `Ranked from slowest to fastest, the ${n.routesPaired} routes come out in nearly the same order as in the MTA's own figures for ${monthName(official.pairedMonth)}. On local routes, though, the tracker reads about ${Math.round((n.localMedianRatio - 1) * 100)}% faster than the MTA, so its speeds are best read as trends and comparisons, not exact figures.`,
  });
}

const out = {
  generatedAt: new Date().toISOString(),
  asOf: { week: last.period, start: last.startDate, end: last.endDate },
  totals: {
    firstDate: full[0].startDate,
    fullWeeks: full.length,
    weeksElapsed: Math.round((new Date(last.endDate) - new Date(full[0].startDate)) / 86400000 / 7),
    comparableWeeks: comparable.length,
    snapshots: full.reduce((s, w) => s + w.totalSnapshots, 0),
    days: full.reduce((s, w) => s + w.days, 0),
  },
  periods: { baseline: b, recent: rc, speedSlopePerWeek: Math.round(speedSlope * 1000) / 1000 },
  learned,
  system,
  dayShape: { recent: shape, baseline: dayShape(baseline) },
  boroughs,
  routes,
  ridership: { lastMonth: lastRideMonth, series: rideSeries, source: ridership.source },
  official,
};

mkdirSync(join(ROOT, 'data/findings'), { recursive: true });
writeFileSync(join(ROOT, 'data/findings/findings.json'), JSON.stringify(out));
console.log(`findings.json: as of ${last.period}, ${comparable.length} comparable weeks, ${routes.length} routes`);
for (const l of learned) console.log(`  ${l.head}: ${l.text}`);
