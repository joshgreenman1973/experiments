import { chromium } from "playwright";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, "data");
const OUTPUT_FILE = join(DATA_DIR, "requests.json");

const BACKFILL = process.argv.includes("--backfill");
const BACKFILL_FULL = process.argv.includes("--backfill-full"); // windowed backfill for all of 2026
const BATCH_SIZE = 50;
const LIST_PAGES = (BACKFILL || BACKFILL_FULL) ? 999 : 4;
const DETAIL_CONCURRENCY = 5; // parallel detail page fetches
const DETAIL_LIMIT = (BACKFILL || BACKFILL_FULL) ? 500 : 30;
// Wall-clock ceiling for the (slow, sequential) detail-page scrape. When NYC
// OpenRecords' Akamai edge is slow in CI, each detail page can take ~30s, so an
// unbounded 500-page pass ran for 4.5h and the job never committed. Stop cleanly
// after this many ms and write whatever progress we have. Override via env.
const DETAIL_TIME_BUDGET_MS =
  parseInt(process.env.DETAIL_TIME_BUDGET_MS || "0", 10) ||
  ((BACKFILL || BACKFILL_FULL) ? 25 * 60 * 1000 : 8 * 60 * 1000);
const DATE_FROM = (BACKFILL || BACKFILL_FULL) ? "01/01/2026" : "";

// NYC Open Data / Socrata: "OpenRecords FOIL Requests" dataset.
// This is the OFFICIAL published dataset (DORIS) and is not behind Akamai —
// replaces the fragile scrape of a860-openrecords.nyc.gov/request/view_all.
// Titles and response/determination messages are NOT in Socrata, so we still
// fall back to scraping individual detail pages for those (best-effort).
const SOCRATA_ENDPOINT = "https://data.cityofnewyork.us/resource/kegn-anvq.json";
const SOCRATA_PAGE_SIZE = 50000; // SODA max per request

if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true });

async function launchBrowser() {
  // Use installed Chrome locally (bypasses Akamai WAF better);
  // in CI, fall back to Playwright chromium
  const useChrome = !process.env.CI;
  const browser = await chromium.launch({
    ...(useChrome ? { channel: "chrome" } : {}),
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
    ],
  });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    locale: "en-US",
    timezoneId: "America/New_York",
    viewport: { width: 1920, height: 1080 },
  });
  // Hide webdriver flag
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    // Override permissions query
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
      params.name === "notifications"
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(params);
  });
  return { browser, context };
}

// Generate weekly date windows from start to today
function generateWeeklyWindows(startDate) {
  const windows = [];
  const start = new Date(startDate);
  const today = new Date();
  let cursor = new Date(start);
  while (cursor < today) {
    const windowEnd = new Date(cursor);
    windowEnd.setDate(windowEnd.getDate() + 6);
    const end = windowEnd > today ? today : windowEnd;
    const fmt = (d) =>
      `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}/${d.getFullYear()}`;
    windows.push({ from: fmt(cursor), to: fmt(end) });
    cursor.setDate(cursor.getDate() + 7);
  }
  return windows;
}

