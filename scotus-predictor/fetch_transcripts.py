"""Incremental Oyez crawler.

Walks SCOTUS terms, downloads case detail + oral-argument transcripts,
caches each as a JSON file on disk. Safe to re-run; skips files that
already exist. Network failures retry with backoff.

Usage:
    python fetch_transcripts.py --start 2005 --end 2024
    python fetch_transcripts.py --term 2023   # single term
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

OYEZ_BASE = "https://api.oyez.org"
ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "data" / "cases"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "scotus-predictor/0.1 (research)"})


def get_json(url: str, retries: int = 4, backoff: float = 2.0):
    last_err = None
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
    print(f"  ! failed after {retries} retries: {url} ({last_err})", file=sys.stderr)
    return None


def fetch_term(term: int) -> list[dict]:
    """Returns list of case stubs for the given term.

    Oyez's `/cases/{term}` endpoint returns the first N cases globally
    rather than filtering by term, so we use the `filter` query param.
    """
    url = f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=1000"
    data = get_json(url) or []
    # Defensive: drop any stub whose term doesn't match (shouldn't happen but cheap).
    return [s for s in data if str(s.get("term")) == str(term)]


def case_filename(term: int, docket: str) -> Path:
    safe_docket = docket.replace("/", "_")
    return CASES_DIR / str(term) / f"{safe_docket}.json"


def transcript_filename(audio_id: str | int) -> Path:
    return TRANSCRIPTS_DIR / f"{audio_id}.json"


def fetch_case(stub: dict) -> dict | None:
    term = stub.get("term")
    docket = stub.get("docket_number")
    if not term or not docket:
        return None
    out_path = case_filename(int(term), docket)
    if out_path.exists():
        try:
            return json.loads(out_path.read_text())
        except Exception:
            pass  # corrupt cache, refetch
    href = stub.get("href")
    if not href:
        return None
    data = get_json(href)
    if not data:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data))
    return data


def fetch_transcript(audio_entry: dict) -> dict | None:
    href = audio_entry.get("href")
    if not href:
        return None
    # Audio id is the last URL segment
    audio_id = urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]
    out_path = transcript_filename(audio_id)
    if out_path.exists():
        try:
            return json.loads(out_path.read_text())
        except Exception:
            pass
    data = get_json(href)
    if not data:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data))
    return data


def process_term(term: int, max_cases: int | None = None):
    print(f"[term {term}] listing cases...")
    stubs = fetch_term(term)
    if not stubs:
        print(f"  no cases returned")
        return
    print(f"  {len(stubs)} cases")
    if max_cases:
        stubs = stubs[:max_cases]
    fetched_cases = 0
    fetched_transcripts = 0
    for i, stub in enumerate(stubs, 1):
        case = fetch_case(stub)
        if not case:
            continue
        fetched_cases += 1
        for audio in (case.get("oral_argument_audio") or []):
            if audio.get("unavailable"):
                continue
            t = fetch_transcript(audio)
            if t and t.get("transcript"):
                fetched_transcripts += 1
        if i % 10 == 0:
            print(f"  progress {i}/{len(stubs)}: {fetched_cases} cases, {fetched_transcripts} transcripts")
    print(f"  done: {fetched_cases} cases, {fetched_transcripts} transcripts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, help="Earliest term (e.g. 2005)")
    ap.add_argument("--end", type=int, help="Latest term inclusive (e.g. 2024)")
    ap.add_argument("--term", type=int, help="Single term shortcut")
    ap.add_argument("--max-cases", type=int, help="Cap per term (debug)")
    args = ap.parse_args()

    if args.term is not None:
        terms = [args.term]
    elif args.start is not None and args.end is not None:
        terms = list(range(args.start, args.end + 1))
    else:
        ap.error("provide --term or --start AND --end")

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    for t in terms:
        process_term(t, max_cases=args.max_cases)


if __name__ == "__main__":
    main()
