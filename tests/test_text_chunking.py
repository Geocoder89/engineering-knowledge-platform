import pytest

from app.chunking.text import TextChunk, chunk_text


def test_preserves_short_page_text_as_one_chunk() -> None:
    page_text = "Cooling system requirements must be reviewed before installation."

    chunks = chunk_text(
        page_text,
        max_characters=100,
        overlap_characters=20,
    )

    assert chunks == (
        TextChunk(
            chunk_index=0,
            text=page_text,
            start_offset=0,
            end_offset=len(page_text),
        ),
    )


def test_splits_long_text_into_overlapping_chunks() -> None:
    page_text = "ABCDEFGHIJKLMNO"

    chunks = chunk_text(
        page_text,
        max_characters=8,
        overlap_characters=3,
    )

    assert chunks == (
        TextChunk(
            chunk_index=0,
            text="ABCDEFGH",
            start_offset=0,
            end_offset=8,
        ),
        TextChunk(
            chunk_index=1,
            text="FGHIJKLM",
            start_offset=5,
            end_offset=13,
        ),
        TextChunk(
            chunk_index=2,
            text="KLMNO",
            start_offset=10,
            end_offset=15,
        ),
    )


def test_returns_no_chunks_for_empty_text() -> None:
    assert (
        chunk_text(
            "",
            max_characters=100,
            overlap_characters=20,
        )
        == ()
    )


@pytest.mark.parametrize(
    (
        "max_characters",
        "overlap_characters",
        "expected_message",
    ),
    (
        (
            0,
            0,
            "max_characters must be greater than zero",
        ),
        (
            100,
            -1,
            "overlap_characters cannot be negative",
        ),
        (
            100,
            100,
            "overlap_characters must be less than max_characters",
        ),
    ),
)
def test_rejects_invalid_chunk_configuration(
    max_characters: int,
    overlap_characters: int,
    expected_message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        chunk_text(
            "Cooling system requirements",
            max_characters=max_characters,
            overlap_characters=overlap_characters,
        )
