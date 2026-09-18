import hashlib
from uuid import uuid4

import pymupdf

from app.models.document import (
    BoundingBox,
    CanonicalDocument,
    DocumentBlock,
    DocumentPage,
    TextSpan,
)


def _bbox(values: tuple[float, float, float, float]) -> BoundingBox:
    return BoundingBox(
        x0=float(values[0]),
        y0=float(values[1]),
        x1=float(values[2]),
        y1=float(values[3]),
    )


def _extract_text_spans(block: dict) -> list[TextSpan]:
    spans: list[TextSpan] = []

    for line in block.get("lines", []):
        for span in line.get("spans", []):
            spans.append(
                TextSpan(
                    text=span.get("text", ""),
                    bbox=_bbox(tuple(span["bbox"])),
                    font=span.get("font"),
                    size=float(span["size"]) if span.get("size") is not None else None,
                    flags=span.get("flags"),
                )
            )

    return spans


def parse_pdf(
    file_bytes: bytes,
    filename: str,
    document_id: str | None = None,
) -> CanonicalDocument:
    if not file_bytes:
        raise ValueError("PDF file is empty.")

    if document_id is None:
        document_id = str(uuid4())

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    try:
        pdf = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Unable to open PDF: {exc}") from exc

    try:
        pages: list[DocumentPage] = []

        for page_index in range(pdf.page_count):
            page = pdf[page_index]

            page_dict = page.get_text("dict", sort=True)
            page_text = page.get_text("text", sort=True)

            blocks: list[DocumentBlock] = []

            for block_index, block in enumerate(page_dict.get("blocks", [])):
                block_type = block.get("type")

                if block_type == 0:
                    canonical_type = "text"

                    text_parts: list[str] = []

                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text_parts.append(span.get("text", ""))

                    block_text = "".join(text_parts).strip()
                    spans = _extract_text_spans(block)

                elif block_type == 1:
                    canonical_type = "image"
                    block_text = ""
                    spans = []

                else:
                    canonical_type = "unknown"
                    block_text = ""
                    spans = []

                bbox_values = tuple(block.get("bbox", (0, 0, 0, 0)))

                blocks.append(
                    DocumentBlock(
                        block_index=block_index,
                        block_type=canonical_type,
                        bbox=_bbox(bbox_values),
                        text=block_text,
                        spans=spans,
                    )
                )

            pages.append(
                DocumentPage(
                    page_number=page_index + 1,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    text=page_text.strip(),
                    blocks=blocks,
                )
            )

        metadata: dict[str, str] = {}

        for key, value in pdf.metadata.items():
            if value is not None:
                metadata[key] = str(value)

        metadata["sha256"] = file_hash

        return CanonicalDocument(
            document_id=document_id,
            filename=filename,
            file_type="application/pdf",
            page_count=pdf.page_count,
            metadata=metadata,
            pages=pages,
        )

    finally:
        pdf.close()