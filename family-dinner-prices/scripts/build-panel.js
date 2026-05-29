#!/usr/bin/env node
/**
 * Locks the tracked panel from data/panel-candidates.json.
 *
 * Selection rules (a baseline is only included if it's a credible family meal):
 *   - adult entree price in [8, 40]
 *   - kid meal in [2, 16] AND cheaper than the adult entree
 *   - appetizer <= 1.15 x adult entree
 *   - whole-meal total in [25, 110]
 *   - item strings contain no price/HTML cruft (so they can be re-matched)
 * Drinks are standardized at a fixed price citywide (menus almost never list
 * soda prices in static HTML, and a can of soda is ~the same everywhere), so
 * drinks contribute no month-to-month noise.
 *
 * Output: data/panel.json — the locked panel with pinned line items + baseline.
 *
 * Usage: node scripts/build-panel.js <baselineDate YYYY-MM-DD>
 */
const fs = require('fs');
const path = require('path');
const dataDir = path.join(__dirname, '..', 'data');

const SODA_PRICE = 2.50;       // per soft drink, standardized
const TAX = 1.08875;           // NYC sales tax
const baselineDate = process.argv[2];
if (!/^\d{4}-\d{2}-\d{2}$/.test(baselineDate || '')) {
  console.error('Usage: node scripts/build-panel.js <YYYY-MM-DD>');
  process.exit(1);
}

const cand = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel-candidates.json'), 'utf8'));
const ok = x => x && typeof x.item === 'string' && x.item.trim().length >= 3 &&
                typeof x.price === 'number' && isFinite(x.price) && x.price > 0;

function familyTotal(a, k, ap) {
  const sub = a * 2 + k * 2 + ap + SODA_PRICE * 2;
  return Math.round(sub * TAX * 100) / 100;
}

const panel = {};
let kept = 0, dropped = 0;
for (const [id, v] of Object.entries(cand)) {
  if (!v.readable) continue;
  const p = v.pinned || {};
  if (!(ok(p.adultEntree) && ok(p.kidMeal) && ok(p.appetizer))) { dropped++; continue; }
  const a = p.adultEntree.price, k = p.kidMeal.price, ap = p.appetizer.price;
  const tot = familyTotal(a, k, ap);
  const messy = /\$|&#/.test(p.adultEntree.item + p.kidMeal.item + p.appetizer.item);
  const sane = a >= 8 && a <= 40 && k >= 2 && k <= 16 && k < a && ap <= a * 1.15 && tot >= 25 && tot <= 110 && !messy;
  if (!sane) { dropped++; continue; }

  panel[id] = {
    name: v.name, borough: v.borough, cuisine: v.cuisine, neighborhood: v.neighborhood, menuUrl: v.menuUrl,
    pinned: {
      adultEntree: { item: p.adultEntree.item.trim(), price: a },
      kidMeal: { item: p.kidMeal.item.trim(), price: k },
      appetizer: { item: p.appetizer.item.trim(), price: ap },
      drinks: { item: 'Soft drink (standardized)', price: SODA_PRICE, standardized: true },
    },
    baselineTotal: tot,
    baselineDate,
  };
  kept++;
}

const out = {
  meta: {
    baselineDate,
    sodaPrice: SODA_PRICE,
    tax: TAX,
    formula: '2 adult entrees + 2 kid meals + 1 appetizer + 2 soft drinks, x sales tax',
    note: 'Tracked panel of restaurants whose menus are reliably readable and whose exact line items are pinned for same-item month-over-month comparison. Drinks standardized citywide.',
    count: kept,
  },
  panel,
};
fs.writeFileSync(path.join(dataDir, 'panel.json'), JSON.stringify(out, null, 2));
console.log(`Panel locked: ${kept} restaurants (dropped ${dropped}). Baseline ${baselineDate}.`);
console.log(`Wrote data/panel.json`);
