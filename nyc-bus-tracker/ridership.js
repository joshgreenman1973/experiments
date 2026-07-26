/**
 * The People on the Bus — companion to All Through the Town.
 * Every NYC bus stop, sized by boardings at each hour of the day.
 * Data: MTA Bus Stop Level Ridership (fvdm-uavx), June 2026, baked into
 * data/ridership/stops.json by scripts in the repo.
 */

const TILE_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const DATA_URL = 'data/ridership/stops.json';

// ember ramp (sequential, one hue) — matches ridership.css
const RAMP = ['#2b0f06', '#6b2409', '#b34a14', '#f07a2e', '#ffab5e', '#ffd9ae'];

let map;
let raw = null;              // parsed stops.json
let fc = { wd: null, we: null }; // FeatureCollections keyed by day type
let vmax = 1;                // max avg hourly boardings at any stop (shared scale)
let citywide = { wd: [], we: [] }; // avg boardings per hour, citywide
let hour = 7;                // current hour on display
let daytype = 'wd';
let playing = false;
let playTimer = null;
let tweenFrame = null;
let leaderCache = {};        // `${dt}${h}` → sorted top rows
let popup = null;
let popupStop = null;        // {id, lngLat} of the open popup, for live refresh

const $ = (id) => document.getElementById(id);
const fmt = (n) => n >= 10000 ? Math.round(n).toLocaleString('en-US')
  : n >= 100 ? Math.round(n).toLocaleString('en-US')
  : n >= 10 ? String(Math.round(n))
  : (Math.round(n * 10) / 10).toString();

