from langchain_core.documents import Document

from financial_advisor.clients import get_llm
from financial_advisor.extraction.prompts import (
    ENTITY_SYSTEM_PROMPT,
    REFLECTION_SYSTEM_PROMPT,
    build_entity_prompt,
    build_reflection_prompt,
)
from financial_advisor.extraction.validators import EntityExtractionResult, ExtractedEntity


def _merge_reflection_additions(
    first_pass: list[ExtractedEntity], reflection: list[ExtractedEntity]
) -> list[ExtractedEntity]:
    """Keep reflection-pass entities not already present (case-insensitive) in the first pass."""
    seen = {e.string.lower() for e in first_pass}
    return first_pass + [e for e in reflection if e.string.lower() not in seen]


def extract_entities(chunk: Document) -> EntityExtractionResult:
    """Two-pass entity extraction: a first pass against the predefined type schema, then a
    single reflection pass that shows the model its own list and asks what's missing.
    See adr/0007 for why this is two passes and not one."""
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
                "content": build_reflection_prompt(
                    chunk.page_content, [e.string for e in first_pass.entities]
                ),
            },
        ]
    )
    print(f"[extract-entities] reflection: {len(reflection.entities)} additional entit(y/ies) found")

    return EntityExtractionResult(
        entities=_merge_reflection_additions(first_pass.entities, reflection.entities)
    )
