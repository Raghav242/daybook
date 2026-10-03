import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core import config
from app.infrastructure.database import Base, get_session
from app.main import app


@pytest.fixture
def raw_client(tmp_path, monkeypatch):
    # A dedicated empty PostgreSQL database may be supplied for integration runs.
    url = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db").replace("\\", "/")
    )
    monkeypatch.setattr(config, "DATABASE_URL", url)
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", False)
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
    if os.getenv("TEST_DATABASE_URL"):
        # This explicitly opted-in database must be disposable, as documented.
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
    engine.dispose()


def authenticate(client, username="test-user", password="test-passphrase-123", register=True):
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf
    response = client.post(
        "/api/auth/register" if register else "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code in (200, 201), response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]


@pytest.fixture
def client(raw_client):
    authenticate(raw_client)
    return raw_client
