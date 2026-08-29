from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.decision_audit import DecisionAuditEventType


class DecisionAuditEventResponse(BaseModel):
    id: UUID
    decision_id: UUID
    sequence_number: int
    event_type: DecisionAuditEventType
    event_data: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class DecisionAuditHistoryResponse(BaseModel):
    decision_id: UUID
    items: list[DecisionAuditEventResponse]
    total: int
    offset: int
    limit: int
