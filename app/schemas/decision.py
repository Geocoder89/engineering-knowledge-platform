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
