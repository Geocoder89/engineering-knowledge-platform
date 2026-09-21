import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.repositories.document import (
    count_documents,
    create_document,
    get_document_by_id,
    get_document_by_id_for_processing,
    list_documents,
)


def test_repository_creates_and_retrieves_document_for_owner() -> None:
    with SessionLocal() as session:
        owner = User(
            email="owner@example.com",
            display_name="Document Owner",
        )
        session.add(owner)
        session.flush()

        created_document = create_document(
            session,
            owner_user_id=owner.id,
            title="Cooling system",
            file_name="cooling-design.pdf",
        )
        created_id = created_document.id

        session.expunge_all()

        retrieved_document = get_document_by_id(
            session,
            created_id,
            owner_user_id=owner.id,
        )

        assert retrieved_document is not None
        assert retrieved_document.id == created_id
        assert retrieved_document.owner_user_id == owner.id
        assert retrieved_document.title == "Cooling system"
        assert retrieved_document.file_name == "cooling-design.pdf"
        assert retrieved_document.status == "pending"

        session.rollback()


def test_repository_rejects_invalid_document_status() -> None:
    with SessionLocal() as session:
        owner = User(
            email="owner@example.com",
            display_name="Document Owner",
        )
        session.add(owner)
        session.flush()

        document = Document(
            owner_user_id=owner.id,
            title="Invalid status document",
            file_name="invalid-status.pdf",
            status="unknown",
        )
        session.add(document)

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_repository_does_not_retrieve_document_for_different_owner() -> None:
    with SessionLocal() as session:
        owner = User(
            email="owner@example.com",
            display_name="Document Owner",
        )
        other_user = User(
            email="other@example.com",
            display_name="Other User",
        )
        session.add_all(
            [
                owner,
                other_user,
            ],
        )
        session.flush()

        created_document = create_document(
            session,
            owner_user_id=owner.id,
            title="Cooling system",
            file_name="cooling-design.pdf",
        )

        session.expunge_all()

        retrieved_document = get_document_by_id(
            session,
            created_document.id,
            owner_user_id=other_user.id,
        )

        assert retrieved_document is None

        session.rollback()


def test_repository_lists_and_counts_only_documents_owned_by_user() -> None:
    with SessionLocal() as session:
        owner = User(
            email="owner@example.com",
            display_name="Document Owner",
        )
        other_user = User(
            email="other@example.com",
            display_name="Other User",
        )
        session.add_all(
            [
                owner,
                other_user,
            ],
        )
        session.flush()

        owner_first_document = create_document(
            session,
            owner_user_id=owner.id,
            title="Owner first document",
            file_name="owner-first.pdf",
        )
        create_document(
            session,
            owner_user_id=other_user.id,
            title="Other user document",
            file_name="other-user.pdf",
        )
        owner_second_document = create_document(
            session,
            owner_user_id=owner.id,
            title="Owner second document",
            file_name="owner-second.pdf",
        )

        owner_documents = list_documents(
            session,
            owner_user_id=owner.id,
            offset=0,
            limit=10,
        )
        owner_document_count = count_documents(
            session,
            owner_user_id=owner.id,
        )
        other_user_documents = list_documents(
            session,
            owner_user_id=other_user.id,
            offset=0,
            limit=10,
        )
        other_user_document_count = count_documents(
            session,
            owner_user_id=other_user.id,
        )

        first_owner_page = list_documents(
            session,
            owner_user_id=owner.id,
            offset=0,
            limit=1,
        )
        second_owner_page = list_documents(
            session,
            owner_user_id=owner.id,
            offset=1,
            limit=1,
        )

        assert {document.id for document in owner_documents} == {
            owner_first_document.id,
            owner_second_document.id,
        }
        assert owner_document_count == 2

        assert len(other_user_documents) == 1
        assert other_user_documents[0].owner_user_id == other_user.id
        assert other_user_document_count == 1

        assert len(first_owner_page) == 1
        assert len(second_owner_page) == 1
        assert {
            first_owner_page[0].id,
            second_owner_page[0].id,
        } == {
            owner_first_document.id,
            owner_second_document.id,
        }

        session.rollback()


def test_repository_retrieves_document_for_trusted_processing() -> None:
    with SessionLocal() as session:
        owner = User(
            email="owner@example.com",
            display_name="Document Owner",
        )
        session.add(owner)
        session.flush()

        created_document = create_document(
            session,
            owner_user_id=owner.id,
            title="Processing document",
            file_name="processing.pdf",
        )
        created_document_id = created_document.id

        session.expunge_all()

        retrieved_document = get_document_by_id_for_processing(
            session,
            created_document_id,
        )

        assert retrieved_document is not None
        assert retrieved_document.id == created_document_id
        assert retrieved_document.owner_user_id == owner.id

        session.rollback()
