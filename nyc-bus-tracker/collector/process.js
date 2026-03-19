#!/usr/bin/env node
/**
 * NYC Bus Tracker — Daily Processor
 * Reads a day's JSONL snapshots and computes:
 * - Per-route headways (time between consecutive buses)
 * - Bunching events (buses within 250m on same route/direction)
 * - Gap events (long intervals without buses)
 * - Route reliability scores
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
const GAP_THRESHOLD_MIN = 20;

function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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

function processDay(date) {
  const snapshots = loadSnapshots(date);
  console.log(`Processing ${date}: ${snapshots.length} snapshots`);

  const routeStats = {};
  let totalBunchingEvents = 0;
  let totalGapRoutes = new Set();

  // Process each snapshot
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
      const dir = parseInt(key.split('_')[1], 10);

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
          directions: {},
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

  // Compute summary stats
  const routeSummaries = Object.values(routeStats).map(rs => {
    const avgBuses = rs.snapshotCount > 0 ? rs.totalBuses / rs.snapshotCount : 0;
    const gapPct = rs.snapshotCount > 0 ? (rs.gapSnapshots / rs.snapshotCount) * 100 : 0;
    // Reliability: % of snapshots with more than 1 bus (not in gap state)
    const reliability = rs.snapshotCount > 0
      ? ((rs.snapshotCount - rs.gapSnapshots) / rs.snapshotCount) * 100
      : 0;

    return {
      route: rs.route,
      avgBuses: Math.round(avgBuses * 10) / 10,
      maxBuses: rs.maxBusCount,
      minBuses: rs.minBusCount === Infinity ? 0 : rs.minBusCount,
      bunchingEvents: rs.bunchingEvents,
      bunchingByHour: rs.bunchingByHour,
      gapSnapshots: rs.gapSnapshots,
      gapPct: Math.round(gapPct * 10) / 10,
      reliability: Math.round(reliability * 10) / 10,
      snapshotCount: rs.snapshotCount,
    };
  });

  // Sort by reliability ascending (worst first)
  routeSummaries.sort((a, b) => a.reliability - b.reliability);

  const dailySummary = {
    date,
    snapshotCount: snapshots.length,
    totalRoutes: routeSummaries.length,
    totalBunchingEvents,
    routesWithGaps: totalGapRoutes.size,
    systemReliability: routeSummaries.length > 0
      ? Math.round(
          routeSummaries.reduce((s, r) => s + r.reliability, 0) / routeSummaries.length * 10
        ) / 10
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
  console.log(`  System reliability: ${summary.systemReliability}%`);
  console.log(`  Total bunching events: ${summary.totalBunchingEvents}`);
  console.log(`  Routes with gaps: ${summary.routesWithGaps}`);

  if (summary.worstRoutes.length > 0) {
    console.log('\n  Worst routes by reliability:');
    for (const r of summary.worstRoutes.slice(0, 5)) {
      console.log(`    ${r.route}: ${r.reliability}% reliable, ${r.bunchingEvents} bunching events`);
    }
  }
}

main();
