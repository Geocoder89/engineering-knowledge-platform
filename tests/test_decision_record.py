from unittest.mock import Mock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.services import decision_record as decision_record_service


def create_record_source_chunk(
    session: Session,
) -> DocumentChunk:
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

    return document_chunk


def test_gets_assembled_draft_decision_record(
    client,
) -> None:
    create_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert create_response.status_code == 201

    created_decision = create_response.json()
    decision_id = created_decision["id"]

    response = client.get(
        f"/decisions/{decision_id}/record",
    )

    assert response.status_code == 200

    assert response.json() == {
        **created_decision,
        "selected_alternative_id": None,
        "rationale": None,
        "submitted_at": None,
        "decided_at": None,
        "cancelled_at": None,
        "superseded_at": None,
        "alternatives": [],
        "history": {
            "total": 1,
            "url": f"/decisions/{decision_id}/history",
        },
    }


def test_gets_complete_assembled_decision_record(
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
    alternatives_url = f"/decisions/{decision['id']}/alternatives"

    first_alternative_response = client.post(
        alternatives_url,
        json={
            "title": "Keep the existing pressure limit",
            "description": (
                "Retain the currently approved maximum operating pressure."
            ),
        },
    )
    second_alternative_response = client.post(
        alternatives_url,
        json={
            "title": "Reduce the pressure limit",
            "description": (
                "Lower the approved maximum pressure to improve the safety margin."
            ),
        },
    )

    assert first_alternative_response.status_code == 201
    assert second_alternative_response.status_code == 201

    first_alternative = first_alternative_response.json()
    second_alternative = second_alternative_response.json()
    document_chunk = create_record_source_chunk(
        db_session,
    )

    evidence_response = client.post(
        (f"{alternatives_url}/{second_alternative['id']}/evidence"),
        json={
            "document_chunk_id": str(document_chunk.id),
            "evidence_type": "supporting",
            "relevance_note": (
                "The source directly supports the safer operating pressure."
            ),
        },
    )

    assert evidence_response.status_code == 201

    evidence = evidence_response.json()

    submit_response = client.post(
        f"/decisions/{decision['id']}/submit",
    )

    assert submit_response.status_code == 200

    rationale = (
        "Reducing the pressure limit provides the strongest "
        "documented safety improvement."
    )
    decide_response = client.post(
        f"/decisions/{decision['id']}/decide",
        json={
            "selected_alternative_id": second_alternative["id"],
            "rationale": rationale,
        },
    )

    assert decide_response.status_code == 200

    response = client.get(
        f"/decisions/{decision['id']}/record",
    )

    assert response.status_code == 200

    record = response.json()

    assert record["id"] == decision["id"]
    assert record["status"] == "decided"
    assert record["selected_alternative_id"] == second_alternative["id"]
    assert record["rationale"] == rationale
    assert record["submitted_at"] is not None
    assert record["decided_at"] is not None
    assert record["cancelled_at"] is None
    assert record["superseded_at"] is None

    assert record["alternatives"] == [
        {
            **first_alternative,
            "evidence": [],
        },
        {
            **second_alternative,
            "evidence": [
                evidence,
            ],
        },
    ]
    assert record["history"] == {
        "total": 6,
        "url": f"/decisions/{decision['id']}/history",
    }


def test_service_assembles_record_with_fixed_repository_queries(
    monkeypatch,
) -> None:
    session = Mock(
        spec=Session,
    )
    decision = Decision(
        id=uuid4(),
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
        status="decided",
    )
    alternatives = [
        DecisionAlternative(
            id=uuid4(),
            decision_id=decision.id,
            title="Keep the existing pressure limit",
            description=("Retain the currently approved maximum operating pressure."),
            position=0,
        ),
        DecisionAlternative(
            id=uuid4(),
            decision_id=decision.id,
            title="Reduce the pressure limit",
            description=(
                "Lower the approved maximum pressure to improve the safety margin."
            ),
            position=1,
        ),
    ]
    citation = Mock()
    citation.decision_alternative_id = alternatives[1].id

    get_decision = Mock(
        return_value=decision,
    )
    list_alternatives = Mock(
        return_value=alternatives,
    )
    list_evidence = Mock(
        return_value=[
            citation,
        ],
    )
    count_history = Mock(
        return_value=6,
    )

    monkeypatch.setattr(
        decision_record_service.decision_repository,
        "get_decision_by_id",
        get_decision,
    )
    monkeypatch.setattr(
        decision_record_service.decision_alternative_repository,
        "list_decision_alternatives",
        list_alternatives,
    )
    monkeypatch.setattr(
        decision_record_service.decision_evidence_repository,
        "list_decision_evidence_for_decision",
        list_evidence,
    )
    monkeypatch.setattr(
        decision_record_service.decision_audit_repository,
        "count_decision_audit_events",
        count_history,
    )

    record = decision_record_service.get_decision_record(
        session,
        decision_id=decision.id,
    )

    assert record is not None
    assert record.decision is decision
    assert record.alternatives == alternatives
    assert record.evidence_by_alternative_id == {
        alternatives[0].id: [],
        alternatives[1].id: [
            citation,
        ],
    }
    assert record.history_total == 6

    get_decision.assert_called_once_with(
        session,
        decision.id,
    )
    list_alternatives.assert_called_once_with(
        session,
        decision_id=decision.id,
    )
    list_evidence.assert_called_once_with(
        session,
        decision_id=decision.id,
    )
    count_history.assert_called_once_with(
        session,
        decision_id=decision.id,
    )


def test_returns_404_for_unknown_decision_record(
    client,
) -> None:
    unknown_id = uuid4()

    response = client.get(
        f"/decisions/{unknown_id}/record",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }


def test_rejects_malformed_decision_record_id(
    client,
) -> None:
    response = client.get(
        "/decisions/not-a-valid-uuid/record",
    )

    assert response.status_code == 422
