from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DecisionEvidenceCitation:
    decision_evidence_id: UUID
    decision_alternative_id: UUID
    evidence_type: str
    relevance_note: str | None
    created_at: datetime

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
