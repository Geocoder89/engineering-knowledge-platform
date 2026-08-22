from dataclasses import dataclass


class DocumentTextExtractionError(ValueError):
    def __init__(self) -> None:
        super().__init__("Document text extraction failed")


@dataclass(frozen=True, slots=True)
class ExtractedDocumentPage:
    page_number: int
    text: str

    @property
    def requires_ocr(self) -> bool:
        return not bool(self.text)


@dataclass(frozen=True, slots=True)
class DocumentTextExtraction:
    pages: tuple[ExtractedDocumentPage, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def pages_requiring_ocr(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages if page.requires_ocr)

    @property
    def requires_ocr(self) -> bool:
        return bool(self.pages_requiring_ocr)
