/**
 * NYC Bus Tracker — Dashboard
 * Real-time animated map of all NYC buses with performance metrics.
 */

// ═══ CONFIG ═══
const CONFIG = {
  // MTA SIRI API (client-side — supports CORS)
  apiBase: 'https://bustime.mta.info/api/siri/vehicle-monitoring.json',
  // API key — set via URL param ?key=XXX or prompt
  apiKey: new URLSearchParams(window.location.search).get('key') || '',
  // Refresh interval in ms (30s minimum per API rules)
  refreshInterval: 30000,
  // Bunching threshold: two buses on same route/direction within this many meters
  bunchingDistanceMeters: 250,
  // Gap threshold: minutes without a bus on a route/direction
  gapThresholdMinutes: 20,
  // Map tile source
  tileUrl: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
};

// ═══ STATE ═══
let map;
let currentSnapshot = null;
let previousSnapshot = null; // for speed calculation
let snapshots = []; // for timeline replay
let isLive = true;
let isPlaying = false;
let playSpeed = 1;
let playTimer = null;
let routeShapes = null;
let routeShapeIndex = null; // routeId → GeoJSON feature (built once on shape load)
let selectedRoute = null;
let sortMode = 'name'; // 'name', 'bunching', 'gaps', 'buses'
let boroFilter = 'all'; // 'all', 'M', 'B', 'Bx', 'Q', 'S', 'top25', 'nearby'
let userLocation = null; // {lat, lon} from geolocation
let busSpeedCache = {}; // busId → speed in mph

// Rolling-average smoothing (dampens poll-to-poll jitter)
const speedSmooth = createRollingAvg(3);
const waitSmooth = createRollingAvg(3);
const gap30Smooth = createRollingAvg(3);
const gap20Smooth = createRollingAvg(3);

let busPositionCache = {}; // busId → {lat, lon, ts, route, dir} — persists across polls

// ═══ DOM CACHE ═══
// Populated once after DOMContentLoaded; avoids repeated getElementById calls
const dom = {};
function cacheDomElements() {
  const ids = [
    'stat-buses', 'stat-routes-count', 'stat-speed', 'stat-bunching',
    'stat-gaps', 'stat-wait', 'speed-hint', 'speed-detail',
    'wait-alerts', 'live-badge', 'status-text', 'loading-overlay',
    'loading-text', 'route-list', 'route-search', 'sort-btn',
    'timeline-slider', 'timeline-time', 'timeline-date', 'timeline-speed',
    'btn-live', 'btn-play', 'borough-filter', 'route-list-header',
  ];
  for (const id of ids) {
    dom[id] = document.getElementById(id);
  }
}

// ═══ INIT ═══
async function init() {
  cacheDomElements();

  // Prompt for API key if not provided
  if (!CONFIG.apiKey) {
    CONFIG.apiKey = prompt(
      'Enter your MTA BusTime API key:\n\n' +
      'Get one free at https://register.developer.obanyc.com/'
    );
    if (!CONFIG.apiKey) {
      dom['loading-text'].textContent =
        'API key required. Reload and enter your key.';
      return;
    }
    // Store in URL for convenience
    const url = new URL(window.location);
    url.searchParams.set('key', CONFIG.apiKey);
    window.history.replaceState({}, '', url);
  }

  updateLoadingText('Initializing map\u2026');

  // Start API fetch NOW — don't wait for map tiles to load
  const apiDataPromise = prefetchLiveData();

  // Init map (loads tiles in parallel with API fetch)
  map = new maplibregl.Map({
    container: 'map',
    style: CONFIG.tileUrl,
    center: [-73.95, 40.72],
    zoom: 11,
    minZoom: 9,
    maxZoom: 18,
    attributionControl: true,
  });

  map.addControl(new maplibregl.NavigationControl(), 'bottom-left');

  map.on('load', async () => {
    // Generate directional pointer icon for buses
    createBusPointerIcon();

    // Try cached snapshot for instant render while fresh data loads
    const cached = loadCachedSnapshot();
    if (cached) {
      processLiveData(cached, true);
      hideLoading();
      dom['live-badge'].style.display = 'flex';
    }

    // Now await the fresh API data (was fetching in parallel with map)
    updateLoadingText('Processing bus data\u2026');
    const prefetchedData = await apiDataPromise;
    if (prefetchedData) {
      processLiveData(prefetchedData);
      cacheLiveData(prefetchedData);
    } else if (!cached) {
      await fetchLiveData(); // fallback only if no cache either
    }

    hideLoading();
    dom['live-badge'].style.display = 'flex';

    // Load route shapes in background — doesn't block initial render
    loadRouteShapes();

    // Set title animation endpoint based on actual container width, then start
    const lane = document.querySelector('.title-lane');
    const title = document.querySelector('.bus-title');
    if (lane && title) {
      const end = lane.offsetWidth - title.offsetWidth;
      if (end > 0) title.style.setProperty('--end', `${end}px`);
      // Start animation after a brief delay so --end is applied
      requestAnimationFrame(() => title.classList.add('animate'));
    }

    // Start auto-refresh
    setInterval(() => {
      if (isLive) fetchLiveData();
    }, CONFIG.refreshInterval);

    // Set up bus click handler
    setupBusClickHandler();
  });

  // Wire up UI
  setupControls();
}

// ═══ DATA LOADING ═══
async function loadRouteShapes() {
  try {
    const res = await fetch('data/routes/routes.geojson');
    routeShapes = await res.json();

    // Build lookup index: routeId → feature (O(1) instead of linear scan)
    routeShapeIndex = new Map();
    for (const f of routeShapes.features) {
      const id = f.properties.route || f.properties.routeId;
      if (id) routeShapeIndex.set(id, f);
    }

    map.addSource('routes', {
      type: 'geojson',
      data: routeShapes,
    });

    // Insert route lines BELOW bus layers so late-loading shapes don't cover dots
    const beforeLayer = map.getLayer('bus-glow') ? 'bus-glow' : undefined;
    map.addLayer({
      id: 'route-lines',
      type: 'line',
      source: 'routes',
      paint: {
        'line-color': ['get', 'color'],
        'line-width': 2,
        'line-opacity': 0.35,
      },
    }, beforeLayer);
  } catch (e) {
    console.warn('Could not load route shapes:', e);
  }
}

