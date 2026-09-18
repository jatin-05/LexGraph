from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.extraction.models import ContractChunkSemanticExtraction


class ValidationIssue(BaseModel):
    item_type: str
    item_index: int
    reason: str
    source_text: str | None = None
    item: dict[str, Any] = Field(default_factory=dict)


class ChunkValidationResult(BaseModel):
    accepted: ContractChunkSemanticExtraction
    issues: list[ValidationIssue] = Field(default_factory=list)


class ContractValidationReport(BaseModel):
    chunks_validated: int
    issues: list[ValidationIssue] = Field(default_factory=list)