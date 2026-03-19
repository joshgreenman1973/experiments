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
let selectedRoute = null;
let sortMode = 'name'; // 'name', 'bunching', 'gaps', 'buses'
let boroFilter = 'all'; // 'all', 'M', 'B', 'Bx', 'Q', 'S'
let busSpeedCache = {}; // busId → speed in mph

// ═══ INIT ═══
async function init() {
  // Prompt for API key if not provided
  if (!CONFIG.apiKey) {
    CONFIG.apiKey = prompt(
      'Enter your MTA BusTime API key:\n\n' +
      'Get one free at https://register.developer.obanyc.com/'
    );
    if (!CONFIG.apiKey) {
      document.getElementById('loading-text').textContent =
        'API key required. Reload and enter your key.';
      return;
    }
    // Store in URL for convenience
    const url = new URL(window.location);
    url.searchParams.set('key', CONFIG.apiKey);
    window.history.replaceState({}, '', url);
  }

  updateLoadingText('Initializing map\u2026');

  // Init map
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

    updateLoadingText('Loading route shapes\u2026');
    await loadRouteShapes();

    updateLoadingText('Fetching live bus positions\u2026');
    await fetchLiveData();

    hideLoading();
    document.getElementById('live-badge').style.display = 'flex';

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

    map.addSource('routes', {
      type: 'geojson',
      data: routeShapes,
    });

    map.addLayer({
      id: 'route-lines',
      type: 'line',
      source: 'routes',
      paint: {
        'line-color': ['get', 'color'],
        'line-width': 2,
        'line-opacity': 0.35,
      },
    });
  } catch (e) {
    console.warn('Could not load route shapes:', e);
  }
}

