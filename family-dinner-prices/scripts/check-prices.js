#!/usr/bin/env node
/**
 * Monthly price checker for NYC family dinner project.
 *
 * For restaurants with a menuUrl in restaurants.json, this script:
 *   1. Fetches the menu page
 *   2. Sends the text to Claude Haiku to extract current prices
 *   3. Detects closures (page gone, "permanently closed" signals)
 *   4. Saves a new dated snapshot
 *
 * Closure detection:
 *   - If a page returns 404/410 or contains closure keywords, marks as closed
 *   - 3 consecutive monthly failures → auto-flagged as closed
 *   - Closed restaurants are excluded from averages (not carried forward)
 *
 * Restaurants without a menuUrl keep their last known price.
 *
 * Usage:
 *   ANTHROPIC_API_KEY=sk-... node scripts/check-prices.js
 *
 * Cost: ~$1–2/month for ~150 restaurants at Haiku rates.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const baseDir = path.join(__dirname, '..');
const dataDir = path.join(baseDir, 'data');
const snapshotsDir = path.join(dataDir, 'snapshots');

const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
if (!ANTHROPIC_API_KEY) {
  console.error('Error: ANTHROPIC_API_KEY environment variable required');
  process.exit(1);
}

// ── Load current state ──────────────────────────────────────────
const registry = JSON.parse(fs.readFileSync(path.join(dataDir, 'restaurants.json'), 'utf8'));

// Find the most recent snapshot to use as fallback
const snapshots = fs.readdirSync(snapshotsDir)
  .filter(f => f.endsWith('.json'))
  .sort()
  .reverse();

if (snapshots.length === 0) {
  console.error('No existing snapshots found. Run create-baseline.js first.');
  process.exit(1);
}

const lastSnapshot = JSON.parse(
  fs.readFileSync(path.join(snapshotsDir, snapshots[0]), 'utf8')
);
console.log(`Last snapshot: ${snapshots[0]} (${Object.keys(lastSnapshot.prices).length} restaurants)`);

// ── Helpers ─────────────────────────────────────────────────────

const CLOSURE_KEYWORDS = [
  'permanently closed',
  'this location has closed',
  'we have closed',
  'no longer in business',
  'closed permanently',
  'this restaurant is closed',
  'has shut down',
  'out of business',
];

function detectClosure(html) {
  const lower = html.toLowerCase();
  for (const kw of CLOSURE_KEYWORDS) {
    if (lower.includes(kw)) return kw;
  }
  return null;
}

function fetchPage(url, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FamilyDinnerBot/1.0)' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return fetchPage(res.headers.location, timeout).then(resolve).catch(reject);
      }
      if (res.statusCode === 404 || res.statusCode === 410) {
        return reject(new Error(`GONE_${res.statusCode}`));
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve(body));
    });
    req.on('error', reject);
    req.setTimeout(timeout, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

function stripHtml(html) {
  // Remove scripts, styles, then tags, collapse whitespace
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 8000); // Keep it short for the API
}

async function callClaude(prompt) {
  const body = JSON.stringify({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 300,
    messages: [{ role: 'user', content: prompt }],
  });

  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) return reject(new Error(parsed.error.message));
          const text = parsed.content?.[0]?.text || '';
          resolve(text);
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function extractPrices(restaurant, menuText) {
  const prompt = `You are extracting restaurant menu prices. The restaurant is "${restaurant.name}" (${restaurant.cuisine}) in ${restaurant.neighborhood}, ${restaurant.borough}, NYC.

Here is text from their menu page:
---
${menuText}
---

I need IN-RESTAURANT dine-in prices (NOT delivery prices). Extract:
1. adultEntree: price of a typical adult dinner entrée (like "${restaurant.adultItem}")
2. kidMeal: price of a kid-sized meal or smaller portion (like "${restaurant.kidItem}")
3. appetizer: price of a shared appetizer/side (like "${restaurant.appItem}")
4. drinks: price of a soda or juice (we order 2 for the adults, kids get water)

Respond ONLY with a JSON object like:
{"adultEntree": 15, "kidMeal": 8, "appetizer": 6, "drinks": 2.50, "confidence": "high"}

Set confidence to "high" if you found clear prices, "medium" if you had to estimate from similar items, "low" if the menu text was unclear. If you cannot find any prices, respond with: {"error": "no prices found"}`;

  const response = await callClaude(prompt);

  try {
    // Extract JSON from response
    const match = response.match(/\{[\s\S]*\}/);
    if (!match) return null;
    const parsed = JSON.parse(match[0]);
    if (parsed.error) return null;
    return parsed;
  } catch {
    return null;
  }
}

// ── Main ────────────────────────────────────────────────────────

async function main() {
  const today = new Date().toISOString().split('T')[0];
  console.log(`\nGenerating snapshot for ${today}\n`);

  const FAIL_THRESHOLD = 3; // consecutive failures before auto-closing

  const active = registry.filter(r => r.status !== 'closed');
  const closed = registry.filter(r => r.status === 'closed');
  const scrapeable = active.filter(r => r.menuUrl);
  const noUrl = active.filter(r => !r.menuUrl);

  console.log(`Active: ${active.length} | Already closed: ${closed.length}`);
  console.log(`Scrapeable: ${scrapeable.length} | Carry forward: ${noUrl.length}\n`);

  const newSnapshot = { date: today, prices: {}, closures: [] };
  const changes = [];
  const newClosures = [];
  let registryChanged = false;

  // Carry forward prices for active restaurants without URLs
  for (const r of noUrl) {
    if (lastSnapshot.prices[r.id]) {
      newSnapshot.prices[r.id] = { ...lastSnapshot.prices[r.id], source: 'carried' };
    }
  }

  // Check scrapeable restaurants
  let checked = 0, updated = 0, failed = 0;

  for (const r of scrapeable) {
    checked++;
    process.stdout.write(`[${checked}/${scrapeable.length}] ${r.name}... `);

    try {
      const html = await fetchPage(r.menuUrl);

      // Check for closure keywords in the raw HTML
      const closureSignal = detectClosure(html);
      if (closureSignal) {
        console.log(`⚠ CLOSED (detected: "${closureSignal}")`);
        r.status = 'closed';
        r.closedDate = today;
        r.closureReason = `Detected keyword: "${closureSignal}"`;
        r.failCount = 0;
        registryChanged = true;
        newClosures.push({ name: r.name, borough: r.borough, reason: closureSignal });
        // Don't include in snapshot prices — excluded from averages
        continue;
      }

      const menuText = stripHtml(html);

      if (menuText.length < 50) {
        console.log('too little text, carrying forward');
        r.failCount = (r.failCount || 0) + 1;
        registryChanged = true;
        if (r.failCount >= FAIL_THRESHOLD) {
          console.log(`  ⚠ ${FAIL_THRESHOLD} consecutive failures — flagging as closed`);
          r.status = 'closed';
          r.closedDate = today;
          r.closureReason = `${FAIL_THRESHOLD} consecutive scrape failures`;
          newClosures.push({ name: r.name, borough: r.borough, reason: 'repeated failures' });
        } else if (lastSnapshot.prices[r.id]) {
          newSnapshot.prices[r.id] = { ...lastSnapshot.prices[r.id], source: 'carried' };
        }
        continue;
      }

      const prices = await extractPrices(r, menuText);

      if (!prices || prices.confidence === 'low') {
        console.log('low confidence, carrying forward');
        r.failCount = (r.failCount || 0) + 1;
        registryChanged = true;
        if (r.failCount >= FAIL_THRESHOLD) {
          console.log(`  ⚠ ${FAIL_THRESHOLD} consecutive failures — flagging as closed`);
          r.status = 'closed';
          r.closedDate = today;
          r.closureReason = `${FAIL_THRESHOLD} consecutive scrape failures`;
          newClosures.push({ name: r.name, borough: r.borough, reason: 'repeated failures' });
        } else if (lastSnapshot.prices[r.id]) {
          newSnapshot.prices[r.id] = { ...lastSnapshot.prices[r.id], source: 'carried' };
        }
        failed++;
        continue;
      }

      // Success — reset fail counter
      if (r.failCount > 0) {
        r.failCount = 0;
        registryChanged = true;
      }

      // Calculate family dinner total with tax
      const subtotal = (prices.adultEntree * 2) + (prices.kidMeal * 2) +
                       prices.appetizer + (prices.drinks * 2);
      const totalWithTax = Math.round(subtotal * 1.08875 * 100) / 100;

      const oldPrice = lastSnapshot.prices[r.id]?.price;
      const delta = oldPrice ? totalWithTax - oldPrice : 0;

      newSnapshot.prices[r.id] = {
        price: totalWithTax,
        adultEntree: prices.adultEntree,
        kidMeal: prices.kidMeal,
        appetizer: prices.appetizer,
        drinks: prices.drinks,
        source: 'scraped',
        confidence: prices.confidence,
      };

      if (Math.abs(delta) > 0.5) {
        changes.push({ name: r.name, borough: r.borough, old: oldPrice, new: totalWithTax, delta });
        updated++;
        console.log(`$${oldPrice} → $${totalWithTax} (${delta > 0 ? '+' : ''}${delta.toFixed(2)})`);
      } else {
        console.log(`$${totalWithTax} (unchanged)`);
      }

      // Rate limit: ~1 req/sec to be polite
      await new Promise(resolve => setTimeout(resolve, 1000));

    } catch (err) {
      // 404/410 = likely closed
      if (err.message.startsWith('GONE_')) {
        console.log(`⚠ CLOSED (${err.message})`);
        r.status = 'closed';
        r.closedDate = today;
        r.closureReason = `Page returned ${err.message.replace('GONE_', '')}`;
        r.failCount = 0;
        registryChanged = true;
        newClosures.push({ name: r.name, borough: r.borough, reason: err.message });
        continue;
      }

      console.log(`error: ${err.message}`);
      r.failCount = (r.failCount || 0) + 1;
      registryChanged = true;

      if (r.failCount >= FAIL_THRESHOLD) {
        console.log(`  ⚠ ${FAIL_THRESHOLD} consecutive failures — flagging as closed`);
        r.status = 'closed';
        r.closedDate = today;
        r.closureReason = `${FAIL_THRESHOLD} consecutive scrape failures`;
        newClosures.push({ name: r.name, borough: r.borough, reason: 'repeated failures' });
      } else if (lastSnapshot.prices[r.id]) {
        newSnapshot.prices[r.id] = { ...lastSnapshot.prices[r.id], source: 'carried' };
      }
      failed++;
    }
  }

  // Record closures in snapshot for history
  newSnapshot.closures = newClosures.map(c => c.name);

  // Save updated registry if anything changed
  if (registryChanged) {
    fs.writeFileSync(path.join(dataDir, 'restaurants.json'), JSON.stringify(registry, null, 2));
    console.log(`\nRegistry updated (${newClosures.length} new closures, fail counts updated)`);
  }

  // Save snapshot
  const snapshotPath = path.join(snapshotsDir, `${today}.json`);
  fs.writeFileSync(snapshotPath, JSON.stringify(newSnapshot, null, 2));

  // Summary
  console.log(`\n════════════════════════════════════════`);
  console.log(`Snapshot saved: ${snapshotPath}`);
  console.log(`Active restaurants in snapshot: ${Object.keys(newSnapshot.prices).length}`);
  console.log(`Scraped: ${checked} | Updated: ${updated} | Failed: ${failed}`);
  console.log(`Carried forward: ${noUrl.length + (checked - updated - failed)}`);

  if (newClosures.length > 0) {
    console.log(`\n🚫 New closures detected (${newClosures.length}):`);
    for (const c of newClosures) {
      console.log(`  ✕ ${c.name} (${c.borough}) — ${c.reason}`);
    }
  }

  if (changes.length > 0) {
    console.log(`\nPrice changes detected:`);
    changes.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    for (const c of changes) {
      const arrow = c.delta > 0 ? '▲' : '▼';
      console.log(`  ${arrow} ${c.name} (${c.borough}): $${c.old} → $${c.new} (${c.delta > 0 ? '+' : ''}$${c.delta.toFixed(2)})`);
    }
  } else {
    console.log(`\nNo price changes detected.`);
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
