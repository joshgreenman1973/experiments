#!/usr/bin/env node
// Creates the baseline snapshot from current data files
// Run once: node scripts/create-baseline.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const baseDir = path.join(__dirname, '..');

function loadDataFile(filename, varName) {
  const code = fs.readFileSync(path.join(baseDir, filename), 'utf8');
  const fn = new Function(code + `; return ${varName};`);
  return fn();
}

const allData = loadDataFile('data.js', 'DATA');
const pizzaData = loadDataFile('pizza-data.js', 'PIZZA_DATA');
const dinerData = loadDataFile('diner-data.js', 'DINER_DATA');
const chineseData = loadDataFile('chinese-data.js', 'CHINESE_DATA');

// Build master registry — one entry per restaurant with a stable ID
const registry = [];
const seen = new Set();

function addToRegistry(entries, dataset) {
  for (const d of entries) {
    const id = slugify(d.name + '-' + d.neighborhood + '-' + d.borough);
    if (seen.has(id)) continue;
    seen.add(id);
    registry.push({
      id,
      name: d.name,
      neighborhood: d.neighborhood,
      borough: d.borough,
      cuisine: d.cuisine,
      lat: d.lat,
      lng: d.lng,
      kidsMenu: d.kidsMenu,
      dataset, // which view(s) this restaurant appears in
      menuUrl: null, // to be populated for scrapeable restaurants
      adultItem: d.adultItem,
      kidItem: d.kidItem,
      appItem: d.appItem,
    });
  }
}

function slugify(str) {
  return str.toLowerCase()
    .replace(/['']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

addToRegistry(allData, 'all');
addToRegistry(pizzaData, 'pizza');
addToRegistry(dinerData, 'diner');
addToRegistry(chineseData, 'chinese');

// Save registry
fs.writeFileSync(
  path.join(baseDir, 'data', 'restaurants.json'),
  JSON.stringify(registry, null, 2)
);
console.log(`Registry: ${registry.length} restaurants`);

// Build baseline snapshot — just prices keyed by ID
const snapshot = { date: '2026-03-21', prices: {} };

function addToSnapshot(entries) {
  for (const d of entries) {
    const id = slugify(d.name + '-' + d.neighborhood + '-' + d.borough);
    if (snapshot.prices[id]) continue;
    snapshot.prices[id] = {
      price: d.price,
      adultEntree: d.adultEntree,
      kidMeal: d.kidMeal,
      appetizer: d.appetizer,
      drinks: d.drinks,
    };
  }
}

addToSnapshot(allData);
addToSnapshot(pizzaData);
addToSnapshot(dinerData);
addToSnapshot(chineseData);

fs.writeFileSync(
  path.join(baseDir, 'data', 'snapshots', '2026-03-21.json'),
  JSON.stringify(snapshot, null, 2)
);
console.log(`Snapshot: ${Object.keys(snapshot.prices).length} prices saved`);
