#!/usr/bin/env node
// Adds a one-sentence plain-English line (`plain`) to each notice in the daily
// files, written by Claude Haiku 5.5 from the notice's own fields and nothing
// else. A line is thrown away, not shown, when it names a dollar figure that
// doesn't match the notice (see checkLine). Methodology: methodology.html#plain-english
//
// Usage:
//   node summarize-notices.mjs             fill missing lines in the newest 10 days (daily run)
//   node summarize-notices.mjs --batch     submit every missing notice as one Message Batch (half price)
//   node summarize-notices.mjs --collect   write a finished batch's lines into the daily files
//   node summarize-notices.mjs --fill      fill missing lines anywhere in the archive (capped)
//   node summarize-notices.mjs --pilot 12  print lines for a sample, write nothing
//
// Needs ANTHROPIC_API_KEY. Without it the daily run changes nothing and exits 0,
// so the digest still publishes.

import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import Anthropic from '@anthropic-ai/sdk';

const DIR = import.meta.dirname;
const DATA_DIR = join(DIR, 'data');
const BATCH_STATE = join(DATA_DIR, 'plain-batch.json');

const MODEL = 'claude-haiku-5-5';
const DAILY_DAYS = 10;
const DAILY_CAP = 400;   // a feed glitch can't turn into a big bill
const CONCURRENCY = 4;

const SYSTEM = `You write one plain-English sentence explaining a notice from The City Record, New York City's official journal of contracts, hearings and rules. Readers are New Yorkers and reporters who don't know procurement jargon.

Say who is doing what: the agency, the action (awarding, renewing, extending, seeking bids, holding a hearing, proposing or adopting a rule), the vendor if there is one, the dollar amount if there is one, the time period or deadline if one is given, and what the money or rule is for.

Rules:
- Use only facts stated in the notice. Do not guess, explain motives, add background or expand codes and abbreviations the notice doesn't spell out (a title code like "BK4" stays out unless the notice says what it means).
- No judgment words such as critical, important, major, only, just, already, controversial.
- One sentence of 35 words or fewer. No preamble, no quotation marks, no bullet.
- Name the agency exactly as the notice's Agency line gives it, and spell out any other acronym the notice spells out. Write New York City, not NYC.
- Money: $5.7 million, $198,000, $1.2 billion. Use the notice's contract amount when it has one.
- Dates in AP style: Oct. 8, 2026; July 1, 2023; March 2027.
- No serial comma.
- Selection methods, in plain words, only when the notice names one:
  Competitive Sealed Bids: the lowest qualified bid wins.
  Competitive Sealed Proposals or Request for Proposals: chosen from competing proposals.
  Pre-Qualified List: competition limited to vendors the city approved in advance.
  Negotiated Acquisition: negotiated with one or a few vendors instead of open competition.
  Sole Source: only one vendor was considered.
  Renewal: continues an existing contract for a new term.
  Emergency Purchase: bought under emergency rules that skip the usual competition.
  Intergovernmental Purchase: bought through a contract another government already holds.
  M/WBE Noncompetitive Small Purchase: a small purchase from a certified minority- or women-owned business without competition.
  Required/Authorized Source or Required Method: a vendor or method the law directs the city to use.
  BP/City Council Discretionary: money set aside for this group by the City Council or a borough president.
  Any other method: name it as written, or leave it out.
- For hearings and meetings, say who meets, about what, and when and where if given.
- If a stated contract period ended before the notice date, give the period as written and say nothing about it.
- If the notice gives too little to say more than its title, restate the title in plain words.
- Never say what the notice leaves out ("the notice does not list…", "no further details," "no vendor or amount given"). State only what it says.`;

