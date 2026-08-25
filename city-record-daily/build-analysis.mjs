// Builds data/analysis.json — the numbers behind "The 2026 File", the long-form
// read of the archive that lives at analysis.html.
//
// This is deliberately separate from build-trends.mjs. trends.json powers the
// dashboard (what happened lately); analysis.json powers a narrative that asks
// a different question: what has changed across the year, and what is an
// artifact of how the City Record — or this archive — publishes.
//
// Every figure the essay states is computed here, so the prose updates with the
// data instead of freezing on the day it was written.
//
// Definitions match methodology.html and build-trends.mjs:
//   • "Award" = Procurement-section notice of type Award (not Intent to Award).
//   • "$" = the published contract_amount, which may be a multi-year or
//     renewal total. It is a headline value, not a cash outlay for the year.
//   • Rates are per publication day, never per calendar day — the archive does
//     not hold every weekday, and the gaps are not evenly spread (see coverage).
//
// Usage: node build-analysis.mjs   (run from the city-record-daily directory)

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const DATA_DIR = 'data';
const OUT = join(DATA_DIR, 'analysis.json');

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// Selection-method families. A method string is matched against these in order.
const COMPETITIVE_RE = /competitive sealed|request for proposals|request for quote|innovative procurement/i;
const NONCOMP_RE = /sole source|negotiated acquisition|emergency|required\/authorized|required method|preferred source|intergovernmental|government to government|m\/wbe noncompetitive|discretionary/i;

const amt = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
const mk = d => d.slice(0, 7);
const mlabel = k => `${MONTH_NAMES[parseInt(k.slice(5), 10) - 1]} ${k.slice(0, 4)}`;
const median = xs => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b); const i = Math.floor(s.length / 2); return s.length % 2 ? s[i] : (s[i - 1] + s[i]) / 2; };
const sum = xs => xs.reduce((a, b) => a + b, 0);
const isAward = n => n.section_name === 'Procurement' && /award/i.test(n.type_of_notice_description || '') && !/intent to award/i.test(n.type_of_notice_description || '');

// ── Load ────────────────────────────────────────────────────────────────
const files = readdirSync(DATA_DIR).filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort();
if (!files.length) { console.error('build-analysis: no daily files found'); process.exit(1); }

const notices = [];
const dates = [];
for (const f of files) {
  const day = JSON.parse(readFileSync(join(DATA_DIR, f), 'utf8'));
  if (!day.date) continue;
  dates.push(day.date);
  for (const n of day.notices || []) { n._date = day.date; notices.push(n); }
}
if (!notices.length) { console.error('build-analysis: daily files held no notices'); process.exit(1); }

const start = dates[0], end = dates[dates.length - 1];
const awards = notices.filter(isAward);
const months = [...new Set(dates.map(mk))];
const dayCount = {};
for (const d of dates) dayCount[mk(d)] = (dayCount[mk(d)] || 0) + 1;

// ── Coverage: which weekdays in range are missing, and are they clustered? ──
const held = new Set(dates);
const weekdays = [];
for (let t = Date.parse(start + 'T00:00:00Z'); t <= Date.parse(end + 'T00:00:00Z'); t += 864e5) {
  const d = new Date(t), dow = d.getUTCDay();
  if (dow > 0 && dow < 6) weekdays.push(d.toISOString().slice(0, 10));
}
const missing = weekdays.filter(d => !held.has(d));
const dowHeld = {};
for (const d of dates) { const w = DOW[new Date(d + 'T00:00:00Z').getUTCDay()]; dowHeld[w] = (dowHeld[w] || 0) + 1; }
// A run of 3+ consecutive missing weekdays reads as an outage, not a holiday.
const outages = [];
for (let i = 0; i < missing.length; i++) {
  let j = i;
  while (j + 1 < missing.length && (Date.parse(missing[j + 1]) - Date.parse(missing[j])) <= 3 * 864e5) j++;
  if (j - i >= 2) outages.push({ from: missing[i], to: missing[j], days: j - i + 1 });
  i = j;
}
// First date on which each weekday name appears, to expose a late-starting capture.
const firstByDow = {};
for (const d of dates) { const w = DOW[new Date(d + 'T00:00:00Z').getUTCDay()]; if (!firstByDow[w]) firstByDow[w] = d; }

