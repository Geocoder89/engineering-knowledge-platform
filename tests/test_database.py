from sqlalchemy import text

from app.database import SessionLocal, engine


def test_database_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


def test_database_session():
    with SessionLocal() as session:
        result = session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
