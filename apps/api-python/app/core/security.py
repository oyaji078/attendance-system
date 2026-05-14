from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import UUID


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest_hex = password_hash.split("$", 3)
        iterations = int(iterations_raw)
    except ValueError:
        return False
    if algorithm != PASSWORD_ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return hmac.compare_digest(candidate, digest_hex)


PLACEHOLDER_SECRETS: tuple[str, ...] = (
    "",
    "change_me_in_production",
    "change_me_secret_key_min_32_chars",
    "dev-local-key-not-for-production-please-change-this-32chars",
    "dev-secret",
    "dev-secret-not-for-production-at-least-32-chars!!",
    "local-dev-attendance-secret-change-me",
    "password",
    "secret",
)


def is_secret_key_safe(key: str) -> tuple[bool, str]:
    if not key:
        return False, "AUTH_SECRET_KEY must not be empty"
    if key.lower() in PLACEHOLDER_SECRETS:
        return False, "AUTH_SECRET_KEY must not be a placeholder value"
    if len(key) < 32:
        return False, f"AUTH_SECRET_KEY must be at least 32 characters (got {len(key)})"
    return True, ""


def _b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64url_decode(payload: str) -> bytes:
    return base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))


def create_session_token(admin_id: UUID, username: str, secret_key: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(admin_id),
        "username": username,
        "iat": now,
        "exp": now + ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(signature)}"


def verify_session_token(token: str, secret_key: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(signature)
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if not hmac.compare_digest(provided, expected):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
