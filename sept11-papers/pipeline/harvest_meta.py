#!/usr/bin/env python3
"""Harvest the full document catalogue from the 9/11 Document Portal search API.

The portal (Mindbreeze InSpire) exposes POST /api/v2/search without auth. It caps
count at 100 and ignores every paging parameter, so we partition the corpus by
Bates-number blocks of 100 (NYC-WTC_000NNNN00..99) and filter to the markdown
(OCR text) entries so each block returns at most 100 rows. Each document is
indexed twice (extension md and pdf); the md entry carries the same metadata.

Output: data/catalogue.jsonl, one row per document. Re-runnable; skips blocks
already fetched (progress in data/harvest_progress.json).
"""
import json, os, sys, time, re, html
import urllib.request

API = "https://sept11documents.cityofnewyork.us/api/v2/search"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
os.makedirs(DATA, exist_ok=True)
OUT = os.path.join(DATA, "catalogue.jsonl")
PROG = os.path.join(DATA, "harvest_progress.json")

PROPS = ["mes:key", "title", "agency", "source", "production_volume", "production_end",
         "box_name", "box_id", "folder_name", "page_count", "pdf_size", "mes:lang",
         "mes:siblings", "mes:docid", "mes:uniformdocid", "full_filename"]

def search(block, tries=5):
    regex = r".*NYC-WTC_000%04d[0-9]{2}.*" % block
    body = {
        "query": {"and": [{"unparsed": "extension:md"}, {"label": "mes:key", "regex": regex}]},
        "count": 100,
        "orderby": "mes:key",
        "properties": [{"name": p, "formats": ["VALUE"]} for p in PROPS]
                      + [{"name": "content", "formats": ["HTML"]}],
        "content_sample_length": 3000,
    }
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "sept11-papers harvester (josh.greenman@gmail.com)"})
    for t in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            wait = 5 * (t + 1)
            print(f"block {block}: {e}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"block {block}: gave up")

def val(p):
    d = p.get("data") or [{}]
    v = d[0].get("value")
    if isinstance(v, dict):
        if "str" in v: return v["str"]
        if "num" in v: return v["num"]
        return None
    return v

def rows(resp):
    for r in resp.get("resultset", {}).get("results", []):
        row = {"docid": r["id"], "location": r.get("location")}
        for p in r.get("properties", []):
            if p["id"] == "content":
                h = (p.get("data") or [{}])[0].get("html") or ""
                row["sample"] = html.unescape(re.sub(r"</?em>", "", h))
            else:
                row[p["id"]] = val(p)
        yield row

def main():
    max_block = int(sys.argv[1]) if len(sys.argv) > 1 else 1760
    done = set()
    if os.path.exists(PROG):
        done = set(json.load(open(PROG))["done"])
    n = 0
    with open(OUT, "a") as out:
        for b in range(0, max_block + 1):
            if b in done: continue
            resp = search(b)
            got = list(rows(resp))
            est = resp.get("estimated_count")
            if est and est > 100:
                print(f"WARNING block {b}: estimated {est} > 100, data lost", file=sys.stderr)
            for row in got:
                out.write(json.dumps(row) + "\n"); n += 1
            out.flush()
            done.add(b)
            json.dump({"done": sorted(done)}, open(PROG, "w"))
            if b % 50 == 0:
                print(f"block {b}: {len(got)} rows (total this run {n})", flush=True)
            time.sleep(0.3)
    print("done", n)

if __name__ == "__main__":
    main()
