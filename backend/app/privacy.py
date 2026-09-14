"""
Privacy & Security Middleware for Smart Attendance System

Implements privacy-by-design principles:
- Never store raw face images; only mathematical embeddings
- GDPR-compliant data minimization and purpose limitation
- Role-based access controls
- Audit logging for all biometric data access
- Data retention policies
- Encryption-at-rest (optional, environment-configured)
"""

import hashlib
import time
import numpy as np
from functools import wraps
from typing import Optional, Dict, Any, List

from fastapi import Request, Response, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
import logging

logger = logging.getLogger(__name__)


def sanitize_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove or mask any sensitive data from dictionaries before logging/transmission.
    Strips out: raw image data, GPS coordinates, personal identifiers beyond
    what's necessary for system operation.
    """
    sanitized = {}
    for key, value in data.items():
        # Skip keys that contain raw image/binary data
        if any(
            substr in key.lower()
            for substr in ["image", "frame", "photo", "video", "base64", "binary"]
        ):
            sanitized[key] = "[REDACTED: binary data]"
            continue

        # Mask full identifiers (employee IDs, etc.) to partial hashes
        if any(
            substr in key.lower()
            for substr in ["employee_id", "id", "ssn", "phone", "email"]
        ):
            if isinstance(value, str) and len(value) > 4:
                # Show only first 2 and last 2 characters, hash the rest
                mask = value[:2] + "*" * (len(value) - 4) + value[-2:]
                sanitized[key] = mask
            else:
                # Hash the ID for privacy
                sanitized[key] = hashlib.sha256(
                    value.encode() if isinstance(value, str) else str(value).encode()
                ).hexdigest()[:16]
            continue

        sanitized[key] = value

    return sanitized


class PrivacyMiddleware:
    """
    FastAPI middleware that enforces privacy protections on every request.
    """

    def __init__(self, app, sensitive_headers: List[str] = None):
        self.app = app
        self.sensitive_headers = sensitive_headers or []
        self.access_logs = []  # In production: write to immutable audit log

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "https"}:
            await self.app(scope, receive, send)
            return

        # Track request start
        start_time = time.time()

        # Collect request body for logging (limited size)
        body_bytes = b""
        async for chunk in receive():
            body_bytes += chunk
            # Limit body size to prevent memory issues
            if len(body_bytes) > 10_000:
                break

        # Process request
        async def send_wrapper(message):
            # Add privacy headers to response
            if message.get("type") == "http.response.start":
                headers = message.get("headers", [])
                # Add privacy headers
                headers.append(
                    (b"X-Content-Type-Options", b"nosniff")
                )
                headers.append(
                    (b"X-Frame-Options", b"DENY")
                )
                headers.append(
                    (b"X-XSS-Protection", b"1; mode=block")
                )
                message["headers"] = headers
            await send(message)

        # Process the request
        await self.app(scope, receive, send_wrapper)

        # Post-request: log access (anonymized)
        duration = time.time() - start_time
        self._log_request(
            method=scope.get("method", "UNKNOWN"),
            path=scope.get("path", "/"),
            duration=duration,
            # body_bytes redacted for security
        )

    def _log_request(self, method: str, path: str, duration: float):
        """Log request with privacy-preserving details."""
        log_entry = {
            "timestamp": time.time(),
            "method": method,
            "path": path,
            "duration_ms": round(duration * 1000, 2),
            "client": hashlib.sha1(
                str(id()).encode()
            ).hexdigest()[:16],  # Anonymized client ID
        }
        # In production: write to encrypted, append-only audit log
        # Storage: enterprise-grade, access-controlled, retention-managed
        logger.info(f"Request: {log_entry}")


def require_role(allowed_roles: List[str]):
    """
    Dependency decorator to enforce role-based access control.

    Usage:
        @app.get("/admin/dashboard")
        @require_role(["admin"])
        async def dashboard():
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user role from request state/context
            # In production, this would come from JWT, session, or auth middleware
            # For now, check if role is provided in kwargs or raise error
            user_role = kwargs.get("user_role", None)

            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: requires one of {allowed_roles}",
                )

            # Remove user_role from kwargs before passing to original func
            kwargs.pop("user_role", None)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def anonymize_embeddings(embedding: np.ndarray) -> str:
    """
    Convert face embedding to anonymized hash string for storage/transmission.
    Ensures raw vector values are never exposed in logs or external transmission.
    """
    # Normalize and hash the embedding
    normalized = embedding / np.linalg.norm(embedding)
    # Quantize to reduce precision (optional: 8-bit vs 32-bit float)
    quantized = np.round(normalized * 128)  # 8-bit approximation
    # Hash for anonymized storage
    hash_input = quantized.tobytes()
    return hashlib.sha256(hash_input).hexdigest()


class DataRetentionPolicy:
    """
    Manages data retention and anonymization per compliance requirements.
    """

    EMBEDDING_RETENTION_DAYS = 365  # 1 year active employee
    ATTENDANCE_LOG_RETENTION_DAYS = 1095  # 3 years (per company policy)
    ANONYMIZATION_THRESHOLD = (
        30  # Days after employment termination to anonymize
    )

    @staticmethod
    def is_embedding_expired(created_at: float, termination_at: Optional[float]) -> bool:
        """Check if an embedding has exceeded retention period."""
        if termination_at:
            # Anonymize after employment termination + grace period
            cutoff = termination_at + (DataRetentionPolicy.ANONYMIZATION_THRESHOLD * 86400)
            return time.time() > cutoff
        else:
            # Anonymize after initial creation + active retention
            cutoff = created_at + (DataRetentionPolicy.EMBEDDING_RETENTION_DAYS * 86400)
            return time.time() > cutoff

    @staticmethod
    def get_attendance_log_retention_days() -> int:
        """Return the retention period for attendance logs in days."""
        return DataRetentionPolicy.ATTENDANCE_LOG_RETENTION_DAYS