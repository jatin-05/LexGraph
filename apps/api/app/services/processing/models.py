from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.extraction.models import ContractSemantics
from app.services.relationships.models import ContractGraph, ReferenceResolution
from app.services.structure.models import DocumentStructure
from app.services.validation.models import ContractValidationReport


class ContractRepresentation(BaseModel):
    structure: DocumentStructure
    semantics: ContractSemantics
    validation: ContractValidationReport
    reference_resolutions: list[ReferenceResolution] = Field(default_factory=list)
    graph: ContractGraph = Field(default_factory=ContractGraph)
