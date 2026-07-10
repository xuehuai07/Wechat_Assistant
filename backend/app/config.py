from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    timeout_seconds: int = 60


@dataclass(frozen=True)
class WebConfig:
    host: str
    port: int
    session_secret: str


@dataclass(frozen=True)
class AgentConfig:
    max_context_turns: int = 20
    max_steps: int = 6
    tool_allowlist: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WechatConfig:
    base_url: str
    credentials_path: Path
    text_only: bool = True
    poll_interval_seconds: int = 1
    long_poll_timeout_seconds: int = 35


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: Path


@dataclass(frozen=True)
class LoggingConfig:
    path: Path


@dataclass(frozen=True)
class Settings:
    channel: str
    model: ModelConfig
    web: WebConfig
    agent: AgentConfig
    wechat: WechatConfig
    storage: StorageConfig
    logging: LoggingConfig
    deepseek_api_key: str
    web_password: str
    amap_maps_api_key: str = ""

    def validate(self) -> None:
        missing = []
        if not self.deepseek_api_key:
            missing.append("DEEPSEEK_API_KEY")
        if not self.web_password:
            missing.append("WEB_PASSWORD")
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
        if self.web.host != "127.0.0.1":
            raise RuntimeError("web.host must default to 127.0.0.1 for local private use")

    def public_summary(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "model": {
                "provider": self.model.provider,
                "model": self.model.model,
                "base_url": self.model.base_url,
            },
            "web": {"host": self.web.host, "port": self.web.port},
            "agent": {
                "max_context_turns": self.agent.max_context_turns,
                "max_steps": self.agent.max_steps,
                "tool_allowlist": self.agent.tool_allowlist,
            },
            "wechat": {
                "base_url": self.wechat.base_url,
                "credentials_path": str(self.wechat.credentials_path),
                "text_only": self.wechat.text_only,
            },
            "storage": {"sqlite_path": str(self.storage.sqlite_path)},
        }


def load_settings(config_path: str | Path | None = None, *, validate: bool = True) -> Settings:
    _load_dotenv(PROJECT_ROOT / ".env")
    path = Path(config_path or os.environ.get("APP_CONFIG", PROJECT_ROOT / "config.json"))
    if not path.exists():
        path = PROJECT_ROOT / "config.example.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    settings = Settings(
        channel=data.get("channel", "weixin_ilink"),
        model=ModelConfig(**data["model"]),
        web=WebConfig(**data["web"]),
        agent=AgentConfig(**data.get("agent", {})),
        wechat=WechatConfig(
            base_url=data["wechat"]["base_url"],
            credentials_path=_resolve_path(data["wechat"]["credentials_path"]),
            text_only=bool(data["wechat"].get("text_only", True)),
            poll_interval_seconds=int(data["wechat"].get("poll_interval_seconds", 1)),
            long_poll_timeout_seconds=int(data["wechat"].get("long_poll_timeout_seconds", 35)),
        ),
        storage=StorageConfig(sqlite_path=_resolve_path(data["storage"]["sqlite_path"])),
        logging=LoggingConfig(path=_resolve_path(data.get("logging", {}).get("path", "./runtime/logs/app.log"))),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        web_password=os.environ.get("WEB_PASSWORD", "").strip(),
        amap_maps_api_key=os.environ.get("AMAP_MAPS_API_KEY", "").strip(),
    )
    if validate:
        settings.validate()
    return settings
