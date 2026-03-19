import { chromium } from "playwright";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, "data");
const OUTPUT_FILE = join(DATA_DIR, "requests.json");

const BATCH_SIZE = 50;
const LIST_PAGES = 4; // 200 most recent requests
const DETAIL_CONCURRENCY = 5; // parallel detail page fetches
const DETAIL_LIMIT = 30; // how many detail pages to scrape per run

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

// Step 1: Scrape the search results list
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
        // Take a screenshot for debugging
        const title = await page.title();
        const url = page.url();
        console.error(`  Failed after 3 attempts. Page title: "${title}", URL: ${url}`);
        const bodyText = await page.evaluate(() => document.body?.innerText?.substring(0, 500));
        console.error(`  Page content: ${bodyText}`);
        throw new Error("Could not load OpenRecords search page after 3 attempts");
      }
      console.log("  Table not found, retrying...");
      await page.waitForTimeout(3000);
    }
  }

  const allRequests = [];
  let start = 0;

  for (let i = 0; i < LIST_PAGES; i++) {
    console.log(`  Fetching batch ${i + 1}/${LIST_PAGES} (start=${start})...`);

    const data = await page.evaluate(
      async ({ start, size }) => {
        const url = `/search/requests?query=&title=on&agency_request_summary=on&open=on&closed=on&date_rec_from=&date_rec_to=&agency_ein=&size=${size}&tz_name=America/New_York&start=${start}&sort_date_submitted=DESC`;
        const resp = await fetch(url, {
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            Accept: "application/json, text/javascript, */*; q=0.01",
          },
        });
        const json = await resp.json();
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
      },
      { start, size: BATCH_SIZE }
    );

    allRequests.push(...data.requests);
    console.log(`    Got ${data.requests.length} (total in system: ${data.total})`);

    if (data.requests.length < BATCH_SIZE) break;
    start += BATCH_SIZE;
    await page.waitForTimeout(800);
  }

  return {
    totalInSystem: allRequests.length > 0 ? allRequests[0]?.totalInSystem : 0,
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

    // Wait for responses section to load (they load via AJAX)
    await page.waitForTimeout(5000);

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

      return { title, responses };
    });

    return detail;
  } catch (err) {
    console.error(`  Failed to scrape ${foilId}: ${err.message}`);
    return null;
  }
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

  // Step 1: Scrape the list
  const { browser: b1, context: c1 } = await launchBrowser();
  const listPage = await c1.newPage();
  const listData = await scrapeList(listPage);
  await b1.close();

  console.log(`\nFetched ${listData.requests.length} requests from search.\n`);

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

  // Step 2: Scrape detail pages for requests that need it
  // Prioritize closed requests (they have titles and determinations)
  const needsDetail = Array.from(existingMap.values())
    .filter((r) => !r.detailScraped || (r.status === "Closed" && (!r.responses || r.responses.length === 0)))
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
    for (let i = 0; i < needsDetail.length; i++) {
      const req = needsDetail[i];
      const detail = await scrapeDetail(detailPage, req.foilId);
      const results = [{ foilId: req.foilId, detail }];

      // Brief pause between requests
      await detailPage.waitForTimeout(1000);

      for (const { foilId, detail } of results) {
        if (detail) {
          const entry = existingMap.get(foilId);
          if (entry) {
            if (detail.title && detail.title !== "* Under Review") {
              entry.title = detail.title;
            }
            entry.responses = detail.responses;
            entry.detailScraped = true;

            // Derive determination from responses
            const closing = detail.responses.find((r) => r.type === "CLOSING");
            const denial = detail.responses.find((r) => r.type === "DENIAL");
            const partialDenial = detail.responses.find((r) =>
              r.type.includes("PARTIAL")
            );
            if (denial) {
              entry.determination = "Denied";
              entry.determinationMessage = denial.message;
              entry.determinationDate = denial.date;
            } else if (partialDenial) {
              entry.determination = "Partially Denied";
              entry.determinationMessage = partialDenial.message;
              entry.determinationDate = partialDenial.date;
            } else if (closing) {
              entry.determination = "Fulfilled";
              entry.determinationMessage = closing.message;
              entry.determinationDate = closing.date;
            }

            // Calculate response time
            const ack = detail.responses.find(
              (r) => r.type === "ACKNOWLEDGMENT"
            );
            const lastResp = detail.responses[0]; // responses are in reverse chronological
            if (entry.dateSubmitted && lastResp?.date) {
              try {
                // Parse date like "Friday, 01/26/2024 at 8:53 AM"
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
          }
        }
      }

      if ((i + 1) % 10 === 0 || i === needsDetail.length - 1) {
        console.log(`  Detail progress: ${i + 1}/${needsDetail.length}`);
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
    totalInSystem: listData.requests.length > 0 ? "597,000+" : existing.totalInSystem,
    requestsFetched: allRequests.length,
    agencyStats,
    requests: allRequests,
  };

  writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`\nSaved ${allRequests.length} requests to ${OUTPUT_FILE}`);
  console.log("Done!");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
