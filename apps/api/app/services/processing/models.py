from __future__ import annotations

from pydantic import BaseModel

from app.services.extraction.models import ContractSemantics
from app.services.structure.models import DocumentStructure
from app.services.validation.models import ContractValidationReport


class ContractRepresentation(BaseModel):
    structure: DocumentStructure
    semantics: ContractSemantics
    validation: ContractValidationReport