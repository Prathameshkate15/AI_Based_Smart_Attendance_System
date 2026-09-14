"""Privacy and security middleware for FastAPI backend."""

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)


class PrivacyHeadersMiddleware(BaseHTTPMiddleware):
    """Add privacy and security headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Privacy headers
        response.headers["Pragma"] = "no-cache"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        return response


class RoleBasedAccessMiddleware(BaseHTTPMiddleware):
    """Enforce role-based access on protected endpoints."""

    def __init__(self, app, role_checker):
        super().__init__(app)
        self.role_checker = role_checker

    async def dispatch(self, request, call_next):
        path = request.url.path
        method = request.method

        # Skip privacy/swagger endpoints
        skip_prefixes = ["/api/v1/health", "/api/v1/docs", "/api/v1/redoc", "/admin"]
        if any(path.startswith(prefix) for prefix in skip_prefixes):
            return await call_next(request)

        # Check authorization
        user_role = getattr(request.state, "user_role", None)
        if user_role and not self.role_checker(user_role, path, method):
            return HTTPException(status_code=403, detail="Access denied")

        return await call_next(request)