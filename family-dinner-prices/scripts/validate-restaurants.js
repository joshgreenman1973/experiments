#!/usr/bin/env node
// Validate all restaurants against Google Places API (New)
// Checks: location accuracy, open/closed status, review count, existence

const fs = require('fs');
const path = require('path');

const API_KEY = process.argv[2];
if (!API_KEY) {
  console.error('Usage: node validate-restaurants.js <GOOGLE_MAPS_API_KEY>');
  process.exit(1);
}

const MIN_REVIEWS = 25;
const MAX_DISTANCE_METERS = 500; // flag if Google's location is >500m from ours

// Load all data files
function loadDataFromJS(filePath, varName) {
  const content = fs.readFileSync(filePath, 'utf-8');
  // Extract the array by evaluating in a sandboxed way
  const fn = new Function(content + `; return ${varName};`);
  return fn();
}

const DATA = loadDataFromJS(path.join(__dirname, '..', 'data.js'), 'DATA');
const PIZZA_DATA = loadDataFromJS(path.join(__dirname, '..', 'pizza-data.js'), 'PIZZA_DATA');
const DINER_DATA = loadDataFromJS(path.join(__dirname, '..', 'diner-data.js'), 'DINER_DATA');
const CHINESE_DATA = loadDataFromJS(path.join(__dirname, '..', 'chinese-data.js'), 'CHINESE_DATA');

// Combine all, tagging source
const allRestaurants = [
  ...DATA.map(r => ({ ...r, source: 'data.js' })),
  ...PIZZA_DATA.map(r => ({ ...r, source: 'pizza-data.js' })),
  ...DINER_DATA.map(r => ({ ...r, source: 'diner-data.js' })),
  ...CHINESE_DATA.map(r => ({ ...r, source: 'chinese-data.js' })),
];

console.log(`Total restaurants to validate: ${allRestaurants.length}`);
console.log(`  data.js: ${DATA.length}`);
console.log(`  pizza-data.js: ${PIZZA_DATA.length}`);
console.log(`  diner-data.js: ${DINER_DATA.length}`);
console.log(`  chinese-data.js: ${CHINESE_DATA.length}`);
console.log('');

// Haversine distance in meters
function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

