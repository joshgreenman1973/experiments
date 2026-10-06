#!/usr/bin/env node
/**
 * NYC Bus Tracker — daily processor, method version 2 (October 2026).
 *
 * Reads one ET day of raw snapshots (data/snapshots/YYYY-MM-DD/HH.jsonl, from
 * the bus-data branch) and writes data/daily/YYYY-MM-DD.json: per route, per
 * Eastern clock hour, the raw sums every later figure is built from. Nothing
 * here is averaged across routes or hours; rollup.js does that, so the
 * weighting rules live in one place.
 *
 * A "reading" is one bus seen in two consecutive snapshots of the same burst
 * (no more than 10 minutes apart) on the same route:
 *   - elapsed time comes from the bus's own GPS timestamp (RecordedAtTime),
 *     falling back to the snapshot clock only when a timestamp is missing;
 *     a bus whose GPS timestamp did not advance is skipped (no new position);
 *   - distance is the straight line between the two positions (snapshots are
 *     about 30 to 45 seconds apart, so the chord is close to the path);
 *   - readings where either position is flagged "layover" are skipped;
 *   - readings of 60 mph or more are GPS errors and are skipped.
 * From the readings, per route and hour:
 *   moving speed      mean of readings at 0.5 mph or more (method v1's figure)
 *   speed with stops  total distance / total time, stopped time included
 *   stopped share     share of reading time spent under 0.5 mph
 *
 * Usage: node process.js [YYYY-MM-DD]   (defaults to yesterday, Eastern)
 * Exits 1 when the day has no snapshots.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { routeKind, routeGroup, holidayOf, weekdayOf, etParts } from './routes.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const SNAPSHOTS_DIR = join(ROOT, 'data', 'snapshots');
const DAILY_DIR = join(ROOT, 'data', 'daily');
const SCHEDULE_FILE = join(ROOT, 'data', 'gtfs', 'scheduled-service.json');

export const METHOD_VERSION = 2;
const PAIR_MAX_GAP_S = 600;
const MIN_DT_S = 5;
const MOVING_MPH = 0.5;
const MAX_MPH = 60;
const MPS_TO_MPH = 2.2369363;

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const isLayover = v => {
  const p = v.phase;
  if (!p) return false;
  return Array.isArray(p) ? p.includes('layover') : String(p).includes('layover');
};

function yesterdayET() {
  return etParts(Date.now() - 86400000).date;
}

function loadSnapshots(date) {
  const flat = join(SNAPSHOTS_DIR, `${date}.jsonl`);
  const dir = join(SNAPSHOTS_DIR, date);
  const lines = [];
  if (existsSync(flat) && statSync(flat).isFile()) lines.push(...readFileSync(flat, 'utf8').split('\n'));
  if (existsSync(dir) && statSync(dir).isDirectory()) {
    for (const f of readdirSync(dir).filter(f => f.endsWith('.jsonl')).sort()) {
      lines.push(...readFileSync(join(dir, f), 'utf8').split('\n'));
    }
  }
  const snaps = [];
  const seen = new Set();
  for (const line of lines) {
    if (!line.trim()) continue;
    let s;
    try { s = JSON.parse(line); } catch { continue; }
    if (!s?.ts || !Array.isArray(s.vehicles) || seen.has(s.ts)) continue;
    seen.add(s.ts);
    snaps.push(s);
  }
  snaps.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  return snaps;
}

function loadSchedule(date) {
  if (!existsSync(SCHEDULE_FILE)) return null;
  try {
    const s = JSON.parse(readFileSync(SCHEDULE_FILE, 'utf8'));
    const pid = s.dates?.[date];
    return pid != null && s.patterns?.[pid] ? { pattern: pid, routes: s.patterns[pid] } : null;
  } catch { return null; }
}

// Per route-hour accumulator layout (kept as a flat array in the output):
const F = {
  nMov: 0,       // readings at or above 0.5 mph
  sumMov: 1,     // sum of those readings' mph
  dist: 2,       // meters, all readings
  time: 3,       // seconds, all readings
  stopTime: 4,   // seconds spent under 0.5 mph
  inSvc: 5,      // sum over snapshots of buses in service (not on layover)
  layover: 6,    // sum over snapshots of buses on layover
  nPax: 7,       // in-service buses reporting a passenger count
  sumPax: 8,     // sum of those counts
  trips: 9,      // distinct trip ids seen in service (snapshot format v2 only)
};
const NF = 10;

export function processDay(date) {
  const snaps = loadSnapshots(date);
  if (!snaps.length) {
    console.error(`No snapshots for ${date}`);
    process.exit(1);
  }

  const hours = {};            // ET hour -> { snaps, buses, layover }
  const routes = {};           // route -> { h: { hour: Float64Array(NF) }, tripSets }
  const formats = new Set();
  const cell = (route, hour) => {
    const r = (routes[route] ||= { h: {}, trips: {} });
    return (r.h[hour] ||= new Array(NF).fill(0));
  };
  let readings = 0, skippedStale = 0, skippedLayover = 0, skippedFast = 0;

  let prev = null, prevMap = null, prevTs = 0;
  for (const s of snaps) {
    formats.add(s.v || 1);
    const ts = Date.parse(s.ts);
    const { hour } = etParts(ts);
    const hs = (hours[hour] ||= { snaps: 0, buses: 0, layover: 0 });
    hs.snaps++;

    const map = new Map();
    for (const v of s.vehicles) {
      if (!v || !v.id || v.lat == null || v.lon == null) continue;
      map.set(v.id, v);
      const c = cell(v.route, hour);
      if (isLayover(v)) { c[F.layover]++; hs.layover++; continue; }
      c[F.inSvc]++;
      hs.buses++;
      if (v.pax != null) { c[F.nPax]++; c[F.sumPax] += v.pax; }
      if (v.trip) ((routes[v.route].trips[hour] ||= new Set())).add(v.trip);
    }

    if (prev && (ts - prevTs) / 1000 <= PAIR_MAX_GAP_S && ts > prevTs) {
      for (const [id, v] of map) {
        const p = prevMap.get(id);
        if (!p || p.route !== v.route) continue;
        if (isLayover(v) || isLayover(p)) { skippedLayover++; continue; }
        let dt;
        const t1 = Date.parse(p.timestamp || ''), t2 = Date.parse(v.timestamp || '');
        if (Number.isFinite(t1) && Number.isFinite(t2)) {
          dt = (t2 - t1) / 1000;
          if (dt < MIN_DT_S) { skippedStale++; continue; }   // GPS did not refresh
        } else {
          dt = (ts - prevTs) / 1000;
        }
        if (dt > PAIR_MAX_GAP_S) continue;
        const d = haversine(p.lat, p.lon, v.lat, v.lon);
        const mph = (d / dt) * MPS_TO_MPH;
        if (mph >= MAX_MPH) { skippedFast++; continue; }
        const c = cell(v.route, hour);
        c[F.dist] += d;
        c[F.time] += dt;
        if (mph >= MOVING_MPH) { c[F.nMov]++; c[F.sumMov] += mph; }
        else c[F.stopTime] += dt;
        readings++;
      }
    }
    prev = s; prevMap = map; prevTs = ts;
  }

  const schedule = loadSchedule(date);
  const out = {};
  for (const [route, r] of Object.entries(routes)) {
    const h = {};
    for (const [hour, c] of Object.entries(r.h)) {
      c[F.trips] = r.trips[hour] ? r.trips[hour].size : 0;
      h[hour] = c.map((x, i) => (i === F.sumMov || i === F.dist || i === F.time || i === F.stopTime) ? Math.round(x * 10) / 10 : x);
    }
    let sched = null;
    if (schedule) {
      const key = Object.keys(schedule.routes).find(k => k.toUpperCase() === route.toUpperCase());
      sched = key ? schedule.routes[key] : null;
    }
    out[route || '(blank)'] = { kind: routeKind(route), group: routeGroup(route), h, sched };
  }

  const holiday = holidayOf(date);
  return {
    methodVersion: METHOD_VERSION,
    generatedAt: new Date().toISOString(),
    date,
    weekday: weekdayOf(date),
    holiday,
    snapshotFormats: [...formats].sort(),
    snapshots: snaps.length,
    firstSnapshot: snaps[0].ts,
    lastSnapshot: snaps[snaps.length - 1].ts,
    readings,
    skipped: { staleGps: skippedStale, layover: skippedLayover, over60mph: skippedFast },
    schedulePattern: schedule ? schedule.pattern : null,
    fields: Object.keys(F),
    hours,
    routes: out,
  };
}

function main() {
  const date = process.argv[2] || yesterdayET();
  const day = processDay(date);
  mkdirSync(DAILY_DIR, { recursive: true });
  const file = join(DAILY_DIR, `${date}.json`);
  writeFileSync(file, JSON.stringify(day));
  const winHours = Object.keys(day.hours).map(Number).filter(h => h >= 6 && h <= 22 && day.hours[h].snaps >= 6);
  console.log(`${date}: ${day.snapshots} snapshots, ${winHours.length}/17 window hours, ${day.readings} readings, ` +
    `${Object.keys(day.routes).length} routes; skipped ${JSON.stringify(day.skipped)} -> ${file}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
