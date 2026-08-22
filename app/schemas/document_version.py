from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    file_name: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
