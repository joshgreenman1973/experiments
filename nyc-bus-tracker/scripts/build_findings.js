#!/usr/bin/env node
/**
 * Build data/findings/findings.json for findings.html ("Round and Round"),
 * method version 2.
 *
 * Runs after the daily processor (bus-tracker-findings.yml). It freezes at the
 * last complete ISO week, so the page changes once a week. Inputs:
 *   data/summary/weekly.json, weekly-routes.json, route-classes.json
 *   data/ridership/routes-monthly.json   MTA passenger counters and fare taps
 *   data/mta/official.json               MTA published metrics (optional)
 *   data/events/events.json              markers for the charts (optional)
 *
 * Headline speeds are weekday speed with stops: local, limited and Select Bus
 * Service routes, each counting once, every hour from 6 a.m. to 11 p.m.
 * counting equally. Only comparable weeks enter comparisons and trends.
 *
 * Fails loud (exit 1) on missing or implausible inputs.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8'));
const opt = p => (existsSync(join(ROOT, p)) ? read(p) : null);
const die = msg => { console.error('build_findings: ' + msg); process.exit(1); };

const ROUTE_MIN_BUSES = 5;
const r1 = x => (x == null || Number.isNaN(x) ? null : Math.round(x * 10) / 10);
const r2 = x => (x == null || Number.isNaN(x) ? null : Math.round(x * 100) / 100);
const mean = a => { const v = a.filter(x => x != null && Number.isFinite(x)); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
const canon = r => String(r || '').toUpperCase().replace(/^([A-Z]+)0+(\d)/, '$1$2');

const weeklyDoc = read('data/summary/weekly.json');
if (weeklyDoc.methodVersion !== 2) die('weekly.json is not method version 2');
const weekly = weeklyDoc.periods;
const wr = read('data/summary/weekly-routes.json');
const classes = read('data/summary/route-classes.json').routes || {};
const ridership = read('data/ridership/routes-monthly.json');
const official = opt('data/mta/official.json');
const events = opt('data/events/events.json')?.events || [];

// Complete weeks only; the running week is excluded so the page only moves
// when a week closes.
const full = weekly.filter(w => w.days === 7);
const comparable = full.filter(w => w.comparable);
if (comparable.length < 4) die(`only ${comparable.length} comparable weeks`);
const N = Math.min(4, Math.floor(comparable.length / 2));
const last = full[full.length - 1];

const system = full.map(w => ({
  week: w.period, start: w.weekStart, end: w.weekEnd, comparable: !!w.comparable, wdOk: !!w.wd.complete, weOk: !!w.we.complete, coverage: w.coveragePct,
  speed: w.wd.all, weekend: w.we.all, moving: w.wd.mov, stop: w.wd.stop,
  am: w.wd.bands?.am?.all ?? null, pm: w.wd.bands?.pm?.all ?? null,
  buses: w.wd.buses != null ? Math.round(w.wd.buses) : null, sched: w.wd.sched != null ? Math.round(w.wd.sched) : null,
  partialSpeed: w.wd.partial?.all ?? null,
}));
for (const s of system) {
  if (s.comparable && (s.speed < 3 || s.speed > 20 || s.buses < 500)) die(`implausible week ${s.week}: ${JSON.stringify(s)}`);
}

const baseline = comparable.slice(0, N), recent = comparable.slice(-N);
const summarize = ws => ({
  weeks: ws.map(w => w.period), start: ws[0].weekStart, end: ws[ws.length - 1].weekEnd,
  speed: r1(mean(ws.map(w => w.wd.all))), moving: r1(mean(ws.map(w => w.wd.mov))), weekend: r1(mean(ws.map(w => w.we.all))),
  buses: Math.round(mean(ws.map(w => w.wd.buses))),
});
function isoWeekIndex(label) { const [y, w] = label.split('-W').map(Number); return y * 53 + w; }
function slopePerWeek(ws, get) {
  const pts = ws.map(w => [isoWeekIndex(w.period), get(w)]).filter(p => p[1] != null);
  const mx = mean(pts.map(p => p[0])), my = mean(pts.map(p => p[1]));
  const num = pts.reduce((s, [x, y]) => s + (x - mx) * (y - my), 0), den = pts.reduce((s, [x]) => s + (x - mx) ** 2, 0);
  return den ? num / den : 0;
}

// The shape of a weekday: hour cells averaged over a set of weeks (Eastern).
function dayShape(ws) {
  const out = [];
  for (let h = 6; h <= 22; h++) {
    const cells = ws.map(w => w.hourly?.wd?.[h]).filter(c => c && c.n > 0);
    if (!cells.length) continue;
    out.push({ hour: h, speed: r1(mean(cells.map(c => c.all))), moving: r1(mean(cells.map(c => c.mov))), buses: Math.round(mean(cells.map(c => c.buses))), sched: cells.every(c => c.sched != null) ? Math.round(mean(cells.map(c => c.sched))) : null, weeks: cells.length });
  }
  return out;
}

// Boroughs: plain mean of comparable route weekday values; express routes are
// their own group.
const BORO = { M: 'Manhattan', B: 'Brooklyn', Q: 'Queens', Bx: 'Bronx', S: 'Staten Island', X: 'Express' };
const PANEL = new Set(['local', 'sbs', 'limited']);
const boroWeek = {};
for (const [route, ps] of Object.entries(wr.routes)) {
  const m = wr.meta[route] || {};
  if (!m.group || !(PANEL.has(m.kind) || m.kind === 'express')) continue;
  for (const p of ps) if (p.cwd && p.wd?.all != null) ((boroWeek[m.group] ||= {})[p.p] ||= []).push(p.wd.all);
}
const boroughs = Object.entries(BORO).map(([code, name]) => ({
  code, name,
  series: full.map(w => ({ week: w.period, start: w.weekStart, comparable: !!w.comparable, speed: w.comparable ? r1(mean(boroWeek[code]?.[w.period] || [])) : null })),
}));

// Routes over the recent comparable weeks, joined to riders.
const months = ridership.months;
const li = months.length - 1;
const rideKey = Object.fromEntries(Object.keys(ridership.routes).map(k => [canon(k), k]));
const recentSet = new Set(recent.map(w => w.period));
const routes = [];
for (const [route, ps] of Object.entries(wr.routes)) {
  const m = wr.meta[route] || {};
  if (!(PANEL.has(m.kind) || m.kind === 'express')) continue;
  const rs = ps.filter(p => recentSet.has(p.p) && p.cwd && p.wd?.all != null);
  if (rs.length < Math.max(1, N - 1)) continue;
  const buses = mean(rs.map(p => p.wd.buses));
  if (buses < ROUTE_MIN_BUSES) continue;
  const ride = ridership.routes[rideKey[canon(route)]];
  routes.push({
    route, borough: m.group, kind: m.kind,
    speed: r1(mean(rs.map(p => p.wd.all))), moving: r1(mean(rs.map(p => p.wd.mov))), stop: r2(mean(rs.map(p => p.wd.stop))),
    buses: r1(buses), busLaneShare: classes[route]?.busLaneShare ?? null,
    riders: ride ? ride.wdAvg[li] || null : null,
  });
}
if (routes.length < 50) die(`only ${routes.length} routes qualified`);
routes.sort((a, b) => a.speed - b.speed);

// Ridership: system counters and taps by month.
const sys = ridership.system;
const rideSeries = months.map((m, i) => ({ month: m, riders: sys.wdAvg[i], taps: sys.tapsWdAvg?.[i] ?? null }));
const last3 = mean(sys.wdAvg.slice(-3)), prior12 = months.length >= 15 ? mean(sys.wdAvg.slice(-15, -3)) : null;
const yearAgo3 = months.length >= 15 ? mean(sys.wdAvg.slice(-15, -12)) : null;

// ── what we've learned ──
const b = summarize(baseline), rc = summarize(recent);
const AP = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
const apDate = d => { const x = new Date(d + 'T00:00Z'); return `${AP[x.getUTCMonth()]} ${x.getUTCDate()}`; };
const fmtRange = (s, e) => `${apDate(s)} to ${apDate(e)}`;
const monthName = m => new Date(m + '-15T00:00Z').toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const shape = dayShape(recent);
const fastest = shape.reduce((a, h) => (h.speed > a.speed ? h : a));
const slowest = shape.reduce((a, h) => (h.speed < a.speed ? h : a));
const hourLabel = h => `${((h + 11) % 12) + 1} ${h < 12 ? 'a.m.' : 'p.m.'}`;
const recentBoro = boroughs.filter(x => x.code !== 'X').map(x => ({ name: x.name, speed: r1(mean(x.series.filter(s => recentSet.has(s.week)).map(s => s.speed))) }))
  .filter(x => x.speed != null).sort((p, q) => q.speed - p.speed);
const slope = slopePerWeek(comparable, w => w.wd.all);
const spanWeeks = isoWeekIndex(comparable[comparable.length - 1].period) - isoWeekIndex(comparable[0].period);
const net = slope * spanWeeks;
const dir = (d, eps, up, down, flat) => (Math.abs(d) < eps ? flat : d > 0 ? up : down);

// Speeds usually fall from August to September; say so when the recent weeks
// include September, using the MTA's own history.
const augSep = official?.season?.augSep || [];
const fell = augSep.filter(r => r.delta < 0).length;
const seasonNote = recent.some(w => w.weekStart.slice(5, 7) === '09' || w.weekEnd.slice(5, 7) === '09') && augSep.length
  ? ` September is usually slower than August: the MTA's own figure fell from August to September in ${fell} of the ${augSep.length} years since ${augSep[0].year}.`
  : '';
const amBand = mean(recent.map(w => w.wd.bands?.am?.all));
const learned = [
  {
    head: 'Speed',
    text: `On weekdays, buses averaged ${rc.speed} mph with stops included over the last ${N} comparable weeks (${fmtRange(rc.start, rc.end)}), against ${b.speed} mph in the first ${N} (${fmtRange(b.start, b.end)}). `
      + dir(net, 0.2, `The trend across all ${comparable.length} comparable weeks points up, about ${r1(net)} mph end to end.`, `The trend across all ${comparable.length} comparable weeks points down, about ${r1(Math.abs(net))} mph end to end.`,
        `Across all ${comparable.length} comparable weeks the trend is flat, moving less than a fifth of a mph end to end.`)
      + seasonNote
      + ` Weekends ran faster, ${rc.weekend?.toFixed(1)} mph recently.`,
  },
  {
    head: 'The day',
    text: `Weekday buses move fastest around ${hourLabel(fastest.hour)} (${fastest.speed} mph) and slowest around ${hourLabel(slowest.hour)} (${slowest.speed} mph).`
      + (slowest.hour >= 12 && amBand != null ? ` The 7-to-10 a.m. rush averages ${r1(amBand)} mph, faster than mid-afternoon.` : ''),
  },
  {
    head: 'Boroughs',
    text: `Among local routes, ${recentBoro[0].name} is the fastest at ${recentBoro[0].speed} mph and ${recentBoro[recentBoro.length - 1].name} the slowest at ${recentBoro[recentBoro.length - 1].speed} mph. The slowest busy route is the ${routes[0].route} at ${routes[0].speed} mph.`,
  },
  {
    head: 'Riders',
    text: prior12
      ? `Weekday boardings counted by the MTA's passenger counters averaged ${(last3 / 1e6).toFixed(2)} million over the three months through ${monthName(months[li])}, against ${(prior12 / 1e6).toFixed(2)} million in the twelve months before${yearAgo3 ? ` and ${(yearAgo3 / 1e6).toFixed(2)} million in the same three months a year earlier` : ''}. The counters are partial: they ran only ${Math.round((mean(sys.ratio.slice(-3)) - 1) * 100)}% above paid fare taps in those three months, though the MTA estimates about half of local riders don't pay.`
      : `Weekday boardings averaged ${(last3 / 1e6).toFixed(2)} million over the three months through ${monthName(months[li])}.`,
  },
  {
    head: 'A change of method',
    text: `Until October 2026 this page reported moving speed, which leaves out time stopped at stops and lights. Recently that measure read ${rc.moving} mph on weekdays, about ${r1(rc.moving - rc.speed)} mph above speed with stops. Every week was recomputed the new way, so the charts compare like with like.`,
  },
];
if (official?.numbers?.localPctWithStops != null) {
  const n = official.numbers;
  learned.splice(1, 0, {
    head: 'Checked against the MTA',
    text: `Ranked from slowest to fastest, the ${n.routesPaired} routes come out in nearly the same order as in the MTA's own figures for ${monthName(official.pairedMonth)}. The MTA's figure for the typical local route falls between the tracker's two measures: speed with stops reads ${n.localPctWithStops}% ${n.localMedianRatio > 1 ? 'faster' : 'slower'}, moving speed ${n.localPctMoving}% ${n.localMedianRatioMoving > 1 ? 'faster' : 'slower'}.`,
  });
}
if (official?.nowcast?.text) learned.push({ head: 'Ahead of the MTA', text: official.nowcast.text });

const out = {
  methodVersion: 2,
  generatedAt: new Date().toISOString(),
  asOf: { week: last.period, start: last.weekStart, end: last.weekEnd },
  totals: {
    firstDate: full[0].weekStart,
    fullWeeks: full.length,
    weeksElapsed: Math.round((new Date(last.weekEnd) - new Date(full[0].weekStart)) / 86400000 / 7),
    comparableWeeks: comparable.length,
    snapshots: full.reduce((s, w) => s + w.snapshots, 0),
    days: full.reduce((s, w) => s + w.days, 0),
  },
  periods: { baseline: b, recent: rc, speedSlopePerWeek: Math.round(slope * 1000) / 1000, n: N },
  learned,
  system,
  dayShape: { recent: shape, baseline: dayShape(baseline) },
  boroughs,
  routes,
  ridership: { lastMonth: months[li], series: rideSeries, source: ridership.source },
  events: events.filter(e => e.date >= full[0].weekStart && e.date <= last.weekEnd),
  official,
};

mkdirSync(join(ROOT, 'data/findings'), { recursive: true });
writeFileSync(join(ROOT, 'data/findings/findings.json'), JSON.stringify(out));
console.log(`findings.json: as of ${last.period}, ${comparable.length} comparable weeks (N=${N}), ${routes.length} routes`);
for (const l of learned) console.log(`  ${l.head}: ${l.text}`);
