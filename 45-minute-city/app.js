/* The 45-Minute City — UI + canvas rendering.
   Routing happens in worker.js; this file only asks questions and draws answers. */

const $ = (s) => document.querySelector(s);

const state = {
  ready: false,
  originNode: -1,
  originLatLng: null,
  budget: 45 * 60,
  mode: "transit",
  band: "weekday_am_peak",
  walkSpeed: 1.4,
  bikeSpeed: 4.0,
  maxWait: 20 * 60,
  accessible: false,
  streetDist: null,
  race: null,
  reachedStops: [],
  meta: null,
  stops: [],
  bands: [],
};

let G = null; // walk/bike street geometry on the main thread
let CG = null; // drivable geometry (separate node space)
let worker = null;
let map = null;
let reqId = 0;
// The counter is shared by snap, render and compare requests, so "is this the
// latest request overall" is the wrong staleness test — a compare batch landing
// between a snap's post and its reply would discard a perfectly current origin.
// Each kind remembers its own latest id instead.
let lastSnapId = 0;
let lastRenderId = 0;

// Time ramp. Near is hot, far is cool; unreachable stays almost invisible.
const RAMP = [
  [0.0, [255, 244, 189]],
  [0.18, [255, 199, 60]],
  [0.38, [255, 122, 41]],
  [0.58, [230, 57, 70]],
  [0.78, [156, 39, 116]],
  [1.0, [66, 30, 110]],
];

function rampColor(t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < RAMP.length; i++) {
    if (t <= RAMP[i][0]) {
      const [t0, c0] = RAMP[i - 1], [t1, c1] = RAMP[i];
      const f = (t - t0) / (t1 - t0);
      return [
        Math.round(c0[0] + (c1[0] - c0[0]) * f),
        Math.round(c0[1] + (c1[1] - c0[1]) * f),
        Math.round(c0[2] + (c1[2] - c0[2]) * f),
      ];
    }
  }
  return RAMP[RAMP.length - 1][1];
}

