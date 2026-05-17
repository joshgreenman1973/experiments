"""SCOTUS justice question predictor.

A small Flask app that:
  - Loads the SQLite corpus built by build_corpus.py
  - Builds a BM25 index per justice over their past questions
  - For an input case description, retrieves the closest real questions
    a given justice has asked on related topics
  - Calls Claude to generate plausible new questions in that justice's
    voice, grounded in the retrieved examples
  - Serves a minimal HTML UI at /

Run:
    export ANTHROPIC_API_KEY=...
    python server.py
    # then open http://localhost:5050
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Any

import anthropic
from flask import Flask, jsonify, request, send_file
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "corpus.db"
INDEX_HTML = ROOT / "index.html"
# Cost note: defaults to Haiku ($1 / $5 per 1M tokens). A typical prediction
# request is ~5-7K input tokens (system + 20 questions + 5 opinion chunks) and
# ~600 output tokens, i.e. well under one cent. Override with
# CLAUDE_MODEL=claude-sonnet-4-6 (~3x cost) or claude-opus-4-7 (~25x cost).
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")
TOP_K = int(os.environ.get("TOP_K", "20"))             # past questions
TOP_K_OPINIONS = int(os.environ.get("TOP_K_OPINIONS", "5"))  # opinion chunks
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "2048"))

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = set("""
a an and are as at be been but by for from has have he her him his i in into is
it its mr ms my of on or that the their them they this to was were what when
which who whom why will with would you your you're it's i'm we us our
""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1]


class Corpus:
    """Holds per-justice BM25 indexes for both oral-argument questions and
    written-opinion paragraphs."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.justices: dict[str, dict] = {}
        self.rows: dict[str, list[dict]] = {}            # justice_id -> question rows
        self.opinion_rows: dict[str, list[dict]] = {}    # justice_id -> opinion chunk rows
        self.indexes: dict[str, BM25Okapi] = {}
        self.opinion_indexes: dict[str, BM25Okapi] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if not self.db_path.exists():
            raise RuntimeError(f"corpus.db not found at {self.db_path}. Run build_corpus.py first.")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        for r in conn.execute("""
            SELECT justice_id, display_name, question_count, opinion_chunk_count
            FROM justices ORDER BY display_name
        """):
            self.justices[r["justice_id"]] = {
                "justice_id": r["justice_id"],
                "display_name": r["display_name"],
                "question_count": r["question_count"],
                "opinion_chunk_count": r["opinion_chunk_count"],
            }

        for r in conn.execute("""
            SELECT id, justice_id, question_text, context_before, context_after,
                   case_name, term, question_presented, audio_id, turn_index
            FROM questions
        """):
            row = dict(r)
            self.rows.setdefault(row["justice_id"], []).append(row)

        for r in conn.execute("""
            SELECT id, justia_opinion_id, justice_id, case_id, case_name, term,
                   opinion_type, chunk_index, text
            FROM opinion_chunks
        """):
            row = dict(r)
            self.opinion_rows.setdefault(row["justice_id"], []).append(row)

        conn.close()

        for jid, rows in self.rows.items():
            # Index over question_text + the preceding advocate context + the
            # case question presented — context carries the topical signal; the
            # justice's words carry the voice signal.
            corpus_tokens = [
                tokenize(
                    (row["question_text"] or "") + " "
                    + (row["context_before"] or "") + " "
                    + (row["question_presented"] or "")
                )
                for row in rows
            ]
            self.indexes[jid] = BM25Okapi(corpus_tokens) if corpus_tokens else None

        for jid, rows in self.opinion_rows.items():
            corpus_tokens = [tokenize(row["text"] or "") for row in rows]
            self.opinion_indexes[jid] = BM25Okapi(corpus_tokens) if corpus_tokens else None

        n_q = sum(len(v) for v in self.rows.values())
        n_o = sum(len(v) for v in self.opinion_rows.values())
        print(
            f"Loaded corpus: {n_q} questions and {n_o} opinion chunks "
            f"across {len(self.justices)} justices",
            file=sys.stderr,
        )

    def search(self, justice_id: str, query: str, top_k: int = TOP_K) -> list[dict]:
        idx = self.indexes.get(justice_id)
        if idx is None:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = idx.get_scores(q_tokens)
        rows = self.rows[justice_id]
        ranked = sorted(zip(scores, rows), key=lambda x: x[0], reverse=True)
        out = []
        for score, row in ranked[:top_k]:
            if score <= 0:
                break
            out.append({**row, "_bm25": float(score)})
        return out

    def search_opinions(self, justice_id: str, query: str, top_k: int = TOP_K_OPINIONS) -> list[dict]:
        idx = self.opinion_indexes.get(justice_id)
        if idx is None:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = idx.get_scores(q_tokens)
        rows = self.opinion_rows[justice_id]
        ranked = sorted(zip(scores, rows), key=lambda x: x[0], reverse=True)
        out = []
        for score, row in ranked[:top_k]:
            if score <= 0:
                break
            out.append({**row, "_bm25": float(score)})
        return out


SYSTEM_TEMPLATE = """You project oral-argument questions in the voice of a specific U.S. Supreme Court Justice.

