"""DuckDB query helpers."""
from __future__ import annotations
from pathlib import Path
import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "imdb.duckdb"
FAMILY_PARQUET = Path(__file__).resolve().parent.parent / "data" / "family.parquet"
FAMILY_CSV = Path(__file__).resolve().parent.parent / "data" / "family.csv"

_con = None


def conn() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        _con = duckdb.connect(str(DB), read_only=True)
    return _con


def search_names(q: str, limit: int = 10) -> list[dict]:
    if not q.strip():
        return []
    # The original matched on a prefix of the whole name, so a surname alone
    # ("scorsese") missed everyone whose first name came first. Surname matching
    # is the third branch; ranking still puts an exact hit above a prefix hit
    # above everything else, then orders by how much the person is voted on.
    rows = conn().execute(
        """
        SELECT n.nconst, n.primaryName, n.birthYear, n.deathYear, n.primaryProfession,
               COALESCE(SUM(r.numVotes), 0) AS total_votes
        FROM names n
        LEFT JOIN principals p ON p.nconst = n.nconst
        LEFT JOIN ratings r    ON r.tconst = p.tconst
        WHERE lower(n.primaryName) LIKE ?
           OR lower(n.primaryName) = ?
           OR lower(n.primaryName) LIKE ?
        GROUP BY n.nconst, n.primaryName, n.birthYear, n.deathYear, n.primaryProfession
        ORDER BY total_votes DESC,
                 (lower(n.primaryName) = ?) DESC,
                 (lower(n.primaryName) LIKE ?) DESC
        LIMIT ?
        """,
        [f"{q.lower()}%", q.lower(), f"% {q.lower()}%",
         q.lower(), f"{q.lower()}%", limit],
    ).fetchall()
    return [
        dict(nconst=r[0], name=r[1], birthYear=r[2], deathYear=r[3],
             profession=r[4], votes=int(r[5]))
        for r in rows
    ]


def get_name(nconst: str) -> dict | None:
    r = conn().execute(
        "SELECT nconst, primaryName, birthYear, deathYear, primaryProfession FROM names WHERE nconst = ?",
        [nconst],
    ).fetchone()
    if not r:
        return None
    return dict(nconst=r[0], name=r[1], birthYear=r[2], deathYear=r[3], profession=r[4])


# Only these title types count as "work together" -- shorts, episodes and video
# games would swamp the graph.
KEEP_TYPES = ("movie", "tvSeries", "tvMiniSeries", "tvMovie")

# Below-the-line crew are only in `principals` for a handful of roles, so keep
# them regardless of billing order; actors get cut off at 10th billing.
CREATIVE_CATEGORIES = ("director", "writer", "producer", "composer",
                       "cinematographer", "editor")


