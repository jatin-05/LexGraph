from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter

from app.services.extraction.extractor import ContractExtractor
from app.services.extraction.models import (
    DefinedTerm,
    Party,
)
from app.services.extraction.models import (
    ContractChunkSemanticExtraction,
    ContractSemantics,
)
from app.services.structure.builder import build_document_structure
from app.services.structure.models import DocumentStructure

from app.services.validation.semantic_validator import (
    ContractSemanticValidator,
)

logger = logging.getLogger(__name__)


class ContractProcessingPipeline:
    # Change this whenever the Docling/chunking logic changes
    CACHE_VERSION = "v1"

    def __init__(self) -> None:
        self.converter = DocumentConverter()
        self.chunker = HybridChunker()
        self.extractor = ContractExtractor()
        self.validator = ContractSemanticValidator()

        self.cache_dir = Path(".cache") / "docling"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> str:
        extension = Path(filename).suffix.lower()

        hasher = hashlib.sha256()
        hasher.update(self.CACHE_VERSION.encode("utf-8"))
        hasher.update(extension.encode("utf-8"))
        hasher.update(file_bytes)

        return hasher.hexdigest()

    def _cache_path(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> Path:
        return self.cache_dir / f"{self._cache_key(file_bytes, filename)}.json"

    def _load_cached_chunks(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> list[dict[str, Any]] | None:
        cache_path = self._cache_path(
            file_bytes=file_bytes,
            filename=filename,
        )

        if not cache_path.exists():
            return None

        try:
            with cache_path.open(
                "r",
                encoding="utf-8",
            ) as cache_file:
                payload = json.load(cache_file)

            chunks = payload.get("chunks")

            if not isinstance(chunks, list):
                raise ValueError("Invalid cache format.")

            logger.info(
                "[ContractPipeline] Docling cache HIT: %s",
                cache_path.name,
            )

            return chunks

        except Exception as exc:
            logger.warning(
                "[ContractPipeline] Failed to load cache %s: %s",
                cache_path,
                exc,
            )

            # Corrupt cache should not break processing
            cache_path.unlink(missing_ok=True)
            return None

    def _save_cached_chunks(
        self,
        file_bytes: bytes,
        filename: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        cache_path = self._cache_path(
            file_bytes=file_bytes,
            filename=filename,
        )

        payload = {
            "cache_version": self.CACHE_VERSION,
            "filename": filename,
            "chunks": chunks,
        }

        with cache_path.open(
            "w",
            encoding="utf-8",
        ) as cache_file:
            json.dump(
                payload,
                cache_file,
                ensure_ascii=False,
                indent=2,
            )

        logger.info(
            "[ContractPipeline] Docling cache SAVED: %s",
            cache_path.name,
        )

    def get_chunks(
        self,
        file_bytes: bytes,
        filename: str,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        if not file_bytes:
            raise ValueError("Document is empty.")

        if not force_refresh:
            cached_chunks = self._load_cached_chunks(
                file_bytes=file_bytes,
                filename=filename,
            )

            if cached_chunks is not None:
                return cached_chunks

        logger.info(
            "[ContractPipeline] Docling cache MISS for %s",
            filename,
        )

        suffix = Path(filename).suffix or ".pdf"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = Path(temp_file.name)

        try:
            start = time.perf_counter()

            document = self.converter.convert(
                source=temp_path
            ).document

            docling_elapsed = time.perf_counter() - start

            logger.info(
                "[ContractPipeline] Docling conversion took %.2f seconds",
                docling_elapsed,
            )

            start = time.perf_counter()

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

            chunking_elapsed = time.perf_counter() - start

            logger.info(
                "[ContractPipeline] Chunking took %.2f seconds (%d chunks)",
                chunking_elapsed,
                len(chunks),
            )

            self._save_cached_chunks(
                file_bytes=file_bytes,
                filename=filename,
                chunks=chunks,
            )

            return chunks

        finally:
            temp_path.unlink(missing_ok=True)

    def extract_contract(
        self,
        file_bytes: bytes,
        filename: str,
        max_chunks: int | None = None,
        force_refresh: bool = False,
        validate: bool = True,
    ):
        chunks = self.get_chunks(
            file_bytes=file_bytes,
            filename=filename,
            force_refresh=force_refresh,
        )

        if not chunks:
            raise ValueError("Docling produced no chunks.")

        # Build the structural representation from Docling output.
        structure = build_document_structure(
            filename=filename,
            chunks=chunks,
        )

        # Limit how many chunks are sent to Qwen.
        if max_chunks is not None:
            if max_chunks <= 0:
                raise ValueError("max_chunks must be greater than 0.")

            chunks_to_process = chunks[:max_chunks]
        else:
            chunks_to_process = chunks

        logger.info(
            "[ContractPipeline] Processing %d semantic chunks from %s",
            len(chunks_to_process),
            filename,
        )

        all_parties = []
        all_defined_terms = []
        all_obligations = []
        all_rights = []
        all_references = []

        validation_issues = []

        for position, chunk in enumerate(
            chunks_to_process,
            start=1,
        ):
            chunk_id = chunk["chunk_id"]

            logger.info(
                "[ContractPipeline] Extracting semantic chunk %d/%d (id=%d)",
                position,
                len(chunks_to_process),
                chunk_id,
            )

            # 1. Ask Qwen for semantic candidates.
            extraction = self.extractor.extract(
                chunk_text=chunk["text"]
            )

            # 2. Optionally validate Qwen's output.
            if validate:
                validation = self.validator.validate(
                    extraction=extraction,
                    chunk_text=chunk["text"],
                )

                accepted = validation.accepted

                validation_issues.extend(
                    validation.issues
                )

                logger.info(
                    "[ContractPipeline] Chunk %d validation: "
                    "accepted parties=%d definitions=%d obligations=%d "
                    "rights=%d references=%d issues=%d",
                    chunk_id,
                    len(accepted.parties),
                    len(accepted.defined_terms),
                    len(accepted.obligations),
                    len(accepted.rights),
                    len(accepted.references),
                    len(validation.issues),
                )

            else:
                # Validation disabled: use raw Qwen output.
                accepted = extraction

                logger.info(
                    "[ContractPipeline] Chunk %d validation skipped",
                    chunk_id,
                )

            # 3. Attach chunk provenance to semantic items.
            for party in accepted.parties:
                party.source_chunk_id = chunk_id

            for term in accepted.defined_terms:
                term.source_chunk_id = chunk_id

            for obligation in accepted.obligations:
                obligation.source_chunk_id = chunk_id

            for right in accepted.rights:
                right.source_chunk_id = chunk_id

            for reference in accepted.references:
                reference.source_chunk_id = chunk_id

            # 4. Add accepted/raw facts to contract-level semantics.
            all_parties.extend(accepted.parties)
            all_defined_terms.extend(accepted.defined_terms)
            all_obligations.extend(accepted.obligations)
            all_rights.extend(accepted.rights)
            all_references.extend(accepted.references)

        # 5. Assemble contract-level semantics.
        semantics = ContractSemantics(
            parties=self._dedupe_parties(all_parties),
            defined_terms=self._dedupe_defined_terms(
                all_defined_terms
            ),
            obligations=all_obligations,
            rights=all_rights,
            references=all_references,
        )

        from app.services.processing.models import ContractRepresentation
        from app.services.validation.models import ContractValidationReport

        # 6. Build validation report.
        validation_report = ContractValidationReport(
            chunks_validated=(
                len(chunks_to_process)
                if validate
                else 0
            ),
            issues=validation_issues,
        )

        # 7. Combine structure + semantics + validation.
        return ContractRepresentation(
            structure=structure,
            semantics=semantics,
            validation=validation_report,
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

        for obligation in extraction.obligations:
            obligation.source_chunk_id = chunk_id

        for right in extraction.rights:
            right.source_chunk_id = chunk_id

        for reference in extraction.references:
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

            if existing.role is None and party.role is not None:
                existing.role = party.role

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