from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from ..agent.chat_agent import ChatAgent
from ..config import Settings
from .credentials import load_credentials, save_credentials
from .ilink_client import ILinkClient, extract_text_messages

logger = logging.getLogger(__name__)


@dataclass
class WechatRuntimeState:
    login_status: str = "idle"
    polling: bool = False
    qr_code: str = ""
    qr_url: str = ""
    last_error: str = ""
    received_count: int = 0
    sent_count: int = 0
    get_updates_buf: str = ""
    context_tokens: dict[str, str] = field(default_factory=dict)


class WechatService:
    def __init__(self, settings: Settings, agent: ChatAgent) -> None:
        self.settings = settings
        self.agent = agent
        self.state = WechatRuntimeState()
        self._client: ILinkClient | None = None
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._load_saved_credentials()

    def _load_saved_credentials(self) -> None:
        creds = load_credentials(self.settings.wechat.credentials_path)
        token = creds.get("token", "")
        base_url = creds.get("base_url", self.settings.wechat.base_url)
        self.state.context_tokens = dict(creds.get("context_tokens", {}))
        if token:
            self._client = ILinkClient(base_url=base_url, token=token, timeout=self.settings.wechat.long_poll_timeout_seconds)
            self.state.login_status = "logged_in"

    def _persist(self) -> None:
        client = self._client
        save_credentials(
            self.settings.wechat.credentials_path,
            {
                "token": client.token if client else "",
                "base_url": client.base_url if client else self.settings.wechat.base_url,
                "context_tokens": self.state.context_tokens,
            },
        )

    def status(self) -> dict[str, Any]:
        return {
            "login_status": self.state.login_status,
            "polling": self.state.polling,
            "qr_url": self.state.qr_url,
            "last_error": self.state.last_error,
            "received_count": self.state.received_count,
            "sent_count": self.state.sent_count,
            "has_token": bool(self._client and self._client.token),
        }

    async def request_qr(self) -> dict[str, Any]:
        client = ILinkClient(self.settings.wechat.base_url, timeout=self.settings.wechat.long_poll_timeout_seconds)
        data = await client.fetch_qr_code()
        qr_code = str(data.get("qrcode") or "")
        qr_url = str(data.get("qrcode_img_content") or data.get("qrcode_url") or data.get("url") or "")
        if not qr_code:
            raise RuntimeError("iLink QR response is missing qrcode")
        if not qr_url:
            raise RuntimeError("iLink QR response is missing qrcode_img_content")
        self.state.qr_code = qr_code
        self.state.qr_url = qr_url
        self.state.login_status = "waiting_scan"
        self.state.last_error = ""
        return {"status": self.state.login_status, "qr_url": qr_url}

    async def poll_qr_once(self) -> dict[str, Any]:
        if not self.state.qr_code:
            raise RuntimeError("QR code has not been requested")
        client = ILinkClient(self.settings.wechat.base_url, timeout=self.settings.wechat.long_poll_timeout_seconds)
        data = await client.poll_qr_status(self.state.qr_code)
        qr_status = str(data.get("status") or "wait")
        token = data.get("token") or data.get("bot_token") or data.get("access_token")
        if token:
            base_url = str(data.get("baseurl") or data.get("base_url") or self.settings.wechat.base_url)
            self._client = ILinkClient(base_url, token=str(token), timeout=self.settings.wechat.long_poll_timeout_seconds)
            self.state.login_status = "logged_in"
            self.state.qr_code = ""
            self.state.qr_url = ""
            self.state.last_error = ""
            self._persist()
        elif qr_status in {"scaned", "scanned"}:
            self.state.login_status = "scanned"
        elif qr_status == "expired":
            self.state.login_status = "expired"
        elif qr_status == "confirmed":
            self.state.last_error = "iLink login confirmed without bot token"
            raise RuntimeError(self.state.last_error)
        return {"status": self.state.login_status, "has_token": bool(self._client and self._client.token)}

    async def start_polling(self) -> None:
        if self._task and not self._task.done():
            return
        if not self._client:
            raise RuntimeError("WeChat is not logged in")
        self._stop.clear()
        self._task = asyncio.create_task(self._poll_loop())

    async def stop_polling(self) -> None:
        self._stop.set()
        if self._task:
            await asyncio.wait([self._task], timeout=5)
        self.state.polling = False

    async def _poll_loop(self) -> None:
        assert self._client
        self.state.polling = True
        while not self._stop.is_set():
            try:
                payload = await self._client.get_updates(self.state.get_updates_buf)
                self.state.get_updates_buf = str(payload.get("get_updates_buf") or self.state.get_updates_buf)
                for message in extract_text_messages(payload):
                    self.state.received_count += 1
                    self.state.context_tokens[message.user_id] = message.context_token
                    self._persist()
                    result = await self.agent.run(
                        conversation_id=f"wx:{message.user_id}",
                        user_message=message.text,
                        source="wechat",
                        external_user_id=message.user_id,
                        external_msg_id=message.message_id,
                    )
                    await self._client.send_text(message.user_id, result.reply, message.context_token)
                    self.state.sent_count += 1
                await asyncio.sleep(self.settings.wechat.poll_interval_seconds)
            except Exception as exc:
                self.state.last_error = str(exc)
                logger.exception("WeChat polling failed")
                await asyncio.sleep(5)
        self.state.polling = False
