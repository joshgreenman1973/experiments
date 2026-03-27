#!/usr/bin/env node
// Fetches NYC City Record notices for a given date, flags notable items,
// writes the daily JSON file, updates the manifest, and regenerates RSS feeds.
//
// Usage: node fetch-daily.mjs [YYYY-MM-DD]
//   Defaults to today. Falls back to previous business day if no data found.

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';

const DIR = import.meta.dirname;
const DATA_DIR = join(DIR, 'data');
const API_BASE = 'https://data.cityofnewyork.us/resource/dg92-zbpx.json';

// --- Date helpers ---

function today() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function prevBusinessDay(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const dow = d.getDay(); // 0=Sun, 6=Sat
  if (dow === 1) d.setDate(d.getDate() - 3); // Mon → Fri
  else if (dow === 0) d.setDate(d.getDate() - 2); // Sun → Fri
  else d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

// --- API fetch ---

async function fetchNotices(dateStr) {
  const url = `${API_BASE}?$where=start_date='${dateStr}'&$limit=2000&$order=section_name,agency_name`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

// --- String cleaning ---

function cleanStr(s) {
  if (typeof s !== 'string') return s;
  // Strip XML-invalid control characters
  return s.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '');
}

function cleanRecord(rec) {
  const out = {};
  for (const [k, v] of Object.entries(rec)) {
    out[k] = cleanStr(v);
  }
  return out;
}

// --- Extract notice fields ---

function extractNotice(raw) {
  return {
    request_id: raw.request_id || '',
    start_date: raw.start_date || '',
    agency_name: raw.agency_name || '',
    section_name: raw.section_name || '',
    type_of_notice_description: raw.type_of_notice_description || '',
    category_description: raw.category_description || '',
    short_title: raw.short_title || '',
    contract_amount: raw.contract_amount || '',
    vendor_name: raw.vendor_name || '',
    due_date: raw.due_date || '',
    event_date: raw.event_date || '',
    selection_method_description: raw.selection_method_description || '',
  };
}

// --- Flagging logic ---

const KEY_AGENCIES_RE = /\b(nycha|housing authority|housing preservation|hpd|dept\.?\s*of\s*education|doe|police|nypd|correction\b|doc\b|homeless services|dhs|children.s services|acs|management and budget|omb|mocj|criminal justice|city planning|office of the mayor|mayor.s office)\b/i;

const POLICY_TERMS_RE = /\b(shelter|jail|rikers|rezoning|affordable housing|charter school|homelessness|public safety|eviction|supportive housing|mental health|opioid|overdose|gun violence|youth program)\b/i;

const SOLE_SOURCE_RE = /\b(sole source|negotiated acquisition|non-competitive|single source)\b/i;

// Special Materials patterns
const EXECUTIVE_ORDER_RE = /executive\s+order/i;
const CEQR_RE = /\b(ceqr|positive declaration|negative declaration|rezoning|environmental\s+(impact|review))\b/i;
const CONCEPT_PAPER_RE = /concept\s+paper/i;
const ROUTINE_SPECIAL_RE = /\b(weekly fuel price|monthly index|LL63)\b/i;

function parseAmount(raw) {
  if (!raw) return 0;
  const s = typeof raw === 'string' ? raw : String(raw);
  const n = parseFloat(s.replace(/[,$]/g, ''));
  return isNaN(n) ? 0 : n;
}

function extractAmountsFromDesc(desc) {
  if (!desc) return 0;
  const matches = desc.match(/\$[\d,]+(?:\.\d{2})?/g);
  if (!matches) return 0;
  let max = 0;
  for (const m of matches) {
    const n = parseFloat(m.replace(/[,$]/g, ''));
    if (n > max) max = n;
  }
  return max;
}

function fmtMoney(n) {
  if (!n || n === 0) return '';
  if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return '$' + Math.round(n / 1e3) + 'K';
  return '$' + n.toLocaleString();
}

function flagNotice(notice, raw) {
  const agency = notice.agency_name || '';
  const section = notice.section_name || '';
  const title = notice.short_title || '';
  const type = notice.type_of_notice_description || '';
  const selection = notice.selection_method_description || '';
  const desc = raw.additional_description_1 || '';
  const amount = parseAmount(notice.contract_amount);
  const descAmount = extractAmountsFromDesc(desc);
  const maxAmount = Math.max(amount, descAmount);
  const vendor = notice.vendor_name || '';
  const category = notice.category_description || '';
  const allText = `${title} ${desc} ${type} ${category}`.toLowerCase();

  // --- Highest priority: executive orders and special materials ---

  // Executive orders from the Mayor
  if (EXECUTIVE_ORDER_RE.test(title)) {
    const isEmergency = /emergency/i.test(title);
    const orderNum = title.match(/No\.?\s*(\d+(\.\d+)?)/i);
    const label = orderNum ? `No. ${orderNum[1]}` : '';
    return {
      priority: 'notable',
      summary: `${isEmergency ? 'Emergency executive' : 'Executive'} order ${label} from the Mayor. Executive orders carry the force of law and can reshape city policy, agency operations, and enforcement priorities.`
    };
  }

  // CEQR environmental reviews and rezonings in Special Materials
  if (section === 'Special Materials' && CEQR_RE.test(title)) {
    return {
      priority: 'notable',
      summary: `Environmental review or rezoning action: ${title.length > 80 ? title.slice(0, 80) + '...' : title}. Land use and environmental reviews signal major development or infrastructure changes.`
    };
  }

  // Concept papers (early signals of new programs)
  if (section === 'Special Materials' && CONCEPT_PAPER_RE.test(title)) {
    return {
      priority: 'notable',
      summary: `Concept paper from ${agency}: ${title.length > 80 ? title.slice(0, 80) + '...' : title}. Concept papers are the earliest public signal of a new program or contract -- the city is seeking feedback before procurement.`
    };
  }

  // Skip routine Special Materials (fuel prices, monthly index, LL63)
  if (section === 'Special Materials' && ROUTINE_SPECIAL_RE.test(title)) {
    return null;
  }

  // Other non-routine Special Materials (comptroller reports, NYCHA intents, etc.)
  if (section === 'Special Materials') {
    return {
      priority: 'notable',
      summary: `Special notice from ${agency}: ${title.length > 80 ? title.slice(0, 80) + '...' : title}. Special Materials often contain significant policy actions, legal notices, or procurement intents that don't fit standard categories.`
    };
  }

  // --- High-priority checks ---

  // Contracts over $1M
  if (maxAmount >= 1_000_000) {
    return {
      priority: 'notable',
      summary: `${fmtMoney(maxAmount)} ${type.toLowerCase() || 'contract'} by ${agency}${vendor ? ' to ' + vendor : ''}. ${section === 'Procurement' ? 'Large procurement worth tracking for scope and competitiveness.' : 'Significant dollar value warrants attention.'}`
    };
  }

  // Agency rules — always flag
  if (section === 'Agency Rules') {
    return {
      priority: 'notable',
      summary: `New rule proposed by ${agency}. Agency rules represent binding policy changes that affect how city services operate and who they reach.`
    };
  }

  // Property dispositions — always flag
  if (section === 'Property Disposition') {
    return {
      priority: 'notable',
      summary: `${agency} property disposition: ${title}. Dispositions of public assets deserve scrutiny to ensure fair value and appropriate use.`
    };
  }

  // Key agencies
  if (KEY_AGENCIES_RE.test(agency)) {
    const shortAgency = agency.length > 40 ? agency.slice(0, 40) + '…' : agency;
    return {
      priority: 'notable',
      summary: `${type || 'Notice'} from ${shortAgency}: ${title.length > 80 ? title.slice(0, 80) + '…' : title}. Key agency activity worth monitoring.`
    };
  }

  // Sole source / non-competitive
  if (SOLE_SOURCE_RE.test(selection) || SOLE_SOURCE_RE.test(allText)) {
    return {
      priority: 'notable',
      summary: `Non-competitive ${type.toLowerCase() || 'procurement'} by ${agency}${vendor ? ' to ' + vendor : ''}${maxAmount ? ' for ' + fmtMoney(maxAmount) : ''}. Sole-source contracts bypass competitive bidding and merit public scrutiny.`
    };
  }

  // Policy-relevant terms
  if (POLICY_TERMS_RE.test(allText)) {
    const match = allText.match(POLICY_TERMS_RE);
    const term = match ? match[0] : 'policy issue';
    return {
      priority: 'notable',
      summary: `${type || 'Notice'} from ${agency} related to ${term}. Policy-relevant topic for city watchers and advocates.`
    };
  }

  // --- Medium-priority checks ---

  // Construction/infrastructure over $500K
  if (maxAmount >= 500_000 && /construction|infrastructure|capital|renovation|repair/i.test(allText)) {
    return {
      priority: 'watching',
      summary: `${fmtMoney(maxAmount)} construction/infrastructure ${type.toLowerCase() || 'contract'} by ${agency}. Large capital spend worth monitoring.`
    };
  }

  // Environmental or health hearings
  if (/hearing|meeting/i.test(type) && /environment|health|water|air quality|toxic|lead|asbestos|climate/i.test(allText)) {
    return {
      priority: 'watching',
      summary: `${type} from ${agency} on environmental/health topic. Public input opportunity on quality-of-life issues.`
    };
  }

  // Human services extensions/renewals
  if (/extension|renewal|amendment/i.test(type) && /human services/i.test(category)) {
    return {
      priority: 'watching',
      summary: `Human services contract ${type.toLowerCase()} by ${agency}${vendor ? ' with ' + vendor : ''}. Continuity of social services contracts worth tracking.`
    };
  }

  // Consulting, lobbying, communications
  if (/consult|lobbying|communications|public relations|advertising/i.test(allText) && maxAmount >= 100_000) {
    return {
      priority: 'watching',
      summary: `${fmtMoney(maxAmount)} consulting/communications ${type.toLowerCase() || 'contract'} by ${agency}. Discretionary spending category that merits transparency.`
    };
  }

  return null;
}

// --- Main ---

async function main() {
  const targetDate = process.argv[2] || today();
  console.log(`Fetching City Record for ${targetDate}...`);

  let raw = await fetchNotices(targetDate);
  let date = targetDate;

  if (raw.length === 0) {
    const fallback = prevBusinessDay(targetDate);
    console.log(`No data for ${targetDate}, trying ${fallback}...`);
    raw = await fetchNotices(fallback);
    date = fallback;
  }

  if (raw.length === 0) {
    console.error('No City Record data found. Exiting.');
    process.exit(1);
  }

  console.log(`Found ${raw.length} notices for ${date}`);

  // Check if file already exists
  const outPath = join(DATA_DIR, `${date}.json`);
  if (existsSync(outPath)) {
    console.log(`${date}.json already exists — overwriting with fresh data.`);
  }

  // Process notices
  const notices = [];
  const notable = [];
  const watching = [];

  for (const r of raw) {
    const cleaned = cleanRecord(r);
    const notice = extractNotice(cleaned);
    notices.push(notice);

    const flag = flagNotice(notice, cleaned);
    if (flag) {
      const flagged = { ...notice, summary: flag.summary };
      if (flag.priority === 'notable') notable.push(flagged);
      else watching.push(flagged);
    }
  }

  // Sort notable: executive orders first, then by contract amount descending
  notable.sort((a, b) => {
    const aExec = EXECUTIVE_ORDER_RE.test(a.short_title) ? 0 : 1;
    const bExec = EXECUTIVE_ORDER_RE.test(b.short_title) ? 0 : 1;
    if (aExec !== bExec) return aExec - bExec;
    const aSpecial = a.section_name === 'Special Materials' ? 0 : 1;
    const bSpecial = b.section_name === 'Special Materials' ? 0 : 1;
    if (aSpecial !== bSpecial) return aSpecial - bSpecial;
    return parseAmount(b.contract_amount) - parseAmount(a.contract_amount);
  });

  console.log(`Flagged: ${notable.length} notable, ${watching.length} watching`);

  // Write daily JSON
  const dayData = { date, notices, notable, watching };
  writeFileSync(outPath, JSON.stringify(dayData, null, 2));
  console.log(`Wrote ${outPath}`);

  // Update manifest
  const manifestPath = join(DATA_DIR, 'manifest.json');
  let manifest = [];
  if (existsSync(manifestPath)) {
    manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  }
  if (!manifest.includes(date)) {
    manifest.push(date);
  }
  manifest.sort((a, b) => b.localeCompare(a));
  writeFileSync(manifestPath, JSON.stringify(manifest));
  console.log(`Updated manifest (${manifest.length} dates, latest: ${manifest[0]})`);

  // Regenerate feeds
  console.log('Regenerating RSS feeds...');
  execSync('node ' + join(DIR, 'generate-feeds.mjs'), { stdio: 'inherit' });

  console.log(`\nDone! ${date} data is ready.`);
}

main().catch(err => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
