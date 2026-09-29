FROM node:22-slim AS web
WORKDIR /workspace/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY pyproject.toml ./
COPY apps/__init__.py apps/__init__.py
COPY apps/api/ apps/api/
COPY packages/ packages/
RUN pip install --no-cache-dir .
COPY --from=web /workspace/apps/web/out/ apps/web/out/
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
