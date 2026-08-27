from collections import defaultdict

from financial_advisor.services.neo4j_service import neo4j_service


def _drop_near_duplicates(chunks: list[dict], similar_pairs: list[tuple[str, str]]) -> list[dict]:
    """Greedy scan in input order: drop a chunk once it's paired with an already-kept one.
    Input order is assumed to be relevance order (highest-score/first-retrieved first), so
    keeping the earlier-seen chunk of a duplicate pair keeps the more relevant copy."""
    similar_to: dict[str, set[str]] = defaultdict(set)
    for a, b in similar_pairs:
        similar_to[a].add(b)
        similar_to[b].add(a)

    kept: list[dict] = []
    kept_ids: set[str] = set()
    for chunk in chunks:
        if similar_to[chunk["id"]] & kept_ids:
            continue
        kept.append(chunk)
        kept_ids.add(chunk["id"])
    return kept


def deduplicate_by_similarity(chunks: list[dict], threshold: float = 0.92) -> list[dict]:
    """Drop chunks that are near-duplicates of an already-kept, higher-ranked chunk, using
    precomputed SIMILAR_TO edges (similarity/linker.py) — a cheap graph lookup among just the
    chunks in hand, instead of recomputing pairwise similarity at retrieval time.

    `threshold` can only be as tight as (>=) whatever `link_similar_chunks` was last run with —
    pairs below that write-time threshold were never stored, so a looser value here finds
    nothing new. Chunks with no SIMILAR_TO edge at all (not yet linked, or genuinely distinct)
    are always kept — this only ever removes redundancy the graph already knows about, never
    invents any.
    """
    if len(chunks) <= 1:
        return chunks

    ids = [c["id"] for c in chunks]
    rows = neo4j_service.run_query(
        """
        MATCH (a:Chunk)-[r:SIMILAR_TO]-(b:Chunk)
        WHERE a.id IN $ids AND b.id IN $ids AND r.score >= $threshold
        RETURN a.id AS a, b.id AS b
        """,
        {"ids": ids, "threshold": threshold},
    )
    pairs = [(row["a"], row["b"]) for row in rows]
    return _drop_near_duplicates(chunks, pairs)
