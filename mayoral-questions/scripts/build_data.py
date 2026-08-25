#!/usr/bin/env python3
"""Build the questions-per-week dataset from harvested mayoral transcripts.

Sources
  Adams + Mamdani (2022-2026): nyc.gov AEM model tree. Exact dates come from
    the articlesearch listing's articleDate field.
  de Blasio (2014-2021): Internet Archive snapshots of the retired nyc.gov
    pages. Exact dates are parsed from the transcript body.

Metric
  A "question" is one `Question:` speaker turn in the published transcript.
  Follow-ups count separately. This measures questions the administration put
  on the record, which is not identical to questions reporters asked.
"""
import json, re, sys, pathlib, collections, urllib.request
from datetime import date, datetime

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRATCH = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "raw"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

MONTHS = ("January February March April May June July August September "
          "October November December").split()
DATE_RE = re.compile(r"(%s)\s+(\d{1,2}),\s+(20\d{2})" % "|".join(MONTHS))

TERMS = [  # inclusive start, inclusive end
    ("de Blasio", date(2014, 1, 1), date(2021, 12, 31)),
    ("Adams",     date(2022, 1, 1), date(2025, 12, 31)),
    ("Mamdani",   date(2026, 1, 1), date(2026, 12, 31)),
]


def mayor_for(d):
    for name, a, b in TERMS:
        if a <= d <= b:
            return name
    return None


def normalize(t):
    """nyc.gov splits speaker labels from their colons across text nodes."""
    t = t.replace(" ", " ")
    t = re.sub(r"\s+:\s*", ": ", t)
    return re.sub(r"[ \t]{2,}", " ", t)


def count_questions(t):
    nq = len(re.findall(r"Question:", t))
    mayor = other = 0
    for m in re.finditer(r"Question:\s*(.{0,500}?)\s([A-Z][A-Za-z.\-' ]{2,45}):", t, re.S):
        spk = m.group(2).strip().lower()
        if spk.startswith("mayor"):
            mayor += 1
        else:
            other += 1
    return nq, mayor, other


def load_date_map():
    """link -> ISO date, from the mayor's office article listing."""
    url = ("https://www.nyc.gov/bin/nyc/articlesearch.json"
           "?path=/content/nycgov/mayors-office/en/news&page=0&limit=5&year=2023")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    res = json.loads(urllib.request.urlopen(req, timeout=90).read().decode())["results"]
    out = {}
    for a in res:
        link, ad = a.get("link"), a.get("articleDate")
        if not (link and ad):
            continue
        try:
            out[link] = datetime.strptime(ad.strip(), "%B %d, %Y").date()
        except ValueError:
            pass
    return out


def parse_body_date(t):
    m = DATE_RE.search(t[:3000])
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTHS.index(m.group(1)) + 1, int(m.group(2)))
    except ValueError:
        return None


