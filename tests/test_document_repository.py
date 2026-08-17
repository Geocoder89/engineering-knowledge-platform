from app.database import SessionLocal
from app.repositories.document import (
    create_document,
    get_document_by_id,
)


def test_repository_creates_and_retrieves_document():
    with SessionLocal() as session:
        created_document = create_document(
            session,
            title="Cooling system",
            file_name="cooling-design.pdf",
        )
        created_id = created_document.id

        session.expunge_all()

        retrieved_document = get_document_by_id(
            session,
            created_id,
        )

        assert retrieved_document is not None
        assert retrieved_document.id == created_id
        assert retrieved_document.title == "Cooling system"
        assert retrieved_document.file_name == "cooling-design.pdf"
        assert retrieved_document.status == "pending"

        session.rollback()
