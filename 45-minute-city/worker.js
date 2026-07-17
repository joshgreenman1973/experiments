// Multimodal router for The 45-Minute City.
//
// Graph model. Street nodes carry walking and cycling. Transit is modelled with
// one state per (stop, route, direction), which is what makes the wait honest:
// you pay a wait when you BOARD, and riding from stop to stop is free after
// that. A naive graph that put a wait on every edge would charge you a wait at
// all thirty stops down Lexington Avenue.
//
//   street -> street          walk or bike time over real CSCL geometry
//   street -> (stop,route,dir) board: wait = headway / 2, capped
//   (s,r,d) -> (s2,r,d)       ride: median scheduled time from MTA GTFS
//   (s,r,d) -> street         alight: free
//
// Transfers fall out of the model: you alight to the street, walk, and board
// again, paying that route's wait.

let S = null; // streets (walk/bike)
let C = null; // core
let CAR = null; // directed drivable graph + per-band traffic calibration
let bandCache = new Map();

const WALK_BIT = 1;
const BIKE_BIT = 2;

function buildCSR(nNodes, ea, eb, ed, ef) {
  const m = ea.length;
  const deg = new Uint32Array(nNodes + 1);
  for (let i = 0; i < m; i++) { deg[ea[i]]++; deg[eb[i]]++; }
  const off = new Uint32Array(nNodes + 1);
  let acc = 0;
  for (let i = 0; i < nNodes; i++) { off[i] = acc; acc += deg[i]; }
  off[nNodes] = acc;
  const cur = off.slice();
  const tgt = new Uint32Array(acc);
  const dst = new Uint16Array(acc);
  const flg = new Uint8Array(acc);
  for (let i = 0; i < m; i++) {
    const a = ea[i], b = eb[i], d = ed[i], f = ef[i];
    tgt[cur[a]] = b; dst[cur[a]] = d; flg[cur[a]] = f; cur[a]++;
    tgt[cur[b]] = a; dst[cur[b]] = d; flg[cur[b]] = f; cur[b]++;
  }
  return { off, tgt, dst, flg };
}

// Binary heap keyed on Float64 distance.
class Heap {
  constructor(cap) { this.d = new Float64Array(cap); this.n = new Uint32Array(cap); this.size = 0; }
  push(dist, node) {
    if (this.size === this.d.length) {
      const nd = new Float64Array(this.size * 2); nd.set(this.d); this.d = nd;
      const nn = new Uint32Array(this.size * 2); nn.set(this.n); this.n = nn;
    }
    let i = this.size++;
    this.d[i] = dist; this.n[i] = node;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.d[p] <= this.d[i]) break;
      this.swap(i, p); i = p;
    }
  }
  pop() {
    const topD = this.d[0], topN = this.n[0];
    this.size--;
    if (this.size > 0) {
      this.d[0] = this.d[this.size]; this.n[0] = this.n[this.size];
      let i = 0;
      for (;;) {
        const l = 2 * i + 1, r = l + 1;
        let s = i;
        if (l < this.size && this.d[l] < this.d[s]) s = l;
        if (r < this.size && this.d[r] < this.d[s]) s = r;
        if (s === i) break;
        this.swap(i, s); i = s;
      }
    }
    return [topD, topN];
  }
  swap(a, b) {
    const d = this.d[a]; this.d[a] = this.d[b]; this.d[b] = d;
    const n = this.n[a]; this.n[a] = this.n[b]; this.n[b] = n;
  }
}

