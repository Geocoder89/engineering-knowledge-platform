from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.domain.decision import DecisionStatus

DecisionTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=200,
    ),
]

DecisionQuestion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=10,
        max_length=2000,
    ),
]

DecisionRationale = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=10,
        max_length=4000,
    ),
]


class DecisionOutcomeCreate(BaseModel):
    selected_alternative_id: UUID
    rationale: DecisionRationale

    model_config = ConfigDict(
        extra="forbid",
    )


class DecisionCreate(BaseModel):
    title: DecisionTitle
    question: DecisionQuestion
    model_config = ConfigDict(
        extra="forbid",
    )


class DecisionResponse(DecisionCreate):
    id: UUID
    status: DecisionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionListResponse(BaseModel):
    items: list[DecisionResponse]
    total: int
    offset: int
    limit: int


class DecisionReviewResponse(DecisionResponse):
    selected_alternative_id: UUID | None
    rationale: str | None
    submitted_at: datetime | None
    decided_at: datetime | None
    cancelled_at: datetime | None
    superseded_at: datetime | None


class DecisionCancellationCreate(BaseModel):
    rationale: DecisionRationale

    model_config = ConfigDict(
        extra="forbid",
    )
