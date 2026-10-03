from datetime import timedelta
from uuid import UUID

import pytest
from conftest import authenticate
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import config
from app.infrastructure.database import get_session
from app.main import app
from app.modules.auth.models import AuthSession, User
from app.modules.auth.service import digest, hasher, now_utc
from app.modules.settings.models import Settings
from app.modules.tasks.models import Task


def session_for_test():
    return app.dependency_overrides[get_session]()


def test_registration_normalizes_and_hashes_password(raw_client):
    user = authenticate(raw_client, "Alice")
    assert raw_client.get("/auth/me").json()["user"] == user
    dependency = session_for_test()
    session = next(dependency)
    stored = session.get(User, UUID(user["id"]))
    assert stored.normalized_username == "alice"
    assert stored.password_hash.startswith("$argon2id$")
    assert hasher.verify(stored.password_hash, "test-passphrase-123")
    token = raw_client.cookies[config.SESSION_COOKIE_NAME]
    assert session.get(AuthSession, digest(token)) is not None
    assert session.get(AuthSession, token) is None
    assert session.scalar(select(Settings).where(Settings.user_id == stored.id)) is not None
    dependency.close()
    csrf = raw_client.get("/api/auth/csrf").json()["csrf_token"]
    duplicate = raw_client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": csrf},
        json={"username": "aLiCe", "password": "another-passphrase-123"},
    )
    assert duplicate.status_code == 409


def test_registration_accepts_five_characters_but_rejects_four(raw_client):
    csrf = raw_client.get("/api/auth/csrf").json()["csrf_token"]
    raw_client.headers["X-CSRF-Token"] = csrf
    response = raw_client.post(
        "/api/auth/register", json={"username": "short-pass", "password": "abcd"}
    )
    assert response.status_code == 422
    user = authenticate(raw_client, "short-pass", "abcde")
    assert authenticate(raw_client, "SHORT-PASS", "abcde", register=False) == user


def test_login_rotates_and_logout_revokes_sessions(raw_client):
    user = authenticate(raw_client, "Alice")
    old = raw_client.cookies[config.SESSION_COOKIE_NAME]
    assert authenticate(raw_client, "ALICE", register=False) == user
    new = raw_client.cookies[config.SESSION_COOKIE_NAME]
    assert new != old
    with TestClient(app) as attacker:
        attacker.cookies.set(config.SESSION_COOKIE_NAME, old)
        assert attacker.get("/api/auth/me").status_code == 401
    assert raw_client.post("/api/auth/logout").status_code == 204
    assert config.SESSION_COOKIE_NAME not in raw_client.cookies
    raw_client.cookies.set(config.SESSION_COOKIE_NAME, new)
    assert raw_client.get("/api/auth/me").status_code == 401


def test_invalid_login_is_generic_and_does_not_echo_password(raw_client):
    authenticate(raw_client, "Alice")
    errors = []
    for username in ["Alice", "unknown-user"]:
        response = raw_client.post(
            "/api/auth/login", json={"username": username, "password": "wrong-secret-value"}
        )
        assert response.status_code == 401
        assert "wrong-secret-value" not in response.text
        errors.append(response.json())
    assert errors[0] == errors[1]


@pytest.mark.parametrize(
    "path", ["tasks", "calendar", "groceries", "bills", "settings", "dashboard"]
)
def test_personal_endpoints_require_authentication(raw_client, path):
    assert raw_client.get("/api/" + path).status_code == 401


def test_expired_and_forged_sessions_are_rejected(raw_client):
    authenticate(raw_client)
    dependency = session_for_test()
    session = next(dependency)
    token_hash = digest(raw_client.cookies[config.SESSION_COOKIE_NAME])
    stored = session.get(AuthSession, token_hash)
    stored.expires_at = now_utc() - timedelta(seconds=1)
    session.commit()
    dependency.close()
    assert raw_client.get("/api/dashboard").status_code == 401
    assert raw_client.post("/api/tasks", json={"title": "No"}).status_code == 401
    raw_client.cookies.set(config.SESSION_COOKIE_NAME, "forged")
    assert raw_client.get("/api/auth/me").status_code == 401


