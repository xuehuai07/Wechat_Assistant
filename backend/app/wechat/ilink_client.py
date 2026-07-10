from __future__ import annotations

import base64
import random
import uuid
from dataclasses import dataclass
from typing import Any

import httpx


CHANNEL_VERSION = "2.0.0"
CLIENT_VERSION = "131072"
BOT_TYPE = "3"


def _random_uin() -> str:
    return base64.b64encode(str(random.randint(0, 0xFFFFFFFF)).encode("utf-8")).decode("utf-8")


def _headers(token: str = "") -> dict[str, str]:
    result = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": _random_uin(),
        "iLink-App-Id": "bot",
        "iLink-App-ClientVersion": CLIENT_VERSION,
    }
    if token:
        result["Authorization"] = f"Bearer {token}"
    return result


@dataclass
class ILinkMessage:
    message_id: str
    user_id: str
    text: str
    context_token: str
    raw: dict[str, Any]


class ILinkClient:
    def __init__(self, base_url: str, token: str = "", timeout: int = 35) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    async def _post(self, endpoint: str, body: dict[str, Any], *, timeout: int | None = None) -> dict[str, Any]:
        body.setdefault("base_info", {}).setdefault("channel_version", CHANNEL_VERSION)
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            response = await client.post(f"{self.base_url}/{endpoint}", headers=_headers(self.token), json=body)
            response.raise_for_status()
            return response.json()

    async def fetch_qr_code(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.base_url}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}")
            response.raise_for_status()
            return response.json()

    async def poll_qr_status(self, qrcode: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout + 5) as client:
            response = await client.get(f"{self.base_url}/ilink/bot/get_qrcode_status", params={"qrcode": qrcode})
            response.raise_for_status()
            return response.json()

    async def get_updates(self, get_updates_buf: str = "") -> dict[str, Any]:
        return await self._post("ilink/bot/getupdates", {"get_updates_buf": get_updates_buf}, timeout=self.timeout + 5)

    async def send_text(self, to_user_id: str, text: str, context_token: str) -> dict[str, Any]:
        return await self._post(
            "ilink/bot/sendmessage",
            {
                "msg": {
                    "from_user_id": "",
                    "to_user_id": to_user_id,
                    "client_id": uuid.uuid4().hex[:16],
                    "message_type": 2,
                    "message_state": 2,
                    "item_list": [{"type": 1, "text_item": {"text": text}}],
                    "context_token": context_token,
                }
            },
        )


def extract_text_messages(payload: dict[str, Any]) -> list[ILinkMessage]:
    messages = []
    for item in payload.get("msgs", []) or []:
        msg = item.get("msg", item)
        user_id = str(msg.get("from_user_id") or msg.get("user_id") or "")
        context_token = str(msg.get("context_token") or "")
        message_id = str(msg.get("msg_id") or msg.get("client_id") or uuid.uuid4().hex)
        chunks = []
        for entry in msg.get("item_list", []) or []:
            if entry.get("type") == 1:
                text = entry.get("text_item", {}).get("text")
                if text:
                    chunks.append(str(text))
        if user_id and chunks:
            messages.append(ILinkMessage(message_id=message_id, user_id=user_id, text="\n".join(chunks), context_token=context_token, raw=msg))
    return messages
