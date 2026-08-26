from enum import StrEnum

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    COMPANY = "Company"
    PERSON = "Person"
    PRODUCT = "Product"
    LOCATION = "Location"
    REGULATION = "Regulation"
    RISK = "Risk"
    FINANCIAL_METRIC = "FinancialMetric"


class RelationshipType(StrEnum):
    COMPETES_WITH = "COMPETES_WITH"
    SUBSIDIARY_OF = "SUBSIDIARY_OF"
    SUPPLIES = "SUPPLIES"
    CUSTOMER_OF = "CUSTOMER_OF"
    PRODUCES = "PRODUCES"
    OPERATES_IN = "OPERATES_IN"
    EXPOSED_TO = "EXPOSED_TO"
    REGULATED_BY = "REGULATED_BY"
    EMPLOYED_BY = "EMPLOYED_BY"


class ExtractedEntity(BaseModel):
    string: str = Field(description="Entity name exactly as it appears in the text")
    type: EntityType
    description: str | None = Field(default=None, description="Brief context from the chunk")


class ExtractedRelationship(BaseModel):
    source: str = Field(description="Entity name of the relationship source, from the known entity list")
    target: str = Field(description="Entity name of the relationship target, from the known entity list")
    type: RelationshipType
    evidence: str | None = Field(default=None, description="Verbatim text that supports this link")


class EntityExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)


class RelationshipExtractionResult(BaseModel):
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
