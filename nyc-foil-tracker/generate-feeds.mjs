// Generate RSS feeds from data/requests.json
//
// Outputs:
//   feed.xml                 — newest 100 requests across all agencies
//   feed/<agency-slug>.xml   — newest 50 for the top 20 agencies by volume
//   feed/topic-<slug>.xml    — newest 50 for each topic bucket (must match index.html patterns)
//
// Run after the scraper, or standalone: `node generate-feeds.mjs`

import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync, readdirSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_FILE = join(__dirname, "data", "requests.json");
const FEED_DIR = join(__dirname, "feed");
const SITE_BASE = process.env.FOIL_SITE_BASE || "https://joshgreenman1973.github.io/experiments/nyc-foil-tracker";

// Mirror of TOPIC_PATTERNS in index.html. Keep in sync.
const TOPIC_PATTERNS = [
  { topic: "Police / NYPD records", re: /\b(nypd|police|arrest|misconduct|body\s*cam|disciplin|cciv|ccrb|memo\s*book|aided|complaint\s*report|stop\s*and\s*frisk|use\s*of\s*force|officer)\b/i },
  { topic: "Real estate / property", re: /\b(phase\s*i?\s*esa|environmental\s*due|deed|property|address|block\s*and\s*lot|bbl|c of o|cofo|certificate of occupancy|building\s*permit|dob|c\/o)\b|\b\d+\s+[a-z]+\s+(st|street|ave|avenue|rd|road|blvd|place|pl|court|ct|drive|dr)\b/i },
  { topic: "311 / complaints", re: /\b(311|complaint|service\s*request|sr\s*number)\b/i },
  { topic: "Vehicle / parking / traffic", re: /\b(parking|ticket|summons|vehicle|plate|license\s*plate|tlc|taxi|for\s*hire|rideshare|red\s*light|speed\s*camera|moving\s*violation|traffic|crash|collision)\b/i },
  { topic: "Environmental / DEP", re: /\b(dep\b|environmental|water|sewer|asbestos|lead|air\s*quality|noise)\b/i },
  { topic: "Permits / licenses", re: /\b(permit|license|application|inspection|citation|violation|sla|liquor)\b/i },
  { topic: "Health / DOHMH", re: /\b(dohmh|health|hospital|medical|h\+h|nyc\s*health|restaurant|food\s*safety|asthma|covid|vaccin)\b/i },
  { topic: "Housing / HPD / NYCHA", re: /\b(nycha|hpd|housing|landlord|tenant|eviction|lease|section\s*8|rent\s*stabiliz)\b/i },
  { topic: "Schools / DOE", re: /\b(doe|department of education|school|student|principal|teacher|iep|special education|specialized\s*high|sat|cuny|charter)\b/i },
  { topic: "Personnel / payroll", re: /\b(payroll|salary|employee|personnel|hire|hiring|pension|overtime|termination|resignation|civil\s*service)\b/i },
  { topic: "Corrections / Rikers", re: /\b(rikers|inmate|incarcerat|doc(\b|orrection)|jail|detain|cell\s*extraction)\b/i },
  { topic: "Procurement / contracts", re: /\b(contract|procurement|rfp|rfq|vendor|bid|sole\s*source|m\/wbe|mwbe)\b/i },
  { topic: "Litigation / appeal", re: /\b(litigat|lawsuit|foil\s*appeal|docket|v\.\s+|indictment|case\s*no\.)\b/i },
  { topic: "Migrants / shelters", re: /\b(migrant|asylum|shelter|sanctuary)\b/i },
  { topic: "Budget / spending", re: /\b(budget|spending|expenditure|grant|funding|allocation|appropriat)\b/i },
];

function topicsFor(title) {
  if (!title) return [];
  return TOPIC_PATTERNS.filter(p => p.re.test(title)).map(p => p.topic);
}

function isUnderReview(r) {
  return r.isUnderReview || r.title === "* Under Review";
}

function escapeXml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function rfc822(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toUTCString();
}

