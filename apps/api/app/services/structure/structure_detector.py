import re

from app.models.document import DocumentBlock


SECTION_PATTERN = re.compile(
    r"^\s*(\d+)\.?\s+(.+?)\s*$"
)


def is_section_heading(block: DocumentBlock) -> bool:
    """
    Detect simple top-level section headings such as:

    1. Definitions
    2. Services
    3. Termination
    """

    if block.block_type != "text":
        return False

    text = " ".join(block.text.split()).strip()

    if not text:
        return False

    match = SECTION_PATTERN.match(text)

    if not match:
        return False

    number = match.group(1)
    title = match.group(2).strip()

    # Avoid treating a long paragraph beginning with "1." as a heading.
    if len(title) > 120:
        return False

    # A heading generally has relatively little text.
    if len(text) > 150:
        return False

    return True