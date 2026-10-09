# Index page for a slate: every argument with its question, length, outcome and a link to its puppet page.
# Usage: python build_index.py SLATE.json WORKROOT URLS.json OUT.html
#   URLS.json: {"<docket>": "https://claude.ai/artifact/...", ..., "_extra": [["title", "url", "note"], ...]}
import datetime, html, json, os, re, sys

slate_path, root, urls_path, out = sys.argv[1:5]
slate = json.load(open(slate_path))
urls = json.load(open(urls_path))
outcomes = {o['docket'].strip(): o for o in json.load(open(slate['outcomes']))} if slate.get('outcomes') else {}
E = lambda s: html.escape(str(s), quote=True)


def fmt_len(sec):
    h, m = int(sec // 3600), int(sec // 60 % 60)
    return f'{h} hr {m} min' if h else f'{m} min'


def fmt_date(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime('%b. ').replace('May.', 'May').replace('Jun.', 'June').replace('Jul.', 'July').replace('Sep.', 'Sept.') + f'{d.day}, {d.year}'


rows, total = [], 0
for c in slate['cases']:
    d = c['docket']
    cfg = json.load(open(os.path.join(root, 'cases', d, 'cfg.json')))
    data = json.load(open(os.path.join(root, 'cases', d, 'page', 'data.json')))
    seg = data['segments'][-1]
    length = seg[1] + seg[2]
    total += length
    o = outcomes.get(d, {})
    m = re.match(r'\s*(\d)-(\d)', o.get('vote', ''))
    vote = f'{m.group(1)}–{m.group(2)}' if m else ''
    if 'dismiss' in o.get('outcome', '').lower() and not m:
        vote = 'Dismissed'
    decided = ('Decided ' + fmt_date(o['decided'])) if o.get('decided') else ''
    speakers = ', '.join(v['display'] for v in cfg['advocates'].values())
    url = urls.get(d)
    rows.append(f'''
    <li class="case">
      <div class="meta"><span>No. {E(d)}</span><span>Argued {E(cfg['argued'])}</span><span>{E(fmt_len(length))}</span></div>
      <h2>{f'<a href="{E(url)}" target="_blank" rel="noopener">' if url else ''}{E(c['name'])}{'</a>' if url else ''}</h2>
      <p class="topic">{E(c['topic'])}</p>
      <p class="who">Arguing: {E(speakers)}</p>
      {f'<p class="out"><span class="vote">{E(vote)}</span> {E(decided)}. {E(o["outcome"])}</p>' if o.get('outcome') else ''}
      {f'<a class="go" href="{E(url)}" target="_blank" rel="noopener">Watch the argument</a>' if url else '<span class="go off">Not published yet</span>'}
    </li>''')

extra = ''.join(f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(t)}</a> <span>{E(n)}</span></li>' for t, u, n in urls.get('_extra', []))
page = f'''<title>{E(slate.get('index_title', slate['label'] + ' in Puppets'))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">
<style>
/* Layout: a docket sheet. One column of cases in argument order, each a card with its question, outcome and link. Single dark look by choice. */
:root {{ --bg: #130c0d; --panel: #1d1314; --fg: #efe6d8; --muted: #b6a796; --faint: #8a7c70; --brass: #c9a24a; --velvet: #8c1d27; --line: #3a2a2a; --focus: #e8c56b;
  --display: "Cinzel", "Trajan Pro", "Times New Roman", serif; --body: "Source Serif 4", Georgia, serif; --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--body); font-size: 17px; line-height: 1.55; }}
[hidden] {{ display: none !important; }}
.wrap {{ max-width: 920px; margin: 0 auto; padding-inline: 20px; padding-block: 36px 64px; display: grid; gap: 30px; }}
.eyebrow {{ font-family: var(--mono); font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--brass); }}
h1 {{ font-family: var(--display); font-weight: 600; font-size: clamp(30px, 5vw, 52px); line-height: 1.08; margin: 6px 0 10px; letter-spacing: .02em; text-wrap: balance; }}
.dek {{ color: var(--muted); font-size: 18px; max-width: 62ch; margin: 0; }}
ol.cases {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; }}
.case {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 18px 20px; display: grid; gap: 6px; min-width: 0; }}
.case .meta {{ display: flex; flex-wrap: wrap; gap: 4px 16px; font-family: var(--mono); font-size: 12px; color: var(--faint); letter-spacing: .04em; font-variant-numeric: tabular-nums; }}
.case h2 {{ font-family: var(--body); font-weight: 600; font-size: 23px; line-height: 1.25; margin: 0; text-wrap: balance; }}
.case h2 a {{ color: var(--fg); text-decoration: none; }}
.case h2 a:hover {{ text-decoration: underline; text-decoration-color: var(--brass); }}
.case p {{ margin: 0; }}
.topic {{ font-size: 17px; }}
.who {{ color: var(--muted); font-size: 15px; }}
.out {{ color: var(--muted); font-size: 15px; border-top: 1px solid var(--line); padding-top: 8px; margin-top: 4px !important; }}
.vote {{ font-family: var(--mono); font-size: 12px; color: var(--bg); background: var(--brass); border-radius: 3px; padding: 1px 6px; margin-right: 4px; white-space: nowrap; }}
.go {{ justify-self: start; margin-top: 6px; font-family: var(--mono); font-size: 13px; letter-spacing: .06em; text-transform: uppercase; color: var(--fg);
  border: 1px solid var(--brass); border-radius: 4px; padding: 6px 12px; text-decoration: none; }}
.go:hover {{ background: var(--velvet); border-color: var(--velvet); }}
.go.off {{ border-color: var(--line); color: var(--faint); }}
:focus-visible {{ outline: 2px solid var(--focus); outline-offset: 2px; }}
.notes {{ border-top: 1px solid var(--line); padding-top: 20px; color: var(--muted); font-size: 15px; display: grid; gap: 10px; max-width: 70ch; }}
.notes p {{ margin: 0; }}
.notes strong {{ color: var(--fg); }}
.notes ul {{ margin: 0; padding-left: 18px; }}
.notes a {{ color: var(--brass); }}
</style>
<div class="wrap">
  <header>
    <div class="eyebrow">Supreme Court of the United States · {E(slate['label'])}</div>
    <h1>{E(slate.get('index_title', slate['label'] + ' in Puppets'))}</h1>
    <p class="dek">{len(slate['cases'])} of the term's biggest arguments, complete and unedited ({E(fmt_len(total))} in all), performed by puppets of the justices over the Court's own audio.</p>
  </header>
  <ol class="cases">{''.join(rows)}
  </ol>
  <div class="notes">
    <p><strong>How these are made.</strong> The audio is the Court's recording of each argument, via Oyez, whose transcripts mark who is speaking when. The justices are 3D caricatures; the lawyers are stand-in puppets in felt colors, not likenesses. Mouths move with the loudness of each speaker's syllables.</p>
    <p><strong>Outcomes</strong> were checked against news coverage and the Court's opinions as summarized in search results; each case page links its source.</p>
    {f'<p><strong>Also</strong></p><ul>{extra}</ul>' if extra else ''}
    <p>Audio and transcript timing from <a href="https://www.oyez.org" target="_blank" rel="noopener">Oyez</a>, licensed CC BY-NC 4.0. Made by Josh Greenman with Claude.</p>
  </div>
</div>
'''
open(out, 'w').write(page)
print(out, len(rows), 'cases', fmt_len(total))