// "W 181 ST/BROADWAY" → "W 181 St/Broadway"
function titleCase(s) {
  return s.toLowerCase().replace(/(^|[\s/\-("])([a-z])/g, (m, p, c) => p + c.toUpperCase())
    .replace(/\b(Av|St|Rd|Blvd|Pl|Dr|Ln|Ct|Expwy|Pkwy|Tpke|Ter|Sq|Br)\b/g, (m) => m)
    .replace(/\b([NSEW])\b/gi, (m) => m.toUpperCase());
}

function hourLabel(h) {
  const name = (x) => {
    const hr = x % 24;
    const h12 = hr % 12 === 0 ? 12 : hr % 12;
    return { n: h12, ap: hr < 12 ? 'AM' : 'PM' };
  };
  const a = name(h), b = name(h + 1);
  if (a.ap === b.ap) return { text: `${a.n}–${b.n}`, ap: a.ap };
  return { text: `${a.n} ${a.ap}–${b.n}`, ap: b.ap };
}

// ═══ data ═══
async function loadData() {
  const res = await fetch(DATA_URL);
  if (!res.ok) throw new Error(`data fetch failed: ${res.status}`);
  raw = await res.json();
  const days = raw.days; // {wd: 22, we: 8}

  for (const dt of ['wd', 'we']) {
    const d = days[dt];
    const feats = [];
    const cw = new Array(24).fill(0);
    for (const s of raw.stops) {
      const [id, name, lon, lat, routes, wdArr, weArr] = s;
      const arr = dt === 'wd' ? wdArr : weArr;
      const p = { id, name };
      let stopMax = 0;
      for (let h = 0; h < 24; h++) {
        const v = arr[h] / d; // avg per day of this type
        p['h' + h] = Math.round(v * 10) / 10;
        cw[h] += v;
        if (v > stopMax) stopMax = v;
      }
      if (stopMax > vmax) vmax = stopMax;
      feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: p });
    }
    citywide[dt] = cw;
    fc[dt] = { type: 'FeatureCollection', features: feats };
  }
  // index for popups/leaderboard
  raw.index = new Map(raw.stops.map((s) => [s[0], s]));
}

// mix of two hourly properties: (1-t)*hA + t*hB
function valExpr(hA, hB, t) {
  if (t <= 0 || hA === hB) return ['to-number', ['get', 'h' + hA]];
  return ['+',
    ['*', ['to-number', ['get', 'h' + hA]], 1 - t],
    ['*', ['to-number', ['get', 'h' + hB]], t]];
}

function paintFor(hA, hB, t) {
  const v = valExpr(hA, hB, t);
  const norm = ['sqrt', ['/', v, vmax]]; // 0..1, area ∝ value
  const radius = ['interpolate', ['linear'], ['zoom'],
    9, ['*', 10, norm],
    11, ['*', 22, norm],
    13, ['*', 46, norm],
    15.5, ['*', 110, norm]];
  const color = ['interpolate', ['linear'], norm,
    0.03, RAMP[0], 0.18, RAMP[1], 0.38, RAMP[2],
    0.62, RAMP[3], 0.85, RAMP[4], 1.0, RAMP[5]];
  return { radius, color };
}

function applyHour(hA, hB, t) {
  const p = paintFor(hA, hB, t);
  map.setPaintProperty('boardings', 'circle-radius', p.radius);
  map.setPaintProperty('boardings', 'circle-color', p.color);
}

// animate from previous hour to new hour (~420ms)
function setHour(h, opts = {}) {
  const prev = hour;
  hour = ((h % 24) + 24) % 24;
  updateClock(); updateLeaders(); updatePlayhead(); refreshPopup();
  writeUrl();
  if (!map || !map.getLayer('boardings')) return;
  if (opts.instant || prev === hour) { applyHour(hour, hour, 0); return; }
  if (tweenFrame) cancelAnimationFrame(tweenFrame);
  const t0 = performance.now(), dur = 420;
  const from = prev;
  const step = (now) => {
    const t = Math.min(1, (now - t0) / dur);
    const e = t * (2 - t); // ease-out
    applyHour(from, hour, e);
    if (t < 1) tweenFrame = requestAnimationFrame(step);
  };
  tweenFrame = requestAnimationFrame(step);
}

function setDaytype(dt) {
  if (dt === daytype) return;
  daytype = dt;
  document.querySelectorAll('.dt-btn').forEach((b) => {
    const on = b.dataset.dt === dt;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on);
  });
  if (map && map.getSource('stops')) map.getSource('stops').setData(fc[dt]);
  $('leader-daytype').textContent = dt === 'wd' ? 'weekday avg' : 'weekend avg';
  drawCurve(); updateClock(); updateLeaders(); refreshPopup();
  writeUrl();
}

function refreshPopup() {
  if (popup && popup.isOpen() && popupStop) openPopup(popupStop.id, popupStop.lngLat);
}

function writeUrl() {
  const u = new URL(window.location);
  u.searchParams.set('h', hour);
  u.searchParams.set('d', daytype);
  history.replaceState(null, '', u);
}

// ═══ panel ═══
function updateClock() {
  const lab = hourLabel(hour);
  $('clock-hour').innerHTML = `${lab.text} <em>${lab.ap}</em>`;
  const riders = citywide[daytype][hour] || 0;
  const rounded = riders >= 1000 ? Math.round(riders / 100) * 100 : Math.round(riders);
  $('clock-riders').textContent = '≈' + rounded.toLocaleString('en-US');
  $('clock-riders-label').textContent =
    `riders board citywide in this hour on an average ${daytype === 'wd' ? 'weekday' : 'weekend day'}`;
  const peakH = citywide[daytype].indexOf(Math.max(...citywide[daytype]));
  const pl = hourLabel(peakH);
  $('clock-note').textContent = hour === peakH
    ? 'This is the busiest hour of the day.'
    : `Busiest hour: ${pl.text} ${pl.ap}.`;
}

function leadersFor(dt, h) {
  const key = dt + h;
  if (leaderCache[key]) return leaderCache[key];
  const d = raw.days[dt];
  const rows = [];
  for (const s of raw.stops) {
    const v = (dt === 'wd' ? s[5] : s[6])[h] / d;
    if (v > 0) rows.push({ id: s[0], name: s[1], lon: s[2], lat: s[3], routes: s[4], v });
  }
  rows.sort((a, b) => b.v - a.v);
  leaderCache[key] = rows.slice(0, 8);
  return leaderCache[key];
}

function updateLeaders() {
  if (!raw) return;
  const rows = leadersFor(daytype, hour);
  const max = rows.length ? rows[0].v : 1;
  $('leaders').innerHTML = rows.map((r, i) => `
    <li class="leader-row" data-id="${r.id}">
      <span class="leader-rank">${i + 1}</span>
      <span class="leader-name">
        <span class="leader-stop">${titleCase(r.name)}</span>
        <span class="leader-routes">${r.routes.join(' · ')}</span>
      </span>
      <span class="leader-val">${fmt(r.v)}<small>board/hr</small></span>
      <span class="leader-bar"><i style="width:${(100 * r.v / max).toFixed(1)}%"></i></span>
    </li>`).join('');
  $('leaders').querySelectorAll('.leader-row').forEach((el) => {
    el.addEventListener('click', () => {
      const r = leadersFor(daytype, hour).find((x) => x.id === el.dataset.id);
      if (!r) return;
      map.flyTo({ center: [r.lon, r.lat], zoom: Math.max(map.getZoom(), 14.5), speed: 1.6 });
      openPopup(r.id, [r.lon, r.lat]);
    });
  });
}

// ═══ curve dock ═══
function drawCurve() {
  const svg = $('curve');
  const W = 960, H = 74, PAD = 4;
  const vals = citywide[daytype];
  const max = Math.max(...vals, 1);
  const x = (h) => ((h + 0.5) / 24) * W;
  const y = (v) => H - PAD - (v / max) * (H - PAD * 2);
  let line = `M ${x(0)} ${y(vals[0])}`;
  for (let h = 1; h < 24; h++) line += ` L ${x(h)} ${y(vals[h])}`;
  const area = `${line} L ${x(23)} ${H} L ${x(0)} ${H} Z`;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = `
    <defs>
      <linearGradient id="curveGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="rgba(240,122,46,0.55)"/>
        <stop offset="1" stop-color="rgba(240,122,46,0.03)"/>
      </linearGradient>
    </defs>
    <path class="area" d="${area}"/>
    <path class="stroke" d="${line}"/>`;
  const ticks = $('hour-ticks');
  ticks.innerHTML = [[0, '12 AM'], [6, '6 AM'], [12, '12 PM'], [18, '6 PM'], [23, '11 PM']]
    .map(([h, t]) => `<span style="left:${(100 * (h + 0.5) / 24).toFixed(2)}%">${t}</span>`).join('');
  updatePlayhead();
}

function updatePlayhead() {
  const wrap = $('scrub-wrap');
  if (!wrap) return;
  $('playhead').style.left = `calc(${(100 * (hour + 0.5) / 24).toFixed(3)}% - 1px)`;
}

function bindScrubber() {
  const wrap = $('scrub-wrap');
  let dragging = false;
  const hourAt = (clientX) => {
    const r = wrap.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (clientX - r.left) / r.width));
    return Math.min(23, Math.floor(f * 24));
  };
  wrap.addEventListener('pointerdown', (e) => {
    dragging = true; wrap.setPointerCapture(e.pointerId);
    stopPlay(); setHour(hourAt(e.clientX));
  });
  wrap.addEventListener('pointermove', (e) => {
    if (dragging) setHour(hourAt(e.clientX));
  });
  wrap.addEventListener('pointerup', () => { dragging = false; });
}

