#!/usr/bin/env node
/**
 * NYC Bus Tracker — Daily Processor
 * Reads a day's JSONL snapshots and computes:
 * - Per-route average speed (route-weighted, consistent with MTA methodology)
 * - Bunching events (buses within 250m on same route/direction)
 * - Gap events (long intervals without buses)
 * - Route reliability scores
 * - System-wide summary stats for historical tracking
 *
 * Usage: node process.js [YYYY-MM-DD]
 * Defaults to yesterday if no date provided.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SNAPSHOTS_DIR = join(__dirname, '..', 'data', 'snapshots');
const DAILY_DIR = join(__dirname, '..', 'data', 'daily');

const BUNCHING_DISTANCE_M = 250;
const DEFAULT_SPEED_MPH = 8; // assumption when a route has no observed speed yet
const GAP_CAP_MIN = 60; // cap individual gaps to avoid terminus skew (matches live app)
const BIG_GAP_20 = 20;
const BIG_GAP_30 = 30;

/** Borough bucket from MTA route shortname. Mirrors live-app prefix matching. */
function boroughOf(route) {
  if (!route) return 'unknown';
  const r = route.toUpperCase();
  if (r.startsWith('BX')) return 'Bx';
  if (r.startsWith('B')) return 'B';
  if (r.startsWith('S')) return 'S';
  if (r.startsWith('Q')) return 'Q';
  if (r.startsWith('M')) return 'M';
  if (r.startsWith('X')) return 'X'; // express
  return 'other';
}

function percentile(arr, p) {
  if (arr.length === 0) return null;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[idx];
}

function isWeekendDate(dateStr) {
  // dateStr is "YYYY-MM-DD" — interpret as ET local date for the weekday lookup.
  // ISO-week math handled separately; here we just need Sat/Sun detection.
  const d = new Date(dateStr + 'T12:00:00Z');
  const day = d.getUTCDay();
  return day === 0 || day === 6;
}

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function round1(n) {
  return Math.round(n * 10) / 10;
}

function avg(arr) {
  return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
}

function getDate(offsetDays = -1) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function parseJsonlBuffer(text) {
  return text.trim().split('\n').map(line => {
    try { return JSON.parse(line); }
    catch { return null; }
  }).filter(Boolean);
}

/** Load all snapshots for a given date, sorted by timestamp.
 *  Supports both layouts:
 *   - legacy: data/snapshots/YYYY-MM-DD.jsonl  (single file)
 *   - hourly: data/snapshots/YYYY-MM-DD/HH.jsonl  (one file per hour ET)
 *  If both exist (unlikely but possible during migration), they're merged. */
function loadSnapshots(date) {
  const flat = join(SNAPSHOTS_DIR, `${date}.jsonl`);
  const dir  = join(SNAPSHOTS_DIR, date);
  const all = [];

  if (existsSync(flat) && statSync(flat).isFile()) {
    all.push(...parseJsonlBuffer(readFileSync(flat, 'utf-8')));
  }
  if (existsSync(dir) && statSync(dir).isDirectory()) {
    const files = readdirSync(dir)
      .filter(f => f.endsWith('.jsonl'))
      .sort(); // 00.jsonl..23.jsonl naturally chronological
    for (const f of files) {
      all.push(...parseJsonlBuffer(readFileSync(join(dir, f), 'utf-8')));
    }
  }

  if (all.length === 0) {
    console.error(`No data file for ${date} (looked at ${flat} and ${dir}/)`);
    process.exit(1);
  }

  // Defensive: sort by timestamp in case files arrived out of order
  all.sort((a, b) => new Date(a.ts) - new Date(b.ts));
  return all;
}

/**
 * Compute per-bus speeds between two consecutive snapshots.
 * Returns Map of routeId -> [speed1, speed2, ...] in mph.
 */
function computeSpeedsBetween(prevSnap, currSnap) {
  const prevMap = new Map();
  for (const v of prevSnap.vehicles) {
    prevMap.set(v.id, v);
  }

  const prevTime = new Date(prevSnap.ts).getTime();
  const currTime = new Date(currSnap.ts).getTime();
  const dtHours = (currTime - prevTime) / 3600000;

  // The collector samples every 30 seconds (in dense bursts inside an hourly
  // workflow, see .github/workflows/bus-tracker-collect.yml). Tight pair window
  // discards consecutive snapshots that crossed an hour boundary or otherwise
  // drifted, keeping speed estimates clean. Anything > 10 minutes apart almost
  // certainly straddles a workflow gap and should not contribute to speed math.
  if (dtHours <= 0 || dtHours > 0.17) return new Map();

  const routeSpeeds = new Map();

  for (const v of currSnap.vehicles) {
    const prev = prevMap.get(v.id);
    if (!prev) continue;
    if (prev.route !== v.route) continue;

    const distMeters = haversine(prev.lat, prev.lon, v.lat, v.lon);
    const speed = (distMeters / 1609.34) / dtHours;

    // Filter unrealistic speeds (GPS glitches, layovers)
    if (speed >= 0.5 && speed < 60) {
      if (!routeSpeeds.has(v.route)) routeSpeeds.set(v.route, []);
      routeSpeeds.get(v.route).push(speed);
    }
  }

  return routeSpeeds;
}

