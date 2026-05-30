#!/usr/bin/env node
/**
 * Builds the FAMILY-BILL panel (data/panel.json) from the verified pinning
 * output (data/familybill-verified.json, the workflow result) plus the menu
 * URLs / platform / freshness we already collected.
 *
 * Each restaurant contributes a pinned ADULT ENTREE and KID PORTION. Beverages
 * are standardized. The baseline bill = (2 adult + 2 kid + 2 beverages) x (1+tax+tip).
 *
 * Usage: node scripts/build-panel.js <baselineDate YYYY-MM-DD>
 */
const fs = require('fs');
const path = require('path');
const dataDir = path.join(__dirname, '..', 'data');
const baselineDate = process.argv[2];
if (!/^\d{4}-\d{2}-\d{2}$/.test(baselineDate || '')) { console.error('Usage: build-panel.js <YYYY-MM-DD>'); process.exit(1); }

const BEV = 2.50, TAX = 0.08875, TIP = 0.18;
const bill = (a, k) => Math.round((2 * a + 2 * k + 2 * BEV) * (1 + TAX + TIP) * 100) / 100;

const verified = JSON.parse(fs.readFileSync(path.join(dataDir, 'familybill-verified.json'), 'utf8'));
const input = JSON.parse(fs.readFileSync(path.join(dataDir, 'familybill-input.json'), 'utf8'));
const byId = Object.fromEntries(input.map(r => [r.id, r]));

// freshness sources: current panel.json (existing 53, by id) + sheet scan (new, by name)
let oldFresh = {}; try { const op = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel.json'), 'utf8')).panel; for (const [id, p] of Object.entries(op)) oldFresh[id] = p.baselineFreshness; } catch {}
let sheetFresh = {}; try { const sc = JSON.parse(fs.readFileSync(path.join(dataDir, 'sheet-candidates-scan.json'), 'utf8')); for (const v of Object.values(sc)) if (v.freshness) sheetFresh[(v.name || '').toLowerCase()] = v.freshness; } catch {}

const ok = x => x && typeof x.item === 'string' && x.item.trim().length >= 3 && typeof x.price === 'number' && x.price > 0;
const panel = {};
let kept = 0, dropped = 0;
for (const v of verified) {
  if (v.valid === false || !ok(v.adultEntree) || !ok(v.kidPortion)) { dropped++; continue; }
  if (!(v.kidPortion.price < v.adultEntree.price)) { dropped++; continue; }   // hard guard
  const meta = byId[v.id]; if (!meta) { dropped++; continue; }
  const fresh = oldFresh[v.id] || sheetFresh[(v.name || '').toLowerCase()] || { lastModified: null, etag: null };
  panel[v.id] = {
    name: v.name, borough: v.borough, cuisine: v.cuisine, neighborhood: meta.neighborhood || '',
    menuUrl: meta.menuUrl, platform: meta.platform || null, baselineFreshness: fresh,
    adultEntree: { item: v.adultEntree.item.trim(), base: v.adultEntree.price },
    kidPortion: { item: v.kidPortion.item.trim(), base: v.kidPortion.price },
    beveragePrice: BEV,
    baselineBill: bill(v.adultEntree.price, v.kidPortion.price),
    overCeiling: !!v.overCeiling,
  };
  kept++;
}

const out = {
  meta: {
    baselineDate, beveragePrice: BEV, tax: TAX, tip: TIP,
    mealModel: '2 adult entrees + 2 kid portions + 2 non-alcoholic beverages, plus 8.875% tax and 18% tip',
    count: kept, bls: null,
  },
  panel,
};
fs.writeFileSync(path.join(dataDir, 'panel.json'), JSON.stringify(out, null, 2));
const bills = Object.values(panel).map(p => p.baselineBill).sort((a, b) => a - b);
const avg = bills.reduce((a, b) => a + b, 0) / (bills.length || 1);
console.log(`Family-bill panel: ${kept} restaurants (dropped ${dropped}). Baseline ${baselineDate}.`);
console.log(`Baseline bill: avg $${avg.toFixed(2)}, median $${bills[Math.floor(bills.length / 2)].toFixed(2)}, range $${bills[0]}-$${bills[bills.length - 1]}`);
