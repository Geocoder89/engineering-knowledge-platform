from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.document_version import (
    DocumentContentIntegrityError,
    DuplicateDocumentVersionError,
    validate_document_file,
)
from app.models.document_version import DocumentVersion
from app.repositories import document_version as document_version_repository
from app.storage.base import DocumentStorage

DUPLICATE_DOCUMENT_VERSION_CONSTRAINT = (
    "uq_document_versions_document_id_checksum_sha256"
)


def is_duplicate_document_version_error(
    error: IntegrityError,
) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)

    return constraint_name == DUPLICATE_DOCUMENT_VERSION_CONSTRAINT


def upload_document_version(
    session: Session,
    storage: DocumentStorage,
    *,
    document_id: UUID,
    file_name: str,
    content_type: str,
    content: bytes,
) -> DocumentVersion:

    validate_document_file(content_type=content_type, content=content)
    checksum_sha256 = sha256(content).hexdigest()

    existing_version = document_version_repository.get_document_version_by_checksum(
        session, document_id=document_id, checksum_sha256=checksum_sha256
    )

    if existing_version is not None:
        raise DuplicateDocumentVersionError()
    version_id = uuid4()
    version_number = document_version_repository.get_next_version_number(
        session, document_id=document_id
    )

    storage_key = f"{document_id}/{version_id}"

    storage.save(
        key=storage_key,
        content=content,
    )

    try:
        return document_version_repository.create_document_version(
            session,
            version_id=version_id,
            document_id=document_id,
            version_number=version_number,
            file_name=file_name,
            content_type=content_type,
            size_bytes=len(content),
            checksum_sha256=sha256(content).hexdigest(),
            storage_key=storage_key,
        )
    except IntegrityError as error:
        storage.delete(key=storage_key)

        if is_duplicate_document_version_error(error):
            raise DuplicateDocumentVersionError() from error
        raise
    except Exception:
        storage.delete(key=storage_key)
        raise


def read_document_version_content(
    storage: DocumentStorage,
    *,
    document_version: DocumentVersion,
) -> bytes:
    content = storage.read(
        key=document_version.storage_key,
    )
    actual_checksum = sha256(content).hexdigest()

    if actual_checksum != document_version.checksum_sha256:
        raise DocumentContentIntegrityError()

    return content