// Prefetch: starts the API call immediately, returns raw parsed data
async function prefetchLiveData() {
  try {
    // VehicleMonitoringDetailLevel=basic keeps route/direction/destination
    // but drops onward calls and stop-level details we don't need
    const url = `${CONFIG.apiBase}?key=${CONFIG.apiKey}&version=2&VehicleMonitoringDetailLevel=basic`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    const delivery = data?.Siri?.ServiceDelivery?.VehicleMonitoringDelivery;
    if (!delivery?.[0]?.VehicleActivity) throw new Error('No vehicle data');
    return delivery[0].VehicleActivity;
  } catch (e) {
    console.error('Prefetch failed:', e);
    return null;
  }
}

// Cache last snapshot in sessionStorage for instant reload
function cacheLiveData(vehicleActivity) {
  try {
    // Store a compact version — just the fields we need
    const compact = vehicleActivity.map(a => {
      const j = a.MonitoredVehicleJourney;
      if (!j?.VehicleLocation) return null;
      return {
        id: j.VehicleRef || '',
        r: j.LineRef || '',
        d: j.DirectionRef || '0',
        lat: j.VehicleLocation.Latitude,
        lon: j.VehicleLocation.Longitude,
        b: j.Bearing || 0,
        dst: j.DestinationName?.[0] || j.DestinationName || '',
      };
    }).filter(Boolean);
    sessionStorage.setItem('bus_cache', JSON.stringify({ ts: Date.now(), v: compact }));
  } catch (e) { /* quota exceeded — ignore */ }
}

function loadCachedSnapshot() {
  try {
    const raw = sessionStorage.getItem('bus_cache');
    if (!raw) return null;
    const cached = JSON.parse(raw);
    // Only use if less than 5 minutes old
    if (Date.now() - cached.ts > 300000) return null;
    // Convert compact format back to API-like structure
    return cached.v.map(v => ({
      MonitoredVehicleJourney: {
        VehicleRef: v.id,
        LineRef: v.r,
        DirectionRef: String(v.d),
        VehicleLocation: { Latitude: v.lat, Longitude: v.lon },
        Bearing: v.b,
        DestinationName: [v.dst],
      },
      RecordedAtTime: new Date(cached.ts).toISOString(),
    }));
  } catch (e) { return null; }
}

// Process raw API data into snapshot and render
// isCached=true skips position merging (stale data, don't pollute cache)
function processLiveData(vehicleActivity, isCached = false) {
  const vehicles = parseVehicles(vehicleActivity);
  const now = Date.now();

  // Update bus position cache with fresh data
  for (const v of vehicles) {
    busPositionCache[v.id] = { lat: v.lat, lon: v.lon, ts: now, route: v.route, dir: v.dir, bearing: v.bearing };
  }

  // Merge: include cached buses missing from this poll (stale < 2 min)
  // and evict entries older than 3 min in the same pass
  const vehicleIds = new Set(vehicles.map(v => v.id));
  const mergedVehicles = [...vehicles];
  for (const [id, cached] of Object.entries(busPositionCache)) {
    const age = now - cached.ts;
    if (age > 180000) {
      delete busPositionCache[id];
    } else if (!vehicleIds.has(id) && age < 120000) {
      mergedVehicles.push({
        id, route: cached.route, dir: cached.dir,
        lat: cached.lat, lon: cached.lon, bearing: cached.bearing || 0,
        dest: '', nextStop: '', distFromStop: '', stopsAway: null, phase: '', ts: '',
        routeFull: '', bunched: 0,
      });
    }
  }

  const snapshot = {
    ts: new Date().toISOString(),
    count: mergedVehicles.length,
    vehicles: mergedVehicles,
  };

  if (previousSnapshot) {
    computeSpeeds(previousSnapshot, snapshot);
  }
  previousSnapshot = currentSnapshot;
  currentSnapshot = snapshot;
  snapshots.push(snapshot);
  if (snapshots.length > 200) snapshots.shift();

  computeMetrics(snapshot);
  updateTimeline();

  dom['status-text'].textContent =
    `Updated ${formatTime(new Date(snapshot.ts))}`;
}

async function fetchLiveData() {
  try {
    const activity = await prefetchLiveData();
    if (!activity) throw new Error('No data');
    processLiveData(activity);
    cacheLiveData(activity);
  } catch (e) {
    console.error('Fetch failed:', e);
    dom['status-text'].textContent = `Error: ${e.message}`;
    hideLoading();
  }
}

function parseVehicles(activities) {
  return activities.map(a => {
    const j = a.MonitoredVehicleJourney;
    if (!j?.VehicleLocation) return null;

    const routeRef = j.LineRef || '';
    const route = routeRef.replace(/^MTA\s*NYCT_/, '').replace(/^MTABC_/, '');

    return {
      id: j.VehicleRef || '',
      route,
      routeFull: routeRef,
      dir: parseInt(j.DirectionRef, 10) || 0,
      lat: j.VehicleLocation.Latitude,
      lon: j.VehicleLocation.Longitude,
      bearing: j.Bearing != null ? Math.round(j.Bearing) : 0,
      dest: j.DestinationName?.[0] || j.DestinationName || '',
      nextStop: j.MonitoredCall?.StopPointRef?.replace(/^MTA_/, '') || '',
      distFromStop: j.MonitoredCall?.Extensions?.Distances?.PresentableDistance || '',
      stopsAway: j.MonitoredCall?.Extensions?.Distances?.StopsFromCall ?? null,
      phase: j.ProgressStatus?.[0] || j.ProgressStatus || '',
      ts: a.RecordedAtTime || '',
    };
  }).filter(Boolean);
}

