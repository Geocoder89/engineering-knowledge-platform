from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain.decision import (
    DecisionNotEditable,
    DecisionReviewRequirementsNotMet,
    DecisionStatus,
    InvalidDecisionStatusTransition,
    SelectedAlternativeNotPartOfDecision,
    validate_decision_is_editable,
)
from app.domain.decision_evidence import (
    DecisionEvidenceCitation,
)
from app.domain.document import DocumentStatus
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.repositories import decision as decision_repository
from app.repositories import (
    decision_alternative as decision_alternative_repository,
)
from app.repositories import (
    decision_audit as decision_audit_repository,
)
from app.repositories import (
    decision_evidence as decision_evidence_repository,
)
from app.schemas.decision import (
    DecisionCancellationCreate,
    DecisionCreate,
    DecisionListResponse,
    DecisionOutcomeCreate,
    DecisionResponse,
    DecisionReviewResponse,
)
from app.schemas.decision_alternative import (
    DecisionAlternativeCreate,
    DecisionAlternativeResponse,
    DecisionAlternativeUpdate,
)
from app.schemas.decision_audit import (
    DecisionAuditHistoryResponse,
)
from app.schemas.decision_evidence import (
    DecisionEvidenceCitationResponse,
    DecisionEvidenceCreate,
    DecisionEvidenceResponse,
)
from app.services import (
    decision_audit as decision_audit_service,
)
from app.services import decision_review as decision_review_service

router = APIRouter(
    prefix="/decisions",
    tags=["decisions"],
)

SessionDependency = Annotated[
    Session,
    Depends(get_session),
]


def require_editable_decision(
    decision: Decision,
) -> None:
    try:
        validate_decision_is_editable(
            DecisionStatus(decision.status),
        )
    except DecisionNotEditable as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


