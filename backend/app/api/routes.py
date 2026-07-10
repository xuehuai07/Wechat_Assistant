from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from .deps import require_auth
from ..maps.service import MapError, ProfileConfigurationError
from ..services.weather import LocationNotFoundError, WeatherError

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class ChatRequest(BaseModel):
    conversation_id: str = "web:default"
    message: str


class NavigationRequest(BaseModel):
    destination: str = Field(min_length=1, max_length=80)
    origin: str | None = Field(default=None, max_length=80)
    mode: Literal["car", "bus", "walk", "ride"] = "car"
    policy: int = Field(default=0, ge=0, le=3)
    callnative: bool = True

    @field_validator("destination", "origin")
    @classmethod
    def normalize_place(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value


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


@router.get("/api/maps/status", dependencies=[Depends(require_auth)])
async def maps_status(request: Request) -> dict:
    return request.app.state.maps.status()


@router.post("/api/maps/navigation", dependencies=[Depends(require_auth)])
async def maps_navigation(request: Request, body: NavigationRequest) -> dict:
    try:
        return request.app.state.maps.navigation_url(
            destination=body.destination,
            origin=body.origin,
            mode=body.mode,
            policy=body.policy,
            callnative=body.callnative,
        )
    except ProfileConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MapError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/weather", dependencies=[Depends(require_auth)])
async def weather(
    request: Request,
    location: str = Query(min_length=2, max_length=80),
    day_offset: int = Query(default=0, ge=0, le=6),
) -> dict:
    if not request.app.state.settings.agent.weather_enabled:
        raise HTTPException(status_code=404, detail="weather is disabled")
    try:
        return await request.app.state.weather.weather(location, day_offset=day_offset)
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WeatherError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
