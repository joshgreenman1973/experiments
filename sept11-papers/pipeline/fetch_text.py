#!/usr/bin/env python3
"""Fetch the full OCR text of every document via the portal's preview API.

POST /api/v2/preview with a result's `location` returns the indexed markdown
rendered as HTML. We strip it to plain text and store data/text/<key>.txt.
Runs a few workers, resumes on restart (skips files that exist), and keeps
re-reading the catalogue until the harvest is finished, so both can run at once.
"""
import json, os, sys, time, re, html
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://sept11documents.cityofnewyork.us/api/v2/preview"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CAT = os.path.join(DATA, "catalogue.jsonl")
PROG = os.path.join(DATA, "harvest_progress.json")
TXT = os.path.join(DATA, "text")
FAIL = os.path.join(DATA, "fetch_failures.jsonl")
os.makedirs(TXT, exist_ok=True)
WORKERS = int(os.environ.get("WORKERS", "4"))
TOTAL_BLOCKS = 1761

def key_of(row):
    k = row["mes:key"]
    m = re.search(r"(NYC-WTC_\d{9})", k)
    return m.group(1) if m else re.sub(r"[^A-Za-z0-9_-]", "_", k)

def to_text(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|pre|br)\s*>", "\n", h)
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = h.replace("\r", "")
    h = re.sub(r"[ \t ]+", " ", h)
    h = re.sub(r" *\n *", "\n", h)
    h = re.sub(r"\n{3,}", "\n\n", h)
    return h.strip() + "\n"

def fetch(row, tries=4):
    body = {"location": row["location"], "category": "september11 Connector",
            "categoryinstance": "September11_MD", "full_html": True,
            "properties": [{"name": "content", "formats": ["HTML"]}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "sept11-papers text fetcher (josh.greenman@gmail.com)"})
    last = None
    for t in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.load(r)
            props = d.get("result", {}).get("properties", [])
            c = next((p for p in props if p["id"] == "content"), None)
            h = (c or {}).get("data", [{}])[0].get("html") if c else None
            if h is None:
                last = "no content in response"; time.sleep(3 * (t + 1)); continue
            return to_text(h)
        except Exception as e:
            last = str(e); time.sleep(5 * (t + 1))
    raise RuntimeError(last)

def pending():
    seen = set()
    rows = []
    if not os.path.exists(CAT): return rows
    for line in open(CAT):
        try: row = json.loads(line)
        except Exception: continue
        k = key_of(row)
        if k in seen: continue
        seen.add(k)
        if not os.path.exists(os.path.join(TXT, k + ".txt")):
            row["_key"] = k; rows.append(row)
    return rows

def harvest_done():
    if not os.path.exists(PROG): return False
    return len(json.load(open(PROG))["done"]) >= TOTAL_BLOCKS

def main():
    done_n = 0; fail_n = 0; t0 = time.time()
    while True:
        rows = pending()
        if not rows:
            if harvest_done(): break
            time.sleep(20); continue
        with ThreadPoolExecutor(WORKERS) as ex:
            futs = {ex.submit(fetch, r): r for r in rows}
            for f in as_completed(futs):
                r = futs[f]
                try:
                    txt = f.result()
                    tmp = os.path.join(TXT, r["_key"] + ".tmp")
                    with open(tmp, "w") as out: out.write(txt)
                    os.replace(tmp, os.path.join(TXT, r["_key"] + ".txt"))
                    done_n += 1
                except Exception as e:
                    fail_n += 1
                    with open(FAIL, "a") as fl:
                        fl.write(json.dumps({"key": r["_key"], "err": str(e)}) + "\n")
                if (done_n + fail_n) % 200 == 0:
                    el = time.time() - t0
                    print(f"{done_n} fetched, {fail_n} failed, {el/60:.1f} min, {done_n/el:.2f}/s", flush=True)
    print(f"finished: {done_n} fetched, {fail_n} failed")

if __name__ == "__main__":
    main()
