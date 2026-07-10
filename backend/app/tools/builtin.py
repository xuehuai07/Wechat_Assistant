from __future__ import annotations

from typing import Any

from ..maps.service import MapService
from ..services.weather import OpenMeteoWeatherService
from .policy import ToolSpec


class WeatherForecastTool:
    name = "weather.get_forecast"
    spec = ToolSpec(
        name=name,
        description="查询明确城市或地点的实时天气与 0-6 天短期预报。地点不明确时不要调用。",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "城市或地点名称，例如 上海、北京、杭州。",
                    "minLength": 2,
                    "maxLength": 80,
                },
                "day_offset": {
                    "type": "integer",
                    "description": "查询日期偏移，0 表示今天，1 表示明天，2 表示后天。",
                    "minimum": 0,
                    "maximum": 6,
                    "default": 0,
                },
            },
            "required": ["location"],
            "additionalProperties": False,
        },
    )

    def __init__(self, weather: OpenMeteoWeatherService, *, enabled: bool = True) -> None:
        self.weather = weather
        self.enabled = enabled

    async def execute(self, params: dict) -> dict:
        if not self.enabled:
            raise RuntimeError("weather is disabled")
        location = str(params.get("location") or "").strip()
        day_offset = int(params.get("day_offset") or 0)
        return await self.weather.weather(location, day_offset=day_offset)


class MapNavigationTool:
    name = "maps.create_navigation_url"
    spec = ToolSpec(
        name=name,
        description="根据本地 profile 中已保存的地点别名生成高德导航 URI。不查询外部地图服务。",
        parameters={
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "目的地别名，必须已经保存在本地 profile。",
                    "minLength": 1,
                    "maxLength": 80,
                },
                "origin": {
                    "type": "string",
                    "description": "可选起点别名，省略时由移动端地图使用当前位置。",
                    "maxLength": 80,
                },
                "mode": {
                    "type": "string",
                    "enum": ["car", "bus", "walk", "ride"],
                    "default": "car",
                },
                "policy": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 3,
                    "default": 0,
                },
                "callnative": {
                    "type": "boolean",
                    "default": True,
                },
            },
            "required": ["destination"],
            "additionalProperties": False,
        },
    )

    def __init__(self, maps: MapService) -> None:
        self.maps = maps

    async def execute(self, params: dict[str, Any]) -> dict:
        return self.maps.navigation_url(
            destination=str(params.get("destination") or "").strip(),
            origin=str(params["origin"]).strip() if params.get("origin") else None,
            mode=params.get("mode") or "car",
            policy=int(params.get("policy") or 0),
            callnative=bool(params.get("callnative", True)),
        )
