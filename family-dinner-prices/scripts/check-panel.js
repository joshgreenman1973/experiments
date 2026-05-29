#!/usr/bin/env node
/**
 * Monthly re-check for the TRACKED PANEL (data/panel.json).
 *
 * The honest core: we only accept a new price for a component if the SAME
 * pinned menu line is still on the page. We locate the pinned item string in
 * the menu text and read the price attached to that same line. If the line is
 * gone (menu changed, item renamed, page went JS-only), we DO NOT substitute a
 * different item — we carry that component's last price forward and flag it
 * `unverified`. This eliminates the item-swap noise that made the old
 * scrape-everything approach untrustworthy.
 *
 * Drinks are standardized (fixed price), so they're never scraped.
 *
 * Output: data/panel-snapshots/<date>.json
 *
 * Usage:
 *   ANTHROPIC_API_KEY not required (no AI; pure string match).
 *   node scripts/check-panel.js
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const dataDir = path.join(__dirname, '..', 'data');
const snapDir = path.join(dataDir, 'panel-snapshots');
if (!fs.existsSync(snapDir)) fs.mkdirSync(snapDir, { recursive: true });

const panelDoc = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel.json'), 'utf8'));
const panel = panelDoc.panel;
const SODA = panelDoc.meta.sodaPrice;
const TAX = panelDoc.meta.tax;

// most recent panel snapshot = fallback for carry-forward
const prior = fs.readdirSync(snapDir).filter(f => f.endsWith('.json')).sort().reverse();
const lastSnap = prior.length ? JSON.parse(fs.readFileSync(path.join(snapDir, prior[0]), 'utf8')) : null;

function fetchPage(url, timeout = 12000, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('TOO_MANY_REDIRECTS'));
    let mod; try { mod = url.startsWith('https') ? https : http; } catch { return reject(new Error('BAD_URL')); }
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FamilyDinnerBot/1.0)' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        let loc = res.headers.location; if (loc.startsWith('/')) { const u = new URL(url); loc = u.origin + loc; }
        return fetchPage(loc, timeout, redirects + 1).then(resolve).catch(reject);
      }
      if (res.statusCode === 404 || res.statusCode === 410) return reject(new Error('GONE_' + res.statusCode));
      if (res.statusCode !== 200) return reject(new Error('HTTP_' + res.statusCode));
      let b = ''; res.on('data', c => b += c); res.on('end', () => resolve(b));
    });
    req.on('error', e => reject(new Error(e.code || e.message)));
    req.setTimeout(timeout, () => { req.destroy(); reject(new Error('TIMEOUT')); });
  });
}

function normalize(s) {
  return s.toLowerCase()
    .replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&#36;/g, '$').replace(/&#8211;/g, '-').replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

// Units that follow a NUMBER but mean it's a quantity, not a price.
const UNIT_AFTER = /^\s*(oz|ozs|g|gr|gram|grams|ml|l|lb|lbs|pc|pcs|piece|pieces|%|"|''|cal|kcal|min|mins|hr|inch|in|ct|count|each|people|person)\b/i;

// Find the pinned item's current price: locate the SAME line text, then read
// the first PROPER price token after it ($-prefixed or 2-decimal), skipping
// quantity numbers (e.g. "24 oz", "6 pcs", "200g"). Returns number or null.
// `baseline` lets us reject mis-reads: a real price won't 2x or halve overnight,
// so anything outside [0.5x, 2x] of the known price is treated as a mis-read.
function priceForPinnedItem(menuNorm, itemText, baseline) {
  const item = normalize(itemText);
  if (item.length < 3) return null;
  const idx = menuNorm.indexOf(item);
  if (idx === -1) return null;
  const window = menuNorm.slice(idx + item.length, idx + item.length + 80);
  // Candidate price tokens: $-prefixed (int or decimal) OR a bare 2-decimal.
  const re = /\$\s?(\d{1,3}(?:\.\d{2})?)|(?<!\d)(\d{1,3}\.\d{2})(?!\d)/g;
  let m;
  while ((m = re.exec(window)) !== null) {
    const raw = m[1] || m[2];
    const after = window.slice(m.index + m[0].length);
    if (UNIT_AFTER.test(after)) continue;           // it's a quantity, not a price
    const val = parseFloat(raw);
    if (!isFinite(val) || val <= 0 || val > 300) continue;
    if (baseline && (val < baseline * 0.5 || val > baseline * 2)) continue; // implausible jump = mis-read
    return val;
  }
  return null;
}

function familyTotal(a, k, ap) {
  const sub = a * 2 + k * 2 + ap + SODA * 2;
  return Math.round(sub * TAX * 100) / 100;
}

async function main() {
  const today = new Date().toISOString().split('T')[0];
  console.log(`Panel re-check for ${today} — ${Object.keys(panel).length} restaurants\n`);
  const snapshot = { date: today, sodaPrice: SODA, tax: TAX, restaurants: {} };
  let verifiedItems = 0, carriedItems = 0, fullyVerified = 0;

  for (const [id, r] of Object.entries(panel)) {
    process.stdout.write(`${r.name}... `);
    let menuNorm = null, reachable = false;
    try { menuNorm = normalize(await fetchPage(r.menuUrl)); reachable = menuNorm.length > 200; }
    catch (e) { process.stdout.write(`(unreachable: ${e.message}) `); }

    const comps = {};
    let allVerified = true;
    for (const key of ['adultEntree', 'kidMeal', 'appetizer']) {
      const pin = r.pinned[key];
      const priorPrice = lastSnap?.restaurants?.[id]?.[key]?.price ?? pin.price;
      let price = null;
      if (reachable) price = priceForPinnedItem(menuNorm, pin.item, priorPrice);
      if (price != null) {
        comps[key] = { item: pin.item, price, status: 'verified' };
        verifiedItems++;
      } else {
        comps[key] = { item: pin.item, price: priorPrice, status: 'carried' };
        carriedItems++; allVerified = false;
      }
    }
    // drinks always standardized
    comps.drinks = { item: r.pinned.drinks.item, price: SODA, status: 'standardized' };

    const total = familyTotal(comps.adultEntree.price, comps.kidMeal.price, comps.appetizer.price);
    snapshot.restaurants[id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, total, fullyVerified: allVerified, ...comps };
    if (allVerified) fullyVerified++;
    console.log(allVerified ? `verified $${total}` : `partial $${total}`);
    await new Promise(res => setTimeout(res, 300));
  }

  const outPath = path.join(snapDir, `${today}.json`);
  fs.writeFileSync(outPath, JSON.stringify(snapshot, null, 2));
  console.log(`\n────────────────────────────`);
  console.log(`Items verified this cycle: ${verifiedItems} | carried forward: ${carriedItems}`);
  console.log(`Fully-verified restaurants: ${fullyVerified}/${Object.keys(panel).length}`);
  console.log(`Wrote ${outPath}`);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
