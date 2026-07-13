// Builds data/trends.json — precomputed aggregates for the Trends dashboard.
//
// Reads every data/YYYY-MM-DD.json daily file and rolls the notices up into
// monthly / daily / agency / vendor time series so the front-end can render
// trends from a single file instead of fetching ~120 daily files.
//
// Definitions (documented in methodology.html):
//   • "Award value" = sum of contract_amount on Procurement-section notices whose
//     type is "Award". This is committed spend and excludes solicitations and
//     intents-to-award (which are pipeline, not awards). Amounts are as published
//     in the City Record and may reflect multi-year contract totals or renewals.
//   • "Non-competitive" = selection method matching NONCOMP_RE below.
//   • "Consulting" = title/description/category matching CONSULTING_RE with an
//     amount at or above $100K (mirrors the daily digest's CONSULTING flag).
//
// Usage: node build-trends.mjs   (run from the city-record-daily directory)

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const DATA_DIR = 'data';

const NONCOMP_RE = /sole source|negotiated|non-competitive|single source|emergency|required\/authorized|preferred source|discretionary|intergovernmental|government to government/i;
const CONSULTING_RE = /consult|lobbying|communications|public relations|advertising/i;

function amt(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

function monthKey(dateStr) {
  return dateStr.slice(0, 7);
}

function monthLabel(mk) {
  const [y, m] = mk.split('-');
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${names[parseInt(m, 10) - 1]} ${y}`;
}

function isAward(n) {
  return n.section_name === 'Procurement' && /award/i.test(n.type_of_notice_description || '')
    && !/intent to award/i.test(n.type_of_notice_description || '');
}

function isNoncomp(n) {
  return NONCOMP_RE.test(n.selection_method_description || '');
}

function isConsulting(n) {
  const text = `${n.short_title || ''} ${n.category_description || ''} ${n.description || ''}`;
  return CONSULTING_RE.test(text) && amt(n.contract_amount) >= 100_000;
}

// ── Load every daily file ────────────────────────────────────────────────
const files = readdirSync(DATA_DIR)
  .filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
  .sort();

if (files.length === 0) {
  console.error('No daily data files found in', DATA_DIR);
  process.exit(1);
}

const months = new Map();   // mk -> aggregate object
const daily = [];           // {date, award_value, award_count, notable_count}
const agencies = new Map(); // name -> {total_value, total_count, by_month:Map, first_month, last_month}
const vendors = new Map();  // name -> {total_value, total_count, awards, by_month:Map, first_month, first_award}
const allAwards = [];       // for largest-contracts leaderboard

let totalAwardValue = 0, totalAwardCount = 0, totalNoticeCount = 0, totalNotable = 0;

function ensureMonth(mk) {
  if (!months.has(mk)) {
    months.set(mk, {
      month: mk, label: monthLabel(mk),
      award_value: 0, award_count: 0, avg_award: 0,
      notice_count: 0, notable_count: 0, watching_count: 0,
      noncomp_value: 0, noncomp_count: 0, noncomp_share: 0,
      emergency_count: 0, consulting_value: 0, consulting_count: 0,
      sections: {}, methods: {}, flags: {},
      _agencyV: new Map(), _agencyC: new Map(),
      _vendorV: new Map(), _vendorC: new Map(),
      days: 0,
    });
  }
  return months.get(mk);
}

function bump(map, key, val) {
  map.set(key, (map.get(key) || 0) + val);
}

for (const file of files) {
  const date = file.replace('.json', '');
  const mk = monthKey(date);
  let day;
  try {
    day = JSON.parse(readFileSync(join(DATA_DIR, file), 'utf8'));
  } catch {
    continue;
  }
  const notices = day.notices || [];
  const notable = day.notable || [];
  const watching = day.watching || [];
  const M = ensureMonth(mk);
  M.days += 1;

  let dayAwardValue = 0, dayAwardCount = 0;

  M.notice_count += notices.length;
  M.notable_count += notable.length;
  M.watching_count += watching.length;
  totalNoticeCount += notices.length;
  totalNotable += notable.length + watching.length;

  for (const n of notices) {
    M.sections[n.section_name || 'Other'] = (M.sections[n.section_name || 'Other'] || 0) + 1;

    if (n.section_name === 'Procurement' && n.selection_method_description) {
      M.methods[n.selection_method_description] = (M.methods[n.selection_method_description] || 0) + 1;
    }
    if (/emergency/i.test(n.selection_method_description || '') || /emergency/i.test(n.type_of_notice_description || '')) {
      M.emergency_count += 1;
    }
    if (isConsulting(n)) {
      M.consulting_count += 1;
      M.consulting_value += amt(n.contract_amount);
    }

    if (isAward(n)) {
      const v = amt(n.contract_amount);
      dayAwardValue += v; dayAwardCount += 1;
      M.award_value += v; M.award_count += 1;
      totalAwardValue += v; totalAwardCount += 1;

      const ag = n.agency_name || 'Unknown';
      bump(M._agencyV, ag, v); bump(M._agencyC, ag, 1);
      const A = agencies.get(ag) || { total_value: 0, total_count: 0, by_month: new Map(), first_month: mk, last_month: mk };
      A.total_value += v; A.total_count += 1; bump(A.by_month, mk, v);
      A.last_month = mk;
      if (mk < A.first_month) A.first_month = mk;
      agencies.set(ag, A);

      if (isNoncomp(n)) { M.noncomp_value += v; M.noncomp_count += 1; }

      const vn = (n.vendor_name || '').trim();
      if (vn) {
        bump(M._vendorV, vn, v); bump(M._vendorC, vn, 1);
        const V = vendors.get(vn) || { total_value: 0, total_count: 0, by_month: new Map(), first_month: mk, first_award: null };
        V.total_value += v; V.total_count += 1; bump(V.by_month, mk, v);
        if (mk < V.first_month) V.first_month = mk;
        if (!V.first_award || date < V.first_award.date) {
          V.first_award = { date, agency: ag, title: n.short_title || '', request_id: n.request_id, amount: v };
        }
        vendors.set(vn, V);
      }

      if (v > 0) {
        allAwards.push({
          request_id: n.request_id, title: n.short_title || '', agency: ag,
          vendor: vn, amount: v, date, method: n.selection_method_description || '',
        });
      }
    }
  }

  // Flag mix (notable + watching)
  for (const item of notable.concat(watching)) {
    const code = item.flag_code;
    if (code) M.flags[code] = (M.flags[code] || 0) + 1;
  }

  daily.push({ date, award_value: dayAwardValue, award_count: dayAwardCount, notable_count: notable.length });
}

// ── Finalize monthly objects ─────────────────────────────────────────────
const monthList = [...months.values()].sort((a, b) => a.month.localeCompare(b.month));
for (const M of monthList) {
  M.avg_award = M.award_count ? Math.round(M.award_value / M.award_count) : 0;
  M.noncomp_share = M.award_value ? M.noncomp_value / M.award_value : 0;
  const topN = (mapV, mapC, k) => [...mapV.entries()].sort((a, b) => b[1] - a[1]).slice(0, k)
    .map(([name, val]) => [name, val, mapC.get(name) || 0]);
  M.top_agencies = topN(M._agencyV, M._agencyC, 6);
  M.top_vendors = topN(M._vendorV, M._vendorC, 6);
  delete M._agencyV; delete M._agencyC; delete M._vendorV; delete M._vendorC;
}

// Flag series: code -> {month: count}
const flagCodes = new Set();
monthList.forEach(M => Object.keys(M.flags).forEach(c => flagCodes.add(c)));
const flagSeries = {};
for (const code of flagCodes) {
  flagSeries[code] = {};
  monthList.forEach(M => { flagSeries[code][M.month] = M.flags[code] || 0; });
}

// ── Agency / vendor leaderboards ─────────────────────────────────────────
function serializeEntities(map, keep) {
  return [...map.entries()]
    .map(([name, o]) => ({
      name,
      total_value: Math.round(o.total_value),
      total_count: o.total_count,
      awards: o.total_count,
      first_month: o.first_month,
      last_month: o.last_month,
      first_award: o.first_award || null,
      by_month: Object.fromEntries([...o.by_month.entries()].map(([m, v]) => [m, Math.round(v)])),
    }))
    .sort((a, b) => b.total_value - a.total_value)
    .slice(0, keep);
}

const agencyList = serializeEntities(agencies, 40);
const vendorList = serializeEntities(vendors, 80);

// First-time vendors: those whose very first award landed in the most recent 2 months
const recentMonths = monthList.slice(-2).map(m => m.month);
const firstTimeVendors = [...vendors.entries()]
  .filter(([, o]) => recentMonths.includes(o.first_month) && o.first_award)
  .map(([name, o]) => ({
    name, month: o.first_month, value: Math.round(o.total_value),
    agency: o.first_award.agency, title: o.first_award.title,
    request_id: o.first_award.request_id, date: o.first_award.date,
  }))
  .sort((a, b) => b.value - a.value)
  .slice(0, 25);

const largestContracts = allAwards
  .sort((a, b) => b.amount - a.amount)
  .slice(0, 30)
  .map(c => ({ ...c, amount: Math.round(c.amount) }));

const out = {
  generated: files[files.length - 1].replace('.json', ''),
  date_range: { start: files[0].replace('.json', ''), end: files[files.length - 1].replace('.json', '') },
  days: files.length,
  totals: {
    award_value: Math.round(totalAwardValue),
    award_count: totalAwardCount,
    notice_count: totalNoticeCount,
    notable_count: totalNotable,
    avg_award: totalAwardCount ? Math.round(totalAwardValue / totalAwardCount) : 0,
  },
  months: monthList,
  daily,
  agencies: agencyList,
  vendors: vendorList,
  first_time_vendors: firstTimeVendors,
  largest_contracts: largestContracts,
  flag_series: flagSeries,
};

writeFileSync(join(DATA_DIR, 'trends.json'), JSON.stringify(out));
console.log(`Wrote ${DATA_DIR}/trends.json — ${monthList.length} months, ${files.length} days, ` +
  `$${(totalAwardValue / 1e9).toFixed(2)}B in ${totalAwardCount} awards, ` +
  `${agencyList.length} agencies, ${vendorList.length} vendors.`);
