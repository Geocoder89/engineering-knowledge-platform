from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.config import settings

# Use a fresh, short-lived connection so a probe does not wait for the request
# pool or retain a stale connection during database restart/recovery.
readiness_engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    connect_args={
        "connect_timeout": 2,
        "options": "-c statement_timeout=1000",
    },
)


def is_database_ready() -> bool:
    try:
        with readiness_engine.connect() as connection:
            return connection.scalar(text("SELECT 1")) == 1
    except SQLAlchemyError:
        # Driver errors can contain credentials, hostnames and SQL parameters.
        return False
