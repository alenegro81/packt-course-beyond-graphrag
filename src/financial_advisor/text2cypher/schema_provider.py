from financial_advisor.services.neo4j_service import neo4j_service

# Never surface raw embedding vectors to the LLM prompt — they're never useful for writing a
# Cypher query and would otherwise cost real tokens on every call.
_EXCLUDED_PROPERTIES = {"embedding"}


def _format_property(prop: str, row: dict) -> str:
    types = "|".join(row["propertyTypes"] or [])
    # `mandatory` is computed by sampling: False means at least one sampled node/relationship of
    # this label/type didn't have the property set. Surfacing that as `?` is what would have
    # caught the real bug this module's notebook walks through — Company.name is absent on the
    # two curated Company nodes, present on every Wikidata-derived stub, so an LLM shown only
    # "name: String" has no reason to suspect it's sometimes null.
    return f"{prop}: {types}" if row["mandatory"] else f"{prop}: {types}?"


def _node_properties() -> str:
    rows = neo4j_service.run_query("CALL db.schema.nodeTypeProperties()")
    by_label: dict[str, list[str]] = {}
    for row in rows:
        prop = row["propertyName"]
        if prop is None or prop in _EXCLUDED_PROPERTIES:
            continue
        for label in row["nodeLabels"]:
            by_label.setdefault(label, []).append(_format_property(prop, row))
    return "\n".join(
        f"  (:{label} {{{', '.join(props)}}})" for label, props in sorted(by_label.items())
    )


def _relationship_properties() -> dict[str, list[str]]:
    rows = neo4j_service.run_query("CALL db.schema.relTypeProperties()")
    by_type: dict[str, list[str]] = {}
    for row in rows:
        rel_type = row["relType"].strip("`:")
        by_type.setdefault(rel_type, [])
        prop = row["propertyName"]
        if prop is not None:
            by_type[rel_type].append(_format_property(prop, row))
    return by_type


def _relationship_patterns() -> str:
    rel_props = _relationship_properties()
    patterns = {
        (rel[0]["name"], rel[1], rel[2]["name"])
        for row in neo4j_service.run_query("CALL db.schema.visualization()")
        for rel in row["relationships"]
    }
    lines = []
    for start, rel_type, end in sorted(patterns):
        props = ", ".join(rel_props.get(rel_type, []))
        rel_str = f"[:{rel_type} {{{props}}}]" if props else f"[:{rel_type}]"
        lines.append(f"  (:{start})-{rel_str}->(:{end})")
    return "\n".join(lines)


def get_schema_description() -> str:
    """Return a formatted description of the current graph schema for use in prompts.

    Built from Neo4j's core `db.schema.*` procedures rather than langchain's `Neo4jGraph.schema`.
    APOC is available on this project's Neo4j instance, but `Neo4jGraph.schema` is deliberately
    not used: it produces one flat text blob with no relationship-pattern section and no
    per-property nullability signal, both of which this module relies on directly (see below).
    `db.schema.nodeTypeProperties`/`relTypeProperties`/`visualization` ship with Neo4j itself and
    need no plugin.

    A property suffixed `?` (e.g. `name: String?`) is not present on every node/relationship of
    that label/type, per `mandatory: false` from `db.schema.nodeTypeProperties`/
    `relTypeProperties` (computed by sampling) — a real signal the LLM should treat as "this can
    be null," not decoration.
    """
    return f"""\
Properties suffixed `?` are optional — not present on every node/relationship of that label/type.

Node labels and properties:
{_node_properties()}

Relationship types and properties:
{chr(10).join(f"  [:{t} {{{', '.join(p)}}}]" if p else f"  [:{t}]" for t, p in sorted(_relationship_properties().items()))}

Relationship patterns (which node types connect via which relationship):
{_relationship_patterns()}
"""
