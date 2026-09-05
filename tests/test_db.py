from sqlalchemy import text
from app.db.session import init_db, engine

def test_db_initialization():
    init_db()
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar() == 1
