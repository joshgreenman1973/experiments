#!/usr/bin/env node
/**
 * Merges the newly-discovered trackable candidates (data/new-candidates-scan.json,
 * locked >= MIN items) into data/trackable-scan.json so build-panel.js picks them
 * up. Captures freshness headers (Last-Modified/ETag) for each via a quick fetch
 * (no AI). Idempotent: keys by a generated id.
 *
 * Usage: node scripts/merge-candidates.js [minItems=4]
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const dataDir = path.join(__dirname, '..', 'data');
const MIN = parseInt(process.argv[2] || '4', 10);

const scan = JSON.parse(fs.readFileSync(path.join(dataDir, 'trackable-scan.json'), 'utf8'));
const cand = JSON.parse(fs.readFileSync(path.join(dataDir, 'new-candidates-scan.json'), 'utf8'));
const slug = (s) => String(s || '').toLowerCase().replace(/['’]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

function headers(url, timeout = 10000, redirects = 0) {
  return new Promise((resolve) => {
    if (redirects > 5) return resolve({});
    let mod; try { mod = url.startsWith('https') ? https : http; } catch { return resolve({}); }
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FamilyDinnerBot/1.0)' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        let loc = res.headers.location; if (loc.startsWith('/')) { const u = new URL(url); loc = u.origin + loc; }
        res.destroy(); return headers(loc, timeout, redirects + 1).then(resolve);
      }
      const h = { lastModified: res.headers['last-modified'] || null, etag: res.headers['etag'] || null };
      res.destroy(); resolve(h);
    });
    req.on('error', () => resolve({}));
    req.setTimeout(timeout, () => { req.destroy(); resolve({}); });
  });
}

async function main() {
  const trackable = Object.values(cand).filter(v => v.readable && (v.locked || 0) >= MIN);
  console.log(`Merging ${trackable.length} new trackable candidates (>=${MIN} items)\n`);
  let added = 0;
  for (const v of trackable) {
    const id = `${slug(v.name)}-${slug(v.neighborhood || '')}-${slug(v.borough)}`;
    if (scan[id]) { console.log(`  skip (exists): ${v.name}`); continue; }
    const fresh = await headers(v.menuUrl);
    scan[id] = {
      name: v.name, borough: v.borough, cuisine: v.cuisine, neighborhood: v.neighborhood || '',
      menuUrl: v.menuUrl, platform: v.platform || null,
      freshness: { lastModified: fresh.lastModified || null, etag: fresh.etag || null },
      readable: true, extracted: v.items.length, locked: v.locked, items: v.items,
    };
    added++;
    console.log(`  + ${v.name} (${v.borough}) — ${v.locked} items`);
  }
  fs.writeFileSync(path.join(dataDir, 'trackable-scan.json'), JSON.stringify(scan, null, 2));
  console.log(`\nAdded ${added}. trackable-scan.json now has ${Object.keys(scan).length} entries.`);
}
main();
