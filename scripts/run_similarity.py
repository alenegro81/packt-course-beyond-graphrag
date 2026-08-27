"""Module 5 — chunk-similarity linking + entity resolution.

Chunk linking (see docs/adr/0009): unscoped nearest-neighbor search over the chunk_embedding
vector index, writes SIMILAR_TO {score} edges for pairs at or above threshold — including across
documents and companies. Idempotent (MERGE) — safe to rerun after new chunks are ingested.

Entity resolution (see docs/adr/0008): per entity type, fuzzy-narrow candidates by name, enrich
survivors with graph context, let the LLM confirm true duplicates, write one EntityGroup +
SAME_AS edges per confirmed cluster. Idempotent — safe to rerun after a new extraction batch
adds more RecognisedEntity nodes.

Louvain topic clustering (similarity/clusters.py) is exploratory (ephemeral GDS projection, not
persisted) and is not run here — see the module_05 notebook for a live demonstration.
"""

from financial_advisor.ingestion.schema import apply_similarity_schema
from financial_advisor.similarity.linker import link_similar_chunks
from financial_advisor.similarity.resolver import resolve_all_entities


def main() -> None:
    apply_similarity_schema()

    n_edges = link_similar_chunks()
    print(f"[run-similarity] {n_edges} SIMILAR_TO edge(s)")

    summary = resolve_all_entities()
    total = sum(summary.values())
    print(f"[run-similarity] {total} EntityGroup(s) created — {summary}")


if __name__ == "__main__":
    main()
