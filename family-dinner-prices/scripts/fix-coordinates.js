#!/usr/bin/env node
// Fix restaurant coordinates using Google Places API validation results
// Also removes closed restaurants and flags low-review ones

const fs = require('fs');
const path = require('path');

const MIN_REVIEWS = 25;

// Load validation results
const resultsPath = path.join(__dirname, '..', 'data', 'validation-results.json');
const results = JSON.parse(fs.readFileSync(resultsPath, 'utf-8'));

// Group results by source file
const bySource = {};
results.forEach(r => {
  if (!bySource[r.source]) bySource[r.source] = [];
  bySource[r.source].push(r);
});

// Stats
let coordFixed = 0;
let removed = 0;
let lowReview = 0;

const removedList = [];
const lowReviewList = [];

// Process each source file
for (const [sourceFile, entries] of Object.entries(bySource)) {
  const filePath = path.join(__dirname, '..', sourceFile);
  let content = fs.readFileSync(filePath, 'utf-8');

  for (const entry of entries) {
    const isClosed = entry.googleStatus === 'CLOSED_PERMANENTLY' || entry.googleStatus === 'CLOSED_TEMPORARILY';
    const notFound = entry.googleStatus === 'NOT_FOUND';
    const tooFewReviews = (entry.reviews !== undefined && entry.reviews < MIN_REVIEWS && !isClosed && !notFound);

    if (isClosed || notFound) {
      // Remove the entire line for this restaurant
      // Match the object literal for this restaurant name
      const escapedName = entry.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // Match from { before name to },\n or the closing }
      const regex = new RegExp(`\\s*\\{name:"${escapedName}"[^}]*\\},?\\n?`, 'g');
      const before = content.length;
      content = content.replace(regex, '\n');
      if (content.length < before) {
        removed++;
        removedList.push({
          name: entry.name,
          neighborhood: entry.neighborhood,
          borough: entry.borough,
          status: entry.googleStatus,
          source: sourceFile
        });
      }
      continue;
    }

    if (tooFewReviews) {
      lowReview++;
      lowReviewList.push({
        name: entry.name,
        neighborhood: entry.neighborhood,
        borough: entry.borough,
        reviews: entry.reviews,
        source: sourceFile
      });
      // Remove these too — they're likely not real/findable places
      const escapedName = entry.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`\\s*\\{name:"${escapedName}"[^}]*\\},?\\n?`, 'g');
      const before = content.length;
      content = content.replace(regex, '\n');
      if (content.length < before) {
        removed++;
        removedList.push({
          name: entry.name,
          neighborhood: entry.neighborhood,
          borough: entry.borough,
          status: `LOW_REVIEWS (${entry.reviews})`,
          source: sourceFile
        });
      }
      continue;
    }

    // Fix coordinates if Google has better ones
    if (entry.googleLat && entry.googleLng && entry.distanceMeters && entry.distanceMeters > 50) {
      const escapedName = entry.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      // Match lat:NUMBER,lng:NUMBER pattern for this restaurant
      const latLngRegex = new RegExp(
        `(\\{name:"${escapedName}"[^}]*?)lat:${entry.ourLat},lng:${entry.ourLng}`,
        'g'
      );

      const googleLat = Math.round(entry.googleLat * 10000) / 10000;
      const googleLng = Math.round(entry.googleLng * 10000) / 10000;

      const before = content;
      content = content.replace(latLngRegex, `$1lat:${googleLat},lng:${googleLng}`);
      if (content !== before) {
        coordFixed++;
      }
    }
  }

  fs.writeFileSync(filePath, content);
}

console.log('='.repeat(60));
console.log('COORDINATE FIX REPORT');
console.log('='.repeat(60));
console.log(`\nCoordinates updated: ${coordFixed}`);
console.log(`Restaurants removed: ${removed}`);

if (removedList.length) {
  console.log('\n🔴 REMOVED:');

  // Group by source and borough for replacement guidance
  const bySourceBorough = {};
  removedList.forEach(r => {
    const key = `${r.source}|${r.borough}`;
    if (!bySourceBorough[key]) bySourceBorough[key] = [];
    bySourceBorough[key].push(r);
  });

  for (const [key, items] of Object.entries(bySourceBorough)) {
    const [source, borough] = key.split('|');
    console.log(`\n  ${source} — ${borough} (need ${items.length} replacement${items.length > 1 ? 's' : ''}):`);
    items.forEach(r => {
      console.log(`    - ${r.name} (${r.neighborhood}) — ${r.status}`);
    });
  }
}

// Count remaining restaurants per file
console.log('\n📊 REMAINING COUNTS:');
for (const sourceFile of ['data.js', 'pizza-data.js', 'diner-data.js', 'chinese-data.js']) {
  const filePath = path.join(__dirname, '..', sourceFile);
  const content = fs.readFileSync(filePath, 'utf-8');
  const count = (content.match(/\{name:"/g) || []).length;
  console.log(`  ${sourceFile}: ${count}`);
}

// Save removal list for replacement script
const removalPath = path.join(__dirname, '..', 'data', 'removed-restaurants.json');
fs.writeFileSync(removalPath, JSON.stringify(removedList, null, 2));
console.log(`\nRemoval list saved to: ${removalPath}`);
