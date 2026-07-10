from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import Settings


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ModelReply:
        url = self.settings.model.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.model.model,
            "messages": messages,
            "temperature": 0.6,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            async with httpx.AsyncClient(timeout=self.settings.model.timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise RuntimeError(f"DeepSeek request failed: HTTP {exc.response.status_code} {detail}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("DeepSeek request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"DeepSeek network error: {exc}") from exc

        try:
            message = data["choices"][0]["message"]
            content = str(message.get("content") or "").strip()
            tool_calls = []
            for raw_call in message.get("tool_calls") or []:
                function = raw_call.get("function") or {}
                name = str(function.get("name") or "").strip()
                if not name:
                    continue
                raw_arguments = function.get("arguments") or "{}"
                if isinstance(raw_arguments, str):
                    arguments = json.loads(raw_arguments or "{}")
                elif isinstance(raw_arguments, dict):
                    arguments = raw_arguments
                else:
                    arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                tool_calls.append(
                    ToolCall(
                        id=str(raw_call.get("id") or name),
                        name=name,
                        arguments=arguments,
                    )
                )
            return ModelReply(content=content, tool_calls=tool_calls)
        except Exception as exc:
            raise RuntimeError("DeepSeek response shape is invalid") from exc
