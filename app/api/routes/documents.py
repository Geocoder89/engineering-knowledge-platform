from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.domain.document import DocumentStatus, InvalidDocumentStatusTransition
from app.domain.document_processing_job import (
    ProcessingJobNotRetryable,
    ProcessingJobRetryLimitExceeded,
)
from app.domain.document_version import (
    DocumentContentIntegrityError,
    DocumentFileTooLargeError,
    DuplicateDocumentVersionError,
    EmptyDocumentFileError,
    InvalidPdfContentError,
    UnsupportedDocumentFileTypeError,
)
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.document_version import DocumentVersion
from app.repositories import document as document_repository
from app.repositories import (
    document_processing_job as processing_job_repository,
)
from app.repositories import document_version as document_version_repository
from app.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusUpdate,
    DocumentUpdate,
)
from app.schemas.document_processing_job import DocumentProcessingJobResponse
from app.schemas.document_version import (
    DocumentVersionListResponse,
    DocumentVersionResponse,
)
from app.services import document as document_service
from app.services import (
    document_processing as document_processing_service,
)
from app.services import document_version as document_version_service
from app.storage.dependencies import DocumentStorageDependency

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


@router.get("/{document_id}/versions", response_model=DocumentVersionListResponse)
def list_document_versions(
    document_id: UUID,
    session: SessionDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentVersionListResponse:
    document = document_repository.get_document_by_id(session, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    versions = document_version_repository.list_document_versions(
        session, document_id=document.id, offset=offset, limit=limit
    )
    total = document_version_repository.count_document_versions(
        session,
        document_id=document.id,
    )

    return DocumentVersionListResponse(
        items=versions, total=total, offset=offset, limit=limit
    )


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document_version(
    document_id: UUID,
    file: Annotated[UploadFile, File()],
    session: SessionDependency,
    storage: DocumentStorageDependency,
) -> DocumentVersion:
    document = document_repository.get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    try:
        content = document_version_service.read_document_file(
            file.file, max_size_bytes=settings.document_max_upload_size_bytes
        )
        uploaded_version = document_version_service.upload_document_version(
            session,
            storage,
            document_id=document.id,
            file_name=file.filename or document.file_name,
            content_type=file.content_type or "application/octet_stream",
            content=content,
        )
    except DocumentFileTooLargeError as error:
        raise HTTPException(
            status_code=413,
            detail=str(error),
        ) from error

    except EmptyDocumentFileError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error

    except DuplicateDocumentVersionError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    except (UnsupportedDocumentFileTypeError, InvalidPdfContentError) as error:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(error),
        ) from error

    try:
        session.commit()
    except Exception:
        session.rollback()
        storage.delete(key=uploaded_version.storage_key)
        raise

    return uploaded_version


@router.get(
    "/{document_id}/versions/{version_number}", response_model=DocumentVersionResponse
)
def get_document_version(
    document_id: UUID,
    version_number: Annotated[int, Path(ge=1)],
    session: SessionDependency,
) -> DocumentVersion:
    document = document_repository.get_document_by_id(session, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    document_version = document_version_repository.get_document_version_by_number(
        session, document_id=document.id, version_number=version_number
    )

    if document_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        )

    return document_version


@router.post(
    "/{document_id}/versions/{version_number}/retry",
    response_model=DocumentResponse,
)
def retry_document_version_processing(
    document_id: UUID,
    version_number: Annotated[int, Path(ge=1)],
    session: SessionDependency,
) -> Document:
    document = document_repository.get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document_version = document_version_repository.get_document_version_by_number(
        session,
        document_id=document.id,
        version_number=version_number,
    )

    if document_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found",
        )

    processing_job = processing_job_repository.get_processing_job_by_document_version(
        session,
        document_version_id=document_version.id,
    )

    if processing_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document processing job not found",
        )

    try:
        document_processing_service.retry_document_processing_job(
            session,
            document=document,
            processing_job=processing_job,
        )
        session.commit()
    except (
        InvalidDocumentStatusTransition,
        ProcessingJobRetryLimitExceeded,
        ProcessingJobNotRetryable,
    ) as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return document


@router.get(
    "/{document_id}/versions/{version_number}/processing-job",
    response_model=DocumentProcessingJobResponse,
)
def get_document_version_processing_job(
    document_id: UUID,
    version_number: Annotated[int, Path(ge=1)],
    session: SessionDependency,
) -> DocumentProcessingJob:
    document = document_repository.get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document_version = document_version_repository.get_document_version_by_number(
        session,
        document_id=document.id,
        version_number=version_number,
    )

    if document_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found",
        )

    processing_job = processing_job_repository.get_processing_job_by_document_version(
        session,
        document_version_id=document_version.id,
    )

    if processing_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document processing job not found",
        )

    return processing_job


@router.get(
    "/{document_id}/versions/{version_number}/content",
    response_class=Response,
)
def download_document_version_content(
    document_id: UUID,
    version_number: Annotated[int, Path(ge=1)],
    session: SessionDependency,
    storage: DocumentStorageDependency,
) -> Response:
    document = document_repository.get_document_by_id(
        session,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document_version = document_version_repository.get_document_version_by_number(
        session,
        document_id=document.id,
        version_number=version_number,
    )

    if document_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found",
        )

    try:
        content = document_version_service.read_document_version_content(
            storage, document_version=document_version
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document content not found",
        ) from error
    except DocumentContentIntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    encoded_file_name = quote(
        document_version.file_name,
        safe="",
    )

    return Response(
        content=content,
        media_type=document_version.content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{encoded_file_name}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
