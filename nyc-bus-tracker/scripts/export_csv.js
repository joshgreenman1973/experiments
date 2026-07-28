#!/usr/bin/env node
/**
 * Export the tracker's JSON series as flat CSVs into data/downloads/.
 * Run after each data refresh (process-daily and ridership workflows call it);
 * safe to run by hand. Exits nonzero if a source file is missing or an output
 * would be empty — never silently publishes a hollow CSV.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, 'data', 'downloads');
fs.mkdirSync(OUT, { recursive: true });

const readJson = (rel) => {
  const p = path.join(ROOT, rel);
  if (!fs.existsSync(p)) { console.error(`FATAL: missing ${rel}`); process.exit(1); }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
};
const esc = (v) => {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};
const writeCsv = (name, header, rows) => {
  if (!rows.length) { console.error(`FATAL: ${name} would be empty`); process.exit(1); }
  const body = [header.join(',')].concat(rows.map((r) => r.map(esc).join(','))).join('\n');
  fs.writeFileSync(path.join(OUT, name), body + '\n');
  console.log(`${name}: ${rows.length} rows`);
};

// 1. weekly system metrics
const weekly = readJson('data/summary/weekly.json');
writeCsv('weekly-system.csv',
  ['period', 'start_date', 'end_date', 'days', 'coverage_pct', 'comparable',
   'avg_speed_hour_norm_mph', 'avg_wait_hour_norm_min', 'bunch_per_100_buses',
   'avg_speed_raw_mph', 'avg_wait_raw_min', 'reliability_pct',
   'routes_with_20min_gaps_per_snap', 'avg_active_buses', 'peak_active_buses'],
  weekly.map((w) => [w.period, w.startDate, w.endDate, w.days, w.coveragePct, w.comparable,
    w.avgSpeedHourNorm, w.avgWaitHourNorm, w.bunchPer100Buses, w.avgSpeed, w.avgWait,
    w.avgReliability, w.avgBigGap20PerSnap, w.avgActiveBuses, w.peakActiveBuses]));

// 2. weekly by borough
const boroRows = [];
for (const w of weekly) {
  for (const [code, b] of Object.entries(w.byBorough || {})) {
    boroRows.push([w.period, code, b.daysSeen, b.avgSpeed, b.avgWait, b.avgBuses,
      b.bunchPairsPerSnap,
      b.avgBuses > 0 && b.bunchPairsPerSnap != null
        ? Math.round(1000 * b.bunchPairsPerSnap / b.avgBuses) / 10 : '']);
  }
}
writeCsv('weekly-borough.csv',
  ['period', 'borough', 'days_seen', 'avg_speed_mph', 'avg_wait_min', 'avg_buses',
   'bunch_pairs_per_snapshot', 'bunch_per_100_buses'], boroRows);

// 3. weekly by route
const weeklyRoutes = readJson('data/summary/weekly-routes.json');
const routeRows = [];
for (const [route, hist] of Object.entries(weeklyRoutes)) {
  for (const r of hist) {
    routeRows.push([route, r.period, r.borough, r.daysSeen, r.avgSpeed, r.avgWait,
      r.avgReliability, r.avgBunchingPerDay, r.avgBuses, r.bigGap20Count, r.bigGap30Count]);
  }
}
writeCsv('weekly-routes.csv',
  ['route', 'period', 'borough', 'days_seen', 'avg_speed_mph', 'avg_wait_min',
   'reliability_pct', 'bunching_events_per_day', 'avg_buses', 'gap20_count', 'gap30_count'],
  routeRows);

// 4. route ridership monthly
const rm = readJson('data/ridership/routes-monthly.json');
const rmRows = [];
for (const [route, rec] of Object.entries(rm.routes)) {
  rm.months.forEach((m, i) => {
    if (rec.total[i] > 0) rmRows.push([route, m, rec.total[i], rec.wdAvg[i]]);
  });
}
writeCsv('route-ridership-monthly.csv',
  ['route', 'month', 'total_boardings', 'avg_weekday_boardings'], rmRows);

// 5. stop-level hourly boardings (month totals; divide by wd/we day counts for daily avgs)
const sp = readJson('data/ridership/stops.json');
const hourCols = [];
for (let h = 0; h < 24; h++) hourCols.push(`wd_total_h${h}`);
for (let h = 0; h < 24; h++) hourCols.push(`we_total_h${h}`);
writeCsv('stops-hourly-june2026.csv',
  ['stop_id', 'name', 'lon', 'lat', 'routes', 'month_boardings', 'month_alightings',
   'm_to_subway', 'in_crz', `weekday_days=${sp.days.wd}`, `weekend_days=${sp.days.we}`]
    .slice(0, 9).concat(hourCols),
  sp.stops.map((s) => [s[0], s[1], s[2], s[3], (s[4] || []).join(' '), s[7], s[8],
    s[9] ?? '', s[10] ?? ''].concat(s[5], s[6])));

// 6. route geography classes
const rc = readJson('data/summary/route-classes.json');
writeCsv('route-classes.csv', ['route', 'bus_lane_share', 'cbd_relation'],
  Object.entries(rc.routes).map(([r, c]) => [r, c.busLaneShare, c.cbd]));

console.log('CSV export complete.');