function parseBand(buf, idx) {
  const dv = new DataView(buf);
  const rc = idx.ride_count, hc = idx.headway_count;
  const ride = {
    a: new Uint16Array(rc), b: new Uint16Array(rc), r: new Uint16Array(rc),
    d: new Uint8Array(rc), t: new Uint16Array(rc),
  };
  let o = idx.ride_offset;
  for (let i = 0; i < rc; i++) {
    ride.a[i] = dv.getUint16(o, true);
    ride.b[i] = dv.getUint16(o + 2, true);
    ride.r[i] = dv.getUint16(o + 4, true);
    ride.d[i] = dv.getUint8(o + 6);
    ride.t[i] = dv.getUint16(o + 7, true);
    o += 9;
  }
  const hw = new Map(); // key -> seconds
  o = idx.headway_offset;
  for (let i = 0; i < hc; i++) {
    const s = dv.getUint16(o, true);
    const r = dv.getUint16(o + 2, true);
    const d = dv.getUint8(o + 4);
    const t = dv.getUint16(o + 5, true);
    hw.set(s * 200000 + r * 2 + d, t);
    o += 7;
  }
  return { ride, hw };
}

// Build the transit state graph for a band: one node per (stop, route, dir).
function buildBand(bandId) {
  if (bandCache.has(bandId)) return bandCache.get(bandId);
  const idx = C.bandIndex[bandId];
  const { ride, hw } = parseBand(C.bandsBuf, idx);

  const stateId = new Map();
  const stateStop = [], stateRoute = [], stateDir = [];
  const key = (s, r, d) => s * 200000 + r * 2 + d;
  function getState(s, r, d) {
    const k = key(s, r, d);
    let i = stateId.get(k);
    if (i === undefined) {
      i = stateStop.length;
      stateId.set(k, i);
      stateStop.push(s); stateRoute.push(r); stateDir.push(d);
    }
    return i;
  }

  const from = [], to = [], cost = [];
  for (let i = 0; i < ride.a.length; i++) {
    const u = getState(ride.a[i], ride.r[i], ride.d[i]);
    const v = getState(ride.b[i], ride.r[i], ride.d[i]);
    from.push(u); to.push(v); cost.push(ride.t[i]);
  }

  const nStates = stateStop.length;
  // CSR over the directed ride edges
  const deg = new Uint32Array(nStates + 1);
  for (const u of from) deg[u]++;
  const off = new Uint32Array(nStates + 1);
  let acc = 0;
  for (let i = 0; i < nStates; i++) { off[i] = acc; acc += deg[i]; }
  off[nStates] = acc;
  const cur = off.slice();
  const tgt = new Uint32Array(acc), cst = new Uint16Array(acc);
  for (let i = 0; i < from.length; i++) {
    tgt[cur[from[i]]] = to[i]; cst[cur[from[i]]] = cost[i]; cur[from[i]]++;
  }

  // states grouped by stop, so a street node can board everything at its stops
  const byStop = new Map();
  for (let i = 0; i < nStates; i++) {
    let arr = byStop.get(stateStop[i]);
    if (!arr) { arr = []; byStop.set(stateStop[i], arr); }
    arr.push(i);
  }

  const band = {
    nStates, off, tgt, cst, byStop, hw,
    stateStop: Uint16Array.from(stateStop),
    stateRoute: Uint16Array.from(stateRoute),
    stateDir: Uint8Array.from(stateDir),
  };
  bandCache.set(bandId, band);
  return band;
}

