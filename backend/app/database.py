from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

# Database configuration
# Using PostgreSQL for production, SQLite for development/demo
# In Docker: postgres://postgres:postgres@postgres:5432/attendance
# For local development:
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


def get_db():
    """Dependency to get DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()