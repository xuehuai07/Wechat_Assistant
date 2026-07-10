from __future__ import annotations

import hmac
import secrets
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEYS = ("key", "token", "password", "secret", "authorization", "context_token")


def mask_secret(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:3]}***{text[-3:]}"


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted = {}
        for key, item in value.items():
            if any(marker in str(key).lower() for marker in SENSITIVE_KEYS):
                redacted[key] = mask_secret(item)
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class SessionStore:
    def __init__(self) -> None:
        self._tokens: set[str] = set()

    def create(self, password: str, submitted: str) -> str | None:
        if not password or not hmac.compare_digest(password, submitted):
            return None
        token = secrets.token_urlsafe(32)
        self._tokens.add(token)
        return token

    def valid(self, token: str | None) -> bool:
        return bool(token and token in self._tokens)

    def revoke(self, token: str | None) -> None:
        if token:
            self._tokens.discard(token)
