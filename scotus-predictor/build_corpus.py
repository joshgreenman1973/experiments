"""Build a SQLite corpus of justice questions from cached Oyez data.

Reads everything under data/cases and data/transcripts, attributes each
turn to a justice via the stable Oyez identifier, captures the question
text and surrounding advocate context, and writes to corpus.db.

Re-runnable: drops and rebuilds the questions table on each invocation.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "data" / "cases"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
OPINIONS_DIR = ROOT / "data" / "opinions"
DB_PATH = ROOT / "corpus.db"

# Current 9 justices (Oyez identifiers). Keep ordered by seniority.
CURRENT_JUSTICES = {
    "john_g_roberts_jr": "Chief Justice John G. Roberts, Jr.",
    "clarence_thomas": "Justice Clarence Thomas",
    "samuel_a_alito_jr": "Justice Samuel A. Alito, Jr.",
    "sonia_sotomayor": "Justice Sonia Sotomayor",
    "elena_kagan": "Justice Elena Kagan",
    "neil_gorsuch": "Justice Neil Gorsuch",
    "brett_m_kavanaugh": "Justice Brett M. Kavanaugh",
    "amy_coney_barrett": "Justice Amy Coney Barrett",
    "ketanji_brown_jackson": "Justice Ketanji Brown Jackson",
}

# Map of last name -> justice_id for matching opinion-author entries.
LASTNAME_TO_JUSTICE_ID = {
    "Roberts": "john_g_roberts_jr",
    "Thomas": "clarence_thomas",
    "Alito": "samuel_a_alito_jr",
    "Sotomayor": "sonia_sotomayor",
    "Kagan": "elena_kagan",
    "Gorsuch": "neil_gorsuch",
    "Kavanaugh": "brett_m_kavanaugh",
    "Barrett": "amy_coney_barrett",
    "Jackson": "ketanji_brown_jackson",
}


def turn_text(turn: dict) -> str:
    blocks = turn.get("text_blocks") or []
    return " ".join((b.get("text") or "").strip() for b in blocks).strip()


def turn_speaker_id(turn: dict) -> str | None:
    spk = turn.get("speaker") or {}
    return spk.get("identifier")


def turn_speaker_name(turn: dict) -> str | None:
    spk = turn.get("speaker") or {}
    return spk.get("name")


def turn_is_current_justice(turn: dict) -> bool:
    return turn_speaker_id(turn) in CURRENT_JUSTICES


def case_metadata(case: dict) -> dict:
    timeline = case.get("timeline") or []
    decision_date = None
    argument_date = None
    for evt in timeline:
        if not evt:
            continue
        label = (evt.get("event") or "").lower()
        dates = evt.get("dates") or []
        if not dates:
            continue
        ts = dates[0]
        if "argued" in label and not argument_date:
            argument_date = ts
        if "decided" in label and not decision_date:
            decision_date = ts
    # written_decision summary if present
    decisions = case.get("decisions") or []
    decision_summary = None
    majority_author = None
    if decisions:
        d0 = decisions[0]
        decision_summary = d0.get("description")
        ma = d0.get("majority_author") or {}
        majority_author = ma.get("name")
    return {
        "case_id": case.get("ID"),
        "case_name": case.get("name"),
        "term": case.get("term"),
        "docket_number": case.get("docket_number"),
        "question_presented": (case.get("question") or "").strip(),
        "case_description": (case.get("description") or "").strip(),
        "facts_of_the_case": (case.get("facts_of_the_case") or "").strip(),
        "argument_date": argument_date,
        "decision_date": decision_date,
        "decision_summary": decision_summary,
        "majority_author": majority_author,
        "citation": (case.get("citation") or {}).get("href") if isinstance(case.get("citation"), dict) else None,
        "justia_url": case.get("justia_url"),
        "oyez_href": case.get("href"),
    }


def iter_cases():
    if not CASES_DIR.exists():
        return
    for term_dir in sorted(CASES_DIR.iterdir()):
        if not term_dir.is_dir():
            continue
        for case_file in sorted(term_dir.glob("*.json")):
            try:
                yield json.loads(case_file.read_text())
            except Exception as e:
                print(f"  ! skip {case_file}: {e}")


def load_transcript(audio_href: str) -> dict | None:
    """Audio href like .../oral_argument_audio/25493 -> data/transcripts/25493.json"""
    audio_id = audio_href.rstrip("/").rsplit("/", 1)[-1]
    path = TRANSCRIPTS_DIR / f"{audio_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def extract_questions(case: dict):
    """Yield question records for current-justice turns in this case."""
    meta = case_metadata(case)
    for audio in (case.get("oral_argument_audio") or []):
        if audio.get("unavailable"):
            continue
        href = audio.get("href")
        if not href:
            continue
        t = load_transcript(href)
        if not t:
            continue
        transcript = t.get("transcript") or {}
        sections = transcript.get("sections") or []
        # Flatten turns across sections; we lose section boundary but keep order.
        turns = []
        for s in sections:
            turns.extend(s.get("turns") or [])
        for i, turn in enumerate(turns):
            if not turn_is_current_justice(turn):
                continue
            q_text = turn_text(turn)
            if len(q_text) < 12:
                continue  # noise: "Yes." "Right."
            # Heuristic: keep turns that contain a '?' OR are substantial (>40 chars).
            if "?" not in q_text and len(q_text) < 40:
                continue
            justice_id = turn_speaker_id(turn)
            # Context: prior non-justice turn (the advocate setup) and next turn (the answer).
            before = ""
            for j in range(i - 1, max(-1, i - 4), -1):
                pt = turns[j]
                if turn_is_current_justice(pt):
                    continue
                txt = turn_text(pt)
                if txt:
                    before = txt[-600:]
                    break
            after = ""
            for j in range(i + 1, min(len(turns), i + 4)):
                nt = turns[j]
                if turn_is_current_justice(nt):
                    continue
                txt = turn_text(nt)
                if txt:
                    after = txt[:600]
                    break
            yield {
                **meta,
                "justice_id": justice_id,
                "justice_name": turn_speaker_name(turn),
                "audio_id": href.rstrip("/").rsplit("/", 1)[-1],
                "turn_index": i,
                "turn_start": turn.get("start"),
                "question_text": q_text,
                "context_before": before,
                "context_after": after,
            }


def iter_opinion_files():
    if not OPINIONS_DIR.exists():
        return
    for f in sorted(OPINIONS_DIR.glob("*.json")):
        try:
            yield json.loads(f.read_text())
        except Exception as e:
            print(f"  ! skip opinion {f}: {e}")


# Heuristics for skipping the boilerplate header that prefixes every Justia
# opinion ("SUPREME COURT OF THE UNITED STATES", "[June 2, 2008]", etc.).
# The actual prose starts with the first paragraph that looks like a sentence.
def _is_header_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    # ALL-CAPS lines or single-bracket date lines are header furniture.
    if len(s) < 80 and s.upper() == s and re.search(r"[A-Z]", s):
        return True
    if re.match(r"^\[[^\]]+\]\s*$", s):
        return True
    if re.match(r"^(NO\.|No\.) ?[\d\-]+\s*$", s):
        return True
    return False


def _strip_opinion_header(text: str) -> str:
    lines = text.split("\n")
    # Drop leading header lines until we hit something that looks like body prose.
    i = 0
    while i < len(lines) and _is_header_line(lines[i]):
        i += 1
    return "\n".join(lines[i:]).strip()


def chunk_opinion(text: str, target_words: int = 220, max_chunks: int = 8) -> list[str]:
    """Split an opinion into ~target_words-sized chunks on paragraph boundaries.

    We keep paragraphs intact (they're the natural unit of legal prose) and
    accumulate them into chunks until each chunk hits the target word count.
    Caps at max_chunks per opinion so a single 60-page dissent doesn't
    dominate one justice's index.
    """
    text = _strip_opinion_header(text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # Fallback for opinions cached before paragraph-preservation was fixed:
    # group sentences into ~5-sentence paragraphs.
    if len(paragraphs) <= 1 and len(text.split()) > 400:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"\(\[])", text.replace("\n", " "))
        paragraphs = []
        buf: list[str] = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            buf.append(s)
            if len(buf) >= 5:
                paragraphs.append(" ".join(buf))
                buf = []
        if buf:
            paragraphs.append(" ".join(buf))
    chunks: list[str] = []
    buf: list[str] = []
    buf_words = 0
    for p in paragraphs:
        wc = len(p.split())
        if buf and buf_words + wc > target_words * 1.4:
            chunks.append("\n\n".join(buf))
            buf = [p]
            buf_words = wc
        else:
            buf.append(p)
            buf_words += wc
        if buf_words >= target_words:
            chunks.append("\n\n".join(buf))
            buf = []
            buf_words = 0
    if buf:
        chunks.append("\n\n".join(buf))
    # Drop very short tail chunks (signature blocks, footnotes scraps).
    chunks = [c for c in chunks if len(c.split()) >= 60]
    if len(chunks) > max_chunks:
        # Spread the selection: take the first chunk (intro framing) plus
        # evenly-spaced chunks across the body. Intro is usually the most
        # signal-dense for voice/doctrinal positioning.
        idxs = [0]
        step = (len(chunks) - 1) / (max_chunks - 1)
        for k in range(1, max_chunks):
            idxs.append(round(k * step))
        chunks = [chunks[i] for i in sorted(set(idxs))]
    return chunks


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
    DROP TABLE IF EXISTS opinion_chunks;
    DROP TABLE IF EXISTS opinions;
    DROP TABLE IF EXISTS questions;
    DROP TABLE IF EXISTS cases;
    DROP TABLE IF EXISTS justices;

    CREATE TABLE justices (
        justice_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        question_count INTEGER DEFAULT 0,
        opinion_chunk_count INTEGER DEFAULT 0
    );

    CREATE TABLE cases (
        case_id TEXT PRIMARY KEY,
        case_name TEXT,
        term INTEGER,
        docket_number TEXT,
        question_presented TEXT,
        case_description TEXT,
        facts_of_the_case TEXT,
        argument_date INTEGER,
        decision_date INTEGER,
        decision_summary TEXT,
        majority_author TEXT,
        citation TEXT,
        justia_url TEXT,
        oyez_href TEXT
    );

    CREATE TABLE questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        justice_id TEXT NOT NULL,
        justice_name TEXT,
        case_id TEXT,
        case_name TEXT,
        term INTEGER,
        audio_id TEXT,
        turn_index INTEGER,
        turn_start REAL,
        question_text TEXT NOT NULL,
        context_before TEXT,
        context_after TEXT,
        question_presented TEXT,
        FOREIGN KEY (justice_id) REFERENCES justices (justice_id),
        FOREIGN KEY (case_id) REFERENCES cases (case_id)
    );

    CREATE TABLE opinions (
        justia_opinion_id INTEGER PRIMARY KEY,
        justice_id TEXT NOT NULL,
        judge_full_name TEXT,
        case_id TEXT,
        case_name TEXT,
        term INTEGER,
        opinion_type TEXT,            -- majority | concurring | dissenting | per_curiam | ...
        title TEXT,
        justia_url TEXT,
        text_length INTEGER,
        FOREIGN KEY (justice_id) REFERENCES justices (justice_id),
        FOREIGN KEY (case_id) REFERENCES cases (case_id)
    );

    CREATE TABLE opinion_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        justia_opinion_id INTEGER NOT NULL,
        justice_id TEXT NOT NULL,
        case_id TEXT,
        case_name TEXT,
        term INTEGER,
        opinion_type TEXT,
        chunk_index INTEGER,
        text TEXT NOT NULL,
        FOREIGN KEY (justia_opinion_id) REFERENCES opinions (justia_opinion_id),
        FOREIGN KEY (justice_id) REFERENCES justices (justice_id)
    );

    CREATE INDEX idx_q_justice ON questions(justice_id);
    CREATE INDEX idx_q_case ON questions(case_id);
    CREATE INDEX idx_q_term ON questions(term);
    CREATE INDEX idx_oc_justice ON opinion_chunks(justice_id);
    CREATE INDEX idx_oc_opinion ON opinion_chunks(justia_opinion_id);
    """)
    for jid, name in CURRENT_JUSTICES.items():
        conn.execute("INSERT INTO justices (justice_id, display_name) VALUES (?, ?)", (jid, name))


