from financial_advisor.extraction.entities import _merge_reflection_additions
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
    raw = {"entities": [{"string": "3M Company", "type": "Company"}]}
    result = EntityExtractionResult(**raw)
    assert len(result.entities) == 1
    assert result.entities[0].type == EntityType.COMPANY


def test_relationship_extraction_result_parses_from_dict():
    raw = {
        "relationships": [
            {"source": "Mike Roman", "target": "3M Company", "type": "EMPLOYED_BY"}
        ]
    }
    result = RelationshipExtractionResult(**raw)
    assert len(result.relationships) == 1
    assert result.relationships[0].type == RelationshipType.EMPLOYED_BY


def test_merge_reflection_additions_keeps_new_entities_only():
    first_pass = [ExtractedEntity(string="3M Company", type=EntityType.COMPANY)]
    reflection = [
        ExtractedEntity(string="3m company", type=EntityType.COMPANY),  # duplicate, case-insensitive
        ExtractedEntity(string="Mike Roman", type=EntityType.PERSON),
    ]
    merged = _merge_reflection_additions(first_pass, reflection)
    assert [e.string for e in merged] == ["3M Company", "Mike Roman"]


def test_merge_reflection_additions_with_no_additions():
    first_pass = [ExtractedEntity(string="3M Company", type=EntityType.COMPANY)]
    merged = _merge_reflection_additions(first_pass, [])
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
