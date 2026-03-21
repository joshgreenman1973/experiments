#!/usr/bin/env node
/**
 * NYC Bus Tracker — Data Collector
 * Fetches all active bus positions from the MTA SIRI VehicleMonitoring API
 * and appends a compact snapshot to the daily JSONL file.
 */

import { writeFileSync, appendFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data', 'snapshots');

const API_KEY = process.env.MTA_API_KEY;
const API_URL = 'https://bustime.mta.info/api/siri/vehicle-monitoring.json';

if (!API_KEY) {
  console.error('MTA_API_KEY environment variable is required.');
  console.error('Register at https://register.developer.obanyc.com/');
  process.exit(1);
}

async function fetchAllVehicles() {
  const url = `${API_URL}?key=${API_KEY}&version=2`;
  console.log('Fetching all vehicle positions...');

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API returned ${res.status}: ${res.statusText}`);
  }

  const data = await res.json();
  const delivery = data?.Siri?.ServiceDelivery?.VehicleMonitoringDelivery;

  if (!delivery || !delivery.length) {
    throw new Error('No VehicleMonitoringDelivery in response');
  }

  const activities = delivery[0]?.VehicleActivity || [];
  console.log(`Received ${activities.length} vehicle records`);

  return activities.map(a => {
    const j = a.MonitoredVehicleJourney;
    if (!j) return null;

    const routeRef = j.LineRef || '';
    // Strip "MTA NYCT_" or "MTABC_" prefix for cleaner route names
    const route = routeRef.replace(/^MTA\s*NYCT_/, '').replace(/^MTABC_/, '');

    return {
      id: j.VehicleRef || '',
      route,
      routeFull: routeRef,
      dir: j.DirectionRef || 0,
      lat: j.VehicleLocation?.Latitude,
      lon: j.VehicleLocation?.Longitude,
      bearing: j.Bearing != null ? Math.round(j.Bearing) : null,
      dest: j.DestinationName || '',
      nextStop: j.MonitoredCall?.StopPointRef?.replace(/^MTA_/, '') || '',
      distFromStop: j.MonitoredCall?.Extensions?.Distances?.PresentableDistance || '',
      stopsAway: j.MonitoredCall?.Extensions?.Distances?.StopsFromCall || null,
      phase: j.ProgressStatus || '',
      timestamp: a.RecordedAtTime || ''
    };
  }).filter(Boolean);
}

function todayStr() {
  const now = new Date();
  // Use ET (UTC-5 or UTC-4 depending on DST)
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  return et.toISOString().slice(0, 10);
}

async function main() {
  const vehicles = await fetchAllVehicles();

  if (vehicles.length === 0) {
    console.log('No vehicles returned (service may be offline). Skipping.');
    return;
  }

  const snapshot = {
    ts: new Date().toISOString(),
    count: vehicles.length,
    vehicles
  };

  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true });
  }

  const filename = `${todayStr()}.jsonl`;
  const filepath = join(DATA_DIR, filename);

  appendFileSync(filepath, JSON.stringify(snapshot) + '\n');
  console.log(`Appended ${vehicles.length} vehicles to ${filename}`);
}

main().catch(err => {
  console.error('Collection failed:', err.message);
  process.exit(1);
});
