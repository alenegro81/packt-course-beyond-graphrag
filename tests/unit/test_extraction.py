from financial_advisor.extraction.entities import _apply_reflection, _restrict_resolved_strings_to_settled_entities
from financial_advisor.extraction.prompts import REFLECTION_COREFERENCE_GUIDANCE
from financial_advisor.extraction.relationships import _filter_valid_relationships
from financial_advisor.extraction.validators import (
    EntityExtractionResult,
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    RelationshipExtractionResult,
    RelationshipType,
)


def test_entity_extraction_result_parses_from_dict():
    raw = {"entities": [{"string": "3M Company", "resolved_string": "3M Company", "type": "Company"}]}
    result = EntityExtractionResult(**raw)
    assert len(result.entities) == 1
    assert result.entities[0].type == EntityType.COMPANY


def test_extracted_entity_tracks_literal_mention_separately_from_resolved_form():
    # The reported issue this fixes: "The Company" showing up as its own entity, unlinked from
    # 3M. resolved_string is what write_extraction_to_graph merges nodes on; string keeps the
    # literal surface form the filing actually used, so the coreference stays auditable.
    entity = ExtractedEntity(string="The Company", resolved_string="3M", type=EntityType.COMPANY)
    assert entity.string == "The Company"
    assert entity.resolved_string == "3M"


def test_reflection_coreference_guidance_mentions_the_company_example():
    assert "the Company" in REFLECTION_COREFERENCE_GUIDANCE
    assert "resolved_string" in REFLECTION_COREFERENCE_GUIDANCE


def test_apply_reflection_adds_new_entities():
    first_pass = [ExtractedEntity(string="3M", resolved_string="3M", type=EntityType.COMPANY)]
    reflection = [ExtractedEntity(string="Mike Roman", resolved_string="Mike Roman", type=EntityType.PERSON)]
    merged = _apply_reflection(first_pass, reflection)
    assert [e.string for e in merged] == ["3M", "Mike Roman"]


def test_apply_reflection_corrects_resolved_string_of_an_existing_entity():
    # The reported issue this fixes: "the Company" showing up as its own entity, unlinked from
    # 3M. Reflection sees the settled first-pass list plus the source text and can now correct
    # an existing entity's resolved_string — it doesn't need to have been the one that
    # originally extracted the coreferenced mention.
    first_pass = [
        ExtractedEntity(string="3M", resolved_string="3M", type=EntityType.COMPANY),
        ExtractedEntity(string="the Company", resolved_string="the Company", type=EntityType.COMPANY),
    ]
    reflection = [
        # correction, not a new entity: string matches an existing one, resolved_string differs
        ExtractedEntity(string="the Company", resolved_string="3M", type=EntityType.COMPANY),
    ]
    merged = _apply_reflection(first_pass, reflection)
    assert len(merged) == 2  # no duplicate added
    corrected = next(e for e in merged if e.string == "the Company")
    assert corrected.resolved_string == "3M"


def test_apply_reflection_correction_is_case_insensitive_on_string_match():
    first_pass = [ExtractedEntity(string="The Company", resolved_string="The Company", type=EntityType.COMPANY)]
    reflection = [ExtractedEntity(string="the company", resolved_string="3M", type=EntityType.COMPANY)]
    merged = _apply_reflection(first_pass, reflection)
    assert len(merged) == 1
    assert merged[0].string == "The Company"  # original casing preserved
    assert merged[0].resolved_string == "3M"


def test_restrict_resolved_strings_keeps_valid_same_type_resolution():
    entities = [
        ExtractedEntity(string="3M", resolved_string="3M", type=EntityType.COMPANY),
        ExtractedEntity(string="the Company", resolved_string="3M", type=EntityType.COMPANY),
    ]
    fixed = _restrict_resolved_strings_to_settled_entities(entities)
    assert fixed[1].resolved_string == "3M"


