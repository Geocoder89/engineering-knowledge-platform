from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

SearchQuery = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=500,
    ),
]


class DocumentSearchRequest(BaseModel):
    query: SearchQuery
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )


class DocumentSearchCitationResponse(BaseModel):
    document_id: UUID
    document_version_id: UUID
    document_page_id: UUID
    document_title: str
    file_name: str
    version_number: int
    page_number: int


class DocumentSearchItemResponse(BaseModel):
    document_chunk_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    similarity_score: float
    citation: DocumentSearchCitationResponse


class DocumentSearchResponse(BaseModel):
    query: str
    limit: int
    items: list[DocumentSearchItemResponse]
