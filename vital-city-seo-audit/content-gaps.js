#!/usr/bin/env node

/**
 * Content Gap Scanner for vitalcitynyc.org
 *
 * Fetches article pages from the sitemap, extracts topics and tags,
 * then compares coverage against a curated list of NYC policy topics
 * and competitor RSS feeds to identify content gaps.
 *
 * Run: node content-gaps.js
 * Output: data/content-gaps.json
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
const SITEMAP_POSTS = `${SITE}/sitemap-posts.xml`;
const DATA_DIR = path.join(__dirname, "data");
const OUTPUT_FILE = path.join(DATA_DIR, "content-gaps.json");
const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const MAX_ARTICLES = 60;
const DELAY_MS = 300;

const COMPETITOR_FEEDS = [
  { name: "THE CITY", url: "https://www.thecity.nyc/feed/" },
  { name: "Gothamist", url: "https://gothamist.com/feed" },
  { name: "City Limits", url: "https://citylimits.org/feed/" },
];

// ---------------------------------------------------------------------------
// Curated NYC policy topic taxonomy
// ---------------------------------------------------------------------------

const POLICY_TOPICS = {
  housing: {
    label: "Housing",
    subtopics: [
      "rent stabilization",
      "NYCHA",
      "homelessness",
      "shelters",
      "affordable housing",
      "zoning",
      "eviction",
      "housing vouchers",
      "public housing",
      "tenant protections",
      "housing court",
      "accessory dwelling units",
    ],
    keywords: [
      "rent", "housing", "nycha", "homeless", "shelter", "affordable",
      "zoning", "eviction", "tenant", "landlord", "voucher", "apartment",
      "dwelling", "rezoning", "house", "unhoused",
    ],
  },
  public_safety: {
    label: "Public Safety",
    subtopics: [
      "policing",
      "gun violence",
      "hate crimes",
      "domestic violence",
      "recidivism",
      "Rikers",
      "bail reform",
      "crime prevention",
      "community violence intervention",
      "police oversight",
      "stop and frisk",
      "gang violence",
    ],
    keywords: [
      "police", "policing", "gun", "shooting", "crime", "violence",
      "rikers", "bail", "recidivism", "jail", "prison", "incarcerat",
      "safety", "murder", "homicide", "assault", "hate crime", "domestic violence",
      "nypd", "corrections", "criminal justice", "victim",
    ],
  },
  education: {
    label: "Education",
    subtopics: [
      "school choice",
      "charter schools",
      "literacy",
      "special education",
      "college access",
      "DOE budget",
      "pre-K",
      "school segregation",
      "teacher shortage",
      "school safety",
      "absenteeism",
      "gifted and talented",
    ],
    keywords: [
      "school", "education", "student", "teacher", "literacy", "charter",
      "college", "doe", "pre-k", "classroom", "learning", "academic",
      "graduation", "dropout", "special ed", "curriculum", "university",
    ],
  },
  transportation: {
    label: "Transportation",
    subtopics: [
      "congestion pricing",
      "bus lanes",
      "bike safety",
      "MTA funding",
      "subway service",
      "pedestrian safety",
      "street design",
      "accessibility",
      "commuter rail",
      "e-bikes and scooters",
      "traffic fatalities",
      "Vision Zero",
    ],
    keywords: [
      "transit", "transportation", "mta", "subway", "bus", "bike",
      "congestion", "traffic", "commut", "pedestrian", "street",
      "cyclist", "lane", "vision zero", "citibike", "ferry",
    ],
  },
  health: {
    label: "Health",
    subtopics: [
      "mental health",
      "opioid crisis",
      "Medicaid",
      "maternal mortality",
      "lead poisoning",
      "public hospitals",
      "health insurance",
      "COVID long-term effects",
      "overdose prevention",
      "health equity",
      "food insecurity",
      "tobacco and vaping",
    ],
    keywords: [
      "health", "mental", "opioid", "fentanyl", "overdose", "medicaid",
      "hospital", "maternal", "lead", "clinic", "doctor", "patient",
      "drug", "addiction", "treatment", "insurance", "disease",
      "wellness", "suicide", "therapy",
    ],
  },
  climate_environment: {
    label: "Climate & Environment",
    subtopics: [
      "flooding",
      "heat deaths",
      "air quality",
      "environmental justice",
      "coastal resilience",
      "green buildings",
      "urban tree canopy",
      "waste and recycling",
      "clean energy",
      "environmental review",
      "superfund sites",
      "water quality",
    ],
    keywords: [
      "climate", "flood", "heat", "air quality", "environment",
      "coastal", "resilience", "green", "emission", "carbon",
      "tree", "waste", "recycl", "energy", "solar", "wind",
      "storm", "hurricane", "sea level", "pollution", "toxic",
    ],
  },
  economy: {
    label: "Economy",
    subtopics: [
      "small business",
      "workforce development",
      "minimum wage",
      "gig economy",
      "inequality",
      "poverty",
      "economic development",
      "commercial vacancies",
      "union labor",
      "cost of living",
      "childcare costs",
      "tech industry",
    ],
    keywords: [
      "economy", "economic", "business", "workforce", "wage", "gig",
      "inequality", "poverty", "job", "employ", "worker", "labor",
      "income", "cost of living", "childcare", "union", "commercial",
      "startup", "industry",
    ],
  },
  government: {
    label: "Government & Accountability",
    subtopics: [
      "city budget",
      "FOIL transparency",
      "ethics",
      "campaign finance",
      "city council oversight",
      "mayoral power",
      "public authorities",
      "lobbying",
      "procurement",
      "agency performance",
      "inspector general",
      "voter participation",
    ],
    keywords: [
      "budget", "foil", "transparency", "ethics", "campaign finance",
      "city council", "mayor", "government", "oversight", "lobby",
      "procurement", "agency", "accountability", "audit", "election",
      "voter", "ballot", "comptroller", "inspector general",
    ],
  },
  immigration: {
    label: "Immigration",
    subtopics: [
      "asylum seekers",
      "sanctuary city",
      "workforce integration",
      "ICE enforcement",
      "deportation",
      "immigration courts",
      "language access",
      "migrant shelters",
      "work permits",
      "unaccompanied minors",
      "DACA",
      "immigrant small business",
    ],
    keywords: [
      "immigra", "asylum", "migrant", "sanctuary", "ice",
      "deportat", "refugee", "undocument", "border", "visa",
      "daca", "newcomer", "language access",
    ],
  },
  technology: {
    label: "Technology & Surveillance",
    subtopics: [
      "surveillance",
      "AI in government",
      "digital divide",
      "broadband access",
      "facial recognition",
      "algorithmic bias",
      "smart city",
      "data privacy",
      "open data",
      "cybersecurity",
      "edtech",
      "govtech",
    ],
    keywords: [
      "technology", "surveillance", "ai ", "artificial intelligence",
      "digital", "broadband", "internet", "facial recognition",
      "algorithm", "data", "cyber", "tech", "smart city",
      "automation", "privacy",
    ],
  },
  youth_families: {
    label: "Youth & Families",
    subtopics: [
      "child welfare",
      "foster care",
      "youth employment",
      "after-school programs",
      "child poverty",
      "juvenile justice",
      "youth mental health",
      "child abuse",
      "family court",
      "runaway youth",
      "youth violence prevention",
      "summer programs",
    ],
    keywords: [
      "child", "youth", "foster", "family", "teen", "adolescent",
      "juvenile", "young people", "after-school", "kid", "parent",
      "welfare", "summer youth", "baby", "infant", "toddler",
      "daycare",
    ],
  },
};

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
    const text = await res.text();
    return { text, status: res.status };
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Normalize text for keyword matching: lowercase, collapse whitespace.
 */
