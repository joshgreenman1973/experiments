# Write W/page/index.html from the player template once the other helper's layout.json and img/ are in W/page/.
#   python finish_page.py [PAGE_DIR]
import html, json, os, sys

W = os.environ.get('W') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'interview')
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
P = sys.argv[1] if len(sys.argv) > 1 else f'{W}/page'
if not (os.path.exists(f'{P}/layout.json') and os.path.isdir(f'{P}/img') and os.listdir(f'{P}/img')):
    print('finish_page: layout.json or img/ not in', P, 'yet; run finish_page.py again when they exist')
    sys.exit(0)
data = json.load(open(f'{P}/data.json'))
page = data['page']
tpl = open(f'{REPO}/web/player.html', encoding='utf-8').read()
# static text shown before data.json loads
setting, noun = page.get('setting', 'courtroom'), page.get('noun', 'argument')
for old, new in [('id="loading">Loading the courtroom…<', f'id="loading">Loading the {setting}…<'),
                 ('aria-label="Puppet courtroom"', f'aria-label="Puppet {setting}"'),
                 ('Press play to start the argument. Space pauses; the arrow keys skip 10 seconds.</div>',
                  f'Press play to start the {noun}. Space pauses; the arrow keys skip 10 seconds.</div>')]:
    assert tpl.count(old) == 1, old
    tpl = tpl.replace(old, new)
subs = {'__TITLE__': 'Mike Lawler Breakfast Interview',
        '__EYEBROW__': 'The New York Editorial Board · Interview · October 8, 2026',
        '__CASE_NAME__': page['case_name'],
        '__DEK__': page['question']}
for k, v in subs.items():
    assert k in tpl
    tpl = tpl.replace(k, html.escape(v, quote=False))
# a single interview page has no catalog of other arguments: skip the optional catalog.json probe (it would log a 404)
probe = 'try { const r = await fetch("catalog.json"); if (r.ok) CAT = await r.json(); } catch (e) {}'
if probe in tpl:
    tpl = tpl.replace(probe, '/* single page: no catalog.json */')
open(f'{P}/index.html', 'w', encoding='utf-8').write(tpl)
print('finish_page: wrote', f'{P}/index.html')
