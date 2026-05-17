# SCOTUS Question Predictor

For any of the nine current Supreme Court justices, generate plausible oral-argument questions on a real or hypothetical case — grounded in the justice's actual past questions, phrased in their voice.

How it works:

1. **Ingest** — `fetch_transcripts.py` pulls SCOTUS oral-argument transcripts from the free [Oyez API](https://api.oyez.org) and caches them as JSON files on disk. Re-runnable; only fetches what's missing.
2. **Corpus** — `build_corpus.py` walks the cached transcripts, attributes each turn to a justice via Oyez's stable `identifier` field, and writes a SQLite database with the question text plus the advocate context before and after.
3. **Retrieve** — at query time, `server.py` runs **BM25** over the chosen justice's questions to find the 20 most topically similar real questions. No embeddings, no vector DB — keeps the system free and laptop-runnable.
4. **Generate** — Claude is given the case description + those 20 real questions as voice samples, and returns predicted questions in JSON.

The interesting part is step 3 → 4: the model isn't inventing a voice from scratch, it's mimicking the justice's actual phrasing patterns and doctrinal preoccupations from real examples retrieved on every query.

## Cost

- **Oyez ingestion**: free (public API, no key).
- **Retrieval**: free (BM25, local).
- **Generation**: defaults to `claude-haiku-4-5` (~$1 in / $5 out per 1M tokens). A typical prediction is ~5K input tokens + ~600 output tokens = **well under one cent per query**.
- Switch the model with `CLAUDE_MODEL=claude-sonnet-4-6` (~3× cost) or `claude-opus-4-7` (~25× cost) for higher fidelity.

## Setup

```bash
pip install flask anthropic requests rank_bm25
```

## Build the corpus (one time)

```bash
# Fetch every term that covers the current bench (Roberts joined Sept 2005).
python fetch_transcripts.py --start 2005 --end 2024
# A single term: --term 2023
# Cap per term for testing: --term 2023 --max-cases 10

# Build the SQLite db from cached transcripts.
python build_corpus.py
```

Re-running `fetch_transcripts.py` only downloads what's missing. Re-running `build_corpus.py` rebuilds the SQLite from whatever's on disk.

## Run the app

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python server.py
# open http://localhost:5050
```

Pick a justice, paste a case description (real or hypothetical), get predicted questions plus links back to the closest real precedent question from that justice.

## Files

- `fetch_transcripts.py` — Oyez crawler. Idempotent disk cache under `data/`.
- `build_corpus.py` — flattens cached JSON into `corpus.db`.
- `server.py` — Flask app: BM25 retrieval + Claude API.
- `index.html` — UI.
- `data/cases/{term}/{docket}.json` — cached case detail.
- `data/transcripts/{audio_id}.json` — cached transcripts.
- `corpus.db` — SQLite question/case index.

## Caveats

- Coverage depends on Oyez. Transcripts are sometimes missing for older argument sessions.
- The "in their own words" claim is a stylistic approximation, not a prediction of the actual content of any future case. The model can produce a plausible-sounding question that the justice would never actually ask. Treat as a Socratic prompt, not an oracle.
- We index by **turn**, not by individual sentence. A single turn often contains multiple questions; we keep them together to preserve the rhetorical flow.
- Written opinions are not yet ingested — only oral-argument questions. Adding opinion text would let the model lean on doctrinal positions in addition to question style; see `extract_questions()` in `build_corpus.py` for the natural extension point.
