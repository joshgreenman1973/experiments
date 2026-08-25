#!/usr/bin/env python3
"""Harvest de Blasio-era transcripts (2014-2021) from the Wayback Machine.

Live nyc.gov 301s these URLs away, so the Internet Archive is the only route.

Two lessons baked in:
  * urllib gets 503s from the Archive where curl gets 200s -> shell out to curl.
  * Asking for a year hint ("/2014id_/") returns stub pages; we must use the
    exact snapshot timestamps that CDX reports with statuscode 200, and fall
    back to other snapshots of the same release when one comes back empty.
"""
import re, json, glob, time, pathlib, subprocess, collections

HERE = pathlib.Path(__file__).parent
OUT = HERE / "db_transcripts"
OUT.mkdir(exist_ok=True)
UA_STR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
MIN_TEXT = 2000  # a real transcript page; stubs strip to a few hundred chars

# release key -> list of (timestamp, original url)
cands = collections.defaultdict(list)
for f in glob.glob(str(HERE / "db_cdx2" / "*.txt")):
    for line in open(f, errors="ignore"):
        parts = line.split()
        if len(parts) < 2:
            continue
        ts, url = parts[0], parts[1]
        m = re.search(r"/office-of-the-mayor/news/(?:sp/)?(\d{1,4})-(\d{2})/([^\s?]*)", url)
        if not m:
            continue
        n, yy, slug = int(m.group(1)), m.group(2), m.group(3)
        if "transcript" not in slug.lower() or not ("14" <= yy <= "21"):
            continue
        cands[(yy, n)].append((ts, url, slug))

work = sorted(cands.items())
print(f"{len(work)} distinct de Blasio transcripts, "
      f"{sum(len(v) for v in cands.values())} candidate snapshots", flush=True)


def strip(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    t = re.sub(r"<[^>]+>", " ", h)
    for a, b in [("&nbsp;", " "), ("&rsquo;", "'"), ("&ldquo;", '"'),
                 ("&rdquo;", '"'), ("&amp;", "&"), ("&#39;", "'")]:
        t = t.replace(a, b)
    t = re.sub(r"\s+:\s*", ": ", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def fetch(ts, url):
    """Return (http_status, text). A 503 is throttling, NOT a missing snapshot -
    conflating the two was what made a whole earlier run look like dead links."""
    wb = f"http://web.archive.org/web/{ts}id_/{url}"
    p = subprocess.run(
        ["curl", "-s", "-L", "-m", "60", "-A", UA_STR, "-w", "\n%{http_code}", wb],
        capture_output=True,
    )
    if p.returncode != 0:
        return 0, ""
    body = p.stdout.decode("utf-8", "ignore")
    nl = body.rfind("\n")
    code = body[nl + 1 :].strip()
    return (int(code) if code.isdigit() else 0), strip(body[:nl])


done = err = skip = 0
retry = []
for (yy, n), snaps in work:
    f = OUT / f"20{yy}_{n:04d}.json"
    if f.exists() and f.stat().st_size > 800:
        skip += 1
        continue
    # ONE request per release, widely spaced: the Archive throttles bursts.
    ts, url, slug = sorted(snaps, reverse=True)[0]
    code, t = fetch(ts, url)
    if code == 503 or code == 0:
        time.sleep(60)
        code, t = fetch(ts, url)
    if not t or len(t) < MIN_TEXT:
        err += 1
        retry.append((yy, n))
        print(f"  MISS 20{yy}-{n} code={code} len={len(t) if t else 0}", flush=True)
        continue
    used = (ts, url, slug)
    f.write_text(json.dumps({
        "year": f"20{yy}", "release": n, "slug": used[2], "timestamp": used[0],
        "url": used[1], "text": t, "chars": len(t)}, indent=1), encoding="utf-8")
    done += 1
    if done % 25 == 0:
        print(f"  {done} fetched / {skip} cached / {err} failed", flush=True)
    time.sleep(4.0)

json.dump(retry, open(HERE / "db_retry.json", "w"))
print(f"DONE fetched={done} cached={skip} failed={err}", flush=True)
