import pytest

from app.storage.local import LocalDocumentStorage


def test_local_document_storage_saves_content(tmp_path):
    storage = LocalDocumentStorage(root_path=tmp_path)
    storage_key = "document-id/version-id"
    content = b"%PDF-1.7\nCooling system design"

    storage.save(
        key=storage_key,
        content=content,
    )

    stored_file = tmp_path / storage_key

    assert stored_file.exists()
    assert stored_file.read_bytes() == content


def test_local_document_storage_rejects_path_traversal(tmp_path):
    storage = LocalDocumentStorage(root_path=tmp_path)

    with pytest.raises(
        ValueError,
        match="outside the storage directory",
    ):
        storage.save(
            key="../outside.pdf",
            content=b"unsafe content",
        )

    assert not (tmp_path.parent / "outside.pdf").exists()
