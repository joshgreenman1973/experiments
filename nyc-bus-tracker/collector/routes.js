/**
 * Shared route and calendar helpers for process.js, rollup.js and the build
 * scripts. The browser pages carry a copy of routeKind/canonRoute in their
 * own files; keep the rules in step.
 */
import { existsSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

export const EXPRESS_RE = /^(BM|BXM|QM|SIM|X)\d/i;

/** Join key for route ids from different MTA sources. The live feed and GTFS
 *  say "Q06"; the passenger-counter data says "Q6". */
export function canonRoute(id) {
  return String(id || '').toUpperCase().replace(/^([A-Z]+)0+(\d)/, '$1$2');
}

/** Borough group by the letters in the route name; express routes are "X". */
export function routeGroup(id) {
  const r = String(id || '').toUpperCase();
  if (!r) return null;
  if (EXPRESS_RE.test(r)) return 'X';
  if (r.startsWith('BX')) return 'Bx';
  for (const c of ['B', 'Q', 'M', 'S']) if (r.startsWith(c)) return c;
  return null;
}

let routeTable = null;
/** Regular routes, from the GTFS route table (scripts/build_gtfs.py) or, before
 *  that file exists, from the route shapes file. Anything the live feed shows
 *  that is not in GTFS (T102, B90, L92 ...) is a temporary shuttle. */
export function loadRouteTable() {
  if (routeTable) return routeTable;
  const tablePath = join(ROOT, 'data', 'routes', 'route-table.json');
  const shapesPath = join(ROOT, 'data', 'routes', 'routes.geojson');
  const routes = {};
  if (existsSync(tablePath)) {
    const t = JSON.parse(readFileSync(tablePath, 'utf8'));
    for (const [id, r] of Object.entries(t.routes || {})) routes[canonRoute(id)] = { id, ...r };
  } else if (existsSync(shapesPath)) {
    const g = JSON.parse(readFileSync(shapesPath, 'utf8'));
    for (const f of g.features || []) {
      const id = f.properties.routeId || f.properties.route;
      if (id) routes[canonRoute(id)] = { id: id.toUpperCase(), long: f.properties.longName || '' };
    }
  }
  routeTable = routes;
  return routes;
}

/** local | sbs | limited | express | shuttle | unknown. Local, limited and
 *  SBS together make up the "local routes" panel behind the speed index. */
export function routeKind(id) {
  const r = String(id || '').toUpperCase();
  if (!r) return 'unknown';
  if (EXPRESS_RE.test(r)) return 'express';
  const table = loadRouteTable();
  const known = Object.keys(table).length > 0;
  const row = table[canonRoute(r)];
  if (known && !row) return 'shuttle';
  if (row?.kind && row.kind !== 'express') return row.kind;
  return r.endsWith('+') ? 'sbs' : 'local';
}

export const isPanelRoute = id => ['local', 'sbs', 'limited'].includes(routeKind(id));
export const isRegularRoute = id => ['local', 'sbs', 'limited', 'express'].includes(routeKind(id));

// ── calendar ────────────────────────────────────────────────────────────────
// Public holidays. "major" days run holiday (Sunday-style) bus service and are
// kept out of the weekday series outright; rollup.js also drops any weekday
// whose route count says service was cut, which catches the rest.
export const HOLIDAYS = {
  '2026-01-01': ['New Year\'s Day', 'major'],
  '2026-01-19': ['Martin Luther King Jr. Day', 'minor'],
  '2026-02-16': ['Presidents\' Day', 'minor'],
  '2026-05-25': ['Memorial Day', 'major'],
  '2026-06-19': ['Juneteenth', 'major'],
  '2026-07-03': ['Independence Day (observed)', 'major'],
  '2026-09-07': ['Labor Day', 'major'],
  '2026-10-12': ['Columbus Day / Indigenous Peoples\' Day', 'minor'],
  '2026-11-11': ['Veterans Day', 'minor'],
  '2026-11-26': ['Thanksgiving', 'major'],
  '2026-11-27': ['Day after Thanksgiving', 'minor'],
  '2026-12-25': ['Christmas', 'major'],
  '2027-01-01': ['New Year\'s Day', 'major'],
  '2027-01-18': ['Martin Luther King Jr. Day', 'minor'],
  '2027-02-15': ['Presidents\' Day', 'minor'],
  '2027-05-31': ['Memorial Day', 'major'],
  '2027-06-18': ['Juneteenth (observed)', 'major'],
  '2027-07-05': ['Independence Day (observed)', 'major'],
  '2027-09-06': ['Labor Day', 'major'],
  '2027-10-11': ['Columbus Day / Indigenous Peoples\' Day', 'minor'],
  '2027-11-11': ['Veterans Day', 'minor'],
  '2027-11-25': ['Thanksgiving', 'major'],
  '2027-11-26': ['Day after Thanksgiving', 'minor'],
  '2027-12-24': ['Christmas (observed)', 'major'],
};

export function holidayOf(date) {
  const h = HOLIDAYS[date];
  return h ? { name: h[0], type: h[1] } : null;
}

/** 0 = Sunday … 6 = Saturday for a YYYY-MM-DD calendar date. */
export function weekdayOf(date) {
  return new Date(date + 'T00:00:00Z').getUTCDay();
}

/** ISO-8601 week label. Midnight UTC: a noon anchor shifted every label in
 *  years that start on a Friday (Dec. 27, 2027 came out as W53). */
export function isoWeek(date) {
  const d = new Date(date + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

/** ET calendar date and clock hour for an instant. */
const fmt = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', hourCycle: 'h23',
});
export function etParts(isoOrDate) {
  const parts = Object.fromEntries(fmt.formatToParts(new Date(isoOrDate)).map(p => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour) };
}

// Analysis window: clock hours 6 through 22 Eastern (6:00 a.m. to 10:59 p.m.),
// the hours the collector covers. Seventeen hours.
export const WINDOW_HOURS = Array.from({ length: 17 }, (_, i) => i + 6);
export const BANDS = {
  early: [6],
  am: [7, 8, 9],
  mid: [10, 11, 12, 13, 14, 15],
  pm: [16, 17, 18],
  eve: [19, 20, 21, 22],
};
