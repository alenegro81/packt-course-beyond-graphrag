"""Module 5 — entity resolution: merge duplicate entities into EntityGroup clusters.

Per entity type (see docs/adr/0008-entity-resolution-design.md): fuzzy-narrow candidates by
name, enrich survivors with graph context, let the LLM confirm true duplicates, write one
EntityGroup + SAME_AS edges per confirmed cluster. Idempotent — safe to rerun after a new
extraction batch adds more RecognisedEntity nodes.

Chunk-similarity linking (SIMILAR_TO edges, similarity/linker.py) is not yet implemented and is
not run here.
"""

from financial_advisor.ingestion.schema import apply_similarity_schema
from financial_advisor.similarity.resolver import resolve_all_entities


def main() -> None:
    apply_similarity_schema()
    summary = resolve_all_entities()
    total = sum(summary.values())
    print(f"[run-similarity] {total} EntityGroup(s) created — {summary}")


if __name__ == "__main__":
    main()
