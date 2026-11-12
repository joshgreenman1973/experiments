#!/usr/bin/env python3
"""Re-fetch the page behind every researched contact and confirm the email
address or phone number is literally on it.

The research files (data/staff_*.json, data/elect_research.json) were compiled
by searching the web. A search tool can paraphrase a page, or produce an address
that merely looks right. So nothing from those files reaches the directory until
this script has downloaded the cited page itself and found the same characters
in it. Contacts that cannot be confirmed are written to data/unverified.json and
left out.
"""
import glob
import hashlib
import html
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "raw", "verify")
os.makedirs(CACHE, exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def cf_decode(h):
    k = int(h[:2], 16)
    return "".join(chr(int(h[i:i + 2], 16) ^ k) for i in range(2, len(h), 2))


def fetch(url):
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key)
    if not os.path.exists(path) or os.path.getsize(path) < 200:
        for extra in (["--http1.1"], []):
            subprocess.run(["/usr/bin/curl", "-sL", *extra, "-A", UA,
                            "-H", "Accept: text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
                            "-H", "Accept-Language: en-US,en;q=0.9", "--compressed",
                            "--max-time", "40", "-o", path, url], capture_output=True)
            if os.path.exists(path) and os.path.getsize(path) > 200:
                break
    if not os.path.exists(path):
        return ""
    raw = open(path, "rb").read()
    if raw[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
        except Exception:
            return ""
    text = raw.decode("utf-8", "ignore")
    if "Just a moment..." in text[:600] or "cf-challenge" in text[:3000]:
        return "__BLOCKED__"
    text = re.sub(r'data-cfemail="([0-9a-f]+)"', lambda m: " " + cf_decode(m.group(1)) + " ", text)
    text = re.sub(r'email-protection#([0-9a-f]+)', lambda m: " " + cf_decode(m.group(1)) + " ", text)
    text = html.unescape(text)
    text = text.replace("%40", "@").replace("​", "")
    return text


def has_email(text, email):
    return email.lower() in text.lower()


def has_phone(text, phone):
    d = re.sub(r"\D", "", phone)
    if d.startswith("1") and len(d) == 11:
        d = d[1:]
    if len(d) < 10:
        return False
    d = d[:10]
    pat = r"\(?%s\)?[\s.\-‐-― /]{0,3}%s[\s.\-‐-― ]{0,3}%s" % (d[:3], d[3:6], d[6:])
    plain = re.sub(r"<[^>]+>", "", text)
    return bool(re.search(pat, text) or re.search(pat, plain) or ("tel:" in text and d in re.sub(r"[^\d]", "", "".join(re.findall(r"tel:[+\d\-(). %]+", text)))))


def check(url, email, phone):
    """-> (email_ok, phone_ok, state)"""
    if not url or not url.startswith("http"):
        return False, False, "no source"
    text = fetch(url)
    if text == "__BLOCKED__" and "web.archive.org" not in url:
        # the site turns scripts away; read the Internet Archive's copy of the same page
        text = fetch("https://web.archive.org/web/2026id_/" + url)
        if not text or text == "__BLOCKED__" or len(text) < 2000:
            mpath = os.path.join(DATA, "archive_copies.json")
            amap = json.load(open(mpath)) if os.path.exists(mpath) else {}
            try:
                if url in amap:
                    raise KeyError
                q = subprocess.run(["/usr/bin/curl", "-s", "--max-time", "30",
                                    "http://archive.org/wayback/available?timestamp=20261101&url=" + re.sub(r"^https?://(www\.)?", "", url)],
                                   capture_output=True, text=True).stdout
                snap = json.loads(q)["archived_snapshots"]["closest"]["url"]
                amap[url] = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap).replace("http://", "https://")
                json.dump(amap, open(mpath, "w"), indent=1)
            except KeyError:
                pass
            except Exception:
                pass
            text = fetch(amap[url]) if url in amap else ""
        if text and text != "__BLOCKED__" and len(text) > 2000:
            e_ok = bool(email) and has_email(text, email)
            p_ok = bool(phone) and has_phone(text, phone)
            return e_ok, p_ok, "archive copy"
        return False, False, "blocked"
    if text == "__BLOCKED__":
        return False, False, "blocked"
    if not text:
        return False, False, "fetch failed"
    e_ok = bool(email) and has_email(text, email)
    p_ok = bool(phone) and has_phone(text, phone)
    return e_ok, p_ok, "fetched"


def main():
    files = sorted(glob.glob(os.path.join(DATA, "staff_*.json")))
    files = [f for f in files if not f.endswith("staff_verified.json")]
    kept, dropped = [], []
    for f in files:
        try:
            rows = json.load(open(f))
        except Exception as exc:
            print(f"  ! {os.path.basename(f)} unreadable: {exc}")
            continue
        if isinstance(rows, dict):
            rows = rows.get("staff") or rows.get("people") or rows.get("rows") or []
        n_e = n_p = 0
        for r in rows:
            r = {k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
            r["file"] = os.path.basename(f)
            email, phone = r.get("email") or "", r.get("phone") or ""
            if not (r.get("staff_name") or email or phone):
                continue
            e_ok, p_ok, state = check(r.get("source_url") or "", email, phone)
            r["state"] = state
            if email and not e_ok:
                dropped.append(dict(r, what="email", value=email))
                r["email"] = ""
            parts = [x.strip() for x in re.split(r";", phone) if re.search(r"\d{3}\D*\d{4}", x)]
            if len(parts) > 1:
                good = [x for x in parts if check(r.get("source_url") or "", "", x)[1]]
                for x in parts:
                    if x not in good:
                        dropped.append(dict(r, what="phone", value=x))
                r["phone"] = "; ".join(good)
            elif phone and not p_ok:
                dropped.append(dict(r, what="phone", value=phone))
                r["phone"] = ""
            n_e += bool(r["email"])
            n_p += bool(r["phone"])
            kept.append(r)
        print(f"  {os.path.basename(f):28} rows {len(rows):4}  emails confirmed {n_e:4}  phones confirmed {n_p:4}")
    json.dump(kept, open(os.path.join(DATA, "staff_verified.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(dropped, open(os.path.join(DATA, "unverified.json"), "w"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("  dropped:", len(dropped), dict(Counter(d["state"] for d in dropped)))


if __name__ == "__main__":
    main()
