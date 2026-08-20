from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain.document import DocumentStatus, InvalidDocumentStatusTransition
from app.models.document import Document
from app.repositories import document as document_repository
from app.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusUpdate,
    DocumentUpdate,
)
from app.services import document as document_service

router = APIRouter(prefix="/documents", tags=["documents"])

# temporary dict store to store documents
# document_store: dict[UUID, DocumentResponse] = {}

SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(document: DocumentCreate, session: SessionDependency) -> Document:
    created_document = document_repository.create_document(
        session, title=document.title, file_name=document.file_name
    )
    session.commit()
    return created_document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    document_status: Annotated[
        DocumentStatus | None,
        Query(alias="status"),
    ] = None,
) -> DocumentListResponse:
    documents = document_repository.list_documents(
        session, offset=offset, limit=limit, status=document_status
    )
    total = document_repository.count_documents(session, status=document_status)
    return DocumentListResponse(
        items=documents, total=total, offset=offset, limit=limit
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, session: SessionDependency) -> Document:
    document = document_repository.get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    return document


@router.patch("/{document_id}/status", response_model=DocumentResponse)
def transition_document_status(
    document_id: UUID,
    status_update: DocumentStatusUpdate,
    session: SessionDependency,
) -> Document:
    document = document_repository.get_document_by_id(session, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    try:
        updated_document = document_service.transition_document_status(
            session, document=document, target_status=status_update.status
        )
    except InvalidDocumentStatusTransition as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    session.commit()
    return updated_document


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document_metadata(
    document_id: UUID,
    document_update: DocumentUpdate,
    session: SessionDependency,
) -> Document:
    document = document_repository.get_document_by_id(session, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    update_fields = document_update.model_dump(exclude_unset=True)

    updated_document = document_repository.update_document_metadata(
        session,
        document=document,
        **update_fields,
    )

    session.commit()

    return updated_document