async function fetchLiveData() {
  try {
    const url = `${CONFIG.apiBase}?key=${CONFIG.apiKey}&version=2`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API ${res.status}`);

    const data = await res.json();
    const delivery = data?.Siri?.ServiceDelivery?.VehicleMonitoringDelivery;
    if (!delivery?.[0]?.VehicleActivity) throw new Error('No vehicle data');

    const vehicles = parseVehicles(delivery[0].VehicleActivity);
    const snapshot = {
      ts: new Date().toISOString(),
      count: vehicles.length,
      vehicles,
    };

    // Calculate speeds from previous snapshot
    if (previousSnapshot) {
      computeSpeeds(previousSnapshot, snapshot);
    }
    previousSnapshot = currentSnapshot;
    currentSnapshot = snapshot;
    snapshots.push(snapshot);
    // Keep last 200 snapshots in memory for timeline
    if (snapshots.length > 200) snapshots.shift();

    renderBuses(snapshot);
    computeMetrics(snapshot);
    updateTimeline();

    document.getElementById('status-text').textContent =
      `Updated ${formatTime(new Date(snapshot.ts))}`;
  } catch (e) {
    console.error('Fetch failed:', e);
    document.getElementById('status-text').textContent =
      `Error: ${e.message}`;
    // Dismiss loading overlay on error so UI is visible
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
        bunched: 0, // will be set by computeMetrics
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

    const distMeters = haversine(prev.lat, prev.lon, v.lat, v.lon);
    const distMiles = distMeters / 1609.34;
    const speed = distMiles / dtHours;

    // Filter out unrealistic speeds (GPS glitches, layovers)
    if (speed >= 0 && speed < 60) {
      busSpeedCache[v.id] = Math.round(speed * 10) / 10;
    }
  }
}

// ═══ METRICS ═══
function computeMetrics(snapshot) {
  const { vehicles } = snapshot;
  const routeGroups = {};

  // Group by route + direction
  for (const v of vehicles) {
    const key = `${v.route}_${v.dir}`;
    if (!routeGroups[key]) routeGroups[key] = [];
    routeGroups[key].push(v);
  }

  let totalBunching = 0;
  let gapRoutes = 0;
  const routeMetrics = {};

  for (const [key, buses] of Object.entries(routeGroups)) {
    const route = key.split('_')[0];
    if (!routeMetrics[route]) {
      routeMetrics[route] = { buses: 0, bunching: 0, gaps: 0, dest: '', speeds: [] };
    }
    routeMetrics[route].buses += buses.length;
    if (buses.length > 0) {
      routeMetrics[route].dest = buses[0].dest;
    }

    // Collect speeds for this route
    for (const b of buses) {
      const spd = busSpeedCache[b.id];
      if (spd != null && spd > 0) {
        routeMetrics[route].speeds.push(spd);
      }
    }

    // Detect bunching: find pairs of buses very close together
    for (let i = 0; i < buses.length; i++) {
      for (let j = i + 1; j < buses.length; j++) {
        const dist = haversine(
          buses[i].lat, buses[i].lon,
          buses[j].lat, buses[j].lon
        );
        if (dist < CONFIG.bunchingDistanceMeters) {
          totalBunching++;
          routeMetrics[route].bunching++;
          // Mark both buses as bunched for visual indicator
          markBusBunched(snapshot, buses[i].id);
          markBusBunched(snapshot, buses[j].id);
        }
      }
    }

    // Estimate gaps in minutes between consecutive buses
    // Sort buses by latitude (rough proxy for position along route)
    // Use longitude for east-west routes
    const isEastWest = buses.length >= 2 &&
      Math.abs(buses[0].lon - buses[1].lon) > Math.abs(buses[0].lat - buses[1].lat);
    const sorted = [...buses].sort((a, b) =>
      isEastWest ? a.lon - b.lon : a.lat - b.lat
    );

    // Default speed assumption if no observed speed: 8 mph
    const routeSpeed = routeMetrics[route].speeds.length > 0
      ? routeMetrics[route].speeds.reduce((a, b) => a + b, 0) / routeMetrics[route].speeds.length
      : 8;
    const speedMps = (routeSpeed * 1609.34) / 3600; // convert mph to meters per second

    if (!routeMetrics[route].gapMinutes) routeMetrics[route].gapMinutes = [];
    if (!routeMetrics[route].dirGaps) routeMetrics[route].dirGaps = {};

    const dir = parseInt(key.split('_')[1], 10);

    if (sorted.length <= 1) {
      routeMetrics[route].gaps++;
    } else {
      let maxGapThisDir = 0;
      for (let i = 0; i < sorted.length - 1; i++) {
        const dist = haversine(
          sorted[i].lat, sorted[i].lon,
          sorted[i + 1].lat, sorted[i + 1].lon
        );
        const gapMin = speedMps > 0 ? (dist / speedMps) / 60 : 0;
        const rounded = Math.round(gapMin);
        routeMetrics[route].gapMinutes.push(rounded);
        maxGapThisDir = Math.max(maxGapThisDir, rounded);
      }
      // Track max gap per direction (0 or 1)
      routeMetrics[route].dirGaps[dir] = maxGapThisDir;
    }
  }

  // Compute max gap per route and identify long waits with direction info
  const longWaits20 = []; // 20-30 min
  const longWaits30 = []; // 30+ min
  for (const [route, rm] of Object.entries(routeMetrics)) {
    rm.maxGap = rm.gapMinutes && rm.gapMinutes.length > 0
      ? Math.max(...rm.gapMinutes) : null;

    if (rm.maxGap != null && rm.maxGap >= 20) {
      // Check which directions have long gaps
      const dirs = rm.dirGaps || {};
      const dir0bad = (dirs[0] || 0) >= 20;
      const dir1bad = (dirs[1] || 0) >= 20;
      // both = \u2194, one direction = \u2192 or \u2190
      const dirLabel = (dir0bad && dir1bad) ? '\u2194' : '\u2192';

      const entry = { route, gap: rm.maxGap, bothDirs: dir0bad && dir1bad, dirLabel };
      if (rm.maxGap >= 30) {
        longWaits30.push(entry);
      } else {
        longWaits20.push(entry);
      }
    }
    if (rm.gaps > 0) gapRoutes++;
  }
  longWaits30.sort((a, b) => b.gap - a.gap);
  longWaits20.sort((a, b) => b.gap - a.gap);

  // Compute system-wide average speed and rider wait time
  const allSpeeds = [];
  const allGaps = [];
  for (const rm of Object.values(routeMetrics)) {
    if (rm.speeds.length > 0) {
      rm.avgSpeed = Math.round(rm.speeds.reduce((a, b) => a + b, 0) / rm.speeds.length * 10) / 10;
      allSpeeds.push(...rm.speeds);
    } else {
      rm.avgSpeed = null;
    }
    if (rm.gapMinutes) allGaps.push(...rm.gapMinutes);
  }
  const systemAvgSpeed = allSpeeds.length > 0
    ? Math.round(allSpeeds.reduce((a, b) => a + b, 0) / allSpeeds.length * 10) / 10
    : null;

  // Average rider wait time = E[gap^2] / (2 * E[gap])
  // This accounts for bunching: if gaps are uneven, riders wait longer
  let avgRiderWait = null;
  if (allGaps.length > 0) {
    const meanGap = allGaps.reduce((a, b) => a + b, 0) / allGaps.length;
    const meanGapSq = allGaps.reduce((a, b) => a + b * b, 0) / allGaps.length;
    avgRiderWait = meanGap > 0 ? Math.round(meanGapSq / (2 * meanGap) * 10) / 10 : null;
  }

  // Update system stats
  document.getElementById('stat-buses').textContent = vehicles.length.toLocaleString();
  document.getElementById('stat-routes-count').textContent =
    `${Object.keys(routeMetrics).length} routes`;

  document.getElementById('stat-bunching').textContent = totalBunching;
  const bunchEl = document.getElementById('stat-bunching');
  bunchEl.className = `value ${totalBunching > 50 ? 'bad' : totalBunching > 20 ? 'warn' : 'good'}`;

  document.getElementById('stat-gaps').textContent =
    longWaits30.length + longWaits20.length;

  // Update speed stat
  const speedEl = document.getElementById('stat-speed');
  if (speedEl) {
    if (systemAvgSpeed != null) {
      speedEl.textContent = `${systemAvgSpeed}`;
      speedEl.className = `value ${systemAvgSpeed < 6 ? 'bad' : systemAvgSpeed < 8 ? 'warn' : 'accent'}`;
    } else {
      speedEl.textContent = '\u2014';
    }
  }

  // Update wait time stat
  const waitEl = document.getElementById('stat-wait');
  if (waitEl) {
    if (avgRiderWait != null) {
      waitEl.textContent = `${avgRiderWait}`;
      waitEl.className = `value ${avgRiderWait > 15 ? 'bad' : avgRiderWait > 10 ? 'warn' : 'accent'}`;
    } else {
      waitEl.textContent = '\u2014';
    }
  }

  // Render long wait alerts
  renderWaitAlerts(longWaits20, longWaits30);

  // Re-render bus layer with bunching flags
  renderBuses(snapshot);

  // Update route list
  renderRouteList(routeMetrics);
}

function markBusBunched(snapshot, busId) {
  const bus = snapshot.vehicles.find(v => v.id === busId);
  if (bus) bus.bunched = 1;
}

// ═══ LONG WAIT ALERTS ═══
function renderWaitAlerts(waits20, waits30) {
  const container = document.getElementById('wait-alerts');

  if (waits30.length === 0 && waits20.length === 0) {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';

  let html = '';

  if (waits30.length > 0) {
    html += `<div class="wait-row" data-tier="30">
      <span class="wait-dot severe"></span>
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
      <span class="wait-dot bad"></span>
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
  const list = document.getElementById('route-list');
  const filter = document.getElementById('route-search').value.toLowerCase();

  let routes = Object.entries(metrics).map(([route, m]) => ({
    route, ...m,
  }));

  // Borough filter
  if (boroFilter !== 'all') {
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
        // Zoom to route
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
  const slider = document.getElementById('timeline-slider');
  const btnLive = document.getElementById('btn-live');
  const btnPlay = document.getElementById('btn-play');
  const speedEl = document.getElementById('timeline-speed');

  btnLive.addEventListener('click', () => {
    isLive = true;
    isPlaying = false;
    clearInterval(playTimer);
    btnLive.classList.add('active');
    btnPlay.classList.remove('active');
    document.getElementById('live-badge').style.display = 'flex';
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
    document.getElementById('live-badge').style.display = 'none';

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
    document.getElementById('live-badge').style.display = 'none';

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
  document.getElementById('route-search').addEventListener('input', () => {
    if (currentSnapshot) computeMetrics(currentSnapshot);
  });

  // Sort button (cycles through modes)
  document.getElementById('sort-btn').addEventListener('click', () => {
    const modes = ['name', 'buses', 'speed', 'bunching', 'gaps'];
    const labels = ['A\u2013Z', 'Buses', 'Speed', 'Bunch', 'Gaps'];
    const idx = modes.indexOf(sortMode);
    sortMode = modes[(idx + 1) % modes.length];
    document.getElementById('sort-btn').textContent = labels[(idx + 1) % labels.length];
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
      boroFilter = btn.dataset.boro;
      document.querySelectorAll('.boro-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
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
    (document.getElementById('timeline-slider').value / 100) * (snapshots.length - 1)
  );

  playTimer = setInterval(() => {
    idx++;
    if (idx >= snapshots.length) {
      idx = 0; // loop
    }
    showSnapshot(idx);
    document.getElementById('timeline-slider').value =
      (idx / (snapshots.length - 1)) * 100;
  }, 1000 / playSpeed);
}

function showSnapshot(idx) {
  if (idx < 0 || idx >= snapshots.length) return;
  const snap = snapshots[idx];
  renderBuses(snap);
  computeMetrics(snap);
  document.getElementById('timeline-time').textContent =
    formatTime(new Date(snap.ts));
  document.getElementById('status-text').textContent =
    `Snapshot ${idx + 1} of ${snapshots.length}`;
}

function updateTimeline() {
  if (!isLive) return;
  const slider = document.getElementById('timeline-slider');
  slider.max = 100;
  slider.value = 100;
  if (currentSnapshot) {
    document.getElementById('timeline-time').textContent =
      formatTime(new Date(currentSnapshot.ts));
    document.getElementById('timeline-date').textContent =
      formatDate(new Date(currentSnapshot.ts));
  }
}

// ═══ UTILITIES ═══
function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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

function routeColor(route) {
  // Consistent color per route from curated palette
  let hash = 0;
  for (let i = 0; i < route.length; i++) {
    hash = route.charCodeAt(i) + ((hash << 5) - hash);
  }
  return ROUTE_COLORS[Math.abs(hash) % ROUTE_COLORS.length];
}

function naturalSort(a, b) {
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
}

function updateLoadingText(text) {
  document.getElementById('loading-text').textContent = text;
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
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
