"""Module 5 — create similarity links between chunks and resolve duplicate entities."""

from financial_advisor.clients import get_graph
from financial_advisor.similarity.linker import link_similar_chunks
from financial_advisor.similarity.resolver import resolve_entities


def main() -> None:
    graph = get_graph()

    print("Linking similar chunks...")
    n_links = link_similar_chunks(graph, threshold=0.92)
    print(f"Created {n_links} SIMILAR_TO edges.")

    print("Resolving duplicate entities...")
    n_merged = resolve_entities(graph)
    print(f"Merged {n_merged} duplicate nodes.")


if __name__ == "__main__":
    main()
