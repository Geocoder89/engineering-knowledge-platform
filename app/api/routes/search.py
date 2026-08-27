from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import EmbeddingProviderDependency
from app.database import get_session
from app.embeddings.base import EmbeddingProviderError, InvalidEmbeddingResponseError
from app.schemas.document_search import (
    DocumentSearchCitationResponse,
    DocumentSearchItemResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
)
from app.services import document_search as document_search_service

router = APIRouter(
    prefix="/search",
    tags=["search"],
)

SessionDependency = Annotated[
    Session,
    Depends(get_session),
]


@router.post(
    "",
    response_model=DocumentSearchResponse,
)
def search_documents_endpoint(
    search_request: DocumentSearchRequest,
    session: SessionDependency,
    embedding_provider: EmbeddingProviderDependency,
) -> DocumentSearchResponse:
    try:
        matches = document_search_service.search_documents(
            session,
            embedding_provider=embedding_provider,
            query=search_request.query,
            limit=search_request.limit,
        )

    except EmbeddingProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document search is temporarily unavailable",
        ) from error

    except InvalidEmbeddingResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Embedding provider returned an invalid response",
        ) from error

    items = [
        DocumentSearchItemResponse(
            document_chunk_id=match.document_chunk_id,
            chunk_index=match.chunk_index,
            text=match.text,
            start_offset=match.start_offset,
            end_offset=match.end_offset,
            similarity_score=1.0 - match.cosine_distance,
            citation=DocumentSearchCitationResponse(
                document_id=match.document_id,
                document_version_id=match.document_version_id,
                document_page_id=match.document_page_id,
                document_title=match.document_title,
                file_name=match.file_name,
                version_number=match.version_number,
                page_number=match.page_number,
            ),
        )
        for match in matches
    ]

    return DocumentSearchResponse(
        query=search_request.query,
        limit=search_request.limit,
        items=items,
    )
