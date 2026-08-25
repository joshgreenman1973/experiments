#!/usr/bin/env python3
"""Harvest every mayoral transcript from nyc.gov's AEM model endpoint (2022-2026).

The HTML pages 403 to scripted clients; the .model.json tree does not.
"""
import json, re, sys, time, pathlib, urllib.request, urllib.error

HERE = pathlib.Path(__file__).parent
OUT = HERE / "transcripts"
OUT.mkdir(exist_ok=True)
BASE = "https://www.nyc.gov"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def listing():
    u = f"{BASE}/bin/nyc/articlesearch.json?path=/content/nycgov/mayors-office/en/news&page=0&limit=5&year=2023"
    return json.loads(get(u))["results"]


def model_url(link):
    p = link[len("/mayors-office/news/") :]
    if p.endswith(".html"):
        p = p[:-5]
    return f"{BASE}/content/nycgov/mayors-office/en/news/{p}.model.json", p


def flatten(node, parts):
    if isinstance(node, dict):
        t = node.get("text")
        if isinstance(t, str):
            parts.append(t)
        for v in node.values():
            if isinstance(v, (dict, list)):
                flatten(v, parts)
    elif isinstance(node, list):
        for x in node:
            flatten(x, parts)


def main():
    res = listing()
    todo = []
    for a in res:
        link = a.get("link") or ""
        title = str(a.get("title") or "")
        if not link.startswith("/mayors-office/news/"):
            continue
        if not title.lower().startswith("transcript"):
            continue
        todo.append((link, title))
    print(f"{len(todo)} transcripts to fetch", flush=True)

    done = err = 0
    for i, (link, title) in enumerate(todo):
        url, p = model_url(link)
        slug = p.replace("/", "_")
        f = OUT / f"{slug}.json"
        if f.exists() and f.stat().st_size > 500:
            done += 1
            continue
        try:
            raw = get(url)
        except Exception as e:
            err += 1
            print(f"  ERR {slug}: {e}", flush=True)
            time.sleep(2)
            continue
        parts = []
        try:
            flatten(json.loads(raw), parts)
        except Exception:
            err += 1
            continue
        text = re.sub(r"<[^>]+>", " ", " ".join(parts))
        text = re.sub(r"[ \t]{2,}", " ", text)
        m = re.search(r"/news/(\d{4})/(\d{2})/", link)
        f.write_text(
            json.dumps(
                {
                    "slug": slug,
                    "link": link,
                    "title": title,
                    "year": m.group(1) if m else None,
                    "month": m.group(2) if m else None,
                    "text": text,
                    "chars": len(text),
                },
                indent=1,
            ),
            encoding="utf-8",
        )
        done += 1
        if done % 50 == 0:
            print(f"  {done}/{len(todo)} fetched ({err} errors)", flush=True)
        time.sleep(0.7)
    print(f"DONE {done} fetched, {err} errors", flush=True)


if __name__ == "__main__":
    main()
