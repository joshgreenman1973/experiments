#!/usr/bin/env node
// Scans ~/Experiments and writes projects-manifest.json used by projects.html.
// Run manually: node scripts/build-manifest.mjs
// Also wired to a git post-commit hook so it refreshes automatically.

import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { pbkdf2Sync, createCipheriv, createHash } from 'crypto';
import { join } from 'path';

// Resolve ROOT dynamically so the script works both locally (~/Experiments)
// and in CI (the runner's checkout path). The script lives at <ROOT>/scripts.
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

// Per-project overrides for live URLs that aren't default github.io/<repo>/
let OVERRIDES = {};
try {
  OVERRIDES = JSON.parse(readFileSync(join(ROOT, 'project-overrides.json'), 'utf8'));
} catch {}
// Subcategory: four buckets used to group the General view.
// Tools & feeds checked first (federal-register-daily would otherwise hit
// "wider world" via "federal"). Override per-project via project-overrides.json.
function classifySubcategory(p) {
  const text = [p.name, p.title, p.description].filter(Boolean).join(' ').toLowerCase();
  if (/\b(register[- ]?daily|record[- ]?daily|scanner|data[- ]?finder|story[- ]?finder|news[- ]?engine|open[- ]?data[- ]?weekly|foil[- ]?tracker|daily data)\b/.test(text)) {
    return 'Tools & feeds';
  }
  if (/\b(world|global|federal|scotus|america|americans|national|nationwide|countries|country|paris|france|tokyo|london|seoul|saint[- ]?sernin|nvdrs|u\.?s\.?|usa|supreme court)\b/.test(text)) {
    return 'The wider world';
  }
  if (/\b(time[- ]machine|menus?|bagels?|donuts?|talent[- ]show|ginos?|family[- ]dinner|movies?|good[- ]time|knit|animal[- ]adventure|library|paris density|midnight)\b/.test(text)) {
    return 'Fun stuff';
  }
  return 'Cities';
}

// Polish level — rough first pass from whether the project has a real
// description. Josh refines in the admin. Tiers match the "alphas and betas"
// framing: beta (presentable) / alpha / pre-alpha (early).
function classifyPolish(p) {
  // Conservative auto-pass: a real description earns 'beta', everything else
  // defaults to 'alpha'. Never auto-assigns 'pre-alpha' — Josh marks the
  // genuinely rough ones himself in the admin.
  // Every project now has a written description, so length is no longer a useful
  // polish signal. Default to 'alpha'; Josh promotes to 'beta' / demotes to
  // 'pre-alpha' per-project in the admin.
  return 'alpha';
}

// Audience classification for the tabbed UI.
const VC_OWNERS = new Set(['vitalcity-nyc', 'vital-city-nyc']);
const PERSONAL_NAMES = new Set([
  'family-tree', 'mauro-family-tree', 'sashas-animal-adventure', 'knitshift',
  'lolas-library', 'greenman-portfolio', 'gallery-cool-stuff', 'france-trip',
  'paris-density', 'midnight-talent-show', 'midnight-talent-show-2',
  'midnight-talent-show-book-one', 'saint-sernin-du-plain',
]);
const PROFESSIONAL_NAMES = new Set(['the-ai-city-preview']);
function classifyAudience(p) {
  if (PROFESSIONAL_NAMES.has(p.name)) return 'professional';
  if (VC_OWNERS.has(p.githubOwner)) return 'professional';
  const text = [p.title, p.description].filter(Boolean).join(' ');
  if (/vital\s*city/i.test(text)) return 'professional';
  if (p.category === 'vital-city-tools') return 'professional';
  if (p.category === 'personal' || (p.category || '').startsWith('personal/')) return 'personal';
  if (PERSONAL_NAMES.has(p.name)) return 'personal';
  return 'general';
}

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
  if (o.title) record.title = o.title;
  if (o.description) record.description = o.description;
  if (o.status) record.status = o.status;
  if (o.audience) record.audience = o.audience;
  if (o.subcategory) record.subcategory = o.subcategory;
  if (o.polish) record.polish = o.polish;
  if (o.featured) record.featured = true;
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
      // First commit (creation) — `--reverse | head -1` returns the oldest.
      created: sh("git log --reverse --format=%cI 2>/dev/null | head -1", dir),
    };
  }
  // Fall back to parent repo history for this path
  const rel = dir.replace(ROOT + '/', '');
  return {
    isNested: false,
    remote: sh('git config --get remote.origin.url', ROOT),
    lastCommit: sh(`git log -1 --format=%cI -- "${rel}"`, ROOT),
    lastCommitMsg: sh(`git log -1 --format=%s -- "${rel}"`, ROOT),
    created: sh(`git log --reverse --format=%cI -- "${rel}" 2>/dev/null | head -1`, ROOT),
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
    // For nested repos, github is the project's own repo. For parent-tracked
    // projects (folders inside the experiments monorepo), point at the
    // tree view of that folder rather than the bare experiments repo.
    github: git.isNested
      ? ghWebUrl(git.remote)
      : ghWebUrl(git.remote) + '/tree/main/' + relPath,
    githubOwner: ghOwner(git.remote),
    livePagesUrl,
    isNestedRepo: git.isNested,
    gitRemote: git.remote || null,
    lastCommit: git.lastCommit || null,
    lastCommitMsg: git.lastCommitMsg || null,
    lastModified: git.lastCommit || null,
    created: git.created || null,
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
    } else if (e.isFile() && e.name.endsWith('.html') && !['index.html', 'projects.html', 'admin.html'].includes(e.name)) {
      const title = extractTitle(full) || e.name;
      const rel = e.name;
      const lastCommit = sh(`git log -1 --format=%cI -- "${rel}"`, ROOT);
      const lastCommitMsg = sh(`git log -1 --format=%s -- "${rel}"`, ROOT);
      const created = sh(`git log --reverse --format=%cI -- "${rel}" 2>/dev/null | head -1`, ROOT);
      const looseRec = applyOverrides({
        name: e.name.replace(/\.html$/, ''),
        title,
        description: null,
        category: 'root',
        localPath: full,
        relPath: rel,
        hasIndex: true,
        indexUrl: `./${rel}`,
        previewUrl: `./${rel}`,
        // Loose HTML at root: link to the file in the parent repo's tree view.
        github: ghWebUrl(sh('git config --get remote.origin.url', ROOT)) + '/blob/main/' + rel,
        githubOwner: ghOwner(sh('git config --get remote.origin.url', ROOT)),
        livePagesUrl: null,
        isNestedRepo: false,
        gitRemote: null,
        lastCommit: lastCommit || null,
        lastCommitMsg: lastCommitMsg || null,
        lastModified: lastCommit || null,
        created: created || null,
        isLooseFile: true,
      });
      if (looseRec) out.push(looseRec);
    }
  }
  return out;
}

