from __future__ import annotations

import re
from typing import Any

from app.services.structure.models import (
    DocumentSection,
    DocumentStructure,
    Provenance,
    StructuralChunk,
)


_HEADING_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)*)\s+(.+?)\s*$"
)


def _parse_heading(
    heading: str,
) -> tuple[str | None, str, int | None]:
    match = _HEADING_PATTERN.match(heading)

    if not match:
        return None, heading.strip(), None

    locator = match.group(1)
    title = match.group(2).strip()
    level = locator.count(".") + 1

    return locator, title, level


def build_document_structure(
    *,
    filename: str,
    chunks: list[dict[str, Any]],
) -> DocumentStructure:

    structural_chunks: list[StructuralChunk] = []

    sections_by_heading: dict[str, DocumentSection] = {}

    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        metadata = chunk.get("metadata") or {}

        headings = [
            str(heading).strip()
            for heading in metadata.get("headings", [])
            if heading
        ]

        provenance: list[Provenance] = []
        pages: set[int] = set()

        for item in metadata.get("doc_items", []):
            for prov in item.get("prov", []):
                page_no = prov.get("page_no")

                if page_no is not None:
                    pages.add(int(page_no))

                bbox = prov.get("bbox")

                provenance.append(
                    Provenance(
                        self_ref=item.get("self_ref"),
                        label=item.get("label"),
                        page_no=page_no,
                        bbox=bbox,
                    )
                )

        structural_chunks.append(
            StructuralChunk(
                chunk_id=chunk_id,
                text=chunk["text"],
                headings=headings,
                pages=sorted(pages),
                provenance=provenance,
            )
        )

        for heading in headings:
            key = heading.strip().lower()

            if key not in sections_by_heading:
                locator, title, level = _parse_heading(heading)

                sections_by_heading[key] = DocumentSection(
                    heading=heading,
                    locator=locator,
                    title=title,
                    level=level,
                )

            section = sections_by_heading[key]

            if chunk_id not in section.chunk_ids:
                section.chunk_ids.append(chunk_id)

            section.pages = sorted(
                set(section.pages).union(pages)
            )

    return DocumentStructure(
        filename=filename,
        sections=list(sections_by_heading.values()),
        chunks=structural_chunks,
    )