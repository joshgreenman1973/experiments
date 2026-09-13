#!/usr/bin/env python3
"""Build the static search index and derived catalogue for the site.

Inputs:  data/catalogue.jsonl (from harvest_meta.py), data/text/<key>.txt (from fetch_text.py)
Outputs (all pre-gzipped, the browser inflates them with DecompressionStream):
  site/data/docs.json.gz         compact per-document records + lookup tables
  site/data/vocab.json.gz        [term, df] for terms seen in >= MIN_DF documents (fuzzy/prefix candidates)
  site/data/shards/<n>.json.gz   {term: [docDelta, tf, docDelta, tf, ...]} keyed by FNV-1a(term) % NSHARDS
  site/text/<key>.txt.gz         full OCR text, for excerpts and the reader
  site/data/stats.json           counts used on the page

Derived per document (heuristics, documented in the About page):
  title   an email subject, memo RE line, or first substantive line
  date    the document's own date, when one can be read off the first page
  kind    email / memo / letter / fax / lab data / press clipping / ... / document
"""
import json, os, re, sys, gzip, html, io, collections, math, datetime
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
TXT = os.path.join(DATA, "text")
NSHARDS = 2048
MIN_DF = 2          # vocab (fuzzy candidates) keeps terms in >= this many docs
MAX_TERM = 32

# ---------------------------------------------------------------- tokenizing
TOKEN_RE = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?")
def tokenize(text):
    return [t.replace("’", "'") for t in TOKEN_RE.findall(text.lower()) if 2 <= len(t) <= MAX_TERM]

def fnv1a(s):
    h = 0x811c9dc5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xffffffff
    return h

# ---------------------------------------------------------------- dates
MONTHS = {m: i + 1 for i, m in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
DATE_PATTERNS = [
    # September 17, 2001 / Sept. 17, 2001 / Sep 17 2001
    re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I),
    # 17 September 2001
    re.compile(r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\.?,?\s+(\d{4})\b", re.I),
    # 9/17/01, 09/17/2001, 9-17-01
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})\b"),
    # 17-Sep-01 (lab tables)
    re.compile(r"\b(\d{1,2})-(jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)-(\d{2}|\d{4})\b", re.I),
    # 2001-09-17
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]
LO, HI = datetime.date(1985, 1, 1), datetime.date(2012, 12, 31)

def _yr(y):
    y = int(y)
    if y < 100: y += 2000 if y < 50 else 1900
    return y

def _mk(y, m, d):
    try:
        dt = datetime.date(y, m, d)
    except ValueError:
        return None
    return dt if LO <= dt <= HI else None

def find_dates(text):
    out = []
    for i, pat in enumerate(DATE_PATTERNS):
        for m in pat.finditer(text):
            g = m.groups()
            try:
                if i == 0:   dt = _mk(_yr(g[2]), MONTHS[g[0].lower()[:3]], int(g[1]))
                elif i == 1: dt = _mk(_yr(g[2]), MONTHS[g[1].lower()[:3]], int(g[0]))
                elif i == 2: dt = _mk(_yr(g[2]), int(g[0]), int(g[1]))
                elif i == 3: dt = _mk(_yr(g[2]), MONTHS[g[1].lower()[:3]], int(g[0]))
                else:        dt = _mk(int(g[0]), int(g[1]), int(g[2]))
            except (KeyError, ValueError):
                dt = None
            if dt: out.append((m.start(), dt))
    out.sort()
    return out

HEADER_RE = re.compile(r"^.*(public\s*portal\s*document|portal\s*public\s*document).*$", re.I | re.M)
BATES_RE = re.compile(r"NYC-WTC[_ ]?\d{9}")
FAX_STAMP_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)-\d{2}-\d{4}\s+\d{2}:\d{2}", re.I)

def split_pages(text):
    """Pages end with a Bates stamp; split on them so page numbers can be derived."""
    parts = re.split(r"(NYC-WTC[_ ]?\d{9})\s*\n", text)
    pages = []
    buf = ""
    for i, part in enumerate(parts):
        if i % 2 == 0: buf += part
        else:
            pages.append(buf); buf = ""
    if buf.strip(): pages.append(buf)
    return pages or [text]

def clean_lines(page):
    lines = []
    for ln in page.split("\n"):
        s = ln.strip()
        if not s: continue
        if HEADER_RE.match(s): continue
        if BATES_RE.fullmatch(s): continue
        if re.fullmatch(r"[\W_]+", s): continue
        lines.append(s)
    return lines

EMAIL_HDR = re.compile(r"^(from|sent|to|cc|subject|date)\s*:", re.I)

