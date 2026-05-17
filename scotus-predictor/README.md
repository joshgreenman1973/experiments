# SCOTUS Question Predictor

For any of the nine current Supreme Court justices, generate plausible oral-argument questions on a real or hypothetical case — grounded in the justice's actual past questions, phrased in their voice.

How it works:

1. **Ingest** —
   - `fetch_transcripts.py` pulls SCOTUS oral-argument transcripts from the free [Oyez API](https://api.oyez.org).
   - `fetch_opinions.py` walks the cached Oyez case files, finds entries that Oyez attributes to a current justice (`written_opinion[*].judge_last_name`), and pulls the opinion text from Justia.
   - Both are idempotent disk caches under `data/`.
2. **Corpus** — `build_corpus.py` walks the cached files and writes a SQLite database with two parallel indexes per justice:
   - `questions` — every oral-argument turn the justice took, with surrounding advocate context.
   - `opinion_chunks` — written opinions (majority, concurring, dissenting) split into ~220-word paragraphs, capped at 8 chunks per opinion so a 60-page dissent doesn't dominate.
3. **Retrieve** — at query time, `server.py` runs **BM25** over *both* indexes for the chosen justice: top 20 question matches and top 5 opinion-chunk matches. No embeddings, no vector DB — laptop-runnable.
4. **Generate** — Claude gets the case description plus both voice samples — the oral-argument questions for syntactic patterns and the written-opinion excerpts for doctrinal commitments — and returns predicted questions in JSON, with citations back to the specific question and opinion it leaned on.

Why opinions matter: justices who speak rarely at oral argument (Thomas especially) still write prolifically. With opinion intelligence, Thomas's voice corpus goes from a handful of questions to hundreds of paragraphs of doctrinal writing, and the predicted questions become meaningful instead of being limited to what little he says aloud.

## Cost

- **Oyez ingestion**: free (public API, no key).
- **Retrieval**: free (BM25, local).
- **Generation**: defaults to `claude-haiku-4-5` (~$1 in / $5 out per 1M tokens). A typical prediction is ~5-7K input tokens (system prompt + 20 questions + 5 opinion excerpts) + ~600 output tokens = **well under one cent per query**.
- Switch the model with `CLAUDE_MODEL=claude-sonnet-4-6` (~3× cost) or `claude-opus-4-7` (~25× cost) for higher fidelity.

## Setup

```bash
pip install flask anthropic requests rank_bm25
```

## Build the corpus (one time)

```bash
# 1. Oral-argument transcripts (Oyez — fast, ~3-5 min per term).
python fetch_transcripts.py --start 2005 --end 2024
#    Single term: --term 2023.  Cap per term for testing: --max-cases 10.

# 2. Written opinions (Justia — slower, ~5-10 min per term, 1 req/sec).
python fetch_opinions.py --start 2005 --end 2024
#    Same flags as fetch_transcripts.

# 3. Build the SQLite db from everything cached so far.
python build_corpus.py
```

All three are idempotent. `fetch_transcripts.py` and `fetch_opinions.py` only download what's missing, so you can re-run after each batch. `build_corpus.py` rebuilds the SQLite from whatever's on disk; re-run it whenever new data lands.

For a fast bootstrap covering all 9 current justices, use `--start 2022 --end 2024` on both fetchers (~30 min total).

## Run the app

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python server.py
# open http://localhost:5050
```

Pick a justice, paste a case description (real or hypothetical), get predicted questions plus links back to the closest real precedent question from that justice.

## Files

- `fetch_transcripts.py` — Oyez crawler. Idempotent disk cache.
- `fetch_opinions.py` — Justia crawler for written opinions of current justices, driven by Oyez's `written_opinion` attribution.
- `build_corpus.py` — flattens cached JSON into `corpus.db` (questions + opinion chunks).
- `server.py` — Flask app: dual-index BM25 retrieval + Claude API.
- `index.html` — UI.
- `data/cases/{term}/{docket}.json` — cached case detail.
- `data/transcripts/{audio_id}.json` — cached transcripts.
- `data/opinions/{justia_opinion_id}.json` — cached opinion text.
- `corpus.db` — SQLite indexes.

## Caveats

- Coverage depends on Oyez and Justia. Transcripts are sometimes missing for older argument sessions; some opinion pages don't include the body text and are silently skipped.
- The "in their own words" claim is a stylistic approximation, not a prediction of the actual content of any future case. The model can produce a plausible-sounding question that the justice would never actually ask. Treat as a Socratic prompt, not an oracle.
- We index questions by **turn**, not by individual sentence. A single turn often contains multiple questions; we keep them together to preserve the rhetorical flow.
- Opinion ingestion currently follows Oyez's `written_opinion[].judge_last_name` attribution. Cases where Oyez doesn't credit the author (some majority opinions list `judge_full_name: null`) are skipped, even when the author is identifiable from the decision metadata. Wiring up that fallback via `decisions[0].majority_author` is a small extension to `fetch_opinions.py`.
- Be polite to Justia. The fetcher sleeps 1 second between requests; don't lower that without good reason.
