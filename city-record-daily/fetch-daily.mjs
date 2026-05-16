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
  const desc = raw.additional_description_1 || '';
  // Truncate very long descriptions to keep payload reasonable
  const trimmedDesc = desc.length > 1200 ? desc.slice(0, 1200) + '…' : desc;
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
    description: trimmedDesc,
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

// Newsworthy keyword bumps
const EMERGENCY_RE = /\bemergency\s+(procurement|contract|declaration|order)\b/i;
const SETTLEMENT_RE = /\b(settlement|stipulation of settlement|class action settlement)\b/i;
const BOND_RE = /\bbond\s+(issuance|sale|series|anticipation)\b/i;
const ULURP_RE = /\bULURP\b/i;
const LANDMARK_RE = /\blandmark\s+(designation|hearing|preservation)\b/i;
const CONSENT_DECREE_RE = /\bconsent\s+decree\b/i;
const MONITOR_RE = /\b(court[-\s]appointed|independent|federal)\s+monitor\b/i;

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

// Reason codes + short factual labels (no editorial prose).
// Front-end maps these to UI chips; methodology.html documents thresholds.
const REASON_LABELS = {
  EXEC_ORDER: 'Mayoral executive order',
  EXEC_ORDER_EMERGENCY: 'Emergency executive order',
  CEQR: 'Environmental review / rezoning',
  CONCEPT_PAPER: 'Concept paper (pre-procurement)',
  SPECIAL_MATERIALS: 'Special Materials (non-routine)',
  BIG_CONTRACT: 'Contract value ≥ $1M',
  AGENCY_RULE: 'Agency rule (proposed or adopted)',
  PROP_DISP: 'City property disposition',
  COURT: 'Court notice',
  AWARD_HEARING: 'Contract award hearing',
  EMERGENCY: 'Emergency action',
  SETTLEMENT: 'Litigation settlement',
  BOND: 'Bond issuance / sale',
  LAND_USE: 'ULURP / landmark action',
  OVERSIGHT: 'Consent decree / monitor',
  KEY_AGENCY: 'Key-agency activity',
  SOLE_SOURCE: 'Sole-source / non-competitive',
  POLICY_TERM: 'Policy-relevant topic',
  BIG_CONSTRUCTION: 'Construction / capital ≥ $500K',
  ENV_HEALTH_HEARING: 'Environmental / health hearing',
  HUMAN_SERV_RENEWAL: 'Human-services renewal / extension',
  CONSULTING: 'Consulting / communications ≥ $100K',
};

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
  const category = notice.category_description || '';
  const allText = `${title} ${desc} ${type} ${category}`.toLowerCase();

  const make = (priority, code) => ({ priority, code, reason: REASON_LABELS[code], max_amount: maxAmount || undefined });

  if (EXECUTIVE_ORDER_RE.test(title)) {
    return make('notable', /emergency/i.test(title) ? 'EXEC_ORDER_EMERGENCY' : 'EXEC_ORDER');
  }
  if (section === 'Special Materials' && CEQR_RE.test(title)) return make('notable', 'CEQR');
  if (section === 'Special Materials' && CONCEPT_PAPER_RE.test(title)) return make('notable', 'CONCEPT_PAPER');
  if (section === 'Special Materials' && ROUTINE_SPECIAL_RE.test(title)) return null;
  if (section === 'Special Materials') return make('notable', 'SPECIAL_MATERIALS');

  if (maxAmount >= 1_000_000) return make('notable', 'BIG_CONTRACT');
  if (section === 'Agency Rules') return make('notable', 'AGENCY_RULE');
  if (section === 'Property Disposition') return make('notable', 'PROP_DISP');
  if (section === 'Court Notices') return make('notable', 'COURT');
  if (section === 'Contract Award Hearings') return make('notable', 'AWARD_HEARING');

  if (EMERGENCY_RE.test(allText)) return make('notable', 'EMERGENCY');
  if (SETTLEMENT_RE.test(allText)) return make('notable', 'SETTLEMENT');
  if (BOND_RE.test(allText)) return make('notable', 'BOND');
  if (ULURP_RE.test(allText) || LANDMARK_RE.test(allText)) return make('notable', 'LAND_USE');
  if (CONSENT_DECREE_RE.test(allText) || MONITOR_RE.test(allText)) return make('notable', 'OVERSIGHT');

  if (KEY_AGENCIES_RE.test(agency)) return make('notable', 'KEY_AGENCY');
  if (SOLE_SOURCE_RE.test(selection) || SOLE_SOURCE_RE.test(allText)) return make('notable', 'SOLE_SOURCE');
  if (POLICY_TERMS_RE.test(allText)) return make('notable', 'POLICY_TERM');

  if (maxAmount >= 500_000 && /construction|infrastructure|capital|renovation|repair/i.test(allText)) {
    return make('watching', 'BIG_CONSTRUCTION');
  }
  if (/hearing|meeting/i.test(type) && /environment|health|water|air quality|toxic|lead|asbestos|climate/i.test(allText)) {
    return make('watching', 'ENV_HEALTH_HEARING');
  }
  if (/extension|renewal|amendment/i.test(type) && /human services/i.test(category)) {
    return make('watching', 'HUMAN_SERV_RENEWAL');
  }
  if (/consult|lobbying|communications|public relations|advertising/i.test(allText) && maxAmount >= 100_000) {
    return make('watching', 'CONSULTING');
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

    // Only try fallback if we don't already have that date's data
    const fallbackPath = join(DATA_DIR, `${fallback}.json`);
    if (existsSync(fallbackPath)) {
      console.log(`${fallback}.json already exists and no new data for ${targetDate}. Nothing to do.`);
      process.exit(0);
    }

    raw = await fetchNotices(fallback);
    date = fallback;
  }

  if (raw.length === 0) {
    console.log('No City Record data found. Nothing to do.');
    process.exit(0);
  }

  console.log(`Found ${raw.length} notices for ${date}`);

  const outPath = join(DATA_DIR, `${date}.json`);

  // Process notices — separate Changes in Personnel into a summary
  const notices = [];
  const notable = [];
  const watching = [];
  const personnelByAction = {};
  const personnelByAgency = {};
  let personnelTotal = 0;

  for (const r of raw) {
    const cleaned = cleanRecord(r);
    const notice = extractNotice(cleaned);

    if (notice.section_name === 'Changes in Personnel') {
      personnelTotal += 1;
      const action = (notice.short_title || 'OTHER').toUpperCase();
      const agency = notice.agency_name || 'UNKNOWN';
      personnelByAction[action] = (personnelByAction[action] || 0) + 1;
      personnelByAgency[agency] = (personnelByAgency[agency] || 0) + 1;
      continue;
    }

    notices.push(notice);

    const flag = flagNotice(notice, cleaned);
    if (flag) {
      const flagged = { ...notice, flag_code: flag.code, flag_reason: flag.reason };
      if (flag.max_amount && flag.max_amount > parseAmount(notice.contract_amount)) {
        flagged.max_amount = flag.max_amount;
      }
      if (flag.priority === 'notable') notable.push(flagged);
      else watching.push(flagged);
    }
  }

  const personnel = personnelTotal > 0 ? {
    total: personnelTotal,
    by_action: personnelByAction,
    by_agency: Object.fromEntries(
      Object.entries(personnelByAgency).sort((a, b) => b[1] - a[1]).slice(0, 10)
    )
  } : null;

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
  if (personnel) dayData.personnel = personnel;
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
