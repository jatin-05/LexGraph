from io import BytesIO

from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter


class DocumentConverterService:
    def __init__(self) -> None:
        self.converter = DocumentConverter()

    def convert(self, file_bytes: bytes, filename: str):
        if not file_bytes:
            raise ValueError("Document is empty.")

        stream = DocumentStream(
            name=filename,
            stream=BytesIO(file_bytes),
        )

        result = self.converter.convert(stream)

        if result.document is None:
            raise ValueError("Docling could not produce a document.")

        return result.document