from __future__ import annotations

from pydantic import BaseModel, Field


class Party(BaseModel):
    name: str = Field(
        description=(
            "Exact party name or party description explicitly stated "
            "in the contract."
        )
    )
    designation: str | None = Field(
        default=None,
        description=(
            "Explicit contractual label for the party, such as "
            "'Customer' or 'Armorblox'. Do not infer."
        ),
    )
    source_text: str = Field(
        description=(
            "REQUIRED: exact or near-exact supporting text copied "
            "from the supplied document chunk."
        )
    )
    source_chunk_id: int | None = None


class DefinedTerm(BaseModel):
    term: str = Field(
        description="Exact defined term."
    )
    definition: str = Field(
        description="Definition explicitly assigned to the term."
    )
    source_text: str = Field(
        description="Text containing the actual definition."
    )
    source_chunk_id: int | None = None


class Obligation(BaseModel):
    party: str = Field(
        description="Party responsible for the obligation."
    )
    action: str = Field(
        description="Action explicitly required."
    )
    object: str | None = None
    condition: str | None = None
    deadline: str | None = None
    source_text: str = Field(
        description="Text supporting the obligation."
    )
    source_chunk_id: int | None = None


class Right(BaseModel):
    party: str = Field(
        description="Party receiving the right."
    )
    action: str = Field(
        description="Action explicitly permitted."
    )
    condition: str | None = None
    deadline: str | None = None
    source_text: str = Field(
        description="Text supporting the right."
    )
    source_chunk_id: int | None = None


class Reference(BaseModel):
    target: str = Field(
        description="Referenced clause, section, defined term, exhibit, Order Form, or other provision."
    )
    reference_type: str = Field(
        description=(
            "Type of reference, such as "
            "section_reference, defined_term_reference, "
            "order_form_reference, exhibit_reference, "
            "or document_reference."
        )
    )
    source_text: str = Field(
        description="Text containing the reference."
    )
    source_chunk_id: int | None = None


class ContractChunkSemanticExtraction(BaseModel):
    """Semantic information extracted from one chunk."""

    parties: list[Party] = Field(default_factory=list)
    defined_terms: list[DefinedTerm] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    rights: list[Right] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)


class ContractSemantics(BaseModel):
    """Semantic information assembled from the entire contract."""

    parties: list[Party] = Field(default_factory=list)
    defined_terms: list[DefinedTerm] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    rights: list[Right] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)   