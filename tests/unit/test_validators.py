import pytest

from financial_advisor.extraction.validators import ExtractionResult, ExtractedEntity, ExtractedRelationship


def test_extraction_result_empty():
    result = ExtractionResult()
    assert result.entities == []
    assert result.relationships == []


def test_extracted_entity_required_fields():
    entity = ExtractedEntity(name="Apple Inc.", type="Company")
    assert entity.name == "Apple Inc."
    assert entity.description is None


def test_extracted_relationship_evidence_optional():
    rel = ExtractedRelationship(source="Tim Cook", target="Apple Inc.", type="CEO_OF")
    assert rel.evidence is None
