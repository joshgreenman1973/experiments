#!/usr/bin/env node
/**
 * NYC Bus Tracker — rollups, method version 2 (October 2026).
 *
 * Reads every data/daily/*.json (written by process.js) and builds the series
 * the pages and downloads use. All weighting rules live here:
 *
 *   Route-hour values. For one route in one Eastern clock hour of one day:
 *   moving speed (mean of readings at 0.5 mph or more, needs 3 readings),
 *   speed with stops (distance / time, needs 2 minutes of readings), stopped
 *   share, buses in service, passengers per bus, scheduled trips in progress.
 *
 *   System hour values. Local, limited and Select Bus Service routes only,
 *   each route counting once (route-equal). Express routes and temporary
 *   shuttles are left out of the speed index; buses in service count every
 *   bus not on layover.
 *
 *   Periods (ISO weeks, calendar months). Weekdays and weekends are kept
 *   apart. For each day type and each of the 17 window hours (6 a.m. to
 *   10:59 p.m. Eastern) a cell is the mean of that hour over the period's days
 *   of that type on which the hour was collected. A day type is "complete"
 *   only when all 17 cells rest on enough days (weeks: 3 weekdays, 1 weekend
 *   day; months: 8 weekdays, 3 weekend days). The period value is the plain
 *   mean of the 17 cells, so every hour counts equally and the hours the
 *   collector happened to catch don't move the number. The all-days index is
 *   5/7 weekday + 2/7 weekend. A week is comparable when it has 7 days and
 *   both day types are complete.
 *
 *   Holidays and service cuts. Major holidays, and any weekday whose midday
 *   route count falls below 85% of nearby weekdays, are typed "holiday" and
 *   left out of both series.
 *
 * Outputs (data/summary/): days.json, weekly.json, monthly.json,
 * weekly-routes.json, monthly-routes.json, latest.json, health.json; and one
 * file per route in data/route-history/.
 *
 * Fails loud when daily files from method version 1 remain (run the backfill
 * workflow), so the series is never a mix of methods.
 */
import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync, rmSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { routeKind, routeGroup, isoWeek, WINDOW_HOURS, BANDS, etParts } from './routes.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const DAILY_DIR = join(ROOT, 'data', 'daily');
const SUMMARY_DIR = join(ROOT, 'data', 'summary');
const HISTORY_DIR = join(ROOT, 'data', 'route-history');

export const METHOD_VERSION = 2;
const MIN_HOUR_SNAPS = 4;          // four snapshots (three readings per bus) make an hour "collected"
const MAX_FILLED_HOURS = 2;        // a day type may miss at most two of its 17 hours
const MIN_MOV_READINGS = 3;
const MIN_ROUTE_TIME_S = 120;
const MPS_TO_MPH = 2.2369363;
const REDUCED_SERVICE_RATIO = 0.85;
const HEALTH_MIN_HOURS = 12;       // the last full day with fewer collected hours trips the alert
const MIN_CELL_DAYS = { week: { weekday: 3, weekend: 1 }, month: { weekday: 8, weekend: 3 } };
const MIDDAY = [10, 11, 12, 13, 14, 15];

const mean = a => { const v = a.filter(x => x != null && Number.isFinite(x)); return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null; };
const rd = (x, n = 2) => (x == null ? null : Math.round(x * 10 ** n) / 10 ** n);
const isPanel = k => k === 'local' || k === 'sbs' || k === 'limited';
const isRegular = k => isPanel(k) || k === 'express';
export const routeSlug = id => id.replace(/\+/g, 'plus');
const AP = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
const apDate = d => `${AP[Number(d.slice(5, 7)) - 1]} ${Number(d.slice(8))}`;

// ── load ────────────────────────────────────────────────────────────────────
function loadDailies() {
  if (!existsSync(DAILY_DIR)) return { days: [], stale: [] };
  const days = [], stale = [];
  for (const f of readdirSync(DAILY_DIR).filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort()) {
    const d = JSON.parse(readFileSync(join(DAILY_DIR, f), 'utf8'));
    if (d.methodVersion === METHOD_VERSION) days.push(d); else stale.push(d.date || f);
  }
  return { days, stale };
}

