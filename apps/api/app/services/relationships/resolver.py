from __future__ import annotations

import re
import unicodedata

from app.services.extraction.models import ContractSemantics
from app.services.relationships.models import ReferenceResolution
from app.services.structure.models import DocumentStructure


_SECTION_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)(?![\w.])")
_LINE_SECTION_NUMBER = re.compile(
    r"^\s*(\d+(?:\.\d+)*)(?:\.)?\s+(.+?)\s*$"
)
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


def _normalize_term(value: str) -> str:
    """Normalize a term, allowing a simple plural at the final word."""
    normalized = _normalize(value)
    words = normalized.split()
    if not words:
        return normalized

    final_word = words[-1]
    if len(final_word) > 3 and final_word.endswith("ies"):
        words[-1] = f"{final_word[:-3]}y"
    elif (
        len(final_word) > 3
        and final_word.endswith("s")
        and not final_word.endswith("ss")
    ):
        words[-1] = final_word[:-1]

    return " ".join(words)


def _section_heading_events(structure: DocumentStructure):
    """Find numbered subsection headings in chunk text, excluding Docling's
    repeated parent-heading context lines.
    """
    events = []
    for chunk_position, chunk in enumerate(structure.chunks):
        contextual_headings = {
            _normalize(heading) for heading in chunk.headings
        }
        for line_position, line in enumerate(chunk.text.splitlines()):
            match = _LINE_SECTION_NUMBER.match(line)
            if not match or _normalize(line) in contextual_headings:
                continue

            locator = match.group(1)
            # A section label is the short text before the first sentence.
            heading_text = match.group(2)
            title = re.split(r"[.!?](?:\s|$)", heading_text, maxsplit=1)[0]
            title = title.strip().rstrip(". ")
            if (
                not title
                or len(title) > 120
                or re.search(r"\bmeans\b", title, re.IGNORECASE)
                or any(quote in title for quote in ('"', "“", "”"))
            ):
                continue

            heading = f"{locator} {title}"
            events.append(
                (chunk_position, line_position, locator, heading)
            )
    return events


