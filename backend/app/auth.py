"""Small stateless admin authentication helper."""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException, status


def _secret() -> bytes:
    return os.getenv("ADMIN_TOKEN_SECRET", "change-this-attendance-secret").encode()


def issue_token(username: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": username, "exp": int(time.time()) + 8 * 60 * 60}).encode()
    ).decode()
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def require_admin(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")
    try:
        payload, signature = authorization[7:].split(".", 1)
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data["exp"] < time.time():
            raise ValueError
        return data["sub"]
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired admin session")
