from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from app.extraction.base import DocumentTextExtractionError
from app.extraction.pdf import PypdfDocumentTextExtractor


def build_blank_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def build_pdf_with_text(text: str) -> bytes:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_stream = (f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET").encode(
        "latin-1"
    )

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 5 0 R >>"
        ),
        (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
        (
            b"<< /Length "
            + str(len(content_stream)).encode("ascii")
            + b" >>\nstream\n"
            + content_stream
            + b"\nendstream"
        ),
    ]

    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{object_number} 0 obj\n".encode("ascii"))
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_offset = len(document)

    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    document.extend(
        (
            f"trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n"
            f"{xref_offset}\n"
            f"%%EOF\n"
        ).encode("ascii")
    )

    return bytes(document)


def build_pdf_with_pages(
    page_texts: tuple[str | None, ...],
) -> bytes:
    output = BytesIO()
    writer = PdfWriter()

    for page_text in page_texts:
        if page_text is None:
            writer.add_blank_page(
                width=612,
                height=792,
            )
            continue

        single_page_pdf = build_pdf_with_text(page_text)
        reader = PdfReader(BytesIO(single_page_pdf))
        writer.add_page(reader.pages[0])

    writer.write(output)

    return output.getvalue()


def test_extracts_text_and_page_count_from_pdf() -> None:
    file_content = build_pdf_with_text("Cooling system design requirements")
    extractor = PypdfDocumentTextExtractor()

    result = extractor.extract(content=file_content)

    assert result.text == "Cooling system design requirements"
    assert result.page_count == 1
    assert result.requires_ocr is False

    assert result.pages_requiring_ocr == ()


def test_identifies_pdf_page_requiring_ocr() -> None:
    file_content = build_blank_pdf()
    extractor = PypdfDocumentTextExtractor()

    result = extractor.extract(content=file_content)

    assert result.text == ""
    assert result.page_count == 1
    assert result.requires_ocr is True
    assert result.pages_requiring_ocr == (1,)


def test_rejects_structurally_invalid_pdf() -> None:
    file_content = b"%PDF-1.7\nThis is not a complete PDF"
    extractor = PypdfDocumentTextExtractor()

    with pytest.raises(
        DocumentTextExtractionError,
        match="Document text extraction failed",
    ):
        extractor.extract(content=file_content)


def test_preserves_extracted_text_by_page() -> None:
    file_content = build_pdf_with_pages(
        (
            "Cooling system requirements",
            None,
            "Electrical system requirements",
        )
    )
    extractor = PypdfDocumentTextExtractor()

    result = extractor.extract(content=file_content)

    assert result.page_count == 3
    assert result.text == (
        "Cooling system requirements\n\nElectrical system requirements"
    )
    assert result.pages_requiring_ocr == (2,)
    assert [(page.page_number, page.text) for page in result.pages] == [
        (1, "Cooling system requirements"),
        (2, ""),
        (3, "Electrical system requirements"),
    ]
