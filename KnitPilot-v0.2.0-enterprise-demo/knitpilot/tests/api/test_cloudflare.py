"""Adapter contract tests on CPython; Wrangler separately checks the deployment bundle."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

from fastapi.testclient import TestClient
import pytest

from apps.api.main import create_app


class BindingsApp:
    """Inject the request-scoped environment used by Cloudflare's ASGI adapter."""

    def __init__(self, app, env):
        self.app, self.env = app, env

    async def __call__(self, scope, receive, send):
        await self.app({**scope, "env": self.env}, receive, send)


def test_worker_secret_overrides_server_environment(monkeypatch, spec):
    monkeypatch.setenv("KNITPILOT_DEMO_TOKEN", "server-secret")
    env = SimpleNamespace(KNITPILOT_REQUIRE_DEMO_TOKEN="1", KNITPILOT_DEMO_TOKEN="worker-secret")
    client = TestClient(BindingsApp(create_app(include_web=False), env))
    body = spec.model_dump()
    assert client.post("/v1/calculate", json=body).status_code == 401
    assert client.post("/v1/calculate", json=body, headers={"X-Demo-Token": "server-secret"}).status_code == 401
    response = client.post("/v1/calculate", json=body, headers={"X-Demo-Token": "worker-secret"})
    assert response.status_code == 200
    assert response.json()["back_panel"]["cast_on"] == 122


def test_worker_missing_secret_fails_closed(monkeypatch, spec):
    monkeypatch.setenv("KNITPILOT_DEMO_TOKEN", "server-secret")
    client = TestClient(BindingsApp(create_app(include_web=False), {"KNITPILOT_REQUIRE_DEMO_TOKEN": "1"}))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/v1/calculate", json=spec.model_dump()).status_code == 503


def test_worker_edit_preview_reuses_engine(spec):
    env = {"KNITPILOT_REQUIRE_DEMO_TOKEN": "1", "KNITPILOT_DEMO_TOKEN": "trial"}
    client = TestClient(BindingsApp(create_app(include_web=False), env))
    body = {"spec": spec.model_dump(), "operations": [{"op": "replace", "path": "/measurements/chest_width",
            "value": 60, "reason": "trial", "user": "qa"}]}
    assert client.post("/v1/operations/preview", json=body).status_code == 401
    response = client.post("/v1/operations/preview", json=body, headers={"X-Demo-Token": "trial"})
    assert response.status_code == 200
    assert response.json()["draft"]["back_panel"]["cast_on"] > 122
    assert response.json()["manual_edits"][0]["old_value"] == 58


class FakeAssets:
    def __init__(self):
        self.urls = []

    async def fetch(self, url):
        self.urls.append(url)

        async def body():
            return b"<html>KnitPilot</html>"

        return SimpleNamespace(status=200, headers={"content-type": "text/html"}, bytes=body)


@pytest.fixture
def worker_client(monkeypatch):
    # Only the Cloudflare entrypoint wrapper is mocked. Routes and calculations are real.
    monkeypatch.setitem(sys.modules, "workers", SimpleNamespace(asgi=SimpleNamespace(entrypoint=lambda app: app)))
    path = Path(__file__).resolve().parents[2] / "deploy/cloudflare/src/worker.py"
    module_spec = importlib.util.spec_from_file_location("knitpilot_worker_test", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    assets = FakeAssets()
    env = SimpleNamespace(ASSETS=assets, KNITPILOT_REQUIRE_DEMO_TOKEN="1")
    return TestClient(BindingsApp(module.app, env)), assets


def test_worker_frontend_redirect_and_assets(worker_client):
    client, assets = worker_client
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/demo/"
    response = client.get("/demo/?trial=1")
    assert response.text == "<html>KnitPilot</html>"
    assert response.headers["content-type"] == "text/html"
    assert assets.urls == ["https://assets.local/demo/?trial=1"]
    assert client.head("/demo/").content == b""


def test_worker_unknown_api_is_not_a_page(worker_client):
    client, assets = worker_client
    assert client.get("/v1/unknown").status_code == 404
    assert client.post("/demo/").status_code == 405
    assert client.get("/health").status_code == 200
    assert assets.urls == []


def test_prepare_cloudflare_rejects_missing_build(tmp_path):
    from scripts.prepare_cloudflare import prepare
    with pytest.raises(ValueError, match="run build first"):
        prepare(tmp_path)


def test_prepare_cloudflare_stages_only_shared_sources(tmp_path):
    from scripts.prepare_cloudflare import prepare
    for directory in ("apps/api", "packages/schemas", "packages/engine", "apps/web/out/_next"):
        (tmp_path / directory).mkdir(parents=True)
    for name in ("apps/__init__.py", "packages/__init__.py", "apps/api/main.py", "packages/engine/core.py"):
        (tmp_path / name).write_text("# test source\n")
    (tmp_path / "apps/api/secret.env").write_text("must not bundle")
    (tmp_path / "apps/web/out/index.html").write_text("<html>demo</html>")
    (tmp_path / "apps/web/out/demo-spec.json").write_text("{}")
    assert prepare(tmp_path) == (4, 2)
    deployment = tmp_path / "deploy/cloudflare"
    assert (deployment / "src/packages/engine/core.py").exists()
    assert not (deployment / "src/apps/api/secret.env").exists()
    assert (deployment / "public/demo/index.html").read_text() == "<html>demo</html>"
    # Rebuild removes stale deployed files without touching the entrypoint.
    (deployment / "src/worker.py").write_text("entrypoint")
    (deployment / "public/stale.html").write_text("stale")
    prepare(tmp_path)
    assert not (deployment / "public/stale.html").exists()
    assert (deployment / "src/worker.py").read_text() == "entrypoint"