def doc_date(pages, all_dates):
    """Pick a document date: an explicit Sent:/Date: line on page one, else the first date on page one
    (excluding the fax-machine timestamps in the scan header), else the most common date in the document."""
    p1 = "\n".join(clean_lines(pages[0]))[:4000]
    for ln in p1.split("\n")[:60]:
        if re.match(r"^(sent|date|dated)\s*:", ln, re.I):
            ds = find_dates(ln)
            if ds: return ds[0][1], "header"
    p1_nofax = FAX_STAMP_RE.sub(" ", p1)
    ds = find_dates(p1_nofax)
    if ds: return ds[0][1], "page1"
    if all_dates:
        c = collections.Counter(d for _, d in all_dates)
        return c.most_common(1)[0][0], "mode"
    return None, None

KIND_RULES = [
    ("email",          re.compile(r"^(from|sent|to|subject)\s*:", re.I | re.M), 2),
    ("lab data",       re.compile(r"\b(SAMPNO|ANALYTE|VIOLTYPE|LOCODE|ACCODE|chain of custody|GC/?MS|ICP-?MS|method (524|508|525|547|515)|surrogate|analytical results|sample id)\b", re.I), 2),
    ("fax",            re.compile(r"\b(fax cover|facsimile|telecopier|fax transmittal|fax transmission|number of pages)\b", re.I), 1),
    ("memo",           re.compile(r"\b(memorandum|memo)\b", re.I), 1),
    ("press clipping", re.compile(r"\b(daily news|new york times|newsday|new york post|wall street journal|associated press|the village voice|by [A-Z][a-z]+ [A-Z][a-z]+\s*$)", re.I | re.M), 1),
    ("press release",  re.compile(r"\b(press release|for immediate release)\b", re.I), 1),
    ("meeting",        re.compile(r"\b(agenda|minutes|meeting notes|attendees)\b", re.I), 1),
    ("letter",         re.compile(r"\b(dear (mr|ms|mrs|dr|sir|madam|commissioner|mayor|councilm)|sincerely|very truly yours|respectfully)\b", re.I), 1),
    ("contract",       re.compile(r"\b(contract|agreement|purchase order|invoice|change order|requisition)\b", re.I), 1),
    ("complaint",      re.compile(r"\b(complaint|referral|hotline)\b", re.I), 1),
    ("report",         re.compile(r"\b(report|assessment|survey|inspection|results summary)\b", re.I), 1),
    ("list",           re.compile(r"\b(list of|building list|address list|schedule)\b", re.I), 1),
]

def doc_kind(pages):
    head = "\n".join(clean_lines(pages[0]))[:2500]
    for kind, pat, need in KIND_RULES:
        n = len(pat.findall(head))
        if n >= need: return kind
    # long numeric tables with few words -> lab data
    toks = tokenize(head)
    if toks and sum(t.isdigit() for t in toks) / len(toks) > 0.55 and len(toks) > 60:
        return "lab data"
    return "document"

def doc_title(pages, kind, folder):
    lines = clean_lines(pages[0])
    def ok(s):
        if len(s) < 8: return False
        if FAX_STAMP_RE.search(s): return False
        if re.search(r"(www\.|alpha systems|barcode|\[signature\]|\[logo)", s, re.I): return False
        words = re.findall(r"[A-Za-z]{2,}", s)
        return len(words) >= 2
    # subject / RE lines first
    for ln in lines[:80]:
        m = re.match(r"^(subject|subj|re|regarding)\s*:\s*(.+)$", ln, re.I)
        if m and ok(m.group(2)): return _trim(m.group(2))
    # headings the OCR marked (markdown '#') were flattened; use first substantive line
    for ln in lines[:40]:
        if EMAIL_HDR.match(ln): continue
        if re.match(r"^(page\s+\d|p\.\s*\d|\d+\s*/\s*\d+)$", ln, re.I): continue
        if ok(ln): return _trim(ln)
    for ln in lines:
        if ok(ln): return _trim(ln)
    return _trim(folder) if folder and folder != "none" else "Untitled document"

def _trim(s, n=110):
    s = re.sub(r"\s+", " ", s).strip(" -–—:;,.*#|")
    s = re.sub(r"\*\*", "", s)
    if len(s) > n: s = s[:n].rsplit(" ", 1)[0] + "…"
    return s

def sender(pages, kind):
    if kind not in ("email", "memo", "fax", "letter"): return None
    head = "\n".join(clean_lines(pages[0]))[:2500]
    m = re.search(r"^from\s*:\s*(.+)$", head, re.I | re.M)
    if not m: return None
    s = m.group(1).strip()
    s = re.sub(r"<[^>]*>|\[mailto:[^\]]*\]|\(.*?\)", "", s).strip(" ,;")
    s = re.sub(r"\s+", " ", s)
    return _trim(s, 60) if 2 <= len(s) <= 80 else None

# ---------------------------------------------------------------- main
def key_of(row):
    m = re.search(r"(NYC-WTC_\d{9})", row["mes:key"])
    return m.group(1) if m else None