// ── one day → hour cells ────────────────────────────────────────────────────
function deriveDay(day) {
  const F = Object.fromEntries(day.fields.map((k, i) => [k, i]));
  const covered = WINDOW_HOURS.filter(h => (day.hours[h]?.snaps || 0) >= MIN_HOUR_SNAPS);
  const routes = {};
  const sys = {};
  for (const h of covered) sys[h] = { mov: [], all: [], stop: [], rMov: [], rAll: [], buses: 0, busesReg: 0, sched: 0, hasSched: false, running: 0 };

  for (const [route, r] of Object.entries(day.routes)) {
    const kind = routeKind(route === "(blank)" ? "" : route);
    const out = {};
    for (const h of covered) {
      const c = r.h[h];
      const snaps = day.hours[h].snaps;
      const sched = Array.isArray(r.sched) ? r.sched[h] : null;
      if (sched != null && isRegular(kind)) { sys[h].sched += sched; sys[h].hasSched = true; }
      if (!c) { if (sched) out[h] = { buses: 0, sched }; continue; }
      const mov = c[F.nMov] >= MIN_MOV_READINGS ? c[F.sumMov] / c[F.nMov] : null;
      const all = c[F.time] >= MIN_ROUTE_TIME_S ? (c[F.dist] / c[F.time]) * MPS_TO_MPH : null;
      const stop = c[F.time] >= MIN_ROUTE_TIME_S ? c[F.stopTime] / c[F.time] : null;
      const buses = c[F.inSvc] / snaps;
      const pax = c[F.nPax] > 0 ? c[F.sumPax] / c[F.nPax] : null;
      out[h] = { mov, all, stop, buses, pax, sched };
      const s = sys[h];
      s.buses += buses;
      if (isRegular(kind)) { s.busesReg += buses; if (c[F.inSvc] > 0) s.running++; }
      if (isPanel(kind)) {
        if (mov != null) s.mov.push(mov);
        if (all != null) { s.all.push(all); s.stop.push(stop); }
      }
      if (isRegular(kind)) {
        if (mov != null) s.rMov.push(mov);
        if (all != null) s.rAll.push(all);
      }
    }
    if (Object.keys(out).length) routes[route] = { kind, group: r.group ?? routeGroup(route), h: out };
  }

  const hours = {};
  for (const h of covered) {
    const s = sys[h];
    hours[h] = {
      mov: mean(s.mov), all: mean(s.all), stop: mean(s.stop),
      mtaMov: mean(s.rMov), mtaAll: mean(s.rAll),
      buses: s.buses, busesReg: s.busesReg,
      sched: s.hasSched ? s.sched : null,
      running: s.running,
    };
  }
  const middayRoutes = new Set();
  for (const [route, r] of Object.entries(routes)) {
    if (!isRegular(r.kind)) continue;
    if (MIDDAY.some(h => r.h[h]?.buses > 0)) middayRoutes.add(route);
  }
  return {
    date: day.date, weekday: day.weekday, holiday: day.holiday || null,
    snapshots: day.snapshots, covered, hours, routes,
    middayCovered: MIDDAY.filter(h => covered.includes(h)).length,
    middayRoutes: middayRoutes.size,
    schedulePattern: day.schedulePattern ?? null,
  };
}

