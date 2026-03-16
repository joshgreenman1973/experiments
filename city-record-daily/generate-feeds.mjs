#!/usr/bin/env node
// Generates RSS/Atom feeds from City Record Digest JSON data files.
// Run after updating data: node generate-feeds.mjs

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

const DATA_DIR = join(import.meta.dirname, 'data');
const FEEDS_DIR = join(import.meta.dirname, 'feeds');
const SITE_URL = 'https://joshgreenman1973.github.io/experiments/city-record-daily';
const RECORD_BASE = 'https://a856-cityrecord.nyc.gov/RequestDetail/';

mkdirSync(FEEDS_DIR, { recursive: true });

// Load manifest and recent data
const manifest = JSON.parse(readFileSync(join(DATA_DIR, 'manifest.json'), 'utf8'));
const recentDates = manifest.slice(0, 30); // last 30 days

const allDays = [];
for (const date of recentDates) {
  const fp = join(DATA_DIR, `${date}.json`);
  if (!existsSync(fp)) continue;
  try {
    allDays.push(JSON.parse(readFileSync(fp, 'utf8')));
  } catch { /* skip bad files */ }
}

// Collect all notable + watching items with their dates
const allItems = [];
for (const day of allDays) {
  const date = day.date;
  for (const item of (day.notable || [])) {
    allItems.push({ ...item, pubDate: date, priority: 'notable' });
  }
  for (const item of (day.watching || [])) {
    allItems.push({ ...item, pubDate: date, priority: 'watching' });
  }
}

// Also collect all notices for section/agency feeds
const allNotices = [];
for (const day of allDays) {
  for (const n of (day.notices || [])) {
    allNotices.push({ ...n, pubDate: day.date });
  }
}

function escXml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtMoney(n) {
  if (!n) return '';
  const num = typeof n === 'string' ? parseFloat(n) : n;
  if (isNaN(num)) return '';
  if (num >= 1e6) return '$' + (num / 1e6).toFixed(1) + 'M';
  if (num >= 1e3) return '$' + (num / 1e3).toFixed(0) + 'K';
  return '$' + num.toLocaleString();
}

function toRfc822(dateStr) {
  return new Date(dateStr + 'T08:00:00-05:00').toUTCString();
}

function slugify(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

function buildRssFeed({ title, description, link, feedUrl, items }) {
  const lastBuild = items.length > 0 ? toRfc822(items[0].pubDate) : toRfc822(new Date().toISOString().slice(0, 10));

  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>${escXml(title)}</title>
  <description>${escXml(description)}</description>
  <link>${escXml(link)}</link>
  <atom:link href="${escXml(feedUrl)}" rel="self" type="application/rss+xml"/>
  <lastBuildDate>${lastBuild}</lastBuildDate>
  <language>en-us</language>
`;

  for (const item of items.slice(0, 100)) {
    const itemLink = RECORD_BASE + item.request_id;
    const agency = item.agency_name || '';
    const section = item.section_name || '';
    const amount = item.contract_amount ? ` | ${fmtMoney(item.contract_amount)}` : '';
    const desc = item.summary
      ? `${item.summary}\n\n${agency} | ${section}${amount}`
      : `${agency} | ${section} | ${item.type_of_notice_description || ''}${amount}`;

    xml += `  <item>
    <title>${escXml(item.short_title || 'Untitled Notice')}</title>
    <link>${escXml(itemLink)}</link>
    <guid isPermaLink="true">${escXml(itemLink)}</guid>
    <pubDate>${toRfc822(item.pubDate)}</pubDate>
    <description>${escXml(desc)}</description>
    <category>${escXml(section)}</category>
  </item>
`;
  }

  xml += `</channel>
</rss>`;
  return xml;
}

// 1. Main feed — all notable items
writeFileSync(
  join(import.meta.dirname, 'feed.xml'),
  buildRssFeed({
    title: 'City Record Digest',
    description: 'Notable NYC government notices — procurement, hearings, rules, and more',
    link: SITE_URL,
    feedUrl: SITE_URL + '/feed.xml',
    items: allItems
  })
);
console.log(`Main feed: ${allItems.length} items`);

// 2. Section feeds
const sections = {};
for (const n of allNotices) {
  const sec = n.section_name || 'Other';
  if (!sections[sec]) sections[sec] = [];
  sections[sec].push(n);
}

const sectionIndex = {};
for (const [secName, notices] of Object.entries(sections)) {
  const slug = slugify(secName);
  const filename = `${slug}.xml`;
  writeFileSync(
    join(FEEDS_DIR, filename),
    buildRssFeed({
      title: `City Record Digest — ${secName}`,
      description: `NYC City Record ${secName} notices`,
      link: SITE_URL,
      feedUrl: `${SITE_URL}/feeds/${filename}`,
      items: notices
    })
  );
  sectionIndex[secName] = filename;
  console.log(`Section feed "${secName}": ${notices.length} items → feeds/${filename}`);
}

// 3. Agency feeds for key agencies
const KEY_AGENCIES = {
  'NYCHA': ['Housing Authority'],
  'HPD': ['Housing Preservation'],
  'DOE': ['Education'],
  'NYPD': ['Police'],
  'DOC': ['Correction'],
  'DHS': ['Homeless Services'],
  'ACS': ['Children\'s Services'],
  'OMB': ['Management and Budget'],
  'City Planning': ['City Planning'],
  'Health + Hospitals': ['Health and Hospitals', 'Health + Hospitals'],
  'DEP': ['Environmental Protection'],
  'DOT': ['Transportation'],
  'Parks': ['Parks and Recreation'],
  'DCAS': ['Citywide Administrative Services'],
  'HRA-DSS': ['Social Svcs', 'Human Resources Administration'],
};

const agencyIndex = {};
for (const [label, keywords] of Object.entries(KEY_AGENCIES)) {
  const matching = allNotices.filter(n => {
    const name = (n.agency_name || '').toLowerCase();
    return keywords.some(kw => name.includes(kw.toLowerCase()));
  });
  if (matching.length === 0) continue;
  const slug = slugify(label);
  const filename = `agency-${slug}.xml`;
  writeFileSync(
    join(FEEDS_DIR, filename),
    buildRssFeed({
      title: `City Record Digest — ${label}`,
      description: `NYC City Record notices for ${label}`,
      link: SITE_URL,
      feedUrl: `${SITE_URL}/feeds/${filename}`,
      items: matching
    })
  );
  agencyIndex[label] = filename;
  console.log(`Agency feed "${label}": ${matching.length} items → feeds/${filename}`);
}

// 4. Write feed index for the site UI
const feedIndex = {
  main: { title: 'All Notable Developments', url: 'feed.xml', count: allItems.length },
  sections: Object.entries(sectionIndex).map(([name, file]) => ({
    name, url: `feeds/${file}`, count: sections[name].length
  })).sort((a, b) => b.count - a.count),
  agencies: Object.entries(agencyIndex).map(([name, file]) => ({
    name,
    url: `feeds/${file}`,
    count: allNotices.filter(n => {
      const nm = (n.agency_name || '').toLowerCase();
      return KEY_AGENCIES[name].some(kw => nm.includes(kw.toLowerCase()));
    }).length
  })).sort((a, b) => b.count - a.count)
};

writeFileSync(join(import.meta.dirname, 'feed-index.json'), JSON.stringify(feedIndex, null, 2));
console.log('\nFeed index written to feed-index.json');
console.log(`Total: 1 main + ${Object.keys(sectionIndex).length} section + ${Object.keys(agencyIndex).length} agency feeds`);
