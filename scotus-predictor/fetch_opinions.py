"""Fetch written-opinion text from Justia for opinions authored by current justices.

Reads cached Oyez case JSON files under data/cases/, scans the
`written_opinion` array for entries authored by a current justice
(matched by last name), and downloads + parses the opinion text from
Justia's HTML pages. Caches each parsed opinion as JSON under
data/opinions/{justia_opinion_id}.json.

Justia rate-limits aggressively; the crawler runs slowly on purpose
(~1 req/sec) and is idempotent so it can be resumed.

Usage:
    python fetch_opinions.py                # all cached cases
    python fetch_opinions.py --start 2018 --end 2024
    python fetch_opinions.py --term 2023
    python fetch_opinions.py --limit 20     # debug cap
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "data" / "cases"
OPINIONS_DIR = ROOT / "data" / "opinions"

# Last names of current justices — used to filter Oyez written_opinion entries
# before we hit Justia. Keep aligned with CURRENT_JUSTICES in build_corpus.py.
CURRENT_LASTNAMES = {
    "Roberts", "Thomas", "Alito", "Sotomayor", "Kagan",
    "Gorsuch", "Kavanaugh", "Barrett", "Jackson",
}

SESSION = requests.Session()
SESSION.headers.update({
    # Justia 403s on bare 'Mozilla/5.0'; an explanatory UA gets through.
    "User-Agent": "scotus-predictor/0.1 (research; +https://github.com/joshgreenman1973/experiments)",
    "Accept": "text/html,application/xhtml+xml",
})

REQ_DELAY_SEC = 1.0  # be polite to Justia


def fetch_html(url: str, retries: int = 4, backoff: float = 3.0) -> str | None:
    last_err = None
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code == 403:
                # back off harder on 403; Justia uses these for rate limiting
                time.sleep(backoff * (attempt + 2))
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    print(f"  ! failed {url} ({last_err})", file=sys.stderr)
    return None


def extract_opinion_text(html: str, justia_opinion_id: int) -> str | None:
    """Extract the body of one specific opinion from a Justia case page.

    Justia case landing pages embed every opinion's text on the same page
    in tab-switchable containers. Two structures occur:

      1. The default-visible tab (often the syllabus, sometimes the
         majority): <div class="block <type>" id="tab-opinion-N">...
      2. The hidden tabs (everything else):
         <div id="tab-opinion-N" class="hidden-content">...

    We try (2) first, then (1).
    """
    target = str(justia_opinion_id)

    # Hidden-content form (most common for non-default opinions).
    m = re.search(
        rf'<div id="tab-opinion-{target}" class="hidden-content">'
        r'(.*?)'
        r'(?=<div id="tab-opinion-\d+" class="hidden-content">|<footer|</main>|</body>)',
        html, re.DOTALL,
    )
    if not m:
        # Default-visible block form.
        m = re.search(
            rf'<div class="block [^"]+" id="tab-opinion-{target}">'
            r'(.*?)'
            r'(?=<div id="tab-opinion-\d+" class="hidden-content">|<div class="block [^"]+" id="tab-opinion-\d+">|<footer|</main>|</body>)',
            html, re.DOTALL,
        )
    if not m:
        return None

    chunk = m.group(1)
    # Strip <script> and <style> blocks first.
    chunk = re.sub(r"<script\b.*?</script>", " ", chunk, flags=re.DOTALL | re.IGNORECASE)
    chunk = re.sub(r"<style\b.*?</style>", " ", chunk, flags=re.DOTALL | re.IGNORECASE)
    # Replace common block-level closers with paragraph breaks before stripping tags.
    chunk = re.sub(r"</(p|div|h\d|li|blockquote|tr)\s*>", "\n\n", chunk, flags=re.IGNORECASE)
    chunk = re.sub(r"<br\s*/?>", "\n", chunk, flags=re.IGNORECASE)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", " ", chunk)
    text = html_lib.unescape(text)
    # Collapse whitespace per-line; KEEP blank lines so paragraph boundaries
    # introduced by </p> survive.
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    # Collapse 3+ newlines down to 2 (paragraph boundary).
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def iter_case_files(start: int | None, end: int | None, term: int | None):
    if not CASES_DIR.exists():
        return
    for term_dir in sorted(CASES_DIR.iterdir()):
        if not term_dir.is_dir():
            continue
        try:
            t = int(term_dir.name)
        except ValueError:
            continue
        if term is not None and t != term:
            continue
        if start is not None and t < start:
            continue
        if end is not None and t > end:
            continue
        for f in sorted(term_dir.glob("*.json")):
            yield f


def opinion_target_filename(opinion_id: int) -> Path:
    return OPINIONS_DIR / f"{opinion_id}.json"


def process_case(case_file: Path) -> tuple[int, int]:
    """Returns (fetched_pages, saved_opinions)."""
    try:
        case = json.loads(case_file.read_text())
    except Exception as e:
        print(f"  ! bad case file {case_file}: {e}")
        return 0, 0

    wo_list = case.get("written_opinion") or []
    # Filter to entries authored by a current justice.
    targets = []
    for wo in wo_list:
        last_name = wo.get("judge_last_name")
        if not last_name or last_name not in CURRENT_LASTNAMES:
            continue
        op_id = wo.get("justia_opinion_id")
        url = wo.get("justia_opinion_url")
        if not op_id or not url:
            continue
        if opinion_target_filename(op_id).exists():
            continue
        targets.append((op_id, url, wo))
    if not targets:
        return 0, 0

    # All opinions for a case live on the same Justia landing page; fetch once.
    # Strip /concurrence.html|/dissent.html|/dissent2.html|/concurrence2.html etc.
    landing_url = re.sub(r"/[^/]+\.html$", "/", targets[0][1])
    html = fetch_html(landing_url)
    time.sleep(REQ_DELAY_SEC)
    if not html:
        return 1, 0

    saved = 0
    case_name = case.get("name")
    term = case.get("term")
    for op_id, url, wo in targets:
        text = extract_opinion_text(html, op_id)
        if not text or len(text) < 200:
            # Some pages don't include the body (e.g. orders); skip silently.
            continue
        record = {
            "justia_opinion_id": op_id,
            "case_id": case.get("ID"),
            "case_name": case_name,
            "term": term,
            "docket_number": case.get("docket_number"),
            "type": (wo.get("type") or {}).get("value"),  # majority | concurring | dissenting | ...
            "title": wo.get("title"),
            "judge_full_name": wo.get("judge_full_name"),
            "judge_last_name": wo.get("judge_last_name"),
            "justia_url": url,
            "landing_url": landing_url,
            "text": text,
        }
        out = opinion_target_filename(op_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record))
        saved += 1
    return 1, saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, help="Earliest term (inclusive)")
    ap.add_argument("--end", type=int, help="Latest term (inclusive)")
    ap.add_argument("--term", type=int, help="Single term shortcut")
    ap.add_argument("--limit", type=int, help="Cap number of case landing pages fetched (debug)")
    args = ap.parse_args()

    OPINIONS_DIR.mkdir(parents=True, exist_ok=True)

    fetched = 0
    saved = 0
    pages = 0
    for cf in iter_case_files(args.start, args.end, args.term):
        if args.limit and pages >= args.limit:
            break
        pf, ps = process_case(cf)
        if pf:
            pages += 1
        fetched += pf
        saved += ps
        if fetched and fetched % 25 == 0:
            print(f"  progress: {fetched} pages fetched, {saved} opinions saved")
    print(f"done: {fetched} pages fetched, {saved} opinions saved")


if __name__ == "__main__":
    main()
