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

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SNAPSHOTS_DIR = join(__dirname, '..', 'data', 'snapshots');
const DAILY_DIR = join(__dirname, '..', 'data', 'daily');

const BUNCHING_DISTANCE_M = 250;

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

function loadSnapshots(date) {
  const file = join(SNAPSHOTS_DIR, `${date}.jsonl`);
  if (!existsSync(file)) {
    console.error(`No data file for ${date}`);
    process.exit(1);
  }

  const lines = readFileSync(file, 'utf-8').trim().split('\n');
  return lines.map(line => {
    try { return JSON.parse(line); }
    catch { return null; }
  }).filter(Boolean);
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

  // Skip if bad interval (negative, zero, or >30 min gap)
  if (dtHours <= 0 || dtHours > 0.5) return new Map();

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

  // Accumulate per-route speeds across all snapshot pairs
  const routeSpeedAccum = {}; // route -> [all speeds across the day]

  // Process consecutive snapshot pairs for speed
  for (let s = 1; s < snapshots.length; s++) {
    const speedsByRoute = computeSpeedsBetween(snapshots[s - 1], snapshots[s]);
    for (const [route, speeds] of speedsByRoute) {
      if (!routeSpeedAccum[route]) routeSpeedAccum[route] = [];
      routeSpeedAccum[route].push(...speeds);
    }
  }

  // Process each snapshot for bunching and gaps
  for (const snap of snapshots) {
    const ts = new Date(snap.ts);
    const hour = ts.getHours();

    // Group vehicles by route + direction
    const groups = {};
    for (const v of snap.vehicles) {
      const key = `${v.route}_${v.dir}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(v);
    }

    for (const [key, buses] of Object.entries(groups)) {
      const route = key.split('_')[0];

      if (!routeStats[route]) {
        routeStats[route] = {
          route,
          totalBuses: 0,
          snapshotCount: 0,
          bunchingEvents: 0,
          bunchingByHour: new Array(24).fill(0),
          gapSnapshots: 0,
          maxBusCount: 0,
          minBusCount: Infinity,
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
          }
        }
      }

      // Gap detection (single bus = potential service gap)
      if (buses.length <= 1) {
        rs.gapSnapshots++;
        totalGapRoutes.add(route);
      }
    }
  }

  // Compute per-route summaries including speed
  const routeSummaries = Object.values(routeStats).map(rs => {
    const avgBuses = rs.snapshotCount > 0 ? rs.totalBuses / rs.snapshotCount : 0;
    const gapPct = rs.snapshotCount > 0 ? (rs.gapSnapshots / rs.snapshotCount) * 100 : 0;
    const reliability = rs.snapshotCount > 0
      ? ((rs.snapshotCount - rs.gapSnapshots) / rs.snapshotCount) * 100
      : 0;

    // Per-route average speed
    const speeds = routeSpeedAccum[rs.route];
    const routeAvgSpeed = speeds && speeds.length > 0 ? round1(avg(speeds)) : null;

    return {
      route: rs.route,
      avgSpeed: routeAvgSpeed,
      avgBuses: round1(avgBuses),
      maxBuses: rs.maxBusCount,
      minBuses: rs.minBusCount === Infinity ? 0 : rs.minBusCount,
      bunchingEvents: rs.bunchingEvents,
      bunchingByHour: rs.bunchingByHour,
      gapSnapshots: rs.gapSnapshots,
      gapPct: round1(gapPct),
      reliability: round1(reliability),
      snapshotCount: rs.snapshotCount,
    };
  });

  // Sort by reliability ascending (worst first)
  routeSummaries.sort((a, b) => a.reliability - b.reliability);

  // System-wide average speed: mean of per-route averages (each route weighted equally)
  const routeAvgSpeeds = routeSummaries
    .filter(r => r.avgSpeed != null)
    .map(r => r.avgSpeed);
  const systemAvgSpeed = routeAvgSpeeds.length > 0 ? round1(avg(routeAvgSpeeds)) : null;

  // System-wide bunching rate: bunching events per snapshot per route
  const totalSnapshots = snapshots.length;
  const bunchingRate = totalSnapshots > 0 && routeSummaries.length > 0
    ? round1(totalBunchingEvents / totalSnapshots)
    : null;

  const dailySummary = {
    date,
    snapshotCount: snapshots.length,
    totalRoutes: routeSummaries.length,
    systemAvgSpeed,
    bunchingRate,
    totalBunchingEvents,
    routesWithGaps: totalGapRoutes.size,
    systemReliability: routeSummaries.length > 0
      ? round1(avg(routeSummaries.map(r => r.reliability)))
      : 0,
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
