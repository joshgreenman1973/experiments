#!/usr/bin/env node
/**
 * Monthly re-check for the cuisine-aware FAMILY-BILL panel (data/panel.json).
 *
 * Each restaurant has a mealType and a list of components (role, item, base, qty):
 *   pizza = 1 large pizza; chinese = 2 dishes + egg rolls; standard = 2 adult + 2 kid.
 * Bill = (sum of component price x qty + 2 drinks @ $2.50) x (1 + tax + tip).
 *
 * We re-price every pinned component by deterministic string match (no AI).
 * Problem handling (prevents stale-price distortion):
 *   - A restaurant counts only if ALL its components re-price cleanly.
 *   - Dropped on 404/410, on 2 consecutive misses, or if it can't fully re-price
 *     at baseline (bad pin). Transient network errors are retried, not dropped.
 *   - Item move beyond +/-100% is treated as a mis-read (winsorized + flagged).
 *
 * Output: data/panel-snapshots/<date>.json   (persists misses/drops to panel.json)
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
const BEV = doc.meta.beveragePrice, BEVQTY = doc.meta.beverageQty, TAX = doc.meta.tax, TIP = doc.meta.tip;
const DROP_THRESHOLD = 2;
const billOf = comps => Math.round((comps.reduce((s, c) => s + c.price * c.qty, 0) + BEV * BEVQTY) * (1 + TAX + TIP) * 100) / 100;

const prior = fs.readdirSync(snapDir).filter(f => f.endsWith('.json')).sort().reverse();
const lastSnap = prior.length ? JSON.parse(fs.readFileSync(path.join(snapDir, prior[0]), 'utf8')) : null;
const isBaseline = !lastSnap;

function fetchOnce(url, timeout = 12000, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('TOO_MANY_REDIRECTS'));
    let mod; try { mod = url.startsWith('https') ? https : http; } catch { return reject(new Error('BAD_URL')); }
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FamilyDinnerBot/1.0)' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) { let loc = res.headers.location; if (loc.startsWith('/')) { const u = new URL(url); loc = u.origin + loc; } return fetchOnce(loc, timeout, redirects + 1).then(resolve).catch(reject); }
      if (res.statusCode === 404 || res.statusCode === 410) return reject(new Error('GONE_' + res.statusCode));
      if (res.statusCode !== 200) return reject(new Error('HTTP_' + res.statusCode));
      let b = ''; res.on('data', c => b += c); res.on('end', () => resolve({ body: b, headers: res.headers }));
    });
    req.on('error', e => reject(new Error(e.code || e.message)));
    req.setTimeout(timeout, () => { req.destroy(); reject(new Error('TIMEOUT')); });
  });
}
async function fetchPage(url) {
  let lastErr = '', gone = false;
  for (let a = 0; a < 3; a++) {
    try { return { ...(await fetchOnce(url)), gone: false, err: '' }; }
    catch (e) { lastErr = e.message; if (String(e.message).startsWith('GONE_')) { gone = true; break; } if (/^HTTP_4\d\d/.test(e.message)) break; await new Promise(r => setTimeout(r, 1200 * (a + 1))); }
  }
  return { body: null, headers: {}, gone, err: lastErr };
}
function normalize(s) {
  return s.toLowerCase().replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&#36;/g, '$').replace(/&#8211;/g, '-').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
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
  console.log(`Cuisine-aware re-check for ${today} — ${ids.length} active${isBaseline ? ' (baseline)' : ''}\n`);
  const snap = { date: today, beveragePrice: BEV, beverageQty: BEVQTY, tax: TAX, tip: TIP, restaurants: {}, dropped: [], missed: [] };
  let priced = 0, winsor = 0, stale = 0;

  for (const id of ids) {
    const r = panel[id];
    process.stdout.write(`${r.name} [${r.mealType}]... `);
    const res = await fetchPage(r.menuUrl);
    if (res.gone) { r.status = 'dropped'; r.droppedReason = 'page gone (404/410)'; r.droppedDate = today; snap.dropped.push(r.name); console.log('DROPPED (gone)'); continue; }
    const menu = res.body ? normalize(res.body) : null;
    const reachable = menu && menu.length > 200;
    if (res.err) process.stdout.write(`(${res.err}) `);

    const comps = []; const missing = [];
    for (const c of r.components) {
      const prevC = lastSnap?.restaurants?.[id]?.components?.find(x => x.role === c.role && x.item === c.item);
      const prevPrice = prevC?.price ?? c.base;
      let price = reachable ? priceFor(menu, c.item, prevPrice) : null;
      let status = 'verified';
      if (price == null) { missing.push(c.role); comps.push({ role: c.role, item: c.item, base: c.base, qty: c.qty, price: null, status: 'missing' }); }
      else { let rel = price / c.base; if (rel < 0.5 || rel > 2) { status = 'winsorized'; price = rel < 0.5 ? c.base * 0.5 : c.base * 2; winsor++; } comps.push({ role: c.role, item: c.item, base: c.base, qty: c.qty, price: Math.round(price * 100) / 100, status }); }
    }

    if (missing.length) {
      r.misses = (r.misses || 0) + 1;
      const drop = isBaseline || r.misses >= DROP_THRESHOLD;
      if (drop) { r.status = 'dropped'; r.droppedReason = `could not re-price ${missing.join(', ')}${isBaseline ? ' at baseline' : ` for ${r.misses} checks`}`; r.droppedDate = today; snap.dropped.push(r.name); console.log(`DROPPED (${missing.join(',')})`); }
      else { snap.missed.push(r.name); console.log(`missed (${missing.join(',')}), excluded [strike ${r.misses}]`); }
      continue;
    }

    r.misses = 0;
    const lm = res.headers['last-modified'] || null, et = res.headers['etag'] || null;
    const bLm = r.baselineFreshness?.lastModified || null, bEt = r.baselineFreshness?.etag || null;
    let pageChanged = null; if (reachable && (lm || et)) pageChanged = !((lm && bLm && lm === bLm) || (et && bEt && et === bEt));
    if (pageChanged === false) stale++;
    const total = billOf(comps);
    snap.restaurants[id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, platform: r.platform || null, mealType: r.mealType, components: comps, beveragePrice: BEV, beverageQty: BEVQTY, bill: total, freshness: { lastModified: lm, etag: et }, pageChanged };
    priced++; console.log(`$${total}`);
    await new Promise(r => setTimeout(r, 250));
  }

  doc.meta.count = Object.values(panel).filter(r => r.status !== 'dropped').length;
  fs.writeFileSync(docPath, JSON.stringify(doc, null, 2));
  fs.writeFileSync(path.join(snapDir, `${today}.json`), JSON.stringify(snap, null, 2));
  console.log(`\n────────────────────────────`);
  console.log(`Priced: ${priced} | missed: ${snap.missed.length} | dropped: ${snap.dropped.length} | winsorized: ${winsor} | unchanged pages: ${stale}`);
  if (snap.dropped.length) console.log(`Dropped: ${snap.dropped.join(', ')}`);
  console.log(`Active panel now: ${doc.meta.count}`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