// ── Monthly spine ───────────────────────────────────────────────────────
const SIZE_BANDS = [
  { key: 'u100k', label: 'Under $100K', lo: 1, hi: 1e5 },
  { key: 'k100_1m', label: '$100K–$1M', lo: 1e5, hi: 1e6 },
  { key: 'm1_10', label: '$1M–$10M', lo: 1e6, hi: 1e7 },
  { key: 'm10_100', label: '$10M–$100M', lo: 1e7, hi: 1e8 },
  { key: 'o100m', label: '$100M+', lo: 1e8, hi: Infinity },
];

const monthly = months.map(m => {
  const rows = notices.filter(n => mk(n._date) === m);
  const aw = awards.filter(n => mk(n._date) === m);
  const vals = aw.map(n => amt(n.contract_amount)).filter(v => v > 0);
  const d = dayCount[m];
  const methodCount = re => aw.filter(n => re.test(n.selection_method_description || '')).length;
  const bands = {};
  for (const b of SIZE_BANDS) bands[b.key] = aw.filter(n => { const v = amt(n.contract_amount); return v >= b.lo && v < b.hi; }).length;
  const sections = {};
  for (const n of rows) sections[n.section_name] = (sections[n.section_name] || 0) + 1;
  const compValue = sum(aw.filter(n => COMPETITIVE_RE.test(n.selection_method_description || '')).map(n => amt(n.contract_amount)));
  const noncompValue = sum(aw.filter(n => !COMPETITIVE_RE.test(n.selection_method_description || '') && NONCOMP_RE.test(n.selection_method_description || '')).map(n => amt(n.contract_amount)));
  const total = sum(vals);
  return {
    month: m, label: mlabel(m), days: d,
    notices: rows.length, notices_per_day: rows.length / d,
    awards: aw.length, awards_per_day: aw.length / d,
    value: total, median: median(vals), mean: vals.length ? total / vals.length : 0,
    comp_value_share: total ? compValue / total : 0,
    noncomp_value_share: total ? noncompValue / total : 0,
    renewals: methodCount(/^renewal/i),
    negotiated: methodCount(/^negotiated acquisition/i),
    sole_source: methodCount(/sole source/i),
    emergency: methodCount(/emergency/i),
    mwbe_small: methodCount(/m\/wbe noncompetitive/i),
    solicitations: rows.filter(n => n.type_of_notice_description === 'Solicitation').length,
    intents: rows.filter(n => n.type_of_notice_description === 'Intent to Award').length,
    rules: rows.filter(n => n.section_name === 'Agency Rules').length,
    hearings: rows.filter(n => /public hearings|meeting/i.test(n.type_of_notice_description || '')).length,
    bands, sections,
  };
});

// ── Selection methods across the whole archive ──────────────────────────
const methodTotals = {};
for (const n of awards) {
  const k = n.selection_method_description || '(not stated)';
  methodTotals[k] = methodTotals[k] || { count: 0, value: 0 };
  methodTotals[k].count++;
  methodTotals[k].value += amt(n.contract_amount);
}
const methods = Object.entries(methodTotals).map(([name, o]) => ({ name, ...o })).sort((a, b) => b.value - a.value);

// ── Concentration ───────────────────────────────────────────────────────
const sortedVals = awards.map(n => amt(n.contract_amount)).sort((a, b) => b - a);
const grandTotal = sum(sortedVals);
const topShares = [1, 5, 10, 25, 50, 100].map(k => ({ n: k, value: sum(sortedVals.slice(0, k)), share: grandTotal ? sum(sortedVals.slice(0, k)) / grandTotal : 0 }));
const bottomHalfShare = grandTotal ? sum(sortedVals.slice(Math.floor(sortedVals.length / 2))) / grandTotal : 0;

