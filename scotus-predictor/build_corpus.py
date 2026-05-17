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


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
    DROP TABLE IF EXISTS questions;
    DROP TABLE IF EXISTS cases;
    DROP TABLE IF EXISTS justices;

    CREATE TABLE justices (
        justice_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        question_count INTEGER DEFAULT 0
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

    CREATE INDEX idx_q_justice ON questions(justice_id);
    CREATE INDEX idx_q_case ON questions(case_id);
    CREATE INDEX idx_q_term ON questions(term);
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

    conn.execute("""
        UPDATE justices SET question_count = (
            SELECT COUNT(*) FROM questions WHERE questions.justice_id = justices.justice_id
        )
    """)

    conn.commit()
    print(f"Built corpus: {len(case_rows)} cases, {question_count} questions")
    for row in conn.execute("SELECT display_name, question_count FROM justices ORDER BY question_count DESC"):
        print(f"  {row[0]}: {row[1]} questions")
    conn.close()


if __name__ == "__main__":
    main()
