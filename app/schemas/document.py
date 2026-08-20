from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.document import DocumentStatus


class DocumentStatusUpdate(BaseModel):
    status: DocumentStatus


class DocumentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    file_name: str = Field(min_length=1, max_length=255)


class DocumentResponse(DocumentCreate):
    id: UUID
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    offset: int
    limit: int