def test_restrict_resolved_strings_resets_cross_type_violation():
    # Regression, observed live: despite the prompt constraint, the model sometimes redirects a
    # Risk entity extracted as a whole sentence that merely mentions "the Company" in passing to
    # a Company entity's string. A coreference must stay within the same type.
    entities = [
        ExtractedEntity(string="3M", resolved_string="3M", type=EntityType.COMPANY),
        ExtractedEntity(
            string="* The Company faces liabilities related to certain fluorochemicals.",
            resolved_string="3M",
            type=EntityType.RISK,
        ),
    ]
    fixed = _restrict_resolved_strings_to_settled_entities(entities)
    risk_entity = fixed[1]
    assert risk_entity.resolved_string == risk_entity.string


def test_restrict_resolved_strings_resets_resolution_to_a_nonexistent_entity():
    # A coreference may only point at a string that's actually one of the settled entities —
    # never an invented canonical form nobody extracted.
    entities = [
        ExtractedEntity(string="the Company", resolved_string="Ghost Company", type=EntityType.COMPANY),
    ]
    fixed = _restrict_resolved_strings_to_settled_entities(entities)
    assert fixed[0].resolved_string == "the Company"


def test_relationship_extraction_result_parses_from_dict():
    raw = {
        "relationships": [
            {"source": "Mike Roman", "target": "3M Company", "type": "EMPLOYED_BY"}
        ]
    }
    result = RelationshipExtractionResult(**raw)
    assert len(result.relationships) == 1
    assert result.relationships[0].type == RelationshipType.EMPLOYED_BY


def test_apply_reflection_with_no_additions_or_corrections():
    first_pass = [ExtractedEntity(string="3M Company", resolved_string="3M Company", type=EntityType.COMPANY)]
    merged = _apply_reflection(first_pass, [])
    assert merged == first_pass


def test_filter_valid_relationships_drops_unknown_entities():
    relationships = [
        ExtractedRelationship(source="3M Company", target="Mike Roman", type=RelationshipType.EMPLOYED_BY),
        ExtractedRelationship(source="3M Company", target="A Ghost Entity", type=RelationshipType.EMPLOYED_BY),
    ]
    valid = _filter_valid_relationships(relationships, ["3M Company", "Mike Roman"])
    assert len(valid) == 1
    assert valid[0].target == "Mike Roman"


def test_filter_valid_relationships_is_case_insensitive():
    relationships = [
        ExtractedRelationship(source="3M COMPANY", target="mike roman", type=RelationshipType.EMPLOYED_BY),
    ]
    valid = _filter_valid_relationships(relationships, ["3M Company", "Mike Roman"])
    assert len(valid) == 1


def test_filter_valid_relationships_ignores_leading_bullet_marker():
    # Regression, observed live on the 3M subsidiaries table: the parent company's entity was
    # extracted with the source PDF's own bullet marker as part of its literal string
    # ("- 3M Company", from a row reading "- 3M Company" under "Registrant"), but the model's
    # relationship output reasonably wrote the clean "3M Company" as the target — an exact-match
    # check alone dropped all 35 otherwise-correct SUBSIDIARY_OF relationships as "unknown".
    relationships = [
        ExtractedRelationship(
            source="3M Financial Management Company", target="3M Company", type=RelationshipType.SUBSIDIARY_OF
        ),
    ]
    valid = _filter_valid_relationships(relationships, ["- 3M Company", "3M Financial Management Company"])
    assert len(valid) == 1


def test_filter_valid_relationships_bullet_normalization_does_not_over_match():
    # "3M Company" itself must never be treated as if it had a stripped marker — the regex
    # requires trailing punctuation ("." or ")") for the alnum-prefix case specifically so an
    # ordinary name starting with 1-2 alphanumeric characters is left alone.
    relationships = [
        ExtractedRelationship(source="A Ghost Entity", target="3M Company", type=RelationshipType.SUBSIDIARY_OF),
    ]
    valid = _filter_valid_relationships(relationships, ["3M Company"])
    assert len(valid) == 0