/* ---------- canvas layer ---------- */
const CanvasLayer = L.Layer.extend({
  onAdd(map) {
    this._map = map;
    const c = (this._canvas = L.DomUtil.create("canvas", "reach-canvas"));
    const size = map.getSize();
    c.width = size.x * devicePixelRatio;
    c.height = size.y * devicePixelRatio;
    c.style.width = size.x + "px";
    c.style.height = size.y + "px";
    map.getPanes().overlayPane.appendChild(c);
    map.on("moveend zoomend resize", this._reset, this);
    map.on("zoomanim", this._animZoom, this);
    this._reset();
  },
  onRemove(map) {
    L.DomUtil.remove(this._canvas);
    map.off("moveend zoomend resize", this._reset, this);
    map.off("zoomanim", this._animZoom, this);
  },
  _animZoom(e) {
    const scale = this._map.getZoomScale(e.zoom);
    const offset = this._map._latLngToNewLayerPoint(this._map.getBounds().getNorthWest(), e.zoom, e.center);
    L.DomUtil.setTransform(this._canvas, offset, scale);
  },
  _reset() {
    const map = this._map;
    const size = map.getSize();
    const c = this._canvas;
    if (c.width !== size.x * devicePixelRatio || c.height !== size.y * devicePixelRatio) {
      c.width = size.x * devicePixelRatio;
      c.height = size.y * devicePixelRatio;
      c.style.width = size.x + "px";
      c.style.height = size.y + "px";
    }
    L.DomUtil.setTransform(c, L.point(0, 0), 1);
    const tl = map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(c, tl);
    this.draw();
  },
  draw() {
    if (!G || !this._map) return;
    const map = this._map;
    const c = this._canvas;
    const ctx = c.getContext("2d");
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);

    const size = map.getSize();
    const nw = map.containerPointToLatLng([0, 0]);
    const se = map.containerPointToLatLng([size.x, size.y]);
    const north = nw.lat, west = nw.lng, south = se.lat, east = se.lng;
    const zoom = map.getZoom();

    if (state.mode === "race") { this.drawRace(ctx, map, north, south, east, west, zoom); return; }
    // Taxi routes on its own directed graph with its own node space; every
    // other mode draws the walk/bike network filtered by flag.
    const isCar = state.mode === "taxi";
    const A = isCar ? CG : G;
    const mask = state.mode === "bike" || state.accessible ? 2 : 1;

    // project once per node, lazily, into container space
    const px = A.px, py = A.py, seen = A.seen;
    A.stamp++;
    const stamp = A.stamp;

    const proj = (i) => {
      if (seen[i] !== stamp) {
        const p = map.latLngToContainerPoint([A.lat[i], A.lon[i]]);
        px[i] = p.x; py[i] = p.y; seen[i] = stamp;
      }
    };

    const dist = state.streetDist;
    const budget = state.budget;
    const m = A.ea.length;

    // Pass 1: the unreachable network, very dim, so the city stays legible.
    ctx.lineWidth = zoom >= 15 ? 0.6 : 0.4;
    ctx.strokeStyle = "rgba(120,140,170,0.16)";
    ctx.beginPath();
    for (let i = 0; i < m; i++) {
      if (!isCar && !(A.ef[i] & mask)) continue;
      const a = A.ea[i], b = A.eb[i];
      const la = A.lat[a], lo = A.lon[a];
      if (la > north || la < south || lo < west || lo > east) {
        const lb = A.lat[b], ob = A.lon[b];
        if (lb > north || lb < south || ob < west || ob > east) continue;
      }
      if (dist && dist[a] >= 0 && dist[b] >= 0) continue;
      proj(a); proj(b);
      ctx.moveTo(px[a], py[a]); ctx.lineTo(px[b], py[b]);
    }
    ctx.stroke();

    if (!dist) return;

    // Pass 2: reachable streets, coloured by travel time, drawn in time order
    // so the fast core sits on top of the slow fringe.
    const BUCKETS = 24;
    const buckets = Array.from({ length: BUCKETS }, () => []);
    for (let i = 0; i < m; i++) {
      if (!isCar && !(A.ef[i] & mask)) continue;
      const a = A.ea[i], b = A.eb[i];
      const da = dist[a], db = dist[b];
      if (da < 0 || db < 0) continue;
      const la = A.lat[a], lo = A.lon[a];
      if (la > north || la < south || lo < west || lo > east) {
        const lb = A.lat[b], ob = A.lon[b];
        if (lb > north || lb < south || ob < west || ob > east) continue;
      }
      const t = Math.max(da, db) / budget;
      buckets[Math.min(BUCKETS - 1, Math.floor(t * BUCKETS))].push(i);
    }
    ctx.lineCap = "round";
    for (let k = BUCKETS - 1; k >= 0; k--) {
      const list = buckets[k];
      if (!list.length) continue;
      const [r, g, bl] = rampColor((k + 0.5) / BUCKETS);
      ctx.strokeStyle = `rgb(${r},${g},${bl})`;
      ctx.lineWidth = zoom >= 15 ? 1.9 : zoom >= 13 ? 1.3 : 0.9;
      ctx.globalAlpha = 0.92;
      ctx.beginPath();
      for (const i of list) {
        const a = A.ea[i], b = A.eb[i];
        proj(a); proj(b);
        ctx.moveTo(px[a], py[a]); ctx.lineTo(px[b], py[b]);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  },

  // Head-to-head: color every street by which mode gets there first from the
  // same origin, waits included on both sides.
  drawRace(ctx, map, north, south, east, west, zoom) {
    const A = CG;
    const px = A.px, py = A.py, seen = A.seen;
    A.stamp++;
    const stamp = A.stamp;
    const proj = (i) => {
      if (seen[i] !== stamp) {
        const p = map.latLngToContainerPoint([A.lat[i], A.lon[i]]);
        px[i] = p.x; py[i] = p.y; seen[i] = stamp;
      }
    };
    const m = A.ea.length;

    // dim base network
    ctx.lineWidth = zoom >= 15 ? 0.6 : 0.4;
    ctx.strokeStyle = "rgba(120,140,170,0.16)";
    ctx.beginPath();
    for (let i = 0; i < m; i++) {
      const a = A.ea[i], b = A.eb[i];
      const la = A.lat[a], lo = A.lon[a];
      if (la > north || la < south || lo < west || lo > east) {
        const lb = A.lat[b], ob = A.lon[b];
        if (lb > north || lb < south || ob < west || ob > east) continue;
      }
      proj(a); proj(b);
      ctx.moveTo(px[a], py[a]); ctx.lineTo(px[b], py[b]);
    }
    ctx.stroke();

    if (!state.race) return;
    const { transit, taxi } = state.race;
    const link = state.carLink;
    const groups = { train: [], cab: [], cabonly: [], tie: [] };
    for (let i = 0; i < m; i++) {
      const a = A.ea[i], b = A.eb[i];
      const la = A.lat[a], lo = A.lon[a];
      if (la > north || la < south || lo < west || lo > east) {
        const lb = A.lat[b], ob = A.lon[b];
        if (lb > north || lb < south || ob < west || ob > east) continue;
      }
      const tx = taxi[a];
      const w = link[a];
      const tr = w === 4294967295 ? -1 : transit[w];
      if (tx < 0 && tr < 0) continue;
      if (tr < 0) groups.cabonly.push(i);      // transit can't get here at all
      else if (tx < 0) groups.train.push(i);
      else if (Math.abs(tx - tr) <= 120) groups.tie.push(i);
      else if (tr < tx) groups.train.push(i);
      else groups.cab.push(i);                  // both reach; cab is faster
    }
    const COLORS = {
      tie: "rgba(154,163,181,0.55)",
      cabonly: "rgba(255,157,46,0.34)",
      cab: "#ff9d2e",
      train: "#4c9aff",
    };
    ctx.lineCap = "round";
    for (const key of ["cabonly", "tie", "cab", "train"]) {
      const list = groups[key];
      if (!list.length) continue;
      ctx.strokeStyle = COLORS[key];
      ctx.lineWidth = zoom >= 15 ? 1.9 : zoom >= 13 ? 1.3 : 0.9;
      ctx.globalAlpha = key === "tie" ? 0.7 : 0.92;
      ctx.beginPath();
      for (const i of list) {
        const a = A.ea[i], b = A.eb[i];
        proj(a); proj(b);
        ctx.moveTo(px[a], py[a]); ctx.lineTo(px[b], py[b]);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  },
});

let reachLayer = null;

/* ---------- init ---------- */
function initMap() {
  map = L.map("map", {
    center: [40.7295, -73.9965],
    zoom: 12,
    zoomControl: false,
    preferCanvas: true,
  });
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer(
    "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_nolabels/{z}/{x}/{y}{r}.png",
    { maxZoom: 19, attribution: "" }
  ).addTo(map);
  L.tileLayer(
    "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_only_labels/{z}/{x}/{y}{r}.png",
    { maxZoom: 19, pane: "shadowPane", opacity: 0.55, attribution: "" }
  ).addTo(map);

  reachLayer = new CanvasLayer();
  reachLayer.addTo(map);

  map.on("click", (e) => setOrigin(e.latlng.lat, e.latlng.lng));
}

function initWorker() {
  // Version-locked: HTML, app, worker and data always load as one set, so a
  // deploy can never mix a cached old worker with new code or new data.
  worker = new Worker("worker.js?v=" + (window.ASSET_V || "dev"));
  worker.onmessage = (e) => {
    const m = e.data;
    if (m.type === "ready") {
      G = {
        lat: new Float64Array(m.lat),
        lon: new Float64Array(m.lon),
        ea: new Uint32Array(m.ea),
        eb: new Uint32Array(m.eb),
        ef: new Uint8Array(m.ef),
        px: null, py: null, seen: null, stamp: 0,
      };
      G.px = new Float32Array(G.lat.length);
      G.py = new Float32Array(G.lat.length);
      G.seen = new Int32Array(G.lat.length);
      CG = {
        lat: new Float64Array(m.carLat),
        lon: new Float64Array(m.carLon),
        ea: new Uint32Array(m.cea),
        eb: new Uint32Array(m.ceb),
        ef: null,
        px: null, py: null, seen: null, stamp: 0,
      };
      CG.px = new Float32Array(CG.lat.length);
      CG.py = new Float32Array(CG.lat.length);
      CG.seen = new Int32Array(CG.lat.length);
      state.carCalibration = m.carCalibration;
      state.access = m.access;
      state.carLink = new Uint32Array(m.carLink);
      state.ready = true;
      state.meta = m.meta;
      state.stops = m.stops;
      state.bands = m.bands;
      $("#loading").classList.add("gone");
      $("#stat-network").textContent =
        `${m.nNodes.toLocaleString()} street nodes · ${m.nEdges.toLocaleString()} segments · ` +
        `${m.nStops.toLocaleString()} stops · ${m.nRoutes.toLocaleString()} routes`;
      buildBandOptions();
      reachLayer.draw();
      setOrigin(40.7295, -73.9965); // Washington Square-ish default
    }
    if (m.type === "snapped") {
      if (m.id !== lastSnapId) return; // a newer origin has been chosen since
      state.originNode = m.node;
      state.originCarNode = m.carNode;
      runRoute();
    }
    if (m.type === "routed") {
      const job = pending.get(m.id);
      pending.delete(m.id);
      if (!job) return;
      const dist = new Float32Array(m.streetDist);
      if (job.purpose === "compare") {
        compare[job.mode] = computeKm(dist, job.mode);
        renderCompare();
        return;
      }
      if (job.purpose === "race-transit" || job.purpose === "race-taxi") {
        if (!raceBuf || (m.id !== raceBuf.idTr && m.id !== raceBuf.idTx)) return;
        if (job.purpose === "race-transit") raceBuf.transit = dist;
        else raceBuf.taxi = dist;
        if (raceBuf.transit && raceBuf.taxi) {
          state.race = { transit: raceBuf.transit, taxi: raceBuf.taxi };
          reachLayer.draw();
          updateRaceStats();
          $("#panel").classList.remove("busy");
          runCompare();
        }
        return;
      }
      if (m.id !== lastRenderId) return;
      const expected = job.mode === "taxi" ? CG.lat.length : G.lat.length;
      if (dist.length !== expected) return; // wrong node space; never draw it
      state.streetDist = dist;
      state.reachedStops = m.reachedStops;
      reachLayer.draw();
      updateStats(m.stats);
      $("#panel").classList.remove("busy");
      runCompare();
    }
  };
  worker.postMessage({ type: "init", base: "", v: window.ASSET_V || "dev" });
}

function setOrigin(lat, lng) {
  state.originLatLng = [lat, lng];
  if (window._originMarker) map.removeLayer(window._originMarker);
  window._originMarker = L.circleMarker([lat, lng], {
    radius: 7, color: "#fff", weight: 2.5, fillColor: "#111", fillOpacity: 1,
  }).addTo(map);
  $("#panel").classList.add("busy");
  lastSnapId = ++reqId;
  worker.postMessage({ type: "snap", id: lastSnapId, lat, lon: lng });
}

const pending = new Map();
const MODES = ["walk", "bike", "taxi", "subway", "bus", "transit"];
const MODE_LABEL = { walk: "Walk", bike: "Bike", taxi: "Taxi/Uber", subway: "Subway", bus: "Bus", transit: "Subway + bus" };
let compare = {};

function opts(mode) {
  return {
    originNode: state.originNode,
    originCarNode: state.originCarNode,
    budget: state.budget,
    mode,
    walkSpeed: state.walkSpeed,
    bikeSpeed: state.bikeSpeed,
    bandId: state.band,
    maxWait: state.maxWait,
    accessible: state.accessible,
  };
}

let raceBuf = null;

function runRoute() {
  if (!state.ready || state.originNode < 0) return;
  $("#panel").classList.add("busy");
  compare = {};
  renderCompare();
  state.race = null;
  if (state.mode === "race") {
    // Two full routes from the same origin, same clock; the map shows who wins.
    const idTr = ++reqId, idTx = ++reqId;
    lastRenderId = idTx;
    raceBuf = { idTr, idTx, transit: null, taxi: null };
    pending.set(idTr, { purpose: "race-transit" });
    pending.set(idTx, { purpose: "race-taxi" });
    worker.postMessage({ type: "route", id: idTr, opts: { ...opts("transit") } });
    worker.postMessage({ type: "route", id: idTx, opts: { ...opts("taxi") } });
    return;
  }
  lastRenderId = ++reqId;
  pending.set(lastRenderId, { purpose: "render", mode: state.mode });
  worker.postMessage({ type: "route", id: lastRenderId, opts: opts(state.mode) });
}

// Run every mode from the same origin so they can be compared on equal terms.
function runCompare() {
  for (const mode of MODES) {
    if (mode === "bike" && state.accessible) continue;
    const id = ++reqId;
    pending.set(id, { purpose: "compare", mode });
    worker.postMessage({ type: "route", id, opts: opts(mode) });
  }
}

function computeKm(dist, mode) {
  const isCar = mode === "taxi";
  const A = isCar ? CG : G;
  const mask = mode === "bike" || state.accessible ? 2 : 1;
  const seenPair = isCar ? new Set() : null; // car edges are directed; count each street once
  let m2 = 0;
  const m = A.ea.length;
  for (let i = 0; i < m; i++) {
    if (!isCar && !(A.ef[i] & mask)) continue;
    const a = A.ea[i], b = A.eb[i];
    if (dist[a] < 0 || dist[b] < 0) continue;
    if (isCar) {
      const k = a < b ? a * 4294967296 + b : b * 4294967296 + a;
      if (seenPair.has(k)) continue;
      seenPair.add(k);
    }
    const dx = (A.lat[a] - A.lat[b]) * 111320;
    const dy = (A.lon[a] - A.lon[b]) * 84500;
    m2 += Math.sqrt(dx * dx + dy * dy);
  }
  return m2 / 1000;
}

function renderCompare() {
  const el = $("#compare");
  const vals = MODES.map((m) => compare[m]).filter((v) => v !== undefined);
  if (!vals.length) { el.innerHTML = '<div class="cmp-wait">measuring every mode ...</div>'; return; }
  const max = Math.max(...vals);
  el.innerHTML = MODES.map((m) => {
    const v = compare[m];
    const w = v === undefined ? 0 : (v / max) * 100;
    const dim = m === "bike" && state.accessible;
    return `<div class="cmp-row${m === state.mode ? " on" : ""}${dim ? " off" : ""}">
      <div class="cmp-k">${MODE_LABEL[m]}</div>
      <div class="cmp-bar"><i style="width:${dim ? 0 : w}%"></i></div>
      <div class="cmp-v">${dim ? "n/a" : v === undefined ? "—" : Math.round(v).toLocaleString()}</div>
    </div>`;
  }).join("");
}

/* ---------- stats ---------- */
function updateStats(stats) {
  const km = computeKm(state.streetDist, state.mode);
  $("#stat-km").textContent = km.toLocaleString(undefined, { maximumFractionDigits: 0 });

  const subway = state.reachedStops.filter((s) => state.stops[s[0]][3] === 0).length;
  const bus = state.reachedStops.length - subway;
  $("#stat-subway").textContent = subway.toLocaleString();
  $("#stat-bus").textContent = bus.toLocaleString();
  $("#stat-time").textContent = stats.ms + " ms";
}

function updateRaceStats() {
  const { transit, taxi } = state.race;
  const link = state.carLink;
  let trainKm = 0, cabKm = 0, cabOnlyKm = 0, tieKm = 0;
  const m = CG.ea.length;
  const seen = new Set();
  for (let i = 0; i < m; i++) {
    const a = CG.ea[i], b = CG.eb[i];
    const k = a < b ? a * 4294967296 + b : b * 4294967296 + a;
    if (seen.has(k)) continue;
    seen.add(k);
    const tx = taxi[a], w = link[a];
    const tr = w === 4294967295 ? -1 : transit[w];
    if (tx < 0 && tr < 0) continue;
    const dx = (CG.lat[a] - CG.lat[b]) * 111320;
    const dy = (CG.lon[a] - CG.lon[b]) * 84500;
    const len = Math.sqrt(dx * dx + dy * dy) / 1000;
    if (tr < 0) cabOnlyKm += len;
    else if (tx < 0) trainKm += len;
    else if (Math.abs(tx - tr) <= 120) tieKm += len;
    else if (tr < tx) trainKm += len;
    else cabKm += len;
  }
  $("#race-train").textContent = Math.round(trainKm).toLocaleString();
  $("#race-cab").textContent = Math.round(cabKm).toLocaleString();
  $("#race-cabonly").textContent = Math.round(cabOnlyKm).toLocaleString();
  $("#race-tie").textContent = Math.round(tieKm).toLocaleString();
}

/* ---------- controls ---------- */
function buildBandOptions() {
  const sel = $("#band");
  sel.innerHTML = "";
  const label = {
    weekday_am_peak: "Weekday morning rush (7–10am)",
    weekday_midday: "Weekday midday (10am–4pm)",
    weekday_pm_peak: "Weekday evening rush (4–7pm)",
    weekday_evening: "Weekday evening (7–11pm)",
    weekday_late: "Weekday late night (11pm–5am)",
    saturday_midday: "Saturday midday (10am–6pm)",
    sunday_midday: "Sunday midday (10am–6pm)",
  };
  for (const b of state.bands) {
    const o = document.createElement("option");
    o.value = b.id;
    o.textContent = label[b.id] || b.id;
    sel.appendChild(o);
  }
  sel.value = state.band;
}

function wireControls() {
  $("#access-toggle").addEventListener("click", () => {
    state.accessible = !state.accessible;
    $("#access-toggle").classList.toggle("on", state.accessible);
    $("#access-toggle").setAttribute("aria-pressed", String(state.accessible));
    $("#access-note").classList.toggle("open", state.accessible);
    document.body.classList.toggle("accessible", state.accessible);
    // A standard bicycle is not an accessible mode; gray it out, and if the
    // rider was in bike mode, fall back to transit.
    document.querySelector('.modes [data-mode="bike"]').disabled = state.accessible;
    if (state.accessible && state.mode === "bike") {
      state.mode = "transit";
      document.querySelectorAll(".modes [data-mode]").forEach((b) => b.classList.remove("on"));
      document.querySelector('.modes [data-mode="transit"]').classList.add("on");
      document.body.dataset.mode = "transit";
    }
    state.streetDist = null;
    runRoute();
  });

  document.querySelectorAll(".modes [data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".modes [data-mode]").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      state.mode = btn.dataset.mode;
      document.body.dataset.mode = state.mode;
      // The taxi graph uses its own node space, so a distance array computed
      // for another mode must not be drawn against it (and vice versa).
      state.streetDist = null;
      // Mode only changes which answer is drawn; the comparison already has all
      // six, so redraw from cache rather than recomputing everything.
      renderCompare();
      runRoute();
    });
  });

  const budget = $("#budget");
  budget.addEventListener("input", () => {
    state.budget = +budget.value * 60;
    $("#budget-val").textContent = budget.value;
    $("#legend-max").textContent = budget.value + " min";
  });
  budget.addEventListener("change", runRoute);

  $("#band").addEventListener("change", (e) => { state.band = e.target.value; runRoute(); });

  const ws = $("#walk-speed");
  ws.addEventListener("input", () => {
    state.walkSpeed = +ws.value;
    $("#walk-speed-val").textContent = (state.walkSpeed * 2.23694).toFixed(1);
  });
  ws.addEventListener("change", runRoute);

  const bs = $("#bike-speed");
  bs.addEventListener("input", () => {
    state.bikeSpeed = +bs.value;
    $("#bike-speed-val").textContent = (state.bikeSpeed * 2.23694).toFixed(1);
  });
  bs.addEventListener("change", runRoute);

  const mw = $("#max-wait");
  mw.addEventListener("input", () => {
    state.maxWait = +mw.value * 60;
    $("#max-wait-val").textContent = mw.value;
  });
  mw.addEventListener("change", runRoute);

  wireSearch();

  $("#ai-btn").addEventListener("click", () => $("#ai-note").classList.toggle("open"));
  $("#method-btn").addEventListener("click", () => $("#method").classList.toggle("open"));
  $("#method-close").addEventListener("click", () => $("#method").classList.remove("open"));
}

