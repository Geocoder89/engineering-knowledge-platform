#!/usr/bin/env bash
# Run from the repository root against a disposable Compose project.
set -euo pipefail

docker compose exec -T api python - <<'PY'
import os
from urllib.request import urlopen

from app.storage.dependencies import get_document_storage

assert os.getuid() != 0, "API must not run as root"
with urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
    assert response.status == 200
get_document_storage().save(key="container-smoke/api.txt", content=b"api-write")
PY

docker compose exec -T worker python - <<'PY'
import os

from app.storage.dependencies import get_document_storage

assert os.getuid() != 0, "Worker must not run as root"
storage = get_document_storage()
assert storage.read(key="container-smoke/api.txt") == b"api-write"
storage.save(key="container-smoke/worker.txt", content=b"worker-write")
PY

docker compose exec -T api python -m pip check
docker compose exec -T api python -m alembic check

# Check the real worker process reached its loop and handles SIGTERM cleanly.
docker compose stop worker
docker compose logs worker | grep -q "Document processing worker started"
docker compose logs worker | grep -q "Document processing worker stopped"

# Recreate every container without applying migrations again or deleting volumes.
docker compose down
docker compose up -d --wait --wait-timeout 90 api worker
docker compose exec -T api python -m alembic check
docker compose exec -T api python - <<'PY'
from app.storage.dependencies import get_document_storage

storage = get_document_storage()
assert storage.read(key="container-smoke/api.txt") == b"api-write"
assert storage.read(key="container-smoke/worker.txt") == b"worker-write"
storage.delete(key="container-smoke/api.txt")
storage.delete(key="container-smoke/worker.txt")
PY

docker compose exec -T worker python - <<'PY'
from sqlalchemy import text

from app.database import engine

with engine.connect() as connection:
    assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 1
PY