// ── day types ───────────────────────────────────────────────────────────────
function assignDayTypes(days) {
  const t = d => Date.parse(d.date + 'T00:00:00Z');
  for (const d of days) {
    if (d.weekday === 0 || d.weekday === 6) { d.dayType = 'weekend'; continue; }
    d.dayType = 'weekday';
    if (d.holiday?.type === 'major') { d.dayType = 'holiday'; d.typeReason = d.holiday.name; continue; }
    if (d.middayCovered < 3) continue;
    const peers = days.filter(o => o !== d && o.weekday >= 1 && o.weekday <= 5 && o.holiday?.type !== 'major'
      && o.middayCovered >= 3 && Math.abs(t(o) - t(d)) <= 14 * 86400000).map(o => o.middayRoutes).sort((a, b) => a - b);
    if (peers.length >= 3) {
      const med = peers[Math.floor(peers.length / 2)];
      if (d.middayRoutes < REDUCED_SERVICE_RATIO * med) {
        d.dayType = 'holiday';
        d.typeReason = `${d.holiday ? d.holiday.name + ': ' : ''}${d.middayRoutes} routes ran at midday against ${med} on nearby weekdays`;
      }
    }
  }
}

// ── period aggregation ──────────────────────────────────────────────────────
const TYPES = ['weekday', 'weekend'];
const SHORT = { weekday: 'wd', weekend: 'we' };
const SYS_KEYS = ['mov', 'all', 'stop', 'mtaMov', 'mtaAll', 'buses', 'busesReg', 'sched'];
const ROUTE_KEYS = ['mov', 'all', 'stop', 'buses', 'sched'];

function systemCells(days, type) {
  const cells = {};
  for (const h of WINDOW_HOURS) {
    const ds = days.filter(d => d.dayType === type && d.hours[h]);
    const pick = k => mean(ds.map(d => d.hours[h][k]));
    const sched = ds.some(d => d.hours[h].sched != null) ? mean(ds.map(d => d.hours[h].sched)) : null;
    cells[h] = {
      n: ds.length, mov: pick('mov'), all: pick('all'), stop: pick('stop'),
      mtaMov: pick('mtaMov'), mtaAll: pick('mtaAll'),
      buses: pick('buses'), busesReg: pick('busesReg'), sched,
    };
  }
  return cells;
}

/** The usual level of each hour: mean over periods whose cell for that hour
 *  rests on enough days. Used only to fill a missed hour (see fillMean). */
function buildRef(cellSets, okCell, keys) {
  const ref = {};
  for (const h of WINDOW_HOURS) {
    ref[h] = {};
    for (const k of keys) {
      const v = cellSets.map(c => (c && okCell(c[h]) ? c[h][k] : null));
      ref[h][k] = mean(v);
    }
  }
  return ref;
}

/** Mean over a fixed set of hours when some were missed. Each missed hour is
 *  taken to have moved like the period's other hours relative to their usual
 *  levels: mean(usual levels) + mean(this period's deviation from them over
 *  the hours it has). With every hour present this is exactly the plain mean. */
function fillMean(hours, valid, cell, ref, k) {
  const hs = hours.filter(h => ref?.[h]?.[k] != null);
  const dev = valid.filter(h => ref?.[h]?.[k] != null && cell(h)?.[k] != null).map(h => cell(h)[k] - ref[h][k]);
  if (hs.length && dev.length) return mean(hs.map(h => ref[h][k])) + mean(dev);
  const plain = valid.map(h => cell(h)?.[k]).filter(v => v != null);
  return plain.length && valid.length === hours.length ? mean(plain) : null;
}