def collaborators(nconst: str, min_shared: int = 2, max_nodes: int = 50) -> dict:
    """Return graph data for a person's recurring collaborators."""
    c = conn()

    titles = [r[0] for r in c.execute(
        f"""
        SELECT DISTINCT p.tconst
        FROM principals p
        JOIN basics b ON b.tconst = p.tconst
        WHERE p.nconst = ?
          AND b.titleType IN {KEEP_TYPES}
        """,
        [nconst],
    ).fetchall()]

    if not titles:
        return dict(center=nconst, nodes=[], edges=[], titles=0)

    placeholders = ",".join(["?"] * len(titles))
    creative_ph = ",".join(["?"] * len(CREATIVE_CATEGORIES))

    rows = c.execute(
        f"""
        SELECT p.nconst, p.tconst, p.category, b.primaryTitle, b.startYear,
               COALESCE(r.averageRating, 0.0) AS rating, COALESCE(r.numVotes, 0) AS votes
        FROM principals p
        JOIN basics b ON b.tconst = p.tconst
        LEFT JOIN ratings r ON r.tconst = p.tconst
        WHERE p.tconst IN ({placeholders})
          AND p.nconst != ?
          AND (p.ordering <= 10 OR p.category IN ({creative_ph}))
        """,
        [*titles, nconst, *CREATIVE_CATEGORIES],
    ).fetchall()

    # `principals` carries one row per credit, so somebody who directed, wrote
    # and edited the same film appears three times. The original counted those
    # rows, which inflated `shared` and triple-weighted the rating average.
    # Fold them down to one entry per title, collecting the roles.
    agg = {}
    for collab_nconst, tconst, category, title, year, rating, votes in rows:
        a = agg.setdefault(collab_nconst, dict(
            nconst=collab_nconst, shared=0, weighted_rating_sum=0.0,
            weight_sum=0.0, categories=set(), titles=[], by_title={}))

        a["categories"].add(category)
        seen = a["by_title"].get(tconst)
        if seen is None:
            seen = dict(tconst=tconst, title=title, year=year,
                        rating=rating, votes=int(votes), roles=set())
            a["by_title"][tconst] = seen
            a["titles"].append(seen)
            a["shared"] += 1
            if votes and rating:
                a["weighted_rating_sum"] += rating * votes
                a["weight_sum"] += votes
        seen["roles"].add(category)

    for a in agg.values():
        del a["by_title"]
        for t in a["titles"]:
            t["category"] = ", ".join(sorted(t.pop("roles")))

    keep = [a for a in agg.values() if a["shared"] >= min_shared]
    keep.sort(key=lambda a: a["shared"], reverse=True)
    keep = keep[:max_nodes]

    if keep:
        ncs = [a["nconst"] for a in keep]
        ph = ",".join(["?"] * len(ncs))
        name_map = {r[0]: r[1] for r in c.execute(
            f"SELECT nconst, primaryName FROM names WHERE nconst IN ({ph})",
            ncs,
        ).fetchall()}
    else:
        name_map = {}

    center = get_name(nconst) or dict(nconst=nconst, name=nconst)
    nodes = [dict(id=nconst, label=center["name"], shared=len(titles), center=True)]
    edges = []
    for a in keep:
        avg_r = a["weighted_rating_sum"] / a["weight_sum"] if a["weight_sum"] else None
        nodes.append(dict(
            id=a["nconst"],
            label=name_map.get(a["nconst"], a["nconst"]),
            shared=a["shared"],
            categories=sorted(a["categories"]),
            avg_rating=avg_r,
        ))
        a["titles"].sort(key=lambda t: t["year"] or 0)
        edges.append(dict(
            source=nconst, target=a["nconst"],
            shared=a["shared"], avg_rating=avg_r,
            titles=a["titles"][:30],
        ))

    # Links between the collaborators themselves, not just back to the hub.
    # Counted within the centre's filmography: how many of *these* titles any
    # two of them both worked on. Two people may well have a longer history
    # elsewhere -- that is a different question, and a much more expensive one.
    per_title = {}
    for a in keep:
        for t in a["titles"]:
            per_title.setdefault(t["tconst"], []).append(a["nconst"])

    peer_counts = {}
    for members in per_title.values():
        members.sort()
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                key = (members[i], members[j])
                peer_counts[key] = peer_counts.get(key, 0) + 1

    peers = [dict(source=s, target=t, shared=c)
             for (s, t), c in peer_counts.items() if c >= min_shared]
    peers.sort(key=lambda p: -p["shared"])

    return dict(center=nconst, center_name=center["name"], nodes=nodes,
                edges=edges, peers=peers[:600], titles=len(titles))


