# Align the published transcript to Whisper's timed words.
# Output: W/align.json = {turns:[{speaker, paras:[[word,...]], ...}], twords:[...], wwords:[...]} (see bottom)
import json, os, re, sys, unicodedata, difflib, bisect
from collections import defaultdict

W = os.environ.get('W') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'interview')
SPEAKERS = [('Mike Lawler', 'lawler'), ('Ben Smith', 'smith'), ('Nicole Gelinas', 'gelinas'), ('Josh Greenman', 'greenman'),
            ('Alyssa Katz', 'katz'), ('Liena Žagare', 'zagare'), ('Timmy Facciola', 'facciola')]


def norm_tokens(s):
    """raw word -> list of normalized sub-tokens (lowercase, no punctuation; hyphens/dashes split)"""
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = unicodedata.normalize('NFKC', s).lower()
    s = re.sub(r"(?<=\w)'(?=\w)", '', s)           # that's -> thats
    s = re.sub(r'(?<=\d)[.,](?=\d)', '', s)         # 1,000 / 1.5 -> 1000 / 15
    s = re.sub(r"[^\w\s]|_", ' ', s)
    return [{'ok': 'okay', 'alright': 'allright'}.get(t, t) for t in s.split()]


# ------------------------------------------------------------ transcript
lines = open(f'{W}/transcript.txt', encoding='utf-8').read().split('\n')
meta = lines[:5]
turns = []        # {speaker key, paras: [text]}
for ln in lines[5:]:
    ln = ln.strip()
    if not ln:
        continue
    sp = None
    for nm, key in SPEAKERS:
        if ln.startswith(nm):
            sp = key; ln = ln[len(nm):].strip(); break
    if sp is None:
        turns[-1]['paras'].append(ln)
    else:
        turns.append(dict(who=sp, paras=[ln]))

twords = []   # transcript tokens
for ti, t in enumerate(turns):
    for pi, p in enumerate(t['paras']):
        for wi, raw in enumerate(p.split()):
            for sub in norm_tokens(raw):
                twords.append(dict(n=sub, turn=ti, para=pi, w=wi, raw=raw))
# [Crosstalk] etc. are not speech: drop from the alignment
# editorial insertions in square brackets ([Crosstalk], [Healthcare Association of New York State], [earn]) are not speech
for ti, t in enumerate(turns):
    for pi, p in enumerate(t['paras']):
        inb = False
        for tw in (x for x in twords if x['turn'] == ti and x['para'] == pi):
            if '[' in tw['raw']:
                inb = True
            if inb:
                tw['skip'] = True
            if ']' in tw['raw']:
                inb = False

# ------------------------------------------------------------ whisper
wh = json.load(open(f'{W}/whisper.json'))
wwords = []
for si, s in enumerate(wh['segments']):
    for w in s['words']:
        subs = norm_tokens(w['word'])
        if not subs:
            continue
        for k, sub in enumerate(subs):
            d = (w['end'] - w['start']) / len(subs)
            wwords.append(dict(n=sub, s=w['start'] + k * d, e=w['start'] + (k + 1) * d, raw=w['word'].strip(), seg=si, p=w.get('probability', 1)))

A = [t['n'] if not t.get('skip') else None for t in twords]
B = [w['n'] for w in wwords]
print('transcript tokens', len(A), 'whisper tokens', len(B))

# ------------------------------------------------------------ patience anchoring + SequenceMatcher on small gaps
match = {}      # a index -> b index


def lis(pairs):
    """longest increasing subsequence of (a,b) pairs sorted by a, increasing b"""
    tails, idx, prev = [], [], [-1] * len(pairs)
    for i, (a, b) in enumerate(pairs):
        j = bisect.bisect_left(tails, b)
        if j == len(tails):
            tails.append(b); idx.append(i)
        else:
            tails[j] = b; idx[j] = i
        prev[i] = idx[j - 1] if j > 0 else -1
    out, k = [], idx[-1] if idx else -1
    while k >= 0:
        out.append(pairs[k]); k = prev[k]
    return out[::-1]