function buildFeed({ title, description, link, items }) {
  const now = new Date().toUTCString();
  const itemXml = items.map(r => {
    const url = r.url || `https://a860-openrecords.nyc.gov/request/view/${r.foilId}`;
    const itemTitle = (r.title && r.title !== "* Under Review")
      ? r.title
      : `${r.foilId} (subject pending)`;
    const desc = [
      `Agency: ${r.agency || "—"}`,
      `Status: ${r.status || "—"}`,
      r.determination ? `Determination: ${r.determination}` : null,
      r.dateDue ? `Due: ${rfc822(r.dateDue)}` : null,
      r.determinationMessage ? `Message: ${r.determinationMessage.slice(0, 400)}` : null,
    ].filter(Boolean).join(" | ");
    const cats = topicsFor(r.title).map(t => `    <category>${escapeXml(t)}</category>`).join("\n");
    return `  <item>
    <title>${escapeXml(itemTitle)}</title>
    <link>${escapeXml(url)}</link>
    <guid isPermaLink="false">${escapeXml(r.foilId)}</guid>
    <pubDate>${rfc822(r.dateSubmitted)}</pubDate>
    <description>${escapeXml(desc)}</description>
    ${r.agency ? `<category>${escapeXml(r.agency)}</category>` : ""}
${cats}
  </item>`;
  }).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>${escapeXml(title)}</title>
  <link>${escapeXml(link)}</link>
  <atom:link href="${escapeXml(link)}" rel="self" type="application/rss+xml"/>
  <description>${escapeXml(description)}</description>
  <language>en-us</language>
  <lastBuildDate>${now}</lastBuildDate>
${itemXml}
</channel>
</rss>
`;
}

function main() {
  if (!existsSync(DATA_FILE)) {
    console.error(`Data file not found: ${DATA_FILE}`);
    process.exit(1);
  }
  const data = JSON.parse(readFileSync(DATA_FILE, "utf-8"));
  const visible = data.requests.filter(r => !isUnderReview(r) && r.title);
  const sorted = [...visible].sort((a, b) => (b.dateSubmitted || "").localeCompare(a.dateSubmitted || ""));

  // Reset feed dir
  if (existsSync(FEED_DIR)) {
    for (const f of readdirSync(FEED_DIR)) {
      if (f.endsWith(".xml")) rmSync(join(FEED_DIR, f));
    }
  } else {
    mkdirSync(FEED_DIR, { recursive: true });
  }

  // Master feed
  const master = buildFeed({
    title: "NYC FOIL Tracker — newest requests",
    description: "Newest freedom-of-information requests filed through NYC OpenRecords",
    link: `${SITE_BASE}/feed.xml`,
    items: sorted.slice(0, 100),
  });
  writeFileSync(join(__dirname, "feed.xml"), master);
  console.log(`Wrote feed.xml (${Math.min(100, sorted.length)} items)`);

  // Per-agency: top 20 by volume
  const agencyCounts = {};
  visible.forEach(r => {
    if (!r.agency) return;
    agencyCounts[r.agency] = (agencyCounts[r.agency] || 0) + 1;
  });
  const topAgencies = Object.entries(agencyCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([name]) => name);

  for (const agency of topAgencies) {
    const items = sorted.filter(r => r.agency === agency).slice(0, 50);
    if (items.length === 0) continue;
    const slug = slugify(agency);
    const file = join(FEED_DIR, `${slug}.xml`);
    const xml = buildFeed({
      title: `NYC FOIL Tracker — ${agency}`,
      description: `Newest FOIL requests filed to ${agency}`,
      link: `${SITE_BASE}/feed/${slug}.xml`,
      items,
    });
    writeFileSync(file, xml);
    console.log(`Wrote feed/${slug}.xml (${items.length} items, agency: ${agency})`);
  }

  // Per-topic
  for (const { topic } of TOPIC_PATTERNS) {
    const items = sorted.filter(r => topicsFor(r.title).includes(topic)).slice(0, 50);
    if (items.length === 0) continue;
    const slug = `topic-${slugify(topic)}`;
    const file = join(FEED_DIR, `${slug}.xml`);
    const xml = buildFeed({
      title: `NYC FOIL Tracker — ${topic}`,
      description: `Newest FOIL requests tagged ${topic}`,
      link: `${SITE_BASE}/feed/${slug}.xml`,
      items,
    });
    writeFileSync(file, xml);
    console.log(`Wrote feed/${slug}.xml (${items.length} items)`);
  }

  // Index of feeds
  const indexLines = [
    "# NYC FOIL Tracker — RSS Feeds",
    "",
    `Generated ${new Date().toISOString()}`,
    "",
    `**Master:** ${SITE_BASE}/feed.xml`,
    "",
    "## By agency (top 20)",
    "",
    ...topAgencies.map(a => `- [${a}](${SITE_BASE}/feed/${slugify(a)}.xml)`),
    "",
    "## By topic",
    "",
    ...TOPIC_PATTERNS.map(({ topic }) => `- [${topic}](${SITE_BASE}/feed/topic-${slugify(topic)}.xml)`),
  ];
  writeFileSync(join(FEED_DIR, "INDEX.md"), indexLines.join("\n"));
  console.log("Wrote feed/INDEX.md");
}

main();
