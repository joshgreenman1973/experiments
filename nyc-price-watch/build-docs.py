#!/usr/bin/env python3
"""Render the project's markdown specs as designed pages.

Run after editing any of the source .md files:  python3 build-docs.py
"""
import markdown, re, pathlib

DOCS = [
    # source,            output,             nav title,    lede
    ("METHODOLOGY.md", "methodology.html", "Methodology",
     "What every series on the tracker actually measures, how it is estimated, "
     "where it comes from and what it cannot be used to claim. Written for readers "
     "who will interrogate the estimator and the sampling frame before trusting a number."),
    ("TRACKING.md", "tracking.html", "How tracking works",
     "A candid account of what it takes to keep each price current with no field staff "
     "and no paid data feeds, and which items are realistically sustainable."),
    ("SCHEDULE.md", "schedule.html", "Refresh schedule",
     "When every source publishes, and the calendar the monthly refresh runs on so that "
     "each pull lands on fresh data rather than an arbitrary date."),
    ("CANDIDATES.md", "candidates.html", "Candidate prices",
     "Other quintessentially New York costs weighed for inclusion, scored on whether they "
     "are distinctive, trackable and meaningful — including the ones deliberately cut."),
]
NAV = [(t, o) for _, o, t, _ in DOCS]

def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", t).lower()).strip("-")

CSS = pathlib.Path("docs-style.css").read_text()

def build(src, out, title, lede):
    md = pathlib.Path(src).read_text()
    lines = md.split("\n")
    version = ""
    for l in lines[1:8]:
        if l.strip().startswith("**Version"):
            version = l.strip().strip("*")
            break
    body_md = re.sub(r"^\*\*Version[^\n]*\n", "", "\n".join(lines[1:]), flags=re.M)
    body = markdown.markdown(body_md, extensions=["tables", "sane_lists", "attr_list"])

    heads = re.findall(r"<h2>(.*?)</h2>", body)
    for h in heads:
        body = body.replace(f"<h2>{h}</h2>", f'<h2 id="{slug(h)}">{h}</h2>', 1)
    toc = "\n".join(
        f'        <li><a href="#{slug(h)}">{re.sub(r"<[^>]+>", "", h)}</a></li>' for h in heads
    )
    sibs = "\n".join(
        '        <li><a href="%s"%s>%s</a></li>' % (o, ' class="here"' if o == out else "", t)
        for t, o in NAV
    )
    meta = f"<b>{version}</b>" if version else ""

    pathlib.Path(out).write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — The NYC Price Watch</title>
<meta name="description" content="{lede[:150]}">
<link rel="stylesheet" href="https://use.typekit.net/qqk2vto.css">
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">

  <header class="mast">
    <div>
      <div class="kicker">The NYC Price Watch · Technical specification</div>
      <h1>{title}</h1>
    </div>
    <div class="issue">
      {meta}
      <a href="./">&larr; Back to the tracker</a><br>
      <a href="https://github.com/joshgreenman1973/experiments/tree/main/nyc-price-watch">Source and data</a>
    </div>
  </header>

  <p class="lede">{lede}</p>

  <div class="layout">
    <nav class="toc">
      <div class="t">Specifications</div>
      <ol class="sibs">
{sibs}
      </ol>
      <div class="t" style="margin-top:1.4rem;">On this page</div>
      <ol>
{toc}
      </ol>
    </nav>
    <article>
{body}
    </article>
  </div>

</div>

<footer>
  <div class="fin">
    <div class="fname">The NYC Price Watch</div>
    <div>Everyday New York prices, tracked monthly from public sources.
      <a href="./">Back to the tracker</a> ·
      <a href="https://github.com/joshgreenman1973/experiments/tree/main/nyc-price-watch">Source and data</a></div>
  </div>
</footer>

</body>
</html>
""")
    return out, len(heads), body.count("<table>")

if __name__ == "__main__":
    for src, out, title, lede in DOCS:
        if not pathlib.Path(src).exists():
            print(f"  SKIP (missing): {src}")
            continue
        o, h, t = build(src, out, title, lede)
        print(f"  built {o:<20} {h:>2} sections  {t} tables")