def _section_span_chunk_ids(
    *,
    start_event,
    events,
    structure: DocumentStructure,
) -> list[int]:
    """Return chunks containing this numbered section, including its split
    continuation, and stop at the next sibling/ancestor section.
    """
    start_position, _, locator, _ = start_event
    target_depth = locator.count(".") + 1
    parent_locator = locator.rpartition(".")[0] or None
    result: list[int] = []

    for chunk_position in range(start_position, len(structure.chunks)):
        chunk = structure.chunks[chunk_position]
        chunk_events = [
            event for event in events if event[0] == chunk_position
        ]
        start_line = (
            start_event[1]
            if chunk_position == start_position
            else -1
        )

        # A new Docling parent heading ends this subsection only when it
        # changes the subsection's parent. The same parent is repeated as
        # context at the top of every chunk.
        parent_changed = False
        for heading in chunk.headings:
            heading_match = _LINE_SECTION_NUMBER.match(heading)
            if not heading_match:
                continue
            heading_locator = heading_match.group(1)
            heading_depth = heading_locator.count(".") + 1
            if (
                heading_depth <= target_depth
                and heading_locator != parent_locator
                and heading_locator != locator
            ):
                parent_changed = True
                break

        if parent_changed:
            break

        boundary = next(
            (
                event
                for event in chunk_events
                if event[1] > start_line
                and event[2] != locator
                and event[2].count(".") + 1 <= target_depth
                and (
                    parent_locator is None
                    or event[2].rpartition(".")[0] == parent_locator
                    or event[2].count(".") + 1 < target_depth
                )
            ),
            None,
        )

        if boundary is not None:
            contextual_headings = {
                _normalize(heading) for heading in chunk.headings
            }
            content_before_boundary = any(
                line.strip()
                and _normalize(line) not in contextual_headings
                for line in chunk.text.splitlines()[start_line + 1:boundary[1]]
            )
            if content_before_boundary and chunk.chunk_id not in result:
                result.append(chunk.chunk_id)
            break

        if chunk.chunk_id not in result:
            result.append(chunk.chunk_id)

    return result


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
            elif reference_type in _EXTERNAL_REFERENCE_TYPES:
                term_resolution = self._resolve_defined_term(
                    index,
                    reference,
                    semantics,
                )
                if term_resolution.status in {"resolved", "ambiguous"}:
                    results.append(term_resolution)
                    continue

                results.append(
                    ReferenceResolution(
                        reference_index=index,
                        source_chunk_id=reference.source_chunk_id,
                        target=reference.target,
                        reference_type=reference.reference_type,
                        status="external",
                        target_kind="external",
                        source_text=reference.source_text,
                        reason=(
                            "No matching defined term was found; this reference "
                            "is treated as external."
                        ),
                    )
                )
            else:
                results.append(
                    ReferenceResolution(
                        reference_index=index,
                        source_chunk_id=reference.source_chunk_id,
                        target=reference.target,
                        reference_type=reference.reference_type,
                        status="unresolved",
                        reason="Reference type is not supported by the resolver.",
                        source_text=reference.source_text,
                    )
                )

        return results

    @staticmethod
    def _resolve_section(index, reference, structure) -> ReferenceResolution:
        normalized_target = _normalize(reference.target)
        number_matches = list(_SECTION_NUMBER.finditer(normalized_target))
        locators = list(dict.fromkeys(match.group(1) for match in number_matches))
        locator = locators[0] if len(locators) == 1 else normalized_target

        if len(locators) > 1:
            requested_locators = {_normalize(value) for value in locators}
        else:
            requested_locators = {_normalize(locator)}

        matches = [
            section
            for section in structure.sections
            if section.locator
            and _normalize(section.locator) in requested_locators
        ]
        labels = [section.heading for section in matches]

        # Docling may expose only top-level headings in chunk metadata while
        # subsection headings remain in chunk text. Recover each subsection's
        # full chunk span, including continuation chunks before its next sibling.
        if not matches and len(locators) == 1:
            locator = locators[0]
            events = _section_heading_events(structure)
            matching_events = [
                event for event in events if event[2] == locator
            ]

            if matching_events:
                candidates = list(dict.fromkeys(event[3] for event in matching_events))
                is_unique_heading = len(matching_events) == 1
                target_chunk_ids = sorted(
                    {
                        chunk_id
                        for event in matching_events
                        for chunk_id in _section_span_chunk_ids(
                            start_event=event,
                            events=events,
                            structure=structure,
                        )
                    }
                )

                return ReferenceResolution(
                    reference_index=index,
                    source_chunk_id=reference.source_chunk_id,
                    target=reference.target,
                    reference_type=reference.reference_type,
                    status="resolved" if is_unique_heading else "ambiguous",
                    target_kind="section",
                    resolved_target=candidates[0] if is_unique_heading else None,
                    target_chunk_ids=target_chunk_ids,
                    candidates=candidates,
                    source_text=reference.source_text,
                    reason=(
                        None
                        if is_unique_heading
                        else "Multiple headings matched the referenced section locator."
                    ),
                )

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
                source_text=reference.source_text,
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
            source_text=reference.source_text,
            reason=(
                "Multiple sections matched the referenced locator."
                if matches
                else "No section heading or chunk heading matched the referenced locator."
            ),
        )

    @staticmethod
    def _resolve_defined_term(index, reference, semantics) -> ReferenceResolution:
        target = _normalize_term(reference.target)
        matches = [
            term
            for term in semantics.defined_terms
            if _normalize_term(term.term) == target
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
            source_text=reference.source_text,
            reason=(
                "Multiple extracted defined terms matched the reference target."
                if len(matches) > 1
                else "No extracted defined term matched the reference target."
                if not matches
                else None
            ),
        )