def main():
    rows = {}
    for line in open(os.path.join(DATA, "catalogue.jsonl")):
        r = json.loads(line); k = key_of(r)
        if k and k not in rows: rows[k] = r
    keys = sorted(rows)
    print(f"{len(keys)} documents in catalogue", flush=True)

    tables = {n: {} for n in ("agency", "source", "box", "folder", "kind")}
    def tid(name, v):
        t = tables[name]
        if v not in t: t[v] = len(t)
        return t[v]

    docs = []
    postings = collections.defaultdict(lambda: array("I"))
    df = collections.Counter()
    missing = 0
    total_tokens = 0
    os.makedirs(os.path.join(SITE, "text"), exist_ok=True)
    os.makedirs(os.path.join(SITE, "data", "shards"), exist_ok=True)

    for i, k in enumerate(keys):
        r = rows[k]
        p = os.path.join(TXT, k + ".txt")
        if not os.path.exists(p):
            missing += 1; text = r.get("sample") or ""
        else:
            text = open(p).read()
        pages = split_pages(text)
        folder = r.get("folder_name") or "none"
        kind = doc_kind(pages)
        title = doc_title(pages, kind, folder)
        all_dates = find_dates(text[:200000])
        d, dsrc = doc_date(pages, all_dates)
        frm = sender(pages, kind)
        toks = tokenize(text)
        total_tokens += len(toks)
        tf = collections.Counter(toks)
        if frm:
            for t in tokenize(frm): tf["from:" + t] += 1
        for t, n in tf.items():
            postings[t].append(i); postings[t].append(min(n, 65535)); df[t] += 1
        import base64
        try: docid = base64.b64decode(r.get("location") or "").decode().rsplit(":", 1)[1]
        except Exception: docid = ""
        docs.append([
            k[8:],                                  # Bates number without prefix
            tid("agency", r.get("agency") or ""),
            tid("source", r.get("source") or ""),
            tid("box", r.get("box_name") or ""),
            tid("folder", folder),
            int(r["page_count"]) if str(r.get("page_count", "")).isdigit() else len(pages),
            d.isoformat() if d else "",
            tid("kind", kind),
            title,
            len(toks),
            docid,
            frm or "",
        ])
        if os.path.exists(p):
            with gzip.open(os.path.join(SITE, "text", k + ".txt.gz"), "wt", compresslevel=6) as g:
                g.write(text)
        if i % 2000 == 0: print(f"  {i} docs, {len(postings)} terms, {total_tokens/1e6:.1f}M tokens", flush=True)

    print(f"missing text for {missing} docs; {len(postings)} distinct terms; {total_tokens/1e6:.1f}M tokens", flush=True)

    # docs + lookup tables
    def inv(t): return [None] * len(t) if not t else [v for v, _ in sorted(t.items(), key=lambda kv: kv[1])]
    out = {"fields": ["bates", "agency", "source", "box", "folder", "pages", "date", "kind", "title", "len", "docid", "from"],
           "tables": {n: inv(t) for n, t in tables.items()},
           "avgLen": total_tokens / max(1, len(docs)),
           "docs": docs}
    with gzip.open(os.path.join(SITE, "data", "docs.json.gz"), "wt", compresslevel=9) as g:
        json.dump(out, g, separators=(",", ":"))

    # vocab
    vocab = [[t, n] for t, n in df.items() if n >= MIN_DF and not t.startswith("from:")]
    vocab.sort(key=lambda x: (-x[1], x[0]))
    with gzip.open(os.path.join(SITE, "data", "vocab.json.gz"), "wt", compresslevel=9) as g:
        json.dump(vocab, g, separators=(",", ":"))
    print(f"vocab: {len(vocab)} terms with df>={MIN_DF}", flush=True)

    # shards: delta-encode doc ids
    shards = [dict() for _ in range(NSHARDS)]
    for t, arr in postings.items():
        enc = []; prev = 0
        for j in range(0, len(arr), 2):
            enc.append(arr[j] - prev); enc.append(arr[j + 1]); prev = arr[j]
        shards[fnv1a(t) % NSHARDS][t] = enc
    sizes = []
    for n, sh in enumerate(shards):
        with gzip.open(os.path.join(SITE, "data", "shards", f"{n}.json.gz"), "wt", compresslevel=9) as g:
            json.dump(sh, g, separators=(",", ":"))
        sizes.append(os.path.getsize(os.path.join(SITE, "data", "shards", f"{n}.json.gz")))
    print(f"shards: {NSHARDS}, total {sum(sizes)/1e6:.1f} MB gz, max {max(sizes)/1e3:.0f} KB", flush=True)

    kinds = collections.Counter(tables["kind"] and inv(tables["kind"])[d[7]] for d in docs)
    dated = sum(1 for d in docs if d[6])
    stats = {"documents": len(docs), "pages": sum(d[5] for d in docs), "tokens": total_tokens,
             "terms": len(postings), "vocab": len(vocab), "dated": dated, "kinds": kinds,
             "built": datetime.date.today().isoformat(), "missingText": missing}
    json.dump(stats, open(os.path.join(SITE, "data", "stats.json"), "w"), indent=1)
    print(json.dumps(stats, indent=1))

if __name__ == "__main__":
    main()
