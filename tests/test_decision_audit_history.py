from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.domain.decision_audit import DecisionAuditEventType
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.models.decision_audit_event import DecisionAuditEvent
from app.models.decision_evidence import DecisionEvidence
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.repositories import (
    decision_audit as decision_audit_repository,
)
from app.services import (
    decision_review as decision_review_service,
)


@dataclass(frozen=True, slots=True)
class AuditSourceGraph:
    document: Document
    document_version: DocumentVersion
    document_page: DocumentPage
    document_chunk: DocumentChunk


def create_audit_source_graph(
    session: Session,
) -> AuditSourceGraph:
    document = Document(
        title="Cooling system",
        file_name="cooling-design.pdf",
        status="ready",
    )
    session.add(document)
    session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_name="cooling-design.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum_sha256="a" * 64,
        storage_key=f"{document.id}/version-1",
    )
    session.add(document_version)
    session.flush()

    page_text = (
        "Reducing maximum operating pressure increases the available safety margin."
    )
    document_page = DocumentPage(
        document_version_id=document_version.id,
        page_number=4,
        text=page_text,
    )
    session.add(document_page)
    session.flush()

    document_chunk = DocumentChunk(
        document_page_id=document_page.id,
        chunk_index=0,
        text=page_text,
        start_offset=0,
        end_offset=len(page_text),
    )
    session.add(document_chunk)
    session.flush()

    return AuditSourceGraph(
        document=document,
        document_version=document_version,
        document_page=document_page,
        document_chunk=document_chunk,
    )


