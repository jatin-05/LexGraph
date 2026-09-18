from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter

from app.services.extraction.extractor import ContractExtractor
from app.services.extraction.models import (
    Clause,
    ContractExtractionResult,
    DefinedTerm,
    Party,
)

logger = logging.getLogger(__name__)


class ContractProcessingPipeline:
    def __init__(self) -> None:
        self.converter = DocumentConverter()
        self.chunker = HybridChunker()
        self.extractor = ContractExtractor()

    def get_chunks(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> list[dict[str, Any]]:
        if not file_bytes:
            raise ValueError("Document is empty.")

        suffix = Path(filename).suffix or ".pdf"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = Path(temp_file.name)

        try:
            document = self.converter.convert(
                source=temp_path
            ).document

            chunks: list[dict[str, Any]] = []

            for index, chunk in enumerate(
                self.chunker.chunk(dl_doc=document)
            ):
                contextualized_text = self.chunker.contextualize(chunk)

                metadata = None

                if getattr(chunk, "meta", None) is not None:
                    metadata = chunk.meta.export_json_dict()

                chunks.append(
                    {
                        "chunk_id": index,
                        "text": contextualized_text,
                        "metadata": metadata,
                    }
                )

            return chunks

        finally:
            temp_path.unlink(missing_ok=True)

    def extract_chunk(
        self,
        file_bytes: bytes,
        filename: str,
        chunk_index: int = 0,
    ) -> dict[str, Any]:
        chunks = self.get_chunks(
            file_bytes=file_bytes,
            filename=filename,
        )

        if not chunks:
            raise ValueError("Docling produced no chunks.")

        if chunk_index < 0 or chunk_index >= len(chunks):
            raise ValueError(
                f"chunk_index must be between 0 and {len(chunks) - 1}."
            )

        chunk = chunks[chunk_index]

        extraction = self.extractor.extract(
            chunk_text=chunk["text"]
        )

        self._attach_chunk_id(
            extraction,
            chunk["chunk_id"],
        )

        return {
            "chunk": chunk,
            "extraction": extraction.model_dump(),
        }

    def extract_contract(
        self,
        file_bytes: bytes,
        filename: str,
        max_chunks: int | None = None,
    ) -> ContractExtractionResult:
        chunks = self.get_chunks(
            file_bytes=file_bytes,
            filename=filename,
        )

        if not chunks:
            raise ValueError("Docling produced no chunks.")

        if max_chunks is not None:
            if max_chunks <= 0:
                raise ValueError("max_chunks must be greater than 0.")

            chunks = chunks[:max_chunks]

        logger.info(
            "[ContractPipeline] Processing %d chunks from %s",
            len(chunks),
            filename,
        )

        all_parties: list[Party] = []
        all_defined_terms: list[DefinedTerm] = []
        all_clauses: list[Clause] = []
        processed_chunks: list[dict[str, Any]] = []

        for position, chunk in enumerate(chunks, start=1):
            chunk_id = chunk["chunk_id"]

            logger.info(
                "[ContractPipeline] Extracting chunk %d/%d (id=%d)",
                position,
                len(chunks),
                chunk_id,
            )

            extraction = self.extractor.extract(
                chunk_text=chunk["text"]
            )

            self._attach_chunk_id(
                extraction,
                chunk_id,
            )

            all_parties.extend(extraction.parties)
            all_defined_terms.extend(extraction.defined_terms)
            all_clauses.extend(extraction.clauses)

            processed_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "extraction": extraction.model_dump(),
                }
            )

        return ContractExtractionResult(
            filename=filename,
            chunks_processed=len(chunks),
            parties=self._dedupe_parties(all_parties),
            defined_terms=self._dedupe_defined_terms(all_defined_terms),
            clauses=all_clauses,
            chunks=processed_chunks,
        )

    @staticmethod
    def _attach_chunk_id(
        extraction,
        chunk_id: int,
    ) -> None:
        for party in extraction.parties:
            party.source_chunk_id = chunk_id

        for term in extraction.defined_terms:
            term.source_chunk_id = chunk_id

        for clause in extraction.clauses:
            clause.source_chunk_id = chunk_id

            for obligation in clause.obligations:
                obligation.source_chunk_id = chunk_id

            for right in clause.rights:
                right.source_chunk_id = chunk_id

            for reference in clause.references:
                reference.source_chunk_id = chunk_id

    @staticmethod
    def _dedupe_parties(
        parties: list[Party],
    ) -> list[Party]:
        seen: dict[str, Party] = {}

        for party in parties:
            key = party.name.strip().lower()

            if key not in seen:
                seen[key] = party
                continue

            existing = seen[key]

            if (
                existing.designation is None
                and party.designation is not None
            ):
                existing.designation = party.designation

        return list(seen.values())

    @staticmethod
    def _dedupe_defined_terms(
        terms: list[DefinedTerm],
    ) -> list[DefinedTerm]:
        seen: dict[tuple[str, str], DefinedTerm] = {}

        for term in terms:
            key = (
                term.term.strip().lower(),
                term.definition.strip(),
            )

            if key not in seen:
                seen[key] = term

        return list(seen.values())