def main():
    if not CASES_DIR.exists():
        print(f"No data at {CASES_DIR}. Run fetch_transcripts.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    cases_seen = set()
    case_rows = []
    question_count = 0

    for case in iter_cases():
        if not case:
            continue
        cid = case.get("ID")
        if not cid or cid in cases_seen:
            continue
        meta = case_metadata(case)
        case_rows.append(meta)
        cases_seen.add(cid)

        for q in extract_questions(case):
            conn.execute("""
                INSERT INTO questions (
                    justice_id, justice_name, case_id, case_name, term,
                    audio_id, turn_index, turn_start, question_text,
                    context_before, context_after, question_presented
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                q["justice_id"], q["justice_name"], q["case_id"], q["case_name"], q["term"],
                q["audio_id"], q["turn_index"], q["turn_start"], q["question_text"],
                q["context_before"], q["context_after"], q["question_presented"],
            ))
            question_count += 1

    for cr in case_rows:
        conn.execute("""
            INSERT OR REPLACE INTO cases (
                case_id, case_name, term, docket_number, question_presented,
                case_description, facts_of_the_case, argument_date, decision_date,
                decision_summary, majority_author, citation, justia_url, oyez_href
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cr["case_id"], cr["case_name"], cr["term"], cr["docket_number"], cr["question_presented"],
            cr["case_description"], cr["facts_of_the_case"], cr["argument_date"], cr["decision_date"],
            cr["decision_summary"], cr["majority_author"], cr["citation"], cr["justia_url"], cr["oyez_href"],
        ))

    opinions_seen = 0
    opinion_chunks_added = 0
    for op in iter_opinion_files():
        last = op.get("judge_last_name")
        jid = LASTNAME_TO_JUSTICE_ID.get(last)
        if not jid:
            continue
        text = op.get("text") or ""
        if len(text) < 400:
            continue
        op_id = op.get("justia_opinion_id")
        if op_id is None:
            continue
        conn.execute("""
            INSERT OR REPLACE INTO opinions (
                justia_opinion_id, justice_id, judge_full_name, case_id, case_name,
                term, opinion_type, title, justia_url, text_length
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            op_id, jid, op.get("judge_full_name"), op.get("case_id"), op.get("case_name"),
            op.get("term"), op.get("type"), op.get("title"), op.get("justia_url"), len(text),
        ))
        opinions_seen += 1
        for idx, chunk in enumerate(chunk_opinion(text)):
            conn.execute("""
                INSERT INTO opinion_chunks (
                    justia_opinion_id, justice_id, case_id, case_name, term,
                    opinion_type, chunk_index, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                op_id, jid, op.get("case_id"), op.get("case_name"), op.get("term"),
                op.get("type"), idx, chunk,
            ))
            opinion_chunks_added += 1

    conn.execute("""
        UPDATE justices SET question_count = (
            SELECT COUNT(*) FROM questions WHERE questions.justice_id = justices.justice_id
        )
    """)
    conn.execute("""
        UPDATE justices SET opinion_chunk_count = (
            SELECT COUNT(*) FROM opinion_chunks WHERE opinion_chunks.justice_id = justices.justice_id
        )
    """)

    conn.commit()
    print(f"Built corpus: {len(case_rows)} cases, {question_count} questions, "
          f"{opinions_seen} opinions ({opinion_chunks_added} chunks)")
    for row in conn.execute("""
        SELECT display_name, question_count, opinion_chunk_count
        FROM justices ORDER BY question_count DESC
    """):
        print(f"  {row[0]}: {row[1]} questions, {row[2]} opinion chunks")
    conn.close()


if __name__ == "__main__":
    main()
