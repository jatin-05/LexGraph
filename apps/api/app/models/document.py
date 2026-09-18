from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class TextSpan(BaseModel):
    text: str
    bbox: BoundingBox
    font: str | None = None
    size: float | None = None
    flags: int | None = None


class DocumentBlock(BaseModel):
    block_index: int
    block_type: Literal["text", "image", "unknown"]
    bbox: BoundingBox
    text: str
    spans: list[TextSpan] = Field(default_factory=list)


class DocumentPage(BaseModel):
    page_number: int
    width: float
    height: float
    text: str
    blocks: list[DocumentBlock] = Field(default_factory=list)


class CanonicalDocument(BaseModel):
    document_id: str
    filename: str
    file_type: str
    page_count: int
    metadata: dict[str, str] = Field(default_factory=dict)
    pages: list[DocumentPage]