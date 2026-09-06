import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Resolve the database URL to an absolute path for stability across restarts
_resolved_url = settings.resolved_database_url

# Ensure data directory exists
_db_path = settings.resolved_database_path
_db_dir = os.path.dirname(_db_path)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

logger.info(f"DATABASE_PATH={_db_path}")
logger.info(f"DATABASE_URL_RESOLVED={_resolved_url}")

connect_args = {"check_same_thread": False} if _resolved_url.startswith("sqlite") else {}

engine = create_engine(
    _resolved_url,
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
    """Initialize database tables and seed sample Kirana data.
    Uses create_all which only creates MISSING tables — never drops or resets existing data.
    """
    logger.info(f"Initializing database at: {_db_path}")
    logger.info(f"Database file exists: {os.path.exists(_db_path)}")
    import app.db.models  # Register models with Base metadata
    from app.db.seed import seed_database
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured (create_all — existing data preserved).")

    with SessionLocal() as session:
        seed_database(session)