def build_decision_evidence_response(
    evidence: DecisionEvidenceCitation,
) -> DecisionEvidenceResponse:
    return DecisionEvidenceResponse(
        id=evidence.decision_evidence_id,
        decision_alternative_id=(evidence.decision_alternative_id),
        document_chunk_id=evidence.document_chunk_id,
        evidence_type=evidence.evidence_type,
        relevance_note=evidence.relevance_note,
        created_at=evidence.created_at,
        chunk_index=evidence.chunk_index,
        text=evidence.text,
        start_offset=evidence.start_offset,
        end_offset=evidence.end_offset,
        citation=DecisionEvidenceCitationResponse(
            document_id=evidence.document_id,
            document_version_id=(evidence.document_version_id),
            document_page_id=evidence.document_page_id,
            document_title=evidence.document_title,
            file_name=evidence.file_name,
            version_number=evidence.version_number,
            page_number=evidence.page_number,
        ),
    )


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

    decision_audit_service.record_decision_created(session, decision=created_decision)
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
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    require_editable_decision(decision)

    created_alternative = decision_alternative_repository.create_decision_alternative(
        session,
        decision_id=decision.id,
        title=alternative.title,
        description=alternative.description,
    )

    decision_audit_service.record_decision_alternative_added(
        session,
        alternative=created_alternative,
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
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    require_editable_decision(decision)

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

    previous_values = {
        field_name: getattr(
            alternative,
            field_name,
        )
        for field_name in update_fields
    }

    updated_alternative = decision_alternative_repository.update_decision_alternative(
        session,
        alternative=alternative,
        **update_fields,
    )

    new_values = {
        field_name: getattr(
            updated_alternative,
            field_name,
        )
        for field_name in update_fields
    }

    decision_audit_service.record_decision_alternative_updated(
        session,
        alternative=updated_alternative,
        previous_values=previous_values,
        new_values=new_values,
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
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    require_editable_decision(decision)

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

    removed_alternative_id = alternative.id
    removed_title = alternative.title
    removed_description = alternative.description
    removed_position = alternative.position

    decision_alternative_repository.delete_decision_alternative(
        session,
        alternative=alternative,
    )

    remaining_alternatives = decision_alternative_repository.list_decision_alternatives(
        session,
        decision_id=decision.id,
    )

    decision_audit_service.record_decision_alternative_removed(
        session,
        decision_id=decision.id,
        alternative_id=removed_alternative_id,
        title=removed_title,
        description=removed_description,
        position=removed_position,
        remaining_alternative_order=[
            remaining_alternative.id for remaining_alternative in remaining_alternatives
        ],
    )

    session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.post(
    ("/{decision_id}/alternatives/{alternative_id}/evidence"),
    response_model=DecisionEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_decision_evidence(
    decision_id: UUID,
    alternative_id: UUID,
    evidence: DecisionEvidenceCreate,
    session: SessionDependency,
) -> DecisionEvidenceResponse:
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    require_editable_decision(
        decision,
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

    document_status = decision_evidence_repository.get_document_chunk_source_status(
        session,
        document_chunk_id=evidence.document_chunk_id,
    )

    if document_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document chunk not found",
        )

    if document_status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Document chunk is not available for evidence"),
        )
    try:
        created_evidence = decision_evidence_repository.create_decision_evidence(
            session,
            decision_alternative_id=alternative.id,
            document_chunk_id=evidence.document_chunk_id,
            evidence_type=evidence.evidence_type,
            relevance_note=evidence.relevance_note,
        )

    except IntegrityError as error:
        session.rollback()

        diagnostics = getattr(
            error.orig,
            "diag",
            None,
        )
        constraint_name = getattr(
            diagnostics,
            "constraint_name",
            None,
        )

        if constraint_name != ("uq_decision_evidence_alternative_chunk"):
            raise

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Document chunk is already linked to this decision alternative"),
        ) from error

    citations = decision_evidence_repository.list_decision_evidence(
        session,
        decision_alternative_id=alternative.id,
    )
    created_citation = next(
        citation
        for citation in citations
        if citation.decision_evidence_id == created_evidence.id
    )
    decision_audit_service.record_decision_evidence_added(
        session,
        decision_id=decision.id,
        citation=created_citation,
    )

    session.commit()

    return build_decision_evidence_response(
        created_citation,
    )


@router.get(
    ("/{decision_id}/alternatives/{alternative_id}/evidence"),
    response_model=list[DecisionEvidenceResponse],
)
def list_decision_evidence(
    decision_id: UUID,
    alternative_id: UUID,
    session: SessionDependency,
) -> list[DecisionEvidenceResponse]:
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

    citations = decision_evidence_repository.list_decision_evidence(
        session,
        decision_alternative_id=alternative.id,
    )

    return [build_decision_evidence_response(citation) for citation in citations]


@router.delete(
    ("/{decision_id}/alternatives/{alternative_id}/evidence/{decision_evidence_id}"),
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_decision_evidence(
    decision_id: UUID,
    alternative_id: UUID,
    decision_evidence_id: UUID,
    session: SessionDependency,
) -> Response:
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    require_editable_decision(
        decision,
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

    evidence = decision_evidence_repository.get_decision_evidence_by_id(
        session,
        decision_alternative_id=alternative.id,
        decision_evidence_id=decision_evidence_id,
    )

    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision evidence not found",
        )

    citations = decision_evidence_repository.list_decision_evidence(
        session,
        decision_alternative_id=alternative.id,
    )
    removed_citation = next(
        citation
        for citation in citations
        if citation.decision_evidence_id == evidence.id
    )

    decision_evidence_repository.delete_decision_evidence(
        session,
        evidence=evidence,
    )

    decision_audit_service.record_decision_evidence_removed(
        session,
        decision_id=decision.id,
        citation=removed_citation,
    )

    session.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.post(
    "/{decision_id}/submit",
    response_model=DecisionReviewResponse,
)
def submit_decision_for_review(
    decision_id: UUID,
    session: SessionDependency,
) -> Decision:
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    try:
        submitted_decision = decision_review_service.submit_decision_for_review(
            session,
            decision=decision,
        )
    except (
        DecisionReviewRequirementsNotMet,
        InvalidDecisionStatusTransition,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    session.commit()

    return submitted_decision


@router.post(
    "/{decision_id}/decide",
    response_model=DecisionReviewResponse,
)
def decide_decision(
    decision_id: UUID,
    outcome: DecisionOutcomeCreate,
    session: SessionDependency,
) -> Decision:
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    try:
        decided_decision = decision_review_service.finalize_decision(
            session,
            decision=decision,
            selected_alternative_id=(outcome.selected_alternative_id),
            rationale=outcome.rationale,
        )
    except (
        InvalidDecisionStatusTransition,
        SelectedAlternativeNotPartOfDecision,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    session.commit()

    return decided_decision


@router.post(
    "/{decision_id}/cancel",
    response_model=DecisionReviewResponse,
)
def cancel_decision(
    decision_id: UUID,
    cancellation: DecisionCancellationCreate,
    session: SessionDependency,
) -> Decision:
    decision = decision_repository.get_decision_by_id_for_update(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    try:
        cancelled_decision = decision_review_service.cancel_decision(
            session,
            decision=decision,
            rationale=cancellation.rationale,
        )
    except InvalidDecisionStatusTransition as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    session.commit()

    return cancelled_decision


@router.get(
    "/{decision_id}/history",
    response_model=DecisionAuditHistoryResponse,
)
def get_decision_audit_history(
    decision_id: UUID,
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DecisionAuditHistoryResponse:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    events = decision_audit_repository.list_decision_audit_events(
        session,
        decision_id=decision.id,
        offset=offset,
        limit=limit,
    )
    total = decision_audit_repository.count_decision_audit_events(
        session,
        decision_id=decision.id,
    )

    return DecisionAuditHistoryResponse(
        decision_id=decision.id,
        items=events,
        total=total,
        offset=offset,
        limit=limit,
    )