// ── Agencies: totals, and how much of each one's year landed in one month ──
const agencyMap = {};
for (const n of awards) {
  const a = agencyMap[n.agency_name] = agencyMap[n.agency_name] || { count: 0, value: 0, byMonth: {} };
  a.count++; a.value += amt(n.contract_amount);
  const m = mk(n._date);
  a.byMonth[m] = a.byMonth[m] || { count: 0, value: 0 };
  a.byMonth[m].count++; a.byMonth[m].value += amt(n.contract_amount);
}
const agencies = Object.entries(agencyMap).map(([name, a]) => {
  let peak = null;
  for (const [m, o] of Object.entries(a.byMonth)) if (!peak || o.value > peak.value) peak = { month: m, label: mlabel(m), ...o };
  return { name, count: a.count, value: a.value, peak_month: peak, peak_share: a.value ? peak.value / a.value : 0, by_month: a.byMonth };
}).sort((a, b) => b.value - a.value);

// ── Vendors ─────────────────────────────────────────────────────────────
const vendorMap = {};
for (const n of awards) {
  const v = (n.vendor_name || '').trim(); if (!v) continue;
  vendorMap[v] = vendorMap[v] || { count: 0, value: 0 };
  vendorMap[v].count++; vendorMap[v].value += amt(n.contract_amount);
}
const vendors = Object.entries(vendorMap).map(([name, o]) => ({ name, ...o })).sort((a, b) => b.value - a.value);

const largest = awards.slice().sort((a, b) => amt(b.contract_amount) - amt(a.contract_amount)).slice(0, 20)
  .map(n => ({ date: n._date, value: amt(n.contract_amount), agency: n.agency_name, vendor: n.vendor_name, method: n.selection_method_description, title: n.short_title, request_id: n.request_id }));

// ── The section swap: one public-comment channel replacing another ──────
const sectionSeries = months.map(m => {
  const rows = notices.filter(n => mk(n._date) === m);
  return {
    month: m, label: mlabel(m),
    award_hearings: rows.filter(n => n.section_name === 'Contract Award Hearings').length,
    public_comment: rows.filter(n => n.section_name === 'Public Comment on Contract Awards').length,
  };
});
const firstDateInSection = name => { const hit = notices.find(n => n.section_name === name); return hit ? hit._date : null; };

// ── Executive orders: numbering, resets, and the standing-emergency clock ──
const eoNotices = notices.filter(n => /executive order/i.test(n.short_title || ''));
const execOrders = eoNotices.map(n => {
  const m = (n.short_title || '').match(/no\.?\s*([0-9]+(?:\.[0-9]+)?)/i);
  return { date: n._date, title: n.short_title, number: m ? m[1] : null, emergency: /emergency/i.test(n.short_title || '') };
}).sort((a, b) => a.date.localeCompare(b.date) || (a.title > b.title ? 1 : -1));
const standingEmergency = {};
for (const e of execOrders) {
  if (!e.emergency || !e.number || !e.number.includes('.')) continue;
  const series = e.number.split('.')[0];
  (standingEmergency[series] = standingEmergency[series] || []).push({ date: e.date, number: e.number });
}
const emergencyRenewalGaps = [];
for (const list of Object.values(standingEmergency)) {
  const uniq = [...new Set(list.map(x => x.date))].sort();
  for (let i = 1; i < uniq.length; i++) emergencyRenewalGaps.push(Math.round((Date.parse(uniq[i]) - Date.parse(uniq[i - 1])) / 864e5));
}

// ── Emergency procurements ──────────────────────────────────────────────
const emergencyAwards = awards.filter(n => /emergency/i.test(n.selection_method_description || ''))
  .map(n => ({ date: n._date, value: amt(n.contract_amount), agency: n.agency_name, vendor: n.vendor_name, title: n.short_title }))
  .sort((a, b) => a.date.localeCompare(b.date));

