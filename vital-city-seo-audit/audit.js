#!/usr/bin/env node

/**
 * SEO Audit Scanner for vitalcitynyc.org
 *
 * Crawls the sitemap, fetches pages, and checks for common SEO issues:
 *   - Missing/duplicate/too-long title tags
 *   - Missing/too-long meta descriptions
 *   - Missing Open Graph & Twitter card tags
 *   - Missing canonical links
 *   - Missing or duplicate H1 tags
 *   - Image alt text coverage
 *   - Missing structured data (JSON-LD)
 *   - Broken internal links (optional, slow)
 *   - Page load size
 *
 * Run: node audit.js [--pages N] [--check-links]
 * Output: data/audit.json + index.html dashboard
 */

const fetch = require("node-fetch");
const cheerio = require("cheerio");
const xml2js = require("xml2js");
const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const SITE = "https://www.vitalcitynyc.org";
const SITEMAP_INDEX = `${SITE}/sitemap.xml`;
const DATA_DIR = path.join(__dirname, "data");
const AUDIT_FILE = path.join(DATA_DIR, "audit.json");
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const MAX_TITLE_LEN = 60;
const MAX_DESC_LEN = 160;
const MIN_DESC_LEN = 50;

// Parse CLI args
const args = process.argv.slice(2);
const maxPages = parseInt(args.find((a, i) => args[i - 1] === "--pages") || "50", 10);
const checkLinks = args.includes("--check-links");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

async function fetchText(url, timeout = 20000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": UA },
      signal: controller.signal,
      redirect: "follow",
    });
    clearTimeout(timer);
    const size = parseInt(res.headers.get("content-length") || "0", 10);
    const text = await res.text();
    return { text, status: res.status, size: size || Buffer.byteLength(text) };
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Sitemap parser
// ---------------------------------------------------------------------------

async function getSitemapUrls() {
  console.log("Fetching sitemap index...");
  const { text: indexXml } = await fetchText(SITEMAP_INDEX);
  const index = await xml2js.parseStringPromise(indexXml, { explicitArray: false });

  const sitemapUrls = [];
  const sitemaps = Array.isArray(index.sitemapindex?.sitemap)
    ? index.sitemapindex.sitemap
    : [index.sitemapindex?.sitemap].filter(Boolean);

  for (const sm of sitemaps) {
    const loc = sm.loc;
    // Only crawl pages and posts (skip authors, tags)
    if (loc.includes("authors") || loc.includes("tags")) continue;
    console.log(`  Fetching ${loc}...`);
    try {
      const { text: smXml } = await fetchText(loc);
      const parsed = await xml2js.parseStringPromise(smXml, { explicitArray: false });
      const urls = Array.isArray(parsed.urlset?.url)
        ? parsed.urlset.url
        : [parsed.urlset?.url].filter(Boolean);
      for (const u of urls) {
        sitemapUrls.push({
          url: u.loc,
          lastmod: u.lastmod || null,
        });
      }
    } catch (err) {
      console.log(`    Error: ${err.message}`);
    }
  }

  console.log(`  Found ${sitemapUrls.length} URLs in sitemap`);
  return sitemapUrls;
}

// ---------------------------------------------------------------------------
// Page auditor
// ---------------------------------------------------------------------------

