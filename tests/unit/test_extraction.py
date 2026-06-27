import pytest

from financial_advisor.extraction.validators import ExtractionResult


def test_extraction_result_parses_from_dict():
    raw = {
        "entities": [{"name": "Apple Inc.", "type": "Company"}],
        "relationships": [{"source": "Tim Cook", "target": "Apple Inc.", "type": "CEO_OF"}],
    }
    result = ExtractionResult(**raw)
    assert len(result.entities) == 1
    assert len(result.relationships) == 1
    assert result.relationships[0].type == "CEO_OF"