// ═══ RENDERING ═══
function renderBuses(snapshot) {
  const geojson = {
    type: 'FeatureCollection',
    features: snapshot.vehicles.map(v => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [v.lon, v.lat] },
      properties: {
        id: v.id,
        route: v.route,
        color: routeColor(v.route),
        dir: v.dir,
        dest: v.dest,
        bearing: v.bearing,
        nextStop: v.nextStop,
        distFromStop: v.distFromStop,
        stopsAway: v.stopsAway,
        phase: v.phase,
        bunched: v.bunched || 0,
      },
    })),
  };

  if (map.getSource('buses')) {
    map.getSource('buses').setData(geojson);
  } else {
    map.addSource('buses', { type: 'geojson', data: geojson });

    // Bus glow — soft halo per route color, red for bunched
    map.addLayer({
      id: 'bus-glow',
      type: 'circle',
      source: 'buses',
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          9, 5, 13, 12, 16, 18,
        ],
        'circle-color': [
          'case',
          ['==', ['get', 'bunched'], 1], 'rgba(210, 35, 42, 0.25)',
          ['get', 'color'],
        ],
        'circle-opacity': [
          'case',
          ['==', ['get', 'bunched'], 1], 1,
          0.15,
        ],
        'circle-blur': 1,
      },
    });

    // Bus dots — colored by route, red override for bunched
    map.addLayer({
      id: 'bus-dots',
      type: 'circle',
      source: 'buses',
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          9, 2.5, 13, 5, 16, 8,
        ],
        'circle-color': [
          'case',
          ['==', ['get', 'bunched'], 1], '#d2232a',
          ['get', 'color'],
        ],
        'circle-opacity': 0.9,
        'circle-stroke-width': [
          'case',
          ['==', ['get', 'bunched'], 1], 1.5,
          0.5,
        ],
        'circle-stroke-color': [
          'case',
          ['==', ['get', 'bunched'], 1], '#ff6666',
          'rgba(255,255,255,0.15)',
        ],
      },
    });

    // Direction arrows — SDF triangle that inherits route color
    map.addLayer({
      id: 'bus-arrows',
      type: 'symbol',
      source: 'buses',
      minzoom: 13,
      layout: {
        'icon-image': 'bus-arrow',
        'icon-size': [
          'interpolate', ['linear'], ['zoom'],
          13, 0.6, 16, 1.0,
        ],
        'icon-rotate': ['get', 'bearing'],
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'icon-rotation-alignment': 'map',
        'icon-pitch-alignment': 'map',
        'icon-offset': [0, -12],
      },
      paint: {
        'icon-color': [
          'case',
          ['==', ['get', 'bunched'], 1], '#ff6666',
          ['get', 'color'],
        ],
        'icon-opacity': 0.9,
      },
    });
  }

  // Highlight selected route
  if (selectedRoute) {
    highlightRoute(selectedRoute);
  }
}

function highlightRoute(route) {
  if (!map.getLayer('route-lines')) return;

  map.setPaintProperty('route-lines', 'line-opacity', [
    'case',
    ['==', ['get', 'route'], route], 0.85,
    0.04,
  ]);
  map.setPaintProperty('route-lines', 'line-width', [
    'case',
    ['==', ['get', 'route'], route], 4,
    1,
  ]);
  map.setPaintProperty('bus-dots', 'circle-opacity', [
    'case',
    ['==', ['get', 'route'], route], 1,
    0.1,
  ]);
  if (map.getLayer('bus-glow')) {
    map.setPaintProperty('bus-glow', 'circle-opacity', [
      'case',
      ['==', ['get', 'route'], route], 0.3,
      0.03,
    ]);
  }
}

function highlightRoutes(routes) {
  if (!map.getLayer('route-lines') || routes.length === 0) return;

  // Build a match expression: ['in', ['get', 'route'], ['literal', [...]]]
  const matchExpr = ['in', ['get', 'route'], ['literal', routes]];

  map.setPaintProperty('route-lines', 'line-opacity', [
    'case', matchExpr, 0.85, 0.04,
  ]);
  map.setPaintProperty('route-lines', 'line-width', [
    'case', matchExpr, 3.5, 1,
  ]);
  map.setPaintProperty('bus-dots', 'circle-opacity', [
    'case', matchExpr, 1, 0.08,
  ]);
  if (map.getLayer('bus-glow')) {
    map.setPaintProperty('bus-glow', 'circle-opacity', [
      'case', matchExpr, 0.3, 0.02,
    ]);
  }
}

function clearRouteHighlight() {
  if (!map.getLayer('route-lines')) return;
  map.setPaintProperty('route-lines', 'line-opacity', 0.35);
  map.setPaintProperty('route-lines', 'line-width', 2);
  map.setPaintProperty('bus-dots', 'circle-opacity', 0.9);
  if (map.getLayer('bus-glow')) {
    map.setPaintProperty('bus-glow', 'circle-opacity', [
      'case',
      ['==', ['get', 'bunched'], 1], 1,
      0.15,
    ]);
  }
}

// ═══ SPEED CALCULATION ═══
function computeSpeeds(prevSnap, currSnap) {
  const prevMap = new Map();
  for (const v of prevSnap.vehicles) {
    prevMap.set(v.id, v);
  }

  const prevTime = new Date(prevSnap.ts).getTime();
  const currTime = new Date(currSnap.ts).getTime();
  const dtHours = (currTime - prevTime) / 3600000; // time diff in hours

  if (dtHours <= 0 || dtHours > 0.5) return; // skip if bad interval or >30 min gap

  for (const v of currSnap.vehicles) {
    const prev = prevMap.get(v.id);
    if (!prev) continue;
    // Skip if bus changed routes between snapshots
    if (prev.route !== v.route) continue;

    // Prefer route-distance (along the polyline) over straight-line haversine.
    // Route-distance is consistent with MTA methodology, which measures speed
    // along actual route geometry rather than as-the-crow-flies.
    const distMeters = measureDistance(prev.lat, prev.lon, v.lat, v.lon, v.route);
    const speed = (distMeters / 1609.34) / dtHours;

    // Filter out unrealistic speeds (GPS glitches, layovers)
    if (speed >= 0 && speed < 60) {
      busSpeedCache[v.id] = round1(speed);
    }
  }
}