def test_csrf_protects_login_registration_and_authenticated_writes(raw_client):
    data = {"username": "Alice", "password": "test-passphrase-123"}
    for path in ["register", "login"]:
        assert raw_client.post("/api/auth/" + path, json=data).status_code == 403
    authenticate(raw_client, "Alice")
    assert (
        raw_client.post(
            "/api/tasks", json={"title": "No"}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert raw_client.put("/api/settings", json={}, headers={"X-CSRF-Token": ""}).status_code == 403
    assert raw_client.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert (
        raw_client.post(
            "/api/tasks", json={"title": "No"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert raw_client.get("/api/tasks").json()["total"] == 0


def test_login_limit_is_database_backed_and_shared(raw_client, monkeypatch):
    authenticate(raw_client, "Alice")
    monkeypatch.setattr(config, "AUTH_RATE_LIMIT", 2)
    for _ in range(2):
        assert (
            raw_client.post(
                "/api/auth/login", json={"username": "Alice", "password": "wrong"}
            ).status_code
            == 401
        )
    with TestClient(app) as another_process:
        csrf = another_process.get("/api/auth/csrf").json()["csrf_token"]
        response = another_process.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "Alice", "password": "test-passphrase-123"},
        )
        assert response.status_code == 429


def test_cookie_flags_and_secret_validation(raw_client, monkeypatch):
    response = raw_client.get("/api/auth/csrf")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", True)
    with TestClient(app, base_url="https://testserver") as https_client:
        cookie = https_client.get("/api/auth/csrf").headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie
        user = authenticate(https_client, "secure-user")
        assert https_client.get("/api/auth/me").json()["user"] == user


def test_database_rejects_missing_or_nonexistent_owners(raw_client):
    authenticate(raw_client)
    dependency = session_for_test()
    session = next(dependency)
    for owner in [None, UUID("11111111-1111-1111-1111-111111111111")]:
        session.add(Task(title="Invalid owner", user_id=owner))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    dependency.close()


RECORDS = [
    ("tasks", {"title": "Alice private task", "due_date": "2000-01-01"}),
    (
        "calendar",
        {
            "title": "Alice private event",
            "start": "2099-01-01T12:00:00Z",
            "end": "2099-01-01T13:00:00Z",
        },
    ),
    ("groceries", {"name": "Alice private groceries", "quantity": "2"}),
    ("bills", {"name": "Alice private bill", "amount": "23.50", "due_date": "2000-01-01"}),
]


@pytest.mark.parametrize("module,data", RECORDS)
def test_database_backed_ownership_for_every_crud_operation(raw_client, module, data):
    alice = authenticate(raw_client, "Alice")
    response = raw_client.post("/api/" + module, json=data)
    assert response.status_code == 201
    record = response.json()
    record_id = record.pop("id")
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        assert bob.get("/api/" + module).json()["total"] == 0
        assert bob.get(f"/api/{module}/{record_id}").status_code == 404
        assert bob.put(f"/api/{module}/{record_id}", json=record).status_code == 404
        assert bob.delete(f"/api/{module}/{record_id}").status_code == 404
        assert bob.post("/api/" + module, json={**data, "user_id": alice["id"]}).status_code == 422
    assert raw_client.get(f"/api/{module}/{record_id}").status_code == 200


def test_dashboard_and_settings_are_isolated(raw_client):
    alice = authenticate(raw_client, "Alice")
    for module, data in RECORDS:
        assert raw_client.post("/api/" + module, json=data).status_code == 201
    prefs = {"timezone": "Asia/Kolkata", "default_currency": "INR", "enabled_modules": ["bills"]}
    assert raw_client.put("/api/settings", json=prefs).status_code == 200
    summary = raw_client.get("/api/dashboard").json()
    assert summary["counts"]["tasks_overdue"] == 1
    assert summary["bill_totals"] == {"USD": "23.50"}
    with TestClient(app) as bob:
        authenticate(bob, "Bob")
        other = bob.get("/api/dashboard").json()
        assert all(value == 0 for value in other["counts"].values())
        for key in ["tasks", "agenda", "upcoming", "groceries", "bills"]:
            assert other[key] == []
        assert other["bill_totals"] == {}
        assert bob.get("/api/settings").json()["default_currency"] == "USD"
        assert bob.put("/api/settings", json={"timezone": "UTC"}).status_code == 200
    assert raw_client.get("/api/settings").json() == prefs
    dependency = session_for_test()
    session = next(dependency)
    assert session.scalar(select(User).where(User.id == UUID(alice["id"]))).username == "Alice"
    dependency.close()
