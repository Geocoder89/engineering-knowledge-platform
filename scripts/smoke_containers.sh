#!/usr/bin/env bash
# Run from the repository root against a disposable Compose project.
set -euo pipefail

docker compose exec -T api python - <<'PY'
import os
from urllib.request import urlopen
from uuid import UUID

from app.storage.dependencies import get_document_storage

assert os.getuid() != 0, "API must not run as root"
with urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
    assert response.status == 200
    assert UUID(response.headers["X-Request-ID"]).version == 4
with urlopen("http://127.0.0.1:8000/ready", timeout=5) as response:
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

# A live API must report unavailable while its database is stopped, then recover.
# Stop the worker first so this check does not interrupt a polling transaction.
docker compose stop db
docker compose exec -T api python - <<'PY'
import json
from urllib.error import HTTPError
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
    assert response.status == 200
try:
    urlopen("http://127.0.0.1:8000/ready", timeout=5)
except HTTPError as error:
    with error:
        assert error.code == 503
        assert json.load(error) == {"status": "unavailable"}
        assert error.headers["X-Request-ID"]
else:
    raise AssertionError("Readiness must fail with PostgreSQL stopped")
PY
docker compose up -d --wait --wait-timeout 90 db
docker compose exec -T api python - <<'PY'
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/ready", timeout=5) as response:
    assert response.status == 200
    assert json.load(response) == {"status": "ready"}
PY

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