// ═══ play ═══
function startPlay() {
  playing = true;
  document.querySelector('.icon-play').hidden = true;
  document.querySelector('.icon-pause').hidden = false;
  playTimer = setInterval(() => setHour(hour + 1), 1150);
}
function stopPlay() {
  if (!playing) return;
  playing = false;
  document.querySelector('.icon-play').hidden = false;
  document.querySelector('.icon-pause').hidden = true;
  clearInterval(playTimer);
}

// ═══ popup + tooltip ═══
function stopChartSvg(s) {
  const d = raw.days[daytype];
  const arr = (daytype === 'wd' ? s[5] : s[6]).map((v) => v / d);
  const max = Math.max(...arr, 1);
  const W = 238, H = 44, bw = W / 24;
  let bars = '';
  for (let h = 0; h < 24; h++) {
    const bh = Math.max(arr[h] > 0 ? 1.5 : 0, (arr[h] / max) * H);
    const cur = h === hour;
    bars += `<rect x="${(h * bw + 0.75).toFixed(1)}" y="${(H - bh).toFixed(1)}"
      width="${(bw - 1.5).toFixed(1)}" height="${bh.toFixed(1)}" rx="1.2"
      fill="${cur ? '#ffab5e' : 'rgba(255,255,255,0.16)'}">
      <title>${hourLabel(h).text} ${hourLabel(h).ap}: ${fmt(arr[h])} board</title></rect>`;
  }
  const lab = (h, t) => `<text class="axis" x="${(h + 0.5) * bw}" y="${H + 9}" text-anchor="middle">${t}</text>`;
  return `<svg viewBox="0 0 ${W} ${H + 11}">${bars}${lab(0, '12A')}${lab(6, '6A')}${lab(12, '12P')}${lab(18, '6P')}${lab(23, '11P')}</svg>`;
}

function openPopup(id, lngLat) {
  const s = raw.index.get(id);
  if (!s) return;
  const dLabel = daytype === 'wd' ? 'weekday' : 'weekend day';
  const perDayB = s[7] / 30, perDayA = s[8] / 30;
  const html = `
    <div class="pop-name">${titleCase(s[1])}</div>
    <div class="pop-routes">${s[4].map((r) => `<span class="pop-route">${r}</span>`).join('')}</div>
    <div class="pop-stats">≈<strong>${fmt(perDayB)}</strong> board · ≈<strong>${fmt(perDayA)}</strong> get off per day, June 2026 average</div>
    <div class="pop-chart">${stopChartSvg(s)}</div>
    <div class="pop-cap">Boardings by hour, average ${dLabel} · orange = hour shown on map</div>`;
  if (popup) popup.remove();
  popupStop = { id, lngLat };
  popup = new maplibregl.Popup({ offset: 10, maxWidth: '300px' })
    .setLngLat(lngLat).setHTML(html).addTo(map);
  popup.on('close', () => { popupStop = null; });
}

