"""Render METHODOLOGY.md to methodology.html in Vital City card styling.

Run: python3 scripts/render_methodology.py
"""
import pathlib, markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent
md = (ROOT / "METHODOLOGY.md").read_text()
body = markdown.markdown(md, extensions=["tables"])
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Subway vs. street: methodology</title>
<link rel="stylesheet" href="https://use.typekit.net/qqk2vto.css">
<style>
:root {{
  --vc-black:#050507; --vc-white:#ffffff; --vc-cloud:#dddddd; --vc-orange:#ff7c53;
  --vc-charcoal:#707175; --vc-graphite:#3a3a3d; --vc-paper:#f7f7f4; --vc-cerulean:#217ebe;
  --vc-sans:"halyard-text","Inter","Helvetica Neue",Arial,sans-serif;
}}
*,*::before,*::after{{box-sizing:border-box;}}
html,body{{background:var(--vc-white);color:var(--vc-black);}}
body{{font-family:var(--vc-sans);font-weight:300;line-height:1.6;margin:0;padding:32px 16px 64px;}}
main{{max-width:760px;margin:0 auto;}}
h1{{font-weight:700;font-size:2rem;line-height:1.15;margin:0 0 12px;text-wrap:balance;}}
h2{{font-weight:700;font-size:1.3rem;margin:40px 0 10px;}}
h3{{font-weight:700;font-size:1.05rem;margin:28px 0 8px;}}
p,li{{font-size:1rem;}}
strong{{font-weight:700;}}
a{{color:var(--vc-cerulean);}}
blockquote{{margin:14px 0;padding:10px 14px;background:var(--vc-paper);font-variant-numeric:tabular-nums;}}
blockquote p{{margin:4px 0;}}
.table-wrap{{overflow-x:auto;margin:14px 0;}}
table{{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums;}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--vc-cloud);vertical-align:top;}}
th{{font-weight:700;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:var(--vc-charcoal);}}
code{{font-size:.88em;background:var(--vc-paper);padding:1px 4px;}}
</style>
</head>
<body>
<main>
{body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")}
</main>
</body>
</html>
"""
(ROOT / "methodology.html").write_text(html)
print("wrote methodology.html")
