from financial_advisor.extraction.validators import EntityType, RelationshipType

ENTITY_TYPES = ", ".join(t.value for t in EntityType)
RELATIONSHIP_TYPES = ", ".join(t.value for t in RelationshipType)

# Scope/role preamble shared by the entity and reflection prompts — keeps both calls anchored to
# the same closed type vocabulary instead of letting the model improvise labels per call.
EXTRACTION_SCOPE = f"""\
You are a financial analyst extracting structured knowledge from a company's SEC 10-K filing. \
Extract only entities of these types: {ENTITY_TYPES}. Use the exact type names given. Do not \
invent other types. Extract only entities explicitly named in the text — do not infer entities \
that are merely implied. Use each entity's name exactly as it appears in the text.
"""

ENTITY_SYSTEM_PROMPT = EXTRACTION_SCOPE

REFLECTION_SYSTEM_PROMPT = f"""\
{EXTRACTION_SCOPE}
You will be shown the source text and a first-pass list of entities already extracted from it. \
Check the text again for any entity of the allowed types that the first pass missed. Only return \
entities that are NOT already in the first-pass list — do not repeat ones already found.
"""

RELATIONSHIP_SYSTEM_PROMPT = f"""\
You are a financial analyst extracting relationships between entities already identified in a \
company's SEC 10-K filing. Extract only relationships of these types: {RELATIONSHIP_TYPES}. Use \
the exact type names given. The source and target of every relationship MUST be one of the \
entity names given to you — never introduce an entity that isn't in that list. Only extract a \
relationship if the text explicitly states it; do not infer one from proximity alone. Include the \
verbatim sentence or phrase that supports each relationship as evidence.
"""


def build_entity_prompt(chunk_text: str) -> str:
    return f"Text:\n{chunk_text}"


def build_reflection_prompt(chunk_text: str, first_pass_entities: list[str]) -> str:
    found = "\n".join(f"  - {name}" for name in first_pass_entities) or "  (none)"
    return f"""\
Text:
{chunk_text}

Entities already found:
{found}
"""


def build_relationship_prompt(chunk_text: str, entity_names: list[str]) -> str:
    names = "\n".join(f"  - {name}" for name in entity_names)
    return f"""\
Text:
{chunk_text}

Known entities (relationships may only use these as source/target):
{names}
"""
