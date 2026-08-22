from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.extraction.base import (
    DocumentTextExtraction,
    DocumentTextExtractionError,
    ExtractedDocumentPage,
)


class PypdfDocumentTextExtractor:
    def extract(self, *, content: bytes) -> DocumentTextExtraction:
        try:
            reader = PdfReader(BytesIO(content))
            extracted_pages: list[ExtractedDocumentPage] = []

            for page_number, page in enumerate(reader.pages, start=1):
                extracted_text = page.extract_text() or ""
                normalized_text = extracted_text.strip()

                extracted_pages.append(
                    ExtractedDocumentPage(
                        page_number=page_number,
                        text=normalized_text,
                    )
                )

            return DocumentTextExtraction(pages=tuple(extracted_pages))
        except PdfReadError as error:
            raise DocumentTextExtractionError() from error
