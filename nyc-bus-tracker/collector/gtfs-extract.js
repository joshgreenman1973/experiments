#!/usr/bin/env node
/**
 * GTFS Route Shape Extractor
 * Downloads MTA bus GTFS data and extracts route shapes as GeoJSON.
 * Run once (or quarterly when GTFS updates).
 *
 * Usage: node gtfs-extract.js
 */

import { writeFileSync, readFileSync, existsSync, mkdirSync, rmSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import AdmZip from 'adm-zip';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, '..', 'data', 'routes');
const TMP_DIR = join(__dirname, '..', '.tmp-gtfs');

// MTA GTFS bus feeds — one per borough + MTA Bus Company
const GTFS_FEEDS = [
  { name: 'bronx', url: 'http://web.mta.info/developers/data/nyct/bus/google_transit_bronx.zip' },
  { name: 'brooklyn', url: 'http://web.mta.info/developers/data/nyct/bus/google_transit_brooklyn.zip' },
  { name: 'manhattan', url: 'http://web.mta.info/developers/data/nyct/bus/google_transit_manhattan.zip' },
  { name: 'queens', url: 'http://web.mta.info/developers/data/nyct/bus/google_transit_queens.zip' },
  { name: 'staten_island', url: 'http://web.mta.info/developers/data/nyct/bus/google_transit_staten_island.zip' },
  { name: 'busco', url: 'http://web.mta.info/developers/data/busco/google_transit.zip' },
];

function parseCsv(text) {
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
  return lines.slice(1).map(line => {
    // Handle quoted fields with commas
    const vals = [];
    let current = '';
    let inQuotes = false;
    for (const ch of line) {
      if (ch === '"') { inQuotes = !inQuotes; continue; }
      if (ch === ',' && !inQuotes) { vals.push(current.trim()); current = ''; continue; }
      current += ch;
    }
    vals.push(current.trim());
    const obj = {};
    headers.forEach((h, i) => { obj[h] = vals[i] || ''; });
    return obj;
  });
}

async function downloadAndExtract(feed) {
  console.log(`Downloading ${feed.name}...`);
  const res = await fetch(feed.url);
  if (!res.ok) throw new Error(`Failed to download ${feed.name}: ${res.status}`);

  const buffer = Buffer.from(await res.arrayBuffer());
  const feedDir = join(TMP_DIR, feed.name);
  mkdirSync(feedDir, { recursive: true });

  const zip = new AdmZip(buffer);
  zip.extractAllTo(feedDir, true);
  return feedDir;
}

function extractRouteShapes(feedDir, feedName) {
  const shapesFile = join(feedDir, 'shapes.txt');
  const routesFile = join(feedDir, 'routes.txt');
  const tripsFile = join(feedDir, 'trips.txt');

  if (!existsSync(shapesFile) || !existsSync(routesFile) || !existsSync(tripsFile)) {
    console.warn(`Missing GTFS files in ${feedName}, skipping`);
    return [];
  }

  const routes = parseCsv(readFileSync(routesFile, 'utf-8'));
  const trips = parseCsv(readFileSync(tripsFile, 'utf-8'));
  const shapes = parseCsv(readFileSync(shapesFile, 'utf-8'));

  // Build route_id → route info
  const routeMap = new Map();
  for (const r of routes) {
    routeMap.set(r.route_id, {
      id: r.route_id,
      shortName: r.route_short_name || r.route_id,
      longName: r.route_long_name || '',
      color: r.route_color ? `#${r.route_color}` : '#4488ff'
    });
  }

  // Find one shape_id per route (pick the first trip's shape)
  const routeShapeMap = new Map();
  for (const t of trips) {
    if (!routeShapeMap.has(t.route_id) && t.shape_id) {
      routeShapeMap.set(t.route_id, t.shape_id);
    }
  }

  // Build shape_id → coordinates
  const shapeCoords = new Map();
  for (const s of shapes) {
    const id = s.shape_id;
    if (!shapeCoords.has(id)) shapeCoords.set(id, []);
    shapeCoords.get(id).push({
      seq: parseInt(s.shape_pt_sequence, 10),
      lat: parseFloat(s.shape_pt_lat),
      lon: parseFloat(s.shape_pt_lon)
    });
  }

  // Sort each shape by sequence
  for (const [, coords] of shapeCoords) {
    coords.sort((a, b) => a.seq - b.seq);
  }

  // Build GeoJSON features
  const features = [];
  for (const [routeId, shapeId] of routeShapeMap) {
    const coords = shapeCoords.get(shapeId);
    const routeInfo = routeMap.get(routeId);
    if (!coords || !routeInfo) continue;

    features.push({
      type: 'Feature',
      properties: {
        route: routeInfo.shortName,
        routeId: routeInfo.id,
        name: routeInfo.longName,
        color: routeInfo.color,
        feed: feedName
      },
      geometry: {
        type: 'LineString',
        coordinates: coords.map(c => [c.lon, c.lat])
      }
    });
  }

  return features;
}

async function main() {
  mkdirSync(TMP_DIR, { recursive: true });
  mkdirSync(OUT_DIR, { recursive: true });

  const allFeatures = [];

  for (const feed of GTFS_FEEDS) {
    try {
      const feedDir = await downloadAndExtract(feed);
      const features = extractRouteShapes(feedDir, feed.name);
      allFeatures.push(...features);
      console.log(`  → ${features.length} routes from ${feed.name}`);
    } catch (err) {
      console.error(`Error processing ${feed.name}:`, err.message);
    }
  }

  const geojson = {
    type: 'FeatureCollection',
    features: allFeatures
  };

  const outFile = join(OUT_DIR, 'routes.geojson');
  writeFileSync(outFile, JSON.stringify(geojson));
  console.log(`\nWrote ${allFeatures.length} route shapes to ${outFile}`);

  // Cleanup
  rmSync(TMP_DIR, { recursive: true, force: true });
  console.log('Cleaned up temp files.');
}

main().catch(err => {
  console.error('GTFS extraction failed:', err.message);
  process.exit(1);
});
