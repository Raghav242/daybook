"""The combined production image serves the built frontend from the API origin."""

import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core import config

ASSET = "/assets/index-Crt3PRS_.js"


@pytest.fixture
def frontend_app(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Daybook</title>", encoding="utf-8")
    (dist / ASSET.lstrip("/")).write_text("console.log('daybook')", encoding="utf-8")
    (dist / "assets" / "notes.txt").write_text("not fingerprinted", encoding="utf-8")
    monkeypatch.setattr(config, "FRONTEND_DIST", str(dist))
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://daybook.example"])
    # A fresh app module so the shared app used by other tests stays untouched.
    module = importlib.reload(main_module)
    yield module.app
    monkeypatch.undo()
    importlib.reload(main_module)


def test_index_is_served_and_always_revalidated(frontend_app):
    client = TestClient(frontend_app)
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Daybook</title>" in response.text
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
    etag = response.headers["etag"]
    revalidated = client.get("/", headers={"If-None-Match": etag})
    assert revalidated.status_code == 304
    assert revalidated.headers["cache-control"] == "no-cache"
    assert client.head("/").status_code == 200


def test_only_fingerprinted_assets_are_immutable(frontend_app):
    client = TestClient(frontend_app)
    asset = client.get(ASSET)
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    plain = client.get("/assets/notes.txt")
    assert plain.status_code == 200
    assert plain.headers["cache-control"] == "no-store"
    missing = client.get("/assets/index-Missing0.js")
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"


def test_api_paths_stay_api_and_unknown_paths_are_not_the_spa(frontend_app):
    client = TestClient(frontend_app)
    health = client.get("/api/health")
    assert health.json() == {"status": "ok"}
    assert health.headers["cache-control"] == "no-store"
    for path in ["/api/does-not-exist", "/api/tasks/extra/segments", "/settings", "/assets"]:
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "http_error", path
        assert response.headers["cache-control"] == "no-store", path


def test_frontend_serving_requires_a_build_and_a_trusted_origin(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://daybook.example"])
    with pytest.raises(RuntimeError, match="index.html"):
        main_module.mount_frontend(str(tmp_path))
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    monkeypatch.setattr(main_module, "CORS_ORIGINS", [])
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        main_module.mount_frontend(str(tmp_path))


def test_local_development_does_not_serve_a_frontend():
    client = TestClient(main_module.app)
    assert client.get("/").status_code == 404
