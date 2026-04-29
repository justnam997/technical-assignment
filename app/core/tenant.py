"""Tenant context: extract org_id at request entry, expose via ContextVar.

This is the safety primitive that prevents cross-tenant leaks. Every
repository method reads `current_org_id()` and includes it in the
WHERE clause.

Why ContextVar (and not request-scoped session info):
  - asyncio-correct: each task has its own context.
  - Always available: no need to thread `org_id` through every call.

Why middleware (and not dependency):
  - Middleware runs before any handler, so even error paths see the
    correct context.
  - A misconfigured route (forgetting the dep) still gets the context.
"""
from __future__ import annotations

import contextvars
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


_current_org_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_org_id", default=None
)
_current_principal_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_principal_id", default=None
)


class TenantContextMissing(RuntimeError):
    """Raised when a query is attempted outside a tenant-scoped request."""


def current_org_id() -> str:
    val = _current_org_id.get()
    if val is None:
        raise TenantContextMissing(
            "tenant context not set — repository method called "
            "outside a request, or middleware misconfigured"
        )
    return val


def current_principal_id() -> str:
    val = _current_principal_id.get()
    if val is None:
        raise TenantContextMissing("principal context not set")
    return val


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts tenant + principal from request headers, sets ContextVars.

    Production note: in real deployments, decode a JWT and read claims.
    For this assignment we trust the upstream gateway to pass headers.
    """

    HEADER_ORG = "x-org-id"
    HEADER_PRINCIPAL = "x-principal-id"

    # Paths that don't require tenant context.
    PUBLIC_PATHS = {"/healthz", "/openapi.json", "/docs", "/redoc"}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in self.PUBLIC_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        org_id = request.headers.get(self.HEADER_ORG)
        principal_id = request.headers.get(self.HEADER_PRINCIPAL)

        if not org_id:
            return Response(
                content='{"detail":"missing X-Org-Id header"}',
                status_code=401,
                media_type="application/json",
            )

        # Default principal to a per-org "anon" so rate-limit still keys per IP/header.
        principal_id = principal_id or f"anon@{org_id}"

        token_org = _current_org_id.set(org_id)
        token_principal = _current_principal_id.set(principal_id)
        try:
            return await call_next(request)
        finally:
            _current_org_id.reset(token_org)
            _current_principal_id.reset(token_principal)
