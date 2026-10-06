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
  // Map tile source
  tileUrl: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
};

// ═══ STATE ═══
let map;
let currentSnapshot = null;
let previousSnapshot = null; // for speed calculation
let isLive = true;
let routeShapes = null;
let routeShapeIndex = null; // routeId → GeoJSON feature (built once on shape load)
let selectedRoute = null;
let sortMode = 'name'; // 'name', 'buses', 'speed'
let boroFilter = 'all'; // 'all', 'M', 'B', 'Bx', 'Q', 'S', 'top25', 'nearby'
let userLocation = null; // {lat, lon} from geolocation

// Live speed, built the way the weekly figures are: per route, distance over
// time across recent polls with stopped time included (layovers left out);
// the headline is the plain mean of local, limited and SBS routes.
const LIVE_WINDOW_MS = 180000;       // pool the last three minutes of readings
const routeReadings = new Map();     // route -> [{ t, dist, dt }]
let routeNames = {};                 // routeId -> { long, kind } from route-table.json
const EXPRESS_RE = /^(BM|BXM|QM|SIM|X)\d/i;

let busPositionCache = {}; // busId → {lat, lon, ts, route, dir} — persists across polls

// ═══ DOM CACHE ═══
// Populated once after DOMContentLoaded; avoids repeated getElementById calls
const dom = {};
function cacheDomElements() {
  const ids = [
    'stat-buses', 'stat-routes-count', 'stat-speed', 'speed-hint', 'speed-detail',
    'live-badge', 'status-text', 'loading-overlay', 'loading-text',
    'route-list', 'route-search', 'sort-btn', 'borough-filter', 'route-list-header',
    'tray', 'tray-handle', 'tray-hint', 'ai-caution-btn', 'ai-caution-pop',
  ];
  for (const id of ids) {
    dom[id] = document.getElementById(id);
  }
}

/** Small "AI caution" chip in the sidebar: toggles a navy popover, closes on
 *  any outside click. */
function bindCautionPopover() {
  const btn = dom['ai-caution-btn'];
  const pop = dom['ai-caution-pop'];
  if (!btn || !pop) return;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    pop.hidden = !pop.hidden;
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#ai-caution-btn') && !e.target.closest('#ai-caution-pop')) {
      pop.hidden = true;
    }
  });
}

// ═══ INIT ═══
async function init() {
  cacheDomElements();
  bindCautionPopover();

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

  updateLoadingText('Waiting for the MTA feed (it can take 20 seconds)\u2026');
  loadRouteNames();

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

  // Start once the style is in. Waiting for the full 'load' event meant one
  // stalled map tile could hold the whole page on its loading screen.
  let started = false;
  const onReady = async () => {
    if (started) return;
    started = true;
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

    // Route shapes load in the background; the weekly tray (tray.js) loads on
    // its own and does not wait for the map.
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
  };
  map.on('load', onReady);
  map.on('style.load', () => setTimeout(onReady, 1500));
  setTimeout(() => { if (map.isStyleLoaded()) onReady(); }, 10000);

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
        routeFull: '', stale: true,
      });
    }
  }

  const snapshot = {
    ts: new Date().toISOString(),
    count: mergedVehicles.length,
    vehicles: mergedVehicles,
  };

  // Speeds compare this poll with the one just before it. Cached replays
  // (sessionStorage) carry no GPS times and are never used for speed.
  if (currentSnapshot && !isCached && !currentSnapshot.cached) {
    computeSpeeds(currentSnapshot, snapshot);
  }
  snapshot.cached = isCached;
  previousSnapshot = currentSnapshot;
  currentSnapshot = snapshot;

  computeMetrics(snapshot);

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
      distFromStop: j.MonitoredCall?.ArrivalProximityText || '',
      stopsAway: j.MonitoredCall?.NumberOfStopsAway ?? null,
      pax: j.MonitoredCall?.Extensions?.Capacities?.EstimatedPassengerCount ?? null,
      phase: [].concat(j.ProgressStatus || []).join(','),
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
    pax: v.pax ?? null,
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

    // Bus glow — soft halo per route color
    map.addLayer({
      id: 'bus-glow',
      type: 'circle',
      source: 'buses',
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          9, 5, 13, 12, 16, 18,
        ],
        'circle-color': ['get', 'color'],
        'circle-opacity': 0.15,
        'circle-blur': 1,
      },
    });

    // Bus dots — colored by route
    map.addLayer({
      id: 'bus-dots',
      type: 'circle',
      source: 'buses',
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          9, 2.5, 13, 5, 16, 8,
        ],
        'circle-color': ['get', 'color'],
        'circle-opacity': 0.9,
        'circle-stroke-width': 0.5,
        'circle-stroke-color': 'rgba(255,255,255,0.15)',
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
        'icon-color': ['get', 'color'],
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
    map.setPaintProperty('bus-glow', 'circle-opacity', 0.15);
  }
}