def anchors(alo, ahi, blo, bhi, n):
    ca, cb = defaultdict(list), defaultdict(list)
    for i in range(alo, ahi - n + 1):
        g = tuple(A[i:i + n])
        if None not in g:
            ca[g].append(i)
    for j in range(blo, bhi - n + 1):
        cb[tuple(B[j:j + n])].append(j)
    pairs = sorted((ca[g][0], cb[g][0]) for g in ca if len(ca[g]) == 1 and len(cb.get(g, ())) == 1)
    return lis(pairs)


def solve(alo, ahi, blo, bhi, n):
    if alo >= ahi or blo >= bhi:
        return
    if (ahi - alo) * (bhi - blo) <= 4_000_000 or n <= 2:
        sm = difflib.SequenceMatcher(None, A[alo:ahi], B[blo:bhi], autojunk=False)
        for a, b, sz in sm.get_matching_blocks():
            for k in range(sz):
                if A[alo + a + k] is not None:
                    match[alo + a + k] = blo + b + k
        return
    an = anchors(alo, ahi, blo, bhi, n)
    if not an:
        solve(alo, ahi, blo, bhi, n - 1 if n > 3 else 2)
        return
    pa, pb = alo, blo
    for a, b in an:
        solve(pa, a, pb, b, n - 1 if n > 3 else 2)
        for k in range(n):
            match[a + k] = b + k
        pa, pb = a + n, b + n
    solve(pa, ahi, pb, bhi, n - 1 if n > 3 else 2)


solve(0, len(A), 0, len(B), 8)
# drop any non-monotonic pairs (should not happen)
prev = -1
for a in sorted(match):
    if match[a] <= prev:
        del match[a]
    else:
        prev = match[a]
print('exact matches', len(match), 'of', sum(1 for x in A if x is not None))


# ------------------------------------------------------------ fuzzy fill inside small gaps
def sim(x, y):
    if x == y:
        return 2
    if len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x)):
        return 1
    if len(x) >= 4 and difflib.SequenceMatcher(None, x, y).ratio() >= 0.78:
        return 1
    return -9


def fuzzy_gap(alo, ahi, blo, bhi):
    n, m = ahi - alo, bhi - blo
    if n == 0 or m == 0 or n * m > 90_000 or max(n, m) > 8 * min(n, m) + 12:
        return
    GAP = -0.6
    sc = [[0.0] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        sc[i][0] = i * GAP; bt[i][0] = 1
    for j in range(1, m + 1):
        sc[0][j] = j * GAP; bt[0][j] = 2
    for i in range(1, n + 1):
        ai = A[alo + i - 1]
        for j in range(1, m + 1):
            best, bb = sc[i - 1][j] + GAP, 1
            v = sc[i][j - 1] + GAP
            if v > best:
                best, bb = v, 2
            if ai is not None:
                s = sim(ai, B[blo + j - 1])
                if s > 0 and sc[i - 1][j - 1] + s > best:
                    best, bb = sc[i - 1][j - 1] + s, 3
            sc[i][j] = best; bt[i][j] = bb
    i, j = n, m
    while i > 0 or j > 0:
        b = bt[i][j]
        if b == 3:
            match[alo + i - 1] = blo + j - 1; fuzzy.add(alo + i - 1); i -= 1; j -= 1
        elif b == 1:
            i -= 1
        else:
            j -= 1


fuzzy = set()
ma = sorted(match)
bounds = [(-1, -1)] + [(a, match[a]) for a in ma] + [(len(A), len(B))]
for (a0, b0), (a1, b1) in zip(bounds, bounds[1:]):
    fuzzy_gap(a0 + 1, a1, b0 + 1, b1)
print('after fuzzy', len(match), 'fuzzy', len(fuzzy))

out = dict(turns=turns, twords=twords, wwords=wwords, match={str(a): b for a, b in match.items()}, fuzzy=sorted(fuzzy))
os.makedirs(f'{W}/tmp', exist_ok=True)
json.dump(out, open(f'{W}/tmp/align_raw.json', 'w'), ensure_ascii=False)
