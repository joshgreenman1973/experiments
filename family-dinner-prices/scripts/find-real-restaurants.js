#!/usr/bin/env node
/**
 * Find real restaurants via Google Places API (New)
 * Uses Text Search to find pizza/Chinese/diner spots across NYC boroughs
 * Filters by 25+ reviews, excludes chains and tourist traps
 */

const API_KEY = 'AIzaSyB24Xj0T3KaX4QG-UGlruT_wF5joplZfX4';
const MIN_REVIEWS = 25;

// Borough center points and rough bounds for searching
const BOROUGH_AREAS = {
  'Manhattan': [
    { label: 'Upper Manhattan', lat: 40.835, lng: -73.940 },
    { label: 'Midtown', lat: 40.755, lng: -73.985 },
    { label: 'Lower Manhattan', lat: 40.720, lng: -73.998 },
    { label: 'East Harlem', lat: 40.795, lng: -73.942 },
    { label: 'Washington Heights', lat: 40.846, lng: -73.936 },
  ],
  'Brooklyn': [
    { label: 'North Brooklyn', lat: 40.710, lng: -73.955 },
    { label: 'Central Brooklyn', lat: 40.670, lng: -73.960 },
    { label: 'South Brooklyn', lat: 40.630, lng: -73.970 },
    { label: 'East Brooklyn', lat: 40.660, lng: -73.900 },
    { label: 'Bay Ridge/Bensonhurst', lat: 40.630, lng: -74.020 },
    { label: 'Flatbush/East Flatbush', lat: 40.650, lng: -73.940 },
    { label: 'Sunset Park', lat: 40.645, lng: -74.010 },
    { label: 'Sheepshead Bay/Brighton', lat: 40.590, lng: -73.945 },
  ],
  'Queens': [
    { label: 'Astoria/LIC', lat: 40.760, lng: -73.920 },
    { label: 'Jackson Heights/Elmhurst', lat: 40.745, lng: -73.880 },
    { label: 'Flushing', lat: 40.760, lng: -73.830 },
    { label: 'Forest Hills/Rego Park', lat: 40.720, lng: -73.845 },
    { label: 'Jamaica/Richmond Hill', lat: 40.700, lng: -73.810 },
    { label: 'Bayside/Fresh Meadows', lat: 40.765, lng: -73.780 },
    { label: 'Far Rockaway', lat: 40.600, lng: -73.755 },
  ],
  'Bronx': [
    { label: 'South Bronx', lat: 40.815, lng: -73.920 },
    { label: 'Fordham/Belmont', lat: 40.860, lng: -73.890 },
    { label: 'Pelham/Throgs Neck', lat: 40.830, lng: -73.835 },
    { label: 'Kingsbridge/Riverdale', lat: 40.880, lng: -73.900 },
    { label: 'Parkchester/Castle Hill', lat: 40.840, lng: -73.860 },
  ],
  'Staten Island': [
    { label: 'North Shore', lat: 40.640, lng: -74.085 },
    { label: 'Mid Island', lat: 40.580, lng: -74.120 },
    { label: 'South Shore', lat: 40.540, lng: -74.180 },
  ]
};

// Known tourist traps / destination restaurants to exclude
const EXCLUDE_PATTERNS = [
  // Tourist traps / destination restaurants
  /lombardi/i, /grimaldi/i, /di fara/i, /juliana/i, /roberta/i,
  /lucali/i, /l&b spumoni/i, /joe.s shanghai/i, /peter luger/i,
  /katz.s/i, /russ.*daughters/i, /rubirosa/i, /din tai fung/i,
  /café china/i, /cafe china/i, /birds of a feather/i,
  /kings co imperial/i, /han dynasty/i, /kesté/i, /keste/i,
  // Chains
  /shake shack/i, /five guys/i, /domino/i, /papa john/i,
  /little caesars/i, /pizza hut/i, /panda express/i,
  /p\.?f\.? chang/i, /cheesecake factory/i, /blaze pizza/i,
  /uno pizzeria/i, /sbarro/i, /chipotle/i,
  // Buffets (not relevant to family dinner pricing)
  /buffet/i, /all you can eat/i,
  // Sushi / hibachi / not actually Chinese
  /sushi/i, /hibachi/i, /taqueria/i, /sabrosura/i, /sabor latino/i,
  /kaieteur/i, /trinidad/i, /nonnas of the world/i,
];

