"""Foundation API: stateless calculation and nonpersistent edit preview."""

from dataclasses import asdict
from pathlib import Path
from os import getenv
from hmac import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from apps.api.service import apply_operations, engine_input
from packages.engine import calculate_spec
from packages.schemas.spec import KnittingSpec, Operation

class OperationPreview(BaseModel):
    spec: KnittingSpec
    operations: list[Operation]


def runtime_setting(request: Request, name: str) -> str | None:
    """Read Worker bindings per request, or environment variables on a server."""
    if "env" in request.scope:
        env = request.scope["env"]
        value = env.get(name) if isinstance(env, dict) else getattr(env, name, None)
        return value if isinstance(value, str) else None
    return getenv(name)


async def demo_access(request: Request, x_demo_token: str | None = Header(default=None)) -> None:
    """Require the configured shared demo code for calculation requests."""
    expected = runtime_setting(request, "KNITPILOT_DEMO_TOKEN")
    if runtime_setting(request, "KNITPILOT_REQUIRE_DEMO_TOKEN") == "1" and not expected:
        raise HTTPException(status_code=503, detail="演示访问码尚未配置")
    if expected and (x_demo_token is None or not compare_digest(x_demo_token.encode(), expected.encode())):
        raise HTTPException(status_code=401, detail="演示访问码无效")


async def index() -> dict[str, str]:
    """Small landing endpoint for the API-only demo."""
    return {"name": "KnitPilot API", "status": "demo", "demo": "/demo/", "docs": "/docs", "health": "/health"}


async def health() -> dict[str, str]:
    return {"status": "ok"}


async def calculate(spec: KnittingSpec) -> dict:
    try:
        return asdict(calculate_spec(engine_input(spec)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def preview(body: OperationPreview) -> dict:
    try:
        updated, edits = apply_operations(body.spec, body.operations)
        draft = calculate_spec(engine_input(updated))
        return {"spec": updated.model_dump(mode="json"), "manual_edits": [e.model_dump(mode="json") for e in edits],
                "draft": asdict(draft)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def demo_redirect() -> RedirectResponse:
    return RedirectResponse("/demo/")


def create_app(*, include_web: bool = True, root_redirect: bool = False) -> FastAPI:
    """Construct the same API for Uvicorn or Cloudflare's ASGI server."""
    application = FastAPI(title="KnitPilot API", version="0.3.0")
    application.add_api_route("/", demo_redirect if root_redirect else index, methods=["GET"])
    application.add_api_route("/health", health, methods=["GET"])
    application.add_api_route("/v1/calculate", calculate, methods=["POST"], dependencies=[Depends(demo_access)])
    application.add_api_route("/v1/operations/preview", preview, methods=["POST"], dependencies=[Depends(demo_access)])
    application.add_api_route("/demo", demo_redirect, methods=["GET"], include_in_schema=False)
    if include_web:
        web_out = Path(__file__).resolve().parents[2] / "apps" / "web" / "out"
        if web_out.is_dir():
            application.mount("/demo", StaticFiles(directory=web_out, html=True), name="demo")
    return application


app = create_app()
