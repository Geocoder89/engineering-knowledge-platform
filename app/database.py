from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.config import settings


# Database connection management.
engine = create_engine(
  settings.database_url,
  pool_pre_ping=True
)
# Sessions creation to track ORM objects and transactions

SessionLocal = sessionmaker(
  bind= engine,
  autoflush=False,
  expire_on_commit=False,
)

def get_session()-> Generator[Session, None,None]:
  with SessionLocal() as session:
    yield session