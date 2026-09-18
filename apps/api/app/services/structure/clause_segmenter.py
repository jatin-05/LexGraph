import re
from uuid import uuid4

from app.models.document import DocumentPage
from app.models.structure import ClauseNode, SectionNode


CLAUSE_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)+)\.?\s+(.+?)\s*$"
)

LETTER_SUBCLAUSE_PATTERN = re.compile(
    r"^\s*\(([a-z])\)\s+(.+?)\s*$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def detect_clause(text: str) -> tuple[str, str] | None:
    """
    Detect numbered clauses such as:

    7.1 Termination
    7.2 Effect of Termination
    7.2.1 Notice
    """

    text = normalize_text(text)

    match = CLAUSE_PATTERN.match(text)

    if not match:
        return None

    number = match.group(1)
    remainder = match.group(2).strip()

    if len(remainder) > 500:
        return None

    return number, remainder


def detect_letter_subclause(text: str) -> str | None:
    text = normalize_text(text)

    match = LETTER_SUBCLAUSE_PATTERN.match(text)

    if not match:
        return None

    return match.group(1)


def build_sections(
    document_id: str,
    pages: list[DocumentPage],
) -> list[SectionNode]:

    sections: list[SectionNode] = []

    current_section: SectionNode | None = None
    current_clause: ClauseNode | None = None

    def flush_clause():
        nonlocal current_clause

        if current_section is not None and current_clause is not None:
            current_section.clauses.append(current_clause)

        current_clause = None

    def flush_section():
        nonlocal current_section

        flush_clause()

        if current_section is not None:
            sections.append(current_section)

        current_section = None

    for page in pages:
        for block in page.blocks:
            if block.block_type != "text":
                continue

            text = normalize_text(block.text)

            if not text:
                continue

            # ---------------------------------------------------------
            # TOP LEVEL SECTION
            # ---------------------------------------------------------
            #
            # A clause like 7.1 has multiple numeric components,
            # whereas a section like 7 has only one.
            #
            section_match = re.match(
                r"^\s*(\d+)\.?\s+(.+?)\s*$",
                text,
            )

            clause_match = detect_clause(text)

            if section_match and clause_match is None:
                flush_section()

                section_number = section_match.group(1)
                section_title = section_match.group(2).strip()

                current_section = SectionNode(
                    section_id=str(uuid4()),
                    number=section_number,
                    title=section_title,
                    level=1,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    clauses=[],
                )

                continue

            # ---------------------------------------------------------
            # NUMBERED CLAUSE
            # ---------------------------------------------------------
            detected = detect_clause(text)

            if detected:
                number, remainder = detected

                # Create an implicit section if the contract begins
                # directly with numbered clauses.
                if current_section is None:
                    top_level = number.split(".")[0]

                    current_section = SectionNode(
                        section_id=str(uuid4()),
                        number=top_level,
                        title=f"Section {top_level}",
                        level=1,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        clauses=[],
                    )

                flush_clause()

                level = number.count(".") + 1

                current_clause = ClauseNode(
                    clause_id=str(uuid4()),
                    number=number,
                    title=remainder if len(remainder) < 120 else None,
                    text=text,
                    level=level,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    parent_clause_id=None,
                    clause_type=(
                        "subclause"
                        if level > 2
                        else "clause"
                    ),
                )

                current_section.page_end = page.page_number

                continue

            # ---------------------------------------------------------
            # LETTER SUBCLAUSE
            # ---------------------------------------------------------
            if current_clause is not None:
                letter = detect_letter_subclause(text)

                if letter:
                    current_clause.text += f"\n{text}"
                    current_clause.page_end = page.page_number
                    continue

            # ---------------------------------------------------------
            # NORMAL BODY TEXT
            # ---------------------------------------------------------
            if current_clause is not None:
                current_clause.text += f"\n{text}"
                current_clause.page_end = page.page_number

            elif current_section is not None:
                # Text directly under a section but before a numbered
                # clause. Keep it attached to the section's first clause
                # later if needed.
                current_section.page_end = page.page_number

    flush_section()

    return sections