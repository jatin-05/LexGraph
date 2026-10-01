from __future__ import annotations

import re
import unicodedata

from app.services.extraction.models import ContractSemantics
from app.services.relationships.models import ReferenceResolution
from app.services.structure.models import DocumentStructure


_SECTION_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)(?![\w.])")
_EXTERNAL_REFERENCE_TYPES = {
    "agreement_reference",
    "document_reference",
    "exhibit_reference",
    "order_form_reference",
    "other_contract_reference",
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.strip().strip("\"'“”‘’")
    return " ".join(re.sub(r"[^\w.]+", " ", value).split())


class ContractReferenceResolver:
    """Resolve extracted references to sections and defined terms when possible."""

    def resolve(
        self,
        *,
        semantics: ContractSemantics,
        structure: DocumentStructure,
    ) -> list[ReferenceResolution]:
        results: list[ReferenceResolution] = []

        for index, reference in enumerate(semantics.references):
            reference_type = reference.reference_type.casefold()

            if reference_type == "section_reference":
                results.append(
                    self._resolve_section(index, reference, structure)
                )
            elif reference_type == "defined_term_reference":
                results.append(
                    self._resolve_defined_term(index, reference, semantics)
                )
            else:
                is_external = reference_type in _EXTERNAL_REFERENCE_TYPES
                results.append(
                    ReferenceResolution(
                        reference_index=index,
                        source_chunk_id=reference.source_chunk_id,
                        target=reference.target,
                        reference_type=reference.reference_type,
                        status="external" if is_external else "unresolved",
                        target_kind="external" if is_external else None,
                    )
                )

        return results

    @staticmethod
    def _resolve_section(index, reference, structure) -> ReferenceResolution:
        normalized_target = _normalize(reference.target)
        number_matches = list(_SECTION_NUMBER.finditer(normalized_target))
        locators = list(dict.fromkeys(match.group(1) for match in number_matches))
        locator = locators[0] if len(locators) == 1 else normalized_target

        requested_locators = {
            _normalize(value) for value in locators
        } if len(locators) > 1 else {_normalize(locator)}

        matches = [
            section
            for section in structure.sections
            if section.locator
            and _normalize(section.locator) in requested_locators
        ]
        labels = [section.heading for section in matches]

        if len(matches) == 1 and len(locators) <= 1:
            section = matches[0]
            return ReferenceResolution(
                reference_index=index,
                source_chunk_id=reference.source_chunk_id,
                target=reference.target,
                reference_type=reference.reference_type,
                status="resolved",
                target_kind="section",
                resolved_target=section.heading,
                target_chunk_ids=section.chunk_ids,
                candidates=labels,
            )

        return ReferenceResolution(
            reference_index=index,
            source_chunk_id=reference.source_chunk_id,
            target=reference.target,
            reference_type=reference.reference_type,
            status="ambiguous" if matches else "unresolved",
            target_kind="section",
            target_chunk_ids=sorted(
                {chunk_id for section in matches for chunk_id in section.chunk_ids}
            ),
            candidates=labels,
        )

    @staticmethod
    def _resolve_defined_term(index, reference, semantics) -> ReferenceResolution:
        target = _normalize(reference.target)
        matches = [
            term
            for term in semantics.defined_terms
            if _normalize(term.term) == target
        ]
        labels = [term.term for term in matches]
        chunk_ids = sorted(
            {
                term.source_chunk_id
                for term in matches
                if term.source_chunk_id is not None
            }
        )

        if len(matches) == 1:
            status = "resolved"
            resolved_target = matches[0].term
        elif matches:
            status = "ambiguous"
            resolved_target = None
        else:
            status = "unresolved"
            resolved_target = None

        return ReferenceResolution(
            reference_index=index,
            source_chunk_id=reference.source_chunk_id,
            target=reference.target,
            reference_type=reference.reference_type,
            status=status,
            target_kind="defined_term",
            resolved_target=resolved_target,
            target_chunk_ids=chunk_ids,
            candidates=labels,
        )