function processDay(date) {
  const snapshots = loadSnapshots(date);
  console.log(`Processing ${date}: ${snapshots.length} snapshots`);

  const routeStats = {};
  let totalBunchingEvents = 0;
  const totalGapRoutes = new Set();

  // Per-route speed accumulators across all snapshot pairs
  const routeSpeedAccum = {}; // route -> [all speeds across the day]

  // Process consecutive snapshot pairs for speed
  for (let s = 1; s < snapshots.length; s++) {
    const speedsByRoute = computeSpeedsBetween(snapshots[s - 1], snapshots[s]);
    for (const [route, speeds] of speedsByRoute) {
      if (!routeSpeedAccum[route]) routeSpeedAccum[route] = [];
      routeSpeedAccum[route].push(...speeds);
    }
  }

  // First pass route average speed (used as the "assumed speed" for gap-time
  // estimation in the second pass). Falls back to DEFAULT_SPEED_MPH per route.
  const routeAvgSpeedHint = {};
  for (const [route, speeds] of Object.entries(routeSpeedAccum)) {
    if (speeds.length > 0) routeAvgSpeedHint[route] = avg(speeds);
  }

  // Hourly system-level accumulators (24 buckets)
  const hourly = {
    snapshots: new Array(24).fill(0),
    busesSum: new Array(24).fill(0),    // bus-count totals → divide by snapshot count later
    bunchPairs: new Array(24).fill(0),
    bigGap20: new Array(24).fill(0),
    bigGap30: new Array(24).fill(0),
    gapSumMin: new Array(24).fill(0),   // sum of gap minutes across all routes/dirs
    gapCount: new Array(24).fill(0),    // number of gap measurements
    gapSumSqMin: new Array(24).fill(0), // sum of gap² (for queuing-formula wait)
  };

  // Per-snapshot active-bus counts (for daily mean/peak/min)
  const activeBusCounts = [];

  // Per-borough accumulators
  const boroughStats = {}; // boro -> { snapshots, busesSum, bunchPairs, gapSumMin, gapCount, gapSumSqMin, routes:Set, speeds:[] }
  function ensureBoro(b) {
    if (!boroughStats[b]) boroughStats[b] = {
      snapshots: 0, busesSum: 0, bunchPairs: 0,
      gapSumMin: 0, gapCount: 0, gapSumSqMin: 0,
      routes: new Set(), speeds: [],
    };
    return boroughStats[b];
  }

  // Process each snapshot for bunching, gaps, wait, hourly, borough
  for (const snap of snapshots) {
    const ts = new Date(snap.ts);
    const hour = ts.getHours();
    hourly.snapshots[hour]++;
    activeBusCounts.push(snap.vehicles.length);
    hourly.busesSum[hour] += snap.vehicles.length;

    // Group vehicles by route + direction
    const groups = {};
    for (const v of snap.vehicles) {
      const key = `${v.route}_${v.dir}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(v);
    }

    // Track which routes had any 20/30+ min gap in THIS snapshot (for big-gap counts)
    const routesWithBigGap20 = new Set();
    const routesWithBigGap30 = new Set();

    for (const [key, buses] of Object.entries(groups)) {
      const [route, dir] = key.split('_');
      const boro = boroughOf(route);
      const bs = ensureBoro(boro);
      bs.snapshots++;
      bs.busesSum += buses.length;
      bs.routes.add(route);

      if (!routeStats[route]) {
        routeStats[route] = {
          route,
          borough: boro,
          totalBuses: 0,
          snapshotCount: 0,
          bunchingEvents: 0,
          bunchingByHour: new Array(24).fill(0),
          gapSnapshots: 0,
          maxBusCount: 0,
          minBusCount: Infinity,
          gapMinutes: [],     // every gap measurement (capped) for this route
          maxGapObserved: 0,  // peak inter-bus gap seen all day
          bigGap20Count: 0,   // snapshots where this route had ≥20-min gap
          bigGap30Count: 0,
        };
      }

      const rs = routeStats[route];
      rs.totalBuses += buses.length;
      rs.snapshotCount++;
      rs.maxBusCount = Math.max(rs.maxBusCount, buses.length);
      rs.minBusCount = Math.min(rs.minBusCount, buses.length);

      // Bunching detection
      for (let i = 0; i < buses.length; i++) {
        for (let j = i + 1; j < buses.length; j++) {
          const dist = haversine(
            buses[i].lat, buses[i].lon,
            buses[j].lat, buses[j].lon
          );
          if (dist < BUNCHING_DISTANCE_M) {
            rs.bunchingEvents++;
            rs.bunchingByHour[hour]++;
            totalBunchingEvents++;
            hourly.bunchPairs[hour]++;
            bs.bunchPairs++;
          }
        }
      }

      // Single-bus snapshot = service gap (legacy field)
      if (buses.length <= 1) {
        rs.gapSnapshots++;
        totalGapRoutes.add(route);
      }

      // ── Inter-bus gap minutes (queuing-formula wait input) ──
      // Mirrors live app's estimateGaps: order along dominant axis, divide
      // straight-line distance by route's observed speed (haversine-based;
      // we don't have route shapes server-side, so this is a known underestimate
      // for winding routes, see methodology). Skip when too few buses to spread.
      if (buses.length >= 3) {
        const isEastWest =
          Math.abs(buses[0].lon - buses[1].lon) >
          Math.abs(buses[0].lat - buses[1].lat);
        const sorted = [...buses].sort((a, b) =>
          isEastWest ? a.lon - b.lon : a.lat - b.lat,
        );
        const speedMph = routeAvgSpeedHint[route] || DEFAULT_SPEED_MPH;
        const speedMps = (speedMph * 1609.34) / 3600;
        let maxGapHere = 0;
        for (let i = 0; i < sorted.length - 1; i++) {
          const dist = haversine(
            sorted[i].lat, sorted[i].lon,
            sorted[i + 1].lat, sorted[i + 1].lon,
          );
          const gapMin = speedMps > 0
            ? Math.min(GAP_CAP_MIN, Math.round((dist / speedMps) / 60))
            : 0;
          rs.gapMinutes.push(gapMin);
          maxGapHere = Math.max(maxGapHere, gapMin);
          rs.maxGapObserved = Math.max(rs.maxGapObserved, gapMin);

          hourly.gapSumMin[hour] += gapMin;
          hourly.gapCount[hour]++;
          hourly.gapSumSqMin[hour] += gapMin * gapMin;

          bs.gapSumMin += gapMin;
          bs.gapCount++;
          bs.gapSumSqMin += gapMin * gapMin;
        }
        // 20+ is inclusive of 30+ (matches live page's "routes with 20+ min waits")
        if (maxGapHere >= BIG_GAP_20) {
          routesWithBigGap20.add(route);
          rs.bigGap20Count++;
        }
        if (maxGapHere >= BIG_GAP_30) {
          routesWithBigGap30.add(route);
          rs.bigGap30Count++;
        }
      }
    }

    hourly.bigGap20[hour] += routesWithBigGap20.size;
    hourly.bigGap30[hour] += routesWithBigGap30.size;
  }

  // Borough route avg speeds (mean of per-route means within each borough)
  for (const [route, hint] of Object.entries(routeAvgSpeedHint)) {
    const b = boroughOf(route);
    if (boroughStats[b]) boroughStats[b].speeds.push(hint);
  }

  // ── Per-route summaries (now include wait/gap stats) ──
  const routeSummaries = Object.values(routeStats).map(rs => {
    const avgBuses = rs.snapshotCount > 0 ? rs.totalBuses / rs.snapshotCount : 0;
    const gapPct = rs.snapshotCount > 0 ? (rs.gapSnapshots / rs.snapshotCount) * 100 : 0;
    const reliability = rs.snapshotCount > 0
      ? ((rs.snapshotCount - rs.gapSnapshots) / rs.snapshotCount) * 100
      : 0;

    const speeds = routeSpeedAccum[rs.route];
    const routeAvgSpeed = speeds && speeds.length > 0 ? round1(avg(speeds)) : null;

    // Wait time: queuing-formula on this route's gap distribution
    let avgWait = null;
    let medianGap = null;
    let p90Gap = null;
    if (rs.gapMinutes.length > 0) {
      const meanGap = avg(rs.gapMinutes);
      const meanGapSq = rs.gapMinutes.reduce((a, b) => a + b * b, 0) / rs.gapMinutes.length;
      avgWait = meanGap > 0 ? round1(meanGapSq / (2 * meanGap)) : null;
      medianGap = percentile(rs.gapMinutes, 50);
      p90Gap = percentile(rs.gapMinutes, 90);
    }

    return {
      route: rs.route,
      borough: rs.borough,
      avgSpeed: routeAvgSpeed,
      avgWait,
      medianGap,
      p90Gap,
      maxGap: rs.maxGapObserved || null,
      avgBuses: round1(avgBuses),
      maxBuses: rs.maxBusCount,
      minBuses: rs.minBusCount === Infinity ? 0 : rs.minBusCount,
      bunchingEvents: rs.bunchingEvents,
      bunchingByHour: rs.bunchingByHour,
      gapSnapshots: rs.gapSnapshots,
      gapPct: round1(gapPct),
      reliability: round1(reliability),
      bigGap20Count: rs.bigGap20Count,
      bigGap30Count: rs.bigGap30Count,
      snapshotCount: rs.snapshotCount,
    };
  });

  // Sort by reliability ascending (worst first)
  routeSummaries.sort((a, b) => a.reliability - b.reliability);

  // System-wide avg speed: unweighted mean of per-route averages
  const routeAvgSpeeds = routeSummaries
    .filter(r => r.avgSpeed != null)
    .map(r => r.avgSpeed);
  const systemAvgSpeed = routeAvgSpeeds.length > 0 ? round1(avg(routeAvgSpeeds)) : null;

  // System-wide wait time: queuing formula across ALL gap observations system-wide
  let systemAvgWait = null;
  let totalGapSum = 0;
  let totalGapSumSq = 0;
  let totalGapCount = 0;
  for (let h = 0; h < 24; h++) {
    totalGapSum += hourly.gapSumMin[h];
    totalGapSumSq += hourly.gapSumSqMin[h];
    totalGapCount += hourly.gapCount[h];
  }
  if (totalGapCount > 0) {
    const meanGap = totalGapSum / totalGapCount;
    const meanGapSq = totalGapSumSq / totalGapCount;
    systemAvgWait = meanGap > 0 ? round1(meanGapSq / (2 * meanGap)) : null;
  }

  // Big-gap counts: average number of routes per snapshot exceeding the threshold
  const totalSnapshots = snapshots.length;
  let bigGap20Sum = 0, bigGap30Sum = 0;
  for (let h = 0; h < 24; h++) {
    bigGap20Sum += hourly.bigGap20[h];
    bigGap30Sum += hourly.bigGap30[h];
  }
  const bigGap20PerSnap = totalSnapshots > 0 ? round1(bigGap20Sum / totalSnapshots) : null;
  const bigGap30PerSnap = totalSnapshots > 0 ? round1(bigGap30Sum / totalSnapshots) : null;

  // Active bus counts across the day
  const activeBusesAvg = activeBusCounts.length > 0 ? round1(avg(activeBusCounts)) : null;
  const activeBusesPeak = activeBusCounts.length > 0 ? Math.max(...activeBusCounts) : null;
  const activeBusesMin = activeBusCounts.length > 0 ? Math.min(...activeBusCounts) : null;

  // Bunching per snapshot (legacy field, unchanged)
  const bunchingRate = totalSnapshots > 0 && routeSummaries.length > 0
    ? round1(totalBunchingEvents / totalSnapshots)
    : null;

  // Hourly system-level rollups (sparse: only hours with at least one snapshot)
  const hourlySystem = {};
  for (let h = 0; h < 24; h++) {
    if (hourly.snapshots[h] === 0) continue;
    const meanGap = hourly.gapCount[h] > 0 ? hourly.gapSumMin[h] / hourly.gapCount[h] : 0;
    const meanGapSq = hourly.gapCount[h] > 0 ? hourly.gapSumSqMin[h] / hourly.gapCount[h] : 0;
    const wait = meanGap > 0 ? round1(meanGapSq / (2 * meanGap)) : null;
    hourlySystem[h] = {
      snapshots: hourly.snapshots[h],
      avgBuses: round1(hourly.busesSum[h] / hourly.snapshots[h]),
      bunchPairsPerSnap: round1(hourly.bunchPairs[h] / hourly.snapshots[h]),
      bigGap20PerSnap: round1(hourly.bigGap20[h] / hourly.snapshots[h]),
      bigGap30PerSnap: round1(hourly.bigGap30[h] / hourly.snapshots[h]),
      avgWait: wait,
    };
  }
  // Per-hour speed (mean of per-route speeds within hour) is non-trivial to bucket
  // because speed is computed across snapshot pairs; we approximate by reusing the
  // pair-level speed sample's source hour. Captured in a separate pass:
  const hourlySpeedAccum = new Array(24).fill(0).map(() => []);
  for (let s = 1; s < snapshots.length; s++) {
    const speedsByRoute = computeSpeedsBetween(snapshots[s - 1], snapshots[s]);
    const h = new Date(snapshots[s].ts).getHours();
    for (const [, speeds] of speedsByRoute) {
      hourlySpeedAccum[h].push(...speeds);
    }
  }
  for (let h = 0; h < 24; h++) {
    if (hourlySystem[h] && hourlySpeedAccum[h].length > 0) {
      hourlySystem[h].avgSpeed = round1(avg(hourlySpeedAccum[h]));
    } else if (hourlySystem[h]) {
      hourlySystem[h].avgSpeed = null;
    }
  }

  // Per-borough rollups
  const byBorough = {};
  for (const [boro, bs] of Object.entries(boroughStats)) {
    if (bs.snapshots === 0) continue;
    const meanGap = bs.gapCount > 0 ? bs.gapSumMin / bs.gapCount : 0;
    const meanGapSq = bs.gapCount > 0 ? bs.gapSumSqMin / bs.gapCount : 0;
    const wait = meanGap > 0 ? round1(meanGapSq / (2 * meanGap)) : null;
    byBorough[boro] = {
      snapshots: bs.snapshots,
      routes: bs.routes.size,
      avgBuses: round1(bs.busesSum / bs.snapshots),
      avgSpeed: bs.speeds.length > 0 ? round1(avg(bs.speeds)) : null,
      bunchPairsPerSnap: round1(bs.bunchPairs / bs.snapshots),
      avgWait: wait,
    };
  }

  const dailySummary = {
    date,
    weekday: new Date(date + 'T12:00:00Z').getUTCDay(), // 0=Sun..6=Sat
    isWeekend: isWeekendDate(date),
    snapshotCount: totalSnapshots,
    totalRoutes: routeSummaries.length,

    // ── Headline system metrics ──
    systemAvgSpeed,
    systemAvgWait,
    bunchingRate,
    totalBunchingEvents,
    bigGap20PerSnap,
    bigGap30PerSnap,
    activeBusesAvg,
    activeBusesPeak,
    activeBusesMin,
    routesWithGaps: totalGapRoutes.size,
    systemReliability: routeSummaries.length > 0
      ? round1(avg(routeSummaries.map(r => r.reliability)))
      : 0,

    // ── Slices ──
    hourly: hourlySystem,    // 0..23 → { snapshots, avgSpeed, avgBuses, bunchPairsPerSnap, avgWait, bigGap20PerSnap, bigGap30PerSnap }
    byBorough,               // 'M'|'B'|'Bx'|'Q'|'S'|'X' → { avgSpeed, avgBuses, avgWait, bunchPairsPerSnap, snapshots, routes }

    // ── Per-route detail (full) ──
    worstRoutes: routeSummaries.slice(0, 20),
    bestRoutes: routeSummaries.slice(-10).reverse(),
    routes: routeSummaries,
  };

  return dailySummary;
}

function main() {
  const date = process.argv[2] || getDate(-1);
  const summary = processDay(date);

  mkdirSync(DAILY_DIR, { recursive: true });
  const outFile = join(DAILY_DIR, `${date}.json`);
  writeFileSync(outFile, JSON.stringify(summary, null, 2));
  console.log(`\nDaily summary written to ${outFile}`);
  console.log(`  Snapshots: ${summary.snapshotCount}`);
  console.log(`  Routes: ${summary.totalRoutes}`);
  console.log(`  System avg speed: ${summary.systemAvgSpeed ?? 'N/A'} mph`);
  console.log(`  System reliability: ${summary.systemReliability}%`);
  console.log(`  Bunching rate: ${summary.bunchingRate ?? 'N/A'} per snapshot`);
  console.log(`  Total bunching events: ${summary.totalBunchingEvents}`);
  console.log(`  Routes with gaps: ${summary.routesWithGaps}`);

  if (summary.worstRoutes.length > 0) {
    console.log('\n  Worst routes by reliability:');
    for (const r of summary.worstRoutes.slice(0, 5)) {
      console.log(`    ${r.route}: ${r.reliability}% reliable, avg ${r.avgSpeed ?? 'N/A'} mph, ${r.bunchingEvents} bunching events`);
    }
  }
}

main();
