from __future__ import annotations

import re
import unicodedata

from app.services.extraction.models import (
    ContractChunkSemanticExtraction,
    Party,
)
from app.services.validation.models import (
    ChunkValidationResult,
    ValidationIssue,
)


class ContractSemanticValidator:
    """
    Deterministically validates LLM-generated semantic extraction
    against the original document chunk.

    The validator does not try to decide whether the legal meaning
    is correct. It checks whether the model's claims are actually
    grounded in the supplied text.
    """

    def validate(
        self,
        extraction: ContractChunkSemanticExtraction,
        chunk_text: str,
    ) -> ChunkValidationResult:

        accepted = ContractChunkSemanticExtraction()
        issues: list[ValidationIssue] = []

        self._validate_parties(
            extraction=extraction,
            chunk_text=chunk_text,
            accepted=accepted,
            issues=issues,
        )

        self._validate_defined_terms(
            extraction=extraction,
            chunk_text=chunk_text,
            accepted=accepted,
            issues=issues,
        )

        self._validate_obligations(
            extraction=extraction,
            chunk_text=chunk_text,
            accepted=accepted,
            issues=issues,
        )

        self._validate_rights(
            extraction=extraction,
            chunk_text=chunk_text,
            accepted=accepted,
            issues=issues,
        )

        self._validate_references(
            extraction=extraction,
            chunk_text=chunk_text,
            accepted=accepted,
            issues=issues,
        )

        return ChunkValidationResult(
            accepted=accepted,
            issues=issues,
        )

    def _validate_parties(
        self,
        *,
        extraction: ContractChunkSemanticExtraction,
        chunk_text: str,
        accepted: ContractChunkSemanticExtraction,
        issues: list[ValidationIssue],
    ) -> None:

        for index, party in enumerate(extraction.parties):
            if not self._source_supported(
                party.source_text,
                chunk_text,
            ):
                self._reject(
                    issues=issues,
                    item_type="party",
                    item_index=index,
                    reason=(
                        "source_text is not supported by the document chunk."
                    ),
                    item=party.model_dump(),
                    source_text=party.source_text,
                )
                continue

            if not self._contains(
                chunk_text,
                party.name,
            ):
                self._reject(
                    issues=issues,
                    item_type="party",
                    item_index=index,
                    reason=(
                        "party name does not appear in the document chunk."
                    ),
                    item=party.model_dump(),
                    source_text=party.source_text,
                )
                continue

            if (
                party.designation
                and not self._contains(
                    party.source_text,
                    party.designation,
                )
            ):
                cleaned_party = party.model_copy(deep=True)
                cleaned_party.designation = None

                issues.append(
                    ValidationIssue(
                        item_type="party_designation",
                        item_index=index,
                        reason=(
                            "Party was accepted, but its designation was not "
                            "explicitly supported by source_text. "
                            "Designation was removed."
                        ),
                        source_text=party.source_text,
                        item=party.model_dump(),
                    )
                )

                accepted.parties.append(cleaned_party)
                continue

            accepted.parties.append(
                party.model_copy(deep=True)
            )

    def _validate_defined_terms(
        self,
        *,
        extraction: ContractChunkSemanticExtraction,
        chunk_text: str,
        accepted: ContractChunkSemanticExtraction,
        issues: list[ValidationIssue],
    ) -> None:

        for index, term in enumerate(extraction.defined_terms):
            if not self._source_supported(
                term.source_text,
                chunk_text,
            ):
                self._reject(
                    issues=issues,
                    item_type="defined_term",
                    item_index=index,
                    reason="source_text is not supported by the document chunk.",
                    item=term.model_dump(),
                    source_text=term.source_text,
                )
                continue

            if not self._contains(
                chunk_text,
                term.term,
            ):
                self._reject(
                    issues=issues,
                    item_type="defined_term",
                    item_index=index,
                    reason="defined term does not appear in the document chunk.",
                    item=term.model_dump(),
                    source_text=term.source_text,
                )
                continue

            if not self._has_definition_pattern(
                term=term.term,
                source_text=term.source_text,
            ):
                self._reject(
                    issues=issues,
                    item_type="defined_term",
                    item_index=index,
                    reason=(
                        "source_text does not contain an explicit definition "
                        "pattern such as 'means', 'shall mean', 'refers to', "
                        "or 'includes'."
                    ),
                    item=term.model_dump(),
                    source_text=term.source_text,
                )
                continue

            accepted.defined_terms.append(term)

    def _validate_obligations(
        self,
        *,
        extraction: ContractChunkSemanticExtraction,
        chunk_text: str,
        accepted: ContractChunkSemanticExtraction,
        issues: list[ValidationIssue],
    ) -> None:

        for index, obligation in enumerate(
            extraction.obligations
        ):
            if not obligation.party.strip():
                self._reject(
                    issues=issues,
                    item_type="obligation",
                    item_index=index,
                    reason="obligation has no responsible party.",
                    item=obligation.model_dump(),
                    source_text=obligation.source_text,
                )
                continue

            if not obligation.action.strip():
                self._reject(
                    issues=issues,
                    item_type="obligation",
                    item_index=index,
                    reason="obligation has no action.",
                    item=obligation.model_dump(),
                    source_text=obligation.source_text,
                )
                continue

            if not self._source_supported(
                obligation.source_text,
                chunk_text,
            ):
                self._reject(
                    issues=issues,
                    item_type="obligation",
                    item_index=index,
                    reason="source_text is not supported by the document chunk.",
                    item=obligation.model_dump(),
                    source_text=obligation.source_text,
                )
                continue

            accepted.obligations.append(obligation)

    def _validate_rights(
        self,
        *,
        extraction: ContractChunkSemanticExtraction,
        chunk_text: str,
        accepted: ContractChunkSemanticExtraction,
        issues: list[ValidationIssue],
    ) -> None:

        for index, right in enumerate(extraction.rights):
            if not right.party.strip():
                self._reject(
                    issues=issues,
                    item_type="right",
                    item_index=index,
                    reason="right has no receiving party.",
                    item=right.model_dump(),
                    source_text=right.source_text,
                )
                continue

            if not right.action.strip():
                self._reject(
                    issues=issues,
                    item_type="right",
                    item_index=index,
                    reason="right has no action.",
                    item=right.model_dump(),
                    source_text=right.source_text,
                )
                continue

            if not self._source_supported(
                right.source_text,
                chunk_text,
            ):
                self._reject(
                    issues=issues,
                    item_type="right",
                    item_index=index,
                    reason="source_text is not supported by the document chunk.",
                    item=right.model_dump(),
                    source_text=right.source_text,
                )
                continue

            accepted.rights.append(right)

    def _validate_references(
        self,
        *,
        extraction: ContractChunkSemanticExtraction,
        chunk_text: str,
        accepted: ContractChunkSemanticExtraction,
        issues: list[ValidationIssue],
    ) -> None:

        for index, reference in enumerate(
            extraction.references
        ):
            if not self._source_supported(
                reference.source_text,
                chunk_text,
            ):
                self._reject(
                    issues=issues,
                    item_type="reference",
                    item_index=index,
                    reason="source_text is not supported by the document chunk.",
                    item=reference.model_dump(),
                    source_text=reference.source_text,
                )
                continue

            if not self._contains(
                reference.source_text,
                reference.target,
            ):
                self._reject(
                    issues=issues,
                    item_type="reference",
                    item_index=index,
                    reason="reference target does not appear in source_text.",
                    item=reference.model_dump(),
                    source_text=reference.source_text,
                )
                continue

            accepted.references.append(reference)

    @classmethod
    def _source_supported(
        cls,
        source_text: str,
        chunk_text: str,
    ) -> bool:
        if not source_text or not source_text.strip():
            return False

        return cls._normalize(source_text) in cls._normalize(chunk_text)

    @classmethod
    def _contains(
        cls,
        haystack: str,
        needle: str,
    ) -> bool:
        if not haystack or not needle:
            return False

        return cls._normalize(needle) in cls._normalize(haystack)

    @classmethod
    def _has_definition_pattern(
        cls,
        *,
        term: str,
        source_text: str,
    ) -> bool:

        normalized_term = cls._normalize(term).strip("'\"")
        normalized_source = cls._normalize(source_text)

        if not normalized_term:
            return False

        pattern = re.compile(
            rf"""['"]?{re.escape(normalized_term)}['"]?
            \s+
            (?:means|shall mean|refers to|is defined as|shall be defined as|includes)
            \b""",
            re.IGNORECASE | re.VERBOSE,
        )

        return bool(pattern.search(normalized_source))

    @staticmethod
    def _normalize(value: str) -> str:
        value = unicodedata.normalize(
            "NFKC",
            value,
        )

        replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u00a0": " ",
        }

        for old, new in replacements.items():
            value = value.replace(old, new)

        # Remove punctuation differences so that:
        #
        # ("Armorblox"), and
        # ("Armorblox") and
        #
        # are treated as the same evidence.
        value = re.sub(
            r"[^a-zA-Z0-9]+",
            " ",
            value,
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip().lower()

    @staticmethod
    def _reject(
        *,
        issues: list[ValidationIssue],
        item_type: str,
        item_index: int,
        reason: str,
        item: dict,
        source_text: str | None,
    ) -> None:
        issues.append(
            ValidationIssue(
                item_type=item_type,
                item_index=item_index,
                reason=reason,
                source_text=source_text,
                item=item,
            )
        )