function auditPage(url, html, size) {
  const $ = cheerio.load(html);
  const issues = [];
  const warnings = [];
  const info = {};

  // Title
  const title = $("title").text().trim();
  info.title = title;
  if (!title) {
    issues.push("Missing <title> tag");
  } else if (title.length > MAX_TITLE_LEN) {
    warnings.push(`Title too long (${title.length} chars, max ${MAX_TITLE_LEN})`);
  } else if (title === "Vital City") {
    warnings.push("Generic title \u2014 should be unique per page");
  }

  // Meta description
  const desc = $('meta[name="description"]').attr("content")?.trim() || "";
  info.description = desc;
  if (!desc) {
    issues.push("Missing meta description");
  } else if (desc.length > MAX_DESC_LEN) {
    warnings.push(`Meta description too long (${desc.length} chars, max ${MAX_DESC_LEN})`);
  } else if (desc.length < MIN_DESC_LEN) {
    warnings.push(`Meta description too short (${desc.length} chars, min ~${MIN_DESC_LEN})`);
  }

  // Canonical
  const canonical = $('link[rel="canonical"]').attr("href") || "";
  info.canonical = canonical;
  if (!canonical) {
    issues.push("Missing canonical link");
  }

  // Open Graph
  const ogTitle = $('meta[property="og:title"]').attr("content") || "";
  const ogDesc = $('meta[property="og:description"]').attr("content") || "";
  const ogImage = $('meta[property="og:image"]').attr("content") || "";
  const ogUrl = $('meta[property="og:url"]').attr("content") || "";
  info.og = { title: ogTitle, description: ogDesc, image: ogImage, url: ogUrl };
  if (!ogTitle) issues.push("Missing og:title");
  if (!ogDesc) issues.push("Missing og:description");
  if (!ogImage) issues.push("Missing og:image");
  if (!ogUrl) warnings.push("Missing og:url");

  // Twitter cards
  const twCard = $('meta[name="twitter:card"]').attr("content") ||
                 $('meta[property="twitter:card"]').attr("content") || "";
  const twTitle = $('meta[name="twitter:title"]').attr("content") ||
                  $('meta[property="twitter:title"]').attr("content") || "";
  info.twitter = { card: twCard, title: twTitle };
  if (!twCard) warnings.push("Missing twitter:card meta tag");
  if (!twTitle && !ogTitle) warnings.push("Missing twitter:title (and no og:title fallback)");

  // H1 tags
  const h1s = [];
  $("h1").each((_, el) => {
    const text = $(el).text().trim();
    if (text) h1s.push(text);
  });
  info.h1s = h1s;
  if (h1s.length === 0) {
    issues.push("Missing H1 tag");
  } else if (h1s.length > 1) {
    warnings.push(`Multiple H1 tags (${h1s.length})`);
  }

  // Heading hierarchy
  const headingLevels = [];
  $("h1, h2, h3, h4, h5, h6").each((_, el) => {
    headingLevels.push(parseInt(el.tagName[1]));
  });
  for (let i = 1; i < headingLevels.length; i++) {
    if (headingLevels[i] > headingLevels[i - 1] + 1) {
      warnings.push(
        `Heading level skip: H${headingLevels[i - 1]} \u2192 H${headingLevels[i]}`
      );
      break;
    }
  }

  // Images without alt text
  let totalImages = 0;
  let missingAlt = 0;
  $("img").each((_, el) => {
    totalImages++;
    const alt = $(el).attr("alt");
    if (!alt || alt.trim() === "") missingAlt++;
  });
  info.images = { total: totalImages, missingAlt };
  if (missingAlt > 0) {
    warnings.push(`${missingAlt} of ${totalImages} images missing alt text`);
  }

  // Structured data (JSON-LD)
  const jsonLd = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    try {
      const parsed = JSON.parse($(el).html());
      jsonLd.push(parsed["@type"] || "unknown");
    } catch {}
  });
  info.structuredData = jsonLd;
  if (jsonLd.length === 0) {
    warnings.push("No structured data (JSON-LD) found");
  }

  // Internal links
  const internalLinks = [];
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href") || "";
    if (
      href.startsWith("/") ||
      href.includes("vitalcitynyc.org")
    ) {
      const full = href.startsWith("http")
        ? href
        : new URL(href, SITE).href;
      internalLinks.push(full);
    }
  });
  info.internalLinkCount = internalLinks.length;

  // Page size
  info.pageSize = size;
  if (size > 500000) {
    warnings.push(`Large page size (${(size / 1024).toFixed(0)} KB)`);
  }

  // Word count (rough)
  const bodyText = $("article").text() || $("main").text() || $("body").text();
  const wordCount = bodyText.split(/\s+/).filter(Boolean).length;
  info.wordCount = wordCount;
  if (wordCount < 300 && url !== SITE && !url.endsWith("/")) {
    warnings.push(`Thin content (${wordCount} words)`);
  }

  return {
    url,
    issues,
    warnings,
    info,
    internalLinks: checkLinks ? [...new Set(internalLinks)] : [],
    score: Math.max(0, 100 - issues.length * 15 - warnings.length * 5),
  };
}

// ---------------------------------------------------------------------------
// Link checker
// ---------------------------------------------------------------------------

