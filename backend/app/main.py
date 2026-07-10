from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agent.chat_agent import ChatAgent
from .api.routes import router
from .config import PROJECT_ROOT, load_settings
from .db import Database
from .logging_config import configure_logging
from .security import SessionStore
from .services.deepseek import DeepSeekClient
from .tools.policy import ToolRegistry
from .wechat.service import WechatService


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings)
    db = Database(settings.storage.sqlite_path)
    db.initialize()
    tools = ToolRegistry(settings.agent.tool_allowlist)
    deepseek = DeepSeekClient(settings)
    agent = ChatAgent(settings, db, deepseek, tools)
    wechat = WechatService(settings, agent)

    app = FastAPI(title="Private WeChat Agent")
    app.state.settings = settings
    app.state.db = db
    app.state.tools = tools
    app.state.agent = agent
    app.state.wechat = wechat
    app.state.sessions = SessionStore()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    dist = PROJECT_ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