// ═══ METRICS ═══
function computeMetrics(snapshot) {
  const { vehicles } = snapshot;
  const routeGroups = groupByRouteDir(vehicles);
  const routeMetrics = {};
  let totalBunching = 0;
  const bunchedIds = new Set();

  for (const [key, buses] of routeGroups) {
    const [route, dirStr] = key.split('_');
    const dir = parseInt(dirStr, 10);

    if (!routeMetrics[route]) {
      routeMetrics[route] = { buses: 0, bunching: 0, gaps: 0, dest: '', speeds: [], gapMinutes: [], dirGaps: {} };
    }
    const rm = routeMetrics[route];
    rm.buses += buses.length;
    if (buses.length > 0 && !rm.dest) rm.dest = buses[0].dest;

    // Collect speeds for this route
    for (const b of buses) {
      const spd = busSpeedCache[b.id];
      if (spd != null && spd > 0) rm.speeds.push(spd);
    }

    // Detect bunching: find pairs of buses very close together
    detectBunching(buses, rm, bunchedIds);

    // Estimate gaps between consecutive buses
    estimateGaps(buses, route, dir, rm);
  }

  // Apply bunching flags to snapshot vehicles
  for (const v of vehicles) {
    v.bunched = bunchedIds.has(v.id) ? 1 : 0;
  }
  totalBunching = countBunchPairs(routeMetrics);

  // Identify long waits
  const { longWaits20, longWaits30 } = identifyLongWaits(routeMetrics);

  // Compute system-wide averages
  const allSpeeds = [];
  const allGaps = [];
  for (const rm of Object.values(routeMetrics)) {
    if (rm.speeds.length > 0) {
      rm.avgSpeed = round1(avg(rm.speeds));
      allSpeeds.push(...rm.speeds);
    } else {
      rm.avgSpeed = null;
    }
    allGaps.push(...rm.gapMinutes);
  }

  const systemAvgSpeed = allSpeeds.length > 0 ? speedSmooth.push(round1(avg(allSpeeds))) : speedSmooth.current();

  // Average rider wait time = E[gap^2] / (2 * E[gap])
  let avgRiderWait = null;
  if (allGaps.length > 0) {
    const meanGap = avg(allGaps);
    const meanGapSq = allGaps.reduce((a, b) => a + b * b, 0) / allGaps.length;
    const rawWait = meanGap > 0 ? round1(meanGapSq / (2 * meanGap)) : null;
    if (rawWait != null) avgRiderWait = waitSmooth.push(rawWait);
  } else {
    avgRiderWait = waitSmooth.current();
  }

  // Smoothed gap counts
  const smoothG30 = Math.round(gap30Smooth.push(longWaits30.length));
  const smoothG20 = Math.round(gap20Smooth.push(longWaits20.length));

  // ── Update DOM ──
  updateSystemStats(vehicles, routeMetrics, totalBunching, systemAvgSpeed, avgRiderWait, smoothG30, smoothG20);
  renderWaitAlerts(longWaits20, longWaits30);
  renderBuses(snapshot);
  renderRouteList(routeMetrics);
}

