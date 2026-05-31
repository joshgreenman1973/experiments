#!/usr/bin/env node
/**
 * Cuisine-aware re-pin. For each panel restaurant (data/familybill-input.json,
 * which carries the priced item basket), pick the items for a realistic family
 * order given the cuisine:
 *   - pizza   : one LARGE whole pizza
 *   - chinese : two different shared main dishes + one order of egg rolls
 *   - standard: one adult entree + one kid portion (kids'-menu item preferred)
 * One Haiku call per restaurant (concurrency + 429 retry). Deterministic guards
 * are applied later in build-panel.js.
 *
 * Output: data/meals-pinned.json
 * Usage: ANTHROPIC_API_KEY=... node scripts/pin-meals.js
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const dataDir = path.join(__dirname, '..', 'data');
const API_KEY = process.env.ANTHROPIC_API_KEY;
if (!API_KEY) { console.error('ANTHROPIC_API_KEY required'); process.exit(1); }
const input = JSON.parse(fs.readFileSync(path.join(dataDir, 'familybill-input.json'), 'utf8'));

const mealType = c => { c = (c || '').toLowerCase(); return /pizz/.test(c) ? 'pizza' : /chinese/.test(c) ? 'chinese' : 'standard'; };

function callClaude(prompt, tries = 0) {
  const body = JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 500, messages: [{ role: 'user', content: prompt }] });
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: 'api.anthropic.com', path: '/v1/messages', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'Content-Length': Buffer.byteLength(body) } },
      (res) => { let d = ''; res.on('data', c => d += c); res.on('end', () => {
        if (res.statusCode === 429 || res.statusCode >= 500) { if (tries >= 5) return reject(new Error('rate ' + res.statusCode)); return setTimeout(() => callClaude(prompt, tries + 1).then(resolve, reject), 1500 * (tries + 1)); }
        try { const p = JSON.parse(d); if (p.error) return reject(new Error(p.error.message)); resolve(p.content?.[0]?.text || ''); } catch (e) { reject(e); }
      }); });
    req.on('error', e => { if (tries < 5) return setTimeout(() => callClaude(prompt, tries + 1).then(resolve, reject), 1500 * (tries + 1)); reject(e); });
    req.write(body); req.end();
  });
}
const json = t => { const m = (t || '').match(/\{[\s\S]*\}/); if (!m) return null; try { return JSON.parse(m[0]); } catch { return null; } };

function prompt(r, type) {
  const menu = r.items.map(it => `- ${it.item} — $${it.price}`).join('\n');
  const head = `Restaurant "${r.name}" (${r.cuisine}, ${r.borough}). Priced menu items:\n${menu}\n\nChoose ONLY from the list above; copy item text + price verbatim.\n`;
  if (type === 'pizza') return head + `Pick ONE large whole pizza a family would share — prefer a plain/cheese LARGE pie; if no size is shown, the standard cheese/margherita pizza. It must be a whole pizza, NOT a slice or personal size, NOT a topping add-on.\nRespond ONLY JSON: {"largePizza":{"item":"...","price":0}}`;
  if (type === 'chinese') return head + `Pick TWO DIFFERENT shared main dishes (entrees like chicken/beef/shrimp/pork/tofu/vegetable dishes, lo mein, or a fried-rice main — NOT soups, NOT appetizers, NOT sides) and ONE order of egg rolls (or spring rolls).\nRespond ONLY JSON: {"dish1":{"item":"...","price":0},"dish2":{"item":"...","price":0},"eggRolls":{"item":"...","price":0}}`;
  return head + `Pick ONE adult dinner entree (a normal shareable main, $6–$32, not a party/catering size, not a drink/dessert/alcohol) and ONE kid portion — PREFER an item from a kids'/children's menu; otherwise a small, cheap single dish a child would eat (chicken fingers, a slice, a small plain dish). The kid portion MUST be cheaper than the adult entree and must be real food (not a drink/dessert).\nRespond ONLY JSON: {"adultEntree":{"item":"...","price":0},"kidPortion":{"item":"...","price":0}}`;
}

async function main() {
  console.log(`Cuisine-aware pin for ${input.length} restaurants\n`);
  const out = []; let i = 0;
  async function worker() {
    while (i < input.length) {
      const r = input[i++]; const type = mealType(r.cuisine);
      try { const pins = json(await callClaude(prompt(r, type)));
        out.push({ id: r.id, name: r.name, borough: r.borough, cuisine: r.cuisine, neighborhood: r.neighborhood, menuUrl: r.menuUrl, platform: r.platform, mealType: type, pins: pins || {} });
        const ok = pins && Object.keys(pins).length; console.log(`  ${ok ? 'OK ' : 'XX '}[${type}] ${r.name}`);
      } catch (e) { out.push({ id: r.id, name: r.name, borough: r.borough, cuisine: r.cuisine, neighborhood: r.neighborhood, menuUrl: r.menuUrl, platform: r.platform, mealType: type, pins: {}, error: e.message }); console.log(`  XX [${type}] ${r.name} — ${e.message}`); }
    }
  }
  await Promise.all(Array.from({ length: 4 }, () => worker()));
  fs.writeFileSync(path.join(dataDir, 'meals-pinned.json'), JSON.stringify(out, null, 1));
  const byT = {}; out.forEach(o => byT[o.mealType] = (byT[o.mealType] || 0) + 1);
  console.log(`\nWrote data/meals-pinned.json (${out.length}). Types: ${JSON.stringify(byT)}`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
