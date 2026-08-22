class EmptyDocumentFileError(ValueError):
    def __init__(self) -> None:
        super().__init__("Document file cannot be empty")


class UnsupportedDocumentFileTypeError(ValueError):
    def __init__(self) -> None:
        super().__init__("Only PDF files are supported")


class InvalidPdfContentError(ValueError):
    def __init__(self) -> None:
        super().__init__("Uploaded content is not a valid PDF")


def validate_document_file(
    *,
    content_type: str,
    content: bytes,
) -> None:
    if not content:
        raise EmptyDocumentFileError()

    if content_type != "application/pdf":
        raise UnsupportedDocumentFileTypeError()

    if not content.startswith(b"%PDF-"):
        raise InvalidPdfContentError()
