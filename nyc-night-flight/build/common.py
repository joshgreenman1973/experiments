"""Shared bits for the Night Flight data scripts."""
import datetime as dt
import gzip
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "src"
OUT = ROOT / "data"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

# BirdCast regions are counties; each New York City borough is one county.
BOROUGHS = [
    ("US-NY-005", "Bronx"),
    ("US-NY-047", "Brooklyn"),
    ("US-NY-061", "Manhattan"),
    ("US-NY-081", "Queens"),
    ("US-NY-085", "Staten Island"),
]

# BirdCast's live feed runs Mar. 1 to June 15 and Aug. 1 to Nov. 15.
SEASON_DATES = {"spring": ((3, 1), (6, 15)), "fall": ((8, 1), (11, 15))}
FIRST_SEASON = (2021, "fall")  # earliest season BirdCast's county dashboard serves


def season_key(year, name):
    return f"{year}-{name}"


def season_bounds(year, name):
    (sm, sd), (em, ed) = SEASON_DATES[name]
    return dt.date(year, sm, sd), dt.date(year, em, ed)


def all_seasons(today=None):
    """Every season from FIRST_SEASON that has started by today, oldest first."""
    today = today or dt.date.today()
    out = []
    for year in range(FIRST_SEASON[0], today.year + 1):
        for name in ("spring", "fall"):
            order = {"spring": 0, "fall": 1}
            if (year, order[name]) < (FIRST_SEASON[0], order[FIRST_SEASON[1]]):
                continue
            start, end = season_bounds(year, name)
            if start <= today:
                out.append((year, name, start, end))
    return out


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


class FetchError(RuntimeError):
    pass


def http_get(url, tries=4, timeout=90, accept="*/*"):
    """GET with gzip and retries. Raises FetchError when retries run out;
    never returns an empty stand-in."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body.decode("utf-8")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            code = getattr(e, "code", None)
            if code in (400, 401, 403, 404) and attempt >= 1:
                break
            time.sleep(5 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text())


def write_json(path, obj, indent=None):
    """Atomic write."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=indent, separators=(",", ":") if indent is None else None, ensure_ascii=False))
    os.replace(tmp, p)
