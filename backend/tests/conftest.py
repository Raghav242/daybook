import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import config
from app.infrastructure.database import get_session
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # A dedicated empty PostgreSQL database may be supplied for integration runs.
    url = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db").replace("\\", "/")
    )
    monkeypatch.setattr(config, "DATABASE_URL", url)
    migration = Config("alembic.ini")
    command.upgrade(migration, "head")
    engine = create_engine(url)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    if os.getenv("TEST_DATABASE_URL"):
        command.downgrade(migration, "base")
