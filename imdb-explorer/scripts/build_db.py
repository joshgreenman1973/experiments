#!/usr/bin/env python3
"""Build data/imdb.duckdb from the raw IMDb .tsv.gz dumps.

Reads straight out of the gzipped files -- no need to expand ~9 GB of TSV to
disk. Keeps only the columns the app actually queries.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "imdb.duckdb"

# Only these title types survive the import. Shorts, episodes, video games and
# the rest add ~7M rows that the app never looks at.
KEEP_TYPES = ("movie", "tvSeries", "tvMiniSeries", "tvMovie")

# IMDb uses a literal backslash-N for nulls and no quoting at all.
READ = "read_csv('{path}', delim='\\t', header=true, quote='', nullstr='\\N', {cols})"


def rd(name: str, cols: str) -> str:
    path = RAW / f"{name}.tsv.gz"
    if not path.exists():
        sys.exit(f"FATAL: {path} is missing. Run scripts/fetch_imdb.sh first.")
    if path.stat().st_size < 1_000_000:
        sys.exit(f"FATAL: {path} is only {path.stat().st_size} bytes -- refusing to build.")
    return READ.format(path=path, cols=cols)


def step(con: duckdb.DuckDBPyConnection, label: str, sql: str, table: str) -> None:
    t0 = time.time()
    print(f"==> {label}", flush=True)
    con.execute(sql)
    n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    if n == 0:
        sys.exit(f"FATAL: {table} came out empty. Refusing to ship a hollow database.")
    print(f"    {n:,} rows in {time.time() - t0:.1f}s", flush=True)


def main() -> None:
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute("PRAGMA memory_limit='4GB'")

    step(con, "basics (titles)", f"""
        CREATE TABLE basics AS
        SELECT tconst, titleType, primaryTitle, startYear, genres
        FROM {rd('title.basics',
                 "columns={'tconst':'VARCHAR','titleType':'VARCHAR',"
                 "'primaryTitle':'VARCHAR','originalTitle':'VARCHAR',"
                 "'isAdult':'VARCHAR','startYear':'INTEGER','endYear':'VARCHAR',"
                 "'runtimeMinutes':'VARCHAR','genres':'VARCHAR'}")}
        WHERE titleType IN {KEEP_TYPES}
    """, "basics")

    step(con, "names (people)", f"""
        CREATE TABLE names AS
        SELECT nconst, primaryName, birthYear, deathYear, primaryProfession
        FROM {rd('name.basics',
                 "columns={'nconst':'VARCHAR','primaryName':'VARCHAR',"
                 "'birthYear':'INTEGER','deathYear':'INTEGER',"
                 "'primaryProfession':'VARCHAR','knownForTitles':'VARCHAR'}")}
    """, "names")

    step(con, "ratings", f"""
        CREATE TABLE ratings AS
        SELECT tconst, averageRating, numVotes
        FROM {rd('title.ratings',
                 "columns={'tconst':'VARCHAR','averageRating':'DOUBLE',"
                 "'numVotes':'BIGINT'}")}
    """, "ratings")

    # principals is the big one (~90M rows). Restrict it to titles we kept.
    step(con, "principals (cast + crew)", f"""
        CREATE TABLE principals AS
        SELECT p.tconst, p.ordering, p.nconst, p.category
        FROM {rd('title.principals',
                 "columns={'tconst':'VARCHAR','ordering':'INTEGER',"
                 "'nconst':'VARCHAR','category':'VARCHAR','job':'VARCHAR',"
                 "'characters':'VARCHAR'}")} p
        SEMI JOIN basics b ON b.tconst = p.tconst
    """, "principals")

    print("==> indexes", flush=True)
    for sql in (
        "CREATE INDEX idx_principals_nconst ON principals(nconst)",
        "CREATE INDEX idx_principals_tconst ON principals(tconst)",
        "CREATE INDEX idx_names_nconst ON names(nconst)",
        "CREATE INDEX idx_names_lower ON names(lower(primaryName))",
        "CREATE INDEX idx_basics_tconst ON basics(tconst)",
        "CREATE INDEX idx_ratings_tconst ON ratings(tconst)",
    ):
        con.execute(sql)

    con.close()
    print(f"\nBuilt {DB} ({DB.stat().st_size / 1e9:.1f} GB)")


if __name__ == "__main__":
    main()
