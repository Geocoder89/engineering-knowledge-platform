from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document_version import DocumentVersion


def get_next_version_number(session: Session, *, document_id: UUID) -> int:
    statement = select(
        func.coalesce(
            func.max(DocumentVersion.version_number),
            0,
        )
        + 1
    ).where(DocumentVersion.document_id == document_id)

    return int(session.scalar(statement) or 1)


def create_document_version(
    session: Session,
    *,
    version_id: UUID,
    document_id: UUID,
    version_number: int,
    file_name: str,
    content_type: str,
    size_bytes: int,
    checksum_sha256: str,
    storage_key: str,
) -> DocumentVersion:
    document_version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_number=version_number,
        file_name=file_name,
        content_type=content_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum_sha256,
        storage_key=storage_key,
    )
    session.add(document_version)
    session.flush()

    return document_version


def list_document_versions(
    session: Session, document_id: UUID, offset: int, limit: int
) -> list[DocumentVersion]:
    statement = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(session.scalars(statement).all())


def count_document_versions(
    session: Session,
    *,
    document_id: UUID,
) -> int:
    statement = (
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
    )

    return session.scalar(statement) or 0


def get_document_version_by_number(
    session: Session,
    *,
    document_id: UUID,
    version_number: int,
) -> DocumentVersion | None:
    statement = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.version_number == version_number,
    )

    return session.scalar(statement)


def get_document_version_by_checksum(
    session: Session, *, document_id: UUID, checksum_sha256: str
) -> DocumentVersion | None:
    statement = select(DocumentVersion).where(
        DocumentVersion.document_id == document_id,
        DocumentVersion.checksum_sha256 == checksum_sha256,
    )
    return session.scalar(statement)