// Google Places API (New) - Text Search
async function searchPlace(restaurant) {
  const query = `${restaurant.name} ${restaurant.neighborhood} ${restaurant.borough} NYC`;

  const response = await fetch('https://places.googleapis.com/v1/places:searchText', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': API_KEY,
      'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.location,places.businessStatus,places.userRatingCount,places.rating,places.priceLevel,places.googleMapsUri'
    },
    body: JSON.stringify({
      textQuery: query,
      locationBias: {
        circle: {
          center: { latitude: restaurant.lat, longitude: restaurant.lng },
          radius: 2000
        }
      }
    })
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API error ${response.status}: ${err}`);
  }

  const data = await response.json();
  return data.places?.[0] || null;
}

// Rate limiting - Google allows 600 QPM for Places API
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const issues = {
    notFound: [],
    closed: [],
    lowReviews: [],
    locationOff: [],
    coordUpdates: [],
  };

  const results = [];
  let processed = 0;

  for (const restaurant of allRestaurants) {
    processed++;
    if (processed % 25 === 0) {
      console.log(`Processing ${processed}/${allRestaurants.length}...`);
    }

    try {
      const place = await searchPlace(restaurant);

      if (!place) {
        issues.notFound.push({
          name: restaurant.name,
          neighborhood: restaurant.neighborhood,
          borough: restaurant.borough,
          source: restaurant.source
        });
        results.push({ ...restaurant, googleStatus: 'NOT_FOUND' });
        continue;
      }

      const googleLat = place.location?.latitude;
      const googleLng = place.location?.longitude;
      const distance = (googleLat && googleLng)
        ? haversine(restaurant.lat, restaurant.lng, googleLat, googleLng)
        : null;
      const reviewCount = place.userRatingCount || 0;
      const businessStatus = place.businessStatus || 'UNKNOWN';
      const rating = place.rating || null;

      const result = {
        name: restaurant.name,
        neighborhood: restaurant.neighborhood,
        borough: restaurant.borough,
        source: restaurant.source,
        googleName: place.displayName?.text,
        googleAddress: place.formattedAddress,
        googleStatus: businessStatus,
        reviews: reviewCount,
        rating: rating,
        priceLevel: place.priceLevel || null,
        distanceMeters: distance ? Math.round(distance) : null,
        ourLat: restaurant.lat,
        ourLng: restaurant.lng,
        googleLat,
        googleLng,
        mapsUrl: place.googleMapsUri
      };

      results.push(result);

      // Check for issues
      if (businessStatus === 'CLOSED_PERMANENTLY' || businessStatus === 'CLOSED_TEMPORARILY') {
        issues.closed.push(result);
      }

      if (reviewCount < MIN_REVIEWS && businessStatus !== 'CLOSED_PERMANENTLY') {
        issues.lowReviews.push(result);
      }

      if (distance && distance > MAX_DISTANCE_METERS) {
        issues.locationOff.push(result);
      } else if (distance && distance > 50) {
        // Suggest coordinate update if >50m off but not flagged as major issue
        issues.coordUpdates.push(result);
      }

    } catch (err) {
      console.error(`  ERROR for ${restaurant.name}: ${err.message}`);
      results.push({ ...restaurant, googleStatus: 'API_ERROR', error: err.message });
    }

    // Small delay to stay well under rate limits
    await sleep(120);
  }

  // Write full results
  const resultsPath = path.join(__dirname, '..', 'data', 'validation-results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));

  // Print report
  console.log('\n' + '='.repeat(70));
  console.log('VALIDATION REPORT');
  console.log('='.repeat(70));

  console.log(`\nTotal checked: ${processed}`);
  console.log(`API errors: ${results.filter(r => r.googleStatus === 'API_ERROR').length}`);

  if (issues.notFound.length) {
    console.log(`\n🔴 NOT FOUND ON GOOGLE (${issues.notFound.length}):`);
    console.log('   These may not exist, be misspelled, or be too new for Google.');
    issues.notFound.forEach(r => {
      console.log(`   - ${r.name} (${r.neighborhood}, ${r.borough}) [${r.source}]`);
    });
  }

  if (issues.closed.length) {
    console.log(`\n🔴 CLOSED (${issues.closed.length}):`);
    console.log('   These need to be replaced.');
    issues.closed.forEach(r => {
      console.log(`   - ${r.name} (${r.neighborhood}, ${r.borough}) — ${r.googleStatus} [${r.source}]`);
    });
  }

  if (issues.lowReviews.length) {
    console.log(`\n🟡 LOW REVIEWS — under ${MIN_REVIEWS} (${issues.lowReviews.length}):`);
    console.log('   May be too obscure or misidentified.');
    issues.lowReviews.forEach(r => {
      console.log(`   - ${r.name} (${r.neighborhood}, ${r.borough}) — ${r.reviews} reviews [${r.source}]`);
    });
  }

  if (issues.locationOff.length) {
    console.log(`\n🟠 LOCATION OFF by >${MAX_DISTANCE_METERS}m (${issues.locationOff.length}):`);
    console.log('   Coordinates are significantly wrong — like your Smiling Pizza issue.');
    issues.locationOff.forEach(r => {
      console.log(`   - ${r.name} (${r.neighborhood}, ${r.borough}) — ${r.distanceMeters}m off [${r.source}]`);
      console.log(`     Ours: ${r.ourLat}, ${r.ourLng} → Google: ${r.googleLat}, ${r.googleLng}`);
      console.log(`     ${r.googleAddress}`);
    });
  }

  if (issues.coordUpdates.length) {
    console.log(`\n🟢 MINOR COORDINATE FIXES — 50-${MAX_DISTANCE_METERS}m off (${issues.coordUpdates.length}):`);
    issues.coordUpdates.forEach(r => {
      console.log(`   - ${r.name} (${r.neighborhood}, ${r.borough}) — ${r.distanceMeters}m off [${r.source}]`);
    });
  }

  // Summary of clean restaurants
  const clean = results.filter(r =>
    r.googleStatus === 'OPERATIONAL' &&
    (r.reviews === undefined || r.reviews >= MIN_REVIEWS) &&
    (!r.distanceMeters || r.distanceMeters <= MAX_DISTANCE_METERS)
  );
  console.log(`\n✅ Clean (no issues): ${clean.length}/${processed}`);

  console.log(`\nFull results saved to: ${resultsPath}`);

  // Return issues for potential auto-fix
  return issues;
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