You will receive a description of a real or hypothetical case plus two voice samples drawn from {justice}'s own record:

  A. {n_examples} actual questions {justice} has asked at oral argument over recent terms, with the advocate setup that preceded each one.
  B. {n_opinions} excerpts from written opinions {justice} has authored (majority, concurring, or dissenting). These reveal doctrinal commitments and prose style that the oral-argument sample under-represents — especially for justices who speak rarely at argument.

Use BOTH samples to calibrate:

  - Syntactic patterns (sentence length, embedded clauses, run-on qualifications, the "what about X — and then what about Y" pattern, etc.)
  - Rhetorical habits (Socratic questioning, slippery-slope hypotheticals, textualist parsing, originalist framing, pragmatic concern for consequences, references to record evidence vs. doctrine, etc.)
  - Diction and tics (favorite phrases, formal vs. colloquial register, addresses like "Counsel")
  - Doctrinal preoccupations evident from BOTH the questions and the opinions — what statutory canons, constitutional theories, or empirical concerns reliably surface in this justice's writing

Bridge written-opinion content into oral-argument form when you generate. A justice's dissents often telegraph the questions they'd press at argument on related issues. Do not invent biographical facts. Do not parody. The goal is plausibility — questions that would not feel out of place in a transcript.

Return strict JSON matching this shape — no prose outside the JSON, no markdown fences:

{{
  "predicted_questions": [
    {{
      "question": "The full text of the question, exactly as the justice might phrase it.",
      "rationale": "One sentence on why this is the kind of question this justice would ask in this case (doctrinal angle, voice pattern, etc.).",
      "closest_precedent_index": 0,
      "drew_from_opinion_index": null
    }},
    ...
  ],
  "voice_notes": "2-3 sentences naming the specific stylistic and doctrinal patterns from the samples you leaned on, citing whether they came from oral argument or written opinions."
}}

`closest_precedent_index` is the 0-indexed entry in voice sample A (questions) closest in phrasing or topical posture. `drew_from_opinion_index` is the 0-indexed entry in voice sample B (opinions) you drew doctrinal substance from, or null if you didn't lean on a specific opinion. Generate exactly {n_questions} questions, ordered by likelihood of being asked."""


def build_examples_block(retrieved: list[dict]) -> str:
    lines = []
    for i, r in enumerate(retrieved):
        lines.append(f"--- Question example {i} (case: {r['case_name']}, term: {r['term']}) ---")
        if r.get("question_presented"):
            lines.append(f"Case question presented: {r['question_presented'][:400]}")
        if r.get("context_before"):
            lines.append(f"Advocate just before: {r['context_before']}")
        lines.append(f"JUSTICE: {r['question_text']}")
        if r.get("context_after"):
            lines.append(f"Advocate response: {r['context_after']}")
        lines.append("")
    return "\n".join(lines)