// Scrape one date window, paginating until all results fetched
async function scrapeWindow(page, dateFrom, dateTo) {
  const requests = [];
  let start = 0;
  let total = 0;
  let consecutiveErrors = 0;

  for (let i = 0; i < 999; i++) {
    let data;
    try {
      data = await page.evaluate(
        async ({ start, size, dateFrom, dateTo }) => {
          const url = `/search/requests?query=&title=on&agency_request_summary=on&open=on&closed=on&date_rec_from=${dateFrom}&date_rec_to=${dateTo}&agency_ein=&size=${size}&tz_name=America/New_York&start=${start}&sort_date_submitted=DESC`;
          const resp = await fetch(url, {
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              Accept: "application/json, text/javascript, */*; q=0.01",
            },
          });
          if (!resp.ok) return { requests: [], total: 0, error: `HTTP ${resp.status}` };
          const text = await resp.text();
          try {
            const json = JSON.parse(text);
            const parser = new DOMParser();
            const doc = parser.parseFromString("<table>" + json.results + "</table>", "text/html");
            const rows = doc.querySelectorAll("tr");
            const reqs = Array.from(rows)
              .map((row) => {
                const tds = row.querySelectorAll("td");
                if (tds.length < 5) return null;
                const link = tds[3]?.querySelector("a");
                return {
                  status: tds[0]?.textContent?.trim(),
                  foilId: tds[1]?.textContent?.trim(),
                  dateSubmitted: tds[2]?.querySelector(".flask-moment")?.dataset?.timestamp || "",
                  title: link?.textContent?.trim() || "",
                  url: link?.getAttribute("href") || "",
                  agency: tds[4]?.textContent?.trim(),
                  dateDue: tds[5]?.querySelector(".flask-moment")?.dataset?.timestamp || "",
                };
              })
              .filter(Boolean);
            return { requests: reqs, total: json.total };
          } catch {
            return { requests: [], total: 0, error: "JSON parse failed" };
          }
        },
        { start, size: BATCH_SIZE, dateFrom, dateTo }
      );
    } catch (err) {
      data = { requests: [], total: 0, error: err.message };
    }

    if (data.error) {
      consecutiveErrors++;
      console.error(`      Error: ${data.error} (${consecutiveErrors} consecutive)`);
      if (consecutiveErrors >= 3) break;
      console.log("      Waiting 10s before retry...");
      await page.waitForTimeout(10000);
      await page.goto("https://a860-openrecords.nyc.gov/request/view_all", {
        waitUntil: "domcontentloaded", timeout: 60000,
      });
      await page.waitForTimeout(5000);
      continue;
    }

    consecutiveErrors = 0;
    requests.push(...data.requests);
    total = data.total || total;

    if (data.requests.length < BATCH_SIZE) break;
    start += BATCH_SIZE;
    await page.waitForTimeout(1500);
  }

  return { requests, total };
}

