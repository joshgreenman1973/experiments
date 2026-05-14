#!/usr/bin/env node

/**
 * Google News Sitemap Tuner for vitalcitynyc.org
 *
 * Checks whether the site meets Google News sitemap requirements:
 *   - Dedicated news sitemap with <news:news> tags
 *   - Required fields: publication, name, language, publication_date, title
 *   - Articles published within the last 2 days
 *   - Sitemap registered in robots.txt
 *   - Proper <lastmod> dates on URLs
 *   - Article pages: meta tags, JSON-LD, bylines, <time> elements
 *   - Googlebot-News rules in robots.txt
 *
 * Run: node news-sitemap.js
 * Output: data/news-sitemap.json
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
const ROBOTS_URL = `${SITE}/robots.txt`;
const DATA_DIR = path.join(__dirname, "data");
const OUTPUT_FILE = path.join(DATA_DIR, "news-sitemap.json");
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const SAMPLE_ARTICLES = 10; // number of recent article pages to inspect
const TWO_DAYS_MS = 2 * 24 * 60 * 60 * 1000;

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
    return { text: await res.text(), status: res.status, url: res.url };
  } catch (err) {
    clearTimeout(timer);
    return { text: null, status: 0, url, error: err.message };
  }
}

async function parseXml(xmlText) {
  return xml2js.parseStringPromise(xmlText, {
    explicitArray: false,
    mergeAttrs: true,
  });
}

function log(msg) {
  console.log(`  ${msg}`);
}

// ---------------------------------------------------------------------------
// 1. Fetch main sitemap + all sub-sitemaps
// ---------------------------------------------------------------------------

async function fetchAllSitemaps() {
  console.log("\n[1/5] Fetching sitemap index and sub-sitemaps...");

  const result = {
    mainSitemap: { url: SITEMAP_INDEX, found: false, isIndex: false },
    subSitemaps: [],
    allUrls: [],
    newsSitemap: null,
  };

  const { text: indexXml, status } = await fetchText(SITEMAP_INDEX);
  if (!indexXml || status !== 200) {
    log(`ERROR: Could not fetch ${SITEMAP_INDEX} (status ${status})`);
    return result;
  }

  result.mainSitemap.found = true;
  const parsed = await parseXml(indexXml);

  // Check if this is a sitemap index or a single sitemap
  if (parsed.sitemapindex) {
    result.mainSitemap.isIndex = true;
    const sitemaps = Array.isArray(parsed.sitemapindex.sitemap)
      ? parsed.sitemapindex.sitemap
      : [parsed.sitemapindex.sitemap];

    log(`Found sitemap index with ${sitemaps.length} sub-sitemap(s)`);

    for (const sm of sitemaps) {
      const loc = typeof sm === "string" ? sm : sm.loc;
      if (!loc) continue;

      const isNewsSitemap =
        /news/i.test(loc) || /sitemap[-_]?news/i.test(loc);
      const sub = { url: loc, isNewsSitemap, urlCount: 0, hasNewsExtension: false, urls: [] };

      const { text: subXml, status: subStatus } = await fetchText(loc);
      if (subXml && subStatus === 200) {
        const subParsed = await parseXml(subXml);
        if (subParsed.urlset) {
          const urls = Array.isArray(subParsed.urlset.url)
            ? subParsed.urlset.url
            : subParsed.urlset.url
            ? [subParsed.urlset.url]
            : [];
          sub.urlCount = urls.length;

          // Check for news:news extension
          const rawHasNews = subXml.includes("<news:news") || subXml.includes("news:publication");
          sub.hasNewsExtension = rawHasNews;

          for (const u of urls) {
            const urlEntry = {
              loc: typeof u === "string" ? u : u.loc,
              lastmod: u.lastmod || null,
            };

            // Parse news:news fields if present
            if (u["news:news"]) {
              urlEntry.newsExtension = {
                hasPublication: !!(u["news:news"]["news:publication"]),
                hasName: !!(u["news:news"]["news:publication"] && u["news:news"]["news:publication"]["news:name"]),
                hasLanguage: !!(u["news:news"]["news:publication"] && u["news:news"]["news:publication"]["news:language"]),
                hasPublicationDate: !!u["news:news"]["news:publication_date"],
                hasTitle: !!u["news:news"]["news:title"],
              };
            }

            sub.urls.push(urlEntry);
            result.allUrls.push(urlEntry);
          }

          if (rawHasNews) {
            result.newsSitemap = sub;
            log(`  -> ${loc} [NEWS SITEMAP] (${urls.length} URLs)`);
          } else {
            log(`  -> ${loc} (${urls.length} URLs)`);
          }
        }
      } else {
        log(`  -> ${loc} (FAILED, status ${subStatus})`);
      }

      result.subSitemaps.push(sub);
    }
  } else if (parsed.urlset) {
    // Single sitemap, not an index
    const urls = Array.isArray(parsed.urlset.url)
      ? parsed.urlset.url
      : parsed.urlset.url
      ? [parsed.urlset.url]
      : [];
    log(`Single sitemap with ${urls.length} URLs`);

    const rawHasNews = indexXml.includes("<news:news");
    const sub = {
      url: SITEMAP_INDEX,
      isNewsSitemap: rawHasNews,
      hasNewsExtension: rawHasNews,
      urlCount: urls.length,
      urls: [],
    };

    for (const u of urls) {
      const urlEntry = {
        loc: typeof u === "string" ? u : u.loc,
        lastmod: u.lastmod || null,
      };
      sub.urls.push(urlEntry);
      result.allUrls.push(urlEntry);
    }

    result.subSitemaps.push(sub);
    if (rawHasNews) result.newsSitemap = sub;
  }

  // Also probe common news sitemap paths directly
  const newsSitemapCandidates = [
    `${SITE}/sitemap-news.xml`,
    `${SITE}/news-sitemap.xml`,
    `${SITE}/sitemap_news.xml`,
    `${SITE}/googlenews-sitemap.xml`,
  ];

  if (!result.newsSitemap) {
    log("No news sitemap found in index; probing common paths...");
    for (const candidate of newsSitemapCandidates) {
      const { text: cXml, status: cStatus } = await fetchText(candidate);
      if (cXml && cStatus === 200 && cXml.includes("<urlset")) {
        const hasNews = cXml.includes("<news:news");
        log(`  -> ${candidate} exists (status 200, news tags: ${hasNews})`);
        result.newsSitemap = { url: candidate, hasNewsExtension: hasNews, probed: true };
        break;
      }
    }
    if (!result.newsSitemap) {
      log("  -> No dedicated news sitemap found at any common path");
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// 2. Analyze news sitemap compliance
// ---------------------------------------------------------------------------

function analyzeNewsSitemap(sitemapData) {
  console.log("\n[2/5] Analyzing Google News sitemap requirements...");

  const findings = {
    hasNewsSitemap: !!sitemapData.newsSitemap,
    newsSitemapUrl: sitemapData.newsSitemap?.url || null,
    hasNewsExtensionTags: sitemapData.newsSitemap?.hasNewsExtension || false,
    totalUrlsInSitemap: sitemapData.allUrls.length,
    urlsWithLastmod: 0,
    urlsWithoutLastmod: 0,
    urlsMissingLastmod: [],
    recentArticles: { within2Days: 0, total: 0, urls: [] },
    newsFieldCompliance: {
      checked: 0,
      missingPublication: 0,
      missingName: 0,
      missingLanguage: 0,
      missingPublicationDate: 0,
      missingTitle: 0,
    },
  };

  const now = Date.now();

  for (const u of sitemapData.allUrls) {
    if (u.lastmod) {
      findings.urlsWithLastmod++;
      const modDate = new Date(u.lastmod).getTime();
      if (now - modDate <= TWO_DAYS_MS) {
        findings.recentArticles.within2Days++;
        findings.recentArticles.urls.push({ url: u.loc, lastmod: u.lastmod });
      }
    } else {
      findings.urlsWithoutLastmod++;
      if (findings.urlsMissingLastmod.length < 10) {
        findings.urlsMissingLastmod.push(u.loc);
      }
    }

    if (u.newsExtension) {
      findings.newsFieldCompliance.checked++;
      if (!u.newsExtension.hasPublication) findings.newsFieldCompliance.missingPublication++;
      if (!u.newsExtension.hasName) findings.newsFieldCompliance.missingName++;
      if (!u.newsExtension.hasLanguage) findings.newsFieldCompliance.missingLanguage++;
      if (!u.newsExtension.hasPublicationDate) findings.newsFieldCompliance.missingPublicationDate++;
      if (!u.newsExtension.hasTitle) findings.newsFieldCompliance.missingTitle++;
    }
  }

  findings.recentArticles.total = sitemapData.allUrls.length;

  log(`Dedicated news sitemap: ${findings.hasNewsSitemap ? "YES" : "NO"}`);
  log(`News extension tags present: ${findings.hasNewsExtensionTags ? "YES" : "NO"}`);
  log(`URLs with <lastmod>: ${findings.urlsWithLastmod} / ${findings.totalUrlsInSitemap}`);
  log(`URLs modified within last 2 days: ${findings.recentArticles.within2Days}`);

  if (findings.newsFieldCompliance.checked > 0) {
    log(`News field compliance checked on ${findings.newsFieldCompliance.checked} entries`);
  }

  return findings;
}

// ---------------------------------------------------------------------------
// 3. Fetch and inspect recent article pages
// ---------------------------------------------------------------------------

async function inspectArticlePages(sitemapData) {
  console.log("\n[3/5] Inspecting recent article pages...");

  // Gather candidate article URLs - prefer those with recent lastmod,
  // or URLs that look like articles (contain /articles/, /research/, etc.)
  let candidates = sitemapData.allUrls
    .filter((u) => u.loc && /\/(articles|research|vital-voices|evidence)\//i.test(u.loc))
    .sort((a, b) => {
      const da = a.lastmod ? new Date(a.lastmod).getTime() : 0;
      const db = b.lastmod ? new Date(b.lastmod).getTime() : 0;
      return db - da;
    })
    .slice(0, SAMPLE_ARTICLES);

  // Fallback: if we didn't find article-looking paths, just take the most recent
  if (candidates.length === 0) {
    candidates = sitemapData.allUrls
      .filter((u) => u.lastmod)
      .sort((a, b) => new Date(b.lastmod).getTime() - new Date(a.lastmod).getTime())
      .slice(0, SAMPLE_ARTICLES);
  }

  // If still nothing, grab some URLs at random
  if (candidates.length === 0) {
    candidates = sitemapData.allUrls.slice(0, SAMPLE_ARTICLES);
  }

  log(`Sampling ${candidates.length} article pages...`);

  const results = [];

  for (const entry of candidates) {
    const url = entry.loc;
    log(`  -> ${url}`);

    const { text: html, status } = await fetchText(url);
    if (!html || status !== 200) {
      results.push({ url, status, error: "Could not fetch page" });
      continue;
    }

    const $ = cheerio.load(html);
    const pageResult = {
      url,
      status,
      metaTags: {},
      jsonLd: {},
      markup: {},
    };

    // --- Meta tags ---
    pageResult.metaTags.articlePublishedTime =
      $('meta[property="article:published_time"]').attr("content") || null;
    pageResult.metaTags.articleModifiedTime =
      $('meta[property="article:modified_time"]').attr("content") || null;
    pageResult.metaTags.articleAuthor =
      $('meta[property="article:author"]').attr("content") || null;
    pageResult.metaTags.articleSection =
      $('meta[property="article:section"]').attr("content") || null;
    pageResult.metaTags.articleTag =
      $('meta[property="article:tag"]')
        .map((_, el) => $(el).attr("content"))
        .get() || [];
    pageResult.metaTags.ogType =
      $('meta[property="og:type"]').attr("content") || null;

    // --- JSON-LD structured data ---
    const jsonLdScripts = $('script[type="application/ld+json"]');
    const jsonLdBlocks = [];
    jsonLdScripts.each((_, el) => {
      try {
        const data = JSON.parse($(el).html());
        jsonLdBlocks.push(data);
      } catch (_e) {
        // skip malformed JSON-LD
      }
    });

    pageResult.jsonLd.count = jsonLdBlocks.length;
    pageResult.jsonLd.types = jsonLdBlocks.map(
      (b) => b["@type"] || (b["@graph"] ? "Graph" : "unknown")
    );

    // Look for NewsArticle or Article type (including within @graph)
    let articleSchema = null;
    for (const block of jsonLdBlocks) {
      if (block["@type"] === "NewsArticle" || block["@type"] === "Article") {
        articleSchema = block;
        break;
      }
      if (block["@graph"] && Array.isArray(block["@graph"])) {
        for (const node of block["@graph"]) {
          if (node["@type"] === "NewsArticle" || node["@type"] === "Article") {
            articleSchema = node;
            break;
          }
        }
        if (articleSchema) break;
      }
    }

    if (articleSchema) {
      pageResult.jsonLd.articleType = articleSchema["@type"];
      pageResult.jsonLd.hasHeadline = !!articleSchema.headline;
      pageResult.jsonLd.hasDatePublished = !!articleSchema.datePublished;
      pageResult.jsonLd.hasDateModified = !!articleSchema.dateModified;
      pageResult.jsonLd.hasAuthor = !!articleSchema.author;
      pageResult.jsonLd.hasImage = !!articleSchema.image;
      pageResult.jsonLd.hasPublisher = !!articleSchema.publisher;

      // Check author details
      if (articleSchema.author) {
        const author = Array.isArray(articleSchema.author)
          ? articleSchema.author[0]
          : articleSchema.author;
        pageResult.jsonLd.authorType = author["@type"] || typeof author;
        pageResult.jsonLd.authorName = author.name || author || null;
      }
    } else {
      pageResult.jsonLd.articleType = null;
      pageResult.jsonLd.hasHeadline = false;
      pageResult.jsonLd.hasDatePublished = false;
      pageResult.jsonLd.hasDateModified = false;
      pageResult.jsonLd.hasAuthor = false;
      pageResult.jsonLd.hasImage = false;
      pageResult.jsonLd.hasPublisher = false;
    }

    // --- HTML markup checks ---

    // Author byline
    const bylineSelectors = [
      '[class*="author"]',
      '[class*="byline"]',
      '[rel="author"]',
      '[itemprop="author"]',
      ".author",
      ".byline",
    ];
    let bylineFound = false;
    let bylineText = null;
    for (const sel of bylineSelectors) {
      const el = $(sel).first();
      if (el.length) {
        bylineFound = true;
        bylineText = el.text().trim().substring(0, 100);
        break;
      }
    }
    pageResult.markup.hasAuthorByline = bylineFound;
    pageResult.markup.bylineText = bylineText;

    // <time> elements
    const timeElements = $("time");
    pageResult.markup.timeElementCount = timeElements.length;
    pageResult.markup.timeElements = timeElements
      .map((_, el) => ({
        datetime: $(el).attr("datetime") || null,
        text: $(el).text().trim().substring(0, 60),
      }))
      .get()
      .slice(0, 5);

    // Article tags / categories in HTML
    const categorySelectors = [
      '[class*="category"]',
      '[class*="tag"]',
      '[class*="topic"]',
      '[rel="tag"]',
    ];
    let categoriesFound = [];
    for (const sel of categorySelectors) {
      $(sel).each((_, el) => {
        const text = $(el).text().trim();
        if (text && text.length < 60 && !categoriesFound.includes(text)) {
          categoriesFound.push(text);
        }
      });
    }
    pageResult.markup.categoriesFound = categoriesFound.slice(0, 10);

    results.push(pageResult);
  }

  // Summarize
  const summary = {
    pagesChecked: results.length,
    withPublishedTimeMeta: results.filter((r) => r.metaTags?.articlePublishedTime).length,
    withArticleJsonLd: results.filter(
      (r) => r.jsonLd?.articleType === "NewsArticle" || r.jsonLd?.articleType === "Article"
    ).length,
    withNewsArticleJsonLd: results.filter((r) => r.jsonLd?.articleType === "NewsArticle").length,
    withAuthorByline: results.filter((r) => r.markup?.hasAuthorByline).length,
    withTimeElements: results.filter((r) => r.markup?.timeElementCount > 0).length,
    withCategories: results.filter((r) => r.markup?.categoriesFound?.length > 0).length,
  };

  log(`Pages with article:published_time: ${summary.withPublishedTimeMeta}/${summary.pagesChecked}`);
  log(`Pages with Article/NewsArticle JSON-LD: ${summary.withArticleJsonLd}/${summary.pagesChecked}`);
  log(`Pages with NewsArticle specifically: ${summary.withNewsArticleJsonLd}/${summary.pagesChecked}`);
  log(`Pages with author byline: ${summary.withAuthorByline}/${summary.pagesChecked}`);
  log(`Pages with <time> elements: ${summary.withTimeElements}/${summary.pagesChecked}`);
  log(`Pages with categories/tags: ${summary.withCategories}/${summary.pagesChecked}`);

  return { summary, pages: results };
}

// ---------------------------------------------------------------------------
// 4. Check robots.txt
// ---------------------------------------------------------------------------

async function checkRobotsTxt(sitemapData) {
  console.log("\n[4/5] Checking robots.txt...");

  const { text: robotsTxt, status } = await fetchText(ROBOTS_URL);
  const findings = {
    found: status === 200,
    raw: null,
    sitemapsDeclared: [],
    hasNewsSitemapDeclared: false,
    googlebotNewsRules: [],
    hasGooglebotNewsBlock: false,
  };

  if (!robotsTxt || status !== 200) {
    log("ERROR: Could not fetch robots.txt");
    return findings;
  }

  findings.raw = robotsTxt;
  const lines = robotsTxt.split("\n").map((l) => l.trim());

  // Extract Sitemap: directives
  for (const line of lines) {
    if (/^sitemap\s*:/i.test(line)) {
      const sitemapUrl = line.replace(/^sitemap\s*:\s*/i, "").trim();
      findings.sitemapsDeclared.push(sitemapUrl);
      if (/news/i.test(sitemapUrl)) {
        findings.hasNewsSitemapDeclared = true;
      }
    }
  }

  // Look for Googlebot-News specific rules
  let inGooglebotNews = false;
  for (const line of lines) {
    if (/^user-agent\s*:\s*googlebot-news/i.test(line)) {
      inGooglebotNews = true;
      findings.hasGooglebotNewsBlock = true;
      continue;
    }
    if (inGooglebotNews) {
      if (/^user-agent\s*:/i.test(line) || line === "") {
        inGooglebotNews = false;
        continue;
      }
      findings.googlebotNewsRules.push(line);
    }
  }

  log(`robots.txt found: YES`);
  log(`Sitemap directives: ${findings.sitemapsDeclared.length}`);
  findings.sitemapsDeclared.forEach((s) => log(`  -> ${s}`));
  log(`News sitemap declared in robots.txt: ${findings.hasNewsSitemapDeclared ? "YES" : "NO"}`);
  log(`Googlebot-News specific rules: ${findings.hasGooglebotNewsBlock ? "YES" : "NO"}`);
  if (findings.googlebotNewsRules.length) {
    findings.googlebotNewsRules.forEach((r) => log(`  -> ${r}`));
  }

  return findings;
}

