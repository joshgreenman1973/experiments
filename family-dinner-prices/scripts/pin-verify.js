#!/usr/bin/env node
/**
 * Family-bill pin + adversarial verify, run locally with controlled concurrency
 * and 429 retry (a reliable stand-in for the multi-agent workflow on smaller
 * batches). For each restaurant it picks an adult entree + kid portion from the
 * priced items, then a second call adversarially checks/repairs the pick.
 *
 * Input:  data/<name>-input.json  [{id,name,cuisine,borough,items:[{item,price}]}]
 * Output: data/<name>-verified.json [{id,name,borough,cuisine,valid,adultEntree,kidPortion,overCeiling,reason}]
 *
 * Usage: ANTHROPIC_API_KEY=... node scripts/pin-verify.js <name>-input.json
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const dataDir = path.join(__dirname, '..', 'data');
const API_KEY = process.env.ANTHROPIC_API_KEY;
if (!API_KEY) { console.error('ANTHROPIC_API_KEY required'); process.exit(1); }
const INPUT = process.argv[2]; if (!INPUT) { console.error('Usage: pin-verify.js <file>-input.json'); process.exit(1); }
const OUTPUT = INPUT.replace(/-input\.json$/, '-verified.json');
const items = JSON.parse(fs.readFileSync(path.join(dataDir, INPUT), 'utf8'));

function callClaude(prompt, tries = 0) {
  const body = JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 500, messages: [{ role: 'user', content: prompt }] });
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: 'api.anthropic.com', path: '/v1/messages', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY, 'anthropic-version': '2023-06-01', 'Content-Length': Buffer.byteLength(body) } },
      (res) => { let d = ''; res.on('data', c => d += c); res.on('end', () => {
        if (res.statusCode === 429 || res.statusCode >= 500) {
          if (tries >= 5) return reject(new Error('rate/again ' + res.statusCode));
          return setTimeout(() => callClaude(prompt, tries + 1).then(resolve, reject), 1500 * (tries + 1));
        }
        try { const p = JSON.parse(d); if (p.error) return reject(new Error(p.error.message)); resolve(p.content?.[0]?.text || ''); } catch (e) { reject(e); }
      }); });
    req.on('error', e => { if (tries < 5) return setTimeout(() => callClaude(prompt, tries + 1).then(resolve, reject), 1500 * (tries + 1)); reject(e); });
    req.write(body); req.end();
  });
}
const json = t => { const m = (t || '').match(/\{[\s\S]*\}/); if (!m) return null; try { return JSON.parse(m[0]); } catch { return null; } };

async function pinVerify(r) {
  const menu = r.items.map(it => `- ${it.item} — $${it.price}`).join('\n');
  const pinPrompt = `Restaurant "${r.name}" (${r.cuisine}, ${r.borough}). Priced menu items:\n${menu}\n\nPick exactly two, ONLY from the list (copy item text + price verbatim):\n1. adultEntree: the most representative ADULT dinner entree a family would order — a normal shareable main, mid-priced; NOT a whole specialty pizza, party/catering size, add-on, drink, or dessert.\n2. kidPortion: a smaller/cheaper item a child would eat (kids' item, a slice, a small plain dish); MUST be cheaper than the adult entree.\nRespond ONLY JSON: {"adultEntree":{"item":"...","price":0},"kidPortion":{"item":"...","price":0}}`;
  const pin = json(await callClaude(pinPrompt));
  if (!pin || !pin.adultEntree || !pin.kidPortion) return { id: r.id, name: r.name, borough: r.borough, cuisine: r.cuisine, valid: false, reason: 'pin failed' };

  const vPrompt = `Build the best valid family-bill pair for "${r.name}" (${r.cuisine}) from this priced menu:\n${menu}\n\nProposed (fix if needed): adultEntree ${pin.adultEntree.item} ($${pin.adultEntree.price}), kidPortion ${pin.kidPortion.item} ($${pin.kidPortion.price}).\n\nYOUR JOB: return a VALID pair if one exists in the list. Do NOT reject when a valid pair exists — repair it by re-selecting.\nRules:\n- adultEntree = a representative single adult main priced $6–$30 (prefer a normal entree; if the only mains are pricier, pick the cheapest main ≤ $30). Not a party/catering/whole-specialty-pie size, not an add-on/drink/dessert.\n- kidPortion = the cheapest suitable single FOOD item that is STRICTLY cheaper than your adultEntree (a kids' item, a slice, a small plain dish). Not a drink/dessert.\n- Only set valid=false if it is genuinely impossible — e.g. every food item is the same price, or no single main is ≤ $30.\nSet overCeiling=true only if your final adultEntree > $25.\nRespond ONLY JSON: {"valid":true,"adultEntree":{"item":"...","price":0},"kidPortion":{"item":"...","price":0},"overCeiling":false,"reason":"..."}`;
  const v = json(await callClaude(vPrompt));
  if (!v) return { id: r.id, name: r.name, borough: r.borough, cuisine: r.cuisine, valid: false, reason: 'verify failed' };
  return { id: r.id, name: r.name, borough: r.borough, cuisine: r.cuisine, valid: v.valid !== false, adultEntree: v.adultEntree, kidPortion: v.kidPortion, overCeiling: !!v.overCeiling, reason: v.reason || '' };
}

async function main() {
  console.log(`Pin+verify ${items.length} restaurants (concurrency 4, 429-retry)\n`);
  const out = []; let i = 0;
  async function worker() {
    while (i < items.length) {
      const r = items[i++];
      try { const res = await pinVerify(r); out.push(res); console.log(`  ${res.valid ? 'OK ' : 'XX '} ${r.name}${res.valid ? ` — ${res.adultEntree.item} $${res.adultEntree.price} / ${res.kidPortion.item} $${res.kidPortion.price}` : ' — ' + res.reason}`); }
      catch (e) { out.push({ id: r.id, name: r.name, borough: r.borough, cuisine: r.cuisine, valid: false, reason: e.message }); console.log(`  XX ${r.name} — ${e.message}`); }
    }
  }
  await Promise.all(Array.from({ length: 4 }, () => worker()));
  fs.writeFileSync(path.join(dataDir, OUTPUT), JSON.stringify(out, null, 1));
  console.log(`\nValid: ${out.filter(x => x.valid).length}/${out.length}. Wrote data/${OUTPUT}`);
}
main().catch(e => { console.error('Fatal:', e); process.exit(1); });
