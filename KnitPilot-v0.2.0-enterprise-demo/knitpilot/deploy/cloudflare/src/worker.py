"""Cloudflare ASGI entrypoint; production arithmetic stays in the Python engine."""

from fastapi import Request
from fastapi.responses import Response
from workers import asgi

from apps.api.main import create_app

app = create_app(include_web=False, root_redirect=True)


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def frontend(path: str, request: Request) -> Response:
    """Fetch the exported Next.js page and assets through the ASSETS binding."""
    # Do not disguise unknown API endpoints as frontend pages.
    if path == "v1" or path.startswith("v1/"):
        return Response(status_code=404)
    env = request.scope["env"]
    asset_url = "https://assets.local" + request.url.path
    if request.url.query:
        asset_url += "?" + request.url.query
    asset_response = await env.ASSETS.fetch(asset_url)
    body = await asset_response.bytes()
    return Response(
        content=b"" if request.method == "HEAD" else body,
        status_code=asset_response.status,
        headers=asset_response.headers,
    )


Default = asgi.entrypoint(app)