/** Group vehicles by "route_dir" key */
function groupByRouteDir(vehicles) {
  const groups = new Map();
  for (const v of vehicles) {
    const key = `${v.route}_${v.dir}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(v);
  }
  return groups;
}

/** Detect bunching within a direction group */
function detectBunching(buses, rm, bunchedIds) {
  for (let i = 0; i < buses.length; i++) {
    for (let j = i + 1; j < buses.length; j++) {
      const dist = haversine(
        buses[i].lat, buses[i].lon,
        buses[j].lat, buses[j].lon
      );
      if (dist < CONFIG.bunchingDistanceMeters) {
        rm.bunching++;
        bunchedIds.add(buses[i].id);
        bunchedIds.add(buses[j].id);
      }
    }
  }
}

/** Count total bunched pairs across all routes */
function countBunchPairs(routeMetrics) {
  let total = 0;
  for (const rm of Object.values(routeMetrics)) total += rm.bunching;
  return total;
}

/** Estimate time gaps between consecutive buses on a route/direction */
function estimateGaps(buses, route, dir, rm) {
  if (buses.length <= 1) {
    rm.gaps++;
    return;
  }
  if (buses.length < 3) return; // fewer than 3 gives unreliable spacing

  // Sort buses by position along route
  const isEastWest = Math.abs(buses[0].lon - buses[1].lon) > Math.abs(buses[0].lat - buses[1].lat);
  const sorted = [...buses].sort((a, b) =>
    isEastWest ? a.lon - b.lon : a.lat - b.lat
  );

  // Default speed assumption if no observed speed: 8 mph
  const routeSpeed = rm.speeds.length > 0 ? avg(rm.speeds) : 8;
  const speedMps = (routeSpeed * 1609.34) / 3600;

  let maxGapThisDir = 0;
  for (let i = 0; i < sorted.length - 1; i++) {
    const dist = measureDistance(
      sorted[i].lat, sorted[i].lon,
      sorted[i + 1].lat, sorted[i + 1].lon,
      route
    );
    const gapMin = speedMps > 0 ? (dist / speedMps) / 60 : 0;
    // Cap at 60 min — anything higher is likely a route terminus gap, not a real wait
    const rounded = Math.min(60, Math.round(gapMin));
    rm.gapMinutes.push(rounded);
    maxGapThisDir = Math.max(maxGapThisDir, rounded);
  }
  rm.dirGaps[dir] = maxGapThisDir;
}

/** Identify routes with 20+ and 30+ minute waits */
function identifyLongWaits(routeMetrics) {
  const longWaits20 = [];
  const longWaits30 = [];

  for (const [route, rm] of Object.entries(routeMetrics)) {
    rm.maxGap = rm.gapMinutes.length > 0 ? Math.max(...rm.gapMinutes) : null;

    if (rm.maxGap != null && rm.maxGap >= 20) {
      const dirs = rm.dirGaps;
      const dir0bad = (dirs[0] || 0) >= 20;
      const dir1bad = (dirs[1] || 0) >= 20;
      const dirLabel = (dir0bad && dir1bad) ? '\u2194' : '\u2192';
      const entry = { route, gap: rm.maxGap, bothDirs: dir0bad && dir1bad, dirLabel };
      if (rm.maxGap >= 30) longWaits30.push(entry);
      else longWaits20.push(entry);
    }
    if (rm.gaps > 0) { /* gapRoutes++ if needed later */ }
  }

  longWaits30.sort((a, b) => b.gap - a.gap);
  longWaits20.sort((a, b) => b.gap - a.gap);
  return { longWaits20, longWaits30 };
}

/** Update the system-wide stat cards in the DOM */
function updateSystemStats(vehicles, routeMetrics, totalBunching, systemAvgSpeed, avgRiderWait, smoothG30, smoothG20) {
  dom['stat-buses'].textContent = vehicles.length.toLocaleString();
  dom['stat-routes-count'].textContent = `${Object.keys(routeMetrics).length} routes`;

  dom['stat-bunching'].textContent = totalBunching;
  dom['stat-bunching'].className = `value ${totalBunching > 50 ? 'bad' : totalBunching > 20 ? 'warn' : 'good'}`;

  dom['stat-gaps'].textContent = smoothG30 + smoothG20;

  const speedEl = dom['stat-speed'];
  if (systemAvgSpeed != null) {
    speedEl.textContent = systemAvgSpeed.toFixed(1);
    speedEl.className = `value ${systemAvgSpeed < 6 ? 'bad' : systemAvgSpeed < 8 ? 'warn' : 'accent'}`;
    const hint = dom['speed-hint'];
    if (hint) hint.style.display = 'none';
  } else {
    speedEl.textContent = '\u2014';
  }

  const waitEl = dom['stat-wait'];
  if (avgRiderWait != null) {
    waitEl.textContent = avgRiderWait.toFixed(1);
    waitEl.className = `value ${avgRiderWait > 15 ? 'bad' : avgRiderWait > 10 ? 'warn' : 'accent'}`;
  } else {
    waitEl.textContent = '\u2014';
  }
}

// ═══ LONG WAIT ALERTS ═══
function renderWaitAlerts(waits20, waits30) {
  const container = dom['wait-alerts'];

  if (waits30.length === 0 && waits20.length === 0) {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';

  let html = '';

  if (waits30.length > 0) {
    html += `<div class="wait-row" data-tier="30">
      <span class="wait-count">${waits30.length}</span>
      <span class="wait-label">route${waits30.length !== 1 ? 's' : ''} with 30+ min waits</span>
      <span class="wait-toggle" id="toggle-30">\u25B6</span>
    </div>
    <div class="wait-detail" id="detail-30" style="display:none">
      ${waits30.map(w => {
        const color = routeColor(w.route);
        return `<span class="wait-chip" style="background:${color};color:#fff" data-route="${w.route}">${w.route} <span class="wait-dir">${w.dirLabel}</span><span class="wait-min">${w.gap}m</span></span>`;
      }).join('')}
    </div>`;
  }

  if (waits20.length > 0) {
    html += `<div class="wait-row" data-tier="20">
      <span class="wait-count">${waits20.length}</span>
      <span class="wait-label">route${waits20.length !== 1 ? 's' : ''} with 20\u201330 min waits</span>
      <span class="wait-toggle" id="toggle-20">\u25B6</span>
    </div>
    <div class="wait-detail" id="detail-20" style="display:none">
      ${waits20.map(w => {
        const color = routeColor(w.route);
        return `<span class="wait-chip" style="background:${color};color:#fff" data-route="${w.route}">${w.route} <span class="wait-dir">${w.dirLabel}</span><span class="wait-min">${w.gap}m</span></span>`;
      }).join('')}
    </div>`;
  }

  container.innerHTML = html;

  // Store for highlight access
  container._waits = { 30: waits30, 20: waits20 };

  // Click row → toggle detail AND highlight all those routes on map
  container.querySelectorAll('.wait-row').forEach(row => {
    row.addEventListener('click', () => {
      const tier = row.dataset.tier;
      const detail = document.getElementById(`detail-${tier}`);
      const toggle = document.getElementById(`toggle-${tier}`);
      const waits = container._waits[tier] || [];
      const routes = waits.map(w => w.route);

      if (detail.style.display === 'none') {
        detail.style.display = 'flex';
        toggle.textContent = '\u25BC';
        // Highlight all long-wait routes on the map
        highlightRoutes(routes);
        selectedRoute = null; // clear single selection
      } else {
        detail.style.display = 'none';
        toggle.textContent = '\u25B6';
        clearRouteHighlight();
      }
    });
  });

  // Chip click → highlight single route
  container.querySelectorAll('.wait-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.stopPropagation();
      const route = chip.dataset.route;
      selectedRoute = route;
      highlightRoute(route);
      zoomToRoute(route);
    });
  });
}

// ═══ ROUTE LIST ═══
function renderRouteList(metrics) {
  const list = dom['route-list'];
  const filter = dom['route-search'].value.toLowerCase();

  let routes = Object.entries(metrics).map(([route, m]) => ({
    route, ...m,
  }));

  // Borough filter, Top 25, or Nearby
  if (boroFilter === 'nearby' && userLocation && currentSnapshot) {
    // Find routes with buses within ~0.5 miles of user
    const nearbyRoutes = new Set();
    for (const v of currentSnapshot.vehicles) {
      const dist = haversine(userLocation.lat, userLocation.lon, v.lat, v.lon);
      if (dist < 800) { // ~0.5 miles in meters
        nearbyRoutes.add(v.route);
      }
    }
    routes = routes.filter(r => nearbyRoutes.has(r.route));
    if (nearbyRoutes.size > 0) {
      highlightRoutes([...nearbyRoutes]);
    }
  } else if (boroFilter === 'top25') {
    // Sort all routes by bus count, take top 25
    routes.sort((a, b) => b.buses - a.buses);
    routes = routes.slice(0, 25);
    // Highlight these on the map
    highlightRoutes(routes.map(r => r.route));
  } else if (boroFilter !== 'all') {
    routes = routes.filter(r => {
      const rt = r.route.toUpperCase();
      if (boroFilter === 'Bx') return rt.startsWith('BX');
      if (boroFilter === 'B') return rt.startsWith('B') && !rt.startsWith('BX');
      if (boroFilter === 'S') return rt.startsWith('S');
      if (boroFilter === 'Q') return rt.startsWith('Q');
      if (boroFilter === 'M') return rt.startsWith('M');
      return true;
    });
  }

  // Text filter
  if (filter) {
    routes = routes.filter(r =>
      r.route.toLowerCase().includes(filter) ||
      r.dest.toLowerCase().includes(filter)
    );
  }

  // Sort
  switch (sortMode) {
    case 'bunching':
      routes.sort((a, b) => b.bunching - a.bunching || a.route.localeCompare(b.route));
      break;
    case 'gaps':
      routes.sort((a, b) => b.gaps - a.gaps || a.route.localeCompare(b.route));
      break;
    case 'buses':
      routes.sort((a, b) => b.buses - a.buses || a.route.localeCompare(b.route));
      break;
    case 'speed':
      routes.sort((a, b) => (a.avgSpeed || 99) - (b.avgSpeed || 99) || a.route.localeCompare(b.route));
      break;
    default:
      routes.sort((a, b) => naturalSort(a.route, b.route));
  }

  list.innerHTML = routes.map(r => {
    const color = routeColor(r.route);
    const isSelected = selectedRoute === r.route;
    const spdStr = r.avgSpeed != null ? r.avgSpeed.toFixed(1) : '\u2014';
    const spdClass = r.avgSpeed != null ? (r.avgSpeed < 6 ? 'bad' : r.avgSpeed < 8 ? 'warn' : '') : '';
    return `
      <div class="route-row${isSelected ? ' selected' : ''}" data-route="${r.route}">
        <div><span class="route-badge" style="background:${color}">${r.route}</span></div>
        <div class="route-dest" title="${r.dest}">${r.dest}</div>
        <div class="route-metric">${r.buses}</div>
        <div class="route-metric ${spdClass}">${spdStr}</div>
        <div class="route-metric ${r.bunching > 0 ? 'bad' : ''}">${r.bunching || '\u2014'}</div>
        <div class="route-metric ${r.gaps > 0 ? 'warn' : ''}">${r.gaps || '\u2014'}</div>
      </div>
    `;
  }).join('');

  // Click handlers
  list.querySelectorAll('.route-row').forEach(row => {
    row.addEventListener('click', () => {
      const route = row.dataset.route;
      if (selectedRoute === route) {
        selectedRoute = null;
        clearRouteHighlight();
      } else {
        selectedRoute = route;
        highlightRoute(route);
        zoomToRoute(route);
      }
      // Re-render to update selected state
      renderRouteList(metrics);
    });
  });
}

function zoomToRoute(route) {
  if (!currentSnapshot) return;
  const buses = currentSnapshot.vehicles.filter(v => v.route === route);
  if (buses.length === 0) return;

  const bounds = new maplibregl.LngLatBounds();
  buses.forEach(b => bounds.extend([b.lon, b.lat]));
  map.fitBounds(bounds, { padding: 80, maxZoom: 14 });
}

// ═══ BUS CLICK HANDLER ═══
function setupBusClickHandler() {
  map.on('click', 'bus-dots', (e) => {
    const props = e.features[0].properties;
    const coords = e.features[0].geometry.coordinates;

    const html = `
      <h3>${props.route}</h3>
      <p>\u2192 <span class="val">${props.dest}</span></p>
      <p>Next stop: <span class="val">${props.distFromStop}</span></p>
      ${props.stopsAway != null ? `<p>Stops away: <span class="val">${props.stopsAway}</span></p>` : ''}
      <p style="color:rgba(255,255,255,0.28);font-size:11px;margin-top:6px">Bus #${props.id}</p>
      ${props.bunched == 1 ? '<div class="bunched-tag">\u26A0 Bunched</div>' : ''}
    `;

    new maplibregl.Popup({ offset: 12, closeButton: true })
      .setLngLat(coords)
      .setHTML(html)
      .addTo(map);
  });

  map.on('mouseenter', 'bus-dots', () => {
    map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', 'bus-dots', () => {
    map.getCanvas().style.cursor = '';
  });
}

// ═══ TIMELINE CONTROLS ═══
function setupControls() {
  const slider = dom['timeline-slider'];
  const btnLive = dom['btn-live'];
  const btnPlay = dom['btn-play'];
  const speedEl = dom['timeline-speed'];

  btnLive.addEventListener('click', () => {
    isLive = true;
    isPlaying = false;
    clearInterval(playTimer);
    btnLive.classList.add('active');
    btnPlay.classList.remove('active');
    dom['live-badge'].style.display = 'flex';
    slider.value = slider.max;
    if (currentSnapshot) {
      renderBuses(currentSnapshot);
      computeMetrics(currentSnapshot);
    }
  });

  btnPlay.addEventListener('click', () => {
    if (snapshots.length < 2) return;
    isLive = false;
    isPlaying = !isPlaying;
    btnLive.classList.remove('active');
    dom['live-badge'].style.display = 'none';

    if (isPlaying) {
      btnPlay.classList.add('active');
      btnPlay.textContent = '\u23F8';
      startPlayback();
    } else {
      btnPlay.classList.remove('active');
      btnPlay.textContent = '\u25B6';
      clearInterval(playTimer);
    }
  });

  slider.addEventListener('input', () => {
    if (snapshots.length === 0) return;
    isLive = false;
    btnLive.classList.remove('active');
    dom['live-badge'].style.display = 'none';

    const idx = Math.round((slider.value / 100) * (snapshots.length - 1));
    showSnapshot(idx);
  });

  speedEl.addEventListener('click', () => {
    const speeds = [1, 2, 5, 10, 30];
    const idx = speeds.indexOf(playSpeed);
    playSpeed = speeds[(idx + 1) % speeds.length];
    speedEl.textContent = `${playSpeed}\u00D7`;
    if (isPlaying) {
      clearInterval(playTimer);
      startPlayback();
    }
  });

  // Route search
  dom['route-search'].addEventListener('input', () => {
    if (currentSnapshot) computeMetrics(currentSnapshot);
  });

  // Sort button (cycles through modes)
  dom['sort-btn'].addEventListener('click', () => {
    const modes = ['name', 'buses', 'speed', 'bunching', 'gaps'];
    const labels = ['A\u2013Z', 'Buses', 'Speed', 'Bunch', 'Gaps'];
    const idx = modes.indexOf(sortMode);
    sortMode = modes[(idx + 1) % modes.length];
    dom['sort-btn'].textContent = labels[(idx + 1) % labels.length];
    updateSortHighlight();
    if (currentSnapshot) computeMetrics(currentSnapshot);
  });

  // Column header sorting
  document.querySelectorAll('.col-sort').forEach(col => {
    col.addEventListener('click', () => {
      sortMode = col.dataset.sort;
      updateSortHighlight();
      if (currentSnapshot) computeMetrics(currentSnapshot);
    });
  });

  // Borough filter
  document.querySelectorAll('.boro-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      // Clear map highlight when leaving top25/nearby
      if ((boroFilter === 'top25' || boroFilter === 'nearby') &&
          btn.dataset.boro !== 'top25' && btn.dataset.boro !== 'nearby') {
        clearRouteHighlight();
      }

      // Handle nearby: trigger geolocation
      if (btn.dataset.boro === 'nearby') {
        if (!navigator.geolocation) {
          alert('Geolocation not supported by your browser.');
          return;
        }
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            userLocation = { lat: pos.coords.latitude, lon: pos.coords.longitude };
            boroFilter = 'nearby';
            selectedRoute = null;
            document.querySelectorAll('.boro-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Zoom to user location
            map.flyTo({ center: [userLocation.lon, userLocation.lat], zoom: 14 });
            if (currentSnapshot) computeMetrics(currentSnapshot);
          },
          () => { alert('Could not get your location.'); }
        );
        return;
      }

      boroFilter = btn.dataset.boro;
      selectedRoute = null;
      document.querySelectorAll('.boro-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (boroFilter !== 'top25' && boroFilter !== 'nearby') clearRouteHighlight();
      if (currentSnapshot) computeMetrics(currentSnapshot);
    });
  });
}

function updateSortHighlight() {
  document.querySelectorAll('.col-sort').forEach(col => {
    col.classList.toggle('active', col.dataset.sort === sortMode);
  });
}

function startPlayback() {
  let idx = Math.round(
    (dom['timeline-slider'].value / 100) * (snapshots.length - 1)
  );

  playTimer = setInterval(() => {
    idx++;
    if (idx >= snapshots.length) {
      idx = 0; // loop
    }
    showSnapshot(idx);
    dom['timeline-slider'].value =
      (idx / (snapshots.length - 1)) * 100;
  }, 1000 / playSpeed);
}

function showSnapshot(idx) {
  if (idx < 0 || idx >= snapshots.length) return;
  const snap = snapshots[idx];
  renderBuses(snap);
  computeMetrics(snap);
  dom['timeline-time'].textContent = formatTime(new Date(snap.ts));
  dom['status-text'].textContent = `Snapshot ${idx + 1} of ${snapshots.length}`;
}

function updateTimeline() {
  if (!isLive) return;
  const slider = dom['timeline-slider'];
  slider.max = 100;
  slider.value = 100;
  if (currentSnapshot) {
    dom['timeline-time'].textContent = formatTime(new Date(currentSnapshot.ts));
    dom['timeline-date'].textContent = formatDate(new Date(currentSnapshot.ts));
  }
}

// ═══ UTILITIES ═══

/** Haversine great-circle distance in meters */
function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Measure distance between two GPS points, preferring along-route distance.
 * Falls back to haversine when route shape is unavailable.
 */
function measureDistance(lat1, lon1, lat2, lon2, routeId) {
  const rd = routeDistance(lat1, lon1, lat2, lon2, routeId);
  return rd != null ? rd : haversine(lat1, lon1, lat2, lon2);
}

/**
 * Snap a GPS point to the nearest segment on a polyline.
 * Returns { idx: segment index, frac: fractional position along segment }.
 */
function snapToPolyline(lat, lon, coords) {
  let bestDist = Infinity;
  let bestIdx = 0;
  let bestFrac = 0;

  for (let i = 0; i < coords.length - 1; i++) {
    const ax = coords[i][0], ay = coords[i][1];
    const bx = coords[i + 1][0], by = coords[i + 1][1];
    const dx = bx - ax, dy = by - ay;
    const lenSq = dx * dx + dy * dy;
    let t = lenSq > 0 ? ((lon - ax) * dx + (lat - ay) * dy) / lenSq : 0;
    t = Math.max(0, Math.min(1, t));
    const px = ax + t * dx, py = ay + t * dy;
    const d = (lon - px) ** 2 + (lat - py) ** 2;
    if (d < bestDist) {
      bestDist = d;
      bestIdx = i;
      bestFrac = t;
    }
  }
  return { idx: bestIdx, frac: bestFrac };
}

/**
 * Compute distance along a route shape between two GPS points.
 * Snaps each point to the nearest segment on the route polyline,
 * then sums the along-route distance between the two snap locations.
 * Returns distance in meters, or null if route shape is unavailable.
 */
function routeDistance(lat1, lon1, lat2, lon2, routeId) {
  if (!routeShapeIndex) return null;
  const feature = routeShapeIndex.get(routeId);
  if (!feature || feature.geometry.type !== 'LineString') return null;

  const coords = feature.geometry.coordinates; // [lon, lat] pairs
  if (coords.length < 2) return null;

  const snap1 = snapToPolyline(lat1, lon1, coords);
  const snap2 = snapToPolyline(lat2, lon2, coords);

  // Ensure we measure from the earlier point along the line to the later
  let startSnap = snap1, endSnap = snap2;
  if (snap1.idx > snap2.idx || (snap1.idx === snap2.idx && snap1.frac > snap2.frac)) {
    startSnap = snap2;
    endSnap = snap1;
  }

  // Sum haversine distances along the polyline from startSnap to endSnap
  let dist = 0;

  // Partial first segment: from snap point to end of segment
  const s0 = coords[startSnap.idx], s1 = coords[startSnap.idx + 1];
  const startLon = s0[0] + startSnap.frac * (s1[0] - s0[0]);
  const startLat = s0[1] + startSnap.frac * (s1[1] - s0[1]);
  if (startSnap.idx === endSnap.idx) {
    // Both on same segment
    const eLon = s0[0] + endSnap.frac * (s1[0] - s0[0]);
    const eLat = s0[1] + endSnap.frac * (s1[1] - s0[1]);
    return haversine(startLat, startLon, eLat, eLon);
  }
  dist += haversine(startLat, startLon, s1[1], s1[0]);

  // Full intermediate segments
  for (let i = startSnap.idx + 1; i < endSnap.idx; i++) {
    dist += haversine(coords[i][1], coords[i][0], coords[i + 1][1], coords[i + 1][0]);
  }

  // Partial last segment: from start of segment to snap point
  const e0 = coords[endSnap.idx], e1 = coords[endSnap.idx + 1];
  const endLon = e0[0] + endSnap.frac * (e1[0] - e0[0]);
  const endLat = e0[1] + endSnap.frac * (e1[1] - e0[1]);
  dist += haversine(e0[1], e0[0], endLat, endLon);

  return dist;
}

/** Round to 1 decimal place */
function round1(n) {
  return Math.round(n * 10) / 10;
}

/** Average of an array of numbers */
function avg(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

/**
 * Simple rolling average with a fixed window size.
 * push(value) adds a value and returns the current smoothed average.
 * current() returns the latest average without adding a new value.
 */
function createRollingAvg(windowSize) {
  const buffer = [];
  function compute() {
    return buffer.length > 0 ? buffer.reduce((a, b) => a + b, 0) / buffer.length : null;
  }
  return {
    push(value) {
      buffer.push(value);
      if (buffer.length > windowSize) buffer.shift();
      return compute();
    },
    current() {
      return compute();
    },
  };
}

function formatTime(d) {
  return d.toLocaleTimeString('en-US', {
    hour: 'numeric', minute: '2-digit',
    timeZone: 'America/New_York',
  });
}

function formatDate(d) {
  return d.toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
    timeZone: 'America/New_York',
  });
}

// Curated palette of 24 vivid, distinguishable colors for route lines
const ROUTE_COLORS = [
  '#dde44c', '#ff7c53', '#4ecdc4', '#e7466d', '#217ebe',
  '#9b9fbc', '#57aa4a', '#f7b731', '#a55eea', '#26de81',
  '#fd9644', '#45aaf2', '#cea9be', '#eb3b5a', '#20bf6b',
  '#fc5c65', '#2bcbba', '#fa8231', '#4b7bec', '#fed330',
  '#778ca3', '#a5b1c2', '#d1d8e0', '#f8b500',
];

const routeColorCache = new Map();
function routeColor(route) {
  let color = routeColorCache.get(route);
  if (color) return color;
  let hash = 0;
  for (let i = 0; i < route.length; i++) {
    hash = route.charCodeAt(i) + ((hash << 5) - hash);
  }
  color = ROUTE_COLORS[Math.abs(hash) % ROUTE_COLORS.length];
  routeColorCache.set(route, color);
  return color;
}

function naturalSort(a, b) {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
}

function updateLoadingText(text) {
  dom['loading-text'].textContent = text;
}

function hideLoading() {
  const overlay = dom['loading-overlay'];
  overlay.style.opacity = '0';
  overlay.style.transition = 'opacity 0.5s';
  setTimeout(() => overlay.style.display = 'none', 500);
}

// ═══ BUS DIRECTION ARROW ICON (SDF) ═══
function createBusPointerIcon() {
  const size = 20;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  // Draw a small chevron/arrow pointing UP
  // SDF mode: white = inside shape, black = outside
  const cx = size / 2;

  ctx.beginPath();
  ctx.moveTo(cx, 2);        // top point
  ctx.lineTo(cx + 6, 14);   // bottom right
  ctx.lineTo(cx, 10);       // inner notch
  ctx.lineTo(cx - 6, 14);   // bottom left
  ctx.closePath();

  ctx.fillStyle = '#ffffff';
  ctx.fill();

  const imageData = ctx.getImageData(0, 0, size, size);
  map.addImage('bus-arrow', imageData, { pixelRatio: 2, sdf: true });
}

// ═══ START ═══
init();
