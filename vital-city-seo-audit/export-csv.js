#!/usr/bin/env node
/**
 * Export all audit data to CSVs for Google Sheets import.
 * Run: node export-csv.js
 * Output: csv/ directory with all files
 */

const fs = require("fs");
const path = require("path");

const CSV_DIR = path.join(__dirname, "csv");
if (!fs.existsSync(CSV_DIR)) fs.mkdirSync(CSV_DIR, { recursive: true });

function csvEscape(val) {
  if (val == null) return "";
  const str = String(val);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

function writeCsv(filename, headers, rows) {
  const lines = [headers.map(csvEscape).join(",")];
  for (const row of rows) {
    lines.push(row.map(csvEscape).join(","));
  }
  const fp = path.join(CSV_DIR, filename);
  fs.writeFileSync(fp, lines.join("\n"));
  console.log(`  \u2713 ${filename} (${rows.length} rows)`);
}

// -------------------------------------------------------------------------
// 1. SEO Audit
// -------------------------------------------------------------------------
console.log("\n1. SEO Audit");
const audit = JSON.parse(fs.readFileSync("data/audit.json", "utf-8"));

writeCsv("seo-audit-pages.csv",
  ["Score", "URL", "Title", "Meta Description", "Errors", "Warnings"],
  audit.pages.map((p) => [
    p.score,
    p.url.replace("https://www.vitalcitynyc.org", ""),
    p.info?.title || "",
    p.info?.description || "",
    (p.issues || []).join("; "),
    (p.warnings || []).join("; "),
  ])
);

writeCsv("seo-audit-summary.csv",
  ["Type", "Issue", "Count"],
  [
    ...audit.commonIssues.map(([issue, count]) => ["Error", issue, count]),
    ...audit.commonWarnings.map(([w, count]) => ["Warning", w, count]),
  ]
);

// -------------------------------------------------------------------------
// 2. Google News Sitemap
// -------------------------------------------------------------------------
console.log("\n2. Google News Sitemap");
const news = JSON.parse(fs.readFileSync("data/news-sitemap.json", "utf-8"));

writeCsv("news-sitemap-recommendations.csv",
  ["Priority", "Issue", "Fix", "Details"],
  (news.recommendations || []).map((r) => [
    r.priority || "",
    r.issue || r.title || "",
    r.fix || r.recommendation || r.description || "",
    r.details || "",
  ])
);

// Article-level checks
const articleChecks = news.articleChecks || news.articles || news.articleAnalysis || [];
if (articleChecks.length > 0) {
  writeCsv("news-sitemap-articles.csv",
    ["URL", "Has Published Time", "Has JSON-LD", "JSON-LD Type", "Has Time Element", "Has Author"],
    articleChecks.map((a) => [
      (a.url || "").replace("https://www.vitalcitynyc.org", ""),
      a.hasPublishedTime ?? a.articlePublishedTime ?? "",
      a.hasJsonLd ?? a.hasStructuredData ?? "",
      a.jsonLdType ?? a.structuredDataType ?? "",
      a.hasTimeElement ?? "",
      a.hasAuthor ?? a.hasAuthorByline ?? "",
    ])
  );
}

// -------------------------------------------------------------------------
// 3. Internal Links
// -------------------------------------------------------------------------
console.log("\n3. Internal Links");
const links = JSON.parse(fs.readFileSync("data/internal-links.json", "utf-8"));

// Orphan pages
writeCsv("internal-links-orphans.csv",
  ["URL", "Note"],
  (links.orphanPages || []).map((p) => {
    const url = typeof p === "string" ? p : p.url || "";
    return [url.replace("https://www.vitalcitynyc.org", ""), "No inbound internal links from crawled pages"];
  })
);

// Low inbound pages
writeCsv("internal-links-low-inbound.csv",
  ["URL", "Inbound Link Count", "Linked From"],
  (links.lowInboundPages || []).map((p) => [
    (p.url || "").replace("https://www.vitalcitynyc.org", ""),
    p.inboundCount ?? p.count ?? "",
    (p.sources || p.linkedFrom || []).map(s => (typeof s === "string" ? s : s.url || "").replace("https://www.vitalcitynyc.org", "")).join("; "),
  ])
);

// Cross-link suggestions
writeCsv("internal-links-suggestions.csv",
  ["Page A", "Page B", "Shared Tags", "Reason"],
  (links.crossLinkSuggestions || []).map((s) => {
    const a = typeof s.pageA === "object" ? s.pageA.url : (s.pageA || s.source || s.from || "");
    const b = typeof s.pageB === "object" ? s.pageB.url : (s.pageB || s.target || s.to || "");
    const tags = s.sharedTags || s.commonTags || [];
    return [
      String(a).replace("https://www.vitalcitynyc.org", ""),
      String(b).replace("https://www.vitalcitynyc.org", ""),
      tags.join(", "),
      `${tags.length} shared tags`,
    ];
  })
);

// Hub pages
const hubs = links.hubPages || links.hubs || [];
if (hubs.length > 0) {
  writeCsv("internal-links-hubs.csv",
    ["URL", "Outbound Link Count"],
    hubs.map((h) => [
      (typeof h === "string" ? h : (h.url || "")).replace("https://www.vitalcitynyc.org", ""),
      h.outboundCount ?? h.count ?? "",
    ])
  );
}

// -------------------------------------------------------------------------
// 4. Content Gaps
// -------------------------------------------------------------------------
console.log("\n4. Content Gaps");
const gaps = JSON.parse(fs.readFileSync("data/content-gaps.json", "utf-8"));

// Topic coverage overview
const topicInv = gaps.topicInventory || {};
const topicRows = Object.entries(topicInv)
  .map(([key, val]) => [
    val.label || key,
    val.articleCount || 0,
    val.coverageDepth || 0,
    (val.subtopicsCovered || []).join(", "),
    (val.uncoveredSubtopics || []).join(", "),
  ])
  .sort((a, b) => a[2] - b[2]); // sort by coverage depth ascending (worst first)

writeCsv("content-gaps-coverage.csv",
  ["Topic", "Article Count", "Coverage Depth (0-100)", "Subtopics Covered", "Subtopics Missing"],
  topicRows
);

// Gap details
writeCsv("content-gaps-gaps.csv",
  ["Topic", "Coverage Depth", "Article Count", "Uncovered Subtopics"],
  (gaps.gaps || []).map((g) => [
    g.label || g.topic || "",
    g.coverageDepth || 0,
    g.articleCount || 0,
    (g.uncoveredSubtopics || []).join(", "),
  ])
);

// Recommendations
writeCsv("content-gaps-recommendations.csv",
  ["Priority", "Topic", "Reason", "Suggested Subtopics"],
  (gaps.recommendations || []).map((r) => [
    r.priority || "",
    r.topic || "",
    r.reason || "",
    (r.suggestedSubtopics || []).join(", "),
  ])
);

// Competitor comparison
const compTopics = gaps.competitorTopics || {};
const compRows = [];
for (const [outlet, topics] of Object.entries(compTopics)) {
  if (typeof topics === "object" && !Array.isArray(topics)) {
    for (const [topic, info] of Object.entries(topics)) {
      compRows.push([outlet, topic, info.articleCount || info.count || (Array.isArray(info) ? info.length : "")]);
    }
  }
}
if (compRows.length > 0) {
  writeCsv("content-gaps-competitors.csv",
    ["Outlet", "Topic", "Article Count"],
    compRows
  );
}

console.log(`\n\u2705 All CSVs exported to ${CSV_DIR}/`);
