// performance.mjs — the whole OpenRecords log, summarized.
//
// scrape.mjs tracks recent requests in detail: titles, determinations, the text
// agencies send back. That is a slice — roughly the last two years — because the
// detail pages have to be scraped one at a time.
//
// This is the other layer: every FOIL request ever filed through the portal
// (kegn-anvq on NYC Open Data, 636k rows back to 2006), with no detail but with
// the four dates that matter — filed, due, closed, and today. It answers the
// questions the sampled layer cannot: how big is the backlog, which agencies
// are sitting on it, how long each one really takes.
//
// Writes data/performance.json. Run: node performance.mjs

import { writeFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, "data");
const OUT = join(DATA_DIR, "performance.json");

const DATASET = "kegn-anvq";
const ENDPOINT = `https://data.cityofnewyork.us/resource/${DATASET}.json`;
const PAGE = 50000;
const MIN_ROWS = 500000; // a short pull is a failure, not a smaller backlog

const OPEN_STATUSES = new Set(["Overdue", "In Progress", "Due Soon", "Open"]);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchAll() {
  const rows = [];
  for (let offset = 0; ; offset += PAGE) {
    const qs = new URLSearchParams({
      $select: "agency_name,request_created_date,request_due_date,request_close_date,request_status,submission_method",
      $order: "request_id",
      $limit: String(PAGE),
      $offset: String(offset),
    });
    let page = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        // A 403 from Socrata here is anonymous throttling, not a permissions wall.
        const res = await fetch(`${ENDPOINT}?${qs}`, { headers: { "User-Agent": "nyc-foil-tracker/1.0" } });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        page = await res.json();
        break;
      } catch (err) {
        console.error(`  retry ${attempt + 1} at offset ${offset} (${err.message})`);
        await sleep(4000 * (attempt + 1));
      }
    }
    if (!page) throw new Error(`FOIL log fetch failed at offset ${offset}`);
    rows.push(...page);
    console.error(`  ${rows.length.toLocaleString()} rows`);
    if (page.length < PAGE) break;
  }
  if (rows.length < MIN_ROWS) {
    throw new Error(`only ${rows.length} rows — the log has had 600k+ since 2024; refusing to publish a short pull`);
  }
  return rows;
}

const day = (v) => {
  if (!v) return null;
  const d = new Date(v.replace("Z", ""));
  return Number.isNaN(d.getTime()) ? null : d;
};
const days = (a, b) => Math.round((a - b) / 86400000);
const iso = (d) => (d ? d.toISOString().slice(0, 10) : null);

function pct(sorted, p) {
  if (!sorted.length) return null;
  const k = Math.min(sorted.length - 1, Math.round((p / 100) * (sorted.length - 1)));
  return sorted[k];
}

function summarize(a) {
  const closed = a.closedDays.slice().sort((x, y) => x - y);
  const judged = a.onTime + a.late;
  return {
    total: a.total,
    filed_12mo: a.recent,
    open: a.open,
    past_due: a.pastDue,
    closed_12mo: a.closedRecent,
    median_days: pct(closed, 50),
    p75_days: pct(closed, 75),
    p90_days: pct(closed, 90),
    on_time_pct: judged ? Math.round((1000 * a.onTime) / judged) / 10 : null,
    median_due_offset: pct(a.dueOffsets.slice().sort((x, y) => x - y), 50),
  };
}

const blank = () => ({
  total: 0, recent: 0, open: 0, pastDue: 0,
  closedDays: [], closedRecent: 0, onTime: 0, late: 0,
  dueOffsets: [], oldestPastDue: null,
});