def test_database_persists_decision_audit_event(
    db_session: Session,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    event_data = {
        "title": decision.title,
        "question": decision.question,
        "status": decision.status,
    }
    event = DecisionAuditEvent(
        decision_id=decision.id,
        sequence_number=1,
        event_type="decision_created",
        event_data=event_data,
    )
    db_session.add(event)
    db_session.flush()

    assert event.id is not None
    assert event.decision_id == decision.id
    assert event.sequence_number == 1
    assert event.event_type == "decision_created"
    assert event.event_data == event_data
    assert event.created_at is not None


@pytest.mark.parametrize(
    "operation",
    [
        "update",
        "delete",
    ],
)
def test_database_rejects_decision_audit_event_mutation(
    db_session: Session,
    operation: str,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    event = DecisionAuditEvent(
        decision_id=decision.id,
        sequence_number=1,
        event_type="decision_created",
        event_data={
            "title": decision.title,
            "question": decision.question,
            "status": decision.status,
        },
    )
    db_session.add(event)
    db_session.flush()

    event_id = event.id

    # Preserve the original event outside the transaction that will fail.
    db_session.commit()

    if operation == "update":
        event.event_type = "decision_cancelled"
    else:
        db_session.delete(event)

    with pytest.raises(
        DBAPIError,
        match="decision audit events are immutable",
    ):
        db_session.flush()

    db_session.rollback()

    persisted_event = db_session.get(
        DecisionAuditEvent,
        event_id,
    )

    assert persisted_event is not None
    assert persisted_event.event_type == "decision_created"
    assert persisted_event.sequence_number == 1


@pytest.mark.parametrize(
    (
        "sequence_number",
        "event_type",
        "event_data",
    ),
    [
        (
            1,
            "decision_created",
            {"status": "draft"},
        ),
        (
            2,
            "unknown_event",
            {"status": "draft"},
        ),
        (
            0,
            "decision_created",
            {"status": "draft"},
        ),
        (
            2,
            "decision_created",
            ["audit payload must be an object"],
        ),
    ],
)
def test_database_rejects_invalid_decision_audit_event(
    db_session: Session,
    sequence_number: int,
    event_type: str,
    event_data: object,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    existing_event = DecisionAuditEvent(
        decision_id=decision.id,
        sequence_number=1,
        event_type="decision_created",
        event_data={
            "status": "draft",
        },
    )
    db_session.add(existing_event)
    db_session.flush()

    invalid_event = DecisionAuditEvent(
        decision_id=decision.id,
        sequence_number=sequence_number,
        event_type=event_type,
        event_data=event_data,
    )
    db_session.add(invalid_event)

    with pytest.raises(
        IntegrityError,
    ):
        db_session.flush()


def test_database_protects_decision_with_audit_history(
    db_session: Session,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    event = DecisionAuditEvent(
        decision_id=decision.id,
        sequence_number=1,
        event_type="decision_created",
        event_data={
            "status": "draft",
        },
    )
    db_session.add(event)
    db_session.flush()

    db_session.delete(decision)

    with pytest.raises(
        IntegrityError,
    ):
        db_session.flush()


def test_repository_appends_and_lists_decision_audit_events(
    db_session: Session,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    created_event_data = {
        "title": decision.title,
        "question": decision.question,
        "status": decision.status,
    }
    created_event = decision_audit_repository.append_decision_audit_event(
        db_session,
        decision_id=decision.id,
        event_type=DecisionAuditEventType.DECISION_CREATED,
        event_data=created_event_data,
    )

    submitted_event_data = {
        "previous_status": "draft",
        "new_status": "in_review",
    }
    submitted_event = decision_audit_repository.append_decision_audit_event(
        db_session,
        decision_id=decision.id,
        event_type=DecisionAuditEventType.DECISION_SUBMITTED,
        event_data=submitted_event_data,
    )

    events = decision_audit_repository.list_decision_audit_events(
        db_session,
        decision_id=decision.id,
    )

    assert created_event.sequence_number == 1
    assert submitted_event.sequence_number == 2
    assert [event.id for event in events] == [
        created_event.id,
        submitted_event.id,
    ]
    assert [event.event_type for event in events] == [
        "decision_created",
        "decision_submitted",
    ]
    assert events[0].event_data == created_event_data
    assert events[1].event_data == submitted_event_data


def test_creating_decision_records_audit_event(
    client,
    db_session: Session,
) -> None:
    payload = {
        "title": "Cooling pressure limit",
        "question": ("Should the maximum cooling-system pressure be reduced?"),
    }

    response = client.post(
        "/decisions",
        json=payload,
    )

    assert response.status_code == 201

    decision = response.json()
    decision_id = UUID(
        decision["id"],
    )

    events = decision_audit_repository.list_decision_audit_events(
        db_session,
        decision_id=decision_id,
    )

    assert len(events) == 1

    event = events[0]

    assert event.sequence_number == 1
    assert event.event_type == "decision_created"
    assert event.event_data == {
        "title": payload["title"],
        "question": payload["question"],
        "status": "draft",
    }


def test_records_decision_alternative_audit_history(
    client,
    db_session: Session,
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()
    original_title = "Reduce the pressure limit"
    updated_title = "Reduce the maximum operating pressure"
    description = "Lower the approved maximum pressure to improve the safety margin."

    create_response = client.post(
        f"/decisions/{decision['id']}/alternatives",
        json={
            "title": original_title,
            "description": description,
        },
    )

    assert create_response.status_code == 201

    alternative = create_response.json()

    update_response = client.patch(
        (f"/decisions/{decision['id']}/alternatives/{alternative['id']}"),
        json={
            "title": updated_title,
        },
    )

    assert update_response.status_code == 200

    delete_response = client.delete(
        (f"/decisions/{decision['id']}/alternatives/{alternative['id']}"),
    )

    assert delete_response.status_code == 204

    events = decision_audit_repository.list_decision_audit_events(
        db_session,
        decision_id=UUID(
            decision["id"],
        ),
    )

    assert [event.sequence_number for event in events] == [
        1,
        2,
        3,
        4,
    ]
    assert [event.event_type for event in events] == [
        "decision_created",
        "alternative_added",
        "alternative_updated",
        "alternative_removed",
    ]

    assert events[1].event_data == {
        "alternative_id": alternative["id"],
        "title": original_title,
        "description": description,
        "position": 0,
    }
    assert events[2].event_data == {
        "alternative_id": alternative["id"],
        "previous": {
            "title": original_title,
        },
        "new": {
            "title": updated_title,
        },
    }
    assert events[3].event_data == {
        "alternative_id": alternative["id"],
        "title": updated_title,
        "description": description,
        "position": 0,
        "remaining_alternative_order": [],
    }


def test_records_decision_evidence_audit_history(
    client,
    db_session: Session,
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()

    alternative_response = client.post(
        f"/decisions/{decision['id']}/alternatives",
        json={
            "title": "Reduce the pressure limit",
            "description": (
                "Lower the approved maximum pressure to improve the safety margin."
            ),
        },
    )

    assert alternative_response.status_code == 201

    alternative = alternative_response.json()
    source = create_audit_source_graph(
        db_session,
    )
    relevance_note = (
        "The source directly describes the safety benefit of this alternative."
    )
    evidence_url = (
        f"/decisions/{decision['id']}/alternatives/{alternative['id']}/evidence"
    )

    create_response = client.post(
        evidence_url,
        json={
            "document_chunk_id": str(
                source.document_chunk.id,
            ),
            "evidence_type": "supporting",
            "relevance_note": relevance_note,
        },
    )

    assert create_response.status_code == 201

    evidence = create_response.json()

    delete_response = client.delete(
        f"{evidence_url}/{evidence['id']}",
    )

    assert delete_response.status_code == 204

    events = decision_audit_repository.list_decision_audit_events(
        db_session,
        decision_id=UUID(
            decision["id"],
        ),
    )

    assert [event.event_type for event in events] == [
        "decision_created",
        "alternative_added",
        "evidence_added",
        "evidence_removed",
    ]

    expected_evidence_data = {
        "evidence_id": evidence["id"],
        "alternative_id": evidence["decision_alternative_id"],
        "document_chunk_id": evidence["document_chunk_id"],
        "evidence_type": evidence["evidence_type"],
        "relevance_note": relevance_note,
        "citation": {
            "document_id": evidence["citation"]["document_id"],
            "document_version_id": (evidence["citation"]["document_version_id"]),
            "document_page_id": evidence["citation"]["document_page_id"],
            "document_title": evidence["citation"]["document_title"],
            "file_name": evidence["citation"]["file_name"],
            "version_number": evidence["citation"]["version_number"],
            "page_number": evidence["citation"]["page_number"],
            "chunk_index": evidence["chunk_index"],
            "text": evidence["text"],
            "start_offset": evidence["start_offset"],
            "end_offset": evidence["end_offset"],
        },
    }

    assert events[2].event_data == expected_evidence_data
    assert events[3].event_data == expected_evidence_data


def test_service_records_submission_and_finalization_audit_history(
    db_session: Session,
    monkeypatch,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    alternatives = [
        DecisionAlternative(
            decision_id=decision.id,
            title="Keep the existing limit",
            description=("Retain the currently approved maximum operating pressure."),
            position=0,
        ),
        DecisionAlternative(
            decision_id=decision.id,
            title="Reduce the pressure limit",
            description=("Lower the maximum pressure to improve the safety margin."),
            position=1,
        ),
    ]
    db_session.add_all(
        alternatives,
    )
    db_session.flush()

    source = create_audit_source_graph(
        db_session,
    )
    evidence = DecisionEvidence(
        decision_alternative_id=alternatives[1].id,
        document_chunk_id=source.document_chunk.id,
        evidence_type="supporting",
        relevance_note=("The source directly supports the safer operating pressure."),
    )
    db_session.add(evidence)
    db_session.flush()

    submitted_at = datetime(
        2026,
        8,
        28,
        15,
        0,
        tzinfo=timezone.utc,
    )
    decided_at = datetime(
        2026,
        8,
        28,
        16,
        0,
        tzinfo=timezone.utc,
    )
    timestamps = iter(
        [
            submitted_at,
            decided_at,
        ]
    )

    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: next(timestamps),
    )

    submitted_decision = decision_review_service.submit_decision_for_review(
        db_session,
        decision=decision,
    )

    assert submitted_decision.status == "in_review"

    rationale = (
        "Reducing the pressure limit provides the strongest "
        "documented safety improvement."
    )
    finalized_decision = decision_review_service.finalize_decision(
        db_session,
        decision=decision,
        selected_alternative_id=alternatives[1].id,
        rationale=rationale,
    )

    assert finalized_decision.status == "decided"

    events = decision_audit_repository.list_decision_audit_events(
        db_session,
        decision_id=decision.id,
    )

    assert [event.sequence_number for event in events] == [
        1,
        2,
    ]
    assert [event.event_type for event in events] == [
        "decision_submitted",
        "decision_finalized",
    ]
    assert events[0].event_data == {
        "previous_status": "draft",
        "new_status": "in_review",
        "submitted_at": submitted_at.isoformat(),
    }
    assert events[1].event_data == {
        "previous_status": "in_review",
        "new_status": "decided",
        "selected_alternative_id": str(
            alternatives[1].id,
        ),
        "rationale": rationale,
        "decided_at": decided_at.isoformat(),
    }


def test_service_records_cancellation_audit_history(
    db_session: Session,
    monkeypatch,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    cancelled_at = datetime(
        2026,
        8,
        28,
        17,
        0,
        tzinfo=timezone.utc,
    )

    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: cancelled_at,
    )

    rationale = "The decision is no longer required because the project scope changed."
    cancelled_decision = decision_review_service.cancel_decision(
        db_session,
        decision=decision,
        rationale=rationale,
    )

    assert cancelled_decision.status == "cancelled"

    events = decision_audit_repository.list_decision_audit_events(
        db_session,
        decision_id=decision.id,
    )

    assert len(events) == 1
    assert events[0].sequence_number == 1
    assert events[0].event_type == "decision_cancelled"
    assert events[0].event_data == {
        "previous_status": "draft",
        "new_status": "cancelled",
        "rationale": rationale,
        "cancelled_at": cancelled_at.isoformat(),
    }


def test_gets_decision_audit_history_in_sequence_order(
    client,
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()

    alternative_response = client.post(
        f"/decisions/{decision['id']}/alternatives",
        json={
            "title": "Reduce the pressure limit",
            "description": (
                "Lower the approved maximum pressure to improve the safety margin."
            ),
        },
    )

    assert alternative_response.status_code == 201

    alternative = alternative_response.json()

    response = client.get(
        f"/decisions/{decision['id']}/history?offset=0&limit=10",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["decision_id"] == decision["id"]
    assert body["total"] == 2
    assert body["offset"] == 0
    assert body["limit"] == 10
    assert [item["sequence_number"] for item in body["items"]] == [
        1,
        2,
    ]
    assert [item["event_type"] for item in body["items"]] == [
        "decision_created",
        "alternative_added",
    ]
    assert body["items"][1]["event_data"] == {
        "alternative_id": alternative["id"],
        "title": alternative["title"],
        "description": alternative["description"],
        "position": alternative["position"],
    }

    page_response = client.get(
        f"/decisions/{decision['id']}/history?offset=1&limit=1",
    )

    assert page_response.status_code == 200

    page = page_response.json()

    assert page["total"] == 2
    assert page["offset"] == 1
    assert page["limit"] == 1
    assert len(page["items"]) == 1
    assert page["items"][0]["sequence_number"] == 2


def test_returns_404_for_unknown_decision_audit_history(
    client,
) -> None:
    response = client.get(
        f"/decisions/{uuid4()}/history",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }


@pytest.mark.parametrize(
    "query",
    [
        "offset=-1&limit=20",
        "offset=0&limit=0",
        "offset=0&limit=101",
    ],
)
def test_rejects_invalid_decision_audit_history_pagination(
    client,
    query: str,
) -> None:
    response = client.get(
        f"/decisions/{uuid4()}/history?{query}",
    )

    assert response.status_code == 422


def test_rejects_malformed_decision_audit_history_id(
    client,
) -> None:
    response = client.get(
        "/decisions/not-a-uuid/history",
    )

    assert response.status_code == 422
