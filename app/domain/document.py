from enum import StrEnum


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


ALLOWED_STATUS_TRANSITIONS: dict[
    DocumentStatus,
    frozenset[DocumentStatus],
] = {
    DocumentStatus.PENDING: frozenset(
        {
            DocumentStatus.PROCESSING,
        }
    ),
    DocumentStatus.PROCESSING: frozenset(
        {
            DocumentStatus.READY,
            DocumentStatus.FAILED,
        }
    ),
    DocumentStatus.FAILED: frozenset(
        {
            DocumentStatus.PENDING,
        }
    ),
    DocumentStatus.READY: frozenset(
        {
            DocumentStatus.ARCHIVED,
        }
    ),
    DocumentStatus.ARCHIVED: frozenset(),
}


class InvalidDocumentStatusTransition(ValueError):
    def __init__(
        self,
        current_status: DocumentStatus,
        target_status: DocumentStatus,
    ) -> None:
        super().__init__(
            f"Cannot transition document from "
            f"'{current_status.value}' to '{target_status.value}'"
        )


def validate_document_status_transition(
    current_status: DocumentStatus,
    target_status: DocumentStatus,
) -> None:
    allowed_targets = ALLOWED_STATUS_TRANSITIONS[current_status]

    if target_status not in allowed_targets:
        raise InvalidDocumentStatusTransition(
            current_status,
            target_status,
        )
