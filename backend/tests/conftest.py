import os
import sys
import shutil
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend root is on Python sys.path
backend_root = Path(__file__).parent.parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.config import settings
from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def temp_test_env():
    """Sets up a temporary storage directory and SQLite database for testing."""
    test_dir = tempfile.mkdtemp(prefix="repopilot_test_")
    test_db_path = Path(test_dir) / "test_repopilot.db"
    test_storage = Path(test_dir) / "storage"

    # Override settings
    settings.DATABASE_URL = f"sqlite:///{test_db_path}"
    settings.STORAGE_DIR = str(test_storage)
    settings.LLM_PROVIDER = "fake"
    settings.WORKER_BACKEND = "fake"

    # Initialize DB engine
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    yield {
        "test_dir": test_dir,
        "engine": engine,
        "session_local": TestingSessionLocal,
    }

    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def db_session(temp_test_env):
    """Provides a transactional database session for unit tests."""
    session = temp_test_env["session_local"]()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(temp_test_env, monkeypatch):
    import app.services.executor as executor

    # Make background jobs use the same test database as the API.
    monkeypatch.setattr(
        executor,
        "SessionLocal",
        temp_test_env["session_local"],
    )

    def override_get_db():
        session = temp_test_env["session_local"]()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()