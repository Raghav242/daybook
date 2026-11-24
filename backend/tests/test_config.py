import pytest
from sqlalchemy import URL, make_url

from app.core import config
from app.core.config import (
    get_cors_origins,
    get_database_url,
    get_migration_database_url,
    normalize_database_url,
)
from app.infrastructure.database import engine_options
from app.infrastructure.migrations import migration_url


def test_password_characters_survive_connection_url_construction(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    password = "example@:/#$ password"
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    monkeypatch.setenv("POSTGRES_HOST", "db")
    url = get_database_url()
    assert isinstance(url, URL)
    assert url.password == password
    assert url.host == "db"
    assert make_url(url.render_as_string(hide_password=False)).password == password


def test_explicit_database_url_override_is_preserved(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    assert get_database_url() == "sqlite:///./test.db"


def test_cors_origins_come_from_environment_and_trim_empty_entries(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://app.example.test, ,https://other.example.test ")
    assert get_cors_origins() == ["https://app.example.test", "https://other.example.test"]
    monkeypatch.delenv("CORS_ORIGINS")
    assert get_cors_origins() == []


def test_libpq_style_urls_use_the_installed_psycopg_driver(monkeypatch):
    neon = "postgresql://user:secret@ep-x-pooler.example.neon.tech/db?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", neon)
    assert get_database_url() == neon.replace("postgresql://", "postgresql+psycopg://", 1)
    assert normalize_database_url("postgres://u@h/d") == "postgresql+psycopg://u@h/d"
    assert normalize_database_url("postgresql+psycopg://u@h/d") == "postgresql+psycopg://u@h/d"
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://u@direct.example/d")
    assert get_migration_database_url() == "postgresql+psycopg://u@direct.example/d"
    monkeypatch.delenv("MIGRATION_DATABASE_URL")
    assert get_migration_database_url() is None


def test_pooled_hosts_get_safe_engine_options():
    pooled = engine_options("postgresql+psycopg://u@ep-x-pooler.example/d")
    assert pooled["pool_pre_ping"] and pooled["pool_recycle"] == 300
    assert pooled["connect_args"] == {"prepare_threshold": None}
    assert "connect_args" not in engine_options("postgresql+psycopg://u@ep-x.example/d")
    assert engine_options("sqlite:///./x.db") == {"pool_pre_ping": True}


def test_migrations_prefer_direct_url_and_refuse_pooled_connections(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql+psycopg://u@ep-x-pooler.example/d")
    monkeypatch.setattr(config, "MIGRATION_DATABASE_URL", None)
    with pytest.raises(RuntimeError, match="MIGRATION_DATABASE_URL"):
        migration_url()
    monkeypatch.setattr(config, "MIGRATION_DATABASE_URL", "postgresql+psycopg://u@ep-x.example/d")
    assert migration_url() == "postgresql+psycopg://u@ep-x.example/d"
    monkeypatch.setattr(config, "MIGRATION_DATABASE_URL", None)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql+psycopg://u@ep-x.example/d")
    assert migration_url() == "postgresql+psycopg://u@ep-x.example/d"
