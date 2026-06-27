from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    name: str
    type: str = Field(description="Node label, e.g. Company, Person, Product, Risk")
    description: str | None = None


class ExtractedRelationship(BaseModel):
    source: str = Field(description="Name of the source entity")
    target: str = Field(description="Name of the target entity")
    type: str = Field(description="Relationship type in SCREAMING_SNAKE_CASE")
    evidence: str | None = Field(default=None, description="Verbatim text that supports this link")


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
