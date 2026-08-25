from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentProcessingJobResponse(BaseModel):
    id: UUID
    document_version_id: UUID
    status: Literal[
        "queued",
        "processing",
        "completed",
        "failed",
    ]
    attempt_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
