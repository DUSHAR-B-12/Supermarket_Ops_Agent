import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(autouse=True)
def mock_llm_for_tests():
    """Autouse fixture to ensure unit tests run deterministically with mock LLM client."""
    with patch("app.agent.runner.get_llm_client") as mock_get_llm:
        mock_client = MagicMock()
        mock_client.generate_completion.side_effect = lambda history, user_message, tool_results: (
            ("\n".join([f"Executed {tr.get('name')}" for tr in tool_results]), None)
            if tool_results
            else ("Processed request", None)
        )
        mock_get_llm.return_value = mock_client
        yield mock_client

@pytest.fixture(scope="function")
def db_session():
    """Provides an isolated in-memory SQLite database session for testing."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