// Step 1 (new): Pull the list from the official NYC Open Data Socrata dataset.
// Returns the same shape as the old scrapeList so downstream code is unchanged.
async function fetchListFromSocrata({ fullBackfill = false, limitRequests = 200 } = {}) {
  console.log(`Fetching list from Socrata (${SOCRATA_ENDPOINT})...`);

  const results = [];
  let offset = 0;
  // Non-backfill: just grab the most recent N, ordered newest first.
  // Backfill: page through everything from 2026-01-01 forward.
  const whereClause = (BACKFILL || fullBackfill)
    ? `?$where=request_submitted_date >= '2026-01-01T00:00:00'&$order=request_submitted_date DESC`
    : `?$order=request_submitted_date DESC`;

  const maxToFetch = (BACKFILL || fullBackfill) ? Infinity : limitRequests;

  while (results.length < maxToFetch) {
    const pageLimit = Math.min(SOCRATA_PAGE_SIZE, maxToFetch - results.length);
    const url = `${SOCRATA_ENDPOINT}${whereClause}&$limit=${pageLimit}&$offset=${offset}`;
    console.log(`  GET offset=${offset} limit=${pageLimit}`);
    const resp = await fetch(url, {
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) {
      throw new Error(`Socrata HTTP ${resp.status}: ${await resp.text().then((t) => t.slice(0, 200))}`);
    }
    const rows = await resp.json();
    if (rows.length === 0) break;
    results.push(...rows);
    if (rows.length < pageLimit) break;
    offset += pageLimit;
  }

  // Try to get the overall dataset size for display
  let totalInSystem = 0;
  try {
    const metaResp = await fetch(
      `${SOCRATA_ENDPOINT}?$select=count(*) as c`,
      { headers: { Accept: "application/json" } }
    );
    if (metaResp.ok) {
      const metaJson = await metaResp.json();
      totalInSystem = parseInt(metaJson[0]?.c || "0", 10) || 0;
    }
  } catch {}

  console.log(`  Got ${results.length} rows from Socrata (total in system: ${totalInSystem || "?"})`);

  // Map Socrata row → existing internal shape.
  // Socrata fields: request_id, agency_name, request_submitted_date,
  //   request_created_date, request_due_date, request_close_date,
  //   request_status, submission_method.
  const mapped = results.map((r) => ({
    status: r.request_status || "",
    foilId: r.request_id || "",
    dateSubmitted: r.request_submitted_date || r.request_created_date || "",
    // Socrata has no title; detail scrape fills this in
    title: "* Under Review",
    url: r.request_id ? `https://a860-openrecords.nyc.gov/request/view/${r.request_id}` : "",
    agency: r.agency_name || "",
    dateDue: r.request_due_date || "",
    dateClosed: r.request_close_date || "",
    submissionMethod: r.submission_method || "",
    isUnderReview: true, // until detail scrape fills title
  }));

  return {
    totalInSystem: totalInSystem || "597,000+",
    requests: mapped,
  };
}

// Step 1 (legacy): Scrape the search results list via Playwright — kept as fallback.
async function scrapeList(page) {
  console.log("Navigating to OpenRecords search...");

  // The site uses Akamai WAF — may need to wait for JS challenge
  for (let attempt = 1; attempt <= 3; attempt++) {
    console.log(`  Load attempt ${attempt}...`);
    await page.goto("https://a860-openrecords.nyc.gov/request/view_all", {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });

    // Wait for potential bot-check challenge to resolve
    await page.waitForTimeout(5000);

    try {
      await page.waitForSelector("table tr td", { timeout: 30000 });
      console.log("  Page loaded successfully.");
      break;
    } catch {
      if (attempt === 3) {
        const title = await page.title();
        const url = page.url();
        console.error(`  Failed after 3 attempts. Page title: "${title}", URL: ${url}`);
        const bodyText = await page.evaluate(() => document.body?.innerText?.substring(0, 500));
        console.error(`  Page content: ${bodyText}`);
        // NYC OpenRecords intermittently blocks scrapers at the Akamai edge
        // (Access Denied). That's a transient upstream issue, not a bug in
        // this workflow — exit cleanly so the scheduled run doesn't light
        // up the repo with a red X. Next week's run will try again.
        if (/access denied/i.test(title) || /access denied/i.test(bodyText || "")) {
          console.warn("::notice::Upstream Access Denied from NYC OpenRecords; skipping this run.");
          if (process.env.GITHUB_OUTPUT) {
            const fs = await import("node:fs");
            fs.appendFileSync(process.env.GITHUB_OUTPUT, "skipped=true\n");
          }
          process.exit(0);
        }
        throw new Error("Could not load OpenRecords search page after 3 attempts");
      }
      console.log("  Table not found, retrying...");
      await page.waitForTimeout(3000);
    }
  }

  const allRequests = [];
  let start = 0;
  let lastTotal = 0;

  const maxPages = BACKFILL ? 999 : LIST_PAGES;
  let consecutiveErrors = 0;
  for (let i = 0; i < maxPages; i++) {
    console.log(`  Fetching batch ${i + 1}${BACKFILL ? "" : `/${maxPages}`} (start=${start})...`);

    let data;
    try {
      data = await page.evaluate(
        async ({ start, size, dateFrom }) => {
          const url = `/search/requests?query=&title=on&agency_request_summary=on&open=on&closed=on&date_rec_from=${dateFrom}&date_rec_to=&agency_ein=&size=${size}&tz_name=America/New_York&start=${start}&sort_date_submitted=DESC`;
          const resp = await fetch(url, {
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              Accept: "application/json, text/javascript, */*; q=0.01",
            },
          });
          if (!resp.ok) return { requests: [], total: 0, error: `HTTP ${resp.status}` };
          const text = await resp.text();
          try {
            const json = JSON.parse(text);
            const parser = new DOMParser();
            const doc = parser.parseFromString(
              "<table>" + json.results + "</table>",
              "text/html"
            );
            const rows = doc.querySelectorAll("tr");
            const requests = Array.from(rows)
              .map((row) => {
                const tds = row.querySelectorAll("td");
                if (tds.length < 5) return null;
                const link = tds[3]?.querySelector("a");
                return {
                  status: tds[0]?.textContent?.trim(),
                  foilId: tds[1]?.textContent?.trim(),
                  dateSubmitted:
                    tds[2]?.querySelector(".flask-moment")?.dataset?.timestamp ||
                    "",
                  title: link?.textContent?.trim() || "",
                  url: link?.getAttribute("href") || "",
                  agency: tds[4]?.textContent?.trim(),
                  dateDue:
                    tds[5]?.querySelector(".flask-moment")?.dataset?.timestamp ||
                    "",
                };
              })
              .filter(Boolean);
            return { requests, total: json.total };
          } catch {
            return { requests: [], total: 0, error: "JSON parse failed" };
          }
        },
        { start, size: BATCH_SIZE, dateFrom: DATE_FROM }
      );
    } catch (err) {
      console.error(`    Batch failed: ${err.message}`);
      data = { requests: [], total: 0, error: err.message };
    }

    if (data.error) {
      consecutiveErrors++;
      console.error(`    Error: ${data.error} (${consecutiveErrors} consecutive)`);
      if (consecutiveErrors >= 3) {
        console.log(`    Stopping after ${consecutiveErrors} consecutive errors. Got ${allRequests.length} requests so far.`);
        break;
      }
      // Wait longer and retry — WAF challenge may need to resolve
      console.log("    Waiting 10s before retry...");
      await page.waitForTimeout(10000);
      // Reload the page to reset WAF state
      await page.goto("https://a860-openrecords.nyc.gov/request/view_all", {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      await page.waitForTimeout(5000);
      continue; // retry same offset
    }

    consecutiveErrors = 0;
    allRequests.push(...data.requests);
    lastTotal = data.total || lastTotal;
    console.log(`    Got ${data.requests.length} (total in system: ${data.total})`);

    if (data.requests.length < BATCH_SIZE) break;
    start += BATCH_SIZE;
    // Slower pace during backfill to avoid WAF
    await page.waitForTimeout(BACKFILL ? 1500 : 800);
  }

  return {
    totalInSystem: lastTotal || 0,
    requests: allRequests.map((r) => ({
      ...r,
      url: r.url ? `https://a860-openrecords.nyc.gov${r.url}` : "",
      isUnderReview: r.title === "* Under Review",
    })),
  };
}

// Step 2: Scrape individual detail pages for responses/determinations
async function scrapeDetail(page, foilId) {
  const url = `https://a860-openrecords.nyc.gov/request/view/${foilId}`;
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });

    // Responses load via AJAX. Wait until the "Loading responses..." placeholder
    // is gone (or 15s elapse) instead of a fixed sleep — slow loads were the main
    // reason responses came back empty.
    await page
      .waitForFunction(
        () => {
          const t = document.body.innerText;
          return /Responses/.test(t) && !/Loading responses\.\.\./.test(t);
        },
        { timeout: 15000 }
      )
      .catch(() => {});
    await page.waitForTimeout(1500);

    const detail = await page.evaluate(() => {
      const bodyText = document.body.innerText;
      const foilStart = bodyText.indexOf("FOIL-");
      if (foilStart === -1) return null;

      const content = bodyText.substring(foilStart, foilStart + 5000);

      // Parse title
      const titleMatch = content.match(/Title:\s*\n\s*(.+)/);
      const title = titleMatch ? titleMatch[1].trim() : "";

      // Parse responses section
      const responsesStart = content.indexOf("Responses");
      const footerStart = content.indexOf("Directory of City Agencies");
      const responsesText =
        responsesStart > -1
          ? content.substring(
              responsesStart,
              footerStart > -1 ? footerStart : undefined
            )
          : "";

      // Parse individual responses
      // They follow the pattern: number\nTYPE\nmessage\ndate
      const responses = [];
      const responseBlocks = responsesText.split(/\n(?=\d+\n[A-Z])/);
      for (const block of responseBlocks) {
        const lines = block.trim().split("\n").map((l) => l.trim()).filter(Boolean);
        if (lines.length < 2) continue;
        // Check if first line is a number
        const num = parseInt(lines[0]);
        if (isNaN(num)) continue;
        const type = lines[1] || "";
        // Everything between type and the date line is the message
        // Date line matches pattern like "Monday, 01/26/2024 at 8:53 AM"
        const datePattern = /^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\d{2}\/\d{2}\/\d{4}\s+at\s+\d{1,2}:\d{2}\s+[AP]M$/;
        let message = "";
        let dateStr = "";
        for (let i = 2; i < lines.length; i++) {
          if (datePattern.test(lines[i])) {
            dateStr = lines[i];
          } else {
            message += (message ? " " : "") + lines[i];
          }
        }
        responses.push({ number: num, type, message, date: dateStr });
      }

      // The full agency letter for each response lives in a hidden modal
      // (#response-modal-<id>). Modals are in the same newest-first order as the
      // numbered response rows, so zip them positionally to recover the complete
      // letter text the response list truncates or omits.
      const modalBodies = [...document.querySelectorAll("[id^='response-modal-']")]
        .map((m) => {
          const body = m.querySelector(".modal-body") || m;
          return (body.innerText || "").trim();
        });
      responses.forEach((r, idx) => {
        const full = modalBodies[idx];
        if (full && full.length > (r.message || "").length) r.message = full;
        if (full) r.letter = full;
      });

      // Expected completion date the agency promised in its acknowledgment
      // (distinct from the statutory due date already tracked).
      let expectedCompletionDate = "";
      for (const b of modalBodies) {
        const m = b.match(/Expected date of completion:\s*(.+)/i);
        if (m) { expectedCompletionDate = m[1].trim(); break; }
      }

      return { title, responses, expectedCompletionDate };
    });

    return detail;
  } catch (err) {
    console.error(`  Failed to scrape ${foilId}: ${err.message}`);
    return null;
  }
}