// The City Record shortens most agency names ("Environmental Protection").
// Give the model the full name so it doesn't have to guess one.
const AGENCY_FULL = {
  'Youth and Community Development': 'the Department of Youth and Community Development',
  'Citywide Administrative Services': 'the Department of Citywide Administrative Services',
  'Dept. of Social Svcs/Human Resources Administration': 'the Human Resources Administration',
  'Human Resources Administration': 'the Human Resources Administration',
  'Health and Mental Hygiene': 'the Department of Health and Mental Hygiene',
  'Environmental Protection': 'the Department of Environmental Protection',
  'Transportation': 'the Department of Transportation',
  "Mayor's Office of Contract Services": "the Mayor's Office of Contract Services",
  'Homeless Services': 'the Department of Homeless Services',
  'Parks and Recreation': 'the Department of Parks and Recreation',
  'Design and Construction': 'the Department of Design and Construction',
  'Information Technology and Telecommunications': 'the Department of Information Technology and Telecommunications',
  'Aging': 'the Department for the Aging',
  'Office of the Mayor': 'the Office of the Mayor',
  'Housing Preservation and Development': 'the Department of Housing Preservation and Development',
  'Fire Department': 'the Fire Department',
  'Sanitation': 'the Department of Sanitation',
  'Housing Authority': 'the New York City Housing Authority',
  'Correction': 'the Department of Correction',
  'Police Department': 'the Police Department',
  'Small Business Services': 'the Department of Small Business Services',
  'Probation': 'the Department of Probation',
  'Finance': 'the Department of Finance',
  'School Construction Authority': 'the School Construction Authority',
  'Education': 'the Department of Education',
  'Consumer and Worker Protection': 'the Department of Consumer and Worker Protection',
  "Mayor's Office of Criminal Justice": "the Mayor's Office of Criminal Justice",
  'Comptroller': "the city comptroller's office",
  'City Planning': 'the Department of City Planning',
  'NYC Health + Hospitals': 'NYC Health + Hospitals',
  'Buildings': 'the Department of Buildings',
  'Economic Development Corporation': 'the Economic Development Corporation',
  'Chief Medical Examiner': 'the Office of Chief Medical Examiner',
  'Management and Budget': 'the Office of Management and Budget',
  'Emergency Management': 'New York City Emergency Management',
  'Administrative Trials and Hearings': 'the Office of Administrative Trials and Hearings',
  'Investigation': 'the Department of Investigation',
  'Cultural Affairs': 'the Department of Cultural Affairs',
  'City Record': 'The City Record',
  'Law Department': 'the Law Department',
  'Records and Information Services': 'the Department of Records and Information Services',
  "Veterans' Services": "the Department of Veterans' Services",
  'Environmental Remediation': 'the Office of Environmental Remediation',
  'Trust For Governors Island': 'the Trust for Governors Island',
};
const agencyFull = name => AGENCY_FULL[name] || name;

function htmlToText(html) {
  return (html || '')
    .replace(/<br\s*\/?>/gi, '\n').replace(/<\/p>/gi, '\n').replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;|&rsquo;|&lsquo;/g, "'").replace(/&[a-z]+;/g, ' ')
    .replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
}

function noticePrompt(n) {
  const field = (label, v) => (v ? `${label}: ${v}\n` : '');
  return 'Notice:\n'
    + field('Published', (n.start_date || '').slice(0, 10))
    + field('Agency', agencyFull(n.agency_name))
    + field('Section', n.section_name)
    + field('Notice type', n.type_of_notice_description)
    + field('Category', n.category_description)
    + field('Title', n.short_title)
    + field('Vendor', n.vendor_name)
    + field('Contract amount (dollars)', n.contract_amount)
    + field('Selection method', n.selection_method_description)
    + field('Response due', (n.due_date || '').slice(0, 10))
    + field('Event date', (n.event_date || '').slice(0, 10))
    + field('Description', htmlToText(n.description));
}

export function params(n) {
  return {
    model: MODEL,
    max_tokens: 2048,
    output_config: { effort: 'low' },
    system: SYSTEM,
    messages: [{ role: 'user', content: noticePrompt(n) }],
  };
}

// Every dollar figure in the line must match the contract amount or a figure
// in the notice's own text, within rounding (5%). Otherwise the line is dropped.
function dollarFigures(text) {
  const out = [];
  const re = /\$\s?(\d[\d,]*(?:\.\d+)?)(\s*(?:million|billion|thousand)\b)?/gi;
  let m;
  while ((m = re.exec(text))) {
    let v = parseFloat(m[1].replace(/,/g, ''));
    const unit = (m[2] || '').trim().toLowerCase();
    if (unit === 'thousand') v *= 1e3;
    if (unit === 'million') v *= 1e6;
    if (unit === 'billion') v *= 1e9;
    out.push(v);
  }
  return out;
}

