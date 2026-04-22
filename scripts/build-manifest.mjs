#!/usr/bin/env node
// Scans ~/Experiments and writes projects-manifest.json used by projects.html.
// Run manually: node scripts/build-manifest.mjs
// Also wired to a git post-commit hook so it refreshes automatically.

import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { join } from 'path';

const ROOT = '/Users/joshgreenman/Experiments';

// Per-project overrides for live URLs that aren't default github.io/<repo>/
let OVERRIDES = {};
try {
  OVERRIDES = JSON.parse(readFileSync(join(ROOT, 'project-overrides.json'), 'utf8'));
} catch {}
function applyOverrides(record) {
  const o = OVERRIDES[record.name];
  if (!o) return record;
  if (o.skip) return null; // excluded from gallery entirely
  if (o.liveUrl) {
    record.livePagesUrl = o.liveUrl;
    // liveUrl also sets preview unless a separate previewUrl is given
    if (!o.previewUrl) record.previewUrl = o.liveUrl;
  }
  if (o.previewUrl) record.previewUrl = o.previewUrl;
  if (o.description) record.description = o.description;
  if (o.status) record.status = o.status;
  return record;
}
const CATEGORY_DIRS = new Set(['nyc-data', 'vital-city-tools', 'personal', '_archive', 'world']);
const SKIP = new Set(['.git', '.claude', '.github', '.netlify', '.agents', 'node_modules', 'scripts', '.DS_Store']);

function sh(cmd, cwd) {
  try {
    return execSync(cmd, { cwd, encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }).trim();
  } catch {
    return '';
  }
}

function readText(path, cap = 50000) {
  try { return readFileSync(path, 'utf8').slice(0, cap); } catch { return ''; }
}

// Decode HTML entities (both named and numeric) so titles/descriptions
// don't render the literal &mdash; / &amp; / etc. in the gallery.
const NAMED_ENTITIES = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'",
  nbsp: ' ', hellip: '…', mdash: '—', ndash: '–',
  copy: '©', reg: '®', trade: '™',
  ldquo: '\u201c', rdquo: '\u201d', lsquo: '\u2018', rsquo: '\u2019',
  laquo: '«', raquo: '»', deg: '°', sect: '§', para: '¶',
  times: '×', divide: '÷', plusmn: '±',
};
function decodeEntities(s) {
  if (!s) return s;
  return s
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => { try { return String.fromCodePoint(parseInt(h, 16)); } catch { return _; } })
    .replace(/&#(\d+);/g, (_, n) => { try { return String.fromCodePoint(parseInt(n, 10)); } catch { return _; } })
    .replace(/&([a-z][a-z0-9]+);/gi, (m, n) => NAMED_ENTITIES[n.toLowerCase()] ?? m);
}

function extractTitle(htmlPath) {
  const html = readText(htmlPath);
  const t = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  if (t) return decodeEntities(t[1].replace(/\s+/g, ' ').trim());
  const h1 = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
  if (h1) return decodeEntities(h1[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 120));
  return null;
}

function extractReadmeDesc(dir) {
  for (const name of ['README.md', 'readme.md', 'README.txt']) {
    const p = join(dir, name);
    if (!existsSync(p)) continue;
    const text = readText(p, 4000);
    const lines = text.split('\n');
    for (const line of lines) {
      const t = line.trim();
      if (!t) continue;
      if (t.startsWith('#') || t.startsWith('!') || t.startsWith('[!') || t.startsWith('<')) continue;
      return decodeEntities(t.slice(0, 240));
    }
  }
  return null;
}

function parseGhRemote(remote) {
  if (!remote) return null;
  const m = remote.match(/github\.com[:/]([^/]+)\/([^/.\s]+?)(?:\.git)?$/);
  return m ? { owner: m[1], repo: m[2] } : null;
}

