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
