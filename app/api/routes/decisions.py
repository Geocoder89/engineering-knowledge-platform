from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.repositories import decision as decision_repository
from app.repositories import (
    decision_alternative as decision_alternative_repository,
)
from app.schemas.decision import DecisionCreate, DecisionListResponse, DecisionResponse
from app.schemas.decision_alternative import (
    DecisionAlternativeCreate,
    DecisionAlternativeResponse,
    DecisionAlternativeUpdate,
)

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


# alternatives


@router.post(
    "/{decision_id}/alternatives",
    response_model=DecisionAlternativeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_decision_alternative(
    decision_id: UUID,
    alternative: DecisionAlternativeCreate,
    session: SessionDependency,
) -> DecisionAlternative:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    created_alternative = decision_alternative_repository.create_decision_alternative(
        session,
        decision_id=decision.id,
        title=alternative.title,
        description=alternative.description,
    )

    session.commit()

    return created_alternative


@router.get(
    "/{decision_id}/alternatives",
    response_model=list[DecisionAlternativeResponse],
)
def list_decision_alternatives(
    decision_id: UUID,
    session: SessionDependency,
) -> list[DecisionAlternative]:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    return decision_alternative_repository.list_decision_alternatives(
        session,
        decision_id=decision.id,
    )


@router.patch(
    "/{decision_id}/alternatives/{alternative_id}",
    response_model=DecisionAlternativeResponse,
)
def update_decision_alternative(
    decision_id: UUID,
    alternative_id: UUID,
    alternative_update: DecisionAlternativeUpdate,
    session: SessionDependency,
) -> DecisionAlternative:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    alternative = decision_alternative_repository.get_decision_alternative_by_id(
        session,
        decision_id=decision.id,
        alternative_id=alternative_id,
    )

    if alternative is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision alternative not found",
        )

    update_fields = alternative_update.model_dump(
        exclude_unset=True,
    )

    updated_alternative = decision_alternative_repository.update_decision_alternative(
        session,
        alternative=alternative,
        **update_fields,
    )

    session.commit()

    return updated_alternative


@router.delete(
    "/{decision_id}/alternatives/{alternative_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_decision_alternative(
    decision_id: UUID,
    alternative_id: UUID,
    session: SessionDependency,
) -> Response:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    alternative = decision_alternative_repository.get_decision_alternative_by_id(
        session,
        decision_id=decision.id,
        alternative_id=alternative_id,
    )

    if alternative is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision alternative not found",
        )

    decision_alternative_repository.delete_decision_alternative(
        session,
        alternative=alternative,
    )

    session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