function bindMapInteractions() {
  const tip = $('tip');
  map.on('mousemove', 'boardings', (e) => {
    const f = e.features[0];
    if (!f) return;
    map.getCanvas().style.cursor = 'pointer';
    const v = f.properties['h' + hour];
    const lab = hourLabel(hour);
    tip.innerHTML = `<span class="t-name">${titleCase(f.properties.name)}</span><br>
      <span class="t-val">${fmt(Number(v))}</span> board ${lab.text} ${lab.ap}
      <div class="t-sub">avg ${daytype === 'wd' ? 'weekday' : 'weekend day'} · click for detail</div>`;
    tip.hidden = false;
    tip.style.left = Math.min(window.innerWidth - 260, e.originalEvent.clientX + 14) + 'px';
    tip.style.top = (e.originalEvent.clientY + 12) + 'px';
  });
  map.on('mouseleave', 'boardings', () => {
    map.getCanvas().style.cursor = '';
    $('tip').hidden = true;
  });
  map.on('click', 'boardings', (e) => {
    const f = e.features[0];
    if (f) openPopup(f.properties.id, f.geometry.coordinates);
  });
}

// ═══ boot ═══
async function boot() {
  const params = new URLSearchParams(window.location.search);
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }));
  hour = params.has('h') ? Math.min(23, Math.max(0, +params.get('h') || 0)) : now.getHours();
  daytype = params.get('d') === 'we' ? 'we'
    : params.get('d') === 'wd' ? 'wd'
    : (now.getDay() === 0 || now.getDay() === 6) ? 'we' : 'wd';
  document.querySelectorAll('.dt-btn').forEach((b) => {
    const on = b.dataset.dt === daytype;
    b.classList.toggle('active', on); b.setAttribute('aria-selected', on);
  });

  const dataPromise = loadData();

  map = new maplibregl.Map({
    container: 'map',
    style: TILE_STYLE,
    bounds: [[-74.18, 40.55], [-73.73, 40.90]],
    fitBoundsOptions: {
      padding: window.innerWidth > 1000
        ? { top: 28, left: 368, right: 36, bottom: 148 }
        : { top: 10, left: 10, right: 10, bottom: 120 },
    },
    minZoom: 8.5,
    maxZoom: 17,
    attributionControl: true,
  });
  map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

  // MapLibre's 'load' waits on initial TILES, which can hang; 'style.load'
  // fires as soon as the style itself is ready for addSource/addLayer. Init on
  // whichever comes first, with a retrying poll as backstop (addSource throws
  // if the style genuinely isn't ready yet — the catch resets and retries).
  let inited = false;
  const initLayers = async () => {
    if (inited) return;
    inited = true;
    await dataPromise;

    map.addSource('stops', { type: 'geojson', data: fc[daytype] });
    // ghost layer: every stop, barely there, so quiet hours still show the network
    map.addLayer({
      id: 'stops-ghost', type: 'circle', source: 'stops',
      paint: { 'circle-radius': 0.8, 'circle-color': 'rgba(255,255,255,0.14)' },
    });
    const p = paintFor(hour, hour, 0);
    map.addLayer({
      id: 'boardings', type: 'circle', source: 'stops',
      paint: {
        'circle-radius': p.radius,
        'circle-color': p.color,
        'circle-opacity': 0.85,
        'circle-blur': 0.25,
      },
    });

    $('leader-daytype').textContent = daytype === 'wd' ? 'weekday avg' : 'weekend avg';
    drawCurve(); updateClock(); updateLeaders();
    bindMapInteractions();
    $('loading-overlay').classList.add('hidden');
  };
  const tryInit = () => initLayers().catch(() => { inited = false; });
  map.on('style.load', tryInit);
  map.on('load', tryInit);
  const readyPoll = setInterval(() => {
    if (inited) { clearInterval(readyPoll); return; }
    tryInit();
  }, 600);

  bindScrubber();
  $('play-btn').addEventListener('click', () => (playing ? stopPlay() : startPlay()));
  document.querySelectorAll('.dt-btn').forEach((b) =>
    b.addEventListener('click', () => setDaytype(b.dataset.dt)));
  $('ai-caution-btn').addEventListener('click', () => {
    $('ai-caution-pop').hidden = !$('ai-caution-pop').hidden;
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#ai-caution-btn') && !e.target.closest('#ai-caution-pop')) {
      $('ai-caution-pop').hidden = true;
    }
  });
}

boot();
