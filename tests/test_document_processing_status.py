from datetime import datetime
from uuid import UUID, uuid4

from tests.test_pdf_extraction import build_pdf_with_pages


def test_retrieves_document_processing_job_status(client) -> None:
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201
    document = create_response.json()

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                build_pdf_with_pages(("Cooling system requirements",)),
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201
    document_version = upload_response.json()

    response = client.get(
        (
            f"/documents/{document['id']}/versions/"
            f"{document_version['version_number']}/processing-job"
        )
    )

    assert response.status_code == 200

    processing_job = response.json()

    UUID(processing_job["id"])
    assert processing_job["document_version_id"] == document_version["id"]
    assert processing_job["status"] == "queued"
    assert processing_job["attempt_count"] == 0
    assert processing_job["error_message"] is None
    assert processing_job["started_at"] is None
    assert processing_job["completed_at"] is None

    created_at = datetime.fromisoformat(processing_job["created_at"])
    assert created_at.tzinfo is not None


def test_returns_404_for_unknown_document_processing_job(
    client,
) -> None:
    unknown_document_id = uuid4()

    response = client.get(
        (f"/documents/{unknown_document_id}/versions/1/processing-job")
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_returns_404_for_unknown_document_version_processing_job(
    client,
) -> None:
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201
    document = create_response.json()

    response = client.get((f"/documents/{document['id']}/versions/1/processing-job"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Document version not found"}
