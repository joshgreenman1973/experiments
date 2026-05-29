#!/usr/bin/env node
/**
 * One-time pinning pass for the tracked-panel rebuild.
 *
 * For every active restaurant with a menuUrl, fetch the menu page. If the
 * static HTML actually contains prices, ask Claude Haiku to extract the FOUR
 * meal components AND the exact menu-line text it used for each. Storing the
 * line text is what makes month-over-month tracking honest: next month we only
 * accept a new price if the SAME line is still on the menu.
 *
 * Output: data/panel-candidates.json — every restaurant we could read, with a
 * `clean` flag (all four components found). The tracked panel is selected from
 * the clean candidates.
 *
 * Usage:
 *   ANTHROPIC_API_KEY=$(security find-generic-password -s "ANTHROPIC_API_KEY" -w) \
 *     node scripts/pin-panel.js
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const baseDir = path.join(__dirname, '..');
const dataDir = path.join(baseDir, 'data');
const API_KEY = process.env.ANTHROPIC_API_KEY;
if (!API_KEY) { console.error('ANTHROPIC_API_KEY required'); process.exit(1); }

const registry = JSON.parse(fs.readFileSync(path.join(dataDir, 'restaurants.json'), 'utf8'));
const active = registry.filter(r => r.status !== 'closed' && r.menuUrl);

function fetchPage(url, timeout = 12000, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('TOO_MANY_REDIRECTS'));
    let mod; try { mod = url.startsWith('https') ? https : http; } catch { return reject(new Error('BAD_URL')); }
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FamilyDinnerBot/1.0)' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        let loc = res.headers.location;
        if (loc.startsWith('/')) { const u = new URL(url); loc = u.origin + loc; }
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

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&#36;/g, '$').replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function callClaude(prompt) {
  const body = JSON.stringify({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 500,
    messages: [{ role: 'user', content: prompt }],
  });
  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: 'api.anthropic.com', path: '/v1/messages', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'Content-Length': Buffer.byteLength(body) },
    }, (res) => {
      let d = ''; res.on('data', c => d += c); res.on('end', () => {
        try { const p = JSON.parse(d); if (p.error) return reject(new Error(p.error.message)); resolve(p.content?.[0]?.text || ''); }
        catch (e) { reject(e); }
      });
    });
    req.on('error', reject); req.write(body); req.end();
  });
}

async function pin(r, menuText) {
  const prompt = `You are pinning menu items for a price tracker. Restaurant: "${r.name}" (${r.cuisine}) in ${r.neighborhood}, ${r.borough}, NYC.

Menu text (dine-in, not delivery):
---
${menuText.slice(0, 9000)}
---

Pick FOUR specific menu items a family of four would order and report the EXACT item name as printed plus its dine-in price:
1. adultEntree — a typical adult dinner entree
2. kidMeal — a smaller/kid-sized portion (or the cheapest simple entree if no kids menu)
3. appetizer — one shared appetizer or side
4. drinks — a single soft drink / soda / can

Rules:
- "item" must be copied verbatim from the menu text so it can be found again next month. Pick a clearly-named single item, NOT a category header or a size-variant range.
- "price" is the number only (no $).
- If you cannot find a clear single item+price for a component, set that component to null.

Respond ONLY with JSON:
{"adultEntree":{"item":"...","price":0},"kidMeal":{"item":"...","price":0},"appetizer":{"item":"...","price":0},"drinks":{"item":"...","price":0},"confidence":"high|medium|low"}`;

  const resp = await callClaude(prompt);
  const m = resp.match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch { return null; }
}

function componentOk(c) {
  return c && typeof c.item === 'string' && c.item.trim().length >= 3 &&
         typeof c.price === 'number' && isFinite(c.price) && c.price > 0;
}

async function main() {
  console.log(`Pinning pass over ${active.length} active restaurants with a menuUrl\n`);
  const out = {};
  const stats = { noDollar: 0, unreachable: 0, extracted: 0, clean: 0 };
  let i = 0;
  const limit = 8;

  async function worker() {
    while (i < active.length) {
      const r = active[i++];
      const tag = `[${i}/${active.length}] ${r.name}`;
      try {
        const html = await fetchPage(r.menuUrl);
        const text = stripHtml(html);
        if (!/\$\s?\d/.test(text) || text.length < 200) {
          stats.noDollar++;
          out[r.id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, readable: false, reason: 'no prices in static HTML' };
          continue;
        }
        const pinned = await pin(r, text);
        await new Promise(res => setTimeout(res, 400));
        if (!pinned) {
          out[r.id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, readable: false, reason: 'extraction failed' };
          continue;
        }
        const comps = ['adultEntree', 'kidMeal', 'appetizer', 'drinks'];
        const clean = comps.every(k => componentOk(pinned[k]));
        stats.extracted++;
        if (clean) stats.clean++;
        out[r.id] = {
          name: r.name, borough: r.borough, cuisine: r.cuisine, neighborhood: r.neighborhood,
          menuUrl: r.menuUrl, readable: true, clean, confidence: pinned.confidence,
          pinned: { adultEntree: pinned.adultEntree, kidMeal: pinned.kidMeal, appetizer: pinned.appetizer, drinks: pinned.drinks },
        };
        console.log(`${tag} — ${clean ? 'CLEAN' : 'partial'} (${pinned.confidence})`);
      } catch (e) {
        stats.unreachable++;
        out[r.id] = { name: r.name, borough: r.borough, cuisine: r.cuisine, readable: false, reason: e.message };
      }
    }
  }

  await Promise.all(Array.from({ length: limit }, () => worker()));

  fs.writeFileSync(path.join(dataDir, 'panel-candidates.json'), JSON.stringify(out, null, 2));
  console.log(`\n──────────────────────────────`);
  console.log(`No prices in HTML: ${stats.noDollar} | Unreachable: ${stats.unreachable}`);
  console.log(`Extracted: ${stats.extracted} | CLEAN (all 4 pinned): ${stats.clean}`);
  console.log(`Wrote data/panel-candidates.json`);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
