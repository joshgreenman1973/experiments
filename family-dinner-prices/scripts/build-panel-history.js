#!/usr/bin/env node
/**
 * Builds panel-history.js (PANEL_HISTORY) from data/panel.json + the dated
 * snapshots in data/panel-snapshots/.
 *
 *  - Jevons index (rec #1): citywide & per-borough index = 100 x geometric mean
 *    of restaurant price relatives vs baseline. Scale-free, robust to high-end.
 *  - Dispersion (rec #5): median / trimmed mean / IQR of restaurant relatives
 *    each month, as a confidence band.
 *  - Core dollar sub-indices (rec #6): for homogeneous categories carried by >=4
 *    restaurants, the actual average dollar price over time (BEC-style).
 *
 * Usage: node scripts/build-panel-history.js
 */
const fs = require('fs');
const path = require('path');
const { CORE_LABELS } = require('./lib-core');
const dataDir = path.join(__dirname, '..', 'data');
const snapDir = path.join(dataDir, 'panel-snapshots');

const panelDoc = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel.json'), 'utf8'));
const files = fs.readdirSync(snapDir).filter(f => f.endsWith('.json')).sort();
if (!files.length) { console.error('No panel snapshots. Run check-panel.js first.'); process.exit(1); }
const snaps = files.map(f => JSON.parse(fs.readFileSync(path.join(snapDir, f), 'utf8')));
const dates = snaps.map(s => s.date);

const geomean = a => a.length ? Math.round(Math.exp(a.reduce((s, x) => s + Math.log(x), 0) / a.length) * 1e4) / 1e4 : null;
const idx = a => a == null ? null : Math.round(a * 1000) / 10; // relative -> index point (100 base)
const median = a => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const quantile = (a, q) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const pos = (s.length - 1) * q; const lo = Math.floor(pos); return s[lo] + (s[lo + 1] - s[lo] || 0) * (pos - lo); };
const trimmedMean = (a, p = 0.1) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); const k = Math.floor(s.length * p); const t = s.slice(k, s.length - k); return t.reduce((x, y) => x + y, 0) / (t.length || 1); };

const boroughs = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island'];

// Index series (geomean of relatives -> index=100 base)
const citywide = snaps.map(s => idx(geomean(Object.values(s.restaurants).map(r => r.relative).filter(x => x != null))));
const byBorough = {};
for (const b of boroughs) byBorough[b] = snaps.map(s => idx(geomean(Object.values(s.restaurants).filter(r => r.borough === b).map(r => r.relative).filter(x => x != null))));

// Dispersion of restaurant relatives (as index points)
const dispersion = {
  median: snaps.map(s => idx(median(Object.values(s.restaurants).map(r => r.relative).filter(x => x != null)))),
  trimmedMean: snaps.map(s => idx(trimmedMean(Object.values(s.restaurants).map(r => r.relative).filter(x => x != null)))),
  p25: snaps.map(s => idx(quantile(Object.values(s.restaurants).map(r => r.relative).filter(x => x != null), 0.25))),
  p75: snaps.map(s => idx(quantile(Object.values(s.restaurants).map(r => r.relative).filter(x => x != null), 0.75))),
};

// Core "typical price" sub-indices. To stay honest these are CATEGORY medians,
// not a matched-item claim: one representative item per restaurant (the plainest
// = lowest-priced variant), then the MEDIAN across restaurants each month
// (robust to a mis-read or an outlier order). Requires >=4 distinct restaurants.
const catRestaurants = {}; // cat -> { id -> [keys] }
for (const [id, r] of Object.entries(panelDoc.panel)) {
  for (const b of r.basket) if (b.core) {
    (catRestaurants[b.core] = catRestaurants[b.core] || {});
    (catRestaurants[b.core][id] = catRestaurants[b.core][id] || []).push(b.key);
  }
}
const core = {};
for (const [cat, byRest] of Object.entries(catRestaurants)) {
  const ids = Object.keys(byRest);
  if (ids.length < 4) continue;
  const series = snaps.map(s => {
    // one representative price per restaurant = the lowest-priced matched variant that month
    const repPrices = ids.map(id => {
      const ps = byRest[id].map(k => s.restaurants[id]?.items?.[k]?.price).filter(p => p != null);
      return ps.length ? Math.min(...ps) : null;
    }).filter(p => p != null);
    const m = median(repPrices);
    return m == null ? null : Math.round(m * 100) / 100;
  });
  core[cat] = { label: CORE_LABELS[cat] || cat, restaurantCount: ids.length, series, baseline: series[0], latest: series[series.length - 1] };
}

// Per-restaurant panel list
const last = snaps[snaps.length - 1];
const panelList = Object.entries(panelDoc.panel).map(([id, r]) => {
  const sr = last.restaurants[id] || {};
  const itemPrices = r.basket.map(b => sr.items?.[b.key]?.price ?? b.base);
  return {
    id, name: r.name, borough: r.borough, cuisine: r.cuisine, neighborhood: r.neighborhood, platform: r.platform,
    basketSize: r.basket.length,
    sampleItems: r.basket.slice(0, 4).map(b => b.item),
    medianPrice: Math.round(median(itemPrices) * 100) / 100,
    index: idx(sr.relative ?? 1.0),
    observed: sr.observed ?? r.basket.length,
    pageChanged: sr.pageChanged ?? null,
  };
});

// Movers (only restaurants with full-ish observation latest)
const movers = panelList
  .filter(p => p.index != null && Math.abs(p.index - 100) > 0.5 && snaps.length >= 2)
  .map(p => ({ name: p.name, borough: p.borough, change: Math.round((p.index - 100) * 10) / 10 }))
  .sort((a, b) => Math.abs(b.change) - Math.abs(a.change));

const staleCount = Object.values(last.restaurants).filter(r => r.pageChanged === false).length;

const out = {
  generatedAt: new Date().toISOString(),
  baselineDate: panelDoc.meta.baselineDate,
  snapshotCount: snaps.length,
  dates,
  indexBase: 100,
  index: { citywide },
  byBorough,
  dispersion,
  core,
  panel: panelList,
  movers,
  stats: {
    count: Object.keys(panelDoc.panel).length,
    totalItems: Object.values(panelDoc.panel).reduce((a, r) => a + r.basket.length, 0),
    observedLatest: Object.values(last.restaurants).reduce((a, r) => a + (r.observed || 0), 0),
    stalePages: staleCount,
    sodaPrice: panelDoc.meta.sodaPrice,
  },
};

const header = `// Auto-generated by build-panel-history.js — do not edit\n// Generated: ${out.generatedAt}\n// Snapshots: ${snaps.length}\n\n`;
fs.writeFileSync(path.join(__dirname, '..', 'panel-history.js'), header + 'const PANEL_HISTORY = ' + JSON.stringify(out, null, 2) + ';\n');
console.log(`Wrote panel-history.js — ${out.stats.count} restaurants, ${snaps.length} snapshot(s), index ${citywide[citywide.length - 1]}`);
console.log(`Core sub-indices: ${Object.keys(core).map(c => CORE_LABELS[c] || c).join(', ') || '(none yet)'}`);
