from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .deps import require_auth

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class ChatRequest(BaseModel):
    conversation_id: str = "web:default"
    message: str


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@router.post("/api/login")
async def login(request: Request, body: LoginRequest) -> dict:
    token = request.app.state.sessions.create(request.app.state.settings.web_password, body.password)
    if not token:
        raise HTTPException(status_code=401, detail="invalid password")
    return {"token": token}


@router.get("/api/status", dependencies=[Depends(require_auth)])
async def status(request: Request) -> dict:
    db = request.app.state.db
    return {
        "config": request.app.state.settings.public_summary(),
        "wechat": request.app.state.wechat.status(),
        "messages": db.recent_messages_all(20),
    }


@router.post("/api/chat", dependencies=[Depends(require_auth)])
async def chat(request: Request, body: ChatRequest) -> dict:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is empty")
    result = await request.app.state.agent.run(body.conversation_id, body.message.strip(), source="web")
    return {"conversation_id": result.conversation_id, "reply": result.reply}


@router.get("/api/conversations", dependencies=[Depends(require_auth)])
async def conversations(request: Request) -> list[dict]:
    return request.app.state.db.list_conversations()


@router.get("/api/messages", dependencies=[Depends(require_auth)])
async def messages(request: Request, conversation_id: str = "web:default") -> list[dict]:
    return request.app.state.db.list_messages(conversation_id)


@router.get("/api/wechat/status", dependencies=[Depends(require_auth)])
async def wechat_status(request: Request) -> dict:
    return request.app.state.wechat.status()


@router.post("/api/wechat/qr", dependencies=[Depends(require_auth)])
async def wechat_qr(request: Request) -> dict:
    return await request.app.state.wechat.request_qr()


@router.post("/api/wechat/qr/poll", dependencies=[Depends(require_auth)])
async def wechat_qr_poll(request: Request) -> dict:
    return await request.app.state.wechat.poll_qr_once()


@router.post("/api/wechat/start", dependencies=[Depends(require_auth)])
async def wechat_start(request: Request) -> dict:
    await request.app.state.wechat.start_polling()
    return request.app.state.wechat.status()


@router.post("/api/wechat/stop", dependencies=[Depends(require_auth)])
async def wechat_stop(request: Request) -> dict:
    await request.app.state.wechat.stop_polling()
    return request.app.state.wechat.status()


@router.get("/api/logs", dependencies=[Depends(require_auth)])
async def logs(request: Request) -> dict:
    path: Path = request.app.state.settings.logging.path
    if not path.exists():
        return {"lines": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    return {"lines": lines}
