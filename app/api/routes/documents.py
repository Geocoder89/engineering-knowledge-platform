from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.document import Document
from app.repositories import document as document_repository
from app.schemas.document import DocumentCreate, DocumentListResponse, DocumentResponse

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
) -> DocumentListResponse:
    documents = document_repository.list_documents(session, offset=offset, limit=limit)
    total = document_repository.count_documents(session)
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