def coappearances(nconsts: list[str]) -> dict:
    """Films where every nconst appears in the principals list."""
    nconsts = [n for n in nconsts if n]
    if len(nconsts) < 2:
        return dict(people=[], titles=[])
    c = conn()
    name_map = {r[0]: r[1] for r in c.execute(
        f"SELECT nconst, primaryName FROM names WHERE nconst IN ({','.join(['?'] * len(nconsts))})",
        nconsts,
    ).fetchall()}

    people = [dict(nconst=n, name=name_map.get(n, n)) for n in nconsts]

    sub_queries = [
        "SELECT DISTINCT tconst FROM principals WHERE nconst = ?"
        for _ in nconsts
    ]

    intersect_sql = " INTERSECT ".join(sub_queries)
    rows = c.execute(
        f"""
        WITH shared AS ({intersect_sql})
        SELECT b.tconst, b.primaryTitle, b.titleType, b.startYear, b.genres,
               COALESCE(r.averageRating, 0.0) AS rating, COALESCE(r.numVotes, 0) AS votes
        FROM shared s
        JOIN basics b ON b.tconst = s.tconst
        LEFT JOIN ratings r ON r.tconst = b.tconst
        WHERE b.titleType IN {KEEP_TYPES}
        ORDER BY votes DESC, b.startYear
        """,
        nconsts,
    ).fetchall()

    if not rows:
        return dict(people=people, titles=[])

    tconsts = [r[0] for r in rows]
    role_rows = c.execute(
        f"""
        SELECT tconst, nconst, category
        FROM principals
        WHERE tconst IN ({','.join(['?'] * len(tconsts))})
          AND nconst IN ({','.join(['?'] * len(nconsts))})
        """,
        [*tconsts, *nconsts],
    ).fetchall()

    roles = {}
    for t, n, cat in role_rows:
        roles.setdefault(t, {})[n] = cat

    titles = []
    for t, name, ttype, year, genres, rating, votes in rows:
        titles.append(dict(
            tconst=t, title=name, titleType=ttype, year=year,
            genres=(genres or "").split(","),
            rating=rating, votes=int(votes),
            roles=[dict(nconst=n, role=roles.get(t, {}).get(n)) for n in nconsts],
        ))
    return dict(people=people, titles=titles)


def _family_source() -> str | None:
    """Return a DuckDB table-expression for the family file, or None if missing/empty."""
    if FAMILY_PARQUET.exists() and FAMILY_PARQUET.stat().st_size > 0:
        return f"read_parquet('{FAMILY_PARQUET}')"
    if FAMILY_CSV.exists() and FAMILY_CSV.stat().st_size > 0:
        return (f"read_csv('{FAMILY_CSV}', columns={{'nconst_a': 'VARCHAR', "
                f"'nconst_b': 'VARCHAR', 'relation_type': 'VARCHAR'}}, "
                f"header=true, ignore_errors=true)")
    return None


def family(nconst: str) -> dict:
    """Family tree centered on a person, with co-appearance films."""
    c = conn()
    src = _family_source()
    center = get_name(nconst) or dict(nconst=nconst, name=nconst)
    if src is None:
        return dict(center=nconst, center_name=center["name"], members=[],
                    error="Family data not yet fetched. Run scripts/fetch_wikidata_family.py.")
    rels = c.execute(
        f"""
        SELECT nconst_b, relation_type FROM {src} WHERE nconst_a = ?
        UNION
        SELECT nconst_a, relation_type FROM {src} WHERE nconst_b = ?
        """,
        [nconst, nconst],
    ).fetchall()

    seen = {}
    for other, rel in rels:
        seen.setdefault(other, set()).add(rel)
    if not seen:
        return dict(center=nconst, center_name=center["name"], members=[])

    others = list(seen.keys())
    ph = ",".join(["?"] * len(others))
    name_map = {r[0]: r[1] for r in c.execute(
        f"SELECT nconst, primaryName FROM names WHERE nconst IN ({ph})",
        others,
    ).fetchall()}

    members = []
    for other in others:
        titles = c.execute(
            f"""
            SELECT DISTINCT b.tconst, b.primaryTitle, b.startYear,
                   COALESCE(r.averageRating, 0.0), COALESCE(r.numVotes, 0)
            FROM principals p1
            JOIN principals p2 ON p1.tconst = p2.tconst
            JOIN basics b ON b.tconst = p1.tconst
            LEFT JOIN ratings r ON r.tconst = p1.tconst
            WHERE p1.nconst = ? AND p2.nconst = ?
              AND b.titleType IN {KEEP_TYPES}
              AND p1.ordering <= 15 AND p2.ordering <= 15
            ORDER BY b.startYear
            """,
            [nconst, other],
        ).fetchall()

        members.append(dict(
            nconst=other,
            name=name_map.get(other, other),
            relations=sorted(seen[other]),
            coappearances=[
                dict(tconst=t[0], title=t[1], year=t[2], rating=t[3], votes=int(t[4]))
                for t in titles
            ],
        ))

    members.sort(key=lambda m: -len(m["coappearances"]))
    return dict(center=nconst, center_name=center["name"], members=members)
