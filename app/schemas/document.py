from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.document import DocumentStatus


class DocumentStatusUpdate(BaseModel):
    status: DocumentStatus


class DocumentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    file_name: str = Field(min_length=1, max_length=255)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_update_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one document field must be provided")

        if any(
            getattr(self, field_name) is None for field_name in self.model_fields_set
        ):
            raise ValueError("Document fields cannot be null")

        return self


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