function summarizeCells(cells, minDays, withBands, ref) {
  const valid = WINDOW_HOURS.filter(h => cells[h].n >= minDays);
  const missing = WINDOW_HOURS.filter(h => cells[h].n < minDays);
  const complete = valid.length > 0 && missing.length <= MAX_FILLED_HOURS;
  const est = (k, n = 2) => (complete ? rd(fillMean(WINDOW_HOURS, valid, h => cells[h], ref, k), n) : null);
  const seen = WINDOW_HOURS.filter(h => cells[h].n > 0);
  const avgOver = (hs, k) => mean(hs.map(h => cells[h][k]));
  const out = {
    complete, missingHours: missing, filledHours: complete ? missing : [],
    days: Math.max(0, ...WINDOW_HOURS.map(h => cells[h].n)),
    mov: est('mov'), all: est('all'), stop: est('stop', 4),
    buses: est('buses', 1), busesReg: est('busesReg', 1),
    sched: valid.some(h => cells[h].sched != null) ? est('sched', 1) : null,
    mtaMov: est('mtaMov'), mtaAll: est('mtaAll'),
    // Over whatever hours were collected; for looking, never for comparing.
    partial: { hours: seen.length, mov: rd(avgOver(seen, 'mov')), all: rd(avgOver(seen, 'all')) },
  };
  if (out.sched) out.delivered = rd(out.busesReg / out.sched, 3);
  if (withBands) {
    out.bands = {};
    for (const [b, hs] of Object.entries(BANDS)) {
      const ok = hs.every(h => cells[h].n >= minDays);
      out.bands[b] = ok ? { mov: rd(avgOver(hs, 'mov')), all: rd(avgOver(hs, 'all')), stop: rd(avgOver(hs, 'stop'), 4), buses: rd(avgOver(hs, 'buses'), 1) } : null;
    }
  }
  return out;
}

function blend(wd, we, k) {
  return wd?.[k] != null && we?.[k] != null ? rd((5 * wd[k] + 2 * we[k]) / 7, k === 'stop' ? 4 : 2) : null;
}

function aggregatePeriod(days, label, unit, periodDays, cells, ref) {
  const min = MIN_CELL_DAYS[unit];
  const wd = summarizeCells(cells.weekday, min.weekday, true, ref.weekday);
  const we = summarizeCells(cells.weekend, min.weekend, false, ref.weekend);
  const collected = days.reduce((s, d) => s + d.covered.length, 0);
  const lastDate = days[days.length - 1].date;
  const ended = unit === 'week' ? days.length === 7 || lastDate >= periodDays.end : lastDate >= periodDays.end;
  const comparable = (unit === 'week' ? days.length === 7 : ended) && wd.complete && we.complete;
  const hourly = {};
  for (const type of TYPES) {
    hourly[SHORT[type]] = Object.fromEntries(WINDOW_HOURS.map(h => {
      const c = cells[type][h];
      return [h, { n: c.n, mov: rd(c.mov), all: rd(c.all), stop: rd(c.stop, 4), buses: rd(c.buses, 1), sched: rd(c.sched, 1) }];
    }));
  }
  return {
    period: label,
    startDate: days[0].date,
    endDate: lastDate,
    days: days.length,
    dayTypes: { weekday: days.filter(d => d.dayType === 'weekday').length, weekend: days.filter(d => d.dayType === 'weekend').length, holiday: days.filter(d => d.dayType === 'holiday').length },
    holidays: days.filter(d => d.dayType === 'holiday').map(d => ({ date: d.date, reason: d.typeReason || d.holiday?.name || '' })),
    coveragePct: Math.round((100 * collected) / (17 * days.length)),
    ended,
    comparable,
    idx: { mov: blend(wd, we, 'mov'), all: blend(wd, we, 'all'), stop: blend(wd, we, 'stop'), buses: blend(wd, we, 'buses') },
    mta: { mov: blend(wd, we, 'mtaMov'), all: blend(wd, we, 'mtaAll') },
    wd, we,
    snapshots: days.reduce((s, d) => s + d.snapshots, 0),
    hourly,
  };
}

// ── routes by period ────────────────────────────────────────────────────────
function routeCells(days, route, type) {
  const cells = {};
  for (const h of WINDOW_HOURS) {
    const ds = days.filter(d => d.dayType === type && d.hours[h]);
    const vals = ds.map(d => d.routes[route]?.h[h]).filter(Boolean);
    cells[h] = {
      cov: ds.length,                       // days of this type the system caught this hour
      n: vals.filter(v => v.buses > 0).length,
      mov: mean(vals.map(v => v.mov)), all: mean(vals.map(v => v.all)), stop: mean(vals.map(v => v.stop)),
      pax: mean(vals.map(v => v.pax)),
      // Absent from an hour the collector caught = no bus on the road then.
      buses: ds.length ? ds.reduce((s, d) => s + (d.routes[route]?.h[h]?.buses || 0), 0) / ds.length : null,
      sched: mean(vals.map(v => v.sched)),
    };
  }
  return cells;
}

