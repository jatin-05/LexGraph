from __future__ import annotations

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    l: float
    t: float
    r: float
    b: float
    coord_origin: str | None = None


class Provenance(BaseModel):
    self_ref: str | None = None
    label: str | None = None
    page_no: int | None = None
    bbox: BoundingBox | None = None


class StructuralChunk(BaseModel):
    chunk_id: int
    text: str
    headings: list[str] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)


class DocumentSection(BaseModel):
    heading: str
    locator: str | None = None
    title: str | None = None
    level: int | None = None
    chunk_ids: list[int] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)


class DocumentStructure(BaseModel):
    filename: str
    sections: list[DocumentSection] = Field(default_factory=list)
    chunks: list[StructuralChunk] = Field(default_factory=list)