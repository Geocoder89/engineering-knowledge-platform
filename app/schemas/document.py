from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    file_name: str = Field(min_length=1, max_length=255)


class DocumentResponse(DocumentCreate):
    id: UUID
    status: Literal["pending"]
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    offset: int
    limit: int