function norm(text) {
  return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

/**
 * Check whether a keyword appears in the given text.
 * Handles partial matches (e.g. "immigra" matches "immigration").
 */
function keywordMatch(keyword, text) {
  return text.includes(keyword.toLowerCase());
}

// ---------------------------------------------------------------------------
// Sitemap: collect article URLs
// ---------------------------------------------------------------------------

async function getArticleUrls() {
  const articleUrls = [];

  // Try the sitemap index first
  console.log("Fetching sitemap index...");
  try {
    const { text: indexXml } = await fetchText(SITEMAP_INDEX);
    const index = await xml2js.parseStringPromise(indexXml, { explicitArray: false });

    const sitemaps = Array.isArray(index.sitemapindex?.sitemap)
      ? index.sitemapindex.sitemap
      : [index.sitemapindex?.sitemap].filter(Boolean);

    for (const sm of sitemaps) {
      const loc = sm.loc;
      // We want posts/articles, skip authors, tags, etc.
      if (loc.includes("authors") || loc.includes("tags")) continue;
      console.log(`  Fetching ${loc}...`);
      try {
        const { text: smXml } = await fetchText(loc);
        const parsed = await xml2js.parseStringPromise(smXml, { explicitArray: false });
        const urls = Array.isArray(parsed.urlset?.url)
          ? parsed.urlset.url
          : [parsed.urlset?.url].filter(Boolean);
        for (const u of urls) {
          articleUrls.push(u.loc);
        }
      } catch (err) {
        console.log(`    Error fetching sub-sitemap: ${err.message}`);
      }
      await delay(DELAY_MS);
    }
  } catch (err) {
    console.log(`  Error fetching sitemap index: ${err.message}`);
  }

  // Also try the posts sitemap directly (may overlap, will deduplicate)
  console.log("Fetching sitemap-posts.xml...");
  try {
    const { text: postsXml } = await fetchText(SITEMAP_POSTS);
    const parsed = await xml2js.parseStringPromise(postsXml, { explicitArray: false });
    const urls = Array.isArray(parsed.urlset?.url)
      ? parsed.urlset.url
      : [parsed.urlset?.url].filter(Boolean);
    for (const u of urls) {
      articleUrls.push(u.loc);
    }
  } catch (err) {
    console.log(`  Error fetching sitemap-posts.xml: ${err.message}`);
  }

  // Deduplicate and filter to article-like paths
  const unique = [...new Set(articleUrls)].filter((url) => {
    const p = new URL(url).pathname;
    // Skip homepage, tag pages, author pages, category pages
    if (p === "/" || p === "") return false;
    if (p.startsWith("/tag/") || p.startsWith("/tags/")) return false;
    if (p.startsWith("/author/") || p.startsWith("/authors/")) return false;
    if (p.startsWith("/category/") || p.startsWith("/categories/")) return false;
    return true;
  });

  console.log(`  Found ${unique.length} unique article URLs`);
  return unique;
}

// ---------------------------------------------------------------------------
// Article extraction
// ---------------------------------------------------------------------------

function extractArticleData(url, html) {
  const $ = cheerio.load(html);

  const title = $("title").text().trim();
  const metaDesc = $('meta[name="description"]').attr("content")?.trim() || "";
  const ogTitle = $('meta[property="og:title"]').attr("content")?.trim() || "";
  const ogDesc = $('meta[property="og:description"]').attr("content")?.trim() || "";

  // Extract tags/categories from multiple sources
  const tags = new Set();

  // 1. Meta keywords
  const metaKeywords = $('meta[name="keywords"]').attr("content") || "";
  metaKeywords.split(",").forEach((k) => {
    const t = k.trim().toLowerCase();
    if (t) tags.add(t);
  });

  // 2. JSON-LD structured data
  $('script[type="application/ld+json"]').each((_, el) => {
    try {
      const ld = JSON.parse($(el).html());
      // May be an array or single object
      const items = Array.isArray(ld) ? ld : [ld];
      for (const item of items) {
        if (item.keywords) {
          const kws = Array.isArray(item.keywords)
            ? item.keywords
            : item.keywords.split(",");
          kws.forEach((k) => {
            const t = k.trim().toLowerCase();
            if (t) tags.add(t);
          });
        }
        if (item.articleSection) {
          const sections = Array.isArray(item.articleSection)
            ? item.articleSection
            : [item.articleSection];
          sections.forEach((s) => tags.add(s.trim().toLowerCase()));
        }
        // Check @graph array (common in Yoast/schema plugins)
        if (item["@graph"]) {
          for (const node of item["@graph"]) {
            if (node.keywords) {
              const kws = Array.isArray(node.keywords)
                ? node.keywords
                : node.keywords.split(",");
              kws.forEach((k) => {
                const t = k.trim().toLowerCase();
                if (t) tags.add(t);
              });
            }
            if (node.articleSection) {
              const sections = Array.isArray(node.articleSection)
                ? node.articleSection
                : [node.articleSection];
              sections.forEach((s) => tags.add(s.trim().toLowerCase()));
            }
          }
        }
      }
    } catch {}
  });

  // 3. Visible tag/category links on the page
  $('a[href*="/tag/"], a[href*="/tags/"], a[href*="/category/"], a[href*="/topics/"]').each(
    (_, el) => {
      const text = $(el).text().trim().toLowerCase();
      if (text && text.length < 60) tags.add(text);
    }
  );

  // 4. Article:tag meta (used by some sites)
  $('meta[property="article:tag"]').each((_, el) => {
    const t = ($(el).attr("content") || "").trim().toLowerCase();
    if (t) tags.add(t);
  });

  // 5. Article:section meta
  $('meta[property="article:section"]').each((_, el) => {
    const t = ($(el).attr("content") || "").trim().toLowerCase();
    if (t) tags.add(t);
  });

  // Build combined text for keyword matching
  const bodyText = $("article").text() || $("main").text() || "";
  const combinedText = norm(
    [title, ogTitle, metaDesc, ogDesc, [...tags].join(" "), bodyText].join(" ")
  );

  return {
    url,
    title: title || ogTitle || "(untitled)",
    description: metaDesc || ogDesc || "",
    tags: [...tags],
    combinedText,
  };
}

// ---------------------------------------------------------------------------
// Topic matching
// ---------------------------------------------------------------------------

function matchArticleToTopics(article) {
  const matched = {};
  const text = article.combinedText;

  for (const [topicId, topic] of Object.entries(POLICY_TOPICS)) {
    let score = 0;
    const matchedKeywords = [];
    const matchedSubtopics = [];

    // Check keywords
    for (const kw of topic.keywords) {
      if (keywordMatch(kw, text)) {
        score++;
        matchedKeywords.push(kw);
      }
    }

    // Check subtopics (more specific, weighted higher)
    for (const sub of topic.subtopics) {
      if (keywordMatch(sub.toLowerCase(), text)) {
        score += 2;
        matchedSubtopics.push(sub);
      }
    }

    // Check tags
    for (const tag of article.tags) {
      for (const kw of topic.keywords) {
        if (keywordMatch(kw, tag)) {
          score += 2;
          break;
        }
      }
    }

    if (score >= 3) {
      matched[topicId] = { score, matchedKeywords, matchedSubtopics };
    }
  }

  return matched;
}

// ---------------------------------------------------------------------------
// Competitor RSS feed parsing
// ---------------------------------------------------------------------------

async function fetchCompetitorTopics() {
  const competitors = [];

  for (const feed of COMPETITOR_FEEDS) {
    console.log(`  Fetching ${feed.name} RSS...`);
    try {
      const { text: rssXml } = await fetchText(feed.url);
      const parsed = await xml2js.parseStringPromise(rssXml, { explicitArray: false });

      const channel = parsed.rss?.channel || parsed.feed || {};
      const items = Array.isArray(channel.item)
        ? channel.item
        : [channel.item].filter(Boolean);

      const articles = [];
      for (const item of items.slice(0, 50)) {
        const title = typeof item.title === "string" ? item.title : item.title?._ || "";
        const desc =
          item.description ||
          item["content:encoded"] ||
          item.summary ||
          "";
        const rawDesc = typeof desc === "string" ? desc : "";

        // Extract categories
        const cats = [];
        if (item.category) {
          const rawCats = Array.isArray(item.category)
            ? item.category
            : [item.category];
          for (const c of rawCats) {
            const catText = typeof c === "string" ? c : c._ || c.$ && c.$.term || "";
            if (catText) cats.push(catText.toLowerCase().trim());
          }
        }

        const combinedText = norm([title, rawDesc.replace(/<[^>]+>/g, ""), cats.join(" ")].join(" "));

        // Match to topics
        const matched = {};
        for (const [topicId, topic] of Object.entries(POLICY_TOPICS)) {
          let score = 0;
          for (const kw of topic.keywords) {
            if (keywordMatch(kw, combinedText)) score++;
          }
          for (const sub of topic.subtopics) {
            if (keywordMatch(sub.toLowerCase(), combinedText)) score += 2;
          }
          if (score >= 3) {
            matched[topicId] = score;
          }
        }

        articles.push({ title, categories: cats, topics: matched });
      }

      competitors.push({
        name: feed.name,
        articleCount: articles.length,
        articles,
      });
    } catch (err) {
      console.log(`    Error: ${err.message}`);
      competitors.push({ name: feed.name, articleCount: 0, articles: [], error: err.message });
    }
    await delay(DELAY_MS);
  }

  return competitors;
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

function analyzeGaps(articles, competitors) {
  // Build topic inventory for Vital City
  const topicInventory = {};
  for (const [topicId, topic] of Object.entries(POLICY_TOPICS)) {
    topicInventory[topicId] = {
      label: topic.label,
      articleCount: 0,
      articles: [],
      subtopicCoverage: {},
    };
    for (const sub of topic.subtopics) {
      topicInventory[topicId].subtopicCoverage[sub] = 0;
    }
  }

  // Count coverage
  for (const article of articles) {
    const matched = matchArticleToTopics(article);
    for (const [topicId, match] of Object.entries(matched)) {
      topicInventory[topicId].articleCount++;
      topicInventory[topicId].articles.push({
        url: article.url,
        title: article.title,
        matchScore: match.score,
      });
      for (const sub of match.matchedSubtopics) {
        if (topicInventory[topicId].subtopicCoverage[sub] !== undefined) {
          topicInventory[topicId].subtopicCoverage[sub]++;
        }
      }
    }
  }

  // Compute coverage depth scores (0-100)
  const maxArticles = Math.max(
    ...Object.values(topicInventory).map((t) => t.articleCount),
    1
  );
  for (const [topicId, inv] of Object.entries(topicInventory)) {
    const topic = POLICY_TOPICS[topicId];
    const articleScore = Math.min(inv.articleCount / maxArticles, 1) * 50;
    const coveredSubtopics = Object.values(inv.subtopicCoverage).filter(
      (c) => c > 0
    ).length;
    const subtopicScore =
      (coveredSubtopics / topic.subtopics.length) * 50;
    inv.coverageDepth = Math.round(articleScore + subtopicScore);
  }

  // Identify gaps
  const gaps = [];
  for (const [topicId, inv] of Object.entries(topicInventory)) {
    const uncoveredSubtopics = Object.entries(inv.subtopicCoverage)
      .filter(([, count]) => count === 0)
      .map(([sub]) => sub);
    const weakSubtopics = Object.entries(inv.subtopicCoverage)
      .filter(([, count]) => count === 1)
      .map(([sub]) => sub);

    if (inv.articleCount === 0 || uncoveredSubtopics.length > 0) {
      gaps.push({
        topicId,
        label: inv.label,
        articleCount: inv.articleCount,
        coverageDepth: inv.coverageDepth,
        uncoveredSubtopics,
        weakSubtopics,
        severity:
          inv.articleCount === 0
            ? "no coverage"
            : uncoveredSubtopics.length > inv.subtopicCoverage
              ? "major gaps"
              : "minor gaps",
      });
    }
  }
  gaps.sort((a, b) => a.coverageDepth - b.coverageDepth);

  // Competitor comparison: what do competitors cover that VC doesn't
  const competitorTopics = {};
  for (const comp of competitors) {
    const compTopicCounts = {};
    for (const article of comp.articles) {
      for (const topicId of Object.keys(article.topics)) {
        compTopicCounts[topicId] = (compTopicCounts[topicId] || 0) + 1;
      }
    }
    competitorTopics[comp.name] = compTopicCounts;
  }

  // Find topics competitors cover more heavily
  const competitorAdvantages = [];
  for (const [topicId, inv] of Object.entries(topicInventory)) {
    for (const [compName, compCounts] of Object.entries(competitorTopics)) {
      const compCount = compCounts[topicId] || 0;
      if (compCount > 0 && inv.articleCount <= 2) {
        competitorAdvantages.push({
          topic: inv.label,
          topicId,
          competitor: compName,
          competitorArticles: compCount,
          vitalCityArticles: inv.articleCount,
        });
      }
    }
  }
  // Deduplicate by topic, merging competitors
  const mergedAdvantages = {};
  for (const adv of competitorAdvantages) {
    if (!mergedAdvantages[adv.topicId]) {
      mergedAdvantages[adv.topicId] = {
        topic: adv.topic,
        topicId: adv.topicId,
        vitalCityArticles: adv.vitalCityArticles,
        competitors: [],
      };
    }
    mergedAdvantages[adv.topicId].competitors.push({
      name: adv.competitor,
      articleCount: adv.competitorArticles,
    });
  }

  // Generate recommendations
  const recommendations = [];

  // 1. Zero-coverage topics
  for (const gap of gaps.filter((g) => g.articleCount === 0)) {
    recommendations.push({
      priority: "high",
      topic: gap.label,
      reason: `No articles found covering ${gap.label}. This is a core NYC policy area.`,
      suggestedSubtopics: gap.uncoveredSubtopics.slice(0, 5),
    });
  }

  // 2. Topics competitors cover but VC doesn't
  for (const [, adv] of Object.entries(mergedAdvantages)) {
    const compNames = adv.competitors.map((c) => c.name).join(", ");
    if (adv.vitalCityArticles === 0) {
      recommendations.push({
        priority: "high",
        topic: adv.topic,
        reason: `${compNames} actively cover this area but Vital City has no articles.`,
        competitorCoverage: adv.competitors,
      });
    }
  }

  // 3. Undertreated subtopics in otherwise-covered areas
  for (const gap of gaps.filter((g) => g.articleCount > 0)) {
    if (gap.uncoveredSubtopics.length >= 3) {
      recommendations.push({
        priority: "medium",
        topic: gap.label,
        reason: `${gap.uncoveredSubtopics.length} subtopics never covered despite ${gap.articleCount} articles in this area.`,
        suggestedSubtopics: gap.uncoveredSubtopics,
      });
    }
  }

  // 4. Weak subtopics
  for (const gap of gaps.filter((g) => g.weakSubtopics.length >= 2)) {
    recommendations.push({
      priority: "low",
      topic: gap.label,
      reason: `${gap.weakSubtopics.length} subtopics covered only once, suggesting shallow treatment.`,
      suggestedSubtopics: gap.weakSubtopics,
    });
  }

  // Deduplicate recommendations by topic, keeping highest priority
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  const seen = new Set();
  const dedupedRecs = [];
  recommendations.sort(
    (a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]
  );
  for (const rec of recommendations) {
    const key = `${rec.priority}-${rec.topic}`;
    if (!seen.has(key)) {
      seen.add(key);
      dedupedRecs.push(rec);
    }
  }

  return { topicInventory, gaps, competitorTopics: Object.values(mergedAdvantages), recommendations: dedupedRecs };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  ensureDataDir();
  console.log("Content Gap Scanner for vitalcitynyc.org\n");

  // Step 1: Get article URLs from sitemap
  const allUrls = await getArticleUrls();
  const urlsToFetch = allUrls.slice(0, MAX_ARTICLES);

  console.log(`\nFetching ${urlsToFetch.length} article pages...\n`);

  // Step 2: Fetch and extract article data
  const articles = [];
  for (let i = 0; i < urlsToFetch.length; i++) {
    const url = urlsToFetch[i];
    try {
      const { text: html } = await fetchText(url);
      const article = extractArticleData(url, html);
      articles.push(article);
      console.log(
        `  [${i + 1}/${urlsToFetch.length}] ${article.title.slice(0, 70)}${article.title.length > 70 ? "\u2026" : ""}`
      );
    } catch (err) {
      console.log(`  [${i + 1}/${urlsToFetch.length}] Error: ${url} - ${err.message}`);
    }
    await delay(DELAY_MS);
  }

  console.log(`\nExtracted data from ${articles.length} articles.`);

  // Step 3: Fetch competitor feeds
  console.log("\nFetching competitor RSS feeds...\n");
  const competitors = await fetchCompetitorTopics();

  // Step 4: Analyze gaps
  console.log("\nAnalyzing content gaps...\n");
  const results = analyzeGaps(articles, competitors);

  // Step 5: Print summary
  console.log("=== TOPIC COVERAGE SUMMARY ===\n");
  const sorted = Object.entries(results.topicInventory).sort(
    (a, b) => b[1].coverageDepth - a[1].coverageDepth
  );
  for (const [, inv] of sorted) {
    const bar = "\u2588".repeat(Math.round(inv.coverageDepth / 5)) +
                "\u2591".repeat(20 - Math.round(inv.coverageDepth / 5));
    console.log(
      `  ${inv.label.padEnd(28)} ${bar} ${inv.coverageDepth}/100  (${inv.articleCount} articles)`
    );
  }

  console.log("\n=== TOP GAPS ===\n");
  for (const gap of results.gaps.slice(0, 8)) {
    console.log(`  ${gap.label} (depth: ${gap.coverageDepth}/100, ${gap.articleCount} articles)`);
    if (gap.uncoveredSubtopics.length > 0) {
      console.log(`    Missing: ${gap.uncoveredSubtopics.slice(0, 5).join(", ")}`);
    }
  }

  console.log("\n=== COMPETITOR ADVANTAGES ===\n");
  for (const adv of results.competitorTopics.slice(0, 6)) {
    const compList = adv.competitors
      .map((c) => `${c.name} (${c.articleCount})`)
      .join(", ");
    console.log(
      `  ${adv.topic}: VC has ${adv.vitalCityArticles} articles vs. ${compList}`
    );
  }

  console.log(`\n=== RECOMMENDATIONS (${results.recommendations.length} total) ===\n`);
  for (const rec of results.recommendations.slice(0, 10)) {
    const icon = rec.priority === "high" ? "!!!" : rec.priority === "medium" ? " !!" : "  !";
    console.log(`  [${icon}] ${rec.topic}: ${rec.reason}`);
    if (rec.suggestedSubtopics) {
      console.log(`        Suggested: ${rec.suggestedSubtopics.slice(0, 4).join(", ")}`);
    }
  }

  // Step 6: Save results (strip combinedText from articles to keep file size down)
  const output = {
    site: SITE,
    scannedAt: new Date().toISOString(),
    articlesScanned: articles.length,
    totalArticleUrls: allUrls.length,
    topicInventory: results.topicInventory,
    gaps: results.gaps,
    competitorTopics: results.competitorTopics,
    recommendations: results.recommendations,
    articleIndex: articles.map((a) => ({
      url: a.url,
      title: a.title,
      tags: a.tags,
    })),
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));
  console.log(`\nResults saved to ${OUTPUT_FILE}`);
}

main().catch(console.error);
