from pathlib import Path


class LocalDocumentStorage:
    def __init__(self, *, root_path: Path) -> None:
        self.root_path = root_path.resolve()

    def save(self, *, key: str, content: bytes) -> None:
        destination = self._resolve_destination(key)

        destination.parent.mkdir(parents=True, exist_ok=True)

        destination.write_bytes(content)

    def delete(self, *, key: str) -> None:
        destination = self._resolve_destination(key)
        destination.unlink(missing_ok=True)

    def _resolve_destination(self, key: str) -> Path:
        destination = (self.root_path / key).resolve()
        if self.root_path not in destination.parents:
            raise ValueError("Storage key resolves outside the storage directory")

        return destination
