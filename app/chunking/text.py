from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int


def chunk_text(
    text: str,
    *,
    max_characters: int,
    overlap_characters: int,
) -> tuple[TextChunk, ...]:

    if max_characters <= 0:
        raise ValueError("max_characters must be greater than zero")

    if overlap_characters < 0:
        raise ValueError("overlap_characters cannot be negative")

    if overlap_characters >= max_characters:
        raise ValueError("overlap_characters must be less than max_characters")

    if not text:
        return ()
    step_size = max_characters - overlap_characters
    chunks: list[TextChunk] = []

    for chunk_index, start_offset in enumerate(range(0, len(text), step_size)):
        end_offset = min(start_offset + max_characters, len(text))

        chunks.append(
            TextChunk(
                chunk_index=chunk_index,
                text=text[start_offset:end_offset],
                start_offset=start_offset,
                end_offset=end_offset,
            ),
        )

        if end_offset == len(text):
            break
    return tuple(chunks)