function ghWebUrl(remote) {
  const p = parseGhRemote(remote);
  return p ? `https://github.com/${p.owner}/${p.repo}` : null;
}

function ghPagesUrl(remote) {
  const p = parseGhRemote(remote);
  return p ? `https://${p.owner}.github.io/${p.repo}/` : null;
}

function ghOwner(remote) {
  const p = parseGhRemote(remote);
  return p ? p.owner : null;
}

// Cache homepage lookups so we only hit the GitHub API once per repo per build
const homepageCache = new Map();
function getGhHomepage(remote) {
  const p = parseGhRemote(remote);
  if (!p) return null;
  const key = `${p.owner}/${p.repo}`;
  if (homepageCache.has(key)) return homepageCache.get(key);
  const out = sh(`gh api repos/${key} --jq .homepage`, ROOT);
  const val = out && out !== 'null' ? out : null;
  homepageCache.set(key, val);
  return val;
}

function getGitInfo(dir) {
  if (existsSync(join(dir, '.git'))) {
    const remote = sh('git config --get remote.origin.url', dir);
    return {
      isNested: true,
      remote,
      homepage: getGhHomepage(remote),
      lastCommit: sh('git log -1 --format=%cI', dir),
      lastCommitMsg: sh('git log -1 --format=%s', dir),
    };
  }
  // Fall back to parent repo history for this path
  const rel = dir.replace(ROOT + '/', '');
  return {
    isNested: false,
    remote: sh('git config --get remote.origin.url', ROOT),
    lastCommit: sh(`git log -1 --format=%cI -- "${rel}"`, ROOT),
    lastCommitMsg: sh(`git log -1 --format=%s -- "${rel}"`, ROOT),
  };
}

function latestMtime(dir, depth = 2) {
  let latest = 0;
  function walk(d, lvl) {
    if (lvl > depth) return;
    let entries;
    try { entries = readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of entries) {
      if (SKIP.has(e.name) || e.name.startsWith('.')) continue;
      const p = join(d, e.name);
      try {
        const s = statSync(p);
        if (s.mtimeMs > latest) latest = s.mtimeMs;
        if (e.isDirectory()) walk(p, lvl + 1);
      } catch {}
    }
  }
  walk(dir, 0);
  return latest ? new Date(latest).toISOString() : null;
}

function isProject(dir) {
  try { if (!statSync(dir).isDirectory()) return false; } catch { return false; }
  return existsSync(join(dir, 'index.html')) ||
         existsSync(join(dir, '.git')) ||
         existsSync(join(dir, 'README.md')) ||
         existsSync(join(dir, 'package.json'));
}

function projectRecord(fullPath, category) {
  const name = fullPath.split('/').pop();
  // Prefer built dist/index.html over root index.html when the root is a
  // Vite/SPA dev entrypoint (references /src/ modules that don't exist statically).
  const distIndex = join(fullPath, 'dist', 'index.html');
  const rootIndex = join(fullPath, 'index.html');
  let indexPath = null;
  if (existsSync(rootIndex)) {
    const head = readText(rootIndex, 4000);
    const looksLikeViteDev = /src=["']\/?src\/[^"']+\.(jsx?|tsx?|mjs)["']/.test(head);
    if (looksLikeViteDev && existsSync(distIndex)) indexPath = distIndex;
    else indexPath = rootIndex;
  } else if (existsSync(distIndex)) {
    indexPath = distIndex;
  }
  const hasIndex = !!indexPath;
  const git = getGitInfo(fullPath);
  const relPath = fullPath.replace(ROOT + '/', '');
  const indexUrl = hasIndex ? `./${indexPath.replace(ROOT + '/', '')}` : null;
  // For nested repos, prefer the GitHub "homepage" field (set via repo settings)
  // which points to the actual deployment (Vercel, custom domain, etc.).
  // Fall back to the default github.io/<repo>/ pattern.
  const livePagesUrl = git.isNested
    ? (git.homepage || ghPagesUrl(git.remote))
    : null;
  // Preview URL works both locally (file://) and when served from Pages:
  // - For nested repos: use their own live URL (absolute, works anywhere)
  // - For parent-repo projects: use relative path (resolves locally and on Pages)
  const previewUrl = livePagesUrl || indexUrl;
  return applyOverrides({
    name,
    title: (hasIndex && extractTitle(indexPath)) || name,
    description: extractReadmeDesc(fullPath),
    category,
    localPath: fullPath,
    relPath,
    hasIndex,
    indexUrl,
    previewUrl,
    github: ghWebUrl(git.remote),
    githubOwner: ghOwner(git.remote),
    livePagesUrl,
    isNestedRepo: git.isNested,
    gitRemote: git.remote || null,
    lastCommit: git.lastCommit || null,
    lastCommitMsg: git.lastCommitMsg || null,
    lastModified: latestMtime(fullPath),
  });
}

