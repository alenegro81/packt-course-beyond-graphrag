from langchain_core.documents import Document

from financial_advisor.clients import get_llm
from financial_advisor.extraction.prompts import (
    ENTITY_SYSTEM_PROMPT,
    REFLECTION_SYSTEM_PROMPT,
    build_entity_prompt,
    build_reflection_prompt,
)
from financial_advisor.extraction.validators import EntityExtractionResult, ExtractedEntity


def _apply_reflection(
    first_pass: list[ExtractedEntity], reflection: list[ExtractedEntity]
) -> list[ExtractedEntity]:
    """Apply the reflection pass's output onto the first pass. Reflection does two jobs at once
    (see extraction.prompts.REFLECTION_COREFERENCE_GUIDANCE): a reflection entity whose `string`
    matches (case-insensitively) one already in the first pass is a coreference correction —
    adopt its `resolved_string` onto the existing entity, don't add a duplicate. Anything else is
    a genuinely new entity the first pass missed, appended as-is."""
    result = list(first_pass)
    index_by_string = {e.string.lower(): i for i, e in enumerate(result)}
    for e in reflection:
        key = e.string.lower()
        if key in index_by_string:
            i = index_by_string[key]
            result[i] = result[i].model_copy(update={"resolved_string": e.resolved_string})
        else:
            result.append(e)
            index_by_string[key] = len(result) - 1
    return result


def _restrict_resolved_strings_to_settled_entities(
    entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    """Backstop, on top of the prompt constraint: `resolved_string`, when different from
    `string`, must match another entity's `string` that's actually in this settled list, of the
    SAME type — a coreference should never invent a canonical form nobody extracted, or point at
    an entity of a different kind. Despite the prompt saying exactly this, the model has been
    observed violating it (e.g. a Risk entity extracted as a whole sentence that merely mentions
    "the Company" in passing getting redirected to a Company entity's string) — the same class of
    prompt-compliance gap `_filter_valid_relationships` already guards against for relationships.
    Any violation is corrected by resetting `resolved_string` back to the entity's own literal
    `string`, never dropped — the entity itself may still be noisy in its own right (e.g. a Risk
    entity extracted as a full sentence rather than a short label), but that's a separate,
    pre-existing extraction-quality issue, not something to hide here."""
    valid_targets = {(e.type, e.string.lower()) for e in entities}
    fixed = []
    for e in entities:
        if e.resolved_string != e.string and (e.type, e.resolved_string.lower()) not in valid_targets:
            e = e.model_copy(update={"resolved_string": e.string})
        fixed.append(e)
    return fixed


def extract_entities(chunk: Document) -> EntityExtractionResult:
    """Two-pass entity extraction: a first pass against the predefined type schema, then a
    single reflection pass that shows the model its own list and asks what's missing — and,
    since it already has the settled entity list and the source text side by side, also asks it
    to resolve coreference: an entity that's really just another way of referring to a different
    entity already in the list (the common SEC-filing case: the filer defines itself early on as
    "the Company" and uses that term throughout instead of its own name). See adr/0007 and its
    amendments for why this is two passes, and why coreference resolution lives in reflection
    rather than a first-pass rule keyed to an externally-supplied filer id.
    """
    model = get_llm()

    first_pass: EntityExtractionResult = model.with_structured_output(EntityExtractionResult).invoke(
        [
            {"role": "system", "content": ENTITY_SYSTEM_PROMPT},
            {"role": "user", "content": build_entity_prompt(chunk.page_content)},
        ]
    )
    print(f"[extract-entities] pass A: {len(first_pass.entities)} entit(y/ies) found")

    reflection: EntityExtractionResult = model.with_structured_output(EntityExtractionResult).invoke(
        [
            {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_reflection_prompt(chunk.page_content, first_pass.entities),
            },
        ]
    )
    print(f"[extract-entities] reflection: {len(reflection.entities)} addition(s)/correction(s)")

    merged = _apply_reflection(first_pass.entities, reflection.entities)
    return EntityExtractionResult(entities=_restrict_resolved_strings_to_settled_entities(merged))