// Merge a scraped detail payload into an existing entry: full action timeline,
// expected-completion date, determination (incl. no-records/referral), response
// time. Shared by the live scraper and the one-off backfill.
function applyDetail(entry, detail) {
  if (detail.title && detail.title !== "* Under Review") {
    entry.title = detail.title;
  }
  entry.responses = detail.responses;
  entry.detailScraped = true;
  if (detail.expectedCompletionDate) {
    entry.expectedCompletionDate = detail.expectedCompletionDate;
  }

  // Full ordered action timeline (oldest -> newest) of everything the agency
  // did: acknowledgment, extension(s), closing/determination, with full letters.
  // OpenRecords numbers responses newest-first (#1 = most recent), so sort by
  // number descending to get oldest -> newest chronological order.
  entry.timeline = [...detail.responses]
    .sort((a, b) => (b.number || 0) - (a.number || 0))
    .map((r) => ({ type: r.type, date: r.date, message: r.message || "" }));

  // Derive determination from responses
  const closing = detail.responses.find((r) => r.type === "CLOSING");
  const denial = detail.responses.find((r) => r.type === "DENIAL");
  const partialDenial = detail.responses.find((r) => r.type.includes("PARTIAL"));
  if (denial) {
    entry.determination = "Denied";
    entry.determinationMessage = denial.message;
    entry.determinationDate = denial.date;
  } else if (partialDenial) {
    entry.determination = "Partially Denied";
    entry.determinationMessage = partialDenial.message;
    entry.determinationDate = partialDenial.date;
  } else if (closing) {
    // A "CLOSING" can mean the records were produced OR that the agency had no
    // responsive records and is referring the requester elsewhere. Distinguish
    // them from the letter text so "Fulfilled" stays accurate.
    const msg = closing.message || "";
    const noRecords =
      /does not (?:have|maintain) the records|no records|direct your request to|not the (?:correct|appropriate) agency/i.test(
        msg
      );
    entry.determination = noRecords ? "No responsive records" : "Fulfilled";
    entry.determinationMessage = msg;
    entry.determinationDate = closing.date;
    // Capture a referral target when the agency names one.
    const ref = msg.match(/direct your request to (?:the )?([A-Z][^.,;]{3,60})/);
    entry.referralAgency = ref ? ref[1].trim() : noRecords ? "Unspecified" : "";
  }

  // Calculate response time
  const lastResp = detail.responses[0]; // responses are in reverse chronological
  if (entry.dateSubmitted && lastResp?.date) {
    try {
      const parseDate = (d) => {
        const match = d.match(
          /(\d{2})\/(\d{2})\/(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s+(AM|PM)/
        );
        if (!match) return null;
        let [, mm, dd, yyyy, hh, min, ampm] = match;
        hh = parseInt(hh);
        if (ampm === "PM" && hh !== 12) hh += 12;
        if (ampm === "AM" && hh === 12) hh = 0;
        return new Date(`${yyyy}-${mm}-${dd}T${String(hh).padStart(2, "0")}:${min}:00`);
      };
      const submitted = new Date(entry.dateSubmitted);
      const responded = parseDate(lastResp.date);
      if (submitted && responded) {
        entry.responseTimeDays = Math.round(
          (responded - submitted) / (1000 * 60 * 60 * 24)
        );
      }
    } catch {}
  }
  return entry;
}

async function main() {
  console.log("=== NYC FOIL Tracker Scraper ===\n");

  // Load existing data to merge
  let existing = { requests: [] };
  if (existsSync(OUTPUT_FILE)) {
    try {
      existing = JSON.parse(readFileSync(OUTPUT_FILE, "utf-8"));
      console.log(`Loaded ${existing.requests.length} existing requests.\n`);
    } catch {
      console.log("Could not parse existing data, starting fresh.\n");
    }
  }
  const existingMap = new Map(existing.requests.map((r) => [r.foilId, r]));

  // Step 1: Pull list from Socrata (no browser, no Akamai)
  let listData;
  try {
    listData = await fetchListFromSocrata({ fullBackfill: BACKFILL_FULL });
  } catch (err) {
    console.error("::error::Socrata list fetch failed:", err.message);
    process.exit(1);
  }

  console.log(`\nFetched ${listData.requests.length} requests from Socrata.\n`);

  // Merge list data
  for (const r of listData.requests) {
    const prev = existingMap.get(r.foilId);
    if (prev) {
      // Update status/dates but keep detail data
      prev.status = r.status;
      prev.dateDue = r.dateDue;
      if (!r.isUnderReview && r.title !== "* Under Review") {
        prev.title = r.title;
      }
    } else {
      existingMap.set(r.foilId, { ...r, responses: [], detailScraped: false });
    }
  }

  // Save list data immediately so we don't lose it if detail scraping fails
  if (BACKFILL) {
    const listSave = Array.from(existingMap.values()).sort(
      (a, b) => (b.dateSubmitted || "").localeCompare(a.dateSubmitted || "")
    );
    writeFileSync(OUTPUT_FILE, JSON.stringify({
      lastUpdated: new Date().toISOString(),
      totalInSystem: listData.totalInSystem || existing.totalInSystem,
      requestsFetched: listSave.length,
      agencyStats: {},
      requests: listSave,
    }, null, 2));
    console.log(`Saved ${listSave.length} list entries to disk before detail scraping.\n`);
  }

  // Step 2: Scrape detail pages for requests that need it
  // Prioritize closed requests (they have titles and determinations)
  const needsDetail = Array.from(existingMap.values())
    .filter(
      (r) =>
        !r.detailScraped ||
        (r.status === "Closed" && (!r.responses || r.responses.length === 0)) ||
        // Re-scrape already-detailed closed requests that predate the richer
        // extraction (no timeline yet) so the new fields backfill over time.
        (r.status === "Closed" && !r.timeline)
    )
    .sort((a, b) => {
      // Closed first, then by date
      if (a.status === "Closed" && b.status !== "Closed") return -1;
      if (b.status === "Closed" && a.status !== "Closed") return 1;
      return (b.dateSubmitted || "").localeCompare(a.dateSubmitted || "");
    })
    .slice(0, DETAIL_LIMIT);

  if (needsDetail.length > 0) {
    console.log(`Scraping ${needsDetail.length} detail pages...\n`);

    const { browser: b2, context: c2 } = await launchBrowser();
    const detailPage = await c2.newPage();

    // Process sequentially to avoid overwhelming the server
    let detailFailures = 0;
    const detailStart = Date.now();
    for (let i = 0; i < needsDetail.length; i++) {
      if (Date.now() - detailStart > DETAIL_TIME_BUDGET_MS) {
        console.log(
          `\n  Detail time budget (${Math.round(DETAIL_TIME_BUDGET_MS / 60000)}m) reached at ${i}/${needsDetail.length}; stopping and saving progress.`
        );
        break;
      }
      const req = needsDetail[i];
      const detail = await scrapeDetail(detailPage, req.foilId);

      if (!detail) {
        detailFailures++;
        if (detailFailures >= 5) {
          console.log(`\n  Stopping detail scraping after ${detailFailures} consecutive failures (WAF likely blocking).`);
          break;
        }
      } else {
        detailFailures = 0; // reset on success
      }

      // Brief pause between requests
      await detailPage.waitForTimeout(1500);

      if (detail) {
        const entry = existingMap.get(req.foilId);
        if (entry) applyDetail(entry, detail);
      }

      if ((i + 1) % 10 === 0 || i === needsDetail.length - 1) {
        console.log(`  Detail progress: ${i + 1}/${needsDetail.length}`);
        // Save intermediate progress every 25 details
        if ((i + 1) % 25 === 0) {
          const intermediate = Array.from(existingMap.values());
          writeFileSync(OUTPUT_FILE, JSON.stringify({ lastUpdated: new Date().toISOString(), requestsFetched: intermediate.length, requests: intermediate }, null, 2));
          console.log(`  Saved intermediate progress (${intermediate.length} requests)`);
        }
      }
    }

    await b2.close();
  }

  // Build output
  const allRequests = Array.from(existingMap.values()).sort(
    (a, b) => (b.dateSubmitted || "").localeCompare(a.dateSubmitted || "")
  );

  // Agency stats
  const agencyStats = {};
  for (const r of allRequests) {
    const agency = r.agency || "Unknown";
    if (!agencyStats[agency]) {
      agencyStats[agency] = {
        total: 0,
        open: 0,
        closed: 0,
        denied: 0,
        fulfilled: 0,
        avgResponseDays: 0,
        responseTimes: [],
      };
    }
    const s = agencyStats[agency];
    s.total++;
    if (r.status === "Open") s.open++;
    if (r.status === "Closed") s.closed++;
    if (r.determination === "Denied") s.denied++;
    if (r.determination === "Fulfilled") s.fulfilled++;
    if (r.responseTimeDays != null) s.responseTimes.push(r.responseTimeDays);
  }

  // Calculate averages
  for (const s of Object.values(agencyStats)) {
    if (s.responseTimes.length > 0) {
      s.avgResponseDays = Math.round(
        s.responseTimes.reduce((a, b) => a + b, 0) / s.responseTimes.length
      );
    }
    delete s.responseTimes;
  }

  const output = {
    lastUpdated: new Date().toISOString(),
    totalInSystem: listData.totalInSystem || existing.totalInSystem || "597,000+",
    requestsFetched: allRequests.length,
    agencyStats,
    requests: allRequests,
  };

  writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`\nSaved ${allRequests.length} requests to ${OUTPUT_FILE}`);

  // Regenerate RSS feeds from the fresh data
  try {
    const { spawnSync } = await import("node:child_process");
    const r = spawnSync("node", [join(__dirname, "generate-feeds.mjs")], { stdio: "inherit" });
    if (r.status !== 0) console.warn("Feed generation exited non-zero (continuing)");
  } catch (err) {
    console.warn("Feed generation failed (non-fatal):", err.message);
  }

  console.log("Done!");
}

// Only auto-run the full scrape when executed directly (`node scrape.mjs`),
// so the helpers can be imported for testing without kicking off a backfill.
import { pathToFileURL } from "node:url";
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error("Fatal error:", err);
    process.exit(1);
  });
}

export { launchBrowser, scrapeDetail, applyDetail };