function routeSummary(cells, withBands, ref) {
  // The hours this route normally runs, from its own history.
  const usual = WINDOW_HOURS.filter(h => ref?.[h]?.all != null || ref?.[h]?.mov != null || cells[h].n > 0);
  const ran = usual.filter(h => cells[h].n > 0);
  if (!ran.length) return null;
  const caught = WINDOW_HOURS.filter(h => cells[h].cov > 0);
  const avg = (hs, k) => mean(hs.map(h => cells[h][k]));
  const o = {
    hours: ran.length,
    mov: rd(fillMean(usual, ran, h => cells[h], ref, 'mov')),
    all: rd(fillMean(usual, ran, h => cells[h], ref, 'all')),
    stop: rd(fillMean(usual, ran, h => cells[h], ref, 'stop'), 4),
    pax: rd(avg(ran, 'pax'), 1),
    buses: rd(fillMean(WINDOW_HOURS, caught, h => cells[h], ref, 'buses'), 2),
    sched: ran.some(h => cells[h].sched != null) ? rd(fillMean(WINDOW_HOURS, caught, h => ({ sched: cells[h].sched ?? 0 }), ref, 'sched'), 2) : null,
  };
  if (withBands) {
    for (const [b, hs] of Object.entries(BANDS)) {
      const want = hs.filter(h => usual.includes(h));
      const ok = want.length && want.every(h => cells[h].n > 0);
      o[b] = ok ? { mov: rd(avg(want, 'mov')), all: rd(avg(want, 'all')) } : null;
    }
  }
  return o;
}

/** Route rows per period. Cells are computed once; with no `refs` given, each
 *  route's usual hour levels are built from these periods (weeks) and returned
 *  for reuse with months. */
function routePeriods(groups, unit, systemByPeriod, allRoutes, refs = null) {
  const min = MIN_CELL_DAYS[unit];
  const cellsBy = {};   // route -> label -> { weekday, weekend, wdN, weN }
  for (const [label, days] of Object.entries(groups)) {
    const present = new Set(days.flatMap(d => Object.keys(d.routes)));
    for (const route of present) {
      const daysOf = type => days.filter(d => d.dayType === type && d.routes[route] && Object.values(d.routes[route].h).some(v => v.buses > 0)).length;
      const wdN = daysOf('weekday'), weN = daysOf('weekend');
      ((cellsBy[route] ||= {})[label] = {
        wdN, weN,
        weekday: wdN ? routeCells(days, route, 'weekday') : null,
        weekend: weN ? routeCells(days, route, 'weekend') : null,
      });
    }
  }
  if (!refs) {
    refs = {};
    for (const [route, byLabel] of Object.entries(cellsBy)) {
      refs[route] = {};
      for (const type of TYPES) {
        refs[route][type] = buildRef(Object.values(byLabel).map(x => x[type]), c => c && c.n > 0, ROUTE_KEYS);
        // buses and sched are defined for any hour the collector caught
        for (const h of WINDOW_HOURS) {
          for (const k of ['buses', 'sched']) {
            refs[route][type][h][k] = mean(Object.values(byLabel).map(x => (x[type] && x[type][h].cov > 0 ? (k === 'sched' ? x[type][h].sched ?? 0 : x[type][h].buses) : null)));
          }
        }
      }
    }
  }
  const out = {};
  for (const route of allRoutes) out[route] = [];
  for (const [route, byLabel] of Object.entries(cellsBy)) {
    for (const [label, x] of Object.entries(byLabel)) {
      const sys = systemByPeriod[label];
      const wd = x.weekday ? routeSummary(x.weekday, true, refs[route]?.weekday) : null;
      const we = x.weekend ? routeSummary(x.weekend, false, refs[route]?.weekend) : null;
      (out[route] ||= []).push({
        p: label,
        // Comparable when the system's sampling for that day type was complete
        // and the route ran on enough of those days.
        cwd: !!(sys?.wd.complete && x.wdN >= min.weekday && wd),
        cwe: !!(sys?.we.complete && x.weN >= min.weekend && we),
        wdN: x.wdN, weN: x.weN, wd, we,
      });
    }
  }
  for (const r of Object.keys(out)) out[r].sort((a, b) => a.p.localeCompare(b.p));
  return { rows: out, refs };
}