// ── Bid windows: days between publication and the stated due date ───────
const leadRows = notices.filter(n => n.type_of_notice_description === 'Solicitation' && n.due_date)
  .map(n => ({ month: mk(n._date), days: Math.round((Date.parse(n.due_date) - Date.parse(n._date + 'T00:00:00')) / 864e5), agency: n.agency_name, title: n.short_title, date: n._date }))
  .filter(r => r.days >= 0 && r.days < 400);
const leadByMonth = months.map(m => {
  const r = leadRows.filter(x => x.month === m).map(x => x.days);
  return { month: m, label: mlabel(m), n: r.length, median: median(r), short_share: r.length ? r.filter(x => x <= 14).length / r.length : 0 };
});
const leadAll = leadRows.map(r => r.days);

// ── Themes worth following across the year ──────────────────────────────
const THEMES = [
  { key: 'shelter', label: 'Shelter and homeless services', re: /shelter|homeless|drop-?in center/i },
  { key: 'immigrant_legal', label: 'Immigrant and low-wage legal services', re: /immigra\w+ legal|legal services (for|to) (immigrants|recent immigrants|unaccompanied)|low.?wage worker legal/i },
  { key: 'mental_health', label: 'Mental health and overdose', re: /mental health|overdose|opioid|naloxone/i },
  { key: 'flood', label: 'Flooding and resiliency', re: /flood|resilien|cloudburst|coastal storm/i },
  { key: 'cyber', label: 'Cybersecurity', re: /cyber/i },
  // Kept for the negative finding: these are near-absent from the record.
  { key: 'ai', label: 'Artificial intelligence', re: /artificial intelligence|machine learning|large language model|\bchatbot\b/i },
  { key: 'micromobility', label: 'E-bikes and micromobility', re: /e-?bike|micromobility/i },
];
const themes = THEMES.map(t => ({
  key: t.key, label: t.label,
  top: awards.filter(n => t.re.test(`${n.short_title || ''} ${n.description || ''}`))
    .sort((a, b) => amt(b.contract_amount) - amt(a.contract_amount)).slice(0, 3)
    .map(n => ({ date: n._date, value: amt(n.contract_amount), agency: n.agency_name, vendor: n.vendor_name, title: n.short_title })),
  series: months.map(m => {
    const rows = notices.filter(n => mk(n._date) === m && t.re.test(`${n.short_title || ''} ${n.description || ''}`));
    const aw = rows.filter(isAward);
    return { month: m, label: mlabel(m), notices: rows.length, awards: aw.length, value: sum(aw.map(n => amt(n.contract_amount))) };
  }),
}));

// ── Youth and Community Development: the year's biggest behavioral shift ──
const dycdAwards = awards.filter(n => n.agency_name === 'Youth and Community Development');
const dycdNegotiated = dycdAwards.filter(n => /^negotiated acquisition/i.test(n.selection_method_description || ''));
const dycd = {
  total_awards: dycdAwards.length,
  total_value: sum(dycdAwards.map(n => amt(n.contract_amount))),
  negotiated_awards: dycdNegotiated.length,
  negotiated_value: sum(dycdNegotiated.map(n => amt(n.contract_amount))),
  negotiated_vendors: new Set(dycdNegotiated.map(n => n.vendor_name)).size,
  citywide_negotiated: awards.filter(n => /^negotiated acquisition/i.test(n.selection_method_description || '')).length,
  by_month: months.map(m => ({ month: m, label: mlabel(m), awards: dycdAwards.filter(n => mk(n._date) === m).length, value: sum(dycdAwards.filter(n => mk(n._date) === m).map(n => amt(n.contract_amount))) })),
  programs: Object.entries(dycdNegotiated.reduce((o, n) => {
    const p = /beacon/i.test(n.short_title) ? 'Beacon' : /cornerstone/i.test(n.short_title) ? 'Cornerstone' : /compass/i.test(n.short_title) ? 'COMPASS' : /syep|summer youth/i.test(n.short_title) ? 'Summer Youth Employment' : /saturday night lights/i.test(n.short_title) ? 'Saturday Night Lights' : 'Other youth programs';
    o[p] = (o[p] || 0) + 1; return o;
  }, {})).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count),
};

