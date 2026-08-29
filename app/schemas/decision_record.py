from pydantic import BaseModel

from app.schemas.decision import DecisionReviewResponse
from app.schemas.decision_alternative import DecisionAlternativeResponse
from app.schemas.decision_evidence import DecisionEvidenceResponse


class DecisionRecordAlternativeResponse(
    DecisionAlternativeResponse,
):
    evidence: list[DecisionEvidenceResponse]


class DecisionRecordHistorySummaryResponse(BaseModel):
    total: int
    url: str


class DecisionRecordResponse(
    DecisionReviewResponse,
):
    alternatives: list[DecisionRecordAlternativeResponse]
    history: DecisionRecordHistorySummaryResponse