/* ---------- address search with autocomplete ---------- */
// Nominatim, debounced to one in-flight request and bounded to the city.
const NYC_VIEWBOX = "-74.30,40.45,-73.65,40.95";

function wireSearch() {
  const input = $("#search");
  const box = $("#suggest");
  let items = [];
  let sel = -1;
  let timer = null;
  let ctrl = null;

  function close() {
    box.classList.remove("open");
    input.setAttribute("aria-expanded", "false");
    items = []; sel = -1;
  }

  function pick(it) {
    close();
    input.value = it.display_name.split(",").slice(0, 2).join(",");
    $("#search-status").textContent = it.display_name.split(",").slice(0, 3).join(",");
    map.setView([+it.lat, +it.lon], 14);
    setOrigin(+it.lat, +it.lon);
  }

  function render() {
    if (!items.length) { close(); return; }
    box.innerHTML = items.map((it, i) => {
      const parts = it.display_name.split(",");
      return `<div class="sg${i === sel ? " sel" : ""}" data-i="${i}" role="option">` +
        `${parts[0].trim()}${parts[1] ? " " + parts[1].trim() : ""}` +
        `<small>${parts.slice(2, 5).join(",").trim()}</small></div>`;
    }).join("");
    box.classList.add("open");
    input.setAttribute("aria-expanded", "true");
    box.querySelectorAll(".sg").forEach((el) => {
      el.addEventListener("mousedown", (e) => { e.preventDefault(); pick(items[+el.dataset.i]); });
    });
  }

  async function lookup(q) {
    if (ctrl) ctrl.abort();
    ctrl = new AbortController();
    try {
      const url = "https://nominatim.openstreetmap.org/search?format=json&limit=5" +
        `&viewbox=${NYC_VIEWBOX}&bounded=1&q=` + encodeURIComponent(q);
      const r = await fetch(url, { headers: { Accept: "application/json" }, signal: ctrl.signal });
      const j = await r.json();
      items = j; sel = -1;
      render();
    } catch (err) {
      if (err.name !== "AbortError") close();
    }
  }

  input.addEventListener("input", () => {
    const q = input.value.trim();
    clearTimeout(timer);
    if (q.length < 3) { close(); return; }
    timer = setTimeout(() => lookup(q), 350);
  });

  input.addEventListener("keydown", (e) => {
    if (!items.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % items.length; render(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + items.length) % items.length; render(); }
    else if (e.key === "Escape") { close(); }
    else if (e.key === "Enter" && sel >= 0) { e.preventDefault(); pick(items[sel]); }
  });

  input.addEventListener("blur", () => setTimeout(close, 150));

  $("#search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearTimeout(timer);
    if (items.length) { pick(items[sel >= 0 ? sel : 0]); return; }
    const q = input.value.trim();
    if (!q) return;
    $("#search-status").textContent = "Looking up ...";
    try {
      const url = "https://nominatim.openstreetmap.org/search?format=json&limit=1" +
        `&viewbox=${NYC_VIEWBOX}&bounded=1&q=` + encodeURIComponent(q);
      const r = await fetch(url, { headers: { Accept: "application/json" } });
      const j = await r.json();
      if (!j.length) { $("#search-status").textContent = "No match found."; return; }
      pick(j[0]);
    } catch (err) {
      $("#search-status").textContent = "Lookup failed.";
    }
  });
}

window.addEventListener("DOMContentLoaded", () => {
  initMap();
  wireControls();
  initWorker();
});
