"""The deploy script against a fake Render API (no network, no real service)."""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "render_deploy.py"
SHA = "a" * 40


class FakeRender:
    def __init__(self, statuses, service=None, post_body=None):
        self.statuses = list(statuses)
        self.service = service or {"id": "srv-1", "autoDeployTrigger": "off"}
        self.post_body = (
            post_body if post_body is not None else {"id": "dep-1", "commit": {"id": SHA}}
        )
        self.requests = []


@pytest.fixture
def render(monkeypatch):
    state = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            fake = state["fake"]
            fake.requests.append(("GET", self.path, self.headers["Authorization"], None))
            if self.path == "/v1/services/srv-1":
                return self.reply(200, fake.service)
            if self.path.startswith("/v1/services/srv-1/deploys?"):
                return self.reply(200, [{"deploy": {"id": "dep-q", "commit": {"id": SHA}}}])
            status = fake.statuses.pop(0) if len(fake.statuses) > 1 else fake.statuses[0]
            self.reply(
                200, {"id": self.path.rsplit("/", 1)[1], "status": status, "commit": {"id": SHA}}
            )

        def do_POST(self):
            fake = state["fake"]
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fake.requests.append(("POST", self.path, self.headers["Authorization"], body))
            self.reply(201 if fake.post_body else 202, fake.post_body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("RENDER_API_BASE", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("RENDER_API_KEY", "test-key")
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-1")
    monkeypatch.setenv("COMMIT_SHA", SHA)
    monkeypatch.setenv("POLL_SECONDS", "0")
    spec = importlib.util.spec_from_file_location("render_deploy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def run(fake):
        state["fake"] = fake
        module.main()
        return fake

    yield module, run
    server.shutdown()


def test_deploys_the_exact_commit_and_waits_until_live(render):
    module, run = render
    fake = run(FakeRender(["build_in_progress", "update_in_progress", "live"]))
    post = [r for r in fake.requests if r[0] == "POST"]
    assert post == [
        (
            "POST",
            "/v1/services/srv-1/deploys",
            "Bearer test-key",
            {"commitId": SHA, "clearCache": "do_not_clear"},
        )
    ]
    assert fake.requests[-1][1] == "/v1/services/srv-1/deploys/dep-1"


@pytest.mark.parametrize(
    "status", ["build_failed", "update_failed", "canceled", "pre_deploy_failed"]
)
def test_failed_deploys_fail_the_workflow(render, status):
    module, run = render
    with pytest.raises(module.DeployError, match=status):
        run(FakeRender(["build_in_progress", status]))


def test_refuses_to_deploy_when_auto_deploy_is_on(render):
    module, run = render
    for service in ({"autoDeployTrigger": "commit"}, {"autoDeploy": "yes"}):
        fake = FakeRender(["live"], service=service)
        with pytest.raises(module.DeployError, match="auto-deploy"):
            run(fake)
        assert not [r for r in fake.requests if r[0] == "POST"]


def test_queued_deploy_is_found_by_commit(render):
    module, run = render
    fake = run(FakeRender(["queued", "live"], post_body={}))
    assert fake.requests[-1][1] == "/v1/services/srv-1/deploys/dep-q"


def test_rejects_short_shas(render, monkeypatch):
    module, run = render
    monkeypatch.setenv("COMMIT_SHA", "abc123")
    with pytest.raises(module.DeployError, match="40-character"):
        run(FakeRender(["live"]))


def test_times_out(render, monkeypatch):
    module, run = render
    monkeypatch.setenv("DEPLOY_TIMEOUT_SECONDS", "0")
    with pytest.raises(module.DeployError, match="still build_in_progress"):
        run(FakeRender(["build_in_progress"]))