function scan() {
  const out = [];
  const entries = readdirSync(ROOT, { withFileTypes: true });
  for (const e of entries) {
    if (SKIP.has(e.name) || e.name.startsWith('.')) continue;
    const full = join(ROOT, e.name);
    if (e.isDirectory()) {
      if (CATEGORY_DIRS.has(e.name)) {
        // Recurse one level into category folders
        const inner = readdirSync(full, { withFileTypes: true });
        for (const ie of inner) {
          if (!ie.isDirectory() || SKIP.has(ie.name) || ie.name.startsWith('.')) continue;
          const innerFull = join(full, ie.name);
          if (isProject(innerFull)) { const r = projectRecord(innerFull, e.name); if (r) out.push(r); }
          // One more level for personal/world/
          else if (ie.name === 'world') {
            const w = readdirSync(innerFull, { withFileTypes: true });
            for (const we of w) {
              if (!we.isDirectory() || SKIP.has(we.name) || we.name.startsWith('.')) continue;
              const wf = join(innerFull, we.name);
              if (isProject(wf)) { const r = projectRecord(wf, `${e.name}/world`); if (r) out.push(r); }
            }
          }
        }
      } else if (isProject(full)) {
        { const r = projectRecord(full, 'root'); if (r) out.push(r); }
      }
    } else if (e.isFile() && e.name.endsWith('.html') && e.name !== 'index.html' && e.name !== 'projects.html') {
      const title = extractTitle(full) || e.name;
      const rel = e.name;
      const lastCommit = sh(`git log -1 --format=%cI -- "${rel}"`, ROOT);
      const lastCommitMsg = sh(`git log -1 --format=%s -- "${rel}"`, ROOT);
      const stat = statSync(full);
      out.push({
        name: e.name.replace(/\.html$/, ''),
        title,
        description: null,
        category: 'root',
        localPath: full,
        relPath: rel,
        hasIndex: true,
        indexUrl: `./${rel}`,
        previewUrl: `./${rel}`,
        github: ghWebUrl(sh('git config --get remote.origin.url', ROOT)),
        githubOwner: ghOwner(sh('git config --get remote.origin.url', ROOT)),
        livePagesUrl: null,
        isNestedRepo: false,
        gitRemote: null,
        lastCommit: lastCommit || null,
        lastCommitMsg: lastCommitMsg || null,
        lastModified: new Date(stat.mtimeMs).toISOString(),
        isLooseFile: true,
      });
    }
  }
  return out;
}

const projects = scan();
projects.sort((a, b) => (b.lastModified || '').localeCompare(a.lastModified || ''));

const manifest = {
  generatedAt: new Date().toISOString(),
  count: projects.length,
  categories: [...new Set(projects.map(p => p.category))].sort(),
  owners: [...new Set(projects.map(p => p.githubOwner).filter(Boolean))].sort(),
  projects,
};

writeFileSync(join(ROOT, 'projects-manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`Wrote projects-manifest.json — ${projects.length} projects`);
