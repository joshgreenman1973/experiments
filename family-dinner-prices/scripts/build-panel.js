#!/usr/bin/env node
/**
 * Builds the cuisine-aware FAMILY-BILL panel (data/panel.json) from the
 * cuisine-aware pins (data/meals-pinned.json), applying deterministic guards.
 *
 * Meal bundles (+ 2 drinks @ $2.50, + 8.875% tax + 18% tip):
 *   - pizza   : 1 large pizza
 *   - chinese : 2 different shared dishes + 1 order of egg rolls
 *   - standard: 2 adult entrees + 2 kid portions
 *
 * Output: data/panel.json
 * Usage: node scripts/build-panel.js <baselineDate YYYY-MM-DD>
 */
const fs = require('fs');
const path = require('path');
const dataDir = path.join(__dirname, '..', 'data');
const baselineDate = process.argv[2];
if (!/^\d{4}-\d{2}-\d{2}$/.test(baselineDate || '')) { console.error('Usage: build-panel.js <YYYY-MM-DD>'); process.exit(1); }

const BEV = 2.50, BEVQTY = 2, TAX = 0.08875, TIP = 0.18;
const pinned = JSON.parse(fs.readFileSync(path.join(dataDir, 'meals-pinned.json'), 'utf8'));
// carry freshness from prior panel if present
let oldFresh = {}; try { const op = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel.json'), 'utf8')).panel; for (const [id, p] of Object.entries(op)) oldFresh[id] = p.baselineFreshness; } catch {}

// Snap a pinned item back to the EXACT basket string (the scout-verified text
// that re-finds on the live page). pin-meals sometimes appended the price into
// the item text; the basket string is canonical, so we match to it and use the
// basket's price.
const baskets = {}; try { for (const r of JSON.parse(fs.readFileSync(path.join(dataDir, 'familybill-input.json'), 'utf8'))) baskets[r.id] = r.items; } catch {}
const norm = s => String(s || '').toLowerCase().replace(/\s*[—\-–]\s*\$.*$/, '').replace(/\s*\$\s*\d[\d.]*\s*$/, '').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
const toks = s => new Set(norm(s).split(' ').filter(w => w.length > 2));
function snap(id, comp) {
  const items = baskets[id]; if (!items || !comp || typeof comp.item !== 'string') return null;
  const target = norm(comp.item); if (!target) return null;
  let best = null, bestScore = 0;
  for (const it of items) {
    const bi = norm(it.item); let score = 0;
    if (bi === target) score = 1;
    else if (bi.includes(target) || target.includes(bi)) score = 0.9;
    else { const a = toks(target), b = toks(it.item); const inter = [...a].filter(x => b.has(x)).length; score = inter / Math.max(1, Math.max(a.size, b.size)); }
    if (score > bestScore) { bestScore = score; best = it; }
  }
  return bestScore >= 0.5 ? { item: best.item.trim(), price: best.price } : null;
}

const num = x => typeof x === 'number' && isFinite(x) && x > 0;
const okItem = c => c && typeof c.item === 'string' && c.item.trim().length >= 3 && num(c.price);
const DRINKISH = /\b(beer|wine|vodka|margarita|cocktail|mojito|sangria|milkshake|smoothie|lemonade|hot chocolate|iced tea|soda can|can soda|fountain)\b/i;
// desserts must not be picked as an entree/dish
const DESSERTISH = /\b(cake|medovyk|medovik|cheesecake|tiramisu|baklava|cannoli|flan|ice cream|gelato|pudding|donut|doughnut|pastry|dessert|brownie|cookie|mousse|churro)\b/i;
const billOf = (comps) => Math.round((comps.reduce((s, c) => s + c.base * c.qty, 0) + BEV * BEVQTY) * (1 + TAX + TIP) * 100) / 100;

function buildStandard(o) {
  const p = o.pins || {};
  const a = snap(o.id, p.adultEntree), k = snap(o.id, p.kidPortion);
  if (!okItem(a) || !okItem(k)) return null;
  if (DRINKISH.test(a.item) || DRINKISH.test(k.item) || DESSERTISH.test(a.item) || DESSERTISH.test(k.item)) return null;
  if (!(a.price >= 6 && a.price <= 32)) return null;
  if (!(k.price < a.price)) return null;
  if (a.item.toLowerCase() === k.item.toLowerCase()) return null;
  return { mealType: 'standard', components: [
    { role: 'Adult entree', item: a.item, base: a.price, qty: 2 },
    { role: 'Kid portion', item: k.item, base: k.price, qty: 2 },
  ], overCeiling: a.price > 25 };
}

function buildComponents(o) {
  const p = o.pins || {};
  if (o.mealType === 'pizza') {
    const z = snap(o.id, p.largePizza);
    if (!okItem(z) || !(z.price >= 10 && z.price <= 45)) return null;
    if (/\bslice\b|personal|individual|mini/i.test(z.item)) return null;
    return { mealType: 'pizza', components: [{ role: 'Large pizza', item: z.item, base: z.price, qty: 1 }], overCeiling: z.price > 35 };
  }
  if (o.mealType === 'chinese') {
    const d1 = snap(o.id, p.dish1), d2 = snap(o.id, p.dish2), e = snap(o.id, p.eggRolls);
    if (!okItem(d1) || !okItem(d2) || !okItem(e)) return null;
    if (d1.item.toLowerCase() === d2.item.toLowerCase()) return null;       // must be two different dishes
    if (DRINKISH.test(d1.item)||DRINKISH.test(d2.item)||DESSERTISH.test(d1.item)||DESSERTISH.test(d2.item)) return null;
    if (!(d1.price >= 5 && d1.price <= 35) || !(d2.price >= 5 && d2.price <= 35)) return null;
    if (!(e.price >= 1 && e.price <= 14)) return null;
    return { mealType: 'chinese', components: [
      { role: 'Dish', item: d1.item, base: d1.price, qty: 1 },
      { role: 'Dish', item: d2.item, base: d2.price, qty: 1 },
      { role: 'Egg rolls', item: e.item, base: e.price, qty: 1 },
    ], overCeiling: Math.max(d1.price, d2.price) > 30 };
  }
  if (o.mealType === 'indian') {
    const d1 = snap(o.id, p.dish1), d2 = snap(o.id, p.dish2), rice = snap(o.id, p.rice), bread = snap(o.id, p.bread);
    const dishesOk = okItem(d1) && okItem(d2) && d1.item.toLowerCase() !== d2.item.toLowerCase()
      && [d1, d2].every(x => !DRINKISH.test(x.item) && !DESSERTISH.test(x.item) && x.price >= 5 && x.price <= 35);
    if (dishesOk && okItem(rice) && okItem(bread) && rice.price >= 1 && rice.price <= 16 && bread.price >= 1 && bread.price <= 14) {
      return { mealType: 'indian', components: [
        { role: 'Dish', item: d1.item, base: d1.price, qty: 1 },
        { role: 'Dish', item: d2.item, base: d2.price, qty: 1 },
        { role: 'Rice', item: rice.item, base: rice.price, qty: 1 },
        { role: 'Naan/bread', item: bread.item, base: bread.price, qty: 1 },
      ], overCeiling: Math.max(d1.price, d2.price) > 30 };
    }
    return buildStandard(o); // fall back when rice/bread not separately listed
  }
  if (o.mealType === 'thai') {
    const d1 = snap(o.id, p.dish1), d2 = snap(o.id, p.dish2), rice = snap(o.id, p.rice);
    const dishesOk = okItem(d1) && okItem(d2) && d1.item.toLowerCase() !== d2.item.toLowerCase()
      && [d1, d2].every(x => !DRINKISH.test(x.item) && !DESSERTISH.test(x.item) && x.price >= 5 && x.price <= 35);
    if (dishesOk && okItem(rice) && rice.price >= 1 && rice.price <= 16) {
      return { mealType: 'thai', components: [
        { role: 'Dish', item: d1.item, base: d1.price, qty: 1 },
        { role: 'Dish', item: d2.item, base: d2.price, qty: 1 },
        { role: 'Rice', item: rice.item, base: rice.price, qty: 1 },
      ], overCeiling: Math.max(d1.price, d2.price) > 30 };
    }
    return buildStandard(o); // fall back when rice not separately listed
  }
  return buildStandard(o);
}

const panel = {}; let kept = 0, dropped = 0; const byType = {};
for (const o of pinned) {
  const built = buildComponents(o);
  if (!built) { dropped++; continue; }
  panel[o.id] = {
    name: o.name, borough: o.borough, cuisine: o.cuisine, neighborhood: o.neighborhood || '',
    menuUrl: o.menuUrl, platform: o.platform || null, baselineFreshness: oldFresh[o.id] || { lastModified: null, etag: null },
    mealType: built.mealType || o.mealType, components: built.components, beveragePrice: BEV, beverageQty: BEVQTY,
    baselineBill: billOf(built.components), overCeiling: built.overCeiling,
  };
  kept++; const mt = built.mealType || o.mealType; byType[mt] = (byType[mt] || 0) + 1;
}

const out = {
  meta: {
    baselineDate, beveragePrice: BEV, beverageQty: BEVQTY, tax: TAX, tip: TIP,
    mealModels: { pizza: '1 large pizza + 2 drinks', chinese: '2 shared dishes + egg rolls + 2 drinks', indian: '2 shared dishes + rice + naan + 2 drinks', thai: '2 shared dishes + rice + 2 drinks', standard: '2 adult entrees + 2 kid portions + 2 drinks' },
    note: 'All bundles + 8.875% sales tax + 18% tip. Drinks standardized at $2.50.',
    count: kept,
    bls: { metro: 'New York-Newark-Jersey City', measure: 'Food away from home', yoy: 3.4, asOf: 'April 2026', source: 'https://www.bls.gov/regions/northeast/news-release/consumerpriceindex_newyork.htm' },
  },
  panel,
};
fs.writeFileSync(path.join(dataDir, 'panel.json'), JSON.stringify(out, null, 2));
const bills = Object.values(panel).map(p => p.baselineBill).sort((a, b) => a - b);
const avg = bills.reduce((a, b) => a + b, 0) / (bills.length || 1);
console.log(`Panel: ${kept} restaurants (dropped ${dropped}). Types: ${JSON.stringify(byType)}`);
console.log(`Baseline bill: avg $${avg.toFixed(2)}, median $${bills[Math.floor(bills.length / 2)].toFixed(2)}, range $${bills[0]}-$${bills[bills.length - 1]}`);
