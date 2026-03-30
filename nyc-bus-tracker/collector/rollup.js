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

/** Aggregate an array of daily summaries into a single period summary */
function aggregatePeriod(days, periodLabel) {
  const speeds = days.filter(d => d.systemAvgSpeed != null).map(d => d.systemAvgSpeed);
  const reliabilities = days.filter(d => d.systemReliability != null).map(d => d.systemReliability);
  const bunchingRates = days.filter(d => d.bunchingRate != null).map(d => d.bunchingRate);
  const totalBunching = days.reduce((s, d) => s + (d.totalBunchingEvents || 0), 0);
  const totalSnapshots = days.reduce((s, d) => s + (d.snapshotCount || 0), 0);

  return {
    period: periodLabel,
    days: days.length,
    startDate: days[0].date,
    endDate: days[days.length - 1].date,
    avgSpeed: speeds.length > 0 ? round1(avg(speeds)) : null,
    avgReliability: reliabilities.length > 0 ? round1(avg(reliabilities)) : null,
    avgBunchingRate: bunchingRates.length > 0 ? round1(avg(bunchingRates)) : null,
    totalBunchingEvents: totalBunching,
    totalSnapshots,
    avgRoutes: round1(avg(days.map(d => d.totalRoutes || 0))),
  };
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

  // Latest: most recent daily + trend context
  const latest = dailies[dailies.length - 1];
  const latestSummary = {
    current: {
      date: latest.date,
      avgSpeed: latest.systemAvgSpeed,
      reliability: latest.systemReliability,
      bunchingRate: latest.bunchingRate,
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

  console.log(`\nWeekly summaries: ${weekly.length} weeks`);
  console.log(`Monthly summaries: ${monthly.length} months`);
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