// ── Fiscal-year boundary ────────────────────────────────────────────────
const fyLabel = 'FY27';
const fyTagged = awards.filter(n => /fy\s?-?27\b|fy2027/i.test(n.short_title || ''));
const boundary = (() => {
  const y = end.slice(0, 4);
  const w = awards.filter(n => n._date >= `${y}-06-16` && n._date <= `${y}-07-15`);
  return { from: `${y}-06-16`, to: `${y}-07-15`, awards: w.length, value: sum(w.map(n => amt(n.contract_amount))), renewals: w.filter(n => /^renewal/i.test(n.selection_method_description || '')).length, days: new Set(w.map(n => n._date)).size };
})();

const byDay = {};
for (const n of awards) { const d = byDay[n._date] = byDay[n._date] || { count: 0, value: 0 }; d.count++; d.value += amt(n.contract_amount); }
const busiestDays = Object.entries(byDay).map(([date, o]) => ({ date, ...o })).sort((a, b) => b.count - a.count).slice(0, 10);
const richestDays = Object.entries(byDay).map(([date, o]) => ({ date, ...o })).sort((a, b) => b.value - a.value).slice(0, 10);

// ── Write ───────────────────────────────────────────────────────────────
const out = {
  generated: new Date().toISOString().slice(0, 10),
  range: { start, end },
  coverage: {
    publication_days: dates.length,
    weekdays_in_range: weekdays.length,
    missing_weekdays: missing.length,
    missing: missing,
    by_weekday: dowHeld,
    first_by_weekday: firstByDow,
    outages,
  },
  totals: {
    notices: notices.length,
    awards: awards.length,
    award_value: grandTotal,
    median_award: median(awards.map(n => amt(n.contract_amount)).filter(v => v > 0)),
    agencies: agencies.length,
    vendors: vendors.length,
  },
  monthly,
  size_bands: SIZE_BANDS.map(b => ({ key: b.key, label: b.label })),
  methods,
  concentration: { top: topShares, bottom_half_share: bottomHalfShare, total: grandTotal, awards: sortedVals.length },
  agencies: agencies.slice(0, 25),
  vendors: vendors.slice(0, 25),
  largest,
  section_swap: { series: sectionSeries, award_hearings_first: firstDateInSection('Contract Award Hearings'), public_comment_first: firstDateInSection('Public Comment on Contract Awards') },
  exec_orders: { all: execOrders, standing_series: Object.keys(standingEmergency).sort(), standing_counts: Object.fromEntries(Object.entries(standingEmergency).map(([k, v]) => [k, v.length])), median_renewal_gap: median(emergencyRenewalGaps) },
  emergency_awards: emergencyAwards,
  bid_windows: { by_month: leadByMonth, overall_median: median(leadAll), n: leadAll.length, short_share: leadAll.length ? leadAll.filter(x => x <= 14).length / leadAll.length : 0, very_short: leadRows.filter(r => r.days <= 3).sort((a, b) => a.days - b.days).slice(0, 10) },
  themes,
  dycd,
  fiscal_year: { label: fyLabel, tagged_awards: fyTagged.length, tagged_value: sum(fyTagged.map(n => amt(n.contract_amount))), tagged_share: grandTotal ? sum(fyTagged.map(n => amt(n.contract_amount))) / grandTotal : 0, by_month: months.map(m => ({ month: m, label: mlabel(m), count: fyTagged.filter(n => mk(n._date) === m).length })), boundary },
  busiest_days: busiestDays,
  richest_days: richestDays,
};

writeFileSync(OUT, JSON.stringify(out));
console.log(`build-analysis: ${dates.length} publication days, ${notices.length} notices, ${awards.length} awards -> ${OUT}`);
