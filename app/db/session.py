import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config.settings import settings

logger = logging.getLogger(__name__)


# Ensure data directory exists if SQLite file path is used
if settings.DATABASE_URL.startswith("sqlite:///"):
    relative_db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(os.path.abspath(relative_db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables and seed sample Kirana data."""
    logger.info(f"Initializing database using URL: {settings.DATABASE_URL}")
    import app.db.models  # Register models with Base metadata
    from app.db.seed import seed_database
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized.")

    with SessionLocal() as session:
        seed_database(session)