def build_opinion_block(retrieved: list[dict]) -> str:
    if not retrieved:
        return "(No written-opinion excerpts available in the corpus for this justice yet.)"
    lines = []
    for i, r in enumerate(retrieved):
        otype = (r.get("opinion_type") or "opinion").upper()
        lines.append(f"--- Opinion excerpt {i} (case: {r['case_name']}, term: {r['term']}, type: {otype}) ---")
        # Cap each excerpt to keep token usage predictable.
        text = (r.get("text") or "").strip()
        if len(text) > 1400:
            text = text[:1400].rsplit(" ", 1)[0] + " ..."
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def predict(client: anthropic.Anthropic, corpus: Corpus, justice_id: str, case_description: str, num_questions: int = 5) -> dict:
    if justice_id not in corpus.justices:
        raise ValueError(f"unknown justice: {justice_id}")
    justice_name = corpus.justices[justice_id]["display_name"]
    retrieved = corpus.search(justice_id, case_description, top_k=TOP_K)
    retrieved_opinions = corpus.search_opinions(justice_id, case_description, top_k=TOP_K_OPINIONS)

    if not retrieved and not retrieved_opinions:
        return {
            "justice_id": justice_id,
            "justice_name": justice_name,
            "predicted_questions": [],
            "voice_notes": "No retrievable past questions or written opinions for this justice match the input case. Ingest more terms via fetch_transcripts.py / fetch_opinions.py.",
            "retrieved_examples": [],
            "retrieved_opinions": [],
        }

    system_prompt = SYSTEM_TEMPLATE.format(
        justice=justice_name,
        n_examples=len(retrieved),
        n_opinions=len(retrieved_opinions),
        n_questions=num_questions,
    )

    user_content = (
        f"CASE DESCRIPTION:\n{case_description.strip()}\n\n"
        f"=== VOICE SAMPLE A — ORAL ARGUMENT QUESTIONS BY {justice_name.upper()} ===\n\n"
        f"{build_examples_block(retrieved) if retrieved else '(No matching oral-argument questions retrieved.)'}\n\n"
        f"=== VOICE SAMPLE B — WRITTEN OPINION EXCERPTS BY {justice_name.upper()} ===\n\n"
        f"{build_opinion_block(retrieved_opinions)}\n\n"
        f"Generate {num_questions} predicted questions now, drawing on both samples as appropriate."
    )

    # No thinking / no effort: Haiku doesn't support them, and for stylistic
    # mimicry from examples there's no need for extended reasoning. If you
    # switch to Opus or Sonnet, you can add thinking={"type": "adaptive"} here.
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = {"predicted_questions": [], "voice_notes": "Model returned non-JSON output.", "raw": text}

    # Attach the retrieved examples so the UI can show grounding.
    parsed["justice_id"] = justice_id
    parsed["justice_name"] = justice_name
    parsed["retrieved_examples"] = [
        {
            "index": i,
            "question": r["question_text"],
            "context_before": r["context_before"],
            "context_after": r["context_after"],
            "case_name": r["case_name"],
            "term": r["term"],
            "score": r["_bm25"],
        }
        for i, r in enumerate(retrieved)
    ]
    parsed["retrieved_opinions"] = [
        {
            "index": i,
            "case_name": r["case_name"],
            "term": r["term"],
            "opinion_type": r["opinion_type"],
            "text": r["text"],
            "score": r["_bm25"],
        }
        for i, r in enumerate(retrieved_opinions)
    ]
    parsed["usage"] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return parsed


def make_app(corpus: Corpus, client: anthropic.Anthropic) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def root():
        if INDEX_HTML.exists():
            return send_file(INDEX_HTML)
        return "<h1>scotus-predictor</h1><p>index.html missing</p>", 200

    @app.get("/api/justices")
    def justices():
        return jsonify({"justices": list(corpus.justices.values())})

    @app.get("/api/sample/<justice_id>")
    def sample(justice_id: str):
        rows = corpus.rows.get(justice_id, [])
        import random
        sample_rows = random.sample(rows, min(5, len(rows))) if rows else []
        return jsonify({
            "justice_id": justice_id,
            "samples": [
                {
                    "question": r["question_text"],
                    "case_name": r["case_name"],
                    "term": r["term"],
                    "context_before": r["context_before"],
                }
                for r in sample_rows
            ],
        })

    @app.post("/api/predict")
    def predict_endpoint():
        body = request.get_json(force=True) or {}
        justice_id = body.get("justice_id")
        case_description = (body.get("case_description") or "").strip()
        num_questions = int(body.get("num_questions") or 5)
        if not justice_id or not case_description:
            return jsonify({"error": "justice_id and case_description are required"}), 400
        try:
            result = predict(client, corpus, justice_id, case_description, num_questions=num_questions)
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except anthropic.APIError as e:
            return jsonify({"error": f"Claude API error: {e}"}), 502

    return app


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY not set; /api/predict will fail.", file=sys.stderr)
    corpus = Corpus(DB_PATH)
    client = anthropic.Anthropic()
    app = make_app(corpus, client)
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
