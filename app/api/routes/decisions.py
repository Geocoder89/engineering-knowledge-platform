from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.decision import Decision
from app.repositories import decision as decision_repository
from app.schemas.decision import DecisionCreate, DecisionListResponse, DecisionResponse

router = APIRouter(
    prefix="/decisions",
    tags=["decisions"],
)

SessionDependency = Annotated[
    Session,
    Depends(get_session),
]


@router.post(
    "",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    decision: DecisionCreate,
    session: SessionDependency,
) -> Decision:
    created_decision = decision_repository.create_decision(
        session,
        title=decision.title,
        question=decision.question,
    )

    session.commit()

    return created_decision


@router.get(
    "",
    response_model=DecisionListResponse,
)
def list_decisions(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DecisionListResponse:
    decisions = decision_repository.list_decisions(
        session,
        offset=offset,
        limit=limit,
    )
    total = decision_repository.count_decisions(
        session,
    )

    return DecisionListResponse(
        items=decisions,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
)
def get_decision(
    decision_id: UUID,
    session: SessionDependency,
) -> Decision:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    return decision
