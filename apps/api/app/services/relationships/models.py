from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReferenceResolution(BaseModel):
    """Resolution result for one extracted contract reference."""

    reference_index: int
    source_chunk_id: int | None = None
    target: str
    reference_type: str
    status: Literal["resolved", "ambiguous", "unresolved", "external"]
    target_kind: Literal["section", "defined_term", "external"] | None = None
    resolved_target: str | None = None
    target_chunk_ids: list[int] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    source_text: str | None = None
    reason: str | None = None


class ContractEntity(BaseModel):
    """A stable node in the in-memory contract graph."""

    entity_id: str
    entity_type: Literal["document", "section", "defined_term"]
    value: str
    filename: str | None = None
    locator: str | None = None
    title: str | None = None
    definition: str | None = None
    chunk_ids: list[int] = Field(default_factory=list)


class ContractRelationship(BaseModel):
    """An evidence-linked edge in the in-memory contract graph."""

    relationship_id: str
    relationship_type: Literal["contains_section", "defines", "references"]
    source_entity_id: str
    source_entity_type: Literal["document", "section", "defined_term"]
    target_entity_id: str
    target_entity_type: Literal["document", "section", "defined_term"]
    source_chunk_id: int | None = None
    source_text: str | None = None


class ContractGraph(BaseModel):
    """An in-memory graph built from document structure and accepted semantics."""

    entities: list[ContractEntity] = Field(default_factory=list)
    relationships: list[ContractRelationship] = Field(default_factory=list)
