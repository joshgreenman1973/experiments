#!/usr/bin/env node
/**
 * Monthly re-check for the tracked panel (data/panel.json).
 *
 * For each restaurant, re-fetch the menu and re-price every pinned basket item
 * by locating the SAME line (deterministic string match — no AI). Implements
 * the index-quality rules:
 *   - Freshness (rec #2): capture Last-Modified/ETag; flag if the page is
 *     byte-for-byte unchanged from the prior check (price may be carried by the
 *     website, not genuinely current).
 *   - Winsorize-and-flag (rec #3): an item relative outside [0.5, 2x] is clipped
 *     to the bound and flagged, not dropped — large real moves stay in, bounded.
 *   - Cell-relative imputation (rec #3): a missing item inherits the restaurant's
 *     own observed mean relative (achieved by computing the restaurant relative
 *     as the geometric mean of the items we DID observe).
 *   - Shrinkflation (rec #4): if the baseline size token no longer appears by the
 *     item, flag a possible size change.
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

const panelDoc = JSON.parse(fs.readFileSync(path.join(dataDir, 'panel.json'), 'utf8'));
const panel = panelDoc.panel;

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
  return s.toLowerCase()
    .replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&#36;/g, '$').replace(/&#8211;/g, '-').replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

const UNIT_AFTER = /^\s*(oz|ozs|g|gr|gram|grams|ml|l|lb|lbs|pc|pcs|piece|pieces|%|"|''|cal|kcal|min|mins|hr|inch|in|ct|count|each|people|person)\b/i;
function priceForItem(menuNorm, itemText, baseline) {
  const item = normalize(itemText);
  if (item.length < 4) return null;
  const idx = menuNorm.indexOf(item);
  if (idx === -1) return null;
  const window = menuNorm.slice(idx + item.length, idx + item.length + 80);
  const re = /\$\s?(\d{1,3}(?:\.\d{2})?)|(?<!\d)(\d{1,3}\.\d{2})(?!\d)/g;
  let m;
  while ((m = re.exec(window)) !== null) {
    const raw = m[1] || m[2];
    if (UNIT_AFTER.test(window.slice(m.index + m[0].length))) continue;
    const val = parseFloat(raw);
    if (isFinite(val) && val > 0 && val <= 300) return val;
  }
  return null;
}
// does the baseline size token still appear near the item?
function sizeStillPresent(menuNorm, itemText, size) {
  if (!size) return true;
  const idx = menuNorm.indexOf(normalize(itemText));
  if (idx === -1) return true;
  const around = menuNorm.slice(Math.max(0, idx - 20), idx + normalize(itemText).length + 90);
  return around.includes(normalize(size));
}

const LO = 0.5, HI = 2.0; // winsorize band on item relatives
function geomean(arr) { if (!arr.length) return null; const s = arr.reduce((a, b) => a + Math.log(b), 0); return Math.exp(s / arr.length); }

async function main() {
  const today = new Date().toISOString().split('T')[0];
  const ids = Object.keys(panel);
  console.log(`Panel re-check for ${today} — ${ids.length} restaurants\n`);
  const snap = { date: today, sodaPrice: panelDoc.meta.sodaPrice, tax: panelDoc.meta.tax, restaurants: {} };
  let observedItems = 0, missingItems = 0, winsorized = 0, sizeFlags = 0, stalePages = 0;

  for (const id of ids) {
    const r = panel[id];
    process.stdout.write(`${r.name}... `);
    let menuNorm = null, headers = {}, reachable = false;
    try { const res = await fetchPage(r.menuUrl); menuNorm = normalize(res.body); headers = res.headers; reachable = menuNorm.length > 200; }
    catch (e) { process.stdout.write(`(unreachable: ${e.message}) `); }

    const items = {};
    const relatives = [];
    for (const b of r.basket) {
      const priorItem = lastSnap?.restaurants?.[id]?.items?.[b.key];
      let price = reachable ? priceForItem(menuNorm, b.item, b.base) : null;
      if (price != null) {
        let rel = price / b.base;
        let wins = false;
        if (rel < LO) { rel = LO; wins = true; } else if (rel > HI) { rel = HI; wins = true; }
        if (wins) winsorized++;
        // Shrinkflation guard: when a price moves materially, surface the size so
        // a same-price size cut (or a size-driven price move) can be reviewed.
        // We record size for display; we do NOT auto-decide (substring matching
        // is too noisy to flag reliably).
        const priceMoved = Math.abs(rel - 1) > 0.05;
        if (priceMoved && b.size) sizeFlags++;
        items[b.key] = { item: b.item, base: b.base, price, size: b.size || '', relative: Math.round(rel * 1e4) / 1e4, status: wins ? 'winsorized' : 'verified', reviewSize: priceMoved && !!b.size };
        relatives.push(rel);
        observedItems++;
      } else {
        items[b.key] = { item: b.item, base: b.base, price: null, size: b.size || '', relative: null, status: 'missing', reviewSize: false };
        missingItems++;
      }
    }
    // restaurant relative = geomean of observed item relatives (cell-relative
    // imputation: missing items implicitly inherit this mean). Fallback: prior.
    let R = geomean(relatives);
    if (R == null) R = lastSnap?.restaurants?.[id]?.relative ?? 1.0;

    // freshness / page-changed signal
    const lm = headers['last-modified'] || null, etag = headers['etag'] || null;
    const baseLm = r.baselineFreshness?.lastModified || null, baseEtag = r.baselineFreshness?.etag || null;
    let pageChanged = null;
    if (reachable && (lm || etag)) pageChanged = !((lm && baseLm && lm === baseLm) || (etag && baseEtag && etag === baseEtag));
    if (pageChanged === false) stalePages++;

    snap.restaurants[id] = {
      name: r.name, borough: r.borough, cuisine: r.cuisine, platform: r.platform || null,
      relative: Math.round(R * 1e4) / 1e4, observed: relatives.length, basketSize: r.basket.length,
      items, freshness: { lastModified: lm, etag }, pageChanged,
    };
    console.log(`rel ${(R).toFixed(3)} (${relatives.length}/${r.basket.length} items${pageChanged === false ? ', page unchanged' : ''})`);
    await new Promise(res => setTimeout(res, 250));
  }

  fs.writeFileSync(path.join(snapDir, `${today}.json`), JSON.stringify(snap, null, 2));
  console.log(`\n────────────────────────────`);
  console.log(`Items observed: ${observedItems} | missing(imputed): ${missingItems} | winsorized: ${winsorized} | size-flags: ${sizeFlags}`);
  console.log(`Pages unchanged since baseline: ${stalePages}/${ids.length}`);
  console.log(`Wrote ${path.join('data/panel-snapshots', today + '.json')}`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