// Taxi: Dijkstra over the directed car graph. Edge cost is length at the
// posted speed limit, slowed by the band's measured traffic factor (median of
// real TLC yellow-cab trips vs the same journey routed at posted speeds).
function routeTaxi(opts) {
  const t0 = performance.now();
  const { originCarNode, budget, bandId, accessible, traffic } = opts;
  const fallbackAlpha = CAR.alpha[bandId] || 2.5;
  const alphaCls = (CAR.alphaByClass[bandId] || {})[traffic || "typical"];
  const zc = CAR.zoneClass;
  const nC = CAR.n;
  const dist = new Float64Array(nC).fill(Infinity);
  const heap = new Heap(1 << 16);
  // The clock starts at the REQUEST, not when the wheels move — same rule as
  // transit, which pays its platform wait. Median request-to-pickup gap from
  // the month's Uber/Lyft records: ~4 min standard, ~7-8 min for a
  // wheelchair-accessible vehicle.
  const bandWaits = C.access.wav[bandId] || {};
  let start = accessible
    ? (bandWaits.wav_wait_secs !== undefined ? bandWaits.wav_wait_secs : 480)
    : (bandWaits.standard_wait_secs !== undefined ? bandWaits.standard_wait_secs : 260);
  if (start > budget) {
    return { streetDist: new Float32Array(nC).fill(-1), reachedStops: [],
             stats: { settled: 0, ms: Math.round(performance.now() - t0) } };
  }
  dist[originCarNode] = start;
  heap.push(start, originCarNode);
  const { off, tgt, base } = CAR.csr;
  let settled = 0;
  while (heap.size > 0) {
    const [d, u] = heap.pop();
    if (d > dist[u] || d > budget) continue;
    settled++;
    // Congestion by borough of the street being driven.
    const a = alphaCls ? alphaCls[zc[u]] : fallbackAlpha;
    for (let e = off[u]; e < off[u + 1]; e++) {
      const nd = d + base[e] * a;
      const v = tgt[e];
      if (nd < dist[v] && nd <= budget) { dist[v] = nd; heap.push(nd, v); }
    }
  }
  const out = new Float32Array(nC);
  for (let i = 0; i < nC; i++) out[i] = dist[i] > budget ? -1 : dist[i];
  return { streetDist: out, reachedStops: [], stats: { settled, ms: Math.round(performance.now() - t0) } };
}

function route(opts) {
  if (opts.mode === "taxi") return routeTaxi(opts);
  const t0 = performance.now();
  const { originNode, budget, mode, walkSpeed, bikeSpeed, bandId, maxWait, accessible } = opts;
  const nS = C.nStreetNodes;
  const useBike = mode === "bike";
  // Accessible mode rolls, not walks: the bike flag is the street network
  // minus step streets (stairs), which is the wheelchair-usable network.
  const mask = useBike || accessible ? BIKE_BIT : WALK_BIT;
  const speed = useBike ? bikeSpeed : walkSpeed; // m/s
  const useTransit = mode === "subway" || mode === "bus" || mode === "transit";

  let band = null, nStates = 0;
  if (useTransit) { band = buildBand(bandId); nStates = band.nStates; }

  const total = nS + nStates;
  const dist = new Float64Array(total).fill(Infinity);
  const heap = new Heap(1 << 16);
  dist[originNode] = 0;
  heap.push(0, originNode);

  const { off, tgt, dst, flg } = S.csr;
  const stopsAtNode = C.stopsAtNode;
  const routeKind = C.routeKind;
  const stopStreetNode = C.stopStreetNode;

  let settled = 0;
  while (heap.size > 0) {
    const [d, u] = heap.pop();
    if (d > dist[u]) continue;
    if (d > budget) continue;
    settled++;

    if (u < nS) {
      // street node: walk/bike out
      for (let e = off[u]; e < off[u + 1]; e++) {
        if (!(flg[e] & mask)) continue;
        const nd = d + (dst[e] / 10) / speed;
        const v = tgt[e];
        if (nd < dist[v] && nd <= budget) { dist[v] = nd; heap.push(nd, v); }
      }
      // board transit at any stop snapped to this node
      if (useTransit) {
        const stops = stopsAtNode.get(u);
        if (stops) {
          for (const s of stops) {
            if (accessible && !C.stopAda[s]) continue; // no elevator, no boarding
            const states = band.byStop.get(s);
            if (!states) continue;
            for (const st of states) {
              const kind = routeKind[band.stateRoute[st]];
              if (mode === "subway" && kind !== 0) continue;
              if (mode === "bus" && kind !== 1) continue;
              const h = band.hw.get(s * 200000 + band.stateRoute[st] * 2 + band.stateDir[st]);
              if (h === undefined) continue;
              const wait = Math.min(h / 2, maxWait);
              const nd = d + wait;
              const v = nS + st;
              if (nd < dist[v] && nd <= budget) { dist[v] = nd; heap.push(nd, v); }
            }
          }
        }
      }
    } else {
      // onboard a route: ride on, or alight to the street for free
      const st = u - nS;
      for (let e = band.off[st]; e < band.off[st + 1]; e++) {
        const nd = d + band.cst[e];
        const v = nS + band.tgt[e];
        if (nd < dist[v] && nd <= budget) { dist[v] = nd; heap.push(nd, v); }
      }
      // A handful of stops sit outside city limits (bus routes that dip into
      // Nassau County) and have no street node; their snap is stored as -1,
      // which reads back from the Uint32Array as 0xFFFFFFFF. Riding THROUGH
      // them still works; you just can't get on or off there. In accessible
      // mode the same applies to subway stations without elevators.
      const alightStop = band.stateStop[st];
      const sn = stopStreetNode[alightStop];
      if (sn !== 4294967295 && (!accessible || C.stopAda[alightStop]) && d < dist[sn]) {
        dist[sn] = d; heap.push(d, sn);
      }
    }
  }

  const streetDist = new Float32Array(nS);
  for (let i = 0; i < nS; i++) streetDist[i] = dist[i] > budget ? -1 : dist[i];

  // Which stops did we actually reach, and how?
  const reachedStops = [];
  if (useTransit) {
    const best = new Map();
    for (let st = 0; st < nStates; st++) {
      const dd = dist[nS + st];
      if (dd > budget) continue;
      const s = band.stateStop[st];
      // In accessible mode a station you can only ride THROUGH is not a
      // station you reached — count egress-usable stops only.
      if (accessible && !C.stopAda[s]) continue;
      if (!best.has(s) || dd < best.get(s)) best.set(s, dd);
    }
    for (const [s, dd] of best) reachedStops.push([s, Math.round(dd)]);
  }

  return {
    streetDist, reachedStops,
    stats: { settled, ms: Math.round(performance.now() - t0) },
  };
}

