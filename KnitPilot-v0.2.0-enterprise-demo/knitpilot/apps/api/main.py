"""Foundation API: stateless calculation and nonpersistent edit preview."""

from dataclasses import asdict
from pathlib import Path
from os import getenv
from hmac import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from apps.api.service import apply_operations, engine_input
from packages.engine import calculate_spec
from packages.schemas.spec import KnittingSpec, Operation

app = FastAPI(title="KnitPilot API", version="0.1.0")


class OperationPreview(BaseModel):
    spec: KnittingSpec
    operations: list[Operation]


def demo_access(x_demo_token: str | None = Header(default=None)) -> None:
    """Require the configured shared demo code for calculation requests."""
    expected = getenv("KNITPILOT_DEMO_TOKEN")
    if getenv("KNITPILOT_REQUIRE_DEMO_TOKEN") == "1" and not expected:
        raise HTTPException(status_code=503, detail="演示访问码尚未配置")
    if expected and (x_demo_token is None or not compare_digest(x_demo_token, expected)):
        raise HTTPException(status_code=401, detail="演示访问码无效")


@app.get("/")
def index() -> dict[str, str]:
    """Small landing endpoint for the API-only demo."""
    return {"name": "KnitPilot API", "status": "demo", "demo": "/demo/", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/calculate", dependencies=[Depends(demo_access)])
def calculate(spec: KnittingSpec) -> dict:
    try:
        return asdict(calculate_spec(engine_input(spec)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/operations/preview", dependencies=[Depends(demo_access)])
def preview(body: OperationPreview) -> dict:
    try:
        updated, edits = apply_operations(body.spec, body.operations)
        draft = calculate_spec(engine_input(updated))
        return {"spec": updated.model_dump(mode="json"), "manual_edits": [e.model_dump(mode="json") for e in edits],
                "draft": asdict(draft)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/demo", include_in_schema=False)
def demo_redirect() -> RedirectResponse:
    return RedirectResponse("/demo/")


_web_out = Path(__file__).resolve().parents[2] / "apps" / "web" / "out"
if _web_out.is_dir():
    app.mount("/demo", StaticFiles(directory=_web_out, html=True), name="demo")