// Lines that talk about what the notice leaves out say nothing useful.
const GAP_TALK = /(notice (does not|doesn't|did not|gives no|lists no|provides no|includes no|omit)|no (further|other|additional) (details?|information)|(with|but) no [^.]{0,80}\b(given|listed|provided|specified|stated)|not (listed|given|specified|provided|stated) in the notice|beyond (its|the) title|\bwait\b)/i;

export function checkLine(line, n) {
  if (!line) return 'empty';
  if (/\n/.test(line)) return 'more than one line';
  if (line.split(/\s+/).length > 60) return 'too long';
  if (GAP_TALK.test(line)) return 'comments on what the notice leaves out';
  const allowed = [parseFloat(n.contract_amount) || 0,
    ...dollarFigures(htmlToText(n.description) + ' ' + (n.short_title || ''))].filter(v => v > 0);
  for (const f of dollarFigures(line)) {
    if (!allowed.some(a => Math.abs(f - a) / a <= 0.05)) return `dollar figure $${f} not in notice`;
  }
  return null;
}

function textOf(message) {
  if (message.stop_reason !== 'end_turn') { console.warn(`  stop_reason=${message.stop_reason}`); return ''; }
  const block = message.content.find(b => b.type === 'text');
  return block ? block.text.trim().replace(/^["“]|["”]$/g, '') : '';
}

// --- Daily files ---------------------------------------------------------

function dayFiles() {
  return readdirSync(DATA_DIR).filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort();
}

const load = f => JSON.parse(readFileSync(join(DATA_DIR, f), 'utf8'));
const lists = d => [d.notices || [], d.notable || [], d.watching || []];

// request_id -> plain line, from every file that already has one
function knownLines(files) {
  const known = new Map();
  for (const f of files) {
    for (const list of lists(load(f))) {
      for (const n of list) if (n.plain) known.set(n.request_id, n.plain);
    }
  }
  return known;
}

// Write lines into every occurrence of each request_id in the given files.
function applyLines(files, lines) {
  let changedFiles = 0;
  for (const f of files) {
    const d = load(f);
    let changed = false;
    for (const list of lists(d)) {
      for (const n of list) {
        const line = lines.get(n.request_id);
        if (line && n.plain !== line) { n.plain = line; changed = true; }
      }
    }
    if (changed) { writeFileSync(join(DATA_DIR, f), JSON.stringify(d, null, 2)); changedFiles++; }
  }
  return changedFiles;
}

// Unique notices lacking a line, keyed by request_id.
function missing(files, known) {
  const todo = new Map();
  for (const f of files) {
    for (const n of load(f).notices || []) {
      if (!n.plain && !known.has(n.request_id) && !todo.has(n.request_id)) todo.set(n.request_id, n);
    }
  }
  return todo;
}

// --- Modes ---------------------------------------------------------------

async function daily(client, everything = false) {
  const all = dayFiles();
  const recent = everything ? all : all.slice(-DAILY_DAYS);
  const known = knownLines(all);
  const todo = [...missing(recent, known).values()].slice(0, DAILY_CAP);
  const lines = new Map(known);
  let dropped = 0, inTok = 0, outTok = 0;
  const queue = [...todo];
  async function worker() {
    while (queue.length) {
      const n = queue.shift();
      try {
        const msg = await client.messages.create(params(n));
        inTok += msg.usage.input_tokens; outTok += msg.usage.output_tokens;
        const line = textOf(msg);
        const why = checkLine(line, n);
        if (why) { dropped++; console.warn(`  dropped ${n.request_id}: ${why}`); continue; }
        lines.set(n.request_id, line);
      } catch (e) {
        console.warn(`  failed ${n.request_id}: ${e.message}`);
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  const changed = applyLines(recent, lines);
  const cost = (inTok * 0.10 + outTok * 0.50) / 1e6;
  console.log(`Plain-English lines: ${todo.length - dropped} written, ${dropped} dropped, `
    + `${changed} files updated, ~$${cost.toFixed(4)}`);
}

async function submitBatch(client) {
  if (existsSync(BATCH_STATE) && JSON.parse(readFileSync(BATCH_STATE, 'utf8')).status !== 'collected') {
    console.error('A batch is already pending; run --collect first.');
    process.exit(1);
  }
  const all = dayFiles();
  const todo = missing(all, knownLines(all));
  if (!todo.size) { console.log('Nothing to do.'); return; }
  const requests = [...todo.values()].map(n => ({ custom_id: n.request_id, params: params(n) }));
  const batch = await client.messages.batches.create({ requests });
  writeFileSync(BATCH_STATE, JSON.stringify({
    batch_id: batch.id, count: requests.length, submitted_at: new Date().toISOString(), status: 'submitted',
  }, null, 1) + '\n');
  console.log(`Submitted batch ${batch.id} with ${requests.length} notices.`);
}

async function collect(client) {
  const state = JSON.parse(readFileSync(BATCH_STATE, 'utf8'));
  const batch = await client.messages.batches.retrieve(state.batch_id);
  if (batch.processing_status !== 'ended') {
    console.log(`Batch ${batch.id} still ${batch.processing_status}:`, batch.request_counts);
    process.exit(2);
  }
  const all = dayFiles();
  const byId = new Map();
  for (const f of all) for (const n of load(f).notices || []) byId.set(n.request_id, n);
  const lines = new Map();
  const dropped = [];
  let failed = 0, inTok = 0, outTok = 0;
  for await (const r of await client.messages.batches.results(batch.id)) {
    if (r.result.type !== 'succeeded') { failed++; continue; }
    const msg = r.result.message;
    inTok += msg.usage.input_tokens; outTok += msg.usage.output_tokens;
    const n = byId.get(r.custom_id);
    const line = textOf(msg);
    const why = n ? checkLine(line, n) : 'notice not found';
    if (why) { dropped.push({ request_id: r.custom_id, why, line }); continue; }
    lines.set(r.custom_id, line);
  }
  const changed = applyLines(all, lines);
  const cost = (inTok * 0.10 + outTok * 0.50) / 2 / 1e6;
  Object.assign(state, {
    status: 'collected', written: lines.size, dropped: dropped.length, failed,
    cost_usd: Number(cost.toFixed(4)), dropped_detail: dropped,
  });
  writeFileSync(BATCH_STATE, JSON.stringify(state, null, 1) + '\n');
  console.log(`Collected: ${lines.size} written, ${dropped.length} dropped, ${failed} failed, `
    + `${changed} files updated, $${cost.toFixed(2)}`);
}

async function pilot(client, count) {
  const all = dayFiles();
  const pool = all.slice(-40).flatMap(f => load(f).notices || []);
  const seen = new Set(), sample = [];
  // one per section/method/type mix, then fill
  for (const n of pool) {
    const key = `${n.section_name}|${n.selection_method_description}|${n.type_of_notice_description}`;
    if (!seen.has(key) && sample.length < count) { seen.add(key); sample.push(n); }
  }
  let inTok = 0, outTok = 0;
  for (const n of sample) {
    const msg = await client.messages.create(params(n));
    inTok += msg.usage.input_tokens; outTok += msg.usage.output_tokens;
    const line = textOf(msg);
    console.log(`\n[${n.request_id}] ${n.section_name} | ${n.type_of_notice_description} | ${n.selection_method_description || '-'} | ${n.short_title}`);
    console.log(`  amount=${n.contract_amount || '-'} vendor=${n.vendor_name || '-'} desc=${htmlToText(n.description).slice(0, 160)}`);
    console.log(`  -> ${line}`);
    const why = checkLine(line, n);
    if (why) console.log(`  !! DROPPED: ${why}`);
  }
  console.log(`\npilot: ${sample.length} notices, ${inTok} in / ${outTok} out tokens, $${((inTok * 0.10 + outTok * 0.50) / 1e6).toFixed(4)}`);
}

async function main() {
  const mode = process.argv[2] || 'daily';
  if (!process.env.ANTHROPIC_API_KEY) {
    console.log('ANTHROPIC_API_KEY not set; skipping plain-English lines.');
    process.exit(mode === 'daily' ? 0 : 1);
  }
  const client = new Anthropic();
  if (mode === '--pilot') await pilot(client, parseInt(process.argv[3] || '12', 10));
  else if (mode === '--batch') await submitBatch(client);
  else if (mode === '--fill') await daily(client, true);   // retry gaps anywhere in the archive
  else if (mode === '--collect') await collect(client);
  else await daily(client);
}

if (process.argv[1] === import.meta.filename) {
  main().catch(e => {
    // Never block the digest over a summary problem.
    console.error('summarize-notices failed:', e.message);
    process.exit(process.argv[2] ? 1 : 0);
  });
}