// ---------------------------------------------------------------------------
// 5. Build recommendations
// ---------------------------------------------------------------------------

function buildRecommendations(sitemapFindings, articleFindings, robotsFindings) {
  console.log("\n[5/5] Building recommendations...");

  const recommendations = [];

  // News sitemap
  if (!sitemapFindings.hasNewsSitemap) {
    recommendations.push({
      priority: "HIGH",
      category: "News Sitemap",
      issue: "No dedicated Google News sitemap found",
      recommendation:
        "Create a separate news sitemap (e.g., /sitemap-news.xml) containing only articles published within the last 2 days. Use the Google News sitemap extension namespace (xmlns:news) with required <news:news> tags.",
    });
  }

  if (sitemapFindings.hasNewsSitemap && !sitemapFindings.hasNewsExtensionTags) {
    recommendations.push({
      priority: "HIGH",
      category: "News Sitemap",
      issue: "News sitemap exists but lacks <news:news> extension tags",
      recommendation:
        "Add Google News XML extension tags to each <url> entry: <news:publication> (with <news:name> and <news:language>), <news:publication_date>, and <news:title>.",
    });
  }

  // Lastmod
  const lastmodPct =
    sitemapFindings.totalUrlsInSitemap > 0
      ? (sitemapFindings.urlsWithLastmod / sitemapFindings.totalUrlsInSitemap) * 100
      : 0;
  if (lastmodPct < 90) {
    recommendations.push({
      priority: "MEDIUM",
      category: "Sitemap Quality",
      issue: `Only ${lastmodPct.toFixed(0)}% of sitemap URLs have <lastmod> dates`,
      recommendation:
        "Add accurate <lastmod> dates to all sitemap URLs. Google uses these to prioritize crawling. Ensure they reflect the actual last-modified date of the content.",
    });
  }

  // Recent articles
  if (sitemapFindings.recentArticles.within2Days === 0) {
    recommendations.push({
      priority: "HIGH",
      category: "Freshness",
      issue: "No articles with lastmod within the last 2 days found in sitemap",
      recommendation:
        "Google News requires articles to be published within the last 2 days to appear. Ensure your news sitemap is updated in real-time as articles are published or modified.",
    });
  }

  // Robots.txt
  if (!robotsFindings.hasNewsSitemapDeclared) {
    recommendations.push({
      priority: "HIGH",
      category: "Robots.txt",
      issue: "News sitemap is not declared in robots.txt",
      recommendation:
        "Add a Sitemap: directive to robots.txt pointing to your news sitemap, e.g.:\nSitemap: https://www.vitalcitynyc.org/sitemap-news.xml",
    });
  }

  if (robotsFindings.sitemapsDeclared.length === 0) {
    recommendations.push({
      priority: "MEDIUM",
      category: "Robots.txt",
      issue: "No Sitemap: directives found in robots.txt",
      recommendation:
        "Declare all sitemaps in robots.txt using Sitemap: directives. This helps search engines discover your sitemaps.",
    });
  }

  // Article page checks
  const summary = articleFindings.summary;
  if (summary.pagesChecked > 0) {
    if (summary.withPublishedTimeMeta < summary.pagesChecked) {
      recommendations.push({
        priority: "HIGH",
        category: "Article Meta Tags",
        issue: `Only ${summary.withPublishedTimeMeta}/${summary.pagesChecked} articles have article:published_time meta tag`,
        recommendation:
          'Add <meta property="article:published_time" content="YYYY-MM-DDTHH:MM:SSZ"> to all article pages. This is critical for Google News to determine article recency.',
      });
    }

    if (summary.withNewsArticleJsonLd === 0) {
      recommendations.push({
        priority: "HIGH",
        category: "Structured Data",
        issue: "No articles use NewsArticle JSON-LD schema",
        recommendation:
          'Use @type: "NewsArticle" instead of "Article" in JSON-LD structured data. NewsArticle is the preferred schema type for Google News. Include: headline, datePublished, dateModified, author (with @type: Person and name), image, and publisher.',
      });
    } else if (summary.withNewsArticleJsonLd < summary.pagesChecked) {
      recommendations.push({
        priority: "MEDIUM",
        category: "Structured Data",
        issue: `Only ${summary.withNewsArticleJsonLd}/${summary.pagesChecked} articles use NewsArticle JSON-LD`,
        recommendation:
          'Ensure all article pages use @type: "NewsArticle" in their JSON-LD structured data.',
      });
    }

    if (summary.withArticleJsonLd < summary.pagesChecked) {
      recommendations.push({
        priority: "HIGH",
        category: "Structured Data",
        issue: `Only ${summary.withArticleJsonLd}/${summary.pagesChecked} articles have any Article/NewsArticle JSON-LD`,
        recommendation:
          "Add JSON-LD structured data with @type: NewsArticle to all article pages. Required fields: headline, datePublished, author, image, publisher.",
      });
    }

    if (summary.withAuthorByline < summary.pagesChecked) {
      recommendations.push({
        priority: "MEDIUM",
        category: "Author Attribution",
        issue: `Only ${summary.withAuthorByline}/${summary.pagesChecked} articles have detectable author bylines`,
        recommendation:
          "Ensure all articles have visible author bylines with proper HTML markup (e.g., <span class=\"author\"> or <a rel=\"author\">). Google News prioritizes content with clear authorship.",
      });
    }

    if (summary.withTimeElements < summary.pagesChecked) {
      recommendations.push({
        priority: "MEDIUM",
        category: "Date Markup",
        issue: `Only ${summary.withTimeElements}/${summary.pagesChecked} articles have <time> elements`,
        recommendation:
          "Use HTML5 <time datetime=\"...\"> elements for publication and modification dates. This provides a machine-readable signal for article freshness.",
      });
    }

    if (summary.withCategories < summary.pagesChecked) {
      recommendations.push({
        priority: "LOW",
        category: "Categorization",
        issue: `Only ${summary.withCategories}/${summary.pagesChecked} articles have detectable tags/categories`,
        recommendation:
          "Add visible article tags or categories with proper markup. These help Google News categorize content. Use article:tag and article:section meta properties.",
      });
    }
  }

  // Google News Publisher Center
  recommendations.push({
    priority: "MEDIUM",
    category: "Publisher Center",
    issue: "Google News Publisher Center presence could not be verified programmatically",
    recommendation:
      "Ensure Vital City is registered in Google News Publisher Center (https://publishercenter.google.com). This allows you to control your publication\u2019s appearance in Google News, submit your news sitemap, and set content labels and sections.",
  });

  return recommendations;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  console.log("=".repeat(60));
  console.log("Google News Sitemap Tuner - vitalcitynyc.org");
  console.log("=".repeat(60));

  ensureDataDir();

  // Step 1: Fetch all sitemaps
  const sitemapData = await fetchAllSitemaps();

  // Step 2: Analyze news sitemap compliance
  const sitemapFindings = analyzeNewsSitemap(sitemapData);

  // Step 3: Inspect article pages
  const articleFindings = await inspectArticlePages(sitemapData);

  // Step 4: Check robots.txt
  const robotsFindings = await checkRobotsTxt(sitemapData);

  // Step 5: Build recommendations
  const recommendations = buildRecommendations(sitemapFindings, articleFindings, robotsFindings);

  // Compile output
  const output = {
    meta: {
      site: SITE,
      scanDate: new Date().toISOString(),
      tool: "Google News Sitemap Tuner",
    },
    sitemap: {
      mainSitemap: sitemapData.mainSitemap,
      subSitemapCount: sitemapData.subSitemaps.length,
      subSitemaps: sitemapData.subSitemaps.map((s) => ({
        url: s.url,
        urlCount: s.urlCount,
        isNewsSitemap: s.isNewsSitemap,
        hasNewsExtension: s.hasNewsExtension,
      })),
      totalUrls: sitemapData.allUrls.length,
      dedicatedNewsSitemap: sitemapData.newsSitemap
        ? { url: sitemapData.newsSitemap.url, hasNewsExtension: sitemapData.newsSitemap.hasNewsExtension }
        : null,
    },
    newsSitemapCompliance: sitemapFindings,
    articlePageAudit: articleFindings,
    robotsTxt: {
      found: robotsFindings.found,
      sitemapsDeclared: robotsFindings.sitemapsDeclared,
      hasNewsSitemapDeclared: robotsFindings.hasNewsSitemapDeclared,
      hasGooglebotNewsBlock: robotsFindings.hasGooglebotNewsBlock,
      googlebotNewsRules: robotsFindings.googlebotNewsRules,
    },
    recommendations,
    summary: {
      totalIssues: recommendations.length,
      highPriority: recommendations.filter((r) => r.priority === "HIGH").length,
      mediumPriority: recommendations.filter((r) => r.priority === "MEDIUM").length,
      lowPriority: recommendations.filter((r) => r.priority === "LOW").length,
    },
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`\nResults saved to ${OUTPUT_FILE}`);

  // Print summary
  console.log("\n" + "=".repeat(60));
  console.log("SUMMARY");
  console.log("=".repeat(60));
  console.log(`Total issues found: ${output.summary.totalIssues}`);
  console.log(`  HIGH priority:   ${output.summary.highPriority}`);
  console.log(`  MEDIUM priority: ${output.summary.mediumPriority}`);
  console.log(`  LOW priority:    ${output.summary.lowPriority}`);
  console.log("\nRecommendations:");
  for (const rec of recommendations) {
    console.log(`\n  [${rec.priority}] ${rec.category}`);
    console.log(`  Issue: ${rec.issue}`);
    console.log(`  Fix: ${rec.recommendation.split("\n")[0]}`);
  }
  console.log();
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