// ===== GitHub API discovery =====
// Pulls every repo on Josh's three accounts that has Pages enabled, so anything
// pushed to GitHub Pages shows up automatically — no local clone required.
// Runs alongside the local-folder scan and dedupes by repo name (local entries
// win when both exist, since they're richer).

const GH_OWNERS = ['joshgreenman1973', 'vitalcity-nyc', 'vital-city-nyc'];
const GH_HEADERS = {
  'User-Agent': 'experiments-manifest-builder',
  'Accept': 'application/vnd.github+json',
  ...(process.env.GITHUB_TOKEN ? { 'Authorization': 'Bearer ' + process.env.GITHUB_TOKEN } : {}),
};

async function ghJson(path) {
  const url = path.startsWith('http') ? path : `https://api.github.com/${path}`;
  const res = await fetch(url, { headers: GH_HEADERS });
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`GitHub API ${res.status} ${res.statusText} for ${url}`);
  }
  return res.json();
}

async function listOwnerRepos(owner) {
  const all = [];
  for (const path of [`orgs/${owner}/repos`, `users/${owner}/repos`]) {
    let page = 1;
    while (page <= 5) {
      const batch = await ghJson(`${path}?per_page=100&page=${page}&type=public`).catch(() => null);
      if (!Array.isArray(batch) || !batch.length) break;
      all.push(...batch);
      if (batch.length < 100) break;
      page++;
    }
    if (all.length) break;
  }
  return all;
}

async function discoverViaGitHub() {
  const out = [];
  for (const owner of GH_OWNERS) {
    let repos;
    try { repos = await listOwnerRepos(owner); }
    catch (e) { console.warn(`  (skipping ${owner}: ${e.message})`); continue; }
    for (const r of repos) {
      if (!r.has_pages) continue;
      if (r.full_name === 'joshgreenman1973/experiments') continue;
      if (r.archived) continue;
      const liveUrl = r.homepage || `https://${owner}.github.io/${r.name}/`;
      // Run through applyOverrides so featured/audience/polish/skip work for
      // repos that exist only on GitHub (never cloned locally).
      const rec = applyOverrides({
        name: r.name,
        title: r.description || r.name,
        description: r.description || null,
        category: 'remote',
        localPath: null,
        relPath: null,
        hasIndex: true,
        indexUrl: null,
        previewUrl: liveUrl,
        github: r.html_url,
        githubOwner: owner,
        livePagesUrl: liveUrl,
        isNestedRepo: true,
        gitRemote: r.clone_url,
        lastCommit: r.pushed_at,
        lastCommitMsg: null,
        lastModified: r.pushed_at,
        created: r.created_at,
        _source: 'github-api',
      });
      if (rec) out.push(rec);
    }
  }
  return out;
}

async function buildProjectList() {
  const local = scan();
  console.log(`  local scan: ${local.length} projects`);
  let remote = [];
  try {
    remote = await discoverViaGitHub();
    console.log(`  github api: ${remote.length} pages-enabled repos`);
  } catch (e) {
    console.warn('  github api discovery skipped:', e.message);
  }
  // Dedupe by name. Local entries win because they have richer metadata
  // (HTML titles, README descriptions, parent-tracked file paths).
  const byName = new Map();
  for (const p of [...remote, ...local]) byName.set(p.name, p);
  return [...byName.values()];
}

let projects = await buildProjectList();

