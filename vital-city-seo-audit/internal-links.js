#!/usr/bin/env node

/**
 * Internal Linking Analyzer for vitalcitynyc.org
 *
 * Crawls article pages and builds a link graph to find:
 *   - Orphan pages (zero inbound internal links)
 *   - Low-inbound pages (1-2 inbound links)
 *   - Hub pages (high outbound link count)
 *   - Sink pages (high inbound, low outbound)
 *   - Cross-linking suggestions (shared tags, no link)
 *
 * Run: node internal-links.js [--pages N]
 * Output: data/internal-links.json
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
const OUTPUT_FILE = path.join(DATA_DIR, "internal-links.json");
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const DELAY_MS = 300;

// Parse CLI args
const args = process.argv.slice(2);
const maxPages = parseInt(
  args.find((a, i) => args[i - 1] === "--pages") || "80",
  10
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    const text = await res.text();
    return { text, status: res.status };
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

/**
 * Normalize a URL for comparison: strip trailing slash, hash, query params.
 * Returns null if the URL is not an internal vitalcitynyc.org page.
 */
function normalizeUrl(href, baseUrl) {
  try {
    const parsed = new URL(href, baseUrl);

    // Only internal links
    if (
      parsed.hostname !== "www.vitalcitynyc.org" &&
      parsed.hostname !== "vitalcitynyc.org"
    ) {
      return null;
    }

    // Strip hash and query
    parsed.hash = "";
    parsed.search = "";

    // Normalize to https://www.vitalcitynyc.org
    parsed.hostname = "www.vitalcitynyc.org";
    parsed.protocol = "https:";

    let normalized = parsed.toString();
    // Strip trailing slash for consistency (but keep root "/" as-is)
    if (normalized.endsWith("/") && parsed.pathname !== "/") {
      normalized = normalized.slice(0, -1);
    }

    return normalized;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Sitemap parser
// ---------------------------------------------------------------------------

async function getArticleUrls() {
  console.log("Fetching sitemap index...");
  const { text: indexXml } = await fetchText(SITEMAP_INDEX);
  const index = await xml2js.parseStringPromise(indexXml, {
    explicitArray: false,
  });

  const articleUrls = [];
  const sitemaps = Array.isArray(index.sitemapindex?.sitemap)
    ? index.sitemapindex.sitemap
    : [index.sitemapindex?.sitemap].filter(Boolean);

  for (const sm of sitemaps) {
    const loc = sm.loc;
    // Crawl posts and pages sitemaps (skip authors, tags)
    if (loc.includes("authors") || loc.includes("tags")) continue;

    console.log(`  Fetching ${loc}...`);
    await sleep(DELAY_MS);
    try {
      const { text: smXml } = await fetchText(loc);
      const parsed = await xml2js.parseStringPromise(smXml, {
        explicitArray: false,
      });
      const urls = Array.isArray(parsed.urlset?.url)
        ? parsed.urlset.url
        : [parsed.urlset?.url].filter(Boolean);

      for (const u of urls) {
        articleUrls.push(u.loc);
      }
    } catch (err) {
      console.log(`    Error: ${err.message}`);
    }
  }

  console.log(`  Found ${articleUrls.length} URLs in sitemaps`);
  return articleUrls;
}

// ---------------------------------------------------------------------------
// Page crawler
// ---------------------------------------------------------------------------

/**
 * Crawl a single page and extract title, tags, and internal links.
 */
function extractPageData(url, html) {
  const $ = cheerio.load(html);

  // Title
  const title =
    $('meta[property="og:title"]').attr("content")?.trim() ||
    $("title").text().trim() ||
    "";

  // Tags / categories
  const tags = new Set();

  // Look for tag links (common Webflow/CMS pattern)
  $('a[href*="/topics/"], a[href*="/tags/"], a[href*="/category/"]').each(
    (_, el) => {
      const text = $(el).text().trim();
      if (text) tags.add(text.toLowerCase());
    }
  );

  // Also check meta keywords
  const metaKeywords = $('meta[name="keywords"]').attr("content") || "";
  if (metaKeywords) {
    metaKeywords.split(",").forEach((k) => {
      const trimmed = k.trim().toLowerCase();
      if (trimmed) tags.add(trimmed);
    });
  }

  // Look for article:tag meta tags
  $('meta[property="article:tag"]').each((_, el) => {
    const content = $(el).attr("content")?.trim().toLowerCase();
    if (content) tags.add(content);
  });

  // Extract all internal links
  const internalLinks = new Set();
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href");
    if (!href) return;

    const normalized = normalizeUrl(href, url);
    if (normalized && normalized !== normalizeUrl(url, url)) {
      internalLinks.add(normalized);
    }
  });

  return {
    title,
    tags: Array.from(tags),
    outboundLinks: Array.from(internalLinks),
  };
}

// ---------------------------------------------------------------------------
// Link graph analysis
// ---------------------------------------------------------------------------

