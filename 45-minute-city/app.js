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
  streetDist: null,
  reachedStops: [],
  meta: null,
  stops: [],
  bands: [],
};

let G = null; // street geometry on the main thread
let worker = null;
let map = null;
let reqId = 0;

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

    // project once per node, lazily, into container space
    const originPt = map.latLngToContainerPoint(map.getCenter());
    const px = G.px, py = G.py, seen = G.seen;
    G.stamp++;
    const stamp = G.stamp;

    const proj = (i) => {
      if (seen[i] !== stamp) {
        const p = map.latLngToContainerPoint([G.lat[i], G.lon[i]]);
        px[i] = p.x; py[i] = p.y; seen[i] = stamp;
      }
    };

    const dist = state.streetDist;
    const budget = state.budget;
    const m = G.ea.length;
    const mask = state.mode === "bike" ? 2 : 1;

    // Pass 1: the unreachable network, very dim, so the city stays legible.
    ctx.lineWidth = zoom >= 15 ? 0.6 : 0.4;
    ctx.strokeStyle = "rgba(120,140,170,0.16)";
    ctx.beginPath();
    for (let i = 0; i < m; i++) {
      if (!(G.ef[i] & mask)) continue;
      const a = G.ea[i], b = G.eb[i];
      const la = G.lat[a], lo = G.lon[a];
      if (la > north || la < south || lo < west || lo > east) {
        const lb = G.lat[b], ob = G.lon[b];
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
      if (!(G.ef[i] & mask)) continue;
      const a = G.ea[i], b = G.eb[i];
      const da = dist[a], db = dist[b];
      if (da < 0 || db < 0) continue;
      const la = G.lat[a], lo = G.lon[a];
      if (la > north || la < south || lo < west || lo > east) {
        const lb = G.lat[b], ob = G.lon[b];
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
        const a = G.ea[i], b = G.eb[i];
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
  worker = new Worker("worker.js");
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
      state.originNode = m.node;
      runRoute();
    }
    if (m.type === "routed") {
      const job = pending.get(m.id);
      pending.delete(m.id);
      if (!job) return;
      const dist = new Float32Array(m.streetDist);
      if (job.purpose === "compare") {
        compare[job.mode] = computeKm(dist, job.mode === "bike" ? 2 : 1);
        renderCompare();
        return;
      }
      if (m.id !== reqId) return;
      state.streetDist = dist;
      state.reachedStops = m.reachedStops;
      reachLayer.draw();
      updateStats(m.stats);
      $("#panel").classList.remove("busy");
      runCompare();
    }
  };
  worker.postMessage({ type: "init", base: "" });
}

function setOrigin(lat, lng) {
  state.originLatLng = [lat, lng];
  if (window._originMarker) map.removeLayer(window._originMarker);
  window._originMarker = L.circleMarker([lat, lng], {
    radius: 7, color: "#fff", weight: 2.5, fillColor: "#111", fillOpacity: 1,
  }).addTo(map);
  $("#panel").classList.add("busy");
  worker.postMessage({ type: "snap", id: ++reqId, lat, lon: lng });
}

const pending = new Map();
const MODES = ["walk", "bike", "subway", "bus", "transit"];
const MODE_LABEL = { walk: "Walk", bike: "Bike", subway: "Subway", bus: "Bus", transit: "Subway + bus" };
let compare = {};

function opts(mode) {
  return {
    originNode: state.originNode,
    budget: state.budget,
    mode,
    walkSpeed: state.walkSpeed,
    bikeSpeed: state.bikeSpeed,
    bandId: state.band,
    maxWait: state.maxWait,
  };
}

function runRoute() {
  if (!state.ready || state.originNode < 0) return;
  $("#panel").classList.add("busy");
  compare = {};
  renderCompare();
  const id = ++reqId;
  pending.set(id, { purpose: "render", mode: state.mode });
  worker.postMessage({ type: "route", id, opts: opts(state.mode) });
}

// Run every mode from the same origin so they can be compared on equal terms.
function runCompare() {
  for (const mode of MODES) {
    const id = ++reqId;
    pending.set(id, { purpose: "compare", mode });
    worker.postMessage({ type: "route", id, opts: opts(mode) });
  }
}

function computeKm(dist, mask) {
  let m2 = 0;
  const m = G.ea.length;
  for (let i = 0; i < m; i++) {
    if (!(G.ef[i] & mask)) continue;
    const a = G.ea[i], b = G.eb[i];
    if (dist[a] < 0 || dist[b] < 0) continue;
    const dx = (G.lat[a] - G.lat[b]) * 111320;
    const dy = (G.lon[a] - G.lon[b]) * 84500;
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
    return `<div class="cmp-row${m === state.mode ? " on" : ""}">
      <div class="cmp-k">${MODE_LABEL[m]}</div>
      <div class="cmp-bar"><i style="width:${w}%"></i></div>
      <div class="cmp-v">${v === undefined ? "—" : Math.round(v).toLocaleString()}</div>
    </div>`;
  }).join("");
}

/* ---------- stats ---------- */
function updateStats(stats) {
  const dist = state.streetDist;
  let reachableM = 0;
  const m = G.ea.length;
  const mask = state.mode === "bike" ? 2 : 1;
  for (let i = 0; i < m; i++) {
    if (!(G.ef[i] & mask)) continue;
    const a = G.ea[i], b = G.eb[i];
    if (dist[a] < 0 || dist[b] < 0) continue;
    const dx = (G.lat[a] - G.lat[b]) * 111320;
    const dy = (G.lon[a] - G.lon[b]) * 84500;
    reachableM += Math.sqrt(dx * dx + dy * dy);
  }
  const km = reachableM / 1000;
  $("#stat-km").textContent = km.toLocaleString(undefined, { maximumFractionDigits: 0 });

  const subway = state.reachedStops.filter((s) => state.stops[s[0]][3] === 0).length;
  const bus = state.reachedStops.length - subway;
  $("#stat-subway").textContent = subway.toLocaleString();
  $("#stat-bus").textContent = bus.toLocaleString();
  $("#stat-time").textContent = stats.ms + " ms";
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
  document.querySelectorAll("[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-mode]").forEach((b) => b.classList.remove("on"));
      btn.classList.add("on");
      state.mode = btn.dataset.mode;
      document.body.dataset.mode = state.mode;
      // Mode only changes which answer is drawn; the comparison already has all
      // five, so redraw from cache rather than recomputing everything.
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

  $("#search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = $("#search").value.trim();
    if (!q) return;
    $("#search-status").textContent = "Looking up ...";
    try {
      const url =
        "https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&q=" +
        encodeURIComponent(q + ", New York City");
      const r = await fetch(url, { headers: { Accept: "application/json" } });
      const j = await r.json();
      if (!j.length) { $("#search-status").textContent = "No match found."; return; }
      $("#search-status").textContent = j[0].display_name.split(",").slice(0, 3).join(",");
      map.setView([+j[0].lat, +j[0].lon], 14);
      setOrigin(+j[0].lat, +j[0].lon);
    } catch (err) {
      $("#search-status").textContent = "Lookup failed.";
    }
  });

  $("#ai-btn").addEventListener("click", () => $("#ai-note").classList.toggle("open"));
  $("#method-btn").addEventListener("click", () => $("#method").classList.toggle("open"));
  $("#method-close").addEventListener("click", () => $("#method").classList.remove("open"));
}

window.addEventListener("DOMContentLoaded", () => {
  initMap();
  wireControls();
  initWorker();
});
