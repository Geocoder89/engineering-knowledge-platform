from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentChunkSearchResult:
    document_chunk_id: UUID
    document_page_id: UUID
    document_version_id: UUID
    document_id: UUID
    document_title: str
    file_name: str
    version_number: int
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    cosine_distance: float
