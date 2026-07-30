# IMDb Explorer

A local tool for digging through the full IMDb dataset — who works with whom,
who has worked with everyone, and who is related to whom. Runs entirely on this
machine against a DuckDB copy of IMDb's bulk files. Nothing is published.

    ./run.sh          # → http://127.0.0.1:8000

## Three views

**Collaborators** — pick a person, get everyone who recurs in their filmography.
Amber spokes run to the centre; green lines join the collaborators to *each
other*, and hovering anyone isolates their web. Click a node for the full list
of shared titles, double-click to re-centre there.

Six ways to read the same data, in the Layout switcher:

| | |
| --- | --- |
| **Orbit** | Four concentric tiers, each a "worked together this often" band, members spread evenly around. The inner ring is the inner circle. |
| **Spiral** | Continuous radius ordered by count, so the filmography unwinds from closest to most incidental. |
| **Force** | Physics layout; clusters find themselves. |
| **Chord** | Everyone on one rim, arcs bowed through the middle. The connections *are* the picture. |
| **Matrix** | The peer mesh as a grid — every collaborator against every other, exact numbers instead of a hairball. |
| **Years** | Every collaboration on a shared time axis, one lane per person, one mark per title. Shows the *shape* of a relationship: a career-long marriage versus three films in one burst. |

In the ring layouts, distance and node area both encode joint titles (area is
proportional, so twice the films draws twice the ink), as does spoke weight.

Peer counts are computed **within the centre's filmography** — how many of
*this person's* titles any two collaborators both worked on. Two people may have
a far longer history elsewhere; that is a different and much more expensive
question.

**Worked together** — pick two or more people and get every title in which all
of them appear among the principals, with each person's role on each title.

**Family** — kinship, which IMDb's bulk files do not contain at all. Sourced
from Wikidata and joined back on IMDb person IDs, then annotated with the films
each pair actually appeared in together.

## Provenance and confidence

| Layer | Source | Confidence |
| --- | --- | --- |
| Titles, people, credits, ratings | [IMDb non-commercial datasets](https://developer.imdb.com/non-commercial-datasets/), refreshed daily by IMDb | High for credited principals; see caveats |
| Family relationships | [Wikidata](https://query.wikidata.org) properties P22 (father), P25 (mother), P40 (child), P26 (spouse), P3373 (sibling) | Partial — see below |

Family coverage has two separate limits, and both matter. Wikidata's own
coverage of film families is uneven and skews toward famous names. On top of
that, the fetcher only asks about the **60,000 most-voted people** in the local
database, because Wikidata's public endpoint cannot be queried in bulk (it caps
every query at 60 seconds and truncates the response mid-row). So an absent
relative means "not in the seeded slice, or not in Wikidata" — never "no such
relative." Widen the slice with `--top`.

### What the numbers do and don't mean

- **`principals` is not a full cast list.** IMDb's bulk export caps each title
  at roughly its ten top-billed people plus a handful of key crew. Two people
  can have worked on the same film and not appear as collaborators here.
- **Only four title types count**: `movie`, `tvSeries`, `tvMiniSeries`,
  `tvMovie`. Shorts, individual episodes, video and video games are dropped at
  import. A director and an actor who only share TV episodes will show nothing.
- **A TV series counts once**, not once per episode, so a decade on the same
  show weighs the same as a single film.
- **Actors are cut off at 10th billing** (`ordering <= 10`); the six creative
  crew categories — director, writer, producer, composer, cinematographer,
  editor — are kept at any billing position, since crew are listed last.
- **Average rating on an edge is vote-weighted** across the shared titles, so a
  blockbuster outweighs an obscurity. Titles with no votes are excluded from the
  average but still count toward the shared total.
- **`shared` on the center node** is that person's total qualifying titles, not
  a count of collaborations.
- **Family co-appearance uses `ordering <= 15`** on both sides, a looser cut
  than the collaborator graph.

## Rebuilding from scratch

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./scripts/fetch_imdb.sh                        # ~1.3 GB of .tsv.gz
./.venv/bin/python scripts/build_db.py         # → data/imdb.duckdb
./.venv/bin/python scripts/fetch_wikidata_family.py   # → data/family.csv (optional)
```

`build_db.py` reads straight out of the gzipped files, keeps only the columns
the app queries, and restricts `principals` to titles that survived the type
filter. Every step asserts a non-zero row count and exits loudly rather than
leaving a hollow database behind.

The family fetcher is optional: without `data/family.csv` (or
`data/family.parquet`) the Family tab says so instead of failing.

IMDb refreshes its dumps daily. Re-run `fetch_imdb.sh` and `build_db.py` to
update; nothing is incremental.

## Layout

```
app/main.py        FastAPI routes
app/queries.py     every SQL query in the project
app/templates/     the single-page front end
scripts/           fetch + build
data/              raw dumps, imdb.duckdb, family.csv   (all gitignored)
```

## Why this isn't in git

The built database plus raw dumps run to several gigabytes, so `data/` and
`.venv/` are ignored and the project is listed in the gallery as a local-only
entry. The code here is enough to rebuild everything.

## History

The original was lost when the folder was deleted between 20 May and 22 June
2026. `app/main.py` and `app/queries.py` were reconstructed from the CPython
3.9 bytecode that survived in `~/Library/Caches/com.apple.python/` — routes,
logic and SQL are the originals, verbatim. The front end and the two scripts had
no cached bytecode and were rewritten from the API contract the recovered code
implies; the visual design is new and is not a reconstruction of anything.

### Deliberate departures from the recovered code

Three changes were made on top of the verbatim recovery. Each fixed something
that was wrong, not merely different.

1. **Search matched a prefix of the whole name**, so "scorsese" returned people
   literally surnamed Scorsese and never Martin Scorsese. It now also matches on
   a word boundary and ranks by how much a person is voted on.
2. **`shared` counted credit rows, not titles.** `principals` holds one row per
   credit, so somebody who directed, wrote and edited the same film counted
   three times — Joel Coen showed 41 shared "titles" with Roger Deakins instead
   of 14, and that film's rating was weighted three times over in the edge
   average. Credits are now folded to one row per title with the roles merged.
3. **The family co-appearance query had the same duplication**; it now uses
   `SELECT DISTINCT`.
