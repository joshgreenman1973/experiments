#!/usr/bin/env node
/**
 * Export the tracker's series as flat CSVs into data/downloads/, plus the data
 * dictionary and the method changelog. Run by scripts/rebuild.sh after every
 * data refresh, and by the ridership workflow. Exits nonzero when a source file
 * is missing or an output would be empty, so a hollow CSV is never published.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'data', 'downloads');
mkdirSync(OUT, { recursive: true });

const readJson = (rel, optional = false) => {
  const p = join(ROOT, rel);
  if (!existsSync(p)) {
    if (optional) return null;
    console.error(`export_csv: missing ${rel}`); process.exit(1);
  }
  return JSON.parse(readFileSync(p, 'utf8'));
};
const esc = v => {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};
const writeCsv = (name, header, rows) => {
  if (!rows.length) { console.error(`export_csv: ${name} would be empty`); process.exit(1); }
  for (const r of rows) if (r.length !== header.length) { console.error(`export_csv: ${name} row width ${r.length} != ${header.length}`); process.exit(1); }
  writeFileSync(join(OUT, name), [header.join(',')].concat(rows.map(r => r.map(esc).join(','))).join('\n') + '\n');
  console.log(`${name}: ${rows.length} rows`);
};
const g = (o, ...ks) => ks.reduce((x, k) => (x == null ? null : x[k]), o) ?? null;

// ── system, by day ──────────────────────────────────────────────────────────
const days = readJson('data/summary/days.json');
writeCsv('daily-system.csv',
  ['date', 'weekday', 'day_type', 'day_type_reason', 'holiday', 'snapshots', 'hours_collected',
   'routes_running_midday', 'moving_mph', 'with_stops_mph', 'stopped_share', 'buses_in_service',
   'buses_in_service_regular_routes', 'trips_scheduled', 'method_version'],
  days.days.map(d => [d.date, ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.weekday], d.dayType, d.reason, d.holiday,
    d.snapshots, d.hoursCollected, d.routesMidday, d.mov, d.all, d.stop, d.buses, d.busesReg, d.sched, days.methodVersion]));

// ── system, by week and month ───────────────────────────────────────────────
const SYS_HEAD = ['period', 'start_date', 'end_date', 'days', 'weekdays', 'weekend_days', 'holiday_days',
  'coverage_pct', 'comparable', 'weekday_complete', 'weekend_complete',
  'index_moving_mph', 'index_with_stops_mph', 'index_stopped_share', 'index_buses_in_service',
  'weekday_moving_mph', 'weekday_with_stops_mph', 'weekday_stopped_share',
  'weekday_6am_moving_mph', 'weekday_am_peak_moving_mph', 'weekday_midday_moving_mph', 'weekday_pm_peak_moving_mph', 'weekday_evening_moving_mph',
  'weekday_am_peak_with_stops_mph', 'weekday_pm_peak_with_stops_mph',
  'weekday_buses_in_service', 'weekday_trips_scheduled', 'weekday_service_ratio',
  'weekend_moving_mph', 'weekend_with_stops_mph', 'weekend_stopped_share', 'weekend_buses_in_service',
  'mta_style_moving_mph', 'mta_style_with_stops_mph', 'snapshots', 'method_version'];
const sysRow = (p, mv) => [p.period, p.startDate, p.endDate, p.days, p.dayTypes.weekday, p.dayTypes.weekend, p.dayTypes.holiday,
  p.coveragePct, p.comparable, p.wd.complete, p.we.complete,
  p.idx.mov, p.idx.all, p.idx.stop, p.idx.buses,
  p.wd.mov, p.wd.all, p.wd.stop,
  g(p, 'wd', 'bands', 'early', 'mov'), g(p, 'wd', 'bands', 'am', 'mov'), g(p, 'wd', 'bands', 'mid', 'mov'), g(p, 'wd', 'bands', 'pm', 'mov'), g(p, 'wd', 'bands', 'eve', 'mov'),
  g(p, 'wd', 'bands', 'am', 'all'), g(p, 'wd', 'bands', 'pm', 'all'),
  p.wd.buses, p.wd.sched, p.wd.delivered ?? null,
  p.we.mov, p.we.all, p.we.stop, p.we.buses,
  p.mta.mov, p.mta.all, p.snapshots, mv];
const weekly = readJson('data/summary/weekly.json');
const monthly = readJson('data/summary/monthly.json');
writeCsv('weekly-system.csv', SYS_HEAD, weekly.periods.map(p => sysRow(p, weekly.methodVersion)));
writeCsv('monthly-system.csv', SYS_HEAD, monthly.periods.map(p => sysRow(p, monthly.methodVersion)));

// ── routes ──────────────────────────────────────────────────────────────────
const ROUTE_HEAD = ['route', 'kind', 'group', 'period', 'weekdays_seen', 'weekend_days_seen', 'weekday_comparable', 'weekend_comparable',
  'weekday_moving_mph', 'weekday_with_stops_mph', 'weekday_stopped_share',
  'weekday_am_peak_moving_mph', 'weekday_am_peak_with_stops_mph', 'weekday_midday_moving_mph',
  'weekday_pm_peak_moving_mph', 'weekday_pm_peak_with_stops_mph', 'weekday_evening_moving_mph',
  'weekday_hours_running', 'weekday_buses_in_service', 'weekday_trips_scheduled', 'weekday_passengers_per_bus',
  'weekend_moving_mph', 'weekend_with_stops_mph', 'weekend_buses_in_service'];
const routeRows = doc => {
  const rows = [];
  for (const [route, periods] of Object.entries(doc.routes)) {
    const m = doc.meta[route] || {};
    for (const p of periods) {
      rows.push([route, m.kind, m.group, p.p, p.wdN, p.weN, p.cwd, p.cwe,
        g(p, 'wd', 'mov'), g(p, 'wd', 'all'), g(p, 'wd', 'stop'),
        g(p, 'wd', 'am', 'mov'), g(p, 'wd', 'am', 'all'), g(p, 'wd', 'mid', 'mov'),
        g(p, 'wd', 'pm', 'mov'), g(p, 'wd', 'pm', 'all'), g(p, 'wd', 'eve', 'mov'),
        g(p, 'wd', 'hours'), g(p, 'wd', 'buses'), g(p, 'wd', 'sched'), g(p, 'wd', 'pax'),
        g(p, 'we', 'mov'), g(p, 'we', 'all'), g(p, 'we', 'buses')]);
    }
  }
  return rows.sort((a, b) => String(a[0]).localeCompare(String(b[0])) || String(a[3]).localeCompare(String(b[3])));
};
const weeklyRoutes = readJson('data/summary/weekly-routes.json');
const monthlyRoutes = readJson('data/summary/monthly-routes.json');
writeCsv('weekly-routes.csv', ROUTE_HEAD, routeRows(weeklyRoutes));
writeCsv('monthly-routes.csv', ROUTE_HEAD, routeRows(monthlyRoutes));

// ── boroughs: plain mean of the group's comparable route values ─────────────
const boroRows = [];
const acc = {};
for (const [route, periods] of Object.entries(weeklyRoutes.routes)) {
  const m = weeklyRoutes.meta[route] || {};
  if (!m.group || m.kind === 'shuttle' || m.kind === 'unknown') continue;
  for (const p of periods) {
    const k = p.p + '|' + m.group;
    const a = (acc[k] ||= { wdMov: [], wdAll: [], weMov: [], weAll: [] });
    if (p.cwd) { a.wdMov.push(p.wd.mov); a.wdAll.push(p.wd.all); }
    if (p.cwe) { a.weMov.push(p.we.mov); a.weAll.push(p.we.all); }
  }
}
const mean = a => { const v = a.filter(x => x != null); return v.length ? Math.round(100 * v.reduce((s, x) => s + x, 0) / v.length) / 100 : null; };
for (const [k, a] of Object.entries(acc)) {
  const [period, group] = k.split('|');
  if (!a.wdMov.length && !a.weMov.length) continue;
  boroRows.push([period, group, a.wdMov.length, mean(a.wdMov), mean(a.wdAll), a.weMov.length, mean(a.weMov), mean(a.weAll)]);
}
boroRows.sort((x, y) => (x[0] + x[1]).localeCompare(y[0] + y[1]));
writeCsv('weekly-borough.csv', ['period', 'group', 'weekday_routes', 'weekday_moving_mph', 'weekday_with_stops_mph',
  'weekend_routes', 'weekend_moving_mph', 'weekend_with_stops_mph'], boroRows);

// ── ridership ───────────────────────────────────────────────────────────────
const rm = readJson('data/ridership/routes-monthly.json');
const rmRows = [];
const at = (arr, i) => (Array.isArray(arr) ? arr[i] ?? null : null);
for (const [route, rec] of Object.entries(rm.routes)) {
  rm.months.forEach((mo, i) => {
    if (rec.total[i] > 0 || at(rec.tapsTotal, i) > 0) {
      rmRows.push([route, mo, rec.total[i], rec.wdAvg[i], at(rec.tapsTotal, i), at(rec.tapsWdAvg, i), at(rec.ratio, i),
        (rec.breakMonths || []).includes(mo)]);
    }
  });
}
writeCsv('route-ridership-monthly.csv',
  ['route', 'month', 'counter_boardings', 'counter_avg_weekday', 'fare_taps', 'fare_taps_avg_weekday',
   'counter_to_taps_ratio', 'network_change_this_month'], rmRows);

const sp = readJson('data/ridership/stops.json');
const hourCols = [];
for (let h = 0; h < 24; h++) hourCols.push(`wd_total_h${h}`);
for (let h = 0; h < 24; h++) hourCols.push(`we_total_h${h}`);
writeCsv('stops-hourly-june2026.csv',
  ['stop_id', 'name', 'lon', 'lat', 'routes', 'month_boardings', 'month_alightings',
   'm_to_subway', 'in_crz', 'weekday_days', 'weekend_days'].concat(hourCols),
  sp.stops.map(s => [s[0], s[1], s[2], s[3], (s[4] || []).join(' '), s[7], s[8],
    s[9] ?? '', s[10] ?? '', sp.days.wd, sp.days.we].concat(s[5], s[6])));

const rc = readJson('data/summary/route-classes.json');
writeCsv('route-classes.csv', ['route', 'bus_lane_share', 'cbd_relation'],
  Object.entries(rc.routes).map(([r, c]) => [r, c.busLaneShare, c.cbd]));

// ── MTA comparison and events ───────────────────────────────────────────────
const official = readJson('data/mta/official.json', true);
if (official?.speedSeries?.months?.length) {
  const s = official.speedSeries;
  writeCsv('mta-comparison.csv',
    ['month', 'mta_headline_mph', 'mta_route_hour_equal_mph', 'ours_with_stops_mph', 'ours_moving_mph', 'nowcast_mta_headline_mph'],
    s.months.map((m, i) => [m, official.numbers?.mtaHeadline?.[m] ?? null, at(s.mta, i), at(s.oursAll, i), at(s.oursMov, i),
      official.nowcast?.month === m ? official.nowcast.value : null]));
}
const ev = readJson('data/events/events.json', true);
if (ev?.events?.length) {
  writeCsv('events.csv', ['date', 'end_date', 'kind', 'label', 'detail'],
    ev.events.map(e => [e.date, e.end || '', e.kind, e.label, e.detail || '']));
}

// ── dictionary and changelog ────────────────────────────────────────────────
writeFileSync(join(OUT, 'DATA-DICTIONARY.txt'), readFileSync(join(ROOT, 'scripts', 'DATA-DICTIONARY.txt'), 'utf8'));
writeFileSync(join(OUT, 'CHANGELOG.txt'), readFileSync(join(ROOT, 'scripts', 'CHANGELOG.txt'), 'utf8'));
console.log('DATA-DICTIONARY.txt and CHANGELOG.txt copied');
