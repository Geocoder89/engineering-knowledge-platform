from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.decision_evidence import (
    DecisionEvidenceCitation,
)
from app.domain.document import DocumentStatus
from app.models.decision_evidence import DecisionEvidence
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion


def get_document_chunk_source_status(
    session: Session,
    *,
    document_chunk_id: UUID,
) -> DocumentStatus | None:
    statement = (
        select(
            Document.status,
        )
        .select_from(DocumentChunk)
        .join(
            DocumentPage,
            DocumentPage.id == DocumentChunk.document_page_id,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == DocumentPage.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            DocumentChunk.id == document_chunk_id,
        )
    )

    document_status = session.scalar(
        statement,
    )

    if document_status is None:
        return None

    return DocumentStatus(
        document_status,
    )


def create_decision_evidence(
    session: Session,
    *,
    decision_alternative_id: UUID,
    document_chunk_id: UUID,
    evidence_type: str,
    relevance_note: str | None,
) -> DecisionEvidence:
    evidence = DecisionEvidence(
        decision_alternative_id=decision_alternative_id,
        document_chunk_id=document_chunk_id,
        evidence_type=evidence_type,
        relevance_note=relevance_note,
    )

    session.add(evidence)
    session.flush()

    return evidence


def list_decision_evidence(
    session: Session,
    *,
    decision_alternative_id: UUID,
) -> list[DecisionEvidenceCitation]:
    statement = (
        select(
            DecisionEvidence.id.label(
                "decision_evidence_id",
            ),
            DecisionEvidence.decision_alternative_id,
            DecisionEvidence.evidence_type,
            DecisionEvidence.relevance_note,
            DecisionEvidence.created_at,
            DocumentChunk.id.label(
                "document_chunk_id",
            ),
            DocumentPage.id.label(
                "document_page_id",
            ),
            DocumentVersion.id.label(
                "document_version_id",
            ),
            Document.id.label(
                "document_id",
            ),
            Document.title.label(
                "document_title",
            ),
            DocumentVersion.file_name,
            DocumentVersion.version_number,
            DocumentPage.page_number,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            DocumentChunk.start_offset,
            DocumentChunk.end_offset,
        )
        .join(
            DocumentChunk,
            DocumentChunk.id == DecisionEvidence.document_chunk_id,
        )
        .join(
            DocumentPage,
            DocumentPage.id == DocumentChunk.document_page_id,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == DocumentPage.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            DecisionEvidence.decision_alternative_id == decision_alternative_id,
        )
        .order_by(
            DecisionEvidence.created_at,
            DecisionEvidence.id,
        )
    )

    rows = session.execute(
        statement,
    ).all()

    return [
        DecisionEvidenceCitation(
            decision_evidence_id=row.decision_evidence_id,
            decision_alternative_id=(row.decision_alternative_id),
            evidence_type=row.evidence_type,
            relevance_note=row.relevance_note,
            created_at=row.created_at,
            document_chunk_id=row.document_chunk_id,
            document_page_id=row.document_page_id,
            document_version_id=row.document_version_id,
            document_id=row.document_id,
            document_title=row.document_title,
            file_name=row.file_name,
            version_number=row.version_number,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            text=row.text,
            start_offset=row.start_offset,
            end_offset=row.end_offset,
        )
        for row in rows
    ]


def get_decision_evidence_by_id(
    session: Session,
    *,
    decision_alternative_id: UUID,
    decision_evidence_id: UUID,
) -> DecisionEvidence | None:
    statement = select(
        DecisionEvidence,
    ).where(
        DecisionEvidence.id == decision_evidence_id,
        DecisionEvidence.decision_alternative_id == decision_alternative_id,
    )

    return session.scalar(
        statement,
    )


def delete_decision_evidence(
    session: Session,
    *,
    evidence: DecisionEvidence,
) -> None:
    session.delete(
        evidence,
    )
    session.flush()
