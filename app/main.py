"""FastAPI app factory.

Public:
  - GET /healthz       — liveness probe
  - GET /docs, /redoc  — OpenAPI explorer
  - GET /openapi.json  — machine-readable spec

All other paths require X-Org-Id (enforced by TenantMiddleware).
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.employees import router as employees_router
from app.core.tenant import TenantMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="HR Employee Search API",
        version="1.0.0",
        description=(
            "Multi-tenant employee directory search. "
            "Each organization sees its own employees via a configurable "
            "column layout."
        ),
    )

    # Order matters: tenant middleware must run before any route handler.
    app.add_middleware(TenantMiddleware)

    app.include_router(employees_router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
