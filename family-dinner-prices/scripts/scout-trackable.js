#!/usr/bin/env node
/**
 * Scouts the TRUE trackable universe.
 *
 * For every active restaurant with a menuUrl: fetch (capturing Last-Modified /
 * ETag freshness headers and the hosting platform), and if the static HTML
 * actually contains prices, ask Claude Haiku to extract a GENEROUS list of
 * clearly-named, clearly-priced menu items — each with any size/quantity
 * descriptor (for shrinkflation tracking). Then test how many of those items
 * the DETERMINISTIC monthly matcher can independently re-find and price.
 *
 * A restaurant is "trackable" if the deterministic matcher can lock >=N of its
 * named items. We report the count at several thresholds plus platform/borough
 * spread so we know the real ceiling and how to grow it.
 *
 * Output: data/trackable-scan.json
 *
 * Usage:
 *   ANTHROPIC_API_KEY=$(security find-generic-password -s "ANTHROPIC_API_KEY" -w) \
 *     node scripts/scout-trackable.js
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const dataDir = path.join(__dirname, '..', 'data');
const API_KEY = process.env.ANTHROPIC_API_KEY;
if (!API_KEY) { console.error('ANTHROPIC_API_KEY required'); process.exit(1); }

const registry = JSON.parse(fs.readFileSync(path.join(dataDir, 'restaurants.json'), 'utf8'));
const active = registry.filter(r => r.status !== 'closed' && r.menuUrl);

// fetch returning { body, headers, finalUrl }
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
      let b = ''; res.on('data', c => b += c); res.on('end', () => resolve({ body: b, headers: res.headers, finalUrl: url }));
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

function platformOf(url, html) {
  const u = url.toLowerCase(); const h = html.toLowerCase();
  if (h.includes('toasttab') || u.includes('toasttab')) return 'Toast';
  if (h.includes('squarespace')) return 'Squarespace';
  if (u.includes('square.site') || h.includes('square-marketplace')) return 'Square';
  if (h.includes('clover.com')) return 'Clover';
  if (h.includes('wix.com') || h.includes('wixsite')) return 'Wix';
  if (h.includes('bentobox')) return 'BentoBox';
  if (h.includes('wp-content') || h.includes('wordpress')) return 'WordPress';
  if (h.includes('godaddy') || h.includes('websitebuilder')) return 'GoDaddy';
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return 'other'; }
}

const UNIT_AFTER = /^\s*(oz|ozs|g|gr|gram|grams|ml|l|lb|lbs|pc|pcs|piece|pieces|%|"|''|cal|kcal|min|mins|hr|inch|in|ct|count|each|people|person)\b/i;
function priceForItem(menuNorm, itemText) {
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
    if (isFinite(val) && val >= 1 && val <= 200) return val;
  }
  return null;
}

function callClaude(prompt) {
  const body = JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 900, messages: [{ role: 'user', content: prompt }] });
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: 'api.anthropic.com', path: '/v1/messages', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'Content-Length': Buffer.byteLength(body) },
    }, (res) => { let d = ''; res.on('data', c => d += c); res.on('end', () => {
      try { const p = JSON.parse(d); if (p.error) return reject(new Error(p.error.message)); resolve(p.content?.[0]?.text || ''); } catch (e) { reject(e); }
    }); });
    req.on('error', reject); req.write(body); req.end();
  });
}

async function extractItems(r, menuText) {
  const prompt = `Restaurant "${r.name}" (${r.cuisine}) in ${r.borough}, NYC. Menu text (dine-in):
---
${menuText.slice(0, 11000)}
---
List up to 12 of the most ordered-looking, clearly-named menu items that have a SINGLE clear price. For each return:
- "item": the exact item name as printed (verbatim, so it can be found again next month). A specific dish, NOT a category header.
- "price": number only.
- "size": any portion/quantity descriptor in or next to the name (e.g. "24 oz", "6 pcs", "Large", "Whole"), or "" if none.
Skip price ranges, "market price", category headers, and add-on modifiers. Prefer staple items a family would order (entrees, mains, sides, kid options).
Respond ONLY with JSON: {"items":[{"item":"...","price":0,"size":""}, ...]}`;
  const resp = await callClaude(prompt);
  const m = resp.match(/\{[\s\S]*\}/);
  if (!m) return [];
  try { const o = JSON.parse(m[0]); return Array.isArray(o.items) ? o.items : []; } catch { return []; }
}

async function main() {
  console.log(`Scouting ${active.length} restaurants with a menuUrl\n`);
  const out = {};
  let i = 0; const limit = 8;
  const stats = { readable: 0, unreadable: 0, unreachable: 0 };

  async function worker() {
    while (i < active.length) {
      const r = active[i++];
      try {
        const { body, headers } = await fetchPage(r.menuUrl);
        const menuNorm = normalize(body);
        const platform = platformOf(r.menuUrl, body);
        const freshness = { lastModified: headers['last-modified'] || null, etag: headers['etag'] || null };
        if (!/\$\s?\d/.test(menuNorm) || menuNorm.length < 200) {
          stats.unreadable++;
          out[r.id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, readable: false, platform, reason: 'no prices in static HTML' };
          continue;
        }
        stats.readable++;
        const items = await extractItems(r, menuNorm);
        await new Promise(res => setTimeout(res, 350));
        // Deterministic re-find test
        const locked = [];
        const seen = new Set();
        for (const it of items) {
          if (!it || typeof it.item !== 'string') continue;
          const key = it.item.trim().toLowerCase();
          if (seen.has(key)) continue; seen.add(key);
          const price = priceForItem(menuNorm, it.item);
          if (price != null) locked.push({ item: it.item.trim(), price, size: (it.size || '').toString().trim() });
        }
        out[r.id] = {
          name: r.name, borough: r.borough, cuisine: r.cuisine, neighborhood: r.neighborhood,
          menuUrl: r.menuUrl, platform, freshness, readable: true,
          extracted: items.length, locked: locked.length, items: locked,
        };
        console.log(`[${i}/${active.length}] ${r.name} — ${locked.length} items locked (${platform})`);
      } catch (e) {
        stats.unreachable++;
        out[r.id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, readable: false, reason: e.message };
      }
    }
  }
  await Promise.all(Array.from({ length: limit }, () => worker()));

  fs.writeFileSync(path.join(dataDir, 'trackable-scan.json'), JSON.stringify(out, null, 2));
  console.log(`\n────────────────────────────`);
  console.log(`Readable: ${stats.readable} | Unreadable: ${stats.unreadable} | Unreachable: ${stats.unreachable}`);
  for (const n of [3, 4, 5, 6]) {
    const c = Object.values(out).filter(v => v.readable && v.locked >= n).length;
    console.log(`Trackable with >=${n} locked items: ${c}`);
  }
  console.log(`Wrote data/trackable-scan.json`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