def main():
    events, undated = [], collections.Counter()

    dmap = load_date_map()
    print(f"listing dates: {len(dmap)}")

    for f in sorted((SCRATCH / "transcripts").glob("*.json")):
        d = json.loads(f.read_text())
        t = normalize(d["text"])
        when = dmap.get(d["link"])
        if not when:
            when = parse_body_date(t)
        if not when:
            undated["adams_mamdani"] += 1
            continue
        nq, mq, oq = count_questions(t)
        events.append({"date": when.isoformat(), "mayor": mayor_for(when),
                       "title": d["title"], "questions": nq,
                       "answered_mayor": mq, "answered_other": oq,
                       "source": "nyc.gov", "url": "https://www.nyc.gov" + d["link"]})

    dbdir = SCRATCH / "db_transcripts"
    if dbdir.exists():
        for f in sorted(dbdir.glob("*.json")):
            d = json.loads(f.read_text())
            t = normalize(d["text"])
            when = parse_body_date(t)
            if not when:
                undated["deblasio"] += 1
                continue
            nq, mq, oq = count_questions(t)
            events.append({"date": when.isoformat(), "mayor": mayor_for(when),
                           "title": d["slug"].replace("-", " ")[:120], "questions": nq,
                           "answered_mayor": mq, "answered_other": oq,
                           "source": "web.archive.org", "url": d["url"]})

    events = [e for e in events if e["mayor"]]
    events.sort(key=lambda e: e["date"])
    print(f"events: {len(events)}  undated dropped: {dict(undated)}")

    # ---- weekly series (ISO week) -------------------------------------
    weekly = collections.defaultdict(lambda: {"questions": 0, "events": 0})
    for e in events:
        y, w, _ = date.fromisoformat(e["date"]).isocalendar()
        k = f"{y}-W{w:02d}"
        weekly[k]["questions"] += e["questions"]
        weekly[k]["events"] += 1 if e["questions"] else 0

    # ---- coverage: how much of each mayor's transcript record we hold ----
    # de Blasio's corpus is only reachable through the Internet Archive, whose
    # coverage is partial. Per-week rates are meaningless without this, because
    # a missing transcript silently removes its questions from the numerator.
    expected = {}
    cdx = SCRATCH / "db_cdx2"
    if cdx.exists():
        keys = set()
        for f in cdx.glob("*.txt"):
            for line in f.read_text(errors="ignore").splitlines():
                parts = line.split()
                if len(parts) < 2:
                    continue
                m = re.search(r"/news/(?:sp/)?(\d{1,4})-(\d{2})/([^\s?]*)", parts[1])
                if m and "transcript" in m.group(3).lower() and "14" <= m.group(2) <= "21":
                    keys.add((m.group(2), int(m.group(1))))
        expected["de Blasio"] = len(keys)

    # ---- per-mayor summary, normalised per week -----------------------
    summary = []
    for name, a, b in TERMS:
        ev = [e for e in events if e["mayor"] == name]
        if not ev:
            continue
        first, last = date.fromisoformat(ev[0]["date"]), date.fromisoformat(ev[-1]["date"])
        span_weeks = max(1, (min(last, b) - a).days / 7)
        q = sum(e["questions"] for e in ev)
        qa = sum(1 for e in ev if e["questions"])
        summary.append({
            "mayor": name, "from": a.isoformat(), "through": min(last, b).isoformat(),
            "weeks": round(span_weeks, 1), "transcripts": len(ev), "qa_events": qa,
            "questions": q,
            "questions_per_week": round(q / span_weeks, 1),
            "events_per_week": round(qa / span_weeks, 2),
            "questions_per_event": round(q / qa, 1) if qa else 0,
            "expected_transcripts": expected.get(name),
            "coverage_pct": (round(100 * len(ev) / expected[name])
                             if expected.get(name) else 100),
            "complete": name not in expected or len(ev) >= expected[name] * 0.97,
            "mayor_answers_first_pct": round(
                100 * sum(e["answered_mayor"] for e in ev) /
                max(1, sum(e["answered_mayor"] + e["answered_other"] for e in ev))),
        })

    out = {"generated": datetime.now().date().isoformat(),
           "metric": "One `Question:` speaker turn in a published transcript. "
                     "Follow-ups count separately.",
           "summary": summary,
           "weekly": [{"week": k, **v} for k, v in sorted(weekly.items())],
           "events": events}
    (ROOT / "data" / "questions.json").write_text(json.dumps(out, indent=1))

    print(f"\n{'mayor':<11}{'weeks':>7}{'Q&A ev':>8}{'questions':>11}"
          f"{'q/week':>9}{'q/event':>9}{'coverage':>10}{'':>4}")
    for r in summary:
        flag = "" if r["complete"] else "  <-- INCOMPLETE, q/week is a floor"
        print(f"{r['mayor']:<11}{r['weeks']:>7}{r['qa_events']:>8}{r['questions']:>11}"
              f"{r['questions_per_week']:>9}{r['questions_per_event']:>9}"
              f"{r['coverage_pct']:>9}%{flag}")


if __name__ == "__main__":
    main()