async function checkBrokenLinks(audits) {
  if (!checkLinks) return [];
  console.log("\nChecking internal links for broken URLs...");

  const allLinks = new Set();
  for (const a of audits) {
    for (const link of a.internalLinks) {
      allLinks.add(link);
    }
  }

  const broken = [];
  let checked = 0;
  for (const link of allLinks) {
    try {
      const res = await fetch(link, {
        method: "HEAD",
        headers: { "User-Agent": UA },
        redirect: "follow",
        signal: AbortSignal.timeout(10000),
      });
      if (res.status >= 400) {
        broken.push({ url: link, status: res.status });
      }
    } catch (err) {
      broken.push({ url: link, status: "error", message: err.message });
    }
    checked++;
    if (checked % 20 === 0) console.log(`  Checked ${checked}/${allLinks.size}`);
    await new Promise((r) => setTimeout(r, 200));
  }
  console.log(`  Done. ${broken.length} broken link(s) found.`);
  return broken;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  ensureDataDir();

  const sitemapUrls = await getSitemapUrls();
  const toAudit = sitemapUrls.slice(0, maxPages);

  console.log(`\nAuditing ${toAudit.length} pages (max ${maxPages})...\n`);

  const audits = [];
  for (let i = 0; i < toAudit.length; i++) {
    const { url } = toAudit[i];
    try {
      const { text: html, size } = await fetchText(url);
      const result = auditPage(url, html, size);
      audits.push(result);

      const icon = result.issues.length > 0 ? "\u274c" : result.warnings.length > 0 ? "\u26a0\ufe0f" : "\u2705";
      console.log(
        `  ${icon} [${i + 1}/${toAudit.length}] ${result.score}/100  ${url.replace(SITE, "")}`
      );
    } catch (err) {
      console.log(`  \u2717 [${i + 1}/${toAudit.length}] ${url}: ${err.message}`);
      audits.push({
        url,
        issues: [`Failed to fetch: ${err.message}`],
        warnings: [],
        info: {},
        score: 0,
      });
    }
    await new Promise((r) => setTimeout(r, 300));
  }

  const brokenLinks = await checkBrokenLinks(audits);

  // Compute summary stats
  const avgScore = Math.round(
    audits.reduce((s, a) => s + a.score, 0) / audits.length
  );
  const totalIssues = audits.reduce((s, a) => s + a.issues.length, 0);
  const totalWarnings = audits.reduce((s, a) => s + a.warnings.length, 0);

  // Common issues
  const issueCounts = {};
  const warningCounts = {};
  for (const a of audits) {
    for (const i of a.issues) {
      const key = i.replace(/\(\d+ chars.*?\)/, "(...)");
      issueCounts[key] = (issueCounts[key] || 0) + 1;
    }
    for (const w of a.warnings) {
      const key = w.replace(/\(\d+ chars.*?\)/, "(...)").replace(/\d+ of \d+/, "N of M");
      warningCounts[key] = (warningCounts[key] || 0) + 1;
    }
  }

  // Title uniqueness
  const titleCounts = {};
  for (const a of audits) {
    const t = a.info.title || "(empty)";
    if (!titleCounts[t]) titleCounts[t] = [];
    titleCounts[t].push(a.url);
  }
  const duplicateTitles = Object.entries(titleCounts).filter(
    ([, urls]) => urls.length > 1
  );

  const auditData = {
    site: SITE,
    scannedAt: new Date().toISOString(),
    pagesAudited: audits.length,
    averageScore: avgScore,
    totalIssues,
    totalWarnings,
    commonIssues: Object.entries(issueCounts).sort((a, b) => b[1] - a[1]),
    commonWarnings: Object.entries(warningCounts).sort((a, b) => b[1] - a[1]),
    duplicateTitles,
    brokenLinks,
    pages: audits.sort((a, b) => a.score - b.score), // worst first
  };

  fs.writeFileSync(AUDIT_FILE, JSON.stringify(auditData, null, 2));
  console.log(`\n\u2705 Audit complete.`);
  console.log(`   Pages: ${audits.length} | Avg score: ${avgScore}/100`);
  console.log(`   Issues: ${totalIssues} | Warnings: ${totalWarnings}`);
  console.log(`   Saved to ${AUDIT_FILE}`);
}

main().catch(console.error);