async function searchPlaces(query, locationBias) {
  const url = 'https://places.googleapis.com/v1/places:searchText';
  const body = {
    textQuery: query,
    maxResultCount: 20,
    locationBias: {
      circle: {
        center: { latitude: locationBias.lat, longitude: locationBias.lng },
        radius: 3000.0
      }
    },
    languageCode: 'en',
    priceLevels: ['PRICE_LEVEL_INEXPENSIVE'],
  };

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': API_KEY,
      'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.location,places.priceLevel,places.rating,places.userRatingCount,places.businessStatus,places.types,places.id'
    },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const err = await res.text();
    console.error(`API error for "${query}" at ${locationBias.label}: ${res.status} ${err}`);
    return [];
  }

  const data = await res.json();
  return (data.places || []).filter(p => {
    // Must be operational
    if (p.businessStatus && p.businessStatus !== 'OPERATIONAL') return false;
    // Must have 25+ reviews
    if (!p.userRatingCount || p.userRatingCount < MIN_REVIEWS) return false;
    // Not a tourist trap or chain
    const name = p.displayName?.text || '';
    if (EXCLUDE_PATTERNS.some(pat => pat.test(name))) return false;
    return true;
  }).map(p => ({
    name: p.displayName?.text || '',
    address: p.formattedAddress || '',
    lat: p.location?.latitude,
    lng: p.location?.longitude,
    priceLevel: p.priceLevel || null,
    rating: p.rating,
    reviewCount: p.userRatingCount,
    placeId: p.id,
  }));
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Determine which borough a lat/lng actually falls in (rough check)
function inferBorough(lat, lng) {
  if (lat > 40.785 && lng > -73.935 && lat < 40.92) return 'Bronx';
  if (lat < 40.575) return 'Staten Island';
  if (lng < -74.05 && lat < 40.65) return 'Staten Island';
  if (lng < -73.83 && lat > 40.68 && lat < 40.80) return 'Queens';
  if (lat > 40.69 && lat < 40.88 && lng > -74.02 && lng < -73.90) return 'Manhattan';
  if (lat < 40.70 && lng > -74.05 && lng < -73.85) return 'Brooklyn';
  // Rough fallback
  if (lng < -73.85 && lat > 40.55) return 'Queens';
  if (lat < 40.74 && lng > -74.04) return 'Brooklyn';
  return 'Unknown';
}

async function findRestaurants(cuisineType, targetPerBorough) {
  const allResults = [];
  const seen = new Set();

  for (const [borough, areas] of Object.entries(BOROUGH_AREAS)) {
    const target = targetPerBorough[borough] || 0;
    if (target === 0) continue;

    console.log(`\nSearching ${cuisineType} in ${borough} (target: ${target})...`);
    const boroughResults = [];

    for (const area of areas) {
      const query = `${cuisineType} restaurant in ${area.label} ${borough} NYC`;
      console.log(`  → ${query}`);
      const results = await searchPlaces(query, area);

      for (const r of results) {
        if (!seen.has(r.placeId)) {
          seen.add(r.placeId);
          r.borough = borough;
          boroughResults.push(r);
        }
      }

      await sleep(200); // Rate limit
    }

    // Sort by review count (most reviewed = most established neighborhood spot)
    boroughResults.sort((a, b) => b.reviewCount - a.reviewCount);

    // Take target count
    const selected = boroughResults.slice(0, target);
    console.log(`  Found ${boroughResults.length} total, selected ${selected.length}`);
    allResults.push(...selected);
  }

  return allResults;
}

async function main() {
  const cuisineType = process.argv[2] || 'pizza';

  let targets;
  if (cuisineType === 'pizza') {
    targets = { Manhattan: 15, Brooklyn: 18, Queens: 15, Bronx: 14, 'Staten Island': 13 };
  } else if (cuisineType === 'chinese') {
    targets = { Manhattan: 15, Brooklyn: 15, Queens: 15, Bronx: 15, 'Staten Island': 15 };
  } else if (cuisineType === 'diner') {
    targets = { Manhattan: 15, Brooklyn: 15, Queens: 15, Bronx: 15, 'Staten Island': 15 };
  } else {
    targets = { Manhattan: 15, Brooklyn: 15, Queens: 15, Bronx: 15, 'Staten Island': 15 };
  }

  console.log(`Finding real ${cuisineType} restaurants across NYC...`);
  console.log(`Targets: ${JSON.stringify(targets)}`);

  const results = await findRestaurants(cuisineType, targets);

  console.log(`\n${'='.repeat(60)}`);
  console.log(`TOTAL: ${results.length} verified ${cuisineType} restaurants`);
  console.log(`${'='.repeat(60)}\n`);

  // Write results
  const outFile = `/tmp/${cuisineType}-places.json`;
  const fs = require('fs');
  fs.writeFileSync(outFile, JSON.stringify(results, null, 2));
  console.log(`Written to ${outFile}`);

  // Print summary by borough
  const byBorough = {};
  results.forEach(r => {
    byBorough[r.borough] = (byBorough[r.borough] || 0) + 1;
  });
  console.log('\nBy borough:', JSON.stringify(byBorough));

  // Print all results
  results.forEach((r, i) => {
    console.log(`${i+1}. ${r.name} | ${r.borough} | ${r.address} | ${r.reviewCount} reviews | ${r.priceLevel || 'n/a'}`);
  });
}

main().catch(console.error);
