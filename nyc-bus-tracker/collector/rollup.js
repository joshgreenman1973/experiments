#!/usr/bin/env node
/**
 * NYC Bus Tracker — Weekly/Monthly Rollup
 * Reads daily JSON summaries and produces:
 * - data/summary/weekly.json  — per-week averages
 * - data/summary/monthly.json — per-month averages
 * - data/summary/latest.json  — most recent daily + trend context (loaded by dashboard)
 *
 * Usage: node rollup.js
 * Reads all files in data/daily/ and regenerates summaries.
 */

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DAILY_DIR = join(__dirname, '..', 'data', 'daily');
const SUMMARY_DIR = join(__dirname, '..', 'data', 'summary');

function round1(n) {
  return Math.round(n * 10) / 10;
}

function avg(arr) {
  return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
}

/** Get ISO week number for a date string "YYYY-MM-DD" */
function isoWeek(dateStr) {
  const d = new Date(dateStr + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

/** Get "YYYY-MM" from "YYYY-MM-DD" */
function yearMonth(dateStr) {
  return dateStr.slice(0, 7);
}

function loadDailySummaries() {
  if (!existsSync(DAILY_DIR)) return [];

  const files = readdirSync(DAILY_DIR)
    .filter(f => f.endsWith('.json'))
    .sort();

  return files.map(f => {
    try {
      return JSON.parse(readFileSync(join(DAILY_DIR, f), 'utf-8'));
    } catch {
      return null;
    }
  }).filter(Boolean);
}

/** Mean of a numeric field across days, ignoring null/undefined values. */
function meanOf(days, field) {
  const nums = days.map(d => d[field]).filter(v => v != null && !Number.isNaN(v));
  return nums.length > 0 ? round1(avg(nums)) : null;
}

// Operating window is 6am–11pm ET = 17 distinct clock-hours collected per day.
// Used to express how complete a period's hourly coverage is.
const OPERATING_HOURS_PER_DAY = 17;

/** Equal-weight mean across the per-hour-of-day values of a metric.
 *  THIS is the apples-to-apples number: it gives every hour of the day equal
 *  say, so a week is NOT skewed by which hours collection happened to capture
 *  (raw snapshot-weighted means over-represent whatever hours got more runs).
 *  `hourly` is the per-hour aggregate built below: { "7": { avgSpeed, ... } }. */
function hourNormMean(hourly, field) {
  const vals = Object.values(hourly)
    .map(h => h[field])
    .filter(v => v != null && !Number.isNaN(v));
  return vals.length > 0 ? round1(avg(vals)) : null;
}

/** Fleet-size-normalized bunching: bunched pairs per 100 active buses,
 *  equal-weighted across hours. Raw "pairs per snapshot" is confounded by how
 *  many buses are running (more buses → mechanically more pairs), so it can't
 *  be compared across weeks with different service levels. Per-100-buses can. */
function hourNormBunchPer100(hourly) {
  const vals = Object.values(hourly)
    .map(h => (h.bunchPairsPerSnap != null && h.avgBuses)
      ? (h.bunchPairsPerSnap / h.avgBuses) * 100 : null)
    .filter(v => v != null && !Number.isNaN(v));
  return vals.length > 0 ? round1(avg(vals)) : null;
}

/** Aggregate an array of daily summaries into a single period summary.
 *  Captures every system-level metric so we can build pre/post-free baselines. */
function aggregatePeriod(days, periodLabel) {
  const totalBunching = days.reduce((s, d) => s + (d.totalBunchingEvents || 0), 0);
  const totalSnapshots = days.reduce((s, d) => s + (d.snapshotCount || 0), 0);

  // Weekday vs weekend split: lets us compare like-with-like across weeks
  const weekdayDays = days.filter(d => !d.isWeekend);
  const weekendDays = days.filter(d => d.isWeekend);

  // Per-borough mean across days
  const allBoroughs = new Set();
  for (const d of days) {
    if (d.byBorough) for (const b of Object.keys(d.byBorough)) allBoroughs.add(b);
  }
  const byBorough = {};
  for (const b of allBoroughs) {
    const bDays = days
      .map(d => d.byBorough?.[b])
      .filter(Boolean);
    if (bDays.length === 0) continue;
    byBorough[b] = {
      daysSeen: bDays.length,
      avgSpeed: meanOf(bDays, 'avgSpeed'),
      avgWait: meanOf(bDays, 'avgWait'),
      avgBuses: meanOf(bDays, 'avgBuses'),
      bunchPairsPerSnap: meanOf(bDays, 'bunchPairsPerSnap'),
    };
  }

  // Per-hour mean across days (only hours present in at least one day)
  const allHours = new Set();
  for (const d of days) {
    if (d.hourly) for (const h of Object.keys(d.hourly)) allHours.add(Number(h));
  }
  const hourly = {};
  for (const h of [...allHours].sort((a, b) => a - b)) {
    const hDays = days.map(d => d.hourly?.[h]).filter(Boolean);
    if (hDays.length === 0) continue;
    hourly[h] = {
      daysSeen: hDays.length,
      avgSpeed: meanOf(hDays, 'avgSpeed'),
      avgWait: meanOf(hDays, 'avgWait'),
      avgBuses: meanOf(hDays, 'avgBuses'),
      bunchPairsPerSnap: meanOf(hDays, 'bunchPairsPerSnap'),
      bigGap20PerSnap: meanOf(hDays, 'bigGap20PerSnap'),
      bigGap30PerSnap: meanOf(hDays, 'bigGap30PerSnap'),
    };
  }

  // ── Coverage: how complete was this period's hourly sampling? ──
  // Sum of per-hour "daysSeen" = total hour-slots actually captured. Expected
  // = operating hours × days. Low coverage means the raw means rest on a
  // partial, possibly skewed slice of the day — flagged so thin periods aren't
  // naively compared to full ones.
  const hourSlotsCaptured = Object.values(hourly)
    .reduce((s, h) => s + (h.daysSeen || 0), 0);
  const expectedSlots = OPERATING_HOURS_PER_DAY * days.length;
  const coveragePct = expectedSlots > 0
    ? Math.round((hourSlotsCaptured / expectedSlots) * 100) : 0;
  // "Comparable" = a full 7-day week with at least half the operating hours
  // represented. Tune the threshold as collection reliability improves.
  const comparable = days.length === 7 && coveragePct >= 50;

  return {
    period: periodLabel,
    days: days.length,
    weekdayDays: weekdayDays.length,
    weekendDays: weekendDays.length,
    startDate: days[0].date,
    endDate: days[days.length - 1].date,
    totalSnapshots,
    totalBunchingEvents: totalBunching,
    avgRoutes: round1(avg(days.map(d => d.totalRoutes || 0))),

    // ── Coverage / comparability ──
    coveragePct,                       // % of operating-hour slots captured
    hoursCaptured: Object.keys(hourly).length,
    comparable,                        // safe to compare week-over-week?

    // ── PRIMARY comparison metrics: time-of-day normalized ──
    // Equal weight per hour-of-day, so two periods are compared on the same
    // daily profile regardless of which hours collection happened to hit.
    // USE THESE for week-over-week / pre-vs-post-free-bus comparisons.
    avgSpeedHourNorm:  hourNormMean(hourly, 'avgSpeed'),
    avgWaitHourNorm:   hourNormMean(hourly, 'avgWait'),
    bunchPer100Buses:  hourNormBunchPer100(hourly),  // fleet-size normalized

    // ── Raw headline metrics (snapshot-weighted mean of daily means) ──
    // Kept for transparency, but NOT apples-to-apples across periods because
    // they over-weight whichever hours got more samples. Prefer the *HourNorm
    // values above for comparisons.
    avgSpeed:           meanOf(days, 'systemAvgSpeed'),
    avgWait:            meanOf(days, 'systemAvgWait'),
    avgReliability:     meanOf(days, 'systemReliability'),
    avgBunchingRate:    meanOf(days, 'bunchingRate'),
    avgBigGap20PerSnap: meanOf(days, 'bigGap20PerSnap'),
    avgBigGap30PerSnap: meanOf(days, 'bigGap30PerSnap'),
    avgActiveBuses:     meanOf(days, 'activeBusesAvg'),
    peakActiveBuses:    days.length > 0
      ? Math.max(0, ...days.map(d => d.activeBusesPeak || 0)) : null,

    // ── Weekday / weekend split (for like-with-like comparisons) ──
    weekday: weekdayDays.length > 0 ? {
      days: weekdayDays.length,
      avgSpeed:           meanOf(weekdayDays, 'systemAvgSpeed'),
      avgWait:            meanOf(weekdayDays, 'systemAvgWait'),
      avgReliability:     meanOf(weekdayDays, 'systemReliability'),
      avgBunchingRate:    meanOf(weekdayDays, 'bunchingRate'),
      avgBigGap20PerSnap: meanOf(weekdayDays, 'bigGap20PerSnap'),
      avgActiveBuses:     meanOf(weekdayDays, 'activeBusesAvg'),
    } : null,
    weekend: weekendDays.length > 0 ? {
      days: weekendDays.length,
      avgSpeed:           meanOf(weekendDays, 'systemAvgSpeed'),
      avgWait:            meanOf(weekendDays, 'systemAvgWait'),
      avgReliability:     meanOf(weekendDays, 'systemReliability'),
      avgBunchingRate:    meanOf(weekendDays, 'bunchingRate'),
      avgBigGap20PerSnap: meanOf(weekendDays, 'bigGap20PerSnap'),
      avgActiveBuses:     meanOf(weekendDays, 'activeBusesAvg'),
    } : null,

    byBorough,
    hourly,
  };
}

/** Build a per-route history map: route -> [{ period, days, avgSpeed, avgWait, ... }] */
function aggregateRoutesByPeriod(periodGroups) {
  // periodGroups: { 'YYYY-Wxx' or 'YYYY-MM': [day, day, ...] }
  // Returns { route: [ { period, ... }, ... ] }
  const routes = {};
  for (const [periodLabel, days] of Object.entries(periodGroups)) {
    const accum = {};
    for (const d of days) {
      if (!d.routes) continue;
      for (const r of d.routes) {
        if (!accum[r.route]) accum[r.route] = {
          route: r.route,
          borough: r.borough || null,
          dailySpeed: [],
          dailyWait: [],
          dailyReliability: [],
          dailyBunching: [],
          dailyBuses: [],
          totalBunchingEvents: 0,
          bigGap20Count: 0,
          bigGap30Count: 0,
          daysSeen: 0,
        };
        const a = accum[r.route];
        if (r.avgSpeed != null) a.dailySpeed.push(r.avgSpeed);
        if (r.avgWait != null) a.dailyWait.push(r.avgWait);
        if (r.reliability != null) a.dailyReliability.push(r.reliability);
        if (r.bunchingEvents != null) a.dailyBunching.push(r.bunchingEvents);
        if (r.avgBuses != null) a.dailyBuses.push(r.avgBuses);
        a.totalBunchingEvents += r.bunchingEvents || 0;
        a.bigGap20Count += r.bigGap20Count || 0;
        a.bigGap30Count += r.bigGap30Count || 0;
        a.daysSeen++;
      }
    }
    for (const [route, a] of Object.entries(accum)) {
      const row = {
        period: periodLabel,
        daysSeen: a.daysSeen,
        borough: a.borough,
        avgSpeed: a.dailySpeed.length > 0 ? round1(avg(a.dailySpeed)) : null,
        avgWait: a.dailyWait.length > 0 ? round1(avg(a.dailyWait)) : null,
        avgReliability: a.dailyReliability.length > 0 ? round1(avg(a.dailyReliability)) : null,
        avgBunchingPerDay: a.dailyBunching.length > 0 ? round1(avg(a.dailyBunching)) : null,
        avgBuses: a.dailyBuses.length > 0 ? round1(avg(a.dailyBuses)) : null,
        totalBunchingEvents: a.totalBunchingEvents,
        bigGap20Count: a.bigGap20Count,
        bigGap30Count: a.bigGap30Count,
      };
      if (!routes[route]) routes[route] = [];
      routes[route].push(row);
    }
  }
  // Sort each route's history chronologically
  for (const route of Object.keys(routes)) {
    routes[route].sort((a, b) => a.period.localeCompare(b.period));
  }
  return routes;
}

function main() {
  const dailies = loadDailySummaries();
  if (dailies.length === 0) {
    console.log('No daily summaries found. Run process.js first.');
    return;
  }

  console.log(`Rolling up ${dailies.length} daily summaries`);

  // Group by ISO week
  const weekGroups = {};
  for (const d of dailies) {
    const wk = isoWeek(d.date);
    if (!weekGroups[wk]) weekGroups[wk] = [];
    weekGroups[wk].push(d);
  }

  const weekly = Object.entries(weekGroups)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([wk, days]) => aggregatePeriod(days, wk));

  // Group by month
  const monthGroups = {};
  for (const d of dailies) {
    const mo = yearMonth(d.date);
    if (!monthGroups[mo]) monthGroups[mo] = [];
    monthGroups[mo].push(d);
  }

  const monthly = Object.entries(monthGroups)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([mo, days]) => aggregatePeriod(days, mo));

  // Per-route history (so we can baseline individual routes pre/post free-bus)
  const weeklyRoutes = aggregateRoutesByPeriod(weekGroups);
  const monthlyRoutes = aggregateRoutesByPeriod(monthGroups);

  // Latest: most recent daily + trend context
  const latest = dailies[dailies.length - 1];
  const latestSummary = {
    current: {
      date: latest.date,
      avgSpeed: latest.systemAvgSpeed,
      avgWait: latest.systemAvgWait,
      reliability: latest.systemReliability,
      bunchingRate: latest.bunchingRate,
      bigGap20PerSnap: latest.bigGap20PerSnap,
      bigGap30PerSnap: latest.bigGap30PerSnap,
      activeBusesAvg: latest.activeBusesAvg,
      activeBusesPeak: latest.activeBusesPeak,
      totalRoutes: latest.totalRoutes,
      snapshotCount: latest.snapshotCount,
    },
    thisWeek: weekly.length > 0 ? weekly[weekly.length - 1] : null,
    lastWeek: weekly.length > 1 ? weekly[weekly.length - 2] : null,
    thisMonth: monthly.length > 0 ? monthly[monthly.length - 1] : null,
    lastMonth: monthly.length > 1 ? monthly[monthly.length - 2] : null,
    weeklyHistory: weekly.slice(-12),  // last 12 weeks
    monthlyHistory: monthly.slice(-12), // last 12 months
  };

  // Write outputs
  mkdirSync(SUMMARY_DIR, { recursive: true });

  writeFileSync(join(SUMMARY_DIR, 'weekly.json'), JSON.stringify(weekly, null, 2));
  writeFileSync(join(SUMMARY_DIR, 'monthly.json'), JSON.stringify(monthly, null, 2));
  writeFileSync(join(SUMMARY_DIR, 'latest.json'), JSON.stringify(latestSummary, null, 2));
  writeFileSync(join(SUMMARY_DIR, 'weekly-routes.json'), JSON.stringify(weeklyRoutes, null, 2));
  writeFileSync(join(SUMMARY_DIR, 'monthly-routes.json'), JSON.stringify(monthlyRoutes, null, 2));

  console.log(`\nWeekly summaries: ${weekly.length} weeks`);
  console.log(`Monthly summaries: ${monthly.length} months`);
  console.log(`Per-route weekly histories: ${Object.keys(weeklyRoutes).length} routes`);
  console.log(`Latest summary written for ${latest.date}`);

  if (weekly.length > 0) {
    const curr = weekly[weekly.length - 1];
    console.log(`\nCurrent week (${curr.period}):`);
    console.log(`  Avg speed: ${curr.avgSpeed ?? 'N/A'} mph`);
    console.log(`  Reliability: ${curr.avgReliability ?? 'N/A'}%`);
    console.log(`  Bunching rate: ${curr.avgBunchingRate ?? 'N/A'}/snapshot`);
  }
}

main();
