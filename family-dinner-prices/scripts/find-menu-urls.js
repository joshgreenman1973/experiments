#!/usr/bin/env node
/**
 * Finds menu page URLs for restaurants in the registry.
 * Uses Google Custom Search or direct URL pattern matching.
 * 
 * Usage: node scripts/find-menu-urls.js
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const dataDir = path.join(__dirname, '..', 'data');
const registry = JSON.parse(fs.readFileSync(path.join(dataDir, 'restaurants.json'), 'utf8'));

// Common menu page patterns to try directly
const MENU_SOURCES = [
  name => `https://www.menupages.com/restaurants/${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '')}/menu`,
  name => `https://www.allmenus.com/ny/new-york/-/${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '')}/menu/`,
];

function fetchHead(url, timeout = 5000) {
  return new Promise((resolve) => {
    const req = https.request(url, { method: 'HEAD', headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      resolve(res.statusCode);
    });
    req.on('error', () => resolve(0));
    req.setTimeout(timeout, () => { req.destroy(); resolve(0); });
    req.end();
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const active = registry.filter(r => r.status !== 'closed' && !r.menuUrl);
  console.log(`Finding menu URLs for ${active.length} restaurants...\n`);
  
  let found = 0;
  
  for (let i = 0; i < active.length; i++) {
    const r = active[i];
    process.stdout.write(`[${i+1}/${active.length}] ${r.name}... `);
    
    // Try MenuPages first (most reliable for NYC)
    for (const urlFn of MENU_SOURCES) {
      const url = urlFn(r.name);
      const status = await fetchHead(url);
      if (status === 200) {
        r.menuUrl = url;
        found++;
        console.log(`✓ ${url}`);
        break;
      }
      await sleep(200);
    }
    
    if (!r.menuUrl) {
      console.log('—');
    }
  }
  
  // Save updated registry
  fs.writeFileSync(path.join(dataDir, 'restaurants.json'), JSON.stringify(registry, null, 2));
  console.log(`\nFound ${found}/${active.length} menu URLs`);
  console.log('Registry updated.');
}

main().catch(console.error);
