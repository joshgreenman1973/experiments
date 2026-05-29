#!/usr/bin/env node
/**
 * Locks the tracked panel from data/trackable-scan.json.
 *
 * Each restaurant contributes a BASKET of its reliably-locked, clearly-named
 * menu items (not a rigid identical bundle) — so the index is a per-restaurant
 * price relative, the way CPI elementary aggregates work. A restaurant is
 * included if the deterministic matcher locked at least MIN_ITEMS of its items.
 *
 * Output: data/panel.json
 * Usage: node scripts/build-panel.js <baselineDate YYYY-MM-DD> [minItems=4]
 */
const fs = require('fs');
const path = require('path');
const { coreCategory, itemKey } = require('./lib-core');
const dataDir = path.join(__dirname, '..', 'data');

const baselineDate = process.argv[2];
const MIN_ITEMS = parseInt(process.argv[3] || '4', 10);
if (!/^\d{4}-\d{2}-\d{2}$/.test(baselineDate || '')) { console.error('Usage: build-panel.js <YYYY-MM-DD> [minItems]'); process.exit(1); }

const scan = JSON.parse(fs.readFileSync(path.join(dataDir, 'trackable-scan.json'), 'utf8'));
const SODA = 2.50, TAX = 1.08875;

const panel = {};
let kept = 0, dropped = 0;
for (const [id, v] of Object.entries(scan)) {
  if (!v.readable || !Array.isArray(v.items)) { dropped++; continue; }
  // sane individual prices, de-duped, reasonable basket
  const seen = new Set();
  const basket = [];
  for (const it of v.items) {
    if (!it || typeof it.item !== 'string' || typeof it.price !== 'number') continue;
    if (!(it.price >= 1 && it.price <= 200)) continue;
    const key = itemKey(it.item);
    if (!key || seen.has(key)) continue; seen.add(key);
    basket.push({ key, item: it.item.trim(), size: (it.size || '').toString().trim(), base: it.price, core: coreCategory(it.item) });
  }
  if (basket.length < MIN_ITEMS) { dropped++; continue; }
  panel[id] = {
    name: v.name, borough: v.borough, cuisine: v.cuisine, neighborhood: v.neighborhood,
    menuUrl: v.menuUrl, platform: v.platform || null,
    baselineFreshness: v.freshness || { lastModified: null, etag: null },
    basket,
  };
  kept++;
}

const out = {
  meta: {
    baselineDate, sodaPrice: SODA, tax: TAX, indexBase: 100, minItems: MIN_ITEMS,
    method: 'Per-restaurant basket of pinned named items; index is the geometric mean (Jevons) of price relatives vs baseline, =100 at base.',
    count: kept,
  },
  panel,
};
fs.writeFileSync(path.join(dataDir, 'panel.json'), JSON.stringify(out, null, 2));
const sizes = Object.values(panel).map(p => p.basket.length);
const tot = sizes.reduce((a, b) => a + b, 0);
console.log(`Panel locked: ${kept} restaurants (dropped ${dropped}), ${tot} pinned items, avg basket ${(tot / (kept||1)).toFixed(1)}. Baseline ${baselineDate}, min ${MIN_ITEMS} items.`);