function analyzeGraph(pages, allSitemapUrls) {
  // Build sets for quick lookup
  const crawledUrls = new Set(Object.keys(pages));

  // Normalize all sitemap URLs for comparison
  const allKnownUrls = new Set();
  for (const url of allSitemapUrls) {
    const n = normalizeUrl(url, SITE);
    if (n) allKnownUrls.add(n);
  }

  // Build inbound counts for all known URLs
  const inboundCounts = {};
  const inboundFrom = {}; // track which pages link to each URL
  for (const url of allKnownUrls) {
    inboundCounts[url] = 0;
    inboundFrom[url] = [];
  }

  // Build outbound link graph
  const linkGraph = {};
  for (const [pageUrl, data] of Object.entries(pages)) {
    // Only count links to known sitemap pages
    const relevantOutbound = data.outboundLinks.filter((link) =>
      allKnownUrls.has(link)
    );
    linkGraph[pageUrl] = relevantOutbound;

    for (const target of relevantOutbound) {
      if (inboundCounts[target] === undefined) {
        inboundCounts[target] = 0;
        inboundFrom[target] = [];
      }
      inboundCounts[target]++;
      inboundFrom[target].push(pageUrl);
    }
  }

  // Orphan pages: in sitemap but zero inbound from crawled pages
  const orphanPages = [];
  for (const url of allKnownUrls) {
    if ((inboundCounts[url] || 0) === 0) {
      orphanPages.push({
        url,
        title: pages[url]?.title || "(not crawled)",
      });
    }
  }
  orphanPages.sort((a, b) => a.url.localeCompare(b.url));

  // Low inbound pages: 1-2 inbound links
  const lowInboundPages = [];
  for (const url of allKnownUrls) {
    const count = inboundCounts[url] || 0;
    if (count >= 1 && count <= 2) {
      lowInboundPages.push({
        url,
        title: pages[url]?.title || "(not crawled)",
        inboundCount: count,
        linkedFrom: inboundFrom[url] || [],
      });
    }
  }
  lowInboundPages.sort((a, b) => a.inboundCount - b.inboundCount);

  // Hub pages: top pages by outbound link count
  const hubPages = Object.entries(linkGraph)
    .map(([url, links]) => ({
      url,
      title: pages[url]?.title || "",
      outboundCount: links.length,
    }))
    .sort((a, b) => b.outboundCount - a.outboundCount)
    .slice(0, 20);

  // Sink pages: high inbound, low outbound
  const sinkPages = [];
  for (const url of crawledUrls) {
    const inbound = inboundCounts[url] || 0;
    const outbound = (linkGraph[url] || []).length;
    if (inbound >= 3 && outbound <= 2) {
      sinkPages.push({
        url,
        title: pages[url]?.title || "",
        inboundCount: inbound,
        outboundCount: outbound,
      });
    }
  }
  sinkPages.sort((a, b) => b.inboundCount - a.inboundCount);

  // Average links per page
  const outboundCounts = Object.values(linkGraph).map((l) => l.length);
  const avgOutbound =
    outboundCounts.length > 0
      ? outboundCounts.reduce((s, n) => s + n, 0) / outboundCounts.length
      : 0;

  const inboundValues = Object.values(inboundCounts);
  const avgInbound =
    inboundValues.length > 0
      ? inboundValues.reduce((s, n) => s + n, 0) / inboundValues.length
      : 0;

  // Cross-linking suggestions: pages that share tags but don't link to each other
  const crossLinkSuggestions = findCrossLinkOpportunities(pages, linkGraph);

  return {
    summary: {
      totalUrlsInSitemap: allKnownUrls.size,
      pagesCrawled: crawledUrls.size,
      orphanPageCount: orphanPages.length,
      lowInboundPageCount: lowInboundPages.length,
      hubPageCount: hubPages.length,
      sinkPageCount: sinkPages.length,
      avgOutboundLinksPerPage: Math.round(avgOutbound * 10) / 10,
      avgInboundLinksPerPage: Math.round(avgInbound * 10) / 10,
      crossLinkSuggestionCount: crossLinkSuggestions.length,
    },
    orphanPages,
    lowInboundPages,
    hubPages,
    sinkPages,
    linkGraph,
    inboundCounts,
    crossLinkSuggestions,
  };
}

/**
 * Find pairs of articles that share tags/topics but do not link to each other.
 * Returns up to 50 suggestions, prioritizing pairs with the most shared tags.
 */
