#!/usr/bin/env node
/**
 * Monthly re-check for the FAMILY-BILL panel (data/panel.json).
 *
 * Bill = (2 adult entree + 2 kid portion + 2 beverage) x (1 + tax + tip).
 *
 * PROBLEM HANDLING (prevents stale-price distortion):
 *   - A restaurant only contributes a bill in a month where BOTH pinned dishes
 *     re-price cleanly. A miss is NOT carried forward into the number.
 *   - A restaurant is DROPPED from the panel (status='dropped', excluded forever
 *     unless re-pinned) when:
 *       * its page returns 404/410 (closed/gone), OR
 *       * it cannot be fully re-priced for 2 consecutive checks, OR
 *       * it cannot be fully re-priced at BASELINE (a bad/seasonal pin).
 *   - Transient one-month misses are excluded that month but retried next month.
 *   - Mis-read guard: an item move beyond +/-100% is treated as a scrape error
 *     (excluded), not a real price.
 *   - Freshness: capture Last-Modified/ETag; flag pages unchanged since baseline.
 *
 * The script PERSISTS miss counts / drops back into panel.json.
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

const docPath = path.join(dataDir, 'panel.json');
const doc = JSON.parse(fs.readFileSync(docPath, 'utf8'));
const panel = doc.panel;
const BEV = doc.meta.beveragePrice, TAX = doc.meta.tax, TIP = doc.meta.tip;
const DROP_THRESHOLD = 2;
const bill = (a, k) => Math.round((2 * a + 2 * k + 2 * BEV) * (1 + TAX + TIP) * 100) / 100;

const prior = fs.readdirSync(snapDir).filter(f => f.endsWith('.json')).sort().reverse();
const lastSnap = prior.length ? JSON.parse(fs.readFileSync(path.join(snapDir, prior[0]), 'utf8')) : null;
const isBaseline = !lastSnap;

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
    if (baseline && (val < baseline * 0.5 || val > baseline * 2)) continue;
    return val;
  }
  return null;
}

async function main() {
  const today = new Date().toISOString().split('T')[0];
  const ids = Object.keys(panel).filter(id => panel[id].status !== 'dropped');
  console.log(`Family-bill re-check for ${today} — ${ids.length} active restaurants${isBaseline ? ' (baseline)' : ''}\n`);
  const snap = { date: today, beveragePrice: BEV, tax: TAX, tip: TIP, restaurants: {}, dropped: [], missed: [] };
  let priced = 0, winsor = 0, stale = 0;

  for (const id of ids) {
    const r = panel[id];
    process.stdout.write(`${r.name}... `);
    let menu = null, headers = {}, gone = false, reachable = false;
    try { const res = await fetchPage(r.menuUrl); menu = normalize(res.body); headers = res.headers; reachable = menu.length > 200; }
    catch (e) { if (String(e.message).startsWith('GONE_')) gone = true; process.stdout.write(`(${e.message}) `); }

    if (gone) { r.status = 'dropped'; r.droppedReason = 'page gone (404/410)'; r.droppedDate = today; snap.dropped.push(r.name); console.log('DROPPED (gone)'); continue; }

    const pieces = {}; let missing = [];
    for (const key of ['adultEntree', 'kidPortion']) {
      const pin = r[key];
      const prevPrice = lastSnap?.restaurants?.[id]?.[key]?.price ?? pin.base;
      let price = reachable ? priceFor(menu, pin.item, prevPrice) : null;
      let status = 'verified';
      if (price == null) { missing.push(key); }
      else { let rel = price / pin.base; if (rel < 0.5 || rel > 2) { status = 'winsorized'; price = rel < 0.5 ? pin.base * 0.5 : pin.base * 2; winsor++; } }
      pieces[key] = { item: pin.item, base: pin.base, price: price == null ? null : Math.round(price * 100) / 100, status: price == null ? 'missing' : status };
    }

    if (missing.length) {
      r.misses = (r.misses || 0) + 1;
      const drop = isBaseline || r.misses >= DROP_THRESHOLD;
      if (drop) { r.status = 'dropped'; r.droppedReason = `could not re-price ${missing.join(' & ')}${isBaseline ? ' at baseline (bad/seasonal pin)' : ` for ${r.misses} checks`}`; r.droppedDate = today; snap.dropped.push(r.name); console.log(`DROPPED (${r.droppedReason})`); }
      else { snap.missed.push(r.name); console.log(`missed (${missing.join(',')}), excluded this month [strike ${r.misses}]`); }
      continue;
    }

    // fully priced
    r.misses = 0;
    const lm = headers['last-modified'] || null, et = headers['etag'] || null;
    const bLm = r.baselineFreshness?.lastModified || null, bEt = r.baselineFreshness?.etag || null;
    let pageChanged = null;
    if (reachable && (lm || et)) pageChanged = !((lm && bLm && lm === bLm) || (et && bEt && et === bEt));
    if (pageChanged === false) stale++;
    const total = bill(pieces.adultEntree.price, pieces.kidPortion.price);
    snap.restaurants[id] = {
      name: r.name, borough: r.borough, cuisine: r.cuisine, platform: r.platform || null,
      adultEntree: pieces.adultEntree, kidPortion: pieces.kidPortion, beveragePrice: BEV, bill: total,
      freshness: { lastModified: lm, etag: et }, pageChanged,
    };
    priced++;
    console.log(`$${total}`);
    await new Promise(r => setTimeout(r, 250));
  }

  // persist drops/misses + active count
  doc.meta.count = Object.values(panel).filter(r => r.status !== 'dropped').length;
  fs.writeFileSync(docPath, JSON.stringify(doc, null, 2));
  fs.writeFileSync(path.join(snapDir, `${today}.json`), JSON.stringify(snap, null, 2));

  console.log(`\n────────────────────────────`);
  console.log(`Priced: ${priced} | missed (excluded): ${snap.missed.length} | dropped: ${snap.dropped.length} | winsorized: ${winsor} | pages unchanged: ${stale}`);
  if (snap.dropped.length) console.log(`Dropped: ${snap.dropped.join(', ')}`);
  console.log(`Active panel now: ${doc.meta.count}`);
  console.log(`Wrote ${path.join('data/panel-snapshots', today + '.json')}`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
