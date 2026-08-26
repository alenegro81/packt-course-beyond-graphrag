from dataclasses import dataclass

from pydantic import BaseModel, Field

from financial_advisor.extraction.validators import EntityType


@dataclass
class CandidateNode:
    """One node in a same-type resolution pool — an extracted `RecognisedEntity` mention or a
    curated `Company`/`Person` node. `key` holds whatever properties re-select this exact node
    in Cypher (`{string, doc_id}` for extracted mentions, `{id}` for curated nodes) since the two
    label families use different uniqueness keys."""

    label: str
    key: dict[str, str]
    name: str
    entity_type: EntityType


class CandidateJudgment(BaseModel):
    index: int = Field(description="0-based index of the candidate as given in the prompt")
    same_entity: bool = Field(
        description="True only if this candidate is the exact same real-world entity as the target"
    )
    reason: str = Field(description="One-sentence justification grounded in the evidence given")


class ResolutionResult(BaseModel):
    judgments: list[CandidateJudgment] = Field(default_factory=list)
