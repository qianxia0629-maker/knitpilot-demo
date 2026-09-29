# KnitPilot · AI针织工艺师

V1 calculation core and API foundation. Drafts need review by a qualified knitting technologist before production.

## Local setup

```bash
cd knitpilot
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q --cov=packages.engine --cov-branch --cov-fail-under=90
cd apps/web && npm ci && npm run build && cd ../..
uvicorn apps.api.main:app --reload
```

Enterprise demo: `http://127.0.0.1:8000/demo/`. API docs: `http://127.0.0.1:8000/docs`. `POST /v1/calculate` takes a complete, confirmed `KnittingSpec`; `POST /v1/operations/preview` applies a measurement patch in memory and recalculates. Neither route persists a version. See `fixtures/basic_pullover.json` and `docs/ARCHITECTURE.md`. The current web app supports manual input, programmatic SVG technical diagrams, QC review, and JSON download. File extraction, database versions and PDF/Excel remain planned.

Enterprise trial demo at `/demo/` after building `apps/web` (`npm ci && npm run build`). Deploy via multi-stage `Dockerfile` and `render.yaml`; setup and acceptance steps: `docs/DEPLOY.md`.
