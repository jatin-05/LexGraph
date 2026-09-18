from typing import Literal

from pydantic import BaseModel, Field


class ClauseNode(BaseModel):
    clause_id: str
    number: str
    title: str | None = None
    text: str
    level: int
    page_start: int
    page_end: int
    parent_clause_id: str | None = None
    clause_type: Literal["section", "clause", "subclause"]


class SectionNode(BaseModel):
    section_id: str
    number: str
    title: str
    level: int
    page_start: int
    page_end: int
    clauses: list[ClauseNode] = Field(default_factory=list)


class ContractStructure(BaseModel):
    document_id: str
    sections: list[SectionNode] = Field(default_factory=list)