self.onmessage = async (e) => {
  const msg = e.data;
  if (msg.type === "init") {
    const base = msg.base || "";
    const q = "?v=" + (msg.v || "dev");
    const [core, bandIndex, nodesBuf, edgesBuf, bandsBuf, carNodesBuf, carEdgesBuf, carCal, access, carCal2, carZonesBuf, carLinkBuf] = await Promise.all([
      fetch(base + "data/core.json" + q).then((r) => r.json()),
      fetch(base + "data/bands.json" + q).then((r) => r.json()),
      fetch(base + "data/street_nodes.bin" + q).then((r) => r.arrayBuffer()),
      fetch(base + "data/street_edges.bin" + q).then((r) => r.arrayBuffer()),
      fetch(base + "data/bands.bin" + q).then((r) => r.arrayBuffer()),
      fetch(base + "data/car_nodes.bin" + q).then((r) => r.arrayBuffer()),
      fetch(base + "data/car_edges.bin" + q).then((r) => r.arrayBuffer()),
      fetch(base + "data/car_calibration.json" + q).then((r) => r.json()),
      fetch(base + "data/access.json" + q).then((r) => r.json()),
      fetch(base + "data/car_calibration2.json" + q).then((r) => r.json()),
      fetch(base + "data/car_zones.bin" + q).then((r) => r.arrayBuffer()),
      fetch(base + "data/car_link.bin" + q).then((r) => r.arrayBuffer()),
    ]);

    // streets
    const nNodes = nodesBuf.byteLength / 8;
    const ni = new Int32Array(nodesBuf);
    const lat = new Float64Array(nNodes), lon = new Float64Array(nNodes);
    for (let i = 0; i < nNodes; i++) { lat[i] = ni[i * 2] / 1e6; lon[i] = ni[i * 2 + 1] / 1e6; }

    const m = edgesBuf.byteLength / 11;
    const dv = new DataView(edgesBuf);
    const ea = new Uint32Array(m), eb = new Uint32Array(m);
    const ed = new Uint16Array(m), ef = new Uint8Array(m);
    for (let i = 0; i < m; i++) {
      const o = i * 11;
      ea[i] = dv.getUint32(o, true);
      eb[i] = dv.getUint32(o + 4, true);
      ed[i] = dv.getUint16(o + 8, true);
      ef[i] = dv.getUint8(o + 10);
    }
    S = { lat, lon, ea, eb, ed, ef, csr: buildCSR(nNodes, ea, eb, ed, ef) };

    // core
    const stopStreetNode = new Uint32Array(core.stops.length);
    const stopsAtNode = new Map();
    for (let i = 0; i < core.stops.length; i++) {
      const n = core.stops[i][4];
      stopStreetNode[i] = n;
      let arr = stopsAtNode.get(n);
      if (!arr) { arr = []; stopsAtNode.set(n, arr); }
      arr.push(i);
    }
    // ADA flags per stop. Buses are 100% ramp-equipped, so every bus stop is
    // accessible; subway stops are accessible only if the MTA lists their
    // station (1 = fully, 2 = one direction — treated as accessible, caveat
    // documented in the methodology).
    const stopAda = new Uint8Array(core.stops.length);
    for (let i = 0; i < core.stops.length; i++) {
      const s = core.stops[i];
      stopAda[i] = s[3] === 1 ? 1 : (access.stations[s[5]] ? 1 : 0);
    }
    C = {
      core, bandIndex, bandsBuf,
      nStreetNodes: nNodes,
      stopStreetNode, stopsAtNode, stopAda,
      routeKind: Uint8Array.from(core.routes.map((r) => r[1])),
      access,
    };

    // spatial hash for snapping a clicked point to the network
    const CELL = 0.004;
    const grid = new Map();
    for (let i = 0; i < nNodes; i++) {
      const k = Math.floor(lat[i] / CELL) + ":" + Math.floor(lon[i] / CELL);
      let a = grid.get(k);
      if (!a) { a = []; grid.set(k, a); }
      a.push(i);
    }
    S.grid = grid; S.CELL = CELL;

    // ---- directed car graph
    const nC = carNodesBuf.byteLength / 8;
    const cni = new Int32Array(carNodesBuf);
    const cLat = new Float64Array(nC), cLon = new Float64Array(nC);
    for (let i = 0; i < nC; i++) { cLat[i] = cni[i * 2] / 1e6; cLon[i] = cni[i * 2 + 1] / 1e6; }
    const mC = carEdgesBuf.byteLength / 11;
    const cdv = new DataView(carEdgesBuf);
    const cea = new Uint32Array(mC), ceb = new Uint32Array(mC);
    const cBase = new Float32Array(mC); // seconds at posted speed
    for (let i = 0; i < mC; i++) {
      const o = i * 11;
      cea[i] = cdv.getUint32(o, true);
      ceb[i] = cdv.getUint32(o + 4, true);
      const meters = cdv.getUint16(o + 8, true) / 10;
      const mph = cdv.getUint8(o + 10);
      cBase[i] = meters / (mph * 0.44704);
    }
    // directed CSR
    const cDeg = new Uint32Array(nC + 1);
    for (let i = 0; i < mC; i++) cDeg[cea[i]]++;
    const cOff = new Uint32Array(nC + 1);
    let cAcc = 0;
    for (let i = 0; i < nC; i++) { cOff[i] = cAcc; cAcc += cDeg[i]; }
    cOff[nC] = cAcc;
    const cCur = cOff.slice();
    const cTgt = new Uint32Array(cAcc);
    const cSecs = new Float32Array(cAcc);
    for (let i = 0; i < mC; i++) {
      cTgt[cCur[cea[i]]] = ceb[i]; cSecs[cCur[cea[i]]] = cBase[i]; cCur[cea[i]]++;
    }
    const cGrid = new Map();
    for (let i = 0; i < nC; i++) {
      const k = Math.floor(cLat[i] / CELL) + ":" + Math.floor(cLon[i] / CELL);
      let a = cGrid.get(k);
      if (!a) { a = []; cGrid.set(k, a); }
      a.push(i);
    }
    const alpha = {};
    for (const [b, v] of Object.entries(carCal.bands || {})) alpha[b] = v.alpha;
    // Per-borough traffic factors: intra-borough Uber/Lyft trips give each
    // borough its own alpha (Manhattan midday 2.85 vs Queens 2.11), applied by
    // the edge's from-node borough class. Citywide is the fallback.
    const zoneClass = new Uint8Array(carZonesBuf);
    const BOROUGHS = carCal2.boroughs || [];
    // Three traffic levels, all measured: light is the 25th-percentile trip for
    // that borough and hour, typical the median, heavy the 75th. Nothing here
    // is a guess about "bad traffic" — each is a real quartile of real trips.
    const alphaByClass = {};
    for (const [band, entry] of Object.entries(carCal2.bands || {})) {
      const mk = (key) => {
        const arr = new Float32Array(Math.max(1, BOROUGHS.length));
        for (let i = 0; i < BOROUGHS.length; i++) {
          const bb = (entry.by_borough || {})[BOROUGHS[i]];
          arr[i] = bb ? bb[key] : entry.citywide.alpha;
        }
        return arr;
      };
      alphaByClass[band] = { light: mk("p25"), typical: mk("alpha"), heavy: mk("p75") };
    }
    CAR = {
      n: nC, lat: cLat, lon: cLon, grid: cGrid,
      csr: { off: cOff, tgt: cTgt, base: cSecs },
      alpha, calibration: carCal,
      zoneClass, alphaByClass, calibration2: carCal2,
    };

    const cLatCopy = cLat.slice(), cLonCopy = cLon.slice();
    self.postMessage({
      type: "ready",
      nNodes, nEdges: m,
      nStops: core.stops.length,
      nRoutes: core.routes.length,
      nCarNodes: nC, nCarEdges: mC,
      meta: core.meta,
      bands: core.bands,
      carCalibration: carCal,
      carCalibration2: carCal2,
      access,
      lat: lat.buffer, lon: lon.buffer,
      ea: ea.buffer, eb: eb.buffer, ef: ef.buffer,
      carLat: cLatCopy.buffer, carLon: cLonCopy.buffer,
      cea: cea.buffer, ceb: ceb.buffer,
      carLink: carLinkBuf,
      stops: core.stops,
    }, [lat.buffer, lon.buffer, ea.buffer, eb.buffer, ef.buffer,
        cLatCopy.buffer, cLonCopy.buffer, cea.buffer, ceb.buffer, carLinkBuf]);
    // rebuild worker-side views (buffers were transferred away)
    const nb = new Int32Array(nodesBuf);
    const la = new Float64Array(nNodes), lo = new Float64Array(nNodes);
    for (let i = 0; i < nNodes; i++) { la[i] = nb[i * 2] / 1e6; lo[i] = nb[i * 2 + 1] / 1e6; }
    S.lat = la; S.lon = lo;
    return;
  }

  if (msg.type === "snap") {
    self.postMessage({
      type: "snapped", id: msg.id,
      node: snap(msg.lat, msg.lon, S.grid, S.lat, S.lon),
      carNode: snap(msg.lat, msg.lon, CAR.grid, CAR.lat, CAR.lon),
    });
    return;
  }

  if (msg.type === "route") {
    const res = route(msg.opts);
    self.postMessage(
      { type: "routed", id: msg.id, streetDist: res.streetDist.buffer, reachedStops: res.reachedStops, stats: res.stats },
      [res.streetDist.buffer]
    );
  }
};

function snap(la, lo, grid, lats, lons) {
  const CELL = S.CELL;
  const ci = Math.floor(la / CELL), cj = Math.floor(lo / CELL);
  let best = -1, bd = Infinity;
  for (let r = 0; r < 6; r++) {
    for (let i = ci - r; i <= ci + r; i++) {
      for (let j = cj - r; j <= cj + r; j++) {
        if (r > 0 && Math.abs(i - ci) !== r && Math.abs(j - cj) !== r) continue;
        const arr = grid.get(i + ":" + j);
        if (!arr) continue;
        for (const n of arr) {
          const dx = (lats[n] - la) * 111320;
          const dy = (lons[n] - lo) * 84000;
          const d = dx * dx + dy * dy;
          if (d < bd) { bd = d; best = n; }
        }
      }
    }
    if (best >= 0 && r >= 1) break;
  }
  return best;
}