// Dedupe: when the same project name appears in multiple locations
// (e.g. at root AND inside a category folder, from an incomplete reorg),
// prefer the nested-repo copy; otherwise prefer the more-recently-modified one.
const byName = new Map();
for (const p of projects) {
  const existing = byName.get(p.name);
  if (!existing) { byName.set(p.name, p); continue; }
  const pick = (() => {
    if (p.isNestedRepo && !existing.isNestedRepo) return p;
    if (existing.isNestedRepo && !p.isNestedRepo) return existing;
    return (p.lastModified || '') > (existing.lastModified || '') ? p : existing;
  })();
  byName.set(p.name, pick);
}
projects = [...byName.values()];

// Manual entries — local-only projects that aren't on GitHub Pages and can't
// be auto-discovered. Defined in project-overrides.json with `"manual": true`.
// They get listed (title, description, copy-path) but have no preview/Open link.
const presentNames = new Set(projects.map(p => p.name));
for (const [name, o] of Object.entries(OVERRIDES)) {
  if (name === '_comment' || !o || !o.manual) continue;
  if (presentNames.has(name)) continue;
  const rec = applyOverrides({
    name,
    title: o.title || name,
    description: null,
    category: 'manual',
    localPath: o.localPath || null,
    relPath: null,
    hasIndex: false,
    indexUrl: null,
    previewUrl: null,
    github: null,
    githubOwner: null,
    livePagesUrl: null,
    isNestedRepo: false,
    gitRemote: null,
    lastCommit: null,
    lastCommitMsg: null,
    lastModified: null,
    created: null,
    localOnly: true,
    _source: 'manual',
  });
  if (rec) projects.push(rec);
}

// Sort newest-first by lastModified, with name as a stable tiebreaker so the
// output is fully deterministic (otherwise two projects sharing a timestamp
// could swap order between runs and dirty the manifest).
projects.sort((a, b) => {
  const cmp = (b.lastModified || '').localeCompare(a.lastModified || '');
  return cmp !== 0 ? cmp : (a.name || '').localeCompare(b.name || '');
});

// Classify each project's audience, subcategory, polish (unless overridden)
for (const p of projects) {
  if (!p.audience) p.audience = classifyAudience(p);
  if (!p.subcategory) p.subcategory = classifySubcategory(p);
  if (!p.polish) p.polish = classifyPolish(p);
}
const general = projects.filter(p => p.audience === 'general');
// Two locked groups, each behind its own password:
//   - "professional" (Vital City / in-development) → GALLERY_PASSWORD
//   - "personal" (family, kids, creative)          → PERSONAL_PASSWORD
// The "Personal / In development" tab unlocks the professional group; the
// personal group is further gated behind a second "Personal" link inside it.
const professionalProjects = projects.filter(p => p.audience === 'professional');
const personalProjects = projects.filter(p => p.audience === 'personal');

// Encrypt a group with AES-256-GCM via PBKDF2-SHA256. The salt is public
// (stored alongside the ciphertext) — it's the password that's secret.
// Matches WebCrypto's AES-GCM format (ciphertext || 16-byte tag).
const GALLERY_PASSWORD = '#9701SW72ct!!!';
const PERSONAL_PASSWORD = '#9701SW72ct???';
const PBKDF2_ITER = 250000;
function encryptGroup(records, password) {
  // Derive salt/iv deterministically from the plaintext so unchanged inputs
  // produce identical ciphertext (otherwise the hourly CI rebuild dirties the
  // manifest every run). Salt and IV are public; uniqueness-per-key for AES-GCM
  // is preserved because any plaintext change yields a new hash.
  const plaintext = Buffer.from(JSON.stringify(records), 'utf8');
  const digest = createHash('sha256').update(plaintext).digest();
  const salt = digest.subarray(0, 16);
  const iv = digest.subarray(16, 28);
  const key = pbkdf2Sync(password, salt, PBKDF2_ITER, 32, 'sha256');
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  const ct = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return {
    alg: 'AES-GCM',
    kdf: 'PBKDF2-SHA256',
    iterations: PBKDF2_ITER,
    salt: salt.toString('base64'),
    iv: iv.toString('base64'),
    ciphertext: Buffer.concat([ct, tag]).toString('base64'),
    count: records.length,
  };
}

const manifest = {
  count: projects.length,
  counts: { general: general.length, professional: professionalProjects.length, personal: personalProjects.length },
  categories: [...new Set(projects.map(p => p.category))].sort(),
  owners: [...new Set(projects.map(p => p.githubOwner).filter(Boolean))].sort(),
  projects: general,
  locked: {
    professional: encryptGroup(professionalProjects, GALLERY_PASSWORD),
    personal: encryptGroup(personalProjects, PERSONAL_PASSWORD),
  },
};

writeFileSync(join(ROOT, 'projects-manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`Wrote projects-manifest.json — ${projects.length} total`);
console.log(`  general: ${general.length} (public)`);
console.log(`  professional: ${professionalProjects.length} (encrypted — Vital City / in development)`);
console.log(`  personal: ${personalProjects.length} (encrypted — separate password)`);
