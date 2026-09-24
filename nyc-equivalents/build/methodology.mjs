// Writes ../methodology.html from pairings-src.json: every pairing with both
// source URLs, verbatim quotes, years, ratio, confidence and caveats, plus the
// blind fact-check ledger in factcheck.json if present.
import fs from 'node:fs';
const src = JSON.parse(fs.readFileSync('pairings-src.json','utf8'));
const fc = fs.existsSync('factcheck.json') ? JSON.parse(fs.readFileSync('factcheck.json','utf8')) : null;
const extraRounds = fs.readdirSync('.').filter(f=>/^factcheck-\d+\.json$/.test(f)).sort()
  .flatMap(f=>JSON.parse(fs.readFileSync(f,'utf8')));
if (fc) fc.items = [...fc.items, ...extraRounds];
const esc = s => String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const realmLabel = k => src.realms.find(r=>r.key===k)?.label || k;
const rows = src.items.map((it,i)=>{
  const ratio = it.match_value/it.nyc_value;
  // Findings are matched by the exact pair of source URLs the checker fetched,
  // not by position: pairings renumber and comparisons get swapped, and a stale
  // finding attached to the wrong line would be worse than none.
  const fcRow = fc?.items?.find(f=>f.checked_nyc_url===it.nyc_url && f.checked_match_url===it.match_url);
  return `
<section class="m" id="p${i+1}">
  <h3><span class="num r-${it.realm}">${i+1}</span> New York City ${esc(it.sentence.replace(/<[^>]+>/g,''))}</h3>
  <p class="meta">${esc(realmLabel(it.realm))} &middot; ratio ${ratio.toFixed(3)} (${esc(it.place)} &divide; New York City) &middot; confidence: ${esc(it.confidence)}</p>
  <dl class="f">
    <div><dt>New York City figure</dt><dd>${esc(it.nyc_display)} (${esc(it.nyc_year)}). Source: <a href="${esc(it.nyc_url)}">${esc(it.nyc_source)}</a><br><q>${esc(it.nyc_quote)}</q></dd></div>
    <div><dt>Comparison figure</dt><dd>${esc(it.match_display)} (${esc(it.match_year)}). Source: <a href="${esc(it.match_url)}">${esc(it.match_source)}</a><br><q>${esc(it.match_quote)}</q></dd></div>
    ${it.note?`<div><dt>Definitions and caveats</dt><dd>${esc(it.note)}</dd></div>`:''}
    ${fcRow?`<div><dt>Blind fact-check</dt><dd><b>${esc(fcRow.verdict)}</b>. ${esc(fcRow.finding)}${fcRow.reverified?` ${esc(fcRow.reverified)}`:''}${fcRow.conflict?`<br><br><b>Contradicting figure found:</b> ${esc(fcRow.conflict)}`:''}${fcRow.resolution?`<br><br><b>What was changed:</b> ${esc(fcRow.resolution)}`:''}</dd></div>`:''}
  </dl>
</section>`;
}).join('\n');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Methodology: New York City equivalents</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Karla:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../house-style/house.css">
<style>
:root{--accent:var(--lilac)}
.r-people{--rc:var(--cobalt)} .r-money{--rc:var(--sun)} .r-place{--rc:var(--mint)}
.r-movement{--rc:var(--cyan)} .r-life{--rc:var(--lilac)} .r-safety{--rc:var(--vermilion)}
.wrap{padding:18px clamp(16px,4vw,48px) 60px;max-width:900px}
.wrap h2{margin:30px 0 8px}
.wrap p{margin:0 0 12px;line-height:1.6}
.m{border-top:1px solid var(--line);padding:14px 0 6px;margin-top:18px}
.m h3{font-weight:600;font-size:1.12rem;margin:0 0 4px;line-height:1.3}
.num{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;color:var(--bg);background:var(--rc);font-size:.85rem;margin-right:6px;vertical-align:-3px}
.meta{font-size:var(--t-small);color:var(--fg2);margin:0 0 8px}
dl.f>div{grid-template-columns:170px 1fr}
q{display:block;margin-top:5px;color:var(--fg2);font-size:.92rem;line-height:1.5;border-left:2px solid var(--line);padding-left:9px}
q::before,q::after{content:''}
.toc{columns:2;column-gap:26px;font-size:.94rem;line-height:1.55;margin:0 0 8px}
@media(max-width:560px){.toc{columns:1}}
.toc a{text-decoration:none;color:var(--fg);border-bottom:1px solid var(--line)}
.fc{border:1px solid var(--line);padding:12px 16px;margin:12px 0 0}
.fc p{margin:0 0 8px}
table.h{margin:8px 0 14px}
</style>
</head>
<body>
<div class="sheet">
  <div class="strip"><span>New York City equivalents</span><span><a href="index.html">Back to the graphic</a></span></div>
  <div class="head">
    <h1>Methodology</h1>
    <p class="sub">How each pairing was built, where both numbers come from, the exact words on each source page and what does not line up perfectly.</p>
  </div>
  <div class="wrap">
    ${src.methodology_intro}
    <h2>Every pairing, with its sources</h2>
    <div class="toc">${src.items.map((it,i)=>`<div><a href="#p${i+1}">${i+1}. ${esc(it.place)}</a></div>`).join('')}</div>
    ${rows}
    ${fc?`<h2>Blind fact-check</h2><div class="fc">${fc.summary}</div>`:''}
    <h2>AI caution</h2>
    <p class="caution">And please read this AI caution. The concept, the choice of figures and the layout were the author's (a human). The research, coding and file handling were done by Anthropic's Claude Code under close direction. Every number was required to come from a fetched source page with a verbatim quote, and a second, independent pass re-checked each pairing blind against its sources. Risks of AI error remain. If you spot a wrong number, a stale figure or a better match, the author would like to hear it.</p>
  </div>
</div>
</body>
</html>`;
fs.writeFileSync('../methodology.html', html);
console.log('methodology.html written', src.items.length, 'pairings', fc?'+ factcheck':'');
