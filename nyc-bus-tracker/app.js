/**
 * NYC Bus Tracker — Dashboard
 * Real-time animated map of all NYC buses with performance metrics.
 */

// ═══ CONFIG ═══
const CONFIG = {
  // MTA SIRI API (client-side — supports CORS)
  // MTA renamed this endpoint in 2026: the old vehicle-monitoring.json now
  // 302-redirects to -v2 and drops the query string on the way, so fetches
  // silently came back empty. Point straight at the v2 path.
  apiBase: 'https://bustime.mta.info/api/siri/vehicle-monitoring-v2.json',
  // API key — defaults to the baked-in MTA BusTime key (public, rate-limited
  // per-key by MTA). Override via URL param ?key=XXX to use a different one.
  apiKey: new URLSearchParams(window.location.search).get('key')
    || '5ecc401b-fc5b-4048-91bc-df104885f171',
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
    'borough-filter', 'route-list-header',
    'tray', 'tray-handle', 'tray-body', 'tray-summary', 'tray-hint',
    'tray-current-period', 'tray-cards', 'tray-empty', 'tray-table-body',
    'tray-coverage-stats', 'tray-boro-trends', 'tray-boro-empty',
    'tray-ridership', 'tray-ridership-empty',
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

    // Load route shapes and historical trends in background
    loadRouteShapes();
    loadTrends();

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
    // but drops onward calls and stop-level details we don't need.
    // NOTE: no &version=2 — the version is now in the path (-v2.json). Passing
    // version=2 as a query param makes the endpoint return an XML error page
    // instead of JSON.
    const url = `${CONFIG.apiBase}?key=${CONFIG.apiKey}&VehicleMonitoringDetailLevel=basic`;
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

// ── Real-time movement engine ──
// The MTA feed only gives new positions every ~30s. To make dots move
// continuously instead of snapping, we glide each bus from its last-rendered
// position to its newest reported position across the whole inter-fetch gap.
// A persistent rAF loop interpolates every frame; when a new snapshot arrives,
// we re-anchor the tween from wherever each dot currently sits on screen.
const BUS_TWEEN_MS = 30000;          // span one fetch interval — continuous motion
const BUS_RENDER_THROTTLE_MS = 100;  // ~10 fps setData; smooth for slow dots, easy on CPU
let busTweenTargets = [];            // [{ id, from:[lon,lat], to:[lon,lat], props }]
let busRenderedPos = new Map();      // id -> [lon,lat] currently shown (tween anchor)
let busTweenStart = 0;
let busRafHandle = null;
let busLastRenderTs = 0;

function lerp(a, b, t) { return a + (b - a) * t; }

function busFrameFeatures(t) {
  // cubic-ease-out feels natural and avoids a hard stop at the end
  const e = 1 - Math.pow(1 - t, 3);
  return busTweenTargets.map(item => {
    const lon = lerp(item.from[0], item.to[0], e);
    const lat = lerp(item.from[1], item.to[1], e);
    return {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: item.props,
    };
  });
}

function busAnimationStep(now) {
  if (!busTweenStart) busTweenStart = now;
  const t = Math.min(1, (now - busTweenStart) / BUS_TWEEN_MS);

  // Throttle the actual setData calls; interpolation math stays per-frame-cheap.
  if (now - busLastRenderTs >= BUS_RENDER_THROTTLE_MS || t >= 1) {
    busLastRenderTs = now;
    const features = busFrameFeatures(t);
    const src = map.getSource('buses');
    if (src) src.setData({ type: 'FeatureCollection', features });
    // Remember where each dot is now, so the next snapshot tweens from here.
    for (const f of features) {
      busRenderedPos.set(f.properties.id, f.geometry.coordinates);
    }
  }

  // Keep looping while still gliding. Once we've arrived (t>=1) we idle the
  // loop to save CPU; the next snapshot restarts it.
  if (t < 1) {
    busRafHandle = requestAnimationFrame(busAnimationStep);
  } else {
    busRafHandle = null;
  }
}

function renderBuses(snapshot) {
  const buildProps = v => ({
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
  });

  // Build tween targets: each bus glides from where it's currently drawn
  // (or its own new position, if we've never seen it) to the new reading.
  // GUARD: if the new position is implausibly far from the last one — more
  // than a bus could travel in one fetch interval — don't glide across it.
  // That "teleport" comes from a stale snapshot (e.g. after a backgrounded
  // tab), a GPS glitch, or a vehicle re-assigned to another route, and gliding
  // it over BUS_TWEEN_MS looks like the dot rocketing across the map. Snap
  // instead (from = to) so it just appears at the new spot.
  // ~50 mph express bus over a 30s interval ≈ 670 m; cap a bit above that.
  const MAX_GLIDE_M = 900;
  busTweenTargets = snapshot.vehicles.map(v => {
    const to = [v.lon, v.lat];
    let from = busRenderedPos.get(v.id) || to;
    if (from !== to && haversine(from[1], from[0], to[1], to[0]) > MAX_GLIDE_M) {
      from = to; // snap — don't animate an unrealistic jump
    }
    return { id: v.id, from, to, props: buildProps(v) };
  });
  // Drop stale anchors for buses no longer present so the Map doesn't grow.
  const liveIds = new Set(snapshot.vehicles.map(v => v.id));
  for (const id of busRenderedPos.keys()) {
    if (!liveIds.has(id)) busRenderedPos.delete(id);
  }

  // Initial frame (t=0) so the source has data immediately on first render.
  const geojson = { type: 'FeatureCollection', features: busFrameFeatures(0) };

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

  // (Re)start the glide toward the new positions. Re-anchoring from the
  // current on-screen position means an early snapshot doesn't cause a jump.
  busTweenStart = 0;
  if (busRafHandle) cancelAnimationFrame(busRafHandle);
  busRafHandle = requestAnimationFrame(busAnimationStep);

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
  // Compute per-route averages, then system-wide as mean of route averages
  // (each route weighted equally, consistent with MTA route-level reporting)
  const routeAvgSpeeds = [];
  const allGaps = [];
  for (const rm of Object.values(routeMetrics)) {
    if (rm.speeds.length > 0) {
      rm.avgSpeed = round1(avg(rm.speeds));
      routeAvgSpeeds.push(rm.avgSpeed);
    } else {
      rm.avgSpeed = null;
    }
    allGaps.push(...rm.gapMinutes);
  }

  const systemAvgSpeed = routeAvgSpeeds.length > 0 ? speedSmooth.push(round1(avg(routeAvgSpeeds))) : speedSmooth.current();

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

// ═══ CONTROLS ═══
function setupControls() {
  // Weekly trends tray toggle
  const tray = dom['tray'];
  const handle = dom['tray-handle'];
  const hint = dom['tray-hint'];
  if (handle && tray) {
    handle.addEventListener('click', () => {
      const open = tray.getAttribute('aria-expanded') === 'true';
      tray.setAttribute('aria-expanded', open ? 'false' : 'true');
      if (hint) hint.textContent = open ? 'click to expand' : 'click to collapse';
    });
  }

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

// Timeline playback removed; keep no-ops so any legacy call sites remain safe.
function startPlayback() {}
function showSnapshot() {}
function updateTimeline() {}

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

// ═══ HISTORICAL TRENDS (tray) ═══
async function loadTrends() {
  // Fetch both the rolled-up summary (latest.json) and the full weekly series
  // (weekly.json). We show whatever is available; missing files are tolerated.
  const [latestRes, weeklyRes, routesRes, ridershipRes] = await Promise.all([
    fetch('data/summary/latest.json').catch(() => null),
    fetch('data/summary/weekly.json').catch(() => null),
    fetch('data/summary/weekly-routes.json').catch(() => null),
    fetch('data/ridership/routes-monthly.json').catch(() => null),
  ]);

  let latest = null;
  let weekly = [];
  let weeklyRoutes = {};
  let ridership = null;
  if (latestRes?.ok) { try { latest = await latestRes.json(); } catch {} }
  if (weeklyRes?.ok) { try { weekly = await weeklyRes.json(); } catch {} }
  if (routesRes?.ok) { try { weeklyRoutes = await routesRes.json(); } catch {} }
  if (ridershipRes?.ok) { try { ridership = await ridershipRes.json(); } catch {} }

  renderTrends(latest, weekly);
  renderBoroughTrends(latest, weeklyRoutes);
  renderRidershipTrends(ridership);
}

// Curated watch list: the two busiest routes in each borough (by average buses
// on the road), used as a stable baseline for tracking speed over time. Keys
// are the borough codes used in the daily/weekly roll-ups; route strings match
// the shortnames in weekly-routes.json ("+" marks a Select Bus Service route).
// Kept fixed (not recomputed each week) so the time series stays comparable.
const WATCH_ROUTES = {
  M:  { name: 'Manhattan',     routes: ['M15+', 'M4'] },
  Bx: { name: 'The Bronx',     routes: ['BX12+', 'BX36'] },
  B:  { name: 'Brooklyn',      routes: ['B6', 'B41'] },
  Q:  { name: 'Queens',        routes: ['Q44+', 'Q58'] },
  S:  { name: 'Staten Island', routes: ['S79+', 'S53'] },
};

// A week only enters the trends if it has a full 7 days AND at least this share
// of operating hours sampled. Thin, sparsely-collected weeks (some June weeks
// dipped to ~9% coverage) would otherwise drag the line around on very little
// data. This is the same "comparable" bar the week-by-week table uses.
const TREND_COVERAGE_MIN = 50;

/** Build the "Speed over time, by borough" section: for each borough, its
 *  aggregate weekly speed plus its two busiest routes, each as a mini trend
 *  (latest value, net trend over the window, and a line + trend-line chart).
 *  Uses only full, adequately-covered weeks so thin weeks don't distort it. */
function renderBoroughTrends(latest, weeklyRoutes) {
  const host = dom['tray-boro-trends'];
  if (!host) return;

  // Full weekly history, gated on coverage (each row carries a per-borough slice).
  const fullWeeks = (latest?.weeklyHistory || [])
    .filter(w => w.days >= 7 && w.coveragePct >= TREND_COVERAGE_MIN);
  const emptyEl = dom['tray-boro-empty'];

  // Need at least two full weeks to show a change; otherwise keep the note.
  if (fullWeeks.length < 1) {
    if (emptyEl) emptyEl.style.display = '';
    host.querySelectorAll('.boro-trend').forEach(n => n.remove());
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';

  // Speed series (aligned to fullWeeks order) for a borough code.
  const boroSpeedSeries = code =>
    fullWeeks.map(w => w.byBorough?.[code]?.avgSpeed ?? null);

  // Speed series for one route, aligned to the same weeks as fullWeeks so the
  // sparkline lines up. weeklyRoutes[route] is a chronological array of periods.
  const routePeriods = new Set(fullWeeks.map(w => w.period));
  const routeSpeedSeries = route => {
    const hist = weeklyRoutes?.[route] || [];
    const byPeriod = {};
    for (const row of hist) {
      if (row.daysSeen >= 7 && routePeriods.has(row.period)) {
        byPeriod[row.period] = row.avgSpeed ?? null;
      }
    }
    return fullWeeks.map(w => byPeriod[w.period] ?? null);
  };

  const blocks = [];
  for (const [code, meta] of Object.entries(WATCH_ROUTES)) {
    const tiles = [];
    tiles.push(miniTrend(meta.name, 'borough avg', boroSpeedSeries(code)));
    for (const route of meta.routes) {
      tiles.push(miniTrend(route, 'route', routeSpeedSeries(route)));
    }
    blocks.push(`<div class="boro-trend">${tiles.join('')}</div>`);
  }

  // Remove any prior render, then insert fresh blocks (keep empty note in DOM).
  host.querySelectorAll('.boro-trend').forEach(n => n.remove());
  host.insertAdjacentHTML('beforeend', blocks.join(''));
}

/** "27,848" under 100k, "114k" under 1M, "1.38M" above. Riders, not mph. */
function fmtRiders(n) {
  if (n == null) return '—';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n >= 100000) return Math.round(n / 1000) + 'k';
  return Math.round(n).toLocaleString('en-US');
}

/** "People carried, by route" tray section: systemwide + watch-route tiles on
 *  the monthly APC ridership series, plus a leaderboard of the top routes in
 *  the latest month with month-over-month change. Data arrives monthly (with a
 *  ~1 month publication lag), unlike the weekly speed metrics above it. */
function renderRidershipTrends(data) {
  const host = dom['tray-ridership'];
  if (!host) return;
  const emptyEl = dom['tray-ridership-empty'];
  if (!data?.months?.length || !data.routes) {
    if (emptyEl) emptyEl.style.display = '';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';

  const months = data.months;
  const li = months.length - 1;
  const monthName = (ym) => {
    const [y, m] = ym.split('-').map(Number);
    return new Date(y, m - 1, 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
  };

  const tile = (label, kind, series) => {
    const latestVal = series[li];
    const t = linTrend(series);
    let changeHtml = '';
    if (t && series[li - 1] > 0 && latestVal != null) {
      const momPct = 100 * (latestVal - series[li - 1]) / series[li - 1];
      const arrow = momPct > 0.05 ? '▲' : momPct < -0.05 ? '▼' : '—';
      const cls = momPct > 0.05 ? 'up' : momPct < -0.05 ? 'down' : 'flat';
      changeHtml = `<div class="trend-change ${cls}">${arrow} ${Math.abs(momPct).toFixed(1)}% vs prior month</div>`;
    }
    return `<div class="mini-trend mini-${kind}">
      <div class="mini-label">${label}</div>
      <div class="mini-value">${fmtRiders(latestVal)}<span class="mini-unit">riders/wkday</span></div>
      ${changeHtml}
      ${sparkTrend(series, true)}
    </div>`;
  };

  // Row 1: the system, then the same watch routes as the speed section.
  const tiles = [tile('All NYC buses', 'boro', data.system.wdAvg)];
  for (const meta of Object.values(WATCH_ROUTES)) {
    for (const route of meta.routes) {
      const rec = data.routes[route];
      if (rec) tiles.push(tile(route, 'route', rec.wdAvg));
    }
  }

  // Leaderboard: top 12 routes by latest-month average weekday riders.
  const ranked = Object.entries(data.routes)
    .map(([route, rec]) => ({ route, now: rec.wdAvg[li], prev: rec.wdAvg[li - 1] }))
    .filter((r) => r.now > 0)
    .sort((a, b) => b.now - a.now)
    .slice(0, 12);
  const rows = ranked.map((r, i) => {
    const mom = r.prev > 0 ? 100 * (r.now - r.prev) / r.prev : null;
    const momHtml = mom == null ? '—'
      : `<span class="${mom > 0.05 ? 'rid-up' : mom < -0.05 ? 'rid-down' : ''}">${mom > 0 ? '+' : ''}${mom.toFixed(1)}%</span>`;
    return `<tr>
      <td class="num">${i + 1}</td>
      <td class="rid-route">${r.route}</td>
      <td class="num">${fmtRiders(r.now)}</td>
      <td class="num">${momHtml}</td>
    </tr>`;
  }).join('');

  host.innerHTML = `
    <div class="boro-trend rid-tiles">${tiles.join('')}</div>
    <div class="rid-board">
      <div class="rid-board-title">Busiest routes, ${monthName(months[li])} — avg weekday riders</div>
      <table class="tray-table rid-table">
        <thead><tr><th class="num">#</th><th>Route</th><th class="num">Riders/wkday</th><th class="num">vs prior mo.</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  host.appendChild(emptyEl); // keep the empty-note node in the DOM for reuse
  if (emptyEl) emptyEl.style.display = 'none';
}

/** Least-squares linear fit over a series (oldest→newest, nulls skipped).
 *  x is the position in the series so gaps count as elapsed time. Returns the
 *  slope/intercept plus the net change the trend line implies across the span
 *  (fitted last minus fitted first) — a stable "faster or slower over time"
 *  figure that doesn't swing with a single noisy week. Null if <2 points. */
function linTrend(series) {
  const pts = series.map((v, i) => ({ i, v })).filter(p => p.v != null);
  if (pts.length < 2) return null;
  const m = pts.length;
  const sx = pts.reduce((s, p) => s + p.i, 0);
  const sy = pts.reduce((s, p) => s + p.v, 0);
  const sxx = pts.reduce((s, p) => s + p.i * p.i, 0);
  const sxy = pts.reduce((s, p) => s + p.i * p.v, 0);
  const denom = m * sxx - sx * sx;
  const slope = denom !== 0 ? (m * sxy - sx * sy) / denom : 0;
  const intercept = (sy - slope * sx) / m;
  const firstI = pts[0].i;
  const lastI = pts[pts.length - 1].i;
  return {
    pts, slope, intercept, firstI, lastI,
    weeks: pts.length,
    netOverWindow: slope * (lastI - firstI),
    fit: i => intercept + slope * i,
  };
}

/** A calm alternative to jumpy bars: the weekly values as a faint line, with a
 *  bold straight trend line (the least-squares fit) laid over them and the
 *  latest point marked. The trend line is what carries the "up or down over
 *  time" read; the faint line keeps the real data visible. `higherIsBetter`
 *  colors the trend green/red by whether the slope is good news. */
function sparkTrend(series, higherIsBetter = true) {
  const t = linTrend(series);
  if (!t) return '';
  const W = 100, H = 26, pad = 3, n = series.length;
  const xOf = i => n > 1 ? (i / (n - 1)) * (W - 2 * pad) + pad : W / 2;
  const ys = [...t.pts.map(p => p.v), t.fit(t.firstI), t.fit(t.lastI)];
  const min = Math.min(...ys), max = Math.max(...ys), range = max - min || 1;
  const yOf = v => (H - pad) - ((v - min) / range) * (H - 2 * pad);

  const actual = t.pts
    .map((p, k) => `${k ? 'L' : 'M'}${xOf(p.i).toFixed(1)} ${yOf(p.v).toFixed(1)}`)
    .join(' ');
  const good = t.slope === 0 ? null : (t.slope > 0) === higherIsBetter;
  const trendColor = good === null ? 'var(--text-tertiary)'
    : good ? 'var(--vc-goodest-green)' : 'var(--vc-baddest-red)';
  const last = t.pts[t.pts.length - 1];

  return `<svg class="spark-trend" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <path d="${actual}" fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="1" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    <line x1="${xOf(t.firstI).toFixed(1)}" y1="${yOf(t.fit(t.firstI)).toFixed(1)}" x2="${xOf(t.lastI).toFixed(1)}" y2="${yOf(t.fit(t.lastI)).toFixed(1)}" stroke="${trendColor}" stroke-width="2" vector-effect="non-scaling-stroke"/>
    <circle cx="${xOf(last.i).toFixed(1)}" cy="${yOf(last.v).toFixed(1)}" r="1.9" fill="rgba(255,255,255,0.6)"/>
  </svg>`;
}

/** One compact speed tile: label, latest full-week mph, the net trend across
 *  every full week tracked (not the noisy week-over-week delta), and a line +
 *  trend-line chart. `series` is speeds (mph) or nulls, oldest first, aligned
 *  across a borough's tiles so the weeks match up. */
function miniTrend(label, kind, series) {
  const valid = series.filter(v => v != null);
  const latestVal = valid.length ? valid[valid.length - 1] : null;

  // Headline figure = the trend across the whole tracked window (higher speed
  // is better), so it reflects direction over time rather than last week's wobble.
  const t = linTrend(series);
  let changeHtml = '';
  if (t) {
    const net = round1(t.netOverWindow);
    if (net !== 0) {
      const arrow = net > 0 ? '▲' : '▼';
      const cls = net > 0 ? 'up' : 'down';
      changeHtml = `<div class="trend-change ${cls}">${arrow} ${Math.abs(net).toFixed(1)} over ${t.weeks} wks</div>`;
    } else {
      changeHtml = `<div class="trend-change flat">— flat over ${t.weeks} wks</div>`;
    }
  }

  const sparkHtml = sparkTrend(series, true);

  const valueHtml = latestVal != null
    ? `${latestVal}<span class="mini-unit">mph</span>`
    : '<span class="mini-nodata">no full week</span>';

  return `<div class="mini-trend mini-${kind === 'borough avg' ? 'boro' : 'route'}">
    <div class="mini-label">${label}</div>
    <div class="mini-value">${valueHtml}</div>
    ${changeHtml}
    ${sparkHtml}
  </div>`;
}

/** Render the bottom tray: collapsed headline + expanded cards + weekly table. */
function renderTrends(data, weeklyAll) {
  const summaryEl = dom['tray-summary'];
  const periodEl = dom['tray-current-period'];
  const cardsEl = dom['tray-cards'];
  const emptyEl = dom['tray-empty'];
  const tbody = dom['tray-table-body'];

  // ── Current and prior full week from latest.json ──
  const thisWeek = data?.thisWeek?.days >= 7 ? data.thisWeek : null;
  const lastWeek = data?.lastWeek?.days >= 7 ? data.lastWeek : null;

  // Collapsed-row summary text — lead with the time-of-day-normalized figures
  // (the comparable ones), falling back to raw for any legacy pre-norm row.
  if (summaryEl) {
    const twSpeed = thisWeek?.avgSpeedHourNorm ?? thisWeek?.avgSpeed;
    const twWait = thisWeek?.avgWaitHourNorm ?? thisWeek?.avgWait;
    if (twSpeed != null) {
      const bits = [
        `${twSpeed} mph`,
        twWait != null ? `${twWait} min wait` : null,
        thisWeek.avgReliability != null ? `${thisWeek.avgReliability}% reliable` : null,
        thisWeek.bunchPer100Buses != null ? `${thisWeek.bunchPer100Buses} bunched/100 buses` : null,
        thisWeek.coveragePct != null ? `${thisWeek.coveragePct}% coverage` : null,
      ].filter(Boolean);
      summaryEl.textContent = `Week of ${thisWeek.startDate}: ${bits.join(' · ')}`;
    } else if (weeklyAll && weeklyAll.length > 0) {
      const partial = weeklyAll[weeklyAll.length - 1];
      summaryEl.textContent = `In progress: ${partial.period} (${partial.days}/7 days collected)`;
    } else {
      summaryEl.textContent = 'Collecting data \u2014 first full week rolls up Mon, May 4';
    }
  }
  if (periodEl) {
    periodEl.textContent = thisWeek
      ? `ISO week ${thisWeek.period} · ${thisWeek.startDate} to ${thisWeek.endDate} · ${thisWeek.totalSnapshots?.toLocaleString?.() ?? thisWeek.totalSnapshots} snapshots across ${thisWeek.days} days`
      : 'Waiting for the first complete ISO week (Monday through Sunday).';
  }

  // ── Expanded cards ──
  if (cardsEl) {
    const cards = [];
    const pushIfPresent = (label, unit, field, direction) => {
      if (thisWeek?.[field] == null) return;
      const change = lastWeek?.[field] != null
        ? round1(thisWeek[field] - lastWeek[field]) : null;
      cards.push(trendCard(
        label,
        thisWeek[field],
        unit,
        change,
        direction,
        `Week of ${thisWeek.startDate}`,
        fullWeeksField(data?.weeklyHistory, field),
      ));
    };
    // Cards use the time-of-day-normalized metrics (comparable week-over-week).
    pushIfPresent('Avg speed', 'mph', 'avgSpeedHourNorm', 'higher is better');
    pushIfPresent('Avg wait', 'min', 'avgWaitHourNorm', 'lower is better');
    pushIfPresent('Reliability', '%', 'avgReliability', 'higher is better');
    pushIfPresent('Bunching', '/100 buses', 'bunchPer100Buses', 'lower is better');
    pushIfPresent('20+ min gaps', '/snap', 'avgBigGap20PerSnap', 'lower is better');
    pushIfPresent('Active buses', '', 'avgActiveBuses', 'higher is better');

    // Monthly roll-ups, only when we have a full calendar month of data
    const thisMonth = data?.thisMonth?.days >= 28 ? data.thisMonth : null;
    const lastMonth = data?.lastMonth?.days >= 28 ? data.lastMonth : null;
    const pushMonth = (label, unit, field, direction) => {
      if (thisMonth?.[field] == null) return;
      const change = lastMonth?.[field] != null
        ? round1(thisMonth[field] - lastMonth[field]) : null;
      cards.push(trendCard(
        label,
        thisMonth[field],
        unit,
        change,
        direction,
        thisMonth.period,
        fullMonthsField(data?.monthlyHistory, field),
      ));
    };
    pushMonth('Monthly speed', 'mph', 'avgSpeedHourNorm', 'higher is better');
    pushMonth('Monthly reliability', '%', 'avgReliability', 'higher is better');
    pushMonth('Monthly bunching', '/100 buses', 'bunchPer100Buses', 'lower is better');

    if (cards.length > 0) {
      if (emptyEl) emptyEl.style.display = 'none';
      // Replace cards but keep the empty placeholder in DOM for re-use
      cardsEl.innerHTML = cards.join('');
    } else if (emptyEl) {
      // Keep empty state visible, but clear any stale cards
      const existing = cardsEl.querySelectorAll('.trend-card');
      existing.forEach(n => n.remove());
      emptyEl.style.display = 'flex';
      cardsEl.appendChild(emptyEl); // ensure it's the rendered child
    }
  }

  // ── Collection coverage stats (transparency drawer) ──
  const covEl = dom['tray-coverage-stats'];
  if (covEl) {
    const cur = data?.current;
    if (cur?.date) {
      const bits = [
        `Latest daily roll-up: <strong>${cur.date}</strong>`,
        cur.snapshotCount != null ? `${cur.snapshotCount.toLocaleString()} snapshots` : null,
        cur.totalRoutes != null ? `${cur.totalRoutes} routes seen` : null,
        cur.activeBusesPeak != null ? `peak ${cur.activeBusesPeak.toLocaleString()} buses` : null,
      ].filter(Boolean);
      const totalSnaps = (weeklyAll || []).reduce((s, w) => s + (w.totalSnapshots || 0), 0);
      const totalDays = (weeklyAll || []).reduce((s, w) => s + (w.days || 0), 0);
      covEl.innerHTML = bits.join(' &middot; ')
        + (totalSnaps > 0
            ? `. Lifetime so far: <strong>${totalSnaps.toLocaleString()}</strong> snapshots across <strong>${totalDays}</strong> day${totalDays !== 1 ? 's' : ''}.`
            : '.');
    } else {
      covEl.textContent = 'No daily roll-up yet — first one lands ~1 AM ET the morning after the first full collection day.';
    }
  }

  // ── Week-by-week table ──
  if (tbody) {
    const rows = Array.isArray(weeklyAll) ? [...weeklyAll] : [];
    if (rows.length === 0) {
      tbody.innerHTML = '<tr class="tray-table-empty"><td colspan="11">No weekly rows yet. The first row appears the morning after the first Monday\u2013Sunday window completes.</td></tr>';
    } else {
      rows.reverse(); // newest first
      const currentPeriod = thisWeek?.period;
      const cell = v => v == null ? '\u2014' : (typeof v === 'number' ? v.toLocaleString() : v);
      tbody.innerHTML = rows.map(w => {
        const isPartial = w.days < 7;
        // A week is "not comparable" if it's partial or thin on coverage; mark
        // it so it isn't read head-to-head with full weeks.
        const lowCoverage = w.coveragePct != null && w.coveragePct < 50;
        const notComparable = isPartial || lowCoverage;
        const rowCls = w.period === currentPeriod ? 'current' : (notComparable ? 'partial' : '');
        const daysCell = isPartial ? `${w.days}/7 *` : `${w.days}`;
        // Prefer the time-of-day-normalized figures (fall back to raw only if a
        // legacy row predates normalization).
        const spd = w.avgSpeedHourNorm ?? w.avgSpeed;
        const wait = w.avgWaitHourNorm ?? w.avgWait;
        const bunch = w.bunchPer100Buses;
        const covCell = w.coveragePct != null
          ? `${w.coveragePct}%${lowCoverage ? ' *' : ''}` : '\u2014';
        return `<tr class="${rowCls}">
          <td>${w.period}</td>
          <td>${w.startDate} &ndash; ${w.endDate}</td>
          <td class="num">${daysCell}</td>
          <td class="num">${covCell}</td>
          <td class="num">${cell(spd)}</td>
          <td class="num">${cell(wait)}</td>
          <td class="num">${cell(w.avgReliability)}</td>
          <td class="num">${cell(bunch)}</td>
          <td class="num">${cell(w.avgBigGap20PerSnap)}</td>
          <td class="num">${cell(w.avgActiveBuses)}</td>
          <td class="num">${cell(w.avgRoutes)}</td>
        </tr>`;
      }).join('');
    }
  }
}

/** Filter history arrays to only include full periods */
function fullWeeksField(history, field) {
  return history?.filter(w => w.days >= 7).map(w => w[field]) || [];
}
function fullMonthsField(history, field) {
  return history?.filter(m => m.days >= 28).map(m => m[field]) || [];
}

function trendCard(label, value, unit, change, direction, period, sparkData) {
  // Determine change direction and formatting
  let changeHtml = '';
  if (change != null && change !== 0) {
    const isGood = direction === 'higher is better' ? change > 0 : change < 0;
    const arrow = change > 0 ? '\u25B2' : '\u25BC';
    const cls = isGood ? 'up' : 'down';
    changeHtml = `<div class="trend-change ${cls}">${arrow} ${Math.abs(change).toFixed(1)} vs prior</div>`;
  } else if (change === 0) {
    changeHtml = `<div class="trend-change flat">\u2014 no change</div>`;
  }

  // Line + fitted trend line (calmer than week-to-week bars). Color the trend
  // by whether its slope is good news for this metric.
  const sparkHtml = sparkTrend(sparkData, direction === 'higher is better');

  return `<div class="trend-card">
    <div class="trend-label">${label}</div>
    <div class="trend-value">${value}<span style="font-size:10px;font-weight:500;color:var(--text-tertiary);margin-left:3px">${unit}</span></div>
    ${changeHtml}
    <div class="trend-period">${period || ''}</div>
    ${sparkHtml}
  </div>`;
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
