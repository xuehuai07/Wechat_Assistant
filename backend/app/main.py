from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agent.chat_agent import ChatAgent
from .api.routes import router
from .config import PROJECT_ROOT, load_settings
from .db import Database
from .logging_config import configure_logging
from .maps.service import AmapWebServiceProvider, MapService
from .security import SessionStore
from .services.deepseek import DeepSeekClient
from .services.weather import OpenMeteoWeatherService
from .tools.builtin import MapNavigationTool, WeatherForecastTool
from .tools.policy import ToolRegistry
from .wechat.service import WechatService


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings)
    db = Database(settings.storage.sqlite_path)
    db.initialize()
    maps = MapService(settings.profile.path, AmapWebServiceProvider(settings.amap_maps_api_key))
    deepseek = DeepSeekClient(settings)
    weather = OpenMeteoWeatherService()
    tools = ToolRegistry(settings.agent.tool_allowlist)
    tools.register(WeatherForecastTool(weather, enabled=settings.agent.weather_enabled))
    tools.register(MapNavigationTool(maps))
    agent = ChatAgent(settings, db, deepseek, tools, weather)
    wechat = WechatService(settings, agent)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if wechat.status()["login_status"] == "logged_in":
            await wechat.start_polling()
        yield
        await wechat.stop_polling()

    app = FastAPI(title="Private WeChat Agent", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.tools = tools
    app.state.maps = maps
    app.state.weather = weather
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
    if settings.web.serve_frontend and dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
