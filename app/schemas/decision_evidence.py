from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
)

EvidenceType = Literal[
    "supporting",
    "opposing",
]

EvidenceRelevanceNote = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=1000,
    ),
]


class DecisionEvidenceCreate(BaseModel):
    document_chunk_id: UUID
    evidence_type: EvidenceType
    relevance_note: EvidenceRelevanceNote | None = None

    model_config = ConfigDict(
        extra="forbid",
    )


class DecisionEvidenceCitationResponse(BaseModel):
    document_id: UUID
    document_version_id: UUID
    document_page_id: UUID
    document_title: str
    file_name: str
    version_number: int
    page_number: int


class DecisionEvidenceResponse(BaseModel):
    id: UUID
    decision_alternative_id: UUID
    document_chunk_id: UUID
    evidence_type: EvidenceType
    relevance_note: str | None
    created_at: datetime
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    citation: DecisionEvidenceCitationResponse
