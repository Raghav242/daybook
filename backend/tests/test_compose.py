"""Validate the real Compose model with an isolated, fake environment file."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKER = shutil.which("docker")
pytestmark = pytest.mark.skipif(not DOCKER, reason="Docker CLI is unavailable")


def compose_model(tmp_path, overrides, production=False):
    template_name = ".env.production.example" if production else ".env.example"
    compose_name = "compose.production.yaml" if production else "compose.yaml"
    template = (ROOT / template_name).read_text(encoding="utf-8-sig")
    values = dict(re.findall(r"(?m)^([A-Z][A-Z0-9_]*)=(.*)$", template))
    values.update(overrides)
    env_file = tmp_path / "compose.env"
    env_file.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    environment = os.environ.copy()
    for key in values:
        environment.pop(key, None)
    return subprocess.run(
        [
            DOCKER,
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(ROOT / compose_name),
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_compose_requires_password(tmp_path):
    result = compose_model(tmp_path, {"POSTGRES_PASSWORD": ""})
    assert result.returncode != 0
    assert "POSTGRES_PASSWORD" in result.stderr


def test_compose_uses_custom_addresses_ports_and_credentials(tmp_path):
    fake_password = "fake@:/#$ password"
    result = compose_model(
        tmp_path,
        {
            "POSTGRES_PASSWORD": "'" + fake_password + "'",
            "HOST_BIND_ADDRESS": "127.0.0.2",
            "POSTGRES_HOST": "custom-db",
            "POSTGRES_PORT": "5544",
            "POSTGRES_PUBLISHED_PORT": "5445",
            "BACKEND_PORT": "8087",
            "BACKEND_PUBLISHED_PORT": "8111",
            "FRONTEND_PORT": "5168",
            "FRONTEND_PUBLISHED_PORT": "5222",
            "CORS_ORIGINS": "https://dashboard.example.test",
            "VITE_API_PROXY": "http://backend:8087",
            "VITE_API_BASE_URL": "https://api.example.test/api",
        },
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    db, backend, frontend = (services[name] for name in ["db", "backend", "frontend"])
    assert db["command"] == ["postgres", "-p", "5544"]
    for service, host_port, container_port in [
        (db, "5445", 5544),
        (backend, "8111", 8087),
        (frontend, "5222", 5168),
    ]:
        binding = service["ports"][0]
        assert binding["host_ip"] == "127.0.0.2"
        assert binding["published"] == host_port
        assert binding["target"] == container_port
    assert backend["environment"]["POSTGRES_HOST"] == "custom-db"
    # Compose escapes dollar signs in its reusable configuration output.
    assert backend["environment"]["POSTGRES_PASSWORD"] == fake_password.replace("$", "$$")
    assert backend["environment"]["CORS_ORIGINS"] == "https://dashboard.example.test"
    assert frontend["environment"]["VITE_API_PROXY"] == "http://backend:8087"
    assert frontend["environment"]["VITE_DEV_PORT"] == "5168"
    assert frontend["environment"]["VITE_API_BASE_URL"] == "https://api.example.test/api"


def test_production_requires_database_secret(tmp_path):
    result = compose_model(tmp_path, {"DATABASE_URL": ""}, production=True)
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_production_separates_public_build_config_and_runtime_secrets(tmp_path):
    database_url = "postgresql+psycopg://fake:fake@managed.example.test/daybook"
    result = compose_model(
        tmp_path,
        {
            "DATABASE_URL": database_url,
            "VITE_API_BASE_URL": "https://api.example.test/api",
            "CORS_ORIGINS": "https://app.example.test",
            "BACKEND_UPSTREAM": "http://backend:8087",
            "BACKEND_PORT": "8087",
        },
        production=True,
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert set(services) == {"migrate", "backend", "frontend"}
    for name, service in services.items():
        assert service["build"]["target"] == "production"
        assert not service.get("volumes")
        if name != "frontend":
            assert not service.get("ports")
            assert service["environment"]["DATABASE_URL"] == database_url
    frontend = services["frontend"]
    assert frontend["build"]["args"] == {"VITE_API_BASE_URL": "https://api.example.test/api"}
    assert "DATABASE_URL" not in frontend["environment"]
    assert frontend["environment"]["BACKEND_UPSTREAM"] == "http://backend:8087"
    assert services["backend"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