// ═══ SPEED CALCULATION ═══
function computeSpeeds(prevSnap, currSnap) {
  const prevMap = new Map(prevSnap.vehicles.map(v => [v.id, v]));
  const now = Date.now();
  for (const v of currSnap.vehicles) {
    if (v.stale) continue;
    const p = prevMap.get(v.id);
    if (!p || p.stale || p.route !== v.route) continue;
    if (String(v.phase).includes('layover') || String(p.phase).includes('layover')) continue;
    const t1 = Date.parse(p.ts), t2 = Date.parse(v.ts);
    if (!Number.isFinite(t1) || !Number.isFinite(t2)) continue;
    const dt = (t2 - t1) / 1000;
    if (dt < 5 || dt > 600) continue;            // GPS did not refresh, or too long a gap
    const dist = haversine(p.lat, p.lon, v.lat, v.lon);
    const mph = (dist / dt) * 2.2369363;
    if (mph >= 60) continue;                      // GPS error
    if (!routeReadings.has(v.route)) routeReadings.set(v.route, []);
    routeReadings.get(v.route).push({ t: now, dist, dt });
  }
  for (const [route, list] of routeReadings) {
    const kept = list.filter(r => now - r.t <= LIVE_WINDOW_MS);
    if (kept.length) routeReadings.set(route, kept); else routeReadings.delete(route);
  }
}

const isLocalRoute = r => !EXPRESS_RE.test(r) && (!Object.keys(routeNames).length || routeNames[r]);

// ═══ METRICS ═══
function computeMetrics(snapshot) {
  const { vehicles } = snapshot;
  const routeMetrics = {};
  for (const v of vehicles) {
    const rm = (routeMetrics[v.route] ||= { buses: 0, dest: '' });
    rm.buses++;
    if (!rm.dest) rm.dest = routeNames[v.route]?.long || v.dest || '';
  }
  // Route speed with stops = total distance / total time over the window;
  // needs two minutes of bus-time so one bus at a light doesn't set it.
  const localSpeeds = [];
  for (const [route, rm] of Object.entries(routeMetrics)) {
    const list = routeReadings.get(route) || [];
    const dist = list.reduce((s, r) => s + r.dist, 0), dt = list.reduce((s, r) => s + r.dt, 0);
    rm.avgSpeed = dt >= 120 ? round1((dist / dt) * 2.2369363) : null;
    if (rm.avgSpeed != null && isLocalRoute(route)) localSpeeds.push(rm.avgSpeed);
  }
  const systemAvgSpeed = localSpeeds.length >= 50 ? round1(avg(localSpeeds)) : null;

  updateSystemStats(vehicles, routeMetrics, systemAvgSpeed);
  renderBuses(snapshot);
  renderRouteList(routeMetrics);
}

