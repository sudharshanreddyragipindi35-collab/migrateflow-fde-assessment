from pydantic import BaseModel, Field, model_validator


class TargetField(BaseModel):
    name: str
    type: str
    required: bool
    format: str | None = None
    values: list[str] = []


class TargetSchema(BaseModel):
    name: str
    version: int
    fields: list[TargetField]


class ScoreComponents(BaseModel):
    name_similarity: float = Field(ge=0, le=1)
    alias_match: float = Field(ge=0, le=1)
    type_compatibility: float = Field(ge=0, le=1)
    value_pattern: float = Field(ge=0, le=1)
    uniqueness: float = Field(ge=0, le=1)
    model_proposal: float = Field(ge=0, le=1)


class ModelMapping(BaseModel):
    source_column: str | None = None
    target_field: str | None
    confidence: float = Field(ge=0, le=1)
    alternatives: list[str] = []
    reasoning: str = Field(max_length=1500)
    warnings: list[str] = []


class ModelMappingBatch(BaseModel):
    mappings: list[ModelMapping]


class MappingProposal(BaseModel):
    source_file: str
    source_column: str
    target_field: str | None
    confidence: float = Field(ge=0, le=1)
    alternatives: list[str]
    reasoning: str
    evidence: ScoreComponents
    warnings: list[str]
    requires_human: bool
    collision: bool = False
    provider: str

    @model_validator(mode="after")
    def unmapped_requires_review(self) -> "MappingProposal":
        if self.target_field is None and not self.requires_human:
            raise ValueError("Unmapped proposals require human review")
        return self
