from sqlalchemy import URL, make_url

from app.core.config import get_cors_origins, get_database_url


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
