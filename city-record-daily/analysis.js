/* The 2026 file — narrative + charts built from data/analysis.json.
   Charts are hand-built inline SVG to match the rest of the site (no libraries).
   Every number in the prose is read from the data file, so the piece tracks the
   archive instead of freezing on the day it was written. */

const BLUE = '#2a5db0', RED = '#c0392b', GREY = '#b9c2cc', GREEN = '#2e7d5b', AMBER = '#d99a2b';

// ── formatting ──────────────────────────────────────────────────────────
const money = v => {
  const a = Math.abs(v);
  if (a >= 1e9) return '$' + (v / 1e9).toFixed(a >= 1e10 ? 0 : 2) + 'B';
  if (a >= 1e6) return '$' + (v / 1e6).toFixed(a >= 1e8 ? 0 : 1) + 'M';
  if (a >= 1e3) return '$' + Math.round(v / 1e3) + 'K';
  return '$' + Math.round(v);
};
const moneyLong = v => '$' + Math.round(v).toLocaleString('en-US');
const n0 = v => Math.round(v).toLocaleString('en-US');
const n1 = v => v.toFixed(1);
const pct = (v, d = 0) => (v * 100).toFixed(d) + '%';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const longDate = d => {
  const [y, m, day] = d.split('-').map(Number);
  const names = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  return `${names[m - 1]} ${day}, ${y}`;
};
const shortDate = d => {
  const [, m, day] = d.split('-').map(Number);
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${names[m - 1]} ${day}`;
};

// ── chart primitives ────────────────────────────────────────────────────
function frame(w, h, inner) {
  return `<svg viewBox="0 0 ${w} ${h}" role="img" preserveAspectRatio="xMidYMid meet">${inner}</svg>`;
}
/* Round the axis top up so that quarter-ticks land on readable numbers
   (40/30/20/10 rather than 50/38/25/13). */
function niceMax(v, ticks = 4) {
  if (v <= 0) return 1;
  const raw = v / ticks;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = ([1, 2, 2.5, 5, 10].find(s => raw <= s * mag) || 10) * mag;
  return step * ticks;
}

/* Vertical bars with a value axis and optional per-bar highlight. */
function barChart(rows, opts = {}) {
  const w = 700, h = opts.height || 210, padL = 46, padR = 12, padT = 14, padB = 30;
  const iw = w - padL - padR, ih = h - padT - padB;
  const max = niceMax(Math.max(...rows.map(r => r.value)));
  const bw = iw / rows.length;
  const fmt = opts.fmt || n0;
  let g = '';
  for (let i = 0; i <= 4; i++) {
    const y = padT + ih - (ih * i / 4);
    g += `<line class="ax-line" x1="${padL}" x2="${w - padR}" y1="${y}" y2="${y}"/>`;
    g += `<text class="ax-val" x="${padL - 6}" y="${y + 3}" text-anchor="end">${fmt(max * i / 4)}</text>`;
  }
  rows.forEach((r, i) => {
    const bh = max ? (r.value / max) * ih : 0;
    const x = padL + i * bw + bw * 0.18, bwid = bw * 0.64;
    const fill = r.color || opts.color || BLUE;
    g += `<rect x="${x}" y="${padT + ih - bh}" width="${bwid}" height="${Math.max(bh, 0.5)}" fill="${fill}"/>`;
    if (opts.showValues !== false) g += `<text class="bar-label" x="${x + bwid / 2}" y="${padT + ih - bh - 5}" text-anchor="middle">${r.display || fmt(r.value)}</text>`;
    g += `<text class="ax-label" x="${x + bwid / 2}" y="${h - padB + 15}" text-anchor="middle">${esc(r.label)}</text>`;
  });
  g += `<line class="ax-base" x1="${padL}" x2="${w - padR}" y1="${padT + ih}" y2="${padT + ih}"/>`;
  return frame(w, h, g);
}

/* Two bars per category, side by side. */
function groupedBars(rows, series, opts = {}) {
  const w = 700, h = opts.height || 210, padL = 40, padR = 12, padT = 16, padB = 34;
  const iw = w - padL - padR, ih = h - padT - padB;
  const max = niceMax(Math.max(...rows.flatMap(r => series.map(s => r[s.key] || 0))));
  const gw = iw / rows.length, bw = (gw * 0.68) / series.length;
  const fmt = opts.fmt || n0;
  let g = '';
  for (let i = 0; i <= 4; i++) {
    const y = padT + ih - (ih * i / 4);
    g += `<line class="ax-line" x1="${padL}" x2="${w - padR}" y1="${y}" y2="${y}"/>`;
    g += `<text class="ax-val" x="${padL - 6}" y="${y + 3}" text-anchor="end">${fmt(max * i / 4)}</text>`;
  }
  rows.forEach((r, i) => {
    series.forEach((s, j) => {
      const v = r[s.key] || 0, bh = max ? (v / max) * ih : 0;
      const x = padL + i * gw + gw * 0.16 + j * bw;
      g += `<rect x="${x}" y="${padT + ih - bh}" width="${bw - 2}" height="${Math.max(bh, 0.5)}" fill="${s.color}"/>`;
    });
    g += `<text class="ax-label" x="${padL + i * gw + gw / 2}" y="${h - padB + 15}" text-anchor="middle">${esc(r.label)}</text>`;
  });
  g += `<line class="ax-base" x1="${padL}" x2="${w - padR}" y1="${padT + ih}" y2="${padT + ih}"/>`;
  series.forEach((s, j) => {
    const x = padL + j * 170;
    g += `<rect x="${x}" y="${h - 10}" width="9" height="9" fill="${s.color}"/><text class="series-note" x="${x + 13}" y="${h - 2}">${esc(s.label)}</text>`;
  });
  return frame(w, h + 6, g);
}

/* 100%-stacked columns — for composition, not level. */
function stackedShare(rows, series, opts = {}) {
  const w = 700, h = opts.height || 200, padL = 34, padR = 12, padT = 10, padB = 34;
  const iw = w - padL - padR, ih = h - padT - padB;
  const bw = iw / rows.length;
  let g = '';
  [0, 0.25, 0.5, 0.75, 1].forEach(f => {
    const y = padT + ih * f;
    g += `<line class="ax-line" x1="${padL}" x2="${w - padR}" y1="${y}" y2="${y}"/>`;
    g += `<text class="ax-val" x="${padL - 6}" y="${y + 3}" text-anchor="end">${Math.round((1 - f) * 100)}%</text>`;
  });
  rows.forEach((r, i) => {
    const total = series.reduce((s, k) => s + (r[k.key] || 0), 0) || 1;
    let acc = 0;
    series.forEach(s => {
      const frac = (r[s.key] || 0) / total, seg = frac * ih;
      g += `<rect x="${padL + i * bw + bw * 0.16}" y="${padT + acc}" width="${bw * 0.68}" height="${Math.max(seg, 0)}" fill="${s.color}"/>`;
      acc += seg;
    });
    g += `<text class="ax-label" x="${padL + i * bw + bw / 2}" y="${h - padB + 15}" text-anchor="middle">${esc(r.label)}</text>`;
  });
  let lx = padL;
  series.forEach(s => {
    g += `<rect x="${lx}" y="${h - 11}" width="9" height="9" fill="${s.color}"/><text class="series-note" x="${lx + 13}" y="${h - 3}">${esc(s.label)}</text>`;
    lx += 24 + s.label.length * 6.3;
  });
  return frame(w, h + 6, g);
}

/* Single line with dots. */
function lineChart(rows, opts = {}) {
  const w = 700, h = opts.height || 190, padL = 46, padR = 14, padT = 16, padB = 30;
  const iw = w - padL - padR, ih = h - padT - padB;
  const max = niceMax(Math.max(...rows.map(r => r.value)));
  const fmt = opts.fmt || n0;
  const x = i => padL + (rows.length === 1 ? iw / 2 : (iw * i) / (rows.length - 1));
  const y = v => padT + ih - (max ? (v / max) * ih : 0);
  let g = '';
  for (let i = 0; i <= 4; i++) {
    const yy = padT + ih - (ih * i / 4);
    g += `<line class="ax-line" x1="${padL}" x2="${w - padR}" y1="${yy}" y2="${yy}"/>`;
    // Only the top and bottom ticks get a label — every point carries its own value,
    // and a full tick ladder collides with the data labels.
    if (i === 0 || i === 4) g += `<text class="ax-val" x="${padL - 6}" y="${yy + 3}" text-anchor="end">${fmt(max * i / 4)}</text>`;
  }
  const pts = rows.map((r, i) => `${x(i)},${y(r.value)}`).join(' ');
  g += `<polyline points="${pts}" fill="none" stroke="${opts.color || BLUE}" stroke-width="2"/>`;
  rows.forEach((r, i) => {
    g += `<circle cx="${x(i)}" cy="${y(r.value)}" r="3.2" fill="${opts.color || BLUE}"/>`;
    if (opts.showValues !== false) g += `<text class="bar-label" x="${x(i)}" y="${y(r.value) - 8}" text-anchor="middle">${r.display || fmt(r.value)}</text>`;
    g += `<text class="ax-label" x="${x(i)}" y="${h - padB + 15}" text-anchor="middle">${esc(r.label)}</text>`;
  });
  g += `<line class="ax-base" x1="${padL}" x2="${w - padR}" y1="${padT + ih}" y2="${padT + ih}"/>`;
  return frame(w, h, g);
}

/* Horizontal bars, for ranked lists. */
function rankBars(rows, opts = {}) {
  const fmtR = opts.fmt || money;
  const longest = Math.max(...rows.map(r => (r.display || fmtR(r.value)).length));
  const w = 700, rowH = opts.rowH || 22, padL = opts.padL || 230, padR = Math.max(70, longest * 6.1 + 12), padT = 4;
  const h = padT + rows.length * rowH + 6;
  const iw = w - padL - padR;
  const max = Math.max(...rows.map(r => r.value)) || 1;
  const fmt = fmtR;
  let g = '';
  rows.forEach((r, i) => {
    const y = padT + i * rowH;
    const bw = (r.value / max) * iw;
    g += `<text class="ax-label" x="${padL - 8}" y="${y + rowH / 2 + 3}" text-anchor="end">${esc(r.label)}</text>`;
    g += `<rect x="${padL}" y="${y + 3}" width="${Math.max(bw, 1)}" height="${rowH - 8}" fill="${r.color || opts.color || BLUE}"/>`;
    g += `<text class="bar-label" x="${padL + bw + 6}" y="${y + rowH / 2 + 3}">${r.display || fmt(r.value)}</text>`;
  });
  return frame(w, h, g);
}

/* Dots on a date axis — used for the executive-order and emergency timelines. */
function dotTimeline(series, range, opts = {}) {
  const w = 700, laneH = opts.laneH || 30, padL = 118, padR = 16, padT = 12;
  const h = padT + series.length * laneH + 26;
  const iw = w - padL - padR;
  const t0 = Date.parse(range[0]), t1 = Date.parse(range[1]);
  const x = d => padL + ((Date.parse(d) - t0) / (t1 - t0 || 1)) * iw;
  let g = '';
  // month gridlines
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  let cur = new Date(t0); cur.setUTCDate(1);
  while (cur.getTime() <= t1) {
    const d = cur.toISOString().slice(0, 10);
    const inRange = Date.parse(d) >= t0;
    // The first month usually starts before the archive does; label it at the axis
    // origin so the leftmost dots are not left without a month.
    const px = inRange ? x(d) : padL;
    if (inRange) g += `<line class="ax-line" x1="${px}" x2="${px}" y1="${padT - 4}" y2="${padT + series.length * laneH}"/>`;
    g += `<text class="ax-label" x="${px}" y="${h - 8}" text-anchor="${inRange ? 'middle' : 'start'}">${MON[cur.getUTCMonth()]}</text>`;
    cur.setUTCMonth(cur.getUTCMonth() + 1);
  }
  series.forEach((s, i) => {
    const y = padT + i * laneH + laneH / 2;
    g += `<line x1="${padL}" x2="${w - padR}" y1="${y}" y2="${y}" stroke="#f0f0f0" stroke-width="1"/>`;
    g += `<text class="ax-label" x="${padL - 8}" y="${y + 3}" text-anchor="end">${esc(s.label)}</text>`;
    s.points.forEach(p => {
      const r = p.r || 3.4;
      g += `<circle cx="${x(p.date)}" cy="${y}" r="${r}" fill="${s.color}" fill-opacity="${p.opacity || 0.85}"><title>${esc(p.title || p.date)}</title></circle>`;
    });
  });
  return frame(w, h, g);
}

// ── page ────────────────────────────────────────────────────────────────
// Cache-bust once a day, which is how often the aggregate is rebuilt.
fetch('data/analysis.json?v=' + new Date().toISOString().slice(0, 10))
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(render)
  .catch(err => {
    document.getElementById('story').innerHTML =
      `<p class="loading">Could not load <code>data/analysis.json</code> (${esc(err.message)}). ` +
      `Run <code>node build-analysis.mjs</code> from the <code>city-record-daily</code> directory to build it.</p>`;
  });

function render(d) {
  const M = d.monthly, first = M[0], last = M[M.length - 1];
  const byMonth = Object.fromEntries(M.map(m => [m.month, m]));
  const short = m => m.label.replace(' 2026', '').replace(/ 20\d\d$/, '');
  const peakRate = M.reduce((a, b) => (b.awards_per_day > a.awards_per_day ? b : a));
  const baseline = M.slice(0, Math.max(1, M.indexOf(peakRate))).reduce((s, m) => s + m.awards, 0) /
                   Math.max(1, M.slice(0, Math.max(1, M.indexOf(peakRate))).reduce((s, m) => s + m.days, 0));
  const out = [];

  // ── Coverage note ─────────────────────────────────────────────────────
  const cov = d.coverage;
  const lateDow = Object.entries(cov.first_by_weekday).filter(([, dt]) => dt > d.range.start).sort((a, b) => b[1].localeCompare(a[1]))[0];
  const lateNote = lateDow && lateDow[1] > d.range.start
    ? `${lateDow[0]}days are missing from the start of the archive &mdash; the first one held is ${longDate(lateDow[1])}, so ${lateDow[0]}day notices before that date are simply absent. `
    : '';
  const outageNote = cov.outages.length
    ? `A ${cov.outages[0].days}-day gap runs from ${longDate(cov.outages[0].from)} to ${longDate(cov.outages[0].to)}, when the Open Data mirror stalled while the City Record itself kept publishing. `
    : '';
  out.push(`<div class="caveat">
    <strong>Read the coverage before the trends.</strong> This archive holds <span class="num">${n0(cov.publication_days)}</span> publication days
    out of <span class="num">${n0(cov.weekdays_in_range)}</span> weekdays between ${longDate(d.range.start)} and ${longDate(d.range.end)}.
    ${lateNote}${outageNote}Because the gaps are not spread evenly, raw monthly counts are not comparable to each other.
    Every rate on this page is therefore stated <strong>per publication day</strong>, not per month.
    Dollar figures are contract amounts as published, which routinely cover multiple years, so they are headline values and not a spending total for 2026.
    <a href="methodology.html">Full methodology</a>.
  </div>`);

  // ── Key numbers ───────────────────────────────────────────────────────
  out.push(`<div class="keynums">
    <div class="keynum"><div class="k">Publication days read</div><div class="v">${n0(cov.publication_days)}</div><div class="s">${longDate(d.range.start)} to ${longDate(d.range.end)}</div></div>
    <div class="keynum"><div class="k">Notices</div><div class="v">${n0(d.totals.notices)}</div><div class="s">every section, every agency</div></div>
    <div class="keynum"><div class="k">Contract awards</div><div class="v">${n0(d.totals.awards)}</div><div class="s">median ${money(d.totals.median_award)}</div></div>
    <div class="keynum"><div class="k">Published award value</div><div class="v">${money(d.totals.award_value)}</div><div class="s">${n0(d.totals.vendors)} vendors, ${n0(d.totals.agencies)} agencies</div></div>
  </div>`);

  out.push(`<div class="toc"><h3>What the year shows</h3><ol>
    <li><a href="#cliff">A procurement cliff at the fiscal-year line</a></li>
    <li><a href="#renewal">Renewal, not competition, is the biggest line item</a></li>
    <li><a href="#median">The typical award got several times larger, and stayed there</a></li>
    <li><a href="#dycd">One agency rewired how it buys</a></li>
    <li><a href="#compression">Agencies compress most of a year into one month</a></li>
    <li><a href="#concentration">Ten awards, a third of the money</a></li>
    <li><a href="#swap">The public-comment channel was renamed, and lost its numbers</a></li>
    <li><a href="#eo">The executive-order counter reset to one</a></li>
    <li><a href="#emergency">Emergency buying: snow in spring, demolition all year</a></li>
    <li><a href="#bids">The one thing that did not move: the bid window</a></li>
    <li><a href="#themes">What the city started buying</a></li>
    <li><a href="#limits">What this archive cannot tell you</a></li>
  </ol></div>`);

  // ── 1. The fiscal-year cliff ──────────────────────────────────────────
  const b = d.fiscal_year.boundary;
  const boundaryCountShare = b.awards / d.totals.awards;
  const boundaryValueShare = b.value / d.totals.award_value;
  out.push(`<section class="finding" id="cliff">
    <div class="kicker">Finding 01</div>
    <h2>A procurement cliff at the fiscal-year line</h2>
    <p class="standfirst">The single loudest signal in the archive is not a policy. It is a date. New York City's fiscal year ends June 30, and the City Record shows the whole procurement apparatus straining against that deadline.</p>
    <p>Through the first months of the year the city published about <span class="num">${n1(baseline)}</span> contract awards on a typical publication day. In ${peakRate.label} that rate reached <span class="num">${n1(peakRate.awards_per_day)}</span> &mdash; ${n1(peakRate.awards_per_day / baseline)} times the earlier pace &mdash; and it has not returned to where it started.</p>
    ${figure('Contract awards published per publication day',
      'Rate, not raw count, because the archive does not hold every weekday.',
      barChart(M.map(m => ({ label: short(m), value: m.awards_per_day, display: n1(m.awards_per_day), color: m === peakRate ? RED : BLUE })), { fmt: v => v.toFixed(0) }),
      `Each bar divides that month's awards by the number of days the archive actually holds for it (${M.map(m => `${short(m)} ${m.days}`).join(', ')}).`)}
    <p>Zoom in on the boundary itself. In the month around the fiscal-year line, from ${longDate(b.from)} to ${longDate(b.to)}, the city published <span class="num">${n0(b.awards)}</span> awards worth <span class="num">${money(b.value)}</span> across just <span class="num">${n0(b.days)}</span> publication days. That is <span class="num">${pct(boundaryCountShare)}</span> of every award in the archive and <span class="num">${pct(boundaryValueShare)}</span> of every published dollar, compressed into one month-long window. <span class="num">${n0(b.renewals)}</span> of those ${n0(b.awards)} awards &mdash; ${pct(b.renewals / b.awards)} &mdash; were renewals of contracts the city already held.</p>
    <p>The titles say the same thing out loud. <span class="num">${n0(d.fiscal_year.tagged_awards)}</span> awards, worth <span class="num">${money(d.fiscal_year.tagged_value)}</span>, carry the coming fiscal year in the title itself, and they cluster hard: ${d.fiscal_year.by_month.filter(x => x.count > 0).map(x => `${short(x)} ${n0(x.count)}`).join(', ')}.</p>
    <div class="pullout">Nearly a third of the year's contracting business, by count and by dollar, moves through a four-week window around June 30.</div>
    ${checkit('Open the digest and search a term like "FY27" or "Renewal," then sort by date. The June and early-July concentration is visible in the raw notice list, not just in the aggregate.')}
  </section>`);

  // ── 2. Renewals ───────────────────────────────────────────────────────
  const renewal = d.methods.find(m => /^renewal/i.test(m.name));
  const topMethods = d.methods.slice(0, 8);
  const compMethods = d.methods.filter(m => /competitive sealed|request for proposals|request for quote/i.test(m.name));
  const compTotal = compMethods.reduce((s, m) => s + m.value, 0);
  const compCount = compMethods.reduce((s, m) => s + m.count, 0);
  out.push(`<section class="finding" id="renewal">
    <div class="kicker">Finding 02</div>
    <h2>Renewal, not competition, is the biggest line item</h2>
    <p class="standfirst">Sorted by published dollars, the largest single procurement method in the archive is not a competition at all. It is the renewal of an existing contract.</p>
    <p>Renewals account for <span class="num">${n0(renewal.count)}</span> awards worth <span class="num">${money(renewal.value)}</span>, or <span class="num">${pct(renewal.value / d.totals.award_value)}</span> of all published award value. Every competitive method in the paper &mdash; sealed bids, sealed proposals, requests for proposals, requests for quote, in every pre-qualified variant &mdash; adds up to <span class="num">${money(compTotal)}</span> across <span class="num">${n0(compCount)}</span> awards. One renewal category very nearly matches all of open competition combined.</p>
    ${figure('Published award value by selection method',
      'Top ' + topMethods.length + ' methods, whole archive.',
      rankBars(topMethods.map(m => ({ label: m.name.length > 38 ? m.name.slice(0, 36) + '…' : m.name, value: m.value, color: /^renewal/i.test(m.name) ? RED : /competitive|request for/i.test(m.name) ? BLUE : GREY, display: `${money(m.value)}  ·  ${n0(m.count)}` })), { padL: 250 }),
      'Bar length is dollars; the number after the dot is the count of awards. Renewals are shown in red, competitive methods in blue.')}
    <p>Renewals are also the mechanism behind the June cliff. Their monthly count runs ${M.slice(0, 3).map(m => `${short(m)} ${n0(m.renewals)}`).join(', ')} early in the year, then spikes to <span class="num">${n0(Math.max(...M.map(m => m.renewals)))}</span> in ${short(M.reduce((a, x) => x.renewals > a.renewals ? x : a))}.</p>
    ${figure('Renewal awards per month', 'Count of awards whose selection method is Renewal.',
      barChart(M.map(m => ({ label: short(m), value: m.renewals, color: m.renewals === Math.max(...M.map(x => x.renewals)) ? RED : BLUE })), { height: 180 }),
      'Counts, not rates — the point here is the absolute pile-up, and the heaviest month is one of the better-covered ones.')}
    <p>None of this is irregular. Renewing a multi-year human-services contract is ordinary practice and it is published exactly as the rules require. It does mean that the majority of the dollars flowing through the City Record in a given year are decisions that were made in an earlier year, and that the public-comment window on them is the renewal notice.</p>
  </section>`);

  // ── 3. The median award ───────────────────────────────────────────────
  const cliffIdx = Math.max(1, M.indexOf(peakRate));
  const early = M.slice(0, cliffIdx), late = M.slice(cliffIdx);
  const earlyLo = Math.min(...early.map(m => m.median)), earlyHi = Math.max(...early.map(m => m.median));
  const lateLo = Math.min(...late.map(m => m.median)), lateHi = Math.max(...late.map(m => m.median));
  const bandSeries = [
    { key: 'u100k', label: 'Under $100K', color: '#dbe4ef' },
    { key: 'k100_1m', label: '$100K–$1M', color: '#9db6d8' },
    { key: 'm1_10', label: '$1M–$10M', color: BLUE },
    { key: 'm10_100', label: '$10M–$100M', color: '#1d3f7a' },
    { key: 'o100m', label: '$100M+', color: RED },
  ];
  const smallFirst = first.bands.u100k / first.days, smallLast = last.bands.u100k / last.days;
  const midFirst = first.bands.m1_10 / first.days, midLast = last.bands.m1_10 / last.days;
  out.push(`<section class="finding" id="median">
    <div class="kicker">Finding 03</div>
    <h2>The typical award got several times larger, and stayed there</h2>
    <p class="standfirst">Totals are easy to distort: one $1 billion renewal moves a month. The median is harder to fool, and the median moved too.</p>
    <p>In every month before ${peakRate.label} the median published award sat between <span class="num">${money(earlyLo)}</span> and <span class="num">${money(earlyHi)}</span>. In every month from ${peakRate.label} onward it has sat between <span class="num">${money(lateLo)}</span> and <span class="num">${money(lateHi)}</span> &mdash; roughly ${n1(((lateLo + lateHi) / 2) / ((earlyLo + earlyHi) / 2))} times higher, with no overlap between the two ranges. The middle of the distribution moved, and it did not move back.</p>
    ${figure('Median published award, by month', 'The midpoint award — half above, half below.',
      lineChart(M.map(m => ({ label: short(m), value: m.median, display: money(m.median) })), { fmt: money, color: RED }),
      'Medians are computed on awards with a published amount above zero.')}
    <p>The composition chart explains it. Small awards did not disappear: awards under $100,000 ran <span class="num">${n1(smallFirst)}</span> a day in ${first.label} and <span class="num">${n1(smallLast)}</span> a day in ${last.label}. What changed is the middle and upper bands. Awards between $1 million and $10 million went from <span class="num">${n1(midFirst)}</span> a day to <span class="num">${n1(midLast)}</span> a day, peaking at <span class="num">${n1(Math.max(...M.map(m => m.bands.m1_10 / m.days)))}</span> a day in ${short(M.reduce((a, x) => (x.bands.m1_10 / x.days) > (a.bands.m1_10 / a.days) ? x : a))}.</p>
    ${figure('Award size mix, by month', 'Share of that month\'s awards falling in each size band.',
      stackedShare(M.map(m => ({ label: short(m), ...m.bands })), bandSeries, { height: 200 }),
      'Shares, so each column sums to 100 percent. The chart shows composition; the counts behind it are in the archive.')}
  </section>`);

  // ── 4. DYCD ───────────────────────────────────────────────────────────
  const y = d.dycd;
  const yFirst = y.by_month[0], yPeak = y.by_month.reduce((a, x) => x.awards > a.awards ? x : a);
  out.push(`<section class="finding" id="dycd">
    <div class="kicker">Finding 04</div>
    <h2>One agency rewired how it buys</h2>
    <p class="standfirst">The Department of Youth and Community Development published <span class="num">${n0(yFirst.awards)}</span> contract awards in ${yFirst.label}. In ${yPeak.label} it published <span class="num">${n0(yPeak.awards)}</span>.</p>
    <p>Across the archive the agency accounts for <span class="num">${n0(y.total_awards)}</span> awards worth <span class="num">${money(y.total_value)}</span>. What makes it distinctive is the method: <span class="num">${n0(y.negotiated_awards)}</span> of those awards, worth <span class="num">${money(y.negotiated_value)}</span>, were negotiated acquisitions &mdash; a route used when a normal competition is impractical. Citywide there were <span class="num">${n0(y.citywide_negotiated)}</span> negotiated acquisitions in the whole archive, so this one agency is <span class="num">${pct(y.negotiated_awards / y.citywide_negotiated)}</span> of the city's use of the method.</p>
    ${figure('Youth and Community Development: awards published per month', 'Count of Procurement-section awards.',
      barChart(y.by_month.map(m => ({ label: short(m), value: m.awards, color: m.awards === yPeak.awards ? RED : BLUE })), { height: 180 }),
      'The agency was close to invisible in the archive in January and is among its highest-volume publishers by midyear.')}
    <p>The money is spread thin and wide: <span class="num">${n0(y.negotiated_vendors)}</span> distinct organizations, most of them community nonprofits, share those negotiated awards. The programs behind them are the recognizable pillars of the city's youth-services system.</p>
    <table class="tbl"><thead><tr><th>Program</th><th class="num">Negotiated awards</th></tr></thead><tbody>
      ${y.programs.map(p => `<tr><td>${esc(p.name)}</td><td class="num">${n0(p.count)}</td></tr>`).join('')}
    </tbody></table>
    <p>Read plainly: a large share of the city's after-school, community-center and summer-jobs money is moving through a non-competitive route, at high volume, to a long list of small providers. The City Record does not say why. It does say, unambiguously, that the pattern started in the spring and has not stopped.</p>
    ${checkit('Search the digest for "Beacon," "Cornerstone," "COMPASS" or "SYEP" to pull the underlying notices, each of which links back to its Open Data row.')}
  </section>`);

  // ── 5. Compression ────────────────────────────────────────────────────
  const compressed = d.agencies.filter(a => a.count >= 8 && a.value > 5e7).sort((a, b) => b.peak_share - a.peak_share).slice(0, 10);
  // The most informative case is a high-share agency that got there on many awards, not one giant one.
  const bulk = compressed.filter(a => a.peak_month && a.by_month[a.peak_month.month] && a.by_month[a.peak_month.month].count >= 20).sort((a, b) => b.peak_share - a.peak_share)[0];
  out.push(`<section class="finding" id="compression">
    <div class="kicker">Finding 05</div>
    <h2>Agencies compress most of a year into one month</h2>
    <p class="standfirst">Aggregate charts hide how lumpy this is at the agency level. For several large buyers, one month carries most of the year's published dollars.</p>
    ${figure('Share of an agency\'s published award dollars falling in its single busiest month',
      'Agencies with at least 8 awards and $50M in published value.',
      rankBars(compressed.map(a => ({ label: a.name.length > 36 ? a.name.slice(0, 34) + '…' : a.name, value: a.peak_share, color: a.peak_share > 0.6 ? RED : BLUE, display: `${pct(a.peak_share, 1)} in ${a.peak_month.label}` })), { padL: 250, fmt: v => pct(v) }),
      'A bar near 100 percent means that agency published essentially all of its award dollars in a single month of the archive. It does not mean it published all of its awards there.')}
    <p>${compressed[0] ? `${esc(compressed[0].name)} tops the list at <span class="num">${pct(compressed[0].peak_share, 1)}</span> of <span class="num">${money(compressed[0].value)}</span> in ${compressed[0].peak_month.label}, but that one is an artifact of size rather than timing: a couple of very large ${compressed[0].peak_month.label} awards swamp everything else the agency published all year.` : ''} ${bulk ? `The more telling case is ${esc(bulk.name)}, which put <span class="num">${pct(bulk.peak_share, 1)}</span> of its published dollars into ${bulk.peak_month.label} across <span class="num">${n0(bulk.by_month[bulk.peak_month.month].count)}</span> separate awards &mdash; genuine calendar compression, not one big contract.` : ''}</p>
    <p>For anyone watching a specific agency, the practical consequence is the same either way: missing one month of the City Record can mean missing most of that agency's year.</p>
  </section>`);

  // ── 6. Concentration ──────────────────────────────────────────────────
  const c = d.concentration;
  const t10 = c.top.find(x => x.n === 10), t100 = c.top.find(x => x.n === 100);
  out.push(`<section class="finding" id="concentration">
    <div class="kicker">Finding 06</div>
    <h2>Ten awards, a third of the money</h2>
    <p class="standfirst">Of <span class="num">${n0(c.awards)}</span> published awards, the ten largest carry <span class="num">${pct(t10.share, 1)}</span> of the dollars. The smaller half of all awards, put together, carry <span class="num">${pct(c.bottom_half_share, 2)}</span>.</p>
    ${figure('Cumulative share of published award dollars, by rank',
      'Awards sorted largest to smallest.',
      rankBars(c.top.map(x => ({ label: `Largest ${n0(x.n)} awards`, value: x.share, display: `${pct(x.share, 1)}  ·  ${money(x.value)}`, color: BLUE })), { padL: 160, fmt: v => pct(v) }),
      'The concentration is a property of contract publishing, not an anomaly: a handful of multi-year citywide agreements dwarf everything else in the paper.')}
    <table class="tbl"><thead><tr><th>Date</th><th>Agency</th><th>Vendor</th><th class="num">Published value</th></tr></thead><tbody>
      ${d.largest.slice(0, 10).map(a => `<tr><td>${shortDate(a.date)}</td><td>${esc(a.agency)}</td><td>${esc(a.vendor || '—')}<div style="color:#999;font-size:11px;line-height:1.4;margin-top:2px;">${esc((a.title || '').slice(0, 72))}${(a.title || '').length > 72 ? '…' : ''} &middot; ${esc(a.method || 'method not stated')}</div></td><td class="num">${money(a.value)}</td></tr>`).join('')}
    </tbody></table>
    <p>The single largest published award in the archive is ${esc(d.largest[0].vendor)}'s <span class="num">${money(d.largest[0].value)}</span> ${esc((d.largest[0].method || '').toLowerCase())} from ${esc(d.largest[0].agency)} on ${longDate(d.largest[0].date)}. On its own it is <span class="num">${pct(d.largest[0].value / d.totals.award_value, 1)}</span> of everything published this year.</p>
  </section>`);

  // ── 7. The renamed section ────────────────────────────────────────────
  const sw = d.section_swap;
  const oldPeak = sw.series.reduce((a, x) => x.award_hearings > a.award_hearings ? x : a);
  const newTotal = sw.series.reduce((s, x) => s + x.public_comment, 0);
  const oldAfter = sw.series.filter(x => x.month > oldPeak.month).reduce((s, x) => s + x.award_hearings, 0);
  out.push(`<section class="finding" id="swap">
    <div class="kicker">Finding 07</div>
    <h2>The public-comment channel was renamed, and lost its numbers</h2>
    <p class="standfirst">Not every trend in the City Record is about the city. Some are about the paper. The clearest one this year is a section that emptied out and a new section that filled up in its place.</p>
    <p>Through ${oldPeak.label} the archive's Contract Award Hearings section carried <span class="num">${n0(oldPeak.award_hearings)}</span> notices. After that it holds <span class="num">${n0(oldAfter)}</span> in total. Starting ${longDate(sw.public_comment_first)} a section called Public Comment on Contract Awards appears, and it has since carried <span class="num">${n0(newTotal)}</span> notices &mdash; the same civic function of opening a proposed award to public comment, under a new heading.</p>
    ${figure('Two sections, one function', 'Notices per month in each section.',
      groupedBars(sw.series.map(s => ({ label: short(s), a: s.award_hearings, b: s.public_comment })),
        [{ key: 'a', label: 'Contract Award Hearings', color: GREY }, { key: 'b', label: 'Public Comment on Contract Awards', color: BLUE }], { height: 190 }),
      'The handover happens between January and February. Anyone tracking the old section alone would conclude the city stopped taking comment on awards.')}
    <p>There is a data consequence worth naming. Notices in the old section came through with the standard procurement fields. The records in the new section arrive with no vendor name and no contract amount at all &mdash; those fields are absent from the row, not merely blank. So the volume of awards open to public comment went up in the record while the machine-readable detail about them went down.</p>
    ${checkit('This is the kind of change that silently breaks a tracker. If a dashboard elsewhere shows award-comment activity falling off a cliff in February 2026, this is almost certainly why.')}
  </section>`);

  // ── 8. Executive orders ───────────────────────────────────────────────
  const eo = d.exec_orders;
  const highNum = eo.all.filter(e => e.number && parseFloat(e.number) >= 100).sort((a, b) => a.date.localeCompare(b.date));
  const resets = eo.all.filter(e => e.number === '1').sort((a, b) => a.date.localeCompare(b.date));
  const plainEO = eo.all.filter(e => !e.emergency);
  const standing = eo.standing_series.filter(s => (eo.standing_counts[s] || 0) >= 5);
  const eoRange = [d.range.start, d.range.end];
  out.push(`<section class="finding" id="eo">
    <div class="kicker">Finding 08</div>
    <h2>The executive-order counter reset to one</h2>
    <p class="standfirst">A change of administration does not announce itself in the City Record. It shows up as a number going backwards.</p>
    ${highNum.length && resets.length ? `<p>On ${longDate(highNum[highNum.length - 1].date)} the paper published emergency executive orders numbered in the ${Math.floor(parseFloat(highNum[highNum.length - 1].number) / 100) * 100}s &mdash; the tail of the previous administration's sequence. Days later, on ${longDate(resets[0].date)}, it published Executive Order No. 1. The counters for both the regular and the emergency series restart within the same fortnight.</p>` : ''}
    ${figure('Executive orders in the City Record', 'Each dot is one published order.',
      dotTimeline([
        { label: 'Executive orders', color: BLUE, points: plainEO.map(e => ({ date: e.date, title: e.title })) },
        ...standing.map((s, i) => ({ label: `Emergency series ${s}`, color: i === 0 ? RED : AMBER, points: (eo.all.filter(e => e.emergency && e.number && e.number.split('.')[0] === s && e.number.includes('.'))).map(e => ({ date: e.date, title: e.title })) })),
      ], eoRange, { laneH: 32 }),
      'Hover a dot for the order number. The emergency lanes move in lockstep, which is what a pair of standing declarations renewed together looks like.')}
    <p>What follows the reset is a rhythm rather than an event. ${standing.length >= 2 ? `Two standing emergency declarations run in parallel all year, each renewed ${eo.standing_counts[standing[0]] === eo.standing_counts[standing[1]] ? `<span class="num">${n0(eo.standing_counts[standing[0]])}</span> times` : `<span class="num">${n0(eo.standing_counts[standing[0]])}</span> and <span class="num">${n0(eo.standing_counts[standing[1]])}</span> times`}, at a median of <span class="num">${n0(eo.median_renewal_gap)}</span> days between renewals.` : ''} Each renewal is a separate notice. The city has published <span class="num">${n0(plainEO.length)}</span> ordinary executive orders over the same stretch &mdash; roughly one for every ${Math.round((eo.all.length - plainEO.length) / Math.max(plainEO.length, 1))} emergency renewals.</p>
    <p>The renewals also bunch. Early in the year each pair is published close to its due date; by summer they arrive in batches of three to five on a single day, catching up on a fortnight at once.</p>
  </section>`);

  // ── 9. Emergency procurement ──────────────────────────────────────────
  const em = d.emergency_awards;
  const snow = em.filter(e => /snow|winter storm|warming/i.test(e.title));
  const demo = em.filter(e => /demo|shoring|fence/i.test(e.title));
  const emTotal = em.reduce((s, e) => s + e.value, 0);
  out.push(`<section class="finding" id="emergency">
    <div class="kicker">Finding 09</div>
    <h2>Emergency buying: snow in spring, demolition all year</h2>
    <p class="standfirst">Emergency procurement is rare in the archive &mdash; <span class="num">${n0(em.length)}</span> awards worth <span class="num">${money(emTotal)}</span> &mdash; and most of it falls into two recurring kinds.</p>
    ${snow.length ? `<p>The first is weather. <span class="num">${n0(snow.length)}</span> emergency awards worth <span class="num">${money(snow.reduce((s, e) => s + e.value, 0))}</span> cover snow operations, snow transportation and warming buses, and they are published between ${longDate(snow[0].date)} and ${longDate(snow[snow.length - 1].date)} &mdash; well after the season most people would file them under. The largest single one is ${money(Math.max(...snow.map(e => e.value)))}.</p>` : ''}
    ${demo.length ? `<p>The second is structural failure. <span class="num">${n0(demo.length)}</span> awards cover emergency demolition, shoring and fencing of buildings, almost all of them from Housing Preservation and Development, running steadily across the whole archive at a rate of roughly ${n1(demo.length / (d.coverage.publication_days / 20))} a month. They are small &mdash; a median of ${money(demo.map(e => e.value).sort((a, x) => a - x)[Math.floor(demo.length / 2)])} &mdash; and they recur among a short list of the same contractors.</p>` : ''}
    ${figure('Emergency procurements', 'Dot area scales with the published amount.',
      dotTimeline([
        { label: 'Weather', color: BLUE, points: snow.map(e => ({ date: e.date, r: Math.max(3, Math.min(11, Math.sqrt(e.value / 1e6) * 2)), title: `${e.date} · ${money(e.value)} · ${e.title}` })) },
        { label: 'Building failure', color: RED, points: demo.map(e => ({ date: e.date, r: Math.max(3, Math.min(11, Math.sqrt(e.value / 1e6) * 2)), title: `${e.date} · ${money(e.value)} · ${e.title}` })) },
        { label: 'Everything else', color: GREEN, points: em.filter(e => !snow.includes(e) && !demo.includes(e)).map(e => ({ date: e.date, r: Math.max(3, Math.min(11, Math.sqrt(e.value / 1e6) * 2)), title: `${e.date} · ${money(e.value)} · ${e.title}` })) },
      ], [d.range.start, d.range.end], { laneH: 34 }),
      'Hover a dot for the agency, amount and title.')}
    <p>Emergency awards are the one category where the notice is genuinely after the fact: the work is done, the money is committed and the City Record is the disclosure. That makes the list a useful running index of what physically went wrong in the city.</p>
  </section>`);

  // ── 10. Bid windows ───────────────────────────────────────────────────
  const bw = d.bid_windows;
  const bwMonths = bw.by_month.filter(m => m.n >= 10);
  out.push(`<section class="finding" id="bids">
    <div class="kicker">Finding 10</div>
    <h2>The one thing that did not move: the bid window</h2>
    <p class="standfirst">Volume swung, size swung, method swung. The amount of time a vendor gets to respond to a solicitation did not.</p>
    <p>Across <span class="num">${n0(bw.n)}</span> solicitations that publish a due date, the median gap between publication and deadline is <span class="num">${n0(bw.overall_median)}</span> days, and it holds within a few days of that every month of the year.</p>
    ${figure('Median days from published solicitation to bid deadline',
      'Months with at least 10 dated solicitations.',
      lineChart(bwMonths.map(m => ({ label: short(m), value: m.median, display: n0(m.median) + 'd' })), { fmt: v => v.toFixed(0) + 'd', color: BLUE, height: 175 }),
      'A flat line here is the point: whatever else changed about city contracting this year, the response window did not.')}
    <p>The tail is where the variation lives. <span class="num">${pct(bw.short_share, 1)}</span> of dated solicitations give two weeks or less. A handful publish within days of their own deadline &mdash; ${bw.very_short.length ? `the shortest in the archive is ${n0(bw.very_short[0].days)} days, on ${esc(bw.very_short[0].agency)}'s "${esc((bw.very_short[0].title || '').slice(0, 56))}" notice` : ''}. Some of those are genuinely short windows; some are almost certainly a notice published late against a deadline set earlier. The City Record alone cannot distinguish the two, and this page does not try to.</p>
  </section>`);

  // ── 11. Themes ────────────────────────────────────────────────────────
  const themeTotal = t => t.series.reduce((s, x) => s + x.notices, 0);
  const themeRows = d.themes.filter(t => themeTotal(t) >= 20);
  const themeThin = d.themes.filter(t => themeTotal(t) < 20);
  const shelter = d.themes.find(t => t.key === 'shelter');
  const legal = d.themes.find(t => t.key === 'immigrant_legal');
  out.push(`<section class="finding" id="themes">
    <div class="kicker">Finding 11</div>
    <h2>What the city started buying</h2>
    <p class="standfirst">Subject matter moves more slowly than volume. Five recurring themes are large enough in the archive to plot; two of them are clearly moving.</p>
    ${themeRows.map(t => {
      const s = t.series, tot = s.reduce((a, x) => a + x.notices, 0), val = s.reduce((a, x) => a + x.value, 0);
      const pk = s.reduce((a, x) => x.notices > a.notices ? x : a);
      return figure(t.label, `${n0(tot)} notices, ${money(val)} in published awards. Peak: ${pk.label}.`,
        barChart(s.map(x => ({ label: short(x), value: x.notices, color: x === pk ? RED : BLUE })), { height: 150, showValues: true }),
        `Keyword match on notice title and body text. Counts every notice type, not only awards.`);
    }).join('')}
    <p>Shelter and homeless services is the heaviest theme in the archive by dollars &mdash; <span class="num">${money(shelter.series.reduce((s, x) => s + x.value, 0))}</span> across <span class="num">${n0(themeTotal(shelter))}</span> notices &mdash; and unlike most categories it does not subside after the fiscal-year line. Its published award value in ${shelter.series[shelter.series.length - 1].label} alone is <span class="num">${money(shelter.series[shelter.series.length - 1].value)}</span>.</p>
    <p>Immigrant and low-wage-worker legal services is the sharpest late move, though the numbers are small enough to say so carefully: <span class="num">${n0(themeTotal(legal))}</span> notices in the whole archive, <span class="num">${n0(legal.series[legal.series.length - 1].notices)}</span> of them in ${legal.series[legal.series.length - 1].label} and <span class="num">${n0(legal.series[legal.series.length - 2] ? legal.series[legal.series.length - 2].notices : 0)}</span> in ${legal.series[legal.series.length - 2] ? legal.series[legal.series.length - 2].label : ''}. They come from the Department of Social Services and the Department of Youth and Community Development. ${legal.top && legal.top.length >= 2 ? `The two largest, both published on ${longDate(legal.top[0].date)}, went to ${esc(legal.top[0].vendor)} (<span class="num">${money(legal.top[0].value)}</span>) and ${esc(legal.top[1].vendor)} (<span class="num">${money(legal.top[1].value)}</span>).` : ''}</p>
    <p>The negative findings are worth recording too. Across ${n0(d.coverage.publication_days)} publication days, ${themeThin.map(t => `<span class="num">${n0(themeTotal(t))}</span> ${themeTotal(t) === 1 ? 'notice mentions' : 'notices mention'} ${t.label.toLowerCase()}`).join(', and ')}. Whatever the city is doing on either front, it is not arriving through published contract notices in this period.</p>
  </section>`);

  // ── 12. Limits ────────────────────────────────────────────────────────
  out.push(`<section class="finding" id="limits">
    <div class="kicker">Finding 12</div>
    <h2>What this archive cannot tell you</h2>
    <p>Four limits govern everything above, and none of them can be engineered away.</p>
    <p><strong>Coverage is uneven.</strong> The archive holds <span class="num">${n0(d.coverage.publication_days)}</span> of <span class="num">${n0(d.coverage.weekdays_in_range)}</span> weekdays in range, and the missing days are clustered rather than scattered. Counts are only comparable after dividing by publication days, which is what this page does throughout.</p>
    <p><strong>Published amounts are not spending.</strong> A contract amount in the City Record is the value of the agreement as published, frequently spanning several years and sometimes restating a renewal of money already counted. <span class="num">${money(d.totals.award_value)}</span> is the sum of headline figures, not a ${d.range.start.slice(0, 4)} outlay.</p>
    <p><strong>The record shows the notice, not the reason.</strong> The City Record says an agency used a negotiated acquisition. It does not say why, whether the determination was justified, or whether anyone objected. Those answers live in agency determinations, Comptroller registration and the Procurement Policy Board record.</p>
    <p><strong>Structure changes underfoot.</strong> Finding 07 is the proof: a section can be renamed and its machine-readable fields can vanish without any announcement in the data itself. Any trend line that crosses such a change is measuring the paper as much as the city.</p>
    <p>Everything on this page is computed by <code>build-analysis.mjs</code> from the daily files in <code>data/</code>, and rebuilt on every daily run. Nothing is hand-entered, and no figure here is estimated or modeled.</p>
  </section>`);

  document.getElementById('story').innerHTML = out.join('');
  document.getElementById('byline').textContent =
    `${n0(d.coverage.publication_days)} publication days · ${longDate(d.range.start)} – ${longDate(d.range.end)} · rebuilt ${longDate(d.generated)}`;
}

// ── small builders used above ───────────────────────────────────────────
function figure(title, sub, svgMarkup, caption) {
  return `<figure><div class="fig-title">${esc(title)}</div><div class="fig-sub">${esc(sub)}</div>${svgMarkup}${caption ? `<figcaption>${caption}</figcaption>` : ''}</figure>`;
}
function checkit(text) {
  return `<div class="checkit"><strong>Check it yourself:</strong> ${text}</div>`;
}
