// Headless-Chromium check of the interview page: loads, plays, seeks, shows captions and chapters, no console errors.
// Usage: NODE_PATH=/opt/node22/lib/node_modules node web_check.js PAGE_DIR OUT_DIR [PORT]
// Saves screenshots (title card, playing wide, a close-up with caption, a late seek, the chapter list) in OUT_DIR
// and prints a PASS/FAIL line per check; exits 1 if anything failed.
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const [pageDir, outDir, portArg] = process.argv.slice(2);
const PORT = +(portArg || 8765);
fs.mkdirSync(outDir, { recursive: true });

const TYPES = { '.html': 'text/html', '.json': 'application/json', '.jpg': 'image/jpeg', '.webp': 'image/webp',
  '.mp3': 'audio/mpeg', '.png': 'image/png', '.js': 'text/javascript' };
// small static server with Range support (audio seeking needs it)
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  const f = path.join(pageDir, u === '/' ? 'index.html' : u);
  if (!f.startsWith(path.resolve(pageDir)) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  const st = fs.statSync(f), type = TYPES[path.extname(f)] || 'application/octet-stream';
  const m = /bytes=(\d*)-(\d*)/.exec(req.headers.range || '');
  if (m) {
    const a = m[1] ? +m[1] : 0, b = m[2] ? +m[2] : st.size - 1;
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${a}-${b}/${st.size}`, 'Accept-Ranges': 'bytes', 'Content-Length': b - a + 1 });
    fs.createReadStream(f, { start: a, end: b }).pipe(res);
  } else {
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes' });
    fs.createReadStream(f).pipe(res);
  }
});

let failed = 0;
const check = (name, ok, extra = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : '')); if (!ok) failed++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1500 } });
  const errors = [], failedReqs = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('requestfailed', r => failedReqs.push(r.url() + ' ' + (r.failure() || {}).errorText));
  page.on('response', r => { if (r.status() >= 400 && !/favicon/.test(r.url())) failedReqs.push(r.status() + ' ' + r.url()); });

  await page.goto(`http://localhost:${PORT}/index.html`);
  await page.waitForFunction(() => document.getElementById('bigplay') && !document.getElementById('bigplay').disabled, null, { timeout: 120000 });
  check('loaded (big play button enabled)', true);
  const data = JSON.parse(fs.readFileSync(path.join(pageDir, 'data.json'), 'utf8'));
  const dur = data.tl.duration;
  await sleep(500);
  await page.screenshot({ path: path.join(outDir, '1_title_card.png') });

  // play from the start
  await page.click('#bigplay');
  await sleep(4000);
  const t1 = await page.evaluate(() => document.getElementById('time').textContent);
  const a1 = await page.evaluate(() => Math.max(document.getElementById('aa').currentTime, document.getElementById('ab').currentTime));
  check('plays (clock and audio advance)', a1 > 1.5 && /^0:0[1-9]/.test(t1), `time="${t1}" audio=${a1.toFixed(2)}s`);
  await page.screenshot({ path: path.join(outDir, '2_playing_wide.png') });

  // captions at the first words
  const cap = await page.evaluate(() => { const c = document.getElementById('cap'); return { hidden: c.hidden, text: c.querySelector('.t').textContent, who: c.querySelector('.l').textContent }; });
  check('caption shows while speaking', !cap.hidden && cap.text.length > 3, `"${cap.who}: ${cap.text.slice(0, 60)}"`);

  // chapters
  const nch = await page.evaluate(() => document.querySelectorAll('#chapters button').length);
  check('chapter list matches data', nch === data.page.chapters.length, `${nch} chapters`);
  const ch = data.page.chapters[Math.min(3, data.page.chapters.length - 1)];
  await page.click(`#chapters li:nth-child(${Math.min(3, data.page.chapters.length - 1) + 1}) button`);
  await sleep(3500);
  const aT = await page.evaluate(() => { const a = document.getElementById('aa'), b = document.getElementById('ab'); return [a.currentTime, a.paused, b.currentTime, b.paused]; });
  const tt = await page.evaluate(() => document.getElementById('time').textContent);
  const shown = tt.split(' / ')[0].split(':').reduce((x, y) => x * 60 + (+y), 0);
  check('chapter click seeks', Math.abs(shown - ch[0]) < 8, `chapter at ${ch[0].toFixed(0)}s, clock "${tt}"`);
  const cur = await page.evaluate(() => document.querySelector('#chapters button.current') && document.querySelector('#chapters button.current').textContent);
  check('chapter highlights as current', !!cur && cur.includes(ch[1].slice(0, 12)), cur ? cur.slice(0, 50) : 'none');
  await page.screenshot({ path: path.join(outDir, '3_closeup_after_chapter_click.png') });

  // scrub-bar seek into a later audio segment (past the first cut), keep playing
  const target = data.segments[Math.min(4, data.segments.length - 1)][1] + 20;
  await page.evaluate(t => { const s = document.getElementById('scrub'); s.value = t; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change')); }, target);
  await sleep(4500);
  const t2 = await page.evaluate(() => document.getElementById('time').textContent);
  const shown2 = t2.split(' / ')[0].split(':').reduce((x, y) => x * 60 + (+y), 0);
  check('scrub seek lands in a later segment and plays on', shown2 >= target - 2 && shown2 < target + 12, `target ${target.toFixed(0)}s, clock "${t2}"`);
  await page.screenshot({ path: path.join(outDir, '4_seek_later_segment.png') });

  // skip with the arrow key
  await page.keyboard.press('ArrowRight'); await sleep(800);
  const t3 = await page.evaluate(() => document.getElementById('time').textContent);
  const shown3 = t3.split(' / ')[0].split(':').reduce((x, y) => x * 60 + (+y), 0);
  check('arrow key skips ahead', shown3 >= shown2 + 7, `"${t2}" -> "${t3}"`);

  // pause and resume with space
  await page.keyboard.press('Space'); await sleep(600);
  const paused = await page.evaluate(() => document.getElementById('aa').paused && document.getElementById('ab').paused);
  check('space pauses', paused);

  // the chapter list and the speaking-time chart, scrolled into view
  await page.evaluate(() => document.getElementById('chapters').scrollIntoView());
  await page.screenshot({ path: path.join(outDir, '5_chapters.png') });

  check('no console errors', errors.length === 0, errors.slice(0, 3).join(' | '));
  check('no failed requests', failedReqs.length === 0, failedReqs.slice(0, 3).join(' | '));
  await browser.close();
  server.close();
  console.log(failed ? `${failed} check(s) failed` : 'all checks passed');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error('test crashed:', e); process.exit(2); });
