from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    chunk_id: int
    text: str
    score: float
    headings: list[str] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    added_via: list[str] = Field(default_factory=list)
    graph_evidence: list[str] = Field(default_factory=list)


class AnswerCitation(BaseModel):
    chunk_id: int
    supporting_quote: str
    pages: list[int] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[AnswerCitation] = Field(default_factory=list)
    insufficient_evidence: bool = False


class RetrievalComparison(BaseModel):
    query: str
    embedding_model: str
    baseline: list[RetrievedChunk]
    graph_augmented: list[RetrievedChunk]
    graph_added_chunk_ids: list[int] = Field(default_factory=list)
    answer_model: str | None = None
    baseline_answer: GroundedAnswer | None = None
    graph_answer: GroundedAnswer | None = None


class ContractQuestionResponse(BaseModel):
    query: str
    embedding_model: str
    answer_model: str
    retrieval_mode: Literal["chunks", "graph"]
    answer: GroundedAnswer
    retrieved_chunks: list[RetrievedChunk]
    graph_added_chunk_ids: list[int] = Field(default_factory=list)
