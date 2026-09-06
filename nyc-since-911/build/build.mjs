import fs from 'node:fs';
const dir = new URL('..', import.meta.url).pathname;
const tpl = fs.readFileSync(dir + 'build/template.html', 'utf8');
const data = JSON.parse(fs.readFileSync(dir + 'data/facts.json', 'utf8'));
let n = 0; for (const s of data.sections) n += s.items.length;
if (n !== 25) throw new Error(`expected 25 items, got ${n}`);
fs.writeFileSync(dir + 'index.html', tpl.replace('__DATA__', JSON.stringify(data)));
console.log('wrote index.html with', n, 'items');

// methodology page: every figure with its URL and verbatim quote
const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;');
let k = 0;
const rows = data.sections.map(sec => `<h2>${esc(sec.title)}</h2>` + sec.items.map(d => {
  k++;
  const side = (lab, v, s) => `<div class="side"><div class="v">${esc(lab)}: <b>${esc(v)}</b></div>${s ? `<div class="u"><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a></div><blockquote>${esc(s.quote)}</blockquote>` : '<div class="u">No source recorded.</div>'}</div>`;
  return `<section class="item" id="i${k}"><h3>${String(k).padStart(2,'0')} · ${esc(d.title)}</h3>
  ${side(d.then_label, d.then_display ?? d.then_value, d.then_src)}
  ${side(d.now_label, d.now_display ?? d.now_value, d.now_src)}
  ${d.method ? `<p class="m"><b>Calculation and caveats.</b> ${d.method}</p>` : ''}
  <p class="m"><b>Confidence.</b> ${esc(d.confidence || 'high')}</p></section>`;
}).join('')).join('');
const ms = (data.milestones||[]).map(m => `<section class="item"><h3>${esc(m.year)} · ${m.text}</h3>${m.url?`<div class="u"><a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.url)}</a></div>`:''}${m.quote?`<blockquote>${esc(m.quote)}</blockquote>`:''}</section>`).join('');
const meth = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Methodology and sources: 25 ways New York City has changed since 9/11</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<style>
body{margin:0;background:#fcfcfb;color:#111;font:16px/1.5 'Barlow','Helvetica Neue',Arial,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:28px 28px 80px}
h1{font:800 48px/1 'Barlow Condensed',sans-serif;text-transform:uppercase;margin:0 0 8px;border-top:6px solid #111;padding-top:18px}
h2{font:700 28px/1 'Barlow Condensed',sans-serif;text-transform:uppercase;margin:44px 0 4px;border-top:4px solid #111;padding-top:8px}
h3{font:700 22px/1.1 'Barlow Condensed',sans-serif;margin:0 0 8px}
.item{border-top:1px solid #d9d9d6;padding:18px 0 14px}
.side{margin:8px 0 10px}
.v{font-weight:500}
.u{font-size:13px;word-break:break-all}
.u a{color:#333}
blockquote{margin:6px 0 0;padding:8px 12px;border-left:3px solid #1d4ed8;background:#f1f1ef;font-size:14.5px;color:#222}
.side+.side blockquote{border-left-color:#f26522}
p.m{font-size:14.5px;color:#333;margin:8px 0 0}
.lede{font-size:17px;max-width:66ch}
a.back{font:600 14px 'Barlow',sans-serif;color:#333}
</style></head><body><div class="wrap">
<a class="back" href="index.html">Back to the infographic</a>
<h1>Methodology and sources</h1>
<p class="lede">Every figure on the infographic is listed here with the page it came from and the exact words on that page. The "then" figure is the one closest to September 2001 that the source publishes; where that is the 2000 census or a 2002 survey, the label says so. The "now" figure is the most recent published as of early September 2026. Percent changes are computed from the two values shown, by script, and are nominal unless the row says otherwise. Figures whose source page could not be fetched during research were left out rather than estimated.</p>
<p class="lede">Research and coding were done with Anthropic's Claude Code under the author's direction. Each figure was required to come from a fetched page with a verbatim quote; the quotes are reproduced below unedited.</p>
${rows}
${ms ? `<h2>World Trade Center site milestones</h2>${ms}` : ''}
</div></body></html>`;
fs.writeFileSync(dir + 'methodology.html', meth);
console.log('wrote methodology.html');
