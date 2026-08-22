from typing import Annotated

from fastapi import Depends

from app.config import settings
from app.storage.base import DocumentStorage
from app.storage.local import LocalDocumentStorage


def get_document_storage() -> DocumentStorage:
    return LocalDocumentStorage(root_path=settings.document_storage_path)


DocumentStorageDependency = Annotated[DocumentStorage, Depends(get_document_storage)]
