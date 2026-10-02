from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.services.llm import create_instructor_client
from app.services.retrieval.models import (
    AnswerCitation,
    GroundedAnswer,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)


class _DraftCitation(BaseModel):
    chunk_id: int = Field(description="ID of a supplied contract passage.")
    supporting_quote: str = Field(
        description=(
            "A short, exact, contiguous quote from that passage that directly "
            "supports the answer."
        )
    )


class _AnswerDraft(BaseModel):
    answer: str = Field(
        description=(
            "A concise answer grounded only in the supplied contract passages. "
            "If evidence is incomplete, say so explicitly."
        )
    )
    citations: list[_DraftCitation] = Field(
        description=(
            "One citation per passage that directly supports the answer, with an "
            "exact supporting quote copied from that passage."
        )
    )
    insufficient_evidence: bool = Field(
        description="True if the supplied passages do not fully answer the question."
    )


class ContractAnswerer:
    """Generate a cited answer from retrieved contract chunks only."""

    MAX_CONTEXT_CHUNKS = 8

    def __init__(self, model_choice: str = "local_qwen") -> None:
        self.model_choice = model_choice
        self.client, self.model = create_instructor_client(
            model_choice,
            task="answer",
        )

    def answer(
        self,
        *,
        query: str,
        chunks: list[RetrievedChunk],
    ) -> GroundedAnswer:
        context_chunks = chunks[: self.MAX_CONTEXT_CHUNKS]
        if not context_chunks:
            return self._abstention()

        context = "\n\n".join(
            (
                f"[CHUNK {chunk.chunk_id}; PAGES {', '.join(map(str, chunk.pages)) or 'unknown'}; "
                f"HEADINGS {', '.join(chunk.headings) or 'unknown'}]\n{chunk.text}"
            )
            for chunk in context_chunks
        )
        system_prompt = """
You answer questions about a contract using only the supplied passages.

Rules:
- Do not use outside knowledge or infer terms not stated in the passages.
- Answer the question directly and concisely.
- Cite each material claim with a citation containing the chunk ID and a short,
  exact, contiguous quote from that chunk that directly supports the claim.
- Do not cite a passage merely because it discusses the same topic; it must
  support the specific claim in your answer.
- Only cite chunk IDs included in the supplied passages.
- If the passages do not fully answer the question, state what is supported
  and what is missing, and set insufficient_evidence to true.
- If nothing in the passages answers the question, say the evidence is
  insufficient, return no citations, and set insufficient_evidence to true.
- Quotes must be copied exactly from the passage. Do not invent or paraphrase
  the supporting quote.
""".strip()
        user_prompt = f"""
QUESTION
{query}

CONTRACT PASSAGES
-----------------
{context}
-----------------
""".strip()

        draft = self.client.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=_AnswerDraft,
            max_retries=1,
            timeout=900.0,
            temperature=0,
        )

        chunks_by_id = {chunk.chunk_id: chunk for chunk in context_chunks}
        invalid_ids = {
            citation.chunk_id
            for citation in draft.citations
            if citation.chunk_id not in chunks_by_id
        }
        if invalid_ids:
            logger.warning(
                "[ContractAnswerer] Model cited unavailable chunks: %s",
                sorted(invalid_ids),
            )
            return self._abstention()

        if not draft.citations:
            logger.warning(
                "[ContractAnswerer] Model returned no evidence citations; abstaining"
            )
            return self._abstention()

        citations_by_id = {}
        for citation in draft.citations:
            chunk = chunks_by_id[citation.chunk_id]
            if not self._quote_is_in_chunk(citation.supporting_quote, chunk.text):
                logger.warning(
                    "[ContractAnswerer] Supporting quote for chunk %s was not "
                    "found verbatim; abstaining",
                    citation.chunk_id,
                )
                return self._abstention()
            citations_by_id.setdefault(
                citation.chunk_id,
                AnswerCitation(
                    chunk_id=citation.chunk_id,
                    supporting_quote=citation.supporting_quote.strip(),
                    pages=chunk.pages,
                    headings=chunk.headings,
                ),
            )

        return GroundedAnswer(
            answer=draft.answer,
            citations=list(citations_by_id.values()),
            insufficient_evidence=draft.insufficient_evidence,
        )

    @staticmethod
    def _quote_is_in_chunk(quote: str, chunk_text: str) -> bool:
        normalized_quote = " ".join(quote.split()).casefold()
        normalized_text = " ".join(chunk_text.split()).casefold()
        return len(normalized_quote) >= 12 and normalized_quote in normalized_text

    @staticmethod
    def _abstention() -> GroundedAnswer:
        return GroundedAnswer(
            answer="The retrieved contract passages do not provide enough evidence to answer this question.",
            citations=[],
            insufficient_evidence=True,
        )
