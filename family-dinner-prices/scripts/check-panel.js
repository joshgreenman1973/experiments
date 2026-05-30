#!/usr/bin/env node
/**
 * Monthly re-check for the FAMILY-BILL panel (data/panel.json).
 *
 * The tracked number is a real family-of-four dinner bill:
 *   (2 x adult entree + 2 x kid portion + 2 x beverage) x (1 + tax + tip)
 * Beverages are standardized citywide (menus rarely list soda prices).
 *
 * Each month we re-fetch the menu and re-price the SAME two pinned items
 * (adult entree, kid portion) by deterministic string match — no AI. If a
 * pinned line is gone/unreadable, we carry its last price forward and flag it
 * rather than substituting a different dish.
 *   - Winsorize-and-flag: an item move beyond +/-100% is clipped + flagged.
 *   - Freshness: capture Last-Modified/ETag; flag pages unchanged since baseline.
 *
 * Output: data/panel-snapshots/<date>.json
 * Usage: node scripts/check-panel.js
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const dataDir = path.join(__dirname, '..', 'data');
const snapDir = path.join(dataDir, 'panel-snapshots');
if (!fs.existsSync(snapDir)) fs.mkdirSync(snapDir, { recursive: true });

const doc = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel.json'), 'utf8'));
const panel = doc.panel;
const BEV = doc.meta.beveragePrice, TAX = doc.meta.tax, TIP = doc.meta.tip;
const bill = (a, k) => Math.round((2 * a + 2 * k + 2 * BEV) * (1 + TAX + TIP) * 100) / 100;

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
      let b = ''; res.on('data', c => b += c); res.on('end', () => resolve({ body: b, headers: res.headers }));
    });
    req.on('error', e => reject(new Error(e.code || e.message)));
    req.setTimeout(timeout, () => { req.destroy(); reject(new Error('TIMEOUT')); });
  });
}
function normalize(s) {
  return s.toLowerCase().replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#36;/g, '$').replace(/&#8211;/g, '-').replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ').trim();
}
const UNIT_AFTER = /^\s*(oz|ozs|g|gr|gram|grams|ml|l|lb|lbs|pc|pcs|piece|pieces|%|"|''|cal|kcal|min|mins|hr|inch|in|ct|count|each|people|person)\b/i;
function priceFor(menuNorm, itemText, baseline) {
  const item = normalize(itemText); if (item.length < 4) return null;
  const idx = menuNorm.indexOf(item); if (idx === -1) return null;
  const w = menuNorm.slice(idx + item.length, idx + item.length + 80);
  const re = /\$\s?(\d{1,3}(?:\.\d{2})?)|(?<!\d)(\d{1,3}\.\d{2})(?!\d)/g; let m;
  while ((m = re.exec(w)) !== null) {
    const raw = m[1] || m[2]; if (UNIT_AFTER.test(w.slice(m.index + m[0].length))) continue;
    const val = parseFloat(raw); if (!isFinite(val) || val <= 0 || val > 300) continue;
    if (baseline && (val < baseline * 0.5 || val > baseline * 2)) continue; // implausible = mis-read
    return val;
  }
  return null;
}

async function main() {
  const today = new Date().toISOString().split('T')[0];
  const ids = Object.keys(panel);
  console.log(`Family-bill re-check for ${today} — ${ids.length} restaurants\n`);
  const snap = { date: today, beveragePrice: BEV, tax: TAX, tip: TIP, restaurants: {} };
  let priced = 0, carried = 0, winsor = 0, stale = 0;

  for (const id of ids) {
    const r = panel[id];
    process.stdout.write(`${r.name}... `);
    let menu = null, headers = {}, ok = false;
    try { const res = await fetchPage(r.menuUrl); menu = normalize(res.body); headers = res.headers; ok = menu.length > 200; }
    catch (e) { process.stdout.write(`(unreachable: ${e.message}) `); }

    const pieces = {};
    for (const key of ['adultEntree', 'kidPortion']) {
      const pin = r[key];
      const priorPrice = lastSnap?.restaurants?.[id]?.[key]?.price ?? pin.base;
      let price = ok ? priceFor(menu, pin.item, priorPrice) : null;
      let status = 'verified';
      if (price == null) { price = priorPrice; status = 'carried'; carried++; }
      else {
        let rel = price / pin.base;
        if (rel < 0.5) { price = pin.base * 0.5; status = 'winsorized'; winsor++; }
        else if (rel > 2) { price = pin.base * 2; status = 'winsorized'; winsor++; }
        else priced++;
      }
      pieces[key] = { item: pin.item, base: pin.base, price: Math.round(price * 100) / 100, status };
    }

    const lm = headers['last-modified'] || null, et = headers['etag'] || null;
    const bLm = r.baselineFreshness?.lastModified || null, bEt = r.baselineFreshness?.etag || null;
    let pageChanged = null;
    if (ok && (lm || et)) pageChanged = !((lm && bLm && lm === bLm) || (et && bEt && et === bEt));
    if (pageChanged === false) stale++;

    const total = bill(pieces.adultEntree.price, pieces.kidPortion.price);
    snap.restaurants[id] = {
      name: r.name, borough: r.borough, cuisine: r.cuisine, platform: r.platform || null,
      adultEntree: pieces.adultEntree, kidPortion: pieces.kidPortion, beveragePrice: BEV, bill: total,
      observed: ['adultEntree', 'kidPortion'].filter(k => pieces[k].status !== 'carried').length,
      freshness: { lastModified: lm, etag: et }, pageChanged,
    };
    console.log(`$${total}${pieces.adultEntree.status === 'carried' || pieces.kidPortion.status === 'carried' ? ' (partial)' : ''}`);
    await new Promise(r => setTimeout(r, 250));
  }
  fs.writeFileSync(path.join(snapDir, `${today}.json`), JSON.stringify(snap, null, 2));
  console.log(`\n────────────────────────────`);
  console.log(`Items priced: ${priced} | carried: ${carried} | winsorized: ${winsor} | pages unchanged: ${stale}/${ids.length}`);
  console.log(`Wrote ${path.join('data/panel-snapshots', today + '.json')}`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
