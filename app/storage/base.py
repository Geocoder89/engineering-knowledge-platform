from typing import Protocol


class DocumentStorage(Protocol):
    def save(self, *, key: str, content: bytes) -> None:
        """Persist content under the supplied storage key."""
        ...

    def delete(self, *, key: str) -> None:
        """
        Delete content associated with the supplied storage key.
        """
        ...

    def read(
        self,
        *,
        key: str,
    ) -> bytes:
        """
        Read and return content stored under the supplied key.
        """