// ── per-route history files (for route.html) ────────────────────────────────
function hourProfile(days, route) {
  const prof = {};
  for (const type of TYPES) {
    const cells = routeCells(days, route, type);
    prof[SHORT[type]] = Object.fromEntries(WINDOW_HOURS.filter(h => cells[h].n > 0)
      .map(h => [h, { n: cells[h].n, mov: rd(cells[h].mov), all: rd(cells[h].all), stop: rd(cells[h].stop, 4), buses: rd(cells[h].buses, 2), sched: rd(cells[h].sched, 2), pax: rd(cells[h].pax, 1) }]));
  }
  return prof;
}

// ── main ────────────────────────────────────────────────────────────────────
function monthBounds(m) {
  const [y, mo] = m.split('-').map(Number);
  const end = new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
  return { start: `${m}-01`, end, length: Number(end.slice(8)) };
}
function weekBounds(days) {
  const d = new Date(days[0].date + 'T00:00:00Z');
  const mon = new Date(d); mon.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  const sun = new Date(mon); sun.setUTCDate(mon.getUTCDate() + 6);
  return { start: mon.toISOString().slice(0, 10), end: sun.toISOString().slice(0, 10) };
}

function main() {
  const { days: raw, stale } = loadDailies();
  if (stale.length > 2) {
    console.error(`rollup: ${stale.length} daily files are from an older method (${stale.slice(0, 5).join(', ')}...). ` +
      'Run the bus-tracker-backfill workflow to reprocess them; refusing to publish a mixed series.');
    process.exit(1);
  }
  if (stale.length) console.warn(`rollup: ignoring ${stale.length} old-method daily file(s): ${stale.join(', ')}`);
  if (!raw.length) { console.error('rollup: no daily files'); process.exit(1); }

  // A day with a handful of snapshots (the March 19 test) carries no usable hour.
  const days = raw.filter(d => d.snapshots >= 6).map(deriveDay);
  assignDayTypes(days);

  const byWeek = {}, byMonth = {};
  for (const d of days) {
    (byWeek[isoWeek(d.date)] ||= []).push(d);
    (byMonth[d.date.slice(0, 7)] ||= []).push(d);
  }
  // Pass 1: hour cells for every period; the usual level of each hour comes
  // from the weeks and is used to fill at most two missed hours.
  const weekCells = Object.fromEntries(Object.entries(byWeek).map(([w, ds]) => [w, { weekday: systemCells(ds, 'weekday'), weekend: systemCells(ds, 'weekend') }]));
  const monthCells = Object.fromEntries(Object.entries(byMonth).map(([m, ds]) => [m, { weekday: systemCells(ds, 'weekday'), weekend: systemCells(ds, 'weekend') }]));
  const REF = {
    weekday: buildRef(Object.values(weekCells).map(c => c.weekday), c => c.n >= MIN_CELL_DAYS.week.weekday, SYS_KEYS),
    weekend: buildRef(Object.values(weekCells).map(c => c.weekend), c => c.n >= MIN_CELL_DAYS.week.weekend, SYS_KEYS),
  };
  const weekly = Object.entries(byWeek).sort(([a], [b]) => a.localeCompare(b))
    .map(([w, ds]) => { const b = weekBounds(ds); return { ...aggregatePeriod(ds, w, 'week', b, weekCells[w], REF), weekStart: b.start, weekEnd: b.end }; });
  const monthly = Object.entries(byMonth).sort(([a], [b]) => a.localeCompare(b))
    .map(([m, ds]) => ({ ...aggregatePeriod(ds, m, 'month', monthBounds(m), monthCells[m], REF), monthDays: monthBounds(m).length }));

  const sysWeek = Object.fromEntries(weekly.map(w => [w.period, w]));
  const sysMonth = Object.fromEntries(monthly.map(m => [m.period, m]));
  const allRoutes = [...new Set(days.flatMap(d => Object.keys(d.routes)))].sort();
  const meta = Object.fromEntries(allRoutes.map(r => [r, { kind: routeKind(r === '(blank)' ? '' : r), group: routeGroup(r) }]));
  const wk = routePeriods(byWeek, 'week', sysWeek, allRoutes);
  const weeklyRoutes = wk.rows;
  const monthlyRoutes = routePeriods(byMonth, 'month', sysMonth, allRoutes, wk.refs).rows;

  // Day table
  const dayRows = days.map(d => {
    const hs = d.covered;
    return {
      date: d.date, weekday: d.weekday, dayType: d.dayType, reason: d.typeReason || null,
      holiday: d.holiday?.name || null,
      snapshots: d.snapshots, hoursCollected: hs.length, hours: hs,
      routesMidday: d.middayRoutes,
      // Means over the hours collected that day. A day with only evening hours
      // reads fast; compare days only when hoursCollected is 17.
      mov: rd(mean(hs.map(h => d.hours[h].mov))), all: rd(mean(hs.map(h => d.hours[h].all))),
      stop: rd(mean(hs.map(h => d.hours[h].stop)), 4),
      buses: rd(mean(hs.map(h => d.hours[h].buses)), 1),
      sched: hs.length && hs.every(h => d.hours[h].sched != null) ? rd(mean(hs.map(h => d.hours[h].sched)), 1) : null,
      busesReg: rd(mean(hs.map(h => d.hours[h].busesReg)), 1),
      schedulePattern: d.schedulePattern,
    };
  });

  mkdirSync(SUMMARY_DIR, { recursive: true });
  const stamp = { methodVersion: METHOD_VERSION, generatedAt: new Date().toISOString() };
  const write = (f, obj) => writeFileSync(join(SUMMARY_DIR, f), JSON.stringify(obj));
  write('days.json', { ...stamp, days: dayRows });
  write('weekly.json', { ...stamp, periods: weekly });
  write('monthly.json', { ...stamp, periods: monthly });
  write('weekly-routes.json', { ...stamp, meta, routes: weeklyRoutes });
  write('monthly-routes.json', { ...stamp, meta, routes: monthlyRoutes });

  // Collection health: the alert the old pipeline never had.
  const todayET = etParts(Date.now()).date;
  const recent = dayRows.filter(d => d.date < todayET).slice(-21);
  const thin = recent.slice(-1).filter(d => d.hoursCollected < HEALTH_MIN_HOURS);
  const health = {
    ...stamp,
    minHours: HEALTH_MIN_HOURS,
    lastDay: recent.length ? recent[recent.length - 1].date : null,
    days: recent.map(d => ({ date: d.date, hours: d.hoursCollected, snapshots: d.snapshots, dayType: d.dayType })),
    alert: thin.length > 0,
    message: thin.length
      ? `Collection was thin on ${thin.map(d => `${apDate(d.date)} (${d.hoursCollected} of 17 hours)`).join(', ')}.`
      : 'Collection is running normally.',
  };
  write('health.json', health);

  const comparableWeeks = weekly.filter(w => w.comparable);
  const latest = {
    ...stamp,
    lastDay: dayRows[dayRows.length - 1],
    lastFullWeek: [...weekly].reverse().find(w => w.days === 7)?.period || null,
    lastComparableWeek: comparableWeeks.length ? comparableWeeks[comparableWeeks.length - 1].period : null,
    comparableWeeks: comparableWeeks.length,
    health: { alert: health.alert, message: health.message },
  };
  write('latest.json', latest);

  // Route history files
  if (existsSync(HISTORY_DIR)) rmSync(HISTORY_DIR, { recursive: true });
  mkdirSync(HISTORY_DIR, { recursive: true });
  const compWeeks = comparableWeeks.map(w => w.period);
  const recentSet = new Set(compWeeks.slice(-4));
  const firstSet = new Set(compWeeks.slice(0, 4));
  const index = {};
  for (const route of allRoutes) {
    if (route === '(blank)') continue;
    const daysWith = days.filter(d => d.routes[route]);
    if (!daysWith.length) continue;
    const recentDays = days.filter(d => recentSet.has(isoWeek(d.date)));
    const firstDays = days.filter(d => firstSet.has(isoWeek(d.date)));
    const daily = daysWith.map(d => {
      const r = d.routes[route];
      const hs = d.covered.filter(h => r.h[h]);
      return [d.date, d.dayType, d.covered.length, rd(mean(hs.map(h => r.h[h].mov))), rd(mean(hs.map(h => r.h[h].all))), rd(mean(d.covered.map(h => r.h[h]?.buses || 0)), 2)];
    });
    const doc = {
      ...stamp, route, ...meta[route],
      weekly: weeklyRoutes[route] || [], monthly: monthlyRoutes[route] || [],
      profile: {
        recent: { weeks: [...recentSet], ...hourProfile(recentDays, route) },
        first: { weeks: [...firstSet], ...hourProfile(firstDays, route) },
      },
      dailyFields: ['date', 'dayType', 'hoursCollected', 'mov', 'all', 'buses'],
      daily,
    };
    writeFileSync(join(HISTORY_DIR, `${routeSlug(route)}.json`), JSON.stringify(doc));
    const cw = (weeklyRoutes[route] || []).filter(w => w.cwd && w.wd?.all != null);
    const lastW = cw[cw.length - 1];
    const vals = cw.map(w => w.wd.all);
    const before = vals.slice(-5, -1);
    const moves = vals.slice(1).map((v, i) => Math.abs(v - vals[i])).sort((a, b) => a - b);
    index[route] = {
      slug: routeSlug(route), ...meta[route], lastWeek: lastW?.p || null,
      wdMov: lastW?.wd?.mov ?? null, wdAll: lastW?.wd?.all ?? null, buses: lastW?.wd?.buses ?? null,
      // Latest comparable week against the mean of the four before it; changes
      // inside the route's usual week-to-week wobble are noise.
      chg: before.length >= 2 ? rd(lastW.wd.all - mean(before)) : null,
      wobble: moves.length >= 2 ? rd(Math.max(0.15, moves[Math.floor(moves.length / 2)])) : null,
      nWeeks: cw.length, days: daysWith.length,
    };
  }
  const wdWeeks = weekly.filter(w => w.days === 7 && w.wd.complete).map(w => w.period);
  writeFileSync(join(HISTORY_DIR, 'index.json'), JSON.stringify({ ...stamp, lastComparableWeek: compWeeks[compWeeks.length - 1] || null, lastWeekdayWeek: wdWeeks[wdWeeks.length - 1] || null, routes: index }));

  console.log(`rollup v${METHOD_VERSION}: ${days.length} days, ${weekly.length} weeks (${comparableWeeks.length} comparable), ` +
    `${monthly.length} months (${monthly.filter(m => m.comparable).length} comparable), ${Object.keys(index).length} route files`);
  for (const w of weekly.slice(-6)) {
    console.log(`  ${w.period} days=${w.days} cov=${w.coveragePct}% comparable=${w.comparable} wd=${w.wd.mov}/${w.wd.all} we=${w.we.mov}/${w.we.all} idx=${w.idx.mov}/${w.idx.all} missing wd=[${w.wd.missingHours}] we=[${w.we.missingHours}]`);
  }
  console.log(`  health: ${health.message}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
