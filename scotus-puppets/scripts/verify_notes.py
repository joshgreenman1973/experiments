# Check decision notes against the opinion text and schedule them for the player.
# Usage: python verify_notes.py NOTES.json OPINION.txt OUT.json
#   Every quote must appear verbatim in the opinion (after normalizing whitespace, curly quotes, dashes and words
#   hyphenated across line breaks); failures are dropped and reported. Output rows, as the player reads them:
#   [show_from, show_until, label, quote, cite, connection, question_time, "Asker: question"]
import json, re, sys

notes_path, op_path, out_path = sys.argv[1:4]
N = json.load(open(notes_path))
raw = open(op_path, errors='replace').read()

HEADER = re.compile(r'^(=== PDF page \d+ ===|Cite as: .*|\(?Slip Opinion\)?.*|OCTOBER TERM, \d{4}.*|\d{1,3}|Syllabus|Opinion of the Court|Per Curiam|'
                    r'.*J\., (concurring|dissenting).*|[A-Z0-9 .,&\'’\-]{3,80} v\. [A-Z0-9 .,&\'’\-]{2,80})$')


def norm(s):
    s = s.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    s = re.sub('[‐‑‒–—―]', '-', s).replace(' ', ' ').replace('­', '')
    return re.sub(r'\s+', ' ', s).strip()


lines = [l.strip() for l in raw.splitlines()]
body = [l for l in lines if l and not HEADER.match(l)]
joined_drop, joined_keep = '', ''
for l in body:  # two readings of a line-end hyphen: split word (drop it) or real compound (keep it)
    if joined_drop.endswith('-') and l[:1].islower():
        joined_drop = joined_drop[:-1] + l
        joined_keep = joined_keep + l
    else:
        joined_drop += ' ' + l
        joined_keep += ' ' + l
texts = [norm(joined_drop), norm(joined_keep), norm(' '.join(lines))]

ok, bad = [], []
for n in N.get('notes', []):
    q = norm(n.get('quote', ''))
    if len(q.split()) < 6 or not any(q in t for t in texts):
        bad.append(n)
        continue
    ok.append(n)

ok.sort(key=lambda n: float(n['t']))
rows, busy_until = [], -1.0
for n in ok:
    words = len(n['quote'].split())
    dur = max(9.0, min(22.0, 4.0 + words * 0.33))
    start = max(float(n['t']) + 1.0, busy_until + 0.6)
    rows.append([round(start, 2), round(start + dur, 2), n['label'].strip().upper(), n['quote'].strip(), n.get('cite', '').strip(),
                 n.get('connection', '').strip(), round(float(n['t']), 1), f"{n.get('asker', '').strip()}: {n.get('question', '').strip()}"])
    busy_until = start + dur
json.dump(dict(notes=rows, outcome_check=N.get('outcome_check', {})), open(out_path, 'w'), indent=1, ensure_ascii=False)
print(f"{N.get('docket')}: {len(rows)} verified, {len(bad)} dropped" + (''.join(f"\n   DROPPED t={b.get('t')}: {b.get('quote', '')[:90]}" for b in bad)))
