#!/usr/bin/env node
/**
 * Finds menu page URLs for restaurants in the registry.
 *
 * Strategy:
 *   1. Try Google Places API to get the restaurant's official website
 *   2. Try MenuPages and AllMenus URL patterns
 *   3. Skip restaurants that already have a menuUrl
 *
 * Usage:
 *   GOOGLE_PLACES_API_KEY=... node scripts/find-menu-urls.js
 *
 * The Google Places API key should be stored as a GitHub secret,
 * NEVER hardcoded in this file.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const dataDir = path.join(__dirname, '..', 'data');
const registry = JSON.parse(fs.readFileSync(path.join(dataDir, 'restaurants.json'), 'utf8'));

const GOOGLE_API_KEY = process.env.GOOGLE_PLACES_API_KEY;

// ── Helpers ─────────────────────────────────────────────────────

function fetchJson(url, options = {}) {
  return new Promise((resolve, reject) => {
    const req = https.request(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve(null); }
      });
    });
    req.on('error', reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

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

// Try to find the restaurant's website via Google Places Text Search
async function findWebsiteViaPlaces(restaurant) {
  if (!GOOGLE_API_KEY) return null;

  const query = `${restaurant.name} ${restaurant.neighborhood} ${restaurant.borough} NYC restaurant`;

  try {
    const body = JSON.stringify({ textQuery: query, maxResultCount: 1 });
    const res = await new Promise((resolve, reject) => {
      const req = https.request('https://places.googleapis.com/v1/places:searchText', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Goog-Api-Key': GOOGLE_API_KEY,
          'X-Goog-FieldMask': 'places.websiteUri',
          'Content-Length': Buffer.byteLength(body),
        },
      }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(data)); }
          catch { resolve(null); }
        });
      });
      req.on('error', reject);
      req.write(body);
      req.end();
    });

    return res?.places?.[0]?.websiteUri || null;
  } catch {
    return null;
  }
}

// Try common menu aggregator URL patterns
async function findViaMenuSites(name) {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '');
  const urls = [
    `https://www.menupages.com/restaurants/${slug}/menu`,
    `https://www.allmenus.com/ny/new-york/-/${slug}/menu/`,
  ];

  for (const url of urls) {
    const status = await fetchHead(url);
    if (status === 200) return url;
    await sleep(200);
  }
  return null;
}

// ── Main ────────────────────────────────────────────────────────

async function main() {
  const active = registry.filter(r => r.status !== 'closed' && !r.menuUrl);

  if (active.length === 0) {
    console.log('All active restaurants already have menu URLs.');
    return;
  }

  console.log(`Finding menu URLs for ${active.length} restaurants...`);
  if (!GOOGLE_API_KEY) {
    console.log('Note: GOOGLE_PLACES_API_KEY not set — skipping Places API lookups.\n');
  } else {
    console.log('Using Google Places API for website lookups.\n');
  }

  let found = 0;

  for (let i = 0; i < active.length; i++) {
    const r = active[i];
    process.stdout.write(`[${i+1}/${active.length}] ${r.name}... `);

    // Strategy 1: Google Places API
    const website = await findWebsiteViaPlaces(r);
    if (website) {
      r.menuUrl = website;
      found++;
      console.log(`✓ ${website}`);
      await sleep(100);
      continue;
    }

    // Strategy 2: Menu aggregator sites
    const menuSite = await findViaMenuSites(r.name);
    if (menuSite) {
      r.menuUrl = menuSite;
      found++;
      console.log(`✓ ${menuSite}`);
      continue;
    }

    console.log('—');
    await sleep(100);
  }

  // Save updated registry
  fs.writeFileSync(path.join(dataDir, 'restaurants.json'), JSON.stringify(registry, null, 2));
  console.log(`\nFound ${found}/${active.length} menu URLs`);
  console.log('Registry updated.');
}

main().catch(console.error);