function updateSystemStats(vehicles, routeMetrics, systemAvgSpeed) {
  dom['stat-buses'].textContent = vehicles.length.toLocaleString();
  dom['stat-routes-count'].textContent = `${Object.keys(routeMetrics).length} routes`;
  const speedEl = dom['stat-speed'];
  const hint = dom['speed-hint'];
  if (systemAvgSpeed == null) {
    speedEl.textContent = '\u2014';
    if (hint) { hint.style.display = ''; hint.textContent = 'measuring\u2026 (about a minute)'; }
    return;
  }
  speedEl.textContent = systemAvgSpeed.toFixed(1);
  speedEl.className = 'value accent';
  if (hint) hint.style.display = 'none';
  // Typical for this hour: the latest comparable week's figure for the same
  // day type and Eastern hour, from tray.js.
  const T = window.BusTypical;
  const detail = dom['speed-detail'];
  if (!detail) return;
  const now = new Date();
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', hourCycle: 'h23' })
    .formatToParts(now).map(x => [x.type, x.value]));
  const hour = Number(parts.hour);
  const weekend = parts.weekday === 'Sat' || parts.weekday === 'Sun';
  const cell = T?.hourly?.[weekend ? 'we' : 'wd']?.[hour];
  if (cell?.all != null) {
    const label = hour === 12 ? 'noon' : `${((hour + 11) % 12) + 1}\u00a0${hour < 12 ? 'a.m.' : 'p.m.'}`;
    const d = systemAvgSpeed - cell.all;
    const word = Math.abs(d) < 0.3 ? 'about typical' : d > 0 ? `${d.toFixed(1)} faster than typical` : `${Math.abs(d).toFixed(1)} slower than typical`;
    detail.innerHTML = `mph, local routes, with stops. Typical ${weekend ? 'weekend' : 'weekday'} ${label}: <strong>${cell.all.toFixed(1)}</strong> (${word})`;
  } else {
    detail.textContent = 'mph, local routes, with stops';
  }
}

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
    // Thresholds for speed with stops (local routes typically run 6 to 8 mph).
    const spdClass = r.avgSpeed != null ? (r.avgSpeed < 5 ? 'bad' : r.avgSpeed < 6.5 ? 'warn' : '') : '';
    return `
      <div class="route-row${isSelected ? ' selected' : ''}" data-route="${r.route}">
        <div><span class="route-badge" style="background:${color}">${r.route}</span></div>
        <div class="route-dest" title="${r.dest}"><span class="rd-name">${r.dest}</span><a class="route-hist" href="route.html?r=${encodeURIComponent(r.route)}" title="Speed history for the ${r.route}">history&nbsp;&rarr;</a></div>
        <div class="route-metric">${r.buses}</div>
        <div class="route-metric ${spdClass}">${spdStr}</div>
      </div>
    `;
  }).join('');

  // Click handlers
  list.querySelectorAll('.route-row').forEach(row => {
    row.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
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
      ${props.pax != null && props.pax !== 'null' ? `<p>About <span class="val">${props.pax}</span> aboard (passenger-counter estimate)</p>` : ''}
      ${String(props.phase).includes('layover') ? '<p>On layover</p>' : ''}
      <p style="color:rgba(255,255,255,0.28);font-size:11px;margin-top:6px">Bus ${String(props.id).replace(/^MTA\w*\s*\w*_/, '#')}</p>
      <p><a href="route.html?r=${encodeURIComponent(props.route)}" style="color:var(--vc-chartreuse)">${props.route} speed history &rarr;</a></p>
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
    const modes = ['name', 'buses', 'speed'];
    const labels = ['A\u2013Z', 'Buses', 'Speed'];
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

/** Round to 1 decimal place */
function round1(n) {
  return Math.round(n * 10) / 10;
}

/** Average of an array of numbers */
function avg(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function formatTime(d) {
  return d.toLocaleTimeString('en-US', {
    hour: 'numeric', minute: '2-digit',
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

// ═══ ROUTE NAMES ═══
async function loadRouteNames() {
  try {
    const res = await fetch('data/routes/route-table.json');
    if (res.ok) routeNames = (await res.json()).routes || {};
  } catch { /* names are a nicety; the feed's destination signs stand in */ }
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
