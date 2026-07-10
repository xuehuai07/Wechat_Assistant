from __future__ import annotations

import httpx

from ..config import Settings


class DeepSeekClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def chat(self, messages: list[dict[str, str]]) -> str:
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
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            raise RuntimeError("DeepSeek response shape is invalid") from exc
