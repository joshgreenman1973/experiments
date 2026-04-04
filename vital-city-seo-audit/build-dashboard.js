#!/usr/bin/env node
/**
 * Generates index.html dashboard from audit.json
 */
const fs = require("fs");
const path = require("path");

const AUDIT_FILE = path.join(__dirname, "data", "audit.json");
const OUTPUT = path.join(__dirname, "index.html");

const data = JSON.parse(fs.readFileSync(AUDIT_FILE, "utf-8"));

function escapeHtml(str) {
  return (str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function scoreColor(score) {
  if (score >= 90) return "#16a34a";
  if (score >= 70) return "#ca8a04";
  return "#dc2626";
}

function scoreBg(score) {
  if (score >= 90) return "#f0fdf4";
  if (score >= 70) return "#fefce8";
  return "#fef2f2";
}

// Summary cards
const pagesWithIssues = data.pages.filter((p) => p.issues.length > 0).length;
const pagesClean = data.pages.filter((p) => p.issues.length === 0 && p.warnings.length === 0).length;

// Issue breakdown for chart
const issueTypes = data.commonIssues.map(([name, count]) => ({ name, count }));
const warningTypes = data.commonWarnings.map(([name, count]) => ({ name, count }));

// Build issue rows
const issueRows = data.commonIssues
  .map(
    ([name, count]) =>
      `<tr><td class="count-cell"><span class="badge badge-error">${count}</span></td><td>${escapeHtml(name)}</td></tr>`
  )
  .join("\n");

const warningRows = data.commonWarnings
  .map(
    ([name, count]) =>
      `<tr><td class="count-cell"><span class="badge badge-warn">${count}</span></td><td>${escapeHtml(name)}</td></tr>`
  )
  .join("\n");

// Duplicate titles
const dupTitleRows = data.duplicateTitles
  .map(
    ([title, urls]) =>
      `<tr>
        <td><code>${escapeHtml(title)}</code></td>
        <td>${urls.length} pages</td>
        <td class="url-list">${urls.map((u) => `<a href="${escapeHtml(u)}" target="_blank">${escapeHtml(u.replace("https://www.vitalcitynyc.org", ""))}</a>`).join("<br>")}</td>
      </tr>`
  )
  .join("\n");

// Page-by-page results
const pageRows = data.pages
  .map((p) => {
    const shortUrl = p.url.replace("https://www.vitalcitynyc.org", "") || "/";
    const allProblems = [
      ...p.issues.map((i) => `<span class="tag tag-error">${escapeHtml(i)}</span>`),
      ...p.warnings.map((w) => `<span class="tag tag-warn">${escapeHtml(w)}</span>`),
    ];
    return `<tr class="page-row" data-score="${p.score}">
      <td class="score-cell" style="color: ${scoreColor(p.score)}; background: ${scoreBg(p.score)}">
        ${p.score}
      </td>
      <td><a href="${escapeHtml(p.url)}" target="_blank">${escapeHtml(shortUrl)}</a></td>
      <td class="problems-cell">${allProblems.join(" ") || '<span class="tag tag-ok">Clean</span>'}</td>
    </tr>`;
  })
  .join("\n");

// Score distribution
const scoreRanges = [
  { label: "90\u2013100", min: 90, max: 100, color: "#16a34a" },
  { label: "70\u201389", min: 70, max: 89, color: "#ca8a04" },
  { label: "50\u201369", min: 50, max: 69, color: "#ea580c" },
  { label: "0\u201349", min: 0, max: 49, color: "#dc2626" },
];
const scoreDist = scoreRanges.map((r) => ({
  ...r,
  count: data.pages.filter((p) => p.score >= r.min && p.score <= r.max).length,
}));
const maxDist = Math.max(...scoreDist.map((d) => d.count), 1);

const distBars = scoreDist
  .map(
    (d) =>
      `<div class="dist-bar-group">
        <div class="dist-label">${d.label}</div>
        <div class="dist-track">
          <div class="dist-bar" style="width: ${Math.round((d.count / maxDist) * 100)}%; background: ${d.color}"></div>
        </div>
        <div class="dist-count">${d.count}</div>
      </div>`
  )
  .join("\n");

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SEO Audit \u2014 vitalcitynyc.org</title>
<style>
  :root {
    --bg: #f8fafc;
    --surface: #ffffff;
    --text: #0f172a;
    --text-secondary: #64748b;
    --border: #e2e8f0;
    --accent: #2563eb;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }
  h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }
  .subtitle { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 2rem; }

  /* Stats */
  .stats { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    flex: 1;
    min-width: 150px;
  }
  .stat-value { font-size: 2rem; font-weight: 700; }
  .stat-label { color: var(--text-secondary); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }

  /* Sections */
  .section { margin-bottom: 2.5rem; }
  .section-title { font-size: 1.15rem; font-weight: 600; margin-bottom: 1rem; }

  /* Score distribution */
  .dist-bar-group { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }
  .dist-label { width: 60px; font-size: 0.85rem; text-align: right; color: var(--text-secondary); }
  .dist-track { flex: 1; height: 24px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
  .dist-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
  .dist-count { width: 30px; font-size: 0.85rem; font-weight: 600; }

  /* Tables */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th {
    text-align: left;
    padding: 0.75rem 1rem;
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    background: #f8fafc;
    border-bottom: 1px solid var(--border);
  }
  td { padding: 0.6rem 1rem; border-bottom: 1px solid var(--border); vertical-align: top; }
  tr:last-child td { border-bottom: none; }

  .count-cell { width: 60px; text-align: center; }
  .score-cell { width: 55px; text-align: center; font-weight: 700; font-size: 0.9rem; border-radius: 4px; }

  .badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.8rem;
  }
  .badge-error { background: #fef2f2; color: #dc2626; }
  .badge-warn { background: #fefce8; color: #ca8a04; }

  .tag {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    font-size: 0.75rem;
    margin: 0.1rem;
    line-height: 1.6;
  }
  .tag-error { background: #fef2f2; color: #dc2626; }
  .tag-warn { background: #fefce8; color: #ca8a04; }
  .tag-ok { background: #f0fdf4; color: #16a34a; }

  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  code { background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.82rem; }
  .url-list a { display: block; font-size: 0.8rem; }

  /* Filters */
  .filter-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; align-items: center; }
  .filter-bar label { font-size: 0.85rem; color: var(--text-secondary); }
  .filter-btn {
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.3rem 0.7rem; font-size: 0.8rem; cursor: pointer; color: var(--text-secondary);
  }
  .filter-btn:hover, .filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }

  .problems-cell { max-width: 500px; }

  /* Responsive */
  @media (max-width: 768px) {
    body { padding: 1rem; }
    .problems-cell { max-width: 250px; }
  }

  /* Two-col layout for issues/warnings */
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  @media (max-width: 768px) { .two-col { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<h1>SEO Audit</h1>
<p class="subtitle">vitalcitynyc.org \u2014 Scanned ${new Date(data.scannedAt).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })} \u2014 ${data.pagesAudited} of ~800 pages</p>

<div class="stats">
  <div class="stat-card">
    <div class="stat-value" style="color: ${scoreColor(data.averageScore)}">${data.averageScore}/100</div>
    <div class="stat-label">Average Score</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" style="color: #dc2626">${data.totalIssues}</div>
    <div class="stat-label">Errors</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" style="color: #ca8a04">${data.totalWarnings}</div>
    <div class="stat-label">Warnings</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" style="color: #16a34a">${pagesClean}</div>
    <div class="stat-label">Clean Pages</div>
  </div>
</div>

<div class="section">
  <div class="section-title">Score Distribution</div>
  <div class="card" style="padding: 1.25rem;">
    ${distBars}
  </div>
</div>

<div class="section two-col">
  <div>
    <div class="section-title">Errors (${data.totalIssues})</div>
    <div class="card">
      <table>
        <thead><tr><th>#</th><th>Issue</th></tr></thead>
        <tbody>${issueRows}</tbody>
      </table>
    </div>
  </div>
  <div>
    <div class="section-title">Warnings (${data.totalWarnings})</div>
    <div class="card">
      <table>
        <thead><tr><th>#</th><th>Warning</th></tr></thead>
        <tbody>${warningRows}</tbody>
      </table>
    </div>
  </div>
</div>

${data.duplicateTitles.length > 0 ? `
<div class="section">
  <div class="section-title">Duplicate Titles</div>
  <div class="card">
    <table>
      <thead><tr><th>Title</th><th>Count</th><th>Pages</th></tr></thead>
      <tbody>${dupTitleRows}</tbody>
    </table>
  </div>
</div>
` : ""}

<div class="section">
  <div class="section-title">Page-by-Page Results</div>
  <div class="filter-bar">
    <label>Show:</label>
    <button class="filter-btn active" onclick="filterPages('all')">All</button>
    <button class="filter-btn" onclick="filterPages('errors')">With Errors</button>
    <button class="filter-btn" onclick="filterPages('warnings')">With Warnings</button>
    <button class="filter-btn" onclick="filterPages('clean')">Clean Only</button>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Score</th><th>Page</th><th>Issues</th></tr></thead>
      <tbody id="page-table">${pageRows}</tbody>
    </table>
  </div>
</div>

<script>
function filterPages(mode) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.page-row').forEach(row => {
    const score = parseInt(row.dataset.score);
    const hasError = row.querySelector('.tag-error');
    const hasWarn = row.querySelector('.tag-warn');
    const isClean = !hasError && !hasWarn;
    if (mode === 'all') row.style.display = '';
    else if (mode === 'errors') row.style.display = hasError ? '' : 'none';
    else if (mode === 'warnings') row.style.display = (hasError || hasWarn) ? '' : 'none';
    else if (mode === 'clean') row.style.display = isClean ? '' : 'none';
  });
}
</script>

</body>
</html>`;

fs.writeFileSync(OUTPUT, html);
console.log(`Dashboard written to ${OUTPUT}`);
