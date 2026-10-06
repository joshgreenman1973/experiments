#!/usr/bin/env node
/**
 * NYC Bus Tracker — Data Collector
 * Fetches all active bus positions from the MTA SIRI VehicleMonitoring API
 * and appends one compact snapshot to the current hour's JSONL file
 * (data/snapshots/YYYY-MM-DD/HH.jsonl, ET date and hour).
 *
 * Snapshot format v2 (October 2026). Each vehicle keeps the v1 keys that
 * process.js has always read (id, route, dir, lat, lon, bearing, phase,
 * timestamp) and adds trip, rate, dep, stopsAway, distFromStop, pax and
 * cap. trip and dep allow buses run to be matched against the schedule; pax is the on-board counter's live passenger estimate where the
 * bus has one.
 */

import { appendFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data', 'snapshots');

const API_KEY = process.env.MTA_API_KEY;
// The version lives in the path. Passing version=2 as a query parameter as
// well makes the endpoint answer with an XML error page.
const API_URL = 'https://bustime.mta.info/api/siri/vehicle-monitoring-v2.json';

if (!API_KEY) {
  console.error('MTA_API_KEY environment variable is required.');
  console.error('Register at https://register.developer.obanyc.com/');
  process.exit(1);
}

const num = v => (v == null || v === '' || Number.isNaN(Number(v)) ? null : Number(v));

async function fetchAllVehicles() {
  const res = await fetch(`${API_URL}?key=${API_KEY}`, { signal: AbortSignal.timeout(60000) });
  if (!res.ok) throw new Error(`API returned ${res.status}: ${res.statusText}`);
  const data = await res.json();
  const delivery = data?.Siri?.ServiceDelivery?.VehicleMonitoringDelivery;
  if (!delivery || !delivery.length) throw new Error('No VehicleMonitoringDelivery in response');

  const activities = delivery[0]?.VehicleActivity || [];
  console.log(`Received ${activities.length} vehicle records`);

  return activities.map(a => {
    const j = a.MonitoredVehicleJourney;
    if (!j || !j.VehicleLocation) return null;
    const route = (j.LineRef || '').replace(/^MTA\s*NYCT_/, '').replace(/^MTABC_/, '');
    const call = j.MonitoredCall || {};
    const caps = call.Extensions?.Capacities || {};
    const phase = j.ProgressStatus;
    return {
      id: j.VehicleRef || '',
      route,
      dir: j.DirectionRef ?? '',
      lat: j.VehicleLocation.Latitude,
      lon: j.VehicleLocation.Longitude,
      bearing: j.Bearing != null ? Math.round(j.Bearing) : null,
      phase: Array.isArray(phase) ? phase.join(',') : (phase || ''),
      rate: j.ProgressRate || '',
      trip: j.FramedVehicleJourneyRef?.DatedVehicleJourneyRef || '',
      dep: j.OriginAimedDepartureTime || '',
      nextStop: (call.StopPointRef || '').replace(/^MTA_/, ''),
      stopsAway: num(call.NumberOfStopsAway),
      distFromStop: num(call.DistanceFromStop),
      pax: num(caps.EstimatedPassengerCount),
      cap: num(caps.EstimatedPassengerCapacity),
      timestamp: a.RecordedAtTime || '',
    };
  }).filter(Boolean);
}

async function main() {
  const vehicles = await fetchAllVehicles();
  if (vehicles.length === 0) {
    console.log('No vehicles returned (service may be offline). Skipping.');
    return;
  }

  const now = new Date();
  const snapshot = { v: 2, ts: now.toISOString(), count: vehicles.length, vehicles };

  // One file per ET hour keeps each blob far below GitHub's 100 MiB ceiling.
  const dateET = now.toLocaleString('en-CA', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  });
  const hourET = now.toLocaleString('en-GB', {
    timeZone: 'America/New_York', hour: '2-digit', hour12: false,
  }).padStart(2, '0').slice(0, 2);

  const dayDir = join(DATA_DIR, dateET);
  if (!existsSync(dayDir)) mkdirSync(dayDir, { recursive: true });
  appendFileSync(join(dayDir, `${hourET}.jsonl`), JSON.stringify(snapshot) + '\n');
  console.log(`Appended ${vehicles.length} vehicles to ${dateET}/${hourET}.jsonl`);
}

main().catch(err => {
  console.error('Collection failed:', err.message);
  process.exit(1);
});