function findCrossLinkOpportunities(pages, linkGraph) {
  const suggestions = [];
  const urls = Object.keys(pages).filter((u) => pages[u].tags.length > 0);

  // Build a tag -> URLs index
  const tagIndex = {};
  for (const url of urls) {
    for (const tag of pages[url].tags) {
      if (!tagIndex[tag]) tagIndex[tag] = [];
      tagIndex[tag].push(url);
    }
  }

  // Find pairs that share tags but don't link to each other
  const seen = new Set();
  const candidates = [];

  for (const [tag, tagUrls] of Object.entries(tagIndex)) {
    if (tagUrls.length < 2 || tagUrls.length > 50) continue; // skip very common tags

    for (let i = 0; i < tagUrls.length; i++) {
      for (let j = i + 1; j < tagUrls.length; j++) {
        const a = tagUrls[i];
        const b = tagUrls[j];
        const key = [a, b].sort().join("|");
        if (seen.has(key)) continue;
        seen.add(key);

        const aLinksToB = (linkGraph[a] || []).includes(b);
        const bLinksToA = (linkGraph[b] || []).includes(a);

        if (!aLinksToB && !bLinksToA) {
          // Count shared tags
          const sharedTags = pages[a].tags.filter((t) =>
            pages[b].tags.includes(t)
          );
          candidates.push({
            pageA: { url: a, title: pages[a].title },
            pageB: { url: b, title: pages[b].title },
            sharedTags,
            sharedTagCount: sharedTags.length,
          });
        }
      }
    }
  }

  // Sort by shared tag count descending, take top 50
  candidates.sort((a, b) => b.sharedTagCount - a.sharedTagCount);
  return candidates.slice(0, 50);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  ensureDataDir();

  console.log(`\nInternal Link Analyzer for vitalcitynyc.org`);
  console.log(`Max pages to crawl: ${maxPages}\n`);

  // Step 1: Get all article URLs from sitemap
  const allSitemapUrls = await getArticleUrls();

  if (allSitemapUrls.length === 0) {
    console.error("No URLs found in sitemap. Exiting.");
    process.exit(1);
  }

  // Step 2: Crawl pages (up to maxPages)
  const urlsToCrawl = allSitemapUrls.slice(0, maxPages);
  const pages = {};
  let crawled = 0;
  let errors = 0;

  for (const url of urlsToCrawl) {
    crawled++;
    const pct = Math.round((crawled / urlsToCrawl.length) * 100);
    process.stdout.write(
      `\r  Crawling ${crawled}/${urlsToCrawl.length} (${pct}%) - ${url.slice(0, 70)}...`
    );

    try {
      const { text: html, status } = await fetchText(url);
      if (status >= 400) {
        console.log(`\n    HTTP ${status}: ${url}`);
        errors++;
        continue;
      }

      const data = extractPageData(url, html);
      pages[normalizeUrl(url, SITE)] = data;
    } catch (err) {
      console.log(`\n    Error crawling ${url}: ${err.message}`);
      errors++;
    }

    await sleep(DELAY_MS);
  }

  console.log(`\n\n  Crawled ${crawled - errors} pages (${errors} errors)\n`);

  // Step 3: Analyze the link graph
  console.log("Analyzing link graph...");
  const results = analyzeGraph(pages, allSitemapUrls);

  // Step 4: Save results
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2));
  console.log(`\nResults saved to ${OUTPUT_FILE}`);

  // Step 5: Print summary
  const s = results.summary;
  console.log(`\n${"=".repeat(60)}`);
  console.log(`  INTERNAL LINK ANALYSIS SUMMARY`);
  console.log(`${"=".repeat(60)}`);
  console.log(`  Total URLs in sitemap:       ${s.totalUrlsInSitemap}`);
  console.log(`  Pages crawled:               ${s.pagesCrawled}`);
  console.log(`  Avg outbound links/page:     ${s.avgOutboundLinksPerPage}`);
  console.log(`  Avg inbound links/page:      ${s.avgInboundLinksPerPage}`);
  console.log(`  Orphan pages (0 inbound):    ${s.orphanPageCount}`);
  console.log(`  Low inbound (1-2 links):     ${s.lowInboundPageCount}`);
  console.log(`  Hub pages (high outbound):   ${s.hubPageCount}`);
  console.log(`  Sink pages (high in/low out):${s.sinkPageCount}`);
  console.log(`  Cross-link suggestions:      ${s.crossLinkSuggestionCount}`);
  console.log(`${"=".repeat(60)}`);

  if (results.orphanPages.length > 0) {
    console.log(`\n  Top orphan pages (no inbound links):`);
    for (const p of results.orphanPages.slice(0, 10)) {
      console.log(`    - ${p.title || p.url}`);
      if (p.title) console.log(`      ${p.url}`);
    }
    if (results.orphanPages.length > 10) {
      console.log(
        `    ... and ${results.orphanPages.length - 10} more (see JSON)`
      );
    }
  }

  if (results.crossLinkSuggestions.length > 0) {
    console.log(`\n  Top cross-link suggestions:`);
    for (const s of results.crossLinkSuggestions.slice(0, 5)) {
      console.log(
        `    \u2194 "${s.pageA.title}" <-> "${s.pageB.title}"`
      );
      console.log(
        `      Shared tags: ${s.sharedTags.join(", ")}`
      );
    }
  }

  console.log("");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
