from __future__ import annotations

from fastapi import Header, HTTPException, Request


def require_auth(request: Request, authorization: str | None = Header(default=None)) -> None:
    store = request.app.state.sessions
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not store.valid(token):
        raise HTTPException(status_code=401, detail="not authenticated")