async function main() {
  console.error("Fetching the OpenRecords FOIL log…");
  const rows = await fetchAll();

  const today = new Date();
  const yearAgo = new Date(today.getTime() - 365 * 86400000);
  const start2024 = new Date("2024-01-01");

  const per = new Map();
  const city = blank();
  city.pastDueSince2024 = 0;
  const filedByYear = new Map();
  const pastDueByYear = new Map();
  let first = null, last = null;

  for (const r of rows) {
    const agency = (r.agency_name || "").trim();
    if (!agency) continue;
    const status = (r.request_status || "").trim();
    const created = day(r.request_created_date);
    const due = day(r.request_due_date);
    const closed = day(r.request_close_date);
    if (!per.has(agency)) per.set(agency, blank());
    const a = per.get(agency);

    a.total++; city.total++;
    if (created) {
      if (!first || created < first) first = created;
      if (!last || created > last) last = created;
      const y = created.getFullYear();
      filedByYear.set(y, (filedByYear.get(y) || 0) + 1);
      if (created >= yearAgo) { a.recent++; city.recent++; }
      if (due) { a.dueOffsets.push(days(due, created)); city.dueOffsets.push(days(due, created)); }
    }

    const stillOpen = OPEN_STATUSES.has(status) && !closed;
    if (stillOpen) {
      a.open++; city.open++;
      if (due && due < today) {
        a.pastDue++; city.pastDue++;
        if (created) {
          const y = created.getFullYear();
          pastDueByYear.set(y, (pastDueByYear.get(y) || 0) + 1);
          if (created >= start2024) city.pastDueSince2024++;
          if (!a.oldestPastDue || created < a.oldestPastDue) a.oldestPastDue = created;
        }
      }
    }

    // Response time is measured only on requests an agency actually closed in the
    // last year. Requests still open are counted in the backlog instead: averaging
    // an unfinished request as if it were finished would flatter a slow agency.
    if (closed && closed >= yearAgo && created) {
      const d = days(closed, created);
      if (d >= 0 && d <= 4000) {
        a.closedDays.push(d); city.closedDays.push(d);
        a.closedRecent++; city.closedRecent++;
        if (due) {
          if (closed <= due) { a.onTime++; city.onTime++; }
          else { a.late++; city.late++; }
        }
      }
    }
  }

  const agencies = [...per.entries()]
    .map(([name, a]) => ({ agency: name, ...summarize(a), oldest_past_due: iso(a.oldestPastDue) }))
    .sort((x, y) => y.total - x.total);

  const byId = {};
  for (const a of agencies) byId[a.agency] = a;

  const payload = {
    generated: iso(today),
    source: {
      dataset: DATASET,
      url: `https://data.cityofnewyork.us/d/${DATASET}`,
      name: "OpenRecords FOIL Requests",
      publisher: "Department of Records and Information Services",
      rows: rows.length,
      first_request: iso(first),
      last_request: iso(last),
      agencies: agencies.length,
    },
    citywide: {
      ...summarize(city),
      past_due_since_2024: city.pastDueSince2024,
      past_due_by_year: [...pastDueByYear.entries()].filter(([y]) => y >= 2010)
        .sort((a, b) => a[0] - b[0]).map(([year, n]) => ({ year, n })),
      filed_by_year: [...filedByYear.entries()].filter(([y]) => y >= 2010 && y <= today.getFullYear())
        .sort((a, b) => a[0] - b[0]).map(([year, n]) => ({ year, n })),
      worst: agencies.slice().sort((a, b) => b.past_due - a.past_due)
        .filter((a) => a.past_due).slice(0, 6)
        .map((a) => ({ agency: a.agency, past_due: a.past_due })),
    },
    agencies,
    byAgency: byId,
  };

  mkdirSync(DATA_DIR, { recursive: true });
  writeFileSync(OUT, JSON.stringify(payload));
  const c = payload.citywide;
  console.error(`wrote ${OUT}`);
  console.error(`  ${c.total.toLocaleString()} requests · ${c.past_due.toLocaleString()} open past due · ` +
    `median close ${c.median_days} days · ${c.on_time_pct}% met the agency's own date`);
}

main().catch((err) => { console.error(err.message); process.exit(1